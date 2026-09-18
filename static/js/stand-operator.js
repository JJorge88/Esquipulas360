(() => {
  const config = JSON.parse(document.getElementById('stand-config').textContent);
  const $ = id => document.getElementById(id);
  let state, connected = false, busy = false, renderedTour = null, pendingRequest = null;
  const feedback = message => { $('stand-feedback').hidden = false; $('stand-feedback').textContent = message; };
  const token = document.querySelector('[name="csrfmiddlewaretoken"]')?.value;
  function codeExpiry() {
    if (!state || state.paired || state.phase === 'ended') return;
    $('code-expiry').textContent = Date.now() >= new Date(state.code_expires_at).getTime()
      ? 'El código caducó. Pulsa Renovar código sin usar para obtener uno nuevo.'
      : `Código válido hasta ${new Date(state.code_expires_at).toLocaleTimeString('es-GT')}. Un solo uso.`;
  }
  setInterval(codeExpiry, 1000);
  function availability() {
    document.querySelectorAll('[data-action], [data-scene]').forEach(button => { button.disabled = !config.can_control || !connected || busy || state?.phase === 'ended' || !state; });
    if ($('new-code')) $('new-code').disabled = !connected || busy || state?.paired || state?.phase === 'ended';
    if ($('open-spectator')) $('open-spectator').disabled = state?.phase === 'ended';
  }
  function render(data) {
    if (data.type === 'ended') {
      state = { ...state, phase: 'ended' }; $('stand-order').textContent = 'Sesión finalizada · Credenciales invalidadas';
      $('viewer-presence').textContent = $('spectator-presence').textContent = 'Sesión finalizada'; $('pair-code').textContent = 'Código invalidado'; availability(); return;
    }
    if (data.type !== 'state') return;
    state = data;
    $('viewer-presence').textContent = data.viewer_connected ? '● Visor conectado' : data.paired ? 'Visor vinculado · Desconectado' : 'Esperando vinculación';
    $('spectator-presence').textContent = data.spectator_connected ? '● Espectador conectado' : 'Pantalla desconectada';
    if (data.paired) { $('pair-code').textContent = 'Visor vinculado'; $('pair-code').classList.add('is-paired'); $('pair-hint').hidden = true; $('code-expiry').textContent = 'El código ya se utilizó. Para cambiar de visor, finaliza esta sesión y crea otra.'; }
    else codeExpiry();
    const actual = data.confirmed_tour?.scenes.find(s => s.id === data.confirmed_scene);
    $('confirmed-scene').textContent = actual?.name || 'Esperando confirmación del visor';
    $('confirmed-tour').textContent = data.confirmed_tour?.name || '';
    const desired = data.tour?.scenes.find(s => s.id === data.scene);
    $('desired-scene').textContent = desired ? `Solicitada: ${desired.name}` : '';
    $('stand-order').textContent = data.content_error || (data.phase === 'waiting' ? 'Recorrido preparado · Pendiente de iniciar' : data.error ? `Error del visor · ${data.error}` : data.order_status === 'applied' ? `Orden ${data.seq} aplicada · Escena confirmada por el visor` : `Orden ${data.seq} enviada · Esperando confirmación${data.viewer_connected ? '' : ' · Visor desconectado'}`);
    $('stand-order').dataset.state = data.error ? 'error' : data.order_status;
    if (data.tour && renderedTour !== data.tour.id) {
      renderedTour = data.tour.id;
      const selected = $('operator-tour'); if ([...selected.options].some(o => Number(o.value) === data.tour.id)) selected.value = String(data.tour.id);
      $('stand-scenes').replaceChildren(...data.tour.scenes.map(item => {
        const button = document.createElement('button'); button.type = 'button'; button.className = 'stand-scene'; button.dataset.scene = item.id;
        const thumb = document.createElement('div'); thumb.className = 'stand-scene-thumbnail';
        if (data.tour.thumbnails[item.id]) { const image = new Image(); image.src = data.tour.thumbnails[item.id]; image.alt = ''; thumb.append(image); } else thumb.textContent = '360°';
        const name = document.createElement('span'); name.textContent = item.name;
        button.append(thumb, name); button.addEventListener('click', () => send('scene', item.id)); return button;
      }));
    }
    document.querySelectorAll('[data-scene]').forEach(button => {
      button.disabled = !config.can_control || !connected || busy;
      button.setAttribute('aria-pressed', String(data.confirmed_scene === button.dataset.scene && data.confirmed_tour?.id === data.tour?.id));
    });
    availability();
  }
  const socket = new StandSocket(config, render, (online, message) => {
    connected = online; $('stand-network').textContent = online ? 'Conexión activa · Confirmaciones en tiempo real' : message;
    if (!online) { $('viewer-presence').textContent = 'Sin información de conexión'; $('spectator-presence').textContent = 'Sin información de conexión'; }
    availability();
  });
  async function send(action, scene = null) {
    if (!state || !connected || busy || !config.can_control || state.phase === 'ended') return;
    if (action === 'end' && !confirm('¿Finalizar la sesión? Se invalidará el acceso del visor y del espectador.')) return;
    busy = true; availability(); feedback('Enviando orden…');
    const fields = { seq: state.seq, action, tour: Number($('operator-tour').value), scene };
    const identity = JSON.stringify(fields);
    // A lost HTTP response can be retried with the same command ID; no duplicate reset/start.
    if (!pendingRequest || pendingRequest.identity !== identity) pendingRequest = { identity, payload: { ...fields, id: crypto.randomUUID() } };
    try {
      const response = await fetch(config.command, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': token, Accept: 'application/json' }, body: JSON.stringify(pendingRequest.payload) });
      const result = await response.json().catch(() => ({}));
      if (!response.ok || result.accepted !== true) throw new Error(result.error || (response.status === 403 ? 'Tu acceso o la sesión cambió. Vuelve a entrar al panel.' : 'No se pudo confirmar la orden. Comprueba la conexión y reintenta.'));
      feedback('Orden aceptada por el servidor. La escena se considera aplicada cuando el visor la confirme.');
      pendingRequest = null;
    } catch (error) { feedback(error instanceof TypeError ? 'No se confirmó el envío. Comprueba el estado y reintenta.' : error.message); }
    finally { busy = false; availability(); }
  }
  document.querySelectorAll('[data-action]').forEach(button => button.addEventListener('click', () => send(button.dataset.action)));
  $('new-code')?.addEventListener('click', async () => {
    if (!connected || busy) return;
    busy = true; availability();
    try {
      const response = await fetch(config.code, { method: 'POST', headers: { 'X-CSRFToken': token, Accept: 'application/json' } });
      const result = await response.json(); if (!response.ok) throw new Error(result.error);
      $('pair-code').textContent = result.code; feedback('Código renovado. El anterior dejó de ser válido.');
    } catch { feedback('No se pudo renovar el código. Revisa la sesión y la conexión.'); }
    finally { busy = false; availability(); }
  });
  availability();
})();
