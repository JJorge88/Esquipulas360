# Esquipulas 360° — fase 1

Plataforma turística y cultural para explorar Esquipulas, Guatemala. Primera base para **58 años como ciudad, 1968–2026**. Incluye inicio, catálogo y demostración esférica; las imágenes técnicas **no representan lugares reales**.

La carpeta estaba vacía. Se conservó el logo adjunto, sin modificaciones. No se recibieron las capturas ni los tres HTML de Stitch; se aplicaron los colores y las tipografías indicadas. No se inventaron fotografías, historia, escudos ni respaldo institucional. No se ha desplegado ni hecho push.

## Ejecutar desde cero

Requisitos: Python 3.12–3.14 (probado con 3.13), Node.js 20 o posterior y npm. `uv` es opcional. Ejecuta desde esta carpeta:

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.lock
.venv/bin/python scripts/setup_env.py
npm ci
npm run build
.venv/bin/python scripts/generate_panoramas.py
.venv/bin/python manage.py migrate
.venv/bin/python manage.py check
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

Abre <http://127.0.0.1:8000/>. Para quien tenga `uv`, los dos primeros comandos se pueden sustituir por `uv sync --locked`. El script de configuración crea `.env` con una clave aleatoria y nunca sobrescribe un archivo existente.

`npm run build` copia las tipografías locales, obtiene A-Frame 1.8.0 desde su distribución oficial si falta y verifica su SHA-256, y compila Tailwind. La instalación necesita internet. El visitante recibe estos recursos desde Django; no se usa el CDN de desarrollo de Tailwind. Esta fase no implementa funcionamiento sin internet ni un service worker.

Para modificar estilos mientras desarrollas, ejecuta `npm run dev:css` en otra terminal. SQLite es solamente de desarrollo. `.env`, `.venv`, `node_modules`, SQLite, panorámicas generadas, archivos reales en `media/` y reportes de pruebas se excluyen de Git.

## Rutas y comportamiento

| Ruta | Resultado |
| --- | --- |
| `/` | Inicio, portada pendiente, próximos lugares, demostración, explicación y ayuda VR |
| `/explorar/` | Catálogo con búsqueda sin distinción de acentos/mayúsculas y categoría combinable |
| `/recorridos/demostracion/` | Visor A-Frame de dos escenas técnicas equirectangulares 2048 × 1024 |
| `/recorridos/<slug-inexistente-o-proximo>/` | HTTP 404; no abre contenido ficticio |

Los filtros se envían mediante GET y funcionan sin JavaScript. Los estados son `demo`, `available` y `upcoming`. Mirador, Basílica y Parque Central están próximos. El visor utiliza JavaScript y WebGL: arrastre, gestos táctiles, puntos seleccionables, selector accesible, pantalla completa cuando el navegador la admite, información cerrada inicialmente, carga/error/reintento y VR iniciada por botón.

## Versiones fijadas

- Django **5.2.17 LTS**; serie con soporte ampliado hasta abril de 2028 según la [página oficial de descargas](https://www.djangoproject.com/download/), consultada durante esta implementación.
- A-Frame **1.8.0**, distribución oficial con hash en `content/vendor.json`; [código de la versión](https://github.com/aframevr/aframe/tree/v1.8.0).
- Tailwind CSS y CLI **4.3.3**.
- Playfair Display y Plus Jakarta Sans **5.3.0**, alojadas localmente desde Fontsource.
- Dependencias Python directas en `pyproject.toml`, resolución completa en `uv.lock` y exportación con hashes en `requirements.lock`. Dependencias JS directas en `package.json` y resolución completa en `package-lock.json`.

## Archivos e imágenes reales

Guía completa: [docs/CONTENIDO.md](docs/CONTENIDO.md). Pruebas de escritorio y pendientes físicos: [docs/VERIFICACION.md](docs/VERIFICACION.md). Inventario de los archivos creados: [docs/ARCHIVOS.md](docs/ARCHIVOS.md).

- Logo original: `static/images/logo.png`. Se muestra completo, con su proporción original.
- Portada de inicio: coloca los archivos en `media/covers/` y configura `hero_desktop` y `hero_mobile` en `content/site.json`. El móvil admite un recorte separado; el fondo de texto mantiene contraste.
- Portadas de recorridos: `media/covers/`, campo `cover` de cada recorrido.
- Panorámicas reales: `media/panoramas/`, campo `panorama` de cada escena. Deben ser equirectangulares completas 2:1, no fotografías planas estiradas.
- Audio opcional: `media/audio/`, campo `audio`. Sin archivo configurado no se crean controles ni tiempos. Nunca se reproduce automáticamente.

## Pruebas

```sh
.venv/bin/python manage.py check
.venv/bin/python manage.py test
npm run build
npm run test:e2e
```

Las pruebas de navegador requieren Google Chrome instalado. Playwright abre Chrome local y puede iniciar el servidor de desarrollo si no está ejecutándose. Se usa renderizado gráfico por software en pruebas automatizadas. Las capturas quedan en `artifacts/`; las trazas de fallos, en `test-results/`. Para ver el reporte: `npx playwright show-report`.

## Meta Quest 2

**No se ha probado físicamente en Meta Quest 2.** La integración de WebXR y los controles dentro de la escena están implementados; la prueba física sigue pendiente. Las pruebas de permisos usan respuestas simuladas y no equivalen a una sesión inmersiva real.

Quest debe acceder a un origen con **HTTPS válido y confiable para el visor**. `http://192.168.x.x:8000` no ofrece el contexto seguro necesario. El permiso de `localhost` en la computadora no se extiende al visor. Usa un proxy HTTPS local con certificado que el visor confíe o, cuando se autorice en otra fase, un origen de prueba HTTPS. No se ha creado túnel ni publicado nada en esta fase.

Para pruebas en red, el servidor puede escuchar con `.venv/bin/python manage.py runserver 0.0.0.0:8000` detrás del proxy. Configura el host real en `DJANGO_ALLOWED_HOSTS` y el origen HTTPS en `DJANGO_CSRF_TRUSTED_ORIGINS`. `DJANGO_TRUST_PROXY=true` solo es apropiado si tu proxy elimina encabezados `X-Forwarded-Proto` suministrados por clientes y establece el suyo. El servidor de Django es para desarrollo, no para publicar producción.

La experiencia usa `immersive-vr` con espacio de referencia `local`, puntos fijos y mandos con rayos de selección. Dentro de VR hay botones para ambas escenas, inicio del recorrido, regresar a Explorar, salir de VR y reintentar si falla una imagen. No hay desplazamiento continuo ni promesa de escala física 1:1. En VR, la inclinación la controla la cabeza; la orientación inicial del contenido se aplica mediante el giro del conjunto de cámara y mandos.

## Límite de esta entrega

Solo fase 1. No incluye pagos, publicidad, directorio comercial, registro de visitantes, editor personalizado, videos 360°, modo guiado, funcionamiento sin internet ni analítica avanzada. El siguiente paso requiere fotografías reales y validación física del visor; no se ha comenzado esa fase.
