"""Real Redis, isolated keys/media/database. No local accounts or content are modified."""
import json
import tempfile
import uuid
from datetime import timedelta

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from tours.models import Category, Scene, Tour
from tours.tests import picture
from . import services as service
from .models import StandSession


class StandTests(TransactionTestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.prefix = 'test-stand-' + uuid.uuid4().hex
        self.overrides = override_settings(MEDIA_ROOT=self.media.name, STAND_REDIS_PREFIX=self.prefix,
            CHANNEL_LAYERS={'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}})
        self.overrides.enable()
        self.user = get_user_model().objects.create_user('operator', is_staff=True)
        self.grant('view', 'add', 'change')
        self.client.force_login(self.user)
        self.category = Category.objects.create(name='Vistas', slug='vistas')
        self.tour = self.make_tour('publico')
        self.a = self.tour.initial_scene
        self.b = Scene.objects.create(tour=self.tour, name='Segunda', key='segunda', panorama=picture())
        self.other = self.make_tour('otro')
        self.draft = Tour.objects.create(name='Borrador privado', slug='privado', description='Privado', category=self.category)
        self.session = service.create(self.user, self.tour.pk)
        self.code = service.store().get(service.key(self.session.pk, 'code'))

    def tearDown(self):
        client = service.store()
        keys = list(client.scan_iter(self.prefix + ':*'))
        if keys:
            client.delete(*keys)
        client.close()
        self.overrides.disable()
        self.media.cleanup()

    def grant(self, *operations):
        self.user.user_permissions.set(Permission.objects.filter(content_type__app_label='stand', codename__in=[x + '_standsession' for x in operations]))
        self.user = get_user_model().objects.get(pk=self.user.pk)

    def make_tour(self, slug):
        t = Tour.objects.create(name=slug, slug=slug, description='Recorrido de prueba', category=self.category)
        t.initial_scene = Scene.objects.create(tour=t, name='Primera', key='primera', panorama=picture())
        t.status = 'available'
        t.save()
        return t

    def url(self, name, *args):
        return reverse('stand:' + name, args=args or [self.session.pk])

    def payload(self, action='start', **changes):
        self.session.refresh_from_db()
        return {'id': str(uuid.uuid4()), 'seq': self.session.seq, 'action': action, 'tour': self.tour.pk, 'scene': None, **changes}

    def pair(self):
        _, token = service.pair(self.code, '127.0.0.1')
        self.session.refresh_from_db()
        return token

    def test_only_public_complete_tours_and_one_active_session(self):
        self.assertEqual({t.pk for t in service.available_tours()}, {self.tour.pk, self.other.pk})
        self.assertEqual(service.create(self.user, self.tour.pk).pk, self.session.pk)
        self.assertEqual(StandSession.objects.count(), 1)
        service.command(self.user, self.session.pk, self.payload('end'))
        with self.assertRaises(ValidationError):
            service.create(self.user, self.draft.pk)
        self.assertNotContains(self.client.get(reverse('stand:index')), self.draft.name)

    def test_staff_permissions_and_owner_are_required(self):
        for perms in [(), ('view',), ('add',)]:
            self.grant(*perms)
            with self.assertRaises(PermissionDenied):
                service.command(self.user, self.session.pk, self.payload())
        self.grant('view', 'add', 'change')
        self.user.is_staff = False
        self.user.save()
        with self.assertRaises(PermissionDenied):
            service.create(self.user, self.tour.pk)
        other = get_user_model().objects.create_user('foreign', is_staff=True)
        other.user_permissions.set(Permission.objects.filter(content_type__app_label='stand'))
        with self.assertRaises(PermissionDenied):
            service.command(other, self.session.pk, self.payload())
        self.assertFalse(service.permitted(other, 'view', self.session))

    def test_anonymous_and_readonly_http_access(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url('operator')).status_code, 302)
        self.assertEqual(self.client.get(self.url('state', self.session.pk, 'operator')).status_code, 403)
        self.client.force_login(self.user)
        self.grant('view')
        self.assertEqual(self.client.get(self.url('operator')).status_code, 200)
        self.assertNotContains(self.client.get(self.url('operator')), 'data-action="start"')
        for name in ('command', 'code', 'open_spectator'):
            r = self.client.post(self.url(name), json.dumps(self.payload()), content_type='application/json')
            self.assertEqual(r.status_code, 403, name)
        self.assertEqual(self.client.post(reverse('stand:index'), {'tour': self.tour.pk}).status_code, 403)

    def test_every_http_write_requires_csrf_and_correct_method(self):
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.user)
        for name in ('command', 'code', 'open_spectator'):
            self.assertEqual(c.post(self.url(name)).status_code, 403)
            self.assertEqual(c.get(self.url(name)).status_code, 405)
        self.assertEqual(c.post(reverse('stand:index')).status_code, 403)
        self.assertEqual(c.post(reverse('stand:join'), {'code': self.code}).status_code, 403)
        self.assertEqual(StandSession.objects.get(pk=self.session.pk).seq, 0)

    def test_pairing_is_single_use_credentials_scoped_httponly_and_not_admin(self):
        c = Client()
        r = c.post(reverse('stand:join'), {'code': self.code.lower()})
        self.assertEqual(r.status_code, 302)
        cookie = r.cookies[f'stand_viewer_{self.session.pk}']
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'], 'Strict')
        self.assertEqual(cookie['path'], f'/stand/{self.session.pk}/')
        self.assertNotIn(settings.SESSION_COOKIE_NAME, r.cookies)
        self.assertEqual(c.get(self.url('viewer')).status_code, 200)
        self.assertEqual(c.get(self.url('spectator')).status_code, 403)
        self.assertEqual(c.get(self.url('state', self.session.pk, 'operator')).status_code, 403)
        self.assertEqual(c.get(self.url('panorama', self.session.pk, self.a.pk)).status_code, 200)
        self.assertEqual(c.get(self.url('panorama', self.session.pk, self.other.initial_scene_id)).status_code, 404)
        self.assertEqual(Client().post(reverse('stand:join'), {'code': self.code}).status_code, 400)
        self.session.refresh_from_db()
        self.assertNotEqual(self.session.viewer_hash, cookie.value)
        self.assertIsNone(self.session.code_hash)
        self.assertNotIn(cookie.value, json.dumps(service.snapshot(self.session)))

    def test_expiry_and_renewal(self):
        StandSession.objects.filter(pk=self.session.pk).update(code_expires_at=timezone.now() - timedelta(seconds=1))
        with self.assertRaises(ValidationError): service.pair(self.code, 'host')
        new = service.regenerate_code(self.user, self.session.pk)
        with self.assertRaises(ValidationError): service.pair(self.code, 'host')
        _, token = service.pair(new, 'host')
        with self.assertRaises(service.Conflict): service.regenerate_code(self.user, self.session.pk)
        StandSession.objects.filter(pk=self.session.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        expired = service.expire(service.get_session(self.session.pk))
        self.assertFalse(service.credential_ok(expired, 'viewer', token))
        self.assertEqual(expired.phase, 'ended')
        self.assertFalse(expired.viewer_hash)

    def test_concurrent_pairing_consumes_code_only_once(self):
        from concurrent.futures import ThreadPoolExecutor
        from django.db import connections
        def attempt():
            try:
                service.pair(self.code, 'concurrent-test')
                return 'paired'
            except ValidationError:
                return 'rejected'
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: attempt(), range(2)))
        self.assertCountEqual(results, ['paired', 'rejected'])

    @override_settings(STAND_PAIR_ATTEMPTS=2)
    def test_pair_attempt_limit(self):
        for _ in range(2):
            with self.assertRaises(ValidationError): service.pair('INVALID!', 'host')
        with self.assertRaisesMessage(service.Conflict, 'Demasiados intentos'):
            service.pair(self.code, 'host')

    def test_confirmed_scene_changes_only_after_matching_ack(self):
        token = self.pair()
        sent = service.command(self.user, self.session.pk, self.payload())
        self.assertIsNone(sent.confirmed_scene)
        self.assertEqual(service.snapshot(sent)['order_status'], 'sent')
        with self.assertRaises(ValidationError):
            service.viewer_event(sent.pk, token, {'type': 'applied', 'seq': sent.seq, 'scene': self.b.key})
        applied = service.viewer_event(sent.pk, token, {'type': 'applied', 'seq': sent.seq, 'scene': self.a.key})
        self.assertEqual(applied.confirmed_scene_id, self.a.pk)
        self.assertEqual(service.snapshot(applied)['order_status'], 'applied')

    def test_stale_commands_events_and_idempotency(self):
        token = self.pair()
        p = self.payload()
        first = service.command(self.user, self.session.pk, p)
        self.assertEqual(service.command(self.user, self.session.pk, p).seq, first.seq)
        with self.assertRaises(service.Conflict): service.command(self.user, first.pk, {**p, 'action': 'restart'})
        with self.assertRaises(service.Conflict): service.command(self.user, first.pk, {**p, 'id': str(uuid.uuid4())})
        next_state = service.command(self.user, first.pk, self.payload('scene', scene=self.b.key))
        service.viewer_event(first.pk, token, {'type': 'applied', 'seq': first.seq, 'scene': self.a.key})
        final = service.viewer_event(first.pk, token, {'type': 'navigate', 'seq': first.seq, 'scene': self.a.key})
        self.assertEqual(final.seq, next_state.seq)
        self.assertEqual(final.scene_id, self.b.pk)
        self.assertIsNone(final.confirmed_scene)

    def test_visitor_navigation_waits_for_ack_and_stays_in_tour(self):
        token = self.pair()
        s = service.command(self.user, self.session.pk, self.payload())
        with self.assertRaises(service.Conflict): service.viewer_event(s.pk, token, {'type': 'navigate', 'seq': s.seq, 'scene': self.b.key})
        service.viewer_event(s.pk, token, {'type': 'applied', 'seq': s.seq, 'scene': self.a.key})
        self.other.initial_scene.key = 'foreign'
        self.other.initial_scene.save()
        with self.assertRaises(ValidationError): service.viewer_event(s.pk, token, {'type': 'navigate', 'seq': s.seq, 'scene': 'foreign'})
        moved = service.viewer_event(s.pk, token, {'type': 'navigate', 'seq': s.seq, 'scene': self.b.key})
        self.assertEqual(moved.action, 'visitor')
        self.assertEqual(moved.confirmed_scene_id, self.a.pk)
        self.assertEqual(moved.scene_id, self.b.pk)

    def test_invalid_operator_targets_and_payloads_rejected(self):
        for value in (None, True, '1', 2**100, self.draft.pk, 99999):
            with self.assertRaises(ValidationError): service.command(self.user, self.session.pk, self.payload('tour', tour=value))
        for value in ('foreign', [], None):
            with self.assertRaises(ValidationError): service.command(self.user, self.session.pk, self.payload('scene', scene=value))
        for p in ({}, self.payload(seq=True), self.payload(id='invalid'), self.payload(action='publish')):
            with self.assertRaises(ValidationError): service.command(self.user, self.session.pk, p)

    def test_error_retains_confirmed_scene_and_recovery_ack_clears_error(self):
        token = self.pair()
        s = service.command(self.user, self.session.pk, self.payload())
        service.viewer_event(s.pk, token, {'type': 'applied', 'seq': s.seq, 'scene': self.a.key})
        s = service.command(self.user, s.pk, self.payload('scene', scene=self.b.key))
        s = service.viewer_event(s.pk, token, {'type': 'error', 'seq': s.seq, 'code': 'load_failed'})
        self.assertEqual(service.snapshot(s)['order_status'], 'error')
        self.assertEqual(s.confirmed_scene_id, self.a.pk)
        s = service.viewer_event(s.pk, token, {'type': 'applied', 'seq': s.seq, 'scene': self.b.key})
        self.assertEqual(s.error, '')

    def test_tour_change_keeps_actual_tour_until_confirmation_and_restart_initial(self):
        token = self.pair()
        s = service.command(self.user, self.session.pk, self.payload())
        service.viewer_event(s.pk, token, {'type': 'applied', 'seq': s.seq, 'scene': self.a.key})
        s = service.command(self.user, s.pk, self.payload('tour', tour=self.other.pk))
        data = service.snapshot(s)
        self.assertEqual(data['tour']['id'], self.other.pk)
        self.assertEqual(data['confirmed_tour']['id'], self.tour.pk)
        service.viewer_event(s.pk, token, {'type': 'applied', 'seq': s.seq, 'scene': self.other.initial_scene.key})
        s = service.command(self.user, s.pk, self.payload('restart'))
        self.assertEqual(s.scene_id, self.other.initial_scene_id)

    def test_withdrawn_content_is_never_exposed_to_guest(self):
        token = self.pair()
        self.tour.status = 'draft'
        self.tour.save()
        data = service.snapshot(service.get_session(self.session.pk))
        self.assertIsNone(data['tour'])
        self.assertTrue(data['content_error'])
        c = Client()
        c.cookies[f'stand_viewer_{self.session.pk}'] = token
        self.assertEqual(c.get(self.url('viewer')).status_code, 403)
        self.assertEqual(c.get(self.url('panorama', self.session.pk, self.a.pk)).status_code, 404)
        with self.assertRaises(ValidationError): service.command(self.user, self.session.pk, self.payload())

    def test_end_revokes_both_credentials_and_deletes_live_pose(self):
        token = self.pair()
        _, spectator = service.spectator_token(self.user, self.session.pk)
        service.store().set(service.key(self.session.pk, 'pose'), '{}')
        s = service.command(self.user, self.session.pk, self.payload('end'))
        self.assertFalse(service.credential_ok(s, 'viewer', token))
        self.assertFalse(service.credential_ok(s, 'spectator', spectator))
        self.assertFalse(service.store().exists(service.key(s.pk, 'pose')))
        self.assertEqual(service.snapshot(s)['type'], 'ended')
        with self.assertRaises(PermissionDenied): service.viewer_event(s.pk, token, {'type': 'navigate', 'seq': s.seq, 'scene': self.a.key})
        with self.assertRaises(service.Conflict): service.command(self.user, s.pk, self.payload())
        self.assertNotEqual(service.create(self.user, self.tour.pk).pk, s.pk)

    def test_reopening_spectator_rotates_credential_and_releases_old_lease(self):
        _, first = service.spectator_token(self.user, self.session.pk)
        service.store().set(service.key(self.session.pk, 'spectator-lease'), 'old-connection', ex=8)
        s, second = service.spectator_token(self.user, self.session.pk)
        self.assertFalse(service.credential_ok(s, 'spectator', first))
        self.assertTrue(service.credential_ok(s, 'spectator', second))
        self.assertFalse(service.store().exists(service.key(s.pk, 'spectator-lease')))

    def communicator(self, role, token='', origin=b'http://127.0.0.1:8000', cookie=None):
        from config.asgi import application
        headers = [(b'origin', origin), (b'host', b'127.0.0.1:8000')]
        if cookie is None: cookie = f'stand_{role}_{self.session.pk}={token}'
        headers.append((b'cookie', cookie.encode()))
        return WebsocketCommunicator(application, f'/stand/{self.session.pk}/socket/{role}/', headers=headers)

    @async_to_sync
    async def socket_check(self, role, token, origin=None, expected=4403):
        ws = self.communicator(role, token, **({'origin': origin} if origin else {}))
        connected, _ = await ws.connect()
        if origin:
            self.assertFalse(connected)
        else:
            self.assertTrue(connected)
            message = await ws.receive_output(timeout=3)
            self.assertEqual(message['type'], 'websocket.close')
            self.assertEqual(message['code'], expected)
        await ws.disconnect()

    def test_websocket_origin_and_role_authorization(self):
        token = self.pair()
        self.socket_check('viewer', token, b'https://hostil.invalid')
        self.socket_check('viewer', 'bad-token')
        self.socket_check('spectator', token)
        self.socket_check('operator', token)

    def test_duplicate_viewer_does_not_evict_original(self):
        token = self.pair()
        @async_to_sync
        async def run():
            first = self.communicator('viewer', token)
            await first.connect()
            self.assertEqual((await first.receive_json_from())['type'], 'state')
            second = self.communicator('viewer', token)
            await second.connect()
            self.assertEqual((await second.receive_output())['code'], 4409)
            await second.disconnect()
            await first.send_json_to({'type': 'ping'})
            # A disconnect notification may yield a state snapshot before pong.
            for _ in range(3):
                if (await first.receive_json_from())['type'] == 'pong': break
            else: self.fail('Original viewer lost its lease')
            await first.disconnect()
        run()

    def test_spectator_cannot_send_navigation_and_viewer_cannot_send_commands(self):
        token = self.pair()
        _, read_token = service.spectator_token(self.user, self.session.pk)
        @async_to_sync
        async def run(role, credential, event):
            ws = self.communicator(role, credential)
            await ws.connect(); await ws.receive_json_from()
            await ws.send_json_to(event)
            self.assertEqual((await ws.receive_output())['code'], 4403)
            await ws.disconnect()
        run('spectator', read_token, {'type': 'navigate', 'seq': 0, 'scene': self.a.key})
        run('viewer', token, {'type': 'end'})

    def test_pose_requires_finite_unit_quaternion_and_current_confirmation(self):
        token = self.pair()
        s = service.command(self.user, self.session.pk, self.payload())
        service.viewer_event(s.pk, token, {'type': 'applied', 'seq': s.seq, 'scene': self.a.key})
        @async_to_sync
        async def run():
            ws = self.communicator('viewer', token)
            await ws.connect(); await ws.receive_json_from()
            pose = {'type': 'pose', 'seq': s.seq, 'scene': self.a.key, 'q': [0, 0, 0, 1], 'sample': 1}
            for q in ([0, 0, 0, 0], [True, 0, 0, 1], [0, 0, 0, float('nan')], [0, 0, 0, float('inf')]):
                await ws.send_to(text_data=json.dumps({**pose, 'q': q}))
                self.assertEqual((await ws.receive_json_from())['type'], 'error')
            await ws.send_json_to({**pose, 'seq': 999})
            await ws.send_json_to(pose)
            await ws.send_json_to({'type': 'ping'})
            self.assertEqual((await ws.receive_json_from())['type'], 'pong')
            await ws.disconnect()
        run()
        stored = json.loads(service.store().get(service.key(s.pk, 'pose')))
        self.assertEqual(stored['q'], [0, 0, 0, 1])
        self.assertLessEqual(service.store().ttl(service.key(s.pk, 'pose')), 8)
        self.assertNotIn('q', {f.name for f in StandSession._meta.fields})

    def test_operator_socket_revoked_after_logout(self):
        cookie = f'{settings.SESSION_COOKIE_NAME}={self.client.cookies[settings.SESSION_COOKIE_NAME].value}'
        @async_to_sync
        async def run():
            from channels.db import database_sync_to_async
            ws = self.communicator('operator', cookie=cookie)
            await ws.connect(); await ws.receive_json_from()
            await database_sync_to_async(self.client.logout)()
            self.assertEqual((await ws.receive_output(timeout=4))['code'], 4403)
            await ws.disconnect()
        run()
