(() => {
  const config = JSON.parse(document.getElementById('stand-config').textContent);
  const root = document.getElementById('main'), scene = document.getElementById('spectator-scene');
  const sky = document.getElementById('spectator-sky'), camera = document.getElementById('spectator-camera');
  const status = document.getElementById('spectator-status'), title = document.getElementById('spectator-title');
  const waiting = document.getElementById('spectator-waiting');
  let state, target, connected = false, lastPose = 0, loaded = '', loading = '', failed = '', texture, image, imageURL, request, generation = 0;
  let ready;
  const initialized = new Promise(resolve => { ready = resolve; });
  const start = () => { if (scene.hasLoaded && scene.renderer && sky.getObject3D('mesh')) { scene.setAttribute('xr-mode-ui', 'enabled', false); ready(); } };
  scene.addEventListener('renderstart', start); scene.addEventListener('loaded', start); start();
  const show = text => { status.textContent = text; };
  if (!window.AFRAME) { show('No se pudo iniciar la panorámica. Recarga la pantalla.'); return; }
  const THREE = AFRAME.THREE;
  target = new THREE.Quaternion();
  AFRAME.registerComponent('stand-follow', {
    tick(time, delta) {
      if (lastPose && connected && Date.now() - lastPose < 6000) camera.object3D.quaternion.slerp(target, 1 - Math.exp(-Math.min(delta, 100) / 85));
    }
  });
  camera.setAttribute('stand-follow', '');
  async function receive(data) {
    if (data.type === 'ended') { ++generation; request?.abort(); connected = false; waiting.hidden = false; waiting.querySelector('h1').textContent = 'Gracias por explorar'; waiting.querySelector('p').textContent = 'La sesión ha finalizado.'; show('Sesión finalizada'); return; }
    if (data.type === 'pose') {
      if (!state || data.seq !== state.applied_seq || data.scene !== state.confirmed_scene) return;
      target.fromArray(data.q).normalize(); lastPose = Date.now();
      if (loaded === `${state.confirmed_tour?.id}:${data.scene}`) show('En directo · Mirada del participante');
      return;
    }
    if (data.type !== 'state') return;
    state = data;
    if (!data.confirmed_scene || !data.confirmed_tour) { show(data.content_error || 'Esperando al participante'); return; }
    const item = data.confirmed_tour.scenes.find(s => s.id === data.confirmed_scene);
    if (!item) return;
    title.textContent = `${data.confirmed_tour.name} · ${item.name}`;
    const identifier = `${data.confirmed_tour.id}:${item.id}`;
    if (identifier === loaded || identifier === loading || identifier === failed) return;
    loading = identifier;
    const ticket = ++generation;
    request?.abort(); const requestController = new AbortController(); request = requestController;
    const timeout = setTimeout(() => requestController.abort(), 20000);
    let url, nextImage, nextTexture;
    show('Cargando la escena confirmada…');
    try {
      await initialized;
      if (ticket !== generation) return;
      const response = await fetch(item.panorama, { signal: requestController.signal });
      if (!response.ok) throw new Error();
      url = URL.createObjectURL(await response.blob()); nextImage = new Image(); nextImage.src = url; await nextImage.decode();
      if (ticket !== generation) return;
      if (requestController.signal.aborted) throw new Error();
      if (Math.abs(nextImage.width / (2 * nextImage.height) - 1) > data.confirmed_tour.panorama_ratio_tolerance + 1e-12 || nextImage.width > scene.renderer.capabilities.maxTextureSize) throw new Error();
      nextTexture = new THREE.Texture(nextImage); nextTexture.colorSpace = THREE.SRGBColorSpace; nextTexture.needsUpdate = true;
      const material = sky.getObject3D('mesh').material; material.map = nextTexture; material.color.set('#ffffff'); material.needsUpdate = true;
      texture?.dispose(); if (image) image.src = ''; if (imageURL) URL.revokeObjectURL(imageURL);
      texture = nextTexture; image = nextImage; imageURL = url; nextTexture = nextImage = url = null;
      loaded = identifier; failed = ''; waiting.hidden = true; root.dataset.scene = item.id;
      show('Esperando la mirada del participante…');
    } catch { if (ticket === generation) { failed = identifier; show('No se pudo cargar esta escena. Reintenta cuando vuelva la conexión.'); document.getElementById('spectator-retry').hidden = false; } }
    finally { clearTimeout(timeout); if (ticket === generation) loading = ''; nextTexture?.dispose(); if (nextImage) nextImage.src = ''; if (url) URL.revokeObjectURL(url); }
  }
  const socket = new StandSocket(config, receive, (online, message) => {
    const recovered = online && !connected; connected = online;
    if (!online) show(message);
    else if (recovered) { failed = ''; if (state) receive(state); }
  });
  document.getElementById('spectator-retry').addEventListener('click', event => { failed = ''; event.target.hidden = true; if (state) receive(state); });
  setInterval(() => {
    if (!connected) return;
    if (state?.content_error) show(state.content_error);
    else if (!state?.viewer_connected) show('Visor desconectado · La vista dejó de actualizarse');
    else if (!lastPose || Date.now() - lastPose > 6000) show('Esperando mirada · La vista no se está actualizando');
  }, 1000);
  document.getElementById('spectator-fullscreen').addEventListener('click', async () => {
    try { if (document.fullscreenElement) await document.exitFullscreen(); else await root.requestFullscreen(); }
    catch { show('No se pudo abrir pantalla completa. Usa la opción del navegador.'); }
  });
  document.addEventListener('fullscreenchange', () => document.getElementById('spectator-fullscreen').textContent = document.fullscreenElement ? 'Salir de pantalla completa' : 'Pantalla completa');
  window.addEventListener('pagehide', event => { if (event.persisted) return; ++generation; request?.abort(); texture?.dispose(); if (imageURL) URL.revokeObjectURL(imageURL); });
})();
