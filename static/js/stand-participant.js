(() => {
  const config = JSON.parse(document.getElementById('stand-config').textContent);
  const player = window.ES360Viewer;
  if (!player || !window.AFRAME) return;
  const scene = document.getElementById('panorama-scene');
  const badge = document.getElementById('stand-connection');
  let state, connected = false, applied = -1, applying = -1, failed = -1, generation = 0, sample = 0, lastSent = 0;
  const info = text => { badge.textContent = text; };
  const socket = new StandSocket(config, receive, (online, message) => {
    if (online && !connected) failed = -1;
    connected = online;
    player.connection(online, state?.phase === 'running', online ? '' : message);
    info(online && state?.phase === 'waiting' ? 'Visor vinculado · Esperando al operador' : message);
  });
  async function receive(data) {
    if (data.type === 'ended') { ++generation; connected = false; state = null; player.finish('Gracias por explorar Esquipulas. Solicita una nueva sesión al operador.'); info('Sesión finalizada'); return; }
    if (data.type === 'error') { info(data.message); return; }
    if (data.type !== 'state') return;
    state = data;
    if (data.content_error) { ++generation; player.connection(false, false, data.content_error); info(data.content_error); return; }
    player.connection(connected, data.phase === 'running', data.phase === 'waiting' ? 'Stand · Esperando al operador' : 'Stand conectado · Explora libremente');
    info(data.phase === 'waiting' ? `Vinculado · ${data.tour.name} · Esperando al operador` : `Conectado · ${data.tour.name}`);
    if (data.phase !== 'running' || !data.tour) return;
    if (applied === data.seq && player.currentScene === data.scene) {
      if (data.applied_seq !== data.seq) socket.send({ type: 'applied', seq: data.seq, scene: data.scene });
      return;
    }
    if (applying === data.seq || failed === data.seq) return;
    const ticket = ++generation;
    applying = data.seq;
    const success = await player.apply(data.tour, data.scene, data.action === 'restart');
    if (ticket !== generation) return;
    applying = -1;
    if (success) {
      applied = data.seq; failed = -1;
      socket.send({ type: 'applied', seq: data.seq, scene: data.scene });
    } else {
      failed = data.seq;
      socket.send({ type: 'error', seq: data.seq, code: 'load_failed' });
      info('No se pudo cargar la escena. El operador recibió el error. Puedes reintentar.');
    }
  }
  window.addEventListener('stand:navigate', event => {
    if (connected && state?.phase === 'running' && applied === state.seq && !player.loading) socket.send({ type: 'navigate', seq: applied, scene: event.detail.scene });
  });
  window.addEventListener('stand:retry', () => { failed = applying = -1; if (state) receive(state); });
  window.addEventListener('stand:graphics-error', () => { if (state) socket.send({ type: 'error', seq: state.seq, code: 'webgl_lost' }); });
  AFRAME.registerComponent('stand-head-pose', {
    tock(time) {
      if (!connected || state?.phase !== 'running' || applied !== state.seq || player.loading || time - lastSent < 100) return;
      lastSent = time;
      socket.send({ type: 'pose', seq: applied, scene: player.currentScene, q: PanoramaTools.worldQuaternion(scene).toArray(), sample: ++sample });
    }
  });
  player.ready.then(() => scene.setAttribute('stand-head-pose', ''));
})();
