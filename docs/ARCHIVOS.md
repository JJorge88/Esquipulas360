# Archivos de fase 4

| Archivo o grupo | Cambio |
| --- | --- |
| `tours/panel.py`, `tours/panel_urls.py` | Panel, autenticación compartida, permisos por operación, resumen real, búsqueda/filtros, CRUD y eliminación con el recolector de Admin |
| `tours/panel_forms.py` | Formularios con validación de modelos existente y configuración visible de cargas |
| `templates/panel/`, `tours/templates/panel/file_input.html` | Plantillas propias, acceso, menú, tarjetas, formularios, confirmaciones y estados vacíos |
| `static/css/panel.css`, `static/js/panel.js` | Identidad visual, móvil, accesibilidad, vistas previas de archivos, conservación del formulario y cambios pendientes |
| `config/urls.py`, `tours/context.py` | Ruta `/panel/` y contexto privado |
| `tours/editor.py`, `tours/content.py`, `templates/tours/editor.html` | Enlaces y panorámicas privadas según origen Admin/panel; misma implementación de edición y visor |
| `tours/test_panel.py` | Pruebas de acceso, permisos, CSRF, archivos, publicación, relaciones, eliminación y endpoints compartidos |
| `tests/browser/panel*`, `playwright.panel.config.mjs`, `package.json` | Suite gráfica con acceso real y base temporal; comando `test:panel` |
| `tests/browser/public_server.py`, `playwright.config.mjs`, `tests/browser/experience.spec.mjs` | Datos aislados para regresiones públicas, sin asumir que el usuario no ha editado su catálogo |
| `tests/browser/editor.spec.mjs` | Espera a que el cursor interseque realmente el marcador antes del clic de prueba |
| `README.md`, `docs/PANEL.md`, `docs/VERIFICACION.md` | Actualización, guía de uso, permisos y resultados |

No se modifican modelos, migraciones, versiones de dependencias, logo ni plantillas de las páginas públicas. Capturas y reportes se guardan en `artifacts/`, fuera de Git. No se versionan usuarios, sesiones, contraseñas, bases de datos ni archivos cargados.

---

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


## Cambios de fase 3

| Área | Archivos nuevos o modificados |
| --- | --- |
| Integración con Admin | `tours/admin.py`; nueva plantilla `templates/admin/tours/scene/change_form.html` con enlace por escena y permisos |
| Editor y API privada | Nuevo `tours/editor.py`: acceso, creación, edición, eliminación, orientación, lectura, panorámicas y prueba privada |
| Pantalla de edición | Nuevos `templates/tours/editor.html`, `static/js/editor.js`, `static/css/editor.css` |
| Motor compartido | Nuevo `static/js/panorama-core.js`; extrae etiquetas, orientación y control táctil de `static/js/viewer.js` para reutilizarlos |
| Vista de prueba | `tours/content.py`, `templates/tours/viewer.html`, `static/js/viewer.js`: mismo visor con datos guardados, rutas de imagen privadas y retorno al editor |
| Pruebas | Nuevo `tours/test_editor.py` (22 casos), `tests/browser/editor.spec.mjs` (7 casos), servidor desechable `tests/browser/editor_server.py` y `playwright.editor.config.mjs` |
| Comandos de prueba | `package.json`: script `test:editor`; `playwright.config.mjs`: selecciona únicamente la suite pública |
| Documentación | Nueva `docs/EDITOR_VISUAL.md`; actualizados README, contenido, verificación e inventario |

No hay cambios de modelos, migraciones, versiones de dependencias, logo, rutas públicas ni contenido persistido. Los datos del editor de prueba se crean en una base temporal; sus capturas/reportes y manifiesto de sesión efímera se excluyen de Git.

## Cambios de fase 5

| Área | Archivos nuevos o modificados |
| --- | --- |
| Sesión y protocolo | Nueva aplicación `stand/`: modelos, servicios, consumidores WebSocket, vistas, URLs y migración `0001_initial` |
| Transporte y servicios | `config/asgi.py`, `config/settings.py`, `config/urls.py`, `compose.stand.yml`, `.env.example` |
| Acceso desde el panel | `tours/panel.py`, `tours/panel_forms.py`, `tours/context.py`, `templates/panel/base.html` |
| Tres roles | Nuevas plantillas `templates/stand/`, `static/css/stand.css`; scripts `stand-socket.js`, `stand-operator.js`, `stand-participant.js`, `stand-spectator.js` |
| Motor conservado | `static/js/panorama-core.js`: cuaternión mundial y fundido; `static/js/viewer.js` y `templates/tours/viewer.html`: modo vinculado condicionado, conservando el visor normal |
| Dependencias fijadas | `pyproject.toml`, `uv.lock`, `requirements.lock`; Channels/Daphne, channels-redis y cliente Redis, sin cambios de versiones de las dependencias anteriores |
| Pruebas | `stand/tests.py`, `tests/browser/stand_server.py`, `stand.spec.mjs`, `playwright.stand.config.mjs`, nuevo script `test:stand` en `package.json` |
| Documentación | Nueva guía `docs/STAND.md`; README, verificación e inventario actualizados |

No se modifican `tours/models.py`, sus migraciones, el logo, el editor, los archivos de contenido ni las dependencias JavaScript. La migración nueva solo añade sesiones; no importa contenido. No hay cuentas nuevas en la instalación local, claves en Git, push, túneles públicos ni despliegue.
