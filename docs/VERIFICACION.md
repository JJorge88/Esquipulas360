# Verificación de fase 4

Entorno: macOS, Python 3.13, Django 5.2.17, Node.js 26 y Google Chrome controlado con Playwright. Las pruebas gráficas usan renderizado por software. Fecha local: 17 de septiembre de 2026.

## Resultado de fase 4

- **96 pruebas Django aprobadas:** 70 anteriores y 26 del panel. Incluyen inicio/cierre de sesión, rechazo de cuentas no autorizadas, permisos independientes, CSRF, ausencia de escrituras por GET, consultas y cifras reales, búsqueda sin acentos, cargas con contenido real, nombres únicos/originales, errores ligados a campos, publicación, relaciones, eliminación y rutas privadas del editor.
- **7 pruebas del panel en Chrome aprobadas:** inicio de sesión real y cierre POST; resumen y filtros; creación de categoría y recorrido con portada; dos panorámicas cargadas desde formularios; puntos de ida y vuelta mediante el editor compartido; orientación guardada y recuperada; navegación privada del borrador y pública después de publicar; publicación incompleta rechazada; errores de validación y red que conservan texto y archivos; avisos al salir y cerrar sesión; categorías editadas/eliminadas con confirmación; bloqueos de eliminación; menú móvil, Escape/foco y ausencia de desbordamiento a 360, 390 y 768 px.
- **7 pruebas de regresión del editor aprobadas:** se conservan creación, selección, reubicación, eliminación, arrastre, persistencia, orientación, cambios pendientes, pruebas privadas, correspondencia de marcadores y controles móviles emulados.
- **13 pruebas públicas aprobadas:** Inicio, Explorar, búsqueda, logo, giro, navegación entre las dos escenas, orientación, liberación de texturas, tolerancia de imágenes, errores/reintento, móvil, pantalla completa y casos WebXR simulados.
- `manage.py check` sin incidencias y `makemigrations --check --dry-run` sin cambios. No se añaden migraciones ni dependencias.
- Recursos compilados y sintaxis JavaScript comprobada. Capturas del resumen, catálogo, edición y acceso revisadas en escritorio; menú/formulario también revisados en móvil emulado.
- La instantánea de categorías, recorridos, escenas, puntos y permisos de las cuentas locales coincide antes y después de la verificación final. El logo coincide byte a byte (SHA-256) con el adjunto original. Los manifiestos de sesión temporales se eliminaron al cerrar las suites.

Las pruebas de panel y editor usan sus propias bases temporales. Se aisló también la suite pública: el catálogo local ya tiene cambios editoriales válidos, por lo que una prueba que asumía tres lugares próximos fallaba al consultar la instalación del usuario. Las aserciones de comportamiento se conservan y ahora se ejecutan sobre una importación temporal de la demostración. No se restablecen ni reimportan los datos locales. En la prueba de selección de marcador se espera la intersección real del cursor de A-Frame antes de pulsar, para evitar un clic anterior al ciclo de renderizado.

El flujo nuevo se comprobó primero con los selectores de prueba ajustados a las etiquetas accesibles reales (los botones de navegación incluyen una flecha y los campos obligatorios incluyen su indicación). Después, las suites completas finalizaron sin fallos. No se cambió el motor público para hacer pasar las pruebas.

Capturas de la **base temporal de demostración**, guardadas fuera de Git:

- `artifacts/panel-summary.png`: resumen en escritorio.
- `artifacts/panel-tours.png`: tarjetas y filtros.
- `artifacts/panel-edit.png`: información, portada, escenas y publicación.
- `artifacts/panel-login.png`: acceso con identidad propia.
- `artifacts/panel-mobile-summary.png` y `artifacts/panel-mobile-edit.png`: pantallas de 390 px.

La prueba gráfica no valida un teléfono físico ni un Meta Quest 2. Esos pendientes se mantienen al final de este documento.

## Resultado de fase 3

- **70 pruebas Django aprobadas:** las 48 de fase 2 y 22 nuevas del editor. Se comprueban autorización por operación, acceso anónimo/no personal, solo lectura, CSRF en POST/PATCH/DELETE, ausencia de escrituras por GET, destinos ajenos/al origen/inexistentes, valores no finitos o fuera de rango, JSON inválido, creación idempotente, edición, eliminación, revisiones y persistencia de orientación.
- **13 pruebas del visor público aprobadas:** conservación de rutas, búsqueda, móvil, puntos, giro, pantalla completa, carga/reintento y comportamiento WebXR simulado.
- **7 pruebas del editor en Chrome aprobadas:** creación visual, selección desde marcador/lista, reubicación y eliminación confirmada; persistencia tras recargar; arrastres sin colocaciones accidentales; errores de guardado y respuesta perdida sin duplicados; orientación y restauración coherentes con la prueba privada; advertencia al salir/recargar; previsualización de datos guardados mientras hay edición pendiente; correspondencia espacial con el visor público; gestos y guardado en móvil emulado.
- `manage.py check` sin incidencias; `makemigrations --check --dry-run` sin cambios: fase 3 no necesita migraciones.
- Compilación de recursos y sintaxis de los archivos JavaScript verificadas. No se cambian versiones de dependencias.
- Revisión visual de capturas del editor en escritorio y móvil. El logo y los datos locales de la demostración se conservan.

Las pruebas del editor en navegador utilizan una base temporal separada, archivos temporales y una sesión de prueba con contraseña inutilizable. El servidor de pruebas se cierra y borra estos datos al terminar. Se añadieron carpetas separadas para los diagnósticos de ambas suites, evitando interferencias entre sus reportes.

Los permisos se comprobaron por HTTP con Django, incluyendo clientes con comprobación CSRF real. Los cambios visuales y las interacciones se comprobaron mediante Chrome. Los errores de red y pérdida de respuesta de guardado se inducen intencionalmente en las pruebas.

## Verificación conservada de fase 2

- `manage.py check`: sin incidencias.
- `makemigrations --check --dry-run`: sin cambios pendientes; migración inicial aplicada en la instalación local y en las bases vacías de pruebas.
- `import_phase1` ejecutado dos veces en la instalación: cuatro recorridos, cuatro categorías, dos escenas y dos puntos; la segunda ejecución conservó todos sin duplicarlos.
- `manage.py test`: **48 pruebas aprobadas** de modelos, cargas reales, permisos y formularios de Admin, publicación, importación y páginas públicas. Base de pruebas aislada y archivos temporales.
- `npm run build`: compilación de Tailwind y preparación/verificación de recursos locales correctas.
- Navegador: **13 pruebas aprobadas**. Se ejecutaron las 12 pruebas de conservación con `npm run test:e2e` sobre la demostración importada y, después, una nueva prueba específica de tolerancia con `npx playwright test --grep "inclusive panorama"`. Las pruebas usan las URLs de archivos de la base, sin depender de nombres originales.
- Sintaxis JavaScript comprobada con `node --check`.
- Logo cotejado por SHA-256 con el adjunto: archivos idénticos.
- Revisión visual de capturas de Inicio, Explorar y Visor en computadora y celular. Diseño sin desbordamiento horizontal en 360, 390 y 768 px; vista de escritorio de 1440 px.

| Comportamiento | Evidencia |
| --- | --- |
| Inicio, catálogo y demostración | HTTP 200 y navegación real en Chrome |
| Slug inexistente, borrador o recorrido próximo | HTTP 404; página de error propia con DEBUG desactivado |
| Búsqueda | `BASILICA`, `Basílica` y `basílica` encuentran Basílica |
| Categorías combinadas | Búsqueda + Patrimonio produce un resultado; búsqueda + Vistas muestra estado vacío; restablecer recupera los cuatro |
| Próximos | Tres tarjetas sin enlaces a un visor inexistente |
| Menú móvil | Apertura, cierre con Escape, foco de retorno y navegación |
| Panorama real esférico | Malla `SphereGeometry`, textura 2048 × 1024 y revisión visual |
| Giro y elevación | Arrastre horizontal mayor a una vuelta, inclinación vertical y posición de cámara fija; gesto táctil horizontal y vertical mediante emulación |
| Navegación | Clic en el punto 3D azul → ámbar y punto 3D ámbar → azul; selector y botón alternativo accesibles |
| Orientación inicial | Escena azul a 0°; ámbar a 90°, con inclinación de 5° en pantalla |
| Carga diferida | La segunda panorámica no se solicita antes de abrir su escena |
| Recursos | Se observa `dispose` de la textura anterior al cambiar de escena |
| Archivos ausentes | Respuesta 404 forzada para cada panorámica, mensaje de error y recuperación al reintentar |
| Información | Panel cerrado al inicio; abrir/cerrar con botones y Escape; no se envían datos de audio al visor |
| Pantalla completa | Entrada y salida mediante el botón de la aplicación |
| VR no disponible | Mensaje claro y recorrido normal utilizable; se comprobó ausencia de API y navegador sin visor |
| Permisos VR | API simulada: ninguna solicitud antes de pulsar el botón, evento automático ignorado, rechazo controlado y botón reutilizable |
| Controles inmersivos | Presencia de entidades 3D para escenas, inicio, catálogo, salida y reintento; rayos de selección de ambos mandos configurados |
| Consola | Sin errores JavaScript ni solicitudes fallidas en el recorrido normal; los 404 de las pruebas de fallo son intencionales |

Chrome puede emitir avisos del controlador gráfico sobre `ReadPixels` por usar renderizado de software. Son avisos del entorno de pruebas; no se presentan como validación de rendimiento de Quest.

## Integridad y administración comprobadas

| Área | Casos verificados |
| --- | --- |
| Permisos | Anónimo/no personal redirigido; personal sin permisos recibe 403; solo lectura no puede editar ni subir archivos; editor autorizado puede guardar y publicar |
| Admin | Interfaz en español; carga y guardado de escenas; puntos dentro de la escena; errores de publicación y carga ligados al formulario; destinos de otro recorrido rechazados |
| Imágenes | JPEG, PNG y WebP de portada; JPEG/PNG de panorama; archivo fingido, extensión incorrecta, truncado, animación y giro EXIF rechazados |
| Límites | Peso, mínimos, máximo por lado, píxeles totales, proporción dentro/fuera de tolerancia y extremos incluidos. Chrome carga panorámicas 1980 × 1000 y 2020 × 1000, y rechaza 1979 × 1000 |
| Relaciones | Escena inicial y destinos del mismo recorrido; prohibición de trasladar escenas y de puntos a su propio origen; ángulos finitos y acotados |
| Publicación | Escena inicial y todas las imágenes requeridas; archivo ausente o corrupto impide publicar; no se permite vaciar ni añadir una escena incompleta en un recorrido publicado |
| Eliminación | Escenas publicadas protegidas individualmente y en lote; destino referenciado protegido en borrador; eliminación completa del recorrido con conexiones de ida y vuelta sin referencias rotas |
| Archivos | Originales byte a byte, nombres únicos, miniaturas pequeñas, reemplazos y eliminaciones conservan archivos anteriores |
| Importación | Repetición sin duplicados; cambios de nombre, slug, estado y texto, además de puntos eliminados, preservados; archivos faltantes no dejan registros parcialmente importados |
| Contenido público | Lectura desde base, orden/destacado, cambios editoriales visibles, borradores ocultos también en enlaces y categorías, próximos sin visor, estados vacíos |
| Datos del visor | Solo contrato público necesario; sin clave de importación ni audio; texto que intenta cerrar el elemento script correctamente escapado |
| Navegación esférica | Conversión de ángulos compatible con los ejes y cambio real azul → ámbar → azul en Chrome |

Se revisó visualmente el acceso nativo a Admin en español. Los formularios autenticados y permisos se comprobaron mediante el cliente HTTP de Django; no se creó una cuenta con contraseña predeterminada en la instalación local. Las migraciones y el importador no crean usuarios.

## Funciones conservadas de fase 1

Se corrigió el orden de inicialización de la cámara en móviles: `look-controls` se activa cuando la escena ya dispone de su componente de permisos. Se desactivó explícitamente la interfaz predeterminada de A-Frame 1.8 después de su inicialización, para dejar solo los controles de la aplicación. La entrada automática por `sessiongranted` se ignora; la aplicación solicita VR únicamente desde su botón.

Los gestos nativos de A-Frame solo cambian el giro horizontal. El proyecto añade inclinación vertical con un dedo, limitada a ±90°, sin solicitar acceso a sensores y sin aplicarla durante una sesión inmersiva. Los cambios de escena cancelan cargas anteriores y liberan los recursos sustituidos.

## Pendiente de comprobación física

El usuario confirmó previamente que puede mirar alrededor desde su navegador.

**No se utilizó un Meta Quest 2 físico. No se declara probado en Quest 2.** La existencia de controles y la simulación de rechazos WebXR no prueban el funcionamiento del seguimiento ni de los mandos.

Cuando se disponga del visor y de un origen HTTPS válido:

1. Abrir la demostración en el navegador del Quest 2 y comprobar soporte de `immersive-vr`.
2. Pulsar Entrar en VR; comprobar permisos, cancelación y retorno al modo normal.
3. Mirar a ambos lados, arriba, abajo y detrás; revisar horizonte y ausencia de movimiento artificial.
4. Seleccionar ambos puntos con cada mando, verificar cambio y retorno, y la orientación inicial.
5. Usar los controles 3D para escena inicial, selección de escena, volver al catálogo y salir; comprobar legibilidad y alcance desde una posición cómoda.
6. Interrumpir la carga de una panorámica y comprobar que el error y Reintentar sean seleccionables dentro de VR.
7. Repetir cambios de escena para revisar consumo de memoria, fluidez y comodidad.
8. Validar recorte de portada y tamaño/calidad de las panorámicas reales cuando existan.

También quedan pendientes pruebas en Safari/iPhone, otros navegadores y dispositivos físicos móviles. La comprobación de celular documentada aquí es emulación de Chrome, no una prueba en un teléfono real. Las fotografías y las referencias Stitch no se recibieron; no se presenta una comparación visual con ellas.
