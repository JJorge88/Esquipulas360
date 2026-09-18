(() => {
  const toggle = document.getElementById('menu-toggle');
  const nav = document.getElementById('main-nav');
  if (!toggle || !nav) return;
  const close = () => {
    toggle.setAttribute('aria-expanded', 'false');
    toggle.setAttribute('aria-label', 'Abrir menú');
    nav.classList.remove('is-open');
  };
  toggle.addEventListener('click', () => {
    const open = toggle.getAttribute('aria-expanded') !== 'true';
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? 'Cerrar menú' : 'Abrir menú');
    nav.classList.toggle('is-open', open);
  });
  nav.addEventListener('click', event => { if (event.target.closest('a')) close(); });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && toggle.getAttribute('aria-expanded') === 'true') { close(); toggle.focus(); }
  });
  document.addEventListener('click', event => { if (!event.target.closest('.site-header')) close(); });
  matchMedia('(min-width: 801px)').addEventListener('change', close);
})();
