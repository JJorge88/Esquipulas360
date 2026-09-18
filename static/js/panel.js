/* Progressive enhancement: HTML forms work without JavaScript; fetch preserves uploads on errors. */
(() => {
  const menu = document.querySelector('#panel-menu-button');
  const sidebar = document.querySelector('#panel-sidebar');
  const scrim = document.querySelector('#panel-scrim');
  const mobile = matchMedia('(max-width: 900px)');
  const setMenu = open => {
    document.body.classList.toggle('menu-open', open);
    menu?.setAttribute('aria-expanded', String(open));
    menu?.setAttribute('aria-label', open ? 'Cerrar menú' : 'Abrir menú');
    if (scrim) scrim.hidden = !open;
    if (sidebar) sidebar.inert = mobile.matches && !open;
    if (open) sidebar?.querySelector('a')?.focus();
  };
  menu?.addEventListener('click', () => setMenu(menu.getAttribute('aria-expanded') !== 'true'));
  scrim?.addEventListener('click', () => { setMenu(false); menu?.focus(); });
  mobile.addEventListener('change', () => setMenu(false));
  setMenu(false);
  document.addEventListener('keydown', event => {
    if (!document.body.classList.contains('menu-open')) return;
    if (event.key === 'Escape') { setMenu(false); menu?.focus(); }
    if (event.key === 'Tab') {
      const links = [...sidebar.querySelectorAll('a, button')];
      if (event.shiftKey && document.activeElement === links[0]) { event.preventDefault(); links.at(-1)?.focus(); }
      else if (!event.shiftKey && document.activeElement === links.at(-1)) { event.preventDefault(); links[0]?.focus(); }
    }
  });

  const form = document.querySelector('[data-panel-form]');
  if (!form) return;
  const status = document.querySelector('#form-status');
  const pending = document.querySelector('#panel-dirty-status');
  // Empty file fields create a fresh File on each read; their timestamp is irrelevant.
  const stableSignature = () => JSON.stringify([...new FormData(form)].filter(([name]) => name !== 'csrfmiddlewaretoken').map(([name, value]) => [name, value instanceof File ? (value.size || value.name ? [value.name, value.size, value.lastModified] : null) : value]));
  const initial = stableSignature();
  let saving = false, leaving = false;
  const dirty = () => stableSignature() !== initial;
  const updateDirty = () => {
    const changed = dirty();
    form.dataset.dirty = String(changed);
    if (pending) { pending.textContent = changed ? 'Cambios sin guardar' : 'Sin cambios pendientes'; pending.classList.toggle('pending', changed); }
  };
  form.addEventListener('input', updateDirty);
  form.addEventListener('change', updateDirty);
  window.addEventListener('beforeunload', event => {
    if (!leaving && (dirty() || saving)) { event.preventDefault(); event.returnValue = ''; }
  });
  document.addEventListener('click', event => {
    const link = event.target.closest('a[href]');
    if (!link || !dirty() || link.getAttribute('href').startsWith('#')) return;
    const separate = link.target === '_blank' || event.ctrlKey || event.metaKey || event.shiftKey;
    const message = separate ? 'Hay cambios sin guardar. La otra pestaña mostrará los datos guardados. ¿Quieres abrirla?' : 'Hay cambios sin guardar. ¿Quieres salir y descartarlos?';
    if (!window.confirm(message)) event.preventDefault();
    else if (!separate) leaving = true;
  });
  document.querySelectorAll('[data-leave-form]').forEach(other => other.addEventListener('submit', event => {
    if (dirty() && !window.confirm('Hay cambios sin guardar. ¿Quieres cerrar sesión y descartarlos?')) event.preventDefault();
    else leaving = true;
  }));
  form.querySelectorAll('[data-image-input]').forEach(input => {
    const preview = document.querySelector(`[data-image-preview="${input.dataset.imageInput}"]`);
    if (!preview) return;
    let objectURL;
    const original = [...preview.childNodes].map(node => node.cloneNode(true));
    const clear = document.getElementById(`${input.name}-clear_id`);
    const show = () => {
      if (objectURL) { URL.revokeObjectURL(objectURL); objectURL = null; }
      if (input.files[0]) {
        objectURL = URL.createObjectURL(input.files[0]);
        const img = new Image(); img.alt = 'Vista previa del archivo seleccionado, todavía sin guardar'; img.src = objectURL;
        img.onerror = () => { const message = document.createElement('small'); message.textContent = 'No se puede mostrar este archivo. Se validará al guardar.'; preview.replaceChildren(message); };
        preview.replaceChildren(img);
      } else if (clear?.checked) { const message = document.createElement('small'); message.textContent = 'Se retirará la imagen al guardar.'; preview.replaceChildren(message); }
      else preview.replaceChildren(...original.map(node => node.cloneNode(true)));
    };
    input.addEventListener('change', show);
    clear?.addEventListener('change', show);
  });
  const feedback = message => { status.hidden = false; status.textContent = message; status.classList.add('error'); status.focus(); };
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (saving) return;
    saving = true;
    const fieldsets = [...form.querySelectorAll('fieldset')];
    fieldsets.forEach(fieldset => { fieldset.inert = true; });
    const button = form.querySelector('[type="submit"]');
    const label = button?.textContent;
    if (button) { button.disabled = true; button.textContent = 'Guardando…'; }
    form.querySelectorAll('[data-field-errors]').forEach(el => el.replaceChildren());
    form.querySelectorAll('.has-error').forEach(el => el.classList.remove('has-error'));
    form.querySelectorAll('[aria-invalid]').forEach(el => el.removeAttribute('aria-invalid'));
    status.hidden = false; status.classList.remove('error'); status.textContent = 'Validando y guardando…';
    try {
      const response = await fetch(form.action, { method: 'POST', body: new FormData(form), headers: { Accept: 'application/json', 'X-CSRFToken': form.querySelector('[name="csrfmiddlewaretoken"]').value }, credentials: 'same-origin' });
      let result;
      try { result = await response.json(); } catch { throw new Error(response.status === 403 ? 'No se pudo validar tu sesión. Abre el panel en otra pestaña, inicia sesión y reintenta.' : 'El servidor no confirmó el guardado. Tus cambios siguen aquí; vuelve a intentarlo.'); }
      if (!response.ok) {
        for (const [name, errors] of Object.entries(result.errors || {})) {
          const list = [...form.querySelectorAll('[data-field-errors]')].find(el => el.dataset.fieldErrors === name);
          if (list) { for (const error of errors) { const li = document.createElement('li'); li.textContent = error; list.append(li); } list.closest('[data-field]')?.classList.add('has-error'); }
          const input = form.elements.namedItem(name); input?.setAttribute?.('aria-invalid', 'true');
        }
        const general = result.errors?.__all__?.join(' ') || '';
        feedback([result.error || 'No se guardaron los cambios.', general].filter(Boolean).join(' '));
        return;
      }
      if (typeof result.redirect !== 'string' || !result.redirect.startsWith('/panel/')) throw new Error('No se recibió una confirmación válida. Revisa el contenido guardado en otra pestaña.');
      leaving = true;
      window.location.assign(result.redirect);
    } catch (error) { feedback(error instanceof TypeError ? 'No pudimos conectar con el servidor. Conservamos tus cambios para reintentar.' : error.message); }
    finally { saving = false; fieldsets.forEach(fieldset => { fieldset.inert = false; }); if (button) { button.disabled = false; button.textContent = label; } updateDirty(); }
  });
})();
