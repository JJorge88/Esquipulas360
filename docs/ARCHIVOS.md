# Inventario de fase 1

La carpeta estaba vacía: todos los siguientes archivos se crearon en esta fase; no había archivos previos que modificar. El logo fue copiado exactamente del adjunto.

| Área | Archivos creados |
| --- | --- |
| Instalación y configuración | `.gitignore`, `.env.example`, `pyproject.toml`, `uv.lock`, `requirements.lock`, `package.json`, `package-lock.json`, `manage.py` |
| Django | `config/__init__.py`, `config/settings.py`, `config/urls.py`, `config/wsgi.py` |
| Catálogo y validación | `tours/__init__.py`, `tours/apps.py`, `tours/checks.py`, `tours/content.py`, `tours/context.py`, `tours/views.py`, `tours/tests.py` |
| Datos | `content/site.json`, `content/tours.json`, `content/vendor.json` |
| Plantillas | `templates/base.html`, `templates/404.html`, `templates/partials/header.html`, `templates/partials/footer.html`, `templates/partials/tour_card.html`, `templates/tours/home.html`, `templates/tours/explore.html`, `templates/tours/viewer.html` |
| Estilos e interacción | `assets/css/input.css`, `static/js/site.js`, `static/js/viewer.js` |
| Identidad | `static/images/logo.png` |
| Preparación de recursos | `scripts/setup_env.py`, `scripts/copy-assets.mjs`, `scripts/generate_panoramas.py` |
| Pruebas de navegador | `playwright.config.mjs`, `tests/browser/experience.spec.mjs` |
| Documentación | `README.md`, `docs/CONTENIDO.md`, `docs/ARCHIVOS.md`, `docs/VERIFICACION.md`, `THIRD_PARTY.md` |

Se crean localmente, pero no se incluyen en el commit: `.env`, `.venv/`, `node_modules/`, `db.sqlite3`, `static/css/app.css`, `static/vendor/`, `static/panoramas/demo-azul.png`, `static/panoramas/demo-ambar.png`, `artifacts/`, `test-results/`, `playwright-report/`. Los futuros archivos reales irán en `media/`, también excluido.
