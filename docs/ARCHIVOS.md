# Inventario del proyecto

## Base de fase 1 (`561490c`)

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


## Cambios de fase 2

La fase 1 se conserva como base; no se reinició el proyecto.

| Área | Archivos nuevos o modificados |
| --- | --- |
| Modelos e integridad | Nuevos `tours/models.py`, `tours/images.py`; adaptados `tours/checks.py`, `tours/apps.py` |
| Migración | Nuevos `tours/migrations/__init__.py`, `0001_initial.py`; únicamente estructura, sin contenido ni descargas |
| Administración | Nuevos `tours/admin.py`, `tours/forms.py`; autenticación y ruta en `config/settings.py`, `config/urls.py` |
| Datos públicos | Reemplazada la lectura estática en `tours/content.py`, `tours/views.py`, `tours/context.py` |
| Importación | Nuevos `tours/legacy.py`, `tours/management/commands/import_phase1.py` y archivos `__init__.py`; `content/tours.json` se mantiene como fuente histórica |
| Plantillas | Enlaces y datos dinámicos en `templates/partials/header.html`, `tour_card.html`, `templates/tours/home.html`, `viewer.html`; mismo diseño |
| Visor | `static/js/viewer.js`: tolerancia de proporción alineada con el servidor; se conservan controles y WebXR |
| Dependencias y límites | `.env.example`, `pyproject.toml`, `uv.lock`, `requirements.lock`; Pillow pasa a dependencia de ejecución |
| Pruebas | `tours/tests.py` (48 casos), `tests/browser/experience.spec.mjs` (12 casos conservados, usando URLs de la base, y 1 nuevo sobre tolerancia) |
| Documentación | `README.md`, `docs/CONTENIDO.md`, `docs/VERIFICACION.md`, este inventario |

No se modificaron el logo, los estilos de la identidad, las dependencias JavaScript, el generador de panorámicas ni la configuración general de portada. La base local y las copias importadas en `media/` están excluidas del commit, al igual que las capturas y otros archivos generados. No se añadieron credenciales ni despliegue.
