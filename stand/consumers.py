import asyncio
import json
import math
import secrets
import time
from contextlib import suppress

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.conf import settings
from django.contrib.auth import get_user
from django.core.exceptions import PermissionDenied, ValidationError
import redis.asyncio as aioredis
from redis.exceptions import RedisError

from . import services as service
from .models import StandSession


class StandConsumer(AsyncJsonWebsocketConsumer):
    """Only snapshots are recovered. Channel messages are wakeups, never queued commands."""
    async def connect(self):
        self.sid = str(self.scope["url_route"]["kwargs"]["sid"])
        self.role = self.scope["url_route"]["kwargs"]["role"]
        self.token = self.scope.get("cookies", {}).get(f"stand_{self.role}_{self.sid}", "")
        self.group = f"stand.{self.sid}"
        self.lease = service.key(self.sid, self.role + "-lease")
        self.nonce = secrets.token_hex(16)
        self.last_seen = time.monotonic()
        self.last_pose = 0
        self.last_sample = -1
        self.message_times = []
        self.last_state = None
        self.task = None
        self.joined = False
        self.redis = aioredis.from_url(settings.STAND_REDIS_URL, decode_responses=True, socket_timeout=2, socket_connect_timeout=2)
        await self.accept()
        try:
            if not await self.authorized():
                await self.close(code=4403)
                return
            if self.role != "operator" and not await self.redis.set(self.lease, self.nonce, nx=True, ex=settings.STAND_HEARTBEAT_TIMEOUT):
                await self.close(code=4409)
                return
            await self.channel_layer.group_add(self.group, self.channel_name)
            self.joined = True
            await self.refresh(force=True)
            pose = await self.redis.get(service.key(self.sid, "pose"))
            if pose and self.role == "spectator":
                await self.send_json(json.loads(pose))
            self.task = asyncio.create_task(self.heartbeat())
        except RedisError:
            await self.close(code=4503)

    @database_sync_to_async
    def authorized(self):
        try:
            session = service.expire(service.get_session(self.sid))
        except (StandSession.DoesNotExist, ValidationError):
            return False
        if self.role == "operator":
            user = self.scope.get("user")
            if not user or not user.is_authenticated:
                return False
            # Reuse Django authentication, including logout/password revocation and fresh permissions.
            from django.contrib.sessions.backends.db import SessionStore
            from types import SimpleNamespace
            request = SimpleNamespace(session=SessionStore(session_key=self.scope["session"].session_key))
            return service.permitted(get_user(request), "view", session)
        return service.credential_ok(session, self.role, self.token)

    async def refresh(self, force=False):
        state = await database_sync_to_async(lambda: service.snapshot(service.get_session(self.sid)))()
        if state["type"] == "ended":
            await self.send_json(state)
            await self.close(code=4401)
            return
        if not await self.authorized():
            await self.close(code=4403)
            return
        if force or state != self.last_state:
            self.last_state = state
            await self.send_json(state)
        else:
            await self.send_json({"type": "heartbeat"})

    async def heartbeat(self):
        try:
            while True:
                await asyncio.sleep(2)
                if time.monotonic() - self.last_seen > settings.STAND_HEARTBEAT_TIMEOUT:
                    await self.close(code=4408)
                    return
                if self.role != "operator":
                    renewed = await self.redis.eval("if redis.call('GET',KEYS[1])==ARGV[1] then return redis.call('EXPIRE',KEYS[1],ARGV[2]) else return 0 end", 1, self.lease, self.nonce, settings.STAND_HEARTBEAT_TIMEOUT)
                    if not renewed:
                        await self.close(code=4409)
                        return
                await self.refresh()
        except asyncio.CancelledError:
            pass
        except (RedisError, StandSession.DoesNotExist):
            await self.close(code=4503)

    async def receive(self, text_data=None, bytes_data=None, **kwargs):
        if bytes_data is not None or not text_data or len(text_data) > 2048:
            await self.close(code=4400)
            return
        now = time.monotonic()
        self.message_times = [t for t in self.message_times if now - t < 1]
        self.message_times.append(now)
        if len(self.message_times) > 25:
            await self.close(code=4429)
            return
        try:
            payload = json.loads(text_data, parse_constant=lambda value: (_ for _ in ()).throw(ValueError()))
            if not isinstance(payload, dict):
                raise ValueError
            kind = payload.get("type")
            if kind == "ping" and set(payload) == {"type"}:
                self.last_seen = now
                await self.send_json({"type": "pong"})
                return
            if self.role != "viewer" or kind not in ("navigate", "applied", "error", "pose"):
                await self.close(code=4403)
                return
            if not await self.authorized():
                await self.close(code=4403)
                return
            self.last_seen = now
            if kind == "pose":
                await self.pose(payload, now)
            else:
                await database_sync_to_async(service.viewer_event)(self.sid, self.token, payload)
                await self.channel_layer.group_send(self.group, {"type": "state.changed"})
        except (ValueError, TypeError, KeyError, ValidationError):
            await self.send_json({"type": "error", "message": "El evento no es válido. No se modificó la sesión."})
        except service.Conflict as exc:
            await self.send_json({"type": "error", "message": str(exc)})
            await self.refresh(force=True)
        except PermissionDenied:
            await self.close(code=4403)
        except (RedisError, StandSession.DoesNotExist):
            await self.close(code=4503)

    async def pose(self, data, now):
        if set(data) != {"type", "seq", "scene", "q", "sample"} or type(data["seq"]) is not int or type(data["sample"]) is not int:
            raise ValueError
        q = data["q"]
        if not isinstance(q, list) or len(q) != 4 or any(type(n) not in (int, float) or not math.isfinite(n) or abs(n) > 1.01 for n in q):
            raise ValueError
        norm = math.sqrt(sum(n * n for n in q))
        if not .9 <= norm <= 1.1:
            raise ValueError
        state = self.last_state or {}
        if state.get("phase") != "running" or state.get("applied_seq") != data["seq"] or state.get("confirmed_scene") != data["scene"] or data["sample"] <= self.last_sample:
            return
        if now - self.last_pose < .08:
            return
        self.last_pose, self.last_sample = now, data["sample"]
        message = {"type": "pose", "seq": data["seq"], "scene": data["scene"], "q": [n / norm for n in q], "at": int(time.time() * 1000)}
        await self.redis.set(service.key(self.sid, "pose"), json.dumps(message), ex=settings.STAND_HEARTBEAT_TIMEOUT)
        await self.channel_layer.group_send(self.group, {"type": "pose.changed", "message": message})

    async def state_changed(self, event):
        try:
            await self.refresh()
        except (RedisError, StandSession.DoesNotExist):
            await self.close(code=4503)

    async def pose_changed(self, event):
        if self.role == "spectator":
            await self.send_json(event["message"])

    async def disconnect(self, code):
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
        try:
            if self.joined:
                await self.channel_layer.group_discard(self.group, self.channel_name)
            if self.role != "operator":
                await self.redis.eval("if redis.call('GET',KEYS[1])==ARGV[1] then return redis.call('DEL',KEYS[1]) else return 0 end", 1, self.lease, self.nonce)
            if self.joined:
                await self.channel_layer.group_send(self.group, {"type": "state.changed"})
        except RedisError:
            pass
        finally:
            await self.redis.aclose()
