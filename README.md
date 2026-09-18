# Esquipulas 360° — fase 3

Plataforma turística y cultural para explorar Esquipulas, Guatemala. Esta entrega continúa las fases 1 (`561490c`) y 2 (`06dabfb`): conserva el diseño, el logo original, las rutas y el visor con sus controles y WebXR. Inicio, Explorar y el visor consultan ahora la base de datos. Los recorridos, escenas y puntos se administran desde Django Admin en español. La fase 3 añade un editor visual de puntos y orientación inicial por escena, con vista de prueba privada para borradores.

La demostración usa imágenes técnicas; **no representa un lugar real** y no requiere fotografías reales. No se ha hecho push ni despliegue.

## Actualizar desde fase 2

No hay dependencias nuevas ni migraciones nuevas. Conserva tu base y `media/`; no hace falta regenerar ni reimportar contenido. Reinicia el servidor después de actualizar los archivos y verifica:

```sh
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
npm run build
```

En Admin, abre una escena guardada y pulsa **Editar puntos visualmente**. Activa **Añadir punto**, haz clic sobre la panorámica, completa etiqueta/destino y guarda. Selecciona los marcadores para editar, reubicar o eliminar con confirmación. Para orientar la escena, mira en la dirección deseada, pulsa **Usar esta vista al iniciar** y **Guardar orientación**.

**Probar datos guardados** abre una pestaña privada con el visor y permite recorrer escenas sin publicar borradores. Consulta [docs/EDITOR_VISUAL.md](docs/EDITOR_VISUAL.md) para permisos, cambios pendientes, errores y uso en móvil.

## Actualizar una instalación de fase 1

Desde la carpeta del proyecto, conserva tu `.env` y ejecuta:

```sh
uv sync --locked
npm ci
npm run build
.venv/bin/python manage.py migrate
.venv/bin/python scripts/generate_panoramas.py
.venv/bin/python manage.py import_phase1
.venv/bin/python manage.py check
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

Si no usas `uv`, sustituye `uv sync --locked` por `.venv/bin/python -m pip install --require-hashes -r requirements.lock`. Pillow es ahora una dependencia de ejecución para validar las cargas.

**Orden del contenido:** primero aplicar las migraciones, después generar las panorámicas y finalmente importar. Las migraciones solo crean estructura; no generan ni descargan archivos. La importación crea las cuatro categorías, la demostración con sus dos escenas y dos puntos, y los tres lugares próximos. Conserva los slugs originales.

Puedes repetir `import_phase1`: identifica cada recorrido por su clave de origen o su slug y omite íntegramente los existentes. No duplica ni reemplaza nombres, estados, escenas, puntos o archivos editados. Tampoco recupera automáticamente escenas o puntos eliminados. No ofrece una opción de sobrescritura. Regenerar las imágenes técnicas no reemplaza las copias ya importadas en `media/`.

## Instalación nueva

Requisitos: Python 3.12–3.14 (probado con 3.13), Node.js 20 o posterior y npm. `uv` es opcional.

```sh
uv sync --locked
.venv/bin/python scripts/setup_env.py
npm ci
npm run build
.venv/bin/python manage.py migrate
.venv/bin/python scripts/generate_panoramas.py
.venv/bin/python manage.py import_phase1
.venv/bin/python manage.py check
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

Sin `uv`, comienza con `python3.13 -m venv .venv` y `.venv/bin/python -m pip install --require-hashes -r requirements.lock`. El script de configuración crea `.env` con una clave aleatoria y nunca sobrescribe un archivo existente.

`npm run build` prepara las tipografías locales, obtiene A-Frame 1.8.0 desde su distribución oficial si falta, verifica su SHA-256 y compila Tailwind. La instalación necesita internet. Los recursos del visitante se sirven localmente; no se usa el CDN de desarrollo de Tailwind. Para trabajar en estilos: `npm run dev:css`.

## Crear el administrador

Ejecuta de forma interactiva y elige tu usuario, correo y contraseña:

```sh
.venv/bin/python manage.py createsuperuser
```

Abre [Django Admin](http://127.0.0.1:8000/admin/). No hay usuarios ni contraseñas predeterminados. No guardes credenciales en Git. Django conserva el hash de contraseña en la base local, excluida del repositorio.

Se usan usuarios, grupos y permisos estándar de Django. Un editor debe ser personal activo (`is_staff`) y tener los permisos correspondientes de ver, añadir, cambiar y eliminar para categorías, recorridos, escenas y puntos. Dar solo permiso de ver no permite editar ni subir imágenes. El superusuario puede gestionar estos permisos; no es necesario otorgar permisos de usuarios/grupos a los editores.

## Agregar un recorrido con dos escenas conectadas

1. En **Categorías**, crea o selecciona una categoría.
2. En **Recorridos**, añade nombre, slug, descripción y categoría; guarda como **Borrador**. La portada es opcional.
3. En **Escenas**, crea «Escena A» para ese recorrido, sube su panorámica y guarda. Repite para «Escena B». Usa orden 0 y 1 y, para empezar, orientación horizontal y vertical 0°.
4. Abre «Escena A». En **Puntos de navegación**, añade destino «Escena B», etiqueta «Ir a B» y posición horizontal 0°, vertical 0°. Guarda.
5. Abre «Escena B» y crea el punto inverso hacia «Escena A» de la misma manera. Los puntos están al frente de cada escena; ajusta después sus ángulos según la imagen.
6. Abre el recorrido, elige «Escena A» como **escena inicial**, configura destacado/orden y cambia a **Disponible**. Para imágenes técnicas, usa **Demostración** y una descripción que lo identifique.
7. Comprueba la tarjeta en Explorar, abre el visor y verifica ida y vuelta. Si está destacado, aparecerá entre los primeros tres lugares destacados de Inicio; las demostraciones tienen su sección propia.

El administrador impide publicar si falta una panorámica o la escena inicial no es válida. Para eliminar escenas, cambia primero el recorrido a borrador, retira los puntos que llegan a ellas y cambia o vacía la escena inicial. Una escena guardada no puede trasladarse a otro recorrido.

La guía [docs/CONTENIDO.md](docs/CONTENIDO.md) detalla publicación, formatos, límites, conservación de originales y convenciones angulares.

## Rutas y estados

| Ruta | Resultado |
| --- | --- |
| `/` | Inicio con contenido destacado y demostración de la base |
| `/explorar/` | Catálogo, búsqueda sin distinción de acentos/mayúsculas y categorías combinables |
| `/recorridos/demostracion/` | Visor de las dos escenas técnicas importadas |
| `/recorridos/<slug>/` | Visor solo si el recorrido es demostración o disponible y está completo |
| `/admin/` | Administración nativa en español, con autenticación |

**Borrador:** oculto en páginas públicas y 404 en la URL del recorrido. **Próximo:** tarjeta visible, sin acceso al visor. **Demostración:** identificada como prueba técnica. **Disponible:** requiere escena inicial del recorrido y panorámicas válidas en todas sus escenas. Demostración exige la misma integridad. Si un archivo panorámico desaparece fuera del administrador, el recorrido deja de mostrarse y su visor devuelve 404.

La búsqueda funciona mediante GET sin JavaScript. El visor mantiene arrastre, gestos táctiles, puntos seleccionables, selector accesible, información, pantalla completa, carga/error/reintento y VR iniciada por botón. Los textos editoriales se muestran como texto plano, con escapado en plantillas y JSON; no se interpretan como HTML.

`content/tours.json` queda como fuente histórica del importador, no como catálogo activo. La portada general de Inicio continúa en `content/site.json`; las portadas de cada recorrido se cargan desde Admin. El logo permanece en `static/images/logo.png`, sin modificaciones.

## Cambios de estructura

`tours/migrations/0001_initial.py` crea Categoría, Recorrido, Escena y Punto de navegación, con restricciones de estados, ángulos y claves. Crea primero Escena sin su relación a Recorrido, después Recorrido y finalmente añade esa relación; evita dependencias circulares entre migraciones. También se aplican las migraciones estándar de autenticación, sesiones y administración de Django.

Las escenas y puntos se eliminan junto con su recorrido completo; una escena referenciada como inicial o destino queda protegida ante eliminación individual. Los archivos físicos no se borran automáticamente. Las validaciones se aplican en formularios y en `save()`. Los scripts internos deben guardar cada instancia completa: se rechazan `update()`, `bulk_create()`, `bulk_update()` y `save(update_fields=...)`, que podrían omitir comprobaciones.

SQLite se mantiene para desarrollo. Respalda juntos `db.sqlite3` y `media/`. No se incluyen en Git `.env`, bases de datos, archivos cargados, dependencias instaladas, recursos generados ni reportes. Consulta el [inventario de cambios](docs/ARCHIVOS.md).

## Pruebas

Con las panorámicas generadas y el contenido importado:

```sh
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py test
npm run build
npm run test:e2e
npm run test:editor
```

Las pruebas de Django usan una base aislada y archivos temporales. `npm run test:editor` también usa una base y archivos desechables, un usuario sin contraseña utilizable y un servidor separado en el puerto 8013; no modifica la instalación local. Su reporte está en `artifacts/editor-report`. Las de navegador requieren Google Chrome instalado y el catálogo de demostración local; pueden iniciar el servidor si no está activo. Usan renderizado gráfico por software, guardan capturas en `artifacts/` y trazas de fallos en `test-results/`. Reporte: `npx playwright show-report`.

Resultado de esta fase: **70 pruebas de Django, 13 del navegador público y 7 del editor aprobadas**. Detalle y pendientes en [docs/VERIFICACION.md](docs/VERIFICACION.md).

## Meta Quest 2

El usuario confirmó que puede mirar alrededor en su navegador. **La prueba física en Meta Quest 2 sigue pendiente.** Las pruebas automatizadas de rechazo de permisos y controles no equivalen a una sesión inmersiva real.

Quest necesita un origen **HTTPS válido y confiable para el visor**. `http://192.168.x.x:8000` no ofrece ese contexto seguro. La excepción de `localhost` de la computadora no se extiende al visor. Para una prueba física, usa un proxy HTTPS local con un certificado confiable para el dispositivo; no se creó túnel ni se publicó nada.

Si usas un proxy local, el servidor puede escuchar con `.venv/bin/python manage.py runserver 0.0.0.0:8000`. Configura el host real en `DJANGO_ALLOWED_HOSTS` y el origen HTTPS en `DJANGO_CSRF_TRUSTED_ORIGINS`. `DJANGO_TRUST_PROXY=true` solo es apropiado si el proxy elimina encabezados `X-Forwarded-Proto` suministrados por clientes y establece el suyo. El servidor Django es para desarrollo.

La experiencia usa `immersive-vr` y espacio de referencia `local`, cámara estacionaria, puntos fijos y mandos con rayos. Conserva botones 3D de escenas, inicio, catálogo, salida y reintento. En VR, la cabeza controla la inclinación y la orientación inicial horizontal gira el conjunto de cámara y mandos. No hay desplazamiento continuo ni escala física 1:1.

## Dependencias y alcance

Django 5.2.17, A-Frame 1.8.0, Tailwind 4.3.3, Pillow 12.3.0; Playfair Display y Plus Jakarta Sans 5.3.0. Las dependencias están fijadas en `uv.lock`, `requirements.lock`, `package-lock.json` y `content/vendor.json`.

Entrega limitada a fase 3: editor visual por escena integrado con Admin. No se añade audio, video, monetización, modo guiado, funcionamiento sin internet, un reemplazo de Django Admin ni despliegue.
