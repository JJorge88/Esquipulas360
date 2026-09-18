(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const root = $('main');
  const inStand = Boolean($('stand-config'));
  let standReady;
  const readyForStand = new Promise(resolve => { standReady = resolve; });
  let standConnected = false, standRunning = false, standFinished = false;
  const scene = $('panorama-scene');
  const status = $('viewer-status');
  const retry = $('retry');
  const select = $('scene-select');
  const vrButton = $('enter-vr');
  const vrMessage = $('vr-message');
  const infoButton = $('info-toggle');
  const info = $('info-panel');
  const toast = message => {
    $('viewer-toast').textContent = message;
    $('viewer-toast').hidden = false;
    clearTimeout(toast.timeout);
    toast.timeout = setTimeout(() => { $('viewer-toast').hidden = true; }, 7000);
  };
  const showStatus = (title, message, error = false) => {
    status.hidden = false;
    status.setAttribute('aria-busy', String(!error));
    $('status-title').textContent = title;
    $('status-message').textContent = message;
    $('loading-ring').hidden = error;
    retry.hidden = !error;
  };
  const toggleInfo = open => {
    info.hidden = !open;
    infoButton.setAttribute('aria-expanded', String(open));
    if (open) $('info-close').focus(); else infoButton.focus();
  };
  infoButton.addEventListener('click', () => toggleInfo(info.hidden));
  $('info-close').addEventListener('click', () => toggleInfo(false));
  document.addEventListener('keydown', event => { if (event.key === 'Escape' && !info.hidden) toggleInfo(false); });
  const fullscreen = $('fullscreen');
  if (!document.fullscreenEnabled) {
    fullscreen.disabled = true;
    fullscreen.setAttribute('aria-label', 'Pantalla completa no disponible en este navegador');
  }
  fullscreen.addEventListener('click', async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await root.requestFullscreen();
    } catch { toast('No se pudo abrir la pantalla completa. Puedes continuar aquí.'); }
  });
  document.addEventListener('fullscreenchange', () => {
    const active = Boolean(document.fullscreenElement);
    fullscreen.setAttribute('aria-pressed', String(active));
    fullscreen.setAttribute('aria-label', active ? 'Salir de pantalla completa' : 'Pantalla completa');
  });
  if (!window.AFRAME) {
    showStatus('El visor no pudo iniciarse', 'No se cargó A-Frame. Comprueba la conexión y vuelve a intentarlo.', true);
    retry.addEventListener('click', () => location.reload());
    vrButton.textContent = 'VR no disponible';
    vrMessage.textContent = 'El visor necesita terminar de cargar.';
    return;
  }
  const THREE = AFRAME.THREE;
  // A-Frame 1.8 seeds scene defaults when upgrading deferred markup.
  // Reapply these settings before the scene initializes its UI and sensors.
  scene.setAttribute('xr-mode-ui', 'enabled', false);
  scene.setAttribute('device-orientation-permission-ui', 'enabled', false);
  let tour = JSON.parse($('tour-data').textContent);
  const scenes = new Map(tour.scenes.map(item => [item.id, item]));
  const sky = $('panorama-sky');
  const rig = $('camera-rig');
  const camera = $('tour-camera');
  const hotspots = $('hotspots');
  const vrNav = $('vr-navigation');
  let currentId = null, pendingId = tour.initial_scene;
  let activeTexture = null, activeImage = null, activeUrl = null;
  let controller = null, generation = 0, initialized = false, xrSupported = false, xrPending = false;
  // Ignore A-Frame's automatic immersive-navigation events. Only our button may request VR.
  const enterVR = scene.enterVR.bind(scene);
  let vrGesture = false;
  scene.enterVR = (...args) => vrGesture ? enterVR(...args) : Promise.resolve();

  function label(text, position, width = 1, action = null, accent = false) {
    const el = document.createElement('a-entity');
    el.setAttribute('position', position);
    el.setAttribute('tour-label', { text, width, height: .26, accent });
    if (action) {
      el.classList.add('vr-clickable');
      el.dataset.action = action;
      el.addEventListener('click', () => navigateVR(action));
    }
    return el;
  }
  const vrTitle = label('Cargando escena…', '0 0.48 0', 2.7);
  const vrStatus = label(tour.status === 'demo' ? 'Demo técnica · No es un lugar real' : tour.name, '0 0.15 0', 2.7);
  vrNav.append(vrTitle, vrStatus);
  let vrSceneButtons = tour.scenes.map((item, index) => label(item.name, `${(index - (tour.scenes.length - 1) / 2) * 1.38} -0.18 0`, 1.3, `scene:${item.id}`, true));
  vrNav.append(...vrSceneButtons);
  vrNav.append(label('Inicio', '-1.02 -0.52 0', .94, 'start'), label(root.dataset.backUrl ? 'Editor' : 'Explorar', '0 -0.52 0', .94, 'explore'), label('Salir de VR', '1.02 -0.52 0', .94, 'exit'));
  const vrRetry = label('Reintentar carga', '0 0.8 0', 1.8, 'retry', true);
  vrRetry.setAttribute('visible', false);
  vrNav.append(vrRetry);

  async function navigateVR(action) {
    if (action.startsWith('scene:')) return loadScene(action.slice(6));
    if (action === 'start') return loadScene(tour.initial_scene);
    if (action === 'retry') {
      if (inStand) return window.dispatchEvent(new Event('stand:retry'));
      return loadScene(pendingId);
    }
    try {
      await scene.exitVR();
      if (action === 'explore') location.assign(root.dataset.backUrl || '/explorar/');
    } catch { toast('No se pudo cerrar VR. Usa el botón del sistema del visor.'); }
  }

  function setVRStatus(text, error = false) {
    vrStatus.setAttribute('tour-label', 'text', text);
    vrRetry.setAttribute('visible', error);
  }

  function releasePanorama() {
    if (activeTexture) activeTexture.dispose();
    if (activeImage) activeImage.src = '';
    if (activeUrl) URL.revokeObjectURL(activeUrl);
    activeTexture = activeImage = activeUrl = null;
  }

  function renderHotspots(item) {
    hotspots.replaceChildren();
    for (const point of item.hotspots) {
      const marker = document.createElement('a-entity');
      marker.setAttribute('position', point.position.join(' '));
      marker.setAttribute('tour-face-camera', '');
      marker.dataset.hotspot = point.id;
      const circle = document.createElement('a-circle');
      circle.setAttribute('radius', .16);
      circle.setAttribute('color', '#fece57');
      circle.setAttribute('material', 'shader: flat; side: double');
      circle.classList.add('hotspot', 'vr-clickable');
      const ring = document.createElement('a-ring');
      ring.setAttribute('radius-inner', .2); ring.setAttribute('radius-outer', .215);
      ring.setAttribute('color', '#fbf9f6'); ring.setAttribute('material', 'shader: flat; side: double');
      const caption = label(point.label, '0 -0.39 0', 1.55);
      caption.classList.add('hotspot', 'vr-clickable');
      circle.addEventListener('click', () => loadScene(point.destination));
      caption.addEventListener('click', () => loadScene(point.destination));
      marker.append(circle, ring, caption);
      hotspots.append(marker);
      const target = new THREE.Vector3();
      scene.camera.getWorldPosition(target);
      marker.object3D.lookAt(target);
    }
    const next = item.hotspots[0];
    $('next-hotspot').hidden = !next;
    if (next) {
      $('next-hotspot').textContent = `${next.label} ↗`;
      $('next-hotspot').onclick = () => loadScene(next.destination);
    }
  }

  function setOrientation(item) {
    PanoramaTools.setOrientation(scene, rig, camera, item.orientation);
  }

  function setAudio(item) {
    const container = $('audio-container');
    const old = container.querySelector('audio');
    if (old) { old.pause(); old.removeAttribute('src'); old.load(); }
    container.replaceChildren();
    if (item.audio) {
      const audio = document.createElement('audio');
      audio.controls = true; audio.preload = 'none'; audio.src = item.audio;
      audio.setAttribute('aria-label', `Audio de ${item.name}`);
      audio.addEventListener('error', () => toast('No se pudo cargar el audio de esta escena.'));
      container.append(audio);
    }
  }

  async function loadScene(id, authoritative = false) {
    if (inStand && !authoritative) {
      if (standConnected && standRunning) window.dispatchEvent(new CustomEvent('stand:navigate', { detail: { scene: id } }));
      else toast('Espera a que el operador inicie el recorrido y haya conexión.');
      return false;
    }
    const item = scenes.get(id);
    if (!item) return;
    pendingId = id;
    const ticket = ++generation;
    controller?.abort();
    const requestController = new AbortController();
    controller = requestController;
    const timeout = setTimeout(() => requestController.abort(), 20000);
    let url = null, image = null, texture = null;
    showStatus('Abriendo otra perspectiva…', `Cargando ${item.name.toLowerCase()}.`);
    root.dataset.loading = 'true';
    hotspots.setAttribute('visible', false);
    setVRStatus(`Cargando ${item.name}…`);
    try {
      const response = await fetch(item.panorama, { signal: requestController.signal });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const blob = await response.blob();
      url = URL.createObjectURL(blob);
      image = new Image(); image.src = url;
      await image.decode();
      if (ticket !== generation) return;
      if (requestController.signal.aborted) throw new Error('Tiempo de carga agotado.');
      const tolerance = tour.panorama_ratio_tolerance ?? 0;
      if (Math.abs(image.naturalWidth / (image.naturalHeight * 2) - 1) > tolerance + 1e-12) throw new Error('La panorámica debe tener proporción 2:1 dentro de la tolerancia configurada.');
      if (image.naturalWidth > scene.renderer.capabilities.maxTextureSize) throw new Error('La panorámica supera la resolución admitida por este dispositivo.');
      texture = new THREE.Texture(image);
      texture.colorSpace = THREE.SRGBColorSpace;
      texture.needsUpdate = true;
      if (inStand) {
        scene.setAttribute('stand-transition', 'active', true);
        await new Promise(resolve => setTimeout(resolve, 160));
        if (ticket !== generation) return false;
      }
      const material = sky.getObject3D('mesh').material;
      material.map = texture; material.color.set('#ffffff'); material.needsUpdate = true;
      releasePanorama();
      activeTexture = texture; activeImage = image; activeUrl = url;
      texture = image = url = null;
      currentId = id;
      select.value = id;
      $('scene-counter').textContent = `${String(tour.scenes.findIndex(s => s.id === id) + 1).padStart(2, '0')} / ${String(tour.scenes.length).padStart(2, '0')}`;
      $('scene-description').textContent = item.text || tour.description;
      vrTitle.setAttribute('tour-label', 'text', item.name);
      setVRStatus(tour.status === 'demo' ? 'Demo técnica · No es un lugar real' : tour.name);
      if (!inStand) setOrientation(item); // Stand commands never rotate the participant's head/rig.
      renderHotspots(item);
      setAudio(item);
      hotspots.setAttribute('visible', true);
      scene.object3D.updateMatrixWorld(true);
      scene.components.raycaster.refreshObjects();
      scene.components.raycaster.checkIntersections();
      root.dataset.scene = id;
      status.hidden = true;
      status.setAttribute('aria-busy', 'false');
      root.dataset.loading = 'false';
      return true;
    } catch (error) {
      if (ticket !== generation) return;
      const reason = error.message.includes('2:1') || error.message.includes('resolución') ? error.message : 'El archivo no está disponible, la conexión falló o la carga tardó demasiado.';
      showStatus('No pudimos abrir esta escena', `${reason} Puedes volver a intentarlo.`, true);
      setVRStatus('Error de carga. Selecciona Reintentar u otra escena.', true);
      root.dataset.loading = 'error';
      return false;
    } finally {
      if (inStand && ticket === generation) scene.setAttribute('stand-transition', 'active', false);
      clearTimeout(timeout);
      texture?.dispose();
      if (image) image.src = '';
      if (url) URL.revokeObjectURL(url);
    }
  }

  async function detectVR() {
    xrSupported = false;
    if (!window.isSecureContext) {
      vrMessage.textContent = 'VR necesita HTTPS válido. Puedes continuar en pantalla normal.';
    } else if (!navigator.xr) {
      vrMessage.textContent = 'VR no disponible en este navegador. Explora en pantalla normal.';
    } else {
      try {
        xrSupported = await navigator.xr.isSessionSupported('immersive-vr');
        vrMessage.textContent = xrSupported ? 'Conecta tus mandos y entra cuando estés listo.' : 'No se detectó un visor VR compatible. Continúa en pantalla normal.';
      } catch {
        vrMessage.textContent = 'No se pudo comprobar VR. Revisa los permisos del navegador; puedes continuar en pantalla normal.';
      }
    }
    vrButton.disabled = !xrSupported || !initialized || xrPending || standFinished;
    vrButton.textContent = xrSupported ? 'Entrar en VR' : 'VR no disponible';
  }
  vrButton.addEventListener('click', async () => {
    if (!xrSupported || xrPending || standFinished) return;
    xrPending = true; vrButton.disabled = true; vrButton.textContent = 'Abriendo VR…';
    try {
      vrGesture = true;
      const request = scene.enterVR();
      vrGesture = false;
      await request;
      if (!scene.renderer.xr.isPresenting) {
        await scene.exitVR();
        vrMessage.textContent = 'No se pudo iniciar una sesión inmersiva. Puedes seguir en pantalla normal.';
      }
    } catch (error) {
      vrMessage.textContent = ['NotAllowedError', 'SecurityError'].includes(error.cause?.name || error.name)
        ? 'Permiso de VR denegado o cancelado. Puedes reintentarlo o seguir aquí.'
        : 'La sesión VR se canceló o no pudo iniciarse. Puedes reintentarlo o seguir aquí.';
    } finally {
      vrGesture = false;
      xrPending = false; vrButton.disabled = !xrSupported || standFinished; vrButton.textContent = 'Entrar en VR';
    }
  });
  scene.addEventListener('enter-vr', () => {
    // A-Frame can also call enter-vr for a nonimmersive fullscreen fallback.
    if (!scene.renderer.xr.isPresenting) return;
    vrNav.setAttribute('visible', true);
    root.classList.add('is-immersive');
    const audio = $('audio-container').querySelector('audio');
    audio?.pause();
  });
  scene.addEventListener('exit-vr', () => {
    vrNav.setAttribute('visible', false);
    root.classList.remove('is-immersive');
    vrMessage.textContent = 'Has vuelto a la pantalla normal. Puedes entrar en VR de nuevo.';
  });
  navigator.xr?.addEventListener('devicechange', detectVR);
  select.addEventListener('change', () => loadScene(select.value));
  retry.addEventListener('click', () => {
    if (inStand && initialized) window.dispatchEvent(new Event('stand:retry'));
    else if (!initialized) location.reload(); else loadScene(pendingId);
  });

  if (inStand) window.ES360Viewer = {
    ready: readyForStand,
    async apply(nextTour, id, reset = false) {
      await readyForStand;
      if (standFinished || !initialized || scene.renderer.getContext().isContextLost()) return false;
      const rebuildControls = tour.id !== nextTour.id || JSON.stringify(tour.scenes.map(item => [item.id, item.name])) !== JSON.stringify(nextTour.scenes.map(item => [item.id, item.name]));
      tour = nextTour;
      scenes.clear(); tour.scenes.forEach(item => scenes.set(item.id, item));
      document.querySelector('.viewer-top-title h1').textContent = tour.name;
      if (rebuildControls) {
        select.replaceChildren(...tour.scenes.map(item => new Option(item.name, item.id)));
        vrSceneButtons.forEach(button => button.remove());
        vrSceneButtons = tour.scenes.map((item, index) => label(item.name, `${(index - (tour.scenes.length - 1) / 2) * 1.38} -0.18 0`, 1.3, `scene:${item.id}`, true));
        vrNav.append(...vrSceneButtons);
      }
      if (reset) { info.hidden = true; infoButton.setAttribute('aria-expanded', 'false'); $('viewer-toast').hidden = true; }
      return loadScene(id, true);
    },
    connection(connected, running, message) {
      standConnected = connected; standRunning = running;
      if (message) setVRStatus(message);
    },
    finish(message) {
      standFinished = true;
      standConnected = standRunning = false;
      ++generation; controller?.abort();
      scene.setAttribute('stand-transition', 'active', false);
      hotspots.setAttribute('visible', false);
      vrSceneButtons.forEach(button => button.setAttribute('visible', false));
      vrButton.disabled = true;
      showStatus('Sesión finalizada', message, false); $('loading-ring').hidden = true;
      setVRStatus('Sesión finalizada · Puedes salir de VR');
    },
    get currentScene() { return currentId; },
    get loading() { return root.dataset.loading !== 'false'; },
  };

  let startupTimeout = setTimeout(() => {
    if (!initialized) showStatus('El visor no pudo iniciarse', 'Comprueba que WebGL esté disponible en tu navegador y vuelve a intentarlo.', true);
  }, 15000);
  function start() {
    if (initialized) return;
    if (!scene.hasLoaded || !scene.renderer || !sky.getObject3D('mesh')) return;
    initialized = true;
    clearTimeout(startupTimeout);
    scene.setAttribute('xr-mode-ui', 'enabled', false);
    // Initialize after the scene's permission component exists (A-Frame 1.8 mobile lifecycle).
    // Touch and mouse need no motion-sensor permission; WebXR provides the headset pose.
    camera.setAttribute('look-controls', { pointerLockEnabled: false, magicWindowTrackingEnabled: false });
    PanoramaTools.touchPitch(scene, camera);
    scene.canvas.setAttribute('aria-label', 'Panorama 360 grados. Arrastra para mirar o usa el selector de escenas.');
    scene.canvas.addEventListener('webglcontextlost', event => {
      event.preventDefault();
      initialized = false;
      controller?.abort();
      if (inStand) window.dispatchEvent(new Event('stand:graphics-error'));
      showStatus('La vista 360° se interrumpió', 'Se perdió la conexión con los gráficos del dispositivo. Reintenta para recargar el visor.', true);
    });
    if (inStand) {
      if (!standFinished) showStatus('Listo para el stand', 'Espera a que el operador inicie el recorrido.');
      $('loading-ring').hidden = true;
      if (!standFinished) setVRStatus('Stand · Esperando al operador');
      standReady();
    } else loadScene(tour.initial_scene);
    detectVR();
  }
  scene.addEventListener('loaded', start, { once: true });
  scene.addEventListener('renderstart', start, { once: true });
  if (scene.hasLoaded) start();
  detectVR();
  window.addEventListener('pagehide', event => {
    if (inStand && event.persisted) return;
    ++generation; controller?.abort(); releasePanorama();
    const audio = $('audio-container').querySelector('audio'); audio?.pause();
    clearTimeout(startupTimeout); clearTimeout(toast.timeout);
  });
  window.addEventListener('pageshow', event => { if (!inStand && event.persisted && initialized) loadScene(currentId || tour.initial_scene); });
})();
