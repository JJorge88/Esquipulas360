(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const config = JSON.parse($('editor-data').textContent);
  const permissions = config.permissions;
  const root = $('main'), scene = $('editor-scene'), sky = $('editor-sky');
  const rig = $('editor-rig'), camera = $('editor-camera'), markers = $('editor-markers');
  const form = $('point-form'), feedback = $('editor-feedback');
  const labelInput = $('point-label'), destinationInput = $('point-destination');
  let points = config.points, savedOrientation = config.scene.orientation;
  let draft = null, pendingOrientation = null, placement = null, busy = false, loaded = false, started = false;
  let texture = null, objectURL = null, panoramaImage = null, controller = null, generation = 0, allowLeave = false;
  const pointFields = ['label', 'destination', 'yaw', 'pitch'];
  const pointDirty = () => Boolean(draft && (!draft.id || pointFields.some(key => draft[key] !== points.find(p => p.id === draft.id)?.[key])));
  const dirty = () => pointDirty() || Boolean(pendingOrientation);
  const message = (text, error = false) => { feedback.textContent = text; feedback.dataset.error = String(error); };
  const showLoading = (text, error = false) => {
    $('panorama-status').hidden = false; $('panorama-message').textContent = text;
    $('retry-panorama').hidden = !error; root.dataset.loading = error ? 'error' : 'true';
  };
  for (const destination of config.destinations) {
    const option = document.createElement('option');
    option.value = destination.id; option.textContent = destination.name;
    destinationInput.append(option);
  }
  function refresh() {
    root.dataset.dirty = String(dirty()); root.dataset.placement = String(Boolean(placement));
    $('pending-state').textContent = busy ? 'Guardando…' : dirty() ? 'Cambios pendientes de guardar' : 'Sin cambios pendientes';
    $('mode-hint').textContent = placement ? 'Haz un clic o toque breve para colocar el punto. Arrastrar solo cambia la vista.' : 'Arrastra para mirar. Selecciona un punto para editarlo.';
    $('point-count').textContent = points.length;
    $('empty-points').hidden = points.length > 0;
    $('point-list').replaceChildren(...points.map(point => {
      const li = document.createElement('li'), button = document.createElement('button');
      button.type = 'button'; button.textContent = point.label; button.dataset.pointId = point.id;
      button.setAttribute('aria-pressed', String(draft?.id === point.id)); button.disabled = busy;
      button.addEventListener('click', () => selectPoint(point, true)); li.append(button); return li;
    }));
    form.hidden = !draft;
    const editable = draft && (draft.id ? permissions.change : permissions.add);
    labelInput.disabled = destinationInput.disabled = busy || !editable;
    $('add-point').disabled = busy || !loaded || !permissions.add || !config.destinations.length;
    $('add-point').title = config.destinations.length ? '' : 'Crea otra escena en este recorrido antes de añadir un punto.';
    $('cancel-placement').hidden = !placement; $('cancel-placement').disabled = busy;
    $('move-point').disabled = busy || !loaded || !editable;
    $('save-point').disabled = busy || !pointDirty() || Boolean(placement) || !editable;
    $('save-point').textContent = busy ? 'Guardando…' : 'Guardar punto';
    $('cancel-point').disabled = busy;
    $('delete-point').hidden = !draft?.id || !permissions.delete;
    $('delete-point').disabled = busy;
    $('capture-orientation').disabled = busy || !loaded || !permissions.orientation;
    $('restore-orientation').disabled = busy || !loaded;
    $('orientation-actions').hidden = !pendingOrientation;
    $('save-orientation').disabled = $('cancel-orientation').disabled = busy;
    const orientation = pendingOrientation || savedOrientation;
    $('orientation-value').textContent = `${pendingOrientation ? 'Pendiente' : 'Guardada'}: horizontal ${orientation.yaw.toFixed(1)}° · vertical ${orientation.pitch.toFixed(1)}°`;
    if (draft) {
      $('point-form-title').textContent = draft.id ? 'Editar punto' : 'Nuevo punto · vista previa';
      $('point-position').textContent = `Posición: horizontal ${draft.yaw.toFixed(1)}° · vertical ${draft.pitch.toFixed(1)}°`;
    }
    renderMarkers();
  }
  function fillForm() {
    labelInput.value = draft?.label || '';
    destinationInput.value = draft?.destination || '';
  }
  function mayDiscardPoint() {
    if (busy) { message('Espera a que termine el guardado.'); return false; }
    return !pointDirty() || window.confirm('Hay cambios pendientes en este punto. ¿Descartarlos?');
  }
  function selectPoint(point, center = false) {
    if (draft?.id === point.id && !placement) return;
    if (!mayDiscardPoint()) return;
    draft = { ...point }; placement = null; fillForm();
    if (center && loaded) PanoramaTools.setOrientation(scene, rig, camera, point);
    refresh();
    message('Punto seleccionado. Puedes editarlo; aquí no se activa la navegación.');
  }
  function renderMarkers() {
    if (!loaded) return;
    markers.replaceChildren();
    const visible = points.filter(p => p.id !== draft?.id);
    if (draft) visible.push(draft);
    for (const point of visible) {
      const marker = document.createElement('a-entity');
      marker.dataset.point = String(point.id || 'new');
      marker.dataset.yaw = point.yaw; marker.dataset.pitch = point.pitch;
      marker.setAttribute('position', PanoramaTools.position(point.yaw, point.pitch).toArray().join(' '));
      marker.setAttribute('tour-face-camera', '');
      const circle = document.createElement('a-circle');
      circle.setAttribute('radius', .16); circle.setAttribute('color', point === draft ? '#fece57' : '#fbf9f6');
      circle.setAttribute('material', 'shader: flat; side: double');
      const ring = document.createElement('a-ring');
      ring.setAttribute('radius-inner', .2); ring.setAttribute('radius-outer', .215);
      ring.setAttribute('color', '#fece57'); ring.setAttribute('material', 'shader: flat; side: double');
      const caption = document.createElement('a-entity');
      caption.setAttribute('position', '0 -0.39 0');
      caption.setAttribute('tour-label', { text: point.label || 'Nuevo punto', width: 1.55, height: .26, accent: point === draft });
      marker.append(circle, ring, caption); markers.append(marker);
      marker.object3D.userData.pointId = point.id;
      marker.object3D.lookAt(new AFRAME.THREE.Vector3(0, 0, 0));
    }
  }
  $('add-point').addEventListener('click', () => {
    if (!mayDiscardPoint()) return;
    draft = null; placement = 'new'; fillForm(); refresh();
    message('Modo Añadir punto: haz clic en la panorámica para elegir su posición.');
  });
  $('move-point').addEventListener('click', () => { placement = 'move'; refresh(); message('Haz clic en la nueva posición. Tu punto no cambiará en la base hasta guardar.'); });
  $('cancel-placement').addEventListener('click', () => { placement = null; refresh(); message('Selección de ubicación cancelada.'); });
  $('cancel-point').addEventListener('click', () => {
    if (!mayDiscardPoint()) return;
    draft = null; placement = null; fillForm(); refresh(); message('Edición del punto cancelada.');
  });
  const editFields = () => {
    if (!draft) return;
    draft.label = labelInput.value; draft.destination = Number(destinationInput.value) || null;
    refresh();
  };
  labelInput.addEventListener('input', editFields); destinationInput.addEventListener('change', editFields);

  async function request(url, method, payload) {
    const abort = new AbortController(), timeout = setTimeout(() => abort.abort(), 20000);
    try {
      const response = await fetch(url, { method, credentials: 'same-origin', mode: 'same-origin', signal: abort.signal,
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': form.querySelector('[name=csrfmiddlewaretoken]').value }, body: JSON.stringify(payload) });
      if (!response.headers.get('content-type')?.includes('application/json')) {
        const reason = response.redirected ? 'La sesión puede haber caducado. Inicia sesión en otra pestaña y reintenta.'
          : response.status === 403 ? 'No se pudo autorizar el guardado. Revisa tus permisos o inicia sesión de nuevo en otra pestaña.'
          : response.status === 404 ? 'La escena o el punto ya no existe. Revisa la versión guardada en otra pestaña.'
          : 'El servidor no pudo confirmar la operación. Reintenta cuando se recupere la conexión.';
        throw new Error(reason);
      }
      const body = await response.json();
      if (!response.ok) throw new Error([body.error, ...Object.values(body.errors || {}).flat()].filter(Boolean).join(' '));
      return body;
    } finally { clearTimeout(timeout); }
  }
  async function save(operation) {
    if (busy) return;
    busy = true; refresh(); message('Guardando en el servidor…');
    try { await operation(); }
    catch (error) {
      const text = error.name === 'AbortError' || error instanceof TypeError ? 'No se pudo confirmar el guardado por un problema de conexión. Reintenta.' : error.message;
      message(`${text} Tus cambios siguen en pantalla.`, true);
    } finally { busy = false; refresh(); feedback.focus({ preventScroll: true }); }
  }
  form.addEventListener('submit', event => {
    event.preventDefault();
    if (!draft || placement || !form.reportValidity()) return;
    save(async () => {
      const payload = Object.fromEntries(pointFields.map(key => [key, draft[key]]));
      const url = draft.id ? `${config.urls.points}${draft.id}/` : config.urls.points;
      if (draft.id) payload.revision = draft.revision; else payload.key = draft.key;
      const body = await request(url, draft.id ? 'PATCH' : 'POST', payload);
      if (!body.point?.id) throw new Error('El servidor no confirmó el punto.');
      points = [...points.filter(p => p.id !== body.point.id), body.point];
      draft = { ...body.point }; fillForm(); message('Punto guardado.');
    });
  });
  $('delete-point').addEventListener('click', () => {
    if (!draft?.id || !window.confirm(`¿Eliminar el punto «${draft.label}»?${pointDirty() ? ' Se descartarán también sus cambios pendientes.' : ''}`)) return;
    save(async () => {
      const body = await request(`${config.urls.points}${draft.id}/`, 'DELETE', { revision: draft.revision });
      if (body.deleted !== draft.id) throw new Error('El servidor no confirmó la eliminación.');
      points = points.filter(p => p.id !== draft.id); draft = null; placement = null;
      fillForm(); message('Punto eliminado.');
    });
  });
  $('capture-orientation').addEventListener('click', () => {
    pendingOrientation = { ...PanoramaTools.currentOrientation(scene), revision: savedOrientation.revision };
    refresh(); message('Vista seleccionada. Pulsa Guardar orientación para confirmarla.');
  });
  function restoreOrientation() {
    pendingOrientation = null; PanoramaTools.setOrientation(scene, rig, camera, savedOrientation); refresh();
  }
  $('restore-orientation').addEventListener('click', () => {
    if (pendingOrientation && !window.confirm('¿Descartar la orientación pendiente y restaurar la guardada?')) return;
    restoreOrientation(); message('Vista guardada restaurada.');
  });
  $('cancel-orientation').addEventListener('click', () => { restoreOrientation(); message('Cambio de orientación cancelado.'); });
  $('save-orientation').addEventListener('click', () => save(async () => {
    const body = await request(config.urls.orientation, 'PATCH', pendingOrientation);
    if (!body.orientation?.revision) throw new Error('El servidor no confirmó la orientación.');
    savedOrientation = body.orientation; pendingOrientation = null; message('Orientación inicial guardada.');
  }));
  $('preview-link').addEventListener('click', () => {
    message(dirty() || busy ? 'La prueba mostrará solo datos guardados. Hay cambios pendientes que se conservan en este editor.' : 'La prueba privada abre los datos guardados en otra pestaña.');
  });
  document.querySelectorAll('a:not([target="_blank"])').forEach(link => link.addEventListener('click', event => {
    if (link.getAttribute('href')?.startsWith('#')) return;
    if (busy || (dirty() && !window.confirm('Hay cambios pendientes. ¿Salir y descartarlos?'))) {
      event.preventDefault(); if (busy) message('Espera a que termine el guardado antes de salir.');
    } else allowLeave = true;
  }));
  window.addEventListener('beforeunload', event => {
    if (!allowLeave && (dirty() || busy)) { event.preventDefault(); event.returnValue = ''; }
  });

  function releasePanorama() {
    texture?.dispose(); if (panoramaImage) panoramaImage.src = ''; if (objectURL) URL.revokeObjectURL(objectURL);
    texture = panoramaImage = objectURL = null;
  }
  async function loadPanorama() {
    if (!config.scene.panorama) {
      showLoading('Esta escena aún no tiene panorámica. Cárgala en el administrador y vuelve a abrir el editor.');
      return;
    }
    const ticket = ++generation; controller?.abort(); controller = new AbortController();
    const activeController = controller, timeout = setTimeout(() => activeController.abort(), 20000);
    let image = null, url = null, nextTexture = null;
    showLoading('Cargando panorámica…'); loaded = false; refresh();
    try {
      const response = await fetch(config.scene.panorama, { credentials: 'same-origin', cache: 'no-store', signal: activeController.signal });
      if (!response.ok) throw new Error();
      url = URL.createObjectURL(await response.blob()); image = new Image(); image.src = url; await image.decode();
      if (ticket !== generation) return;
      if (activeController.signal.aborted) throw new Error();
      if (Math.abs(image.naturalWidth / (2 * image.naturalHeight) - 1) > config.tolerance + 1e-12) throw new Error();
      if (image.naturalWidth > scene.renderer.capabilities.maxTextureSize) throw new Error('La imagen supera la resolución de este dispositivo.');
      nextTexture = new AFRAME.THREE.Texture(image); nextTexture.colorSpace = AFRAME.THREE.SRGBColorSpace; nextTexture.needsUpdate = true;
      const material = sky.getObject3D('mesh').material; material.map = nextTexture; material.color.set('#ffffff'); material.needsUpdate = true;
      releasePanorama(); texture = nextTexture; objectURL = url; panoramaImage = image;
      nextTexture = url = image = null; loaded = true;
      PanoramaTools.setOrientation(scene, rig, camera, pendingOrientation || savedOrientation);
      $('panorama-status').hidden = true; root.dataset.loading = 'false'; refresh();
    } catch (error) {
      if (ticket === generation) showLoading(error.message || 'No se pudo cargar la panorámica. Comprueba la conexión, tus permisos y el archivo; después reintenta.', true);
    } finally { clearTimeout(timeout); nextTexture?.dispose(); if (image) image.src = ''; if (url) URL.revokeObjectURL(url); }
  }
  refresh();
  if (!window.AFRAME || !window.PanoramaTools) {
    showLoading('No se pudo iniciar el motor panorámico. Comprueba la conexión y recarga.', true);
    $('retry-panorama').addEventListener('click', () => location.reload()); return;
  }
  scene.setAttribute('xr-mode-ui', 'enabled', false); scene.setAttribute('device-orientation-permission-ui', 'enabled', false);
  // Editing is deliberately a screen-only interaction; private preview reuses the full public viewer.
  scene.enterVR = () => Promise.resolve();
  const startupTimeout = setTimeout(() => { if (!started) showLoading('No se pudo iniciar WebGL. Revisa tu navegador y reintenta.', true); }, 15000);
  $('retry-panorama').addEventListener('click', () => { if (started) loadPanorama(); else location.reload(); });
  function start() {
    if (started || !scene.hasLoaded || !scene.renderer || !sky.getObject3D('mesh')) return;
    started = true; clearTimeout(startupTimeout);
    scene.setAttribute('xr-mode-ui', 'enabled', false);
    camera.setAttribute('look-controls', { pointerLockEnabled: false, magicWindowTrackingEnabled: false });
    PanoramaTools.touchPitch(scene, camera);
    scene.canvas.setAttribute('aria-label', 'Panorámica editable. Arrastra para mirar. Activa Añadir punto antes de colocarlo.');
    let gesture = null;
    scene.canvas.addEventListener('pointerdown', event => {
      if (!event.isPrimary || event.button !== 0) { gesture = null; return; }
      gesture = { id: event.pointerId, x: event.clientX, y: event.clientY, distance: 0, start: performance.now() };
    });
    scene.canvas.addEventListener('pointermove', event => {
      if (gesture?.id === event.pointerId) gesture.distance = Math.max(gesture.distance, Math.hypot(event.clientX - gesture.x, event.clientY - gesture.y));
    });
    const cancel = () => { gesture = null; };
    scene.canvas.addEventListener('pointercancel', cancel); scene.canvas.addEventListener('pointerleave', cancel);
    scene.canvas.addEventListener('pointerup', event => {
      const click = gesture; gesture = null;
      if (!click || click.id !== event.pointerId || click.distance > 6 || Math.hypot(event.clientX - click.x, event.clientY - click.y) > 6 || performance.now() - click.start > 800 || !loaded || busy) return;
      const box = scene.canvas.getBoundingClientRect(), raycaster = new AFRAME.THREE.Raycaster();
      scene.object3D.updateMatrixWorld(true);
      raycaster.setFromCamera(new AFRAME.THREE.Vector2((event.clientX - box.left) / box.width * 2 - 1, -(event.clientY - box.top) / box.height * 2 + 1), scene.camera);
      if (placement) {
        const angles = PanoramaTools.angles(raycaster.ray.direction);
        if (placement === 'new') {
          const bytes = crypto.getRandomValues(new Uint8Array(16));
          draft = { key: Array.from(bytes, b => b.toString(16).padStart(2, '0')).join(''), label: '', destination: null, ...angles };
        } else Object.assign(draft, angles);
        placement = null; fillForm(); refresh(); message('Ubicación elegida. Completa la etiqueta y el destino, y guarda el punto.');
        labelInput.focus({ preventScroll: true });
      } else {
        const hit = raycaster.intersectObjects(markers.object3D.children, true)[0];
        let object = hit?.object;
        while (object && !object.userData.pointId) object = object.parent;
        const point = points.find(p => p.id === object?.userData.pointId);
        if (point) selectPoint(point);
      }
    });
    scene.canvas.addEventListener('webglcontextlost', event => {
      event.preventDefault(); loaded = false; started = false; controller?.abort(); refresh();
      showLoading('Se interrumpieron los gráficos. Conserva tus cambios antes de recargar; el navegador pedirá confirmación si siguen pendientes.', true);
    });
    loadPanorama();
  }
  scene.addEventListener('loaded', start, { once: true }); scene.addEventListener('renderstart', start, { once: true });
  if (scene.hasLoaded) start();
  window.addEventListener('pagehide', () => { ++generation; controller?.abort(); releasePanorama(); clearTimeout(startupTimeout); });
  window.addEventListener('pageshow', event => { if (event.persisted && started) { allowLeave = false; loadPanorama(); } });
})();
