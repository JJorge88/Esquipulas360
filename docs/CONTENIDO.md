# Administrar lugares, escenas y puntos

Desde fase 3, cada escena guardada ofrece **Editar puntos visualmente** en Admin: coloca o mueve marcadores con un clic, elige etiqueta/destino y guarda; la vista inicial también se elige mirando la panorámica. La guía [EDITOR_VISUAL.md](EDITOR_VISUAL.md) explica su uso y la prueba privada de borradores. Los campos angulares de Admin continúan disponibles.

El contenido de los recorridos se guarda en la base de datos y se edita desde `/admin/`. No es necesario cambiar plantillas ni JSON. La instalación y la creación del superusuario se describen en [README.md](../README.md).

## Recorridos y publicación

Cada recorrido tiene nombre, slug único, descripción, categoría, portada opcional, estado, destacado, orden y escena inicial. Las categorías tienen nombre y slug único. Conviene conservar los slugs publicados para mantener sus enlaces. La importación conserva `demostracion`, `mirador`, `basilica` y `parque-central`.

| Estado | Tarjeta pública | Visor | Requisitos |
| --- | --- | --- | --- |
| Borrador | No | 404, incluso por URL directa | Permite preparar escenas sin imagen |
| Próximo | Sí | 404 | Permite preparar contenido sin publicarlo |
| Demostración | Sí, identificada como técnica | Sí | Escena inicial propia, todas las panorámicas presentes y válidas |
| Disponible | Sí | Sí | Los mismos controles de integridad |

La escena inicial y los destinos deben pertenecer al mismo recorrido en cualquier estado. No se admiten puntos que vuelvan a su propia escena. No se exige portada, un número mínimo de dos escenas ni un punto de retorno para publicar; revisa manualmente la navegación que quieras ofrecer. Para dos escenas conectadas, crea un punto en cada dirección.

Inicio muestra hasta tres recorridos destacados que no sean demostraciones, por orden ascendente, después nombre y clave interna. Explorar muestra todos los recorridos públicos en ese orden. La primera demostración pública según ese orden alimenta los enlaces y la sección de demostración de Inicio. Las categorías sin recorridos públicos no aparecen como filtros.

Guardar un recorrido publicado vuelve a validar todas sus panorámicas. Editar una escena publicada exige mantener su imagen válida; no se puede vaciar ni añadir una escena incompleta. Las escenas no se trasladan entre recorridos después de guardarse. No hay acciones masivas que eludan la validación para publicar.

Para retirar o reorganizar escenas:

1. Cambia el recorrido a **Borrador**.
2. Cambia o vacía la escena inicial si vas a eliminarla.
3. Elimina o redirige los puntos que llegan a la escena que retirarás.
4. Elimina la escena, completa la nueva estructura y vuelve a publicar.

Django protege los destinos y la escena inicial frente a eliminaciones que dejen referencias rotas. Eliminar un recorrido completo elimina sus registros de escenas y puntos; sus archivos permanecen en disco. En Admin, vuelve primero a borrador para poder confirmar la eliminación de todas sus escenas.

Si alguien retira un original del disco fuera del administrador, la consulta pública oculta el recorrido afectado y su URL devuelve 404. Los errores de red al cargar una imagen en un visor ya abierto conservan el mensaje y el reintento de fase 1.

## Crear dos escenas conectadas

Crea un recorrido como Borrador. En **Escenas**, crea y guarda A y B, eligiendo el mismo recorrido y una panorámica para cada una. Luego vuelve a A y añade un punto hacia B en la tabla **Puntos de navegación**; guarda y repite desde B hacia A. Los destinos de esa tabla se limitan a las otras escenas del recorrido. También se pueden gestionar puntos desde su listado propio, que valida origen y destino.

Configura orientación inicial 0° horizontal y 0° vertical en ambas escenas para comenzar. Un punto con posición 0°/0° aparece al frente. Introduce una etiqueta corta y descriptiva, por ejemplo «Ir al patio». El nombre, el texto informativo y las etiquetas son texto plano; escribir HTML no genera contenido activo.

Vuelve al recorrido, selecciona A como escena inicial, elige estado y guarda. Si usas imágenes técnicas, marca **Demostración**. Los archivos generados `static/panoramas/demo-azul.png` y `demo-ambar.png` permiten practicar sin fotografías reales.

## Orientación compatible con el visor

Todos los ángulos se guardan en **grados**. Son referencias de la imagen, **no una brújula ni norte geográfico**.

| Valor | Dirección |
| --- | --- |
| Horizontal (`yaw`) 0° | Frente, eje −Z |
| Horizontal +90° | Izquierda, eje −X |
| Horizontal −90° | Derecha, eje +X |
| Horizontal ±180° | Atrás, eje +Z |
| Vertical (`pitch`) 0° | Horizonte |
| Vertical positiva | Arriba, hasta +90° |
| Vertical negativa | Abajo, hasta −90° |

La orientación de una **escena** indica hacia dónde mira inicialmente la cámara. Los ángulos de un **punto** ubican ese punto respecto de la imagen, no respecto del giro actual del visitante. El rango horizontal es −180° a +180°; el vertical, −90° a +90°. Se rechazan valores no finitos.

Para transmitir puntos al visor se usan estas coordenadas con ángulos convertidos a radianes y radio `r = 3.5`:

```text
x = -r × sin(yaw) × cos(pitch)
y =  r × sin(pitch)
z = -r × cos(yaw) × cos(pitch)
```

Son unidades de la escena, no metros medidos. El importador convierte las coordenadas antiguas a ángulos conservando su dirección. En la demo, azul comienza a 0°/0°; ámbar a 90°/5°. La cabeza controla la inclinación durante VR; no se fuerza el `pitch` editorial en una sesión inmersiva.

## Carga de imágenes

Las portadas aceptan **JPEG (.jpg/.jpeg), PNG y WebP**. Las panorámicas aceptan **JPEG y PNG estáticos**. Se comprueba el formato real con Pillow, su coincidencia con la extensión, la integridad de los píxeles, dimensiones, peso y, en panorámicas, proporción. No se confía en el MIME enviado por el navegador. Archivos dañados, imágenes animadas y panorámicas que requieren giro EXIF se rechazan con errores de formulario.

Valores predeterminados, configurables mediante `.env`:

| Variable | Valor | Significado |
| --- | --- | --- |
| `COVER_MAX_BYTES` | 12582912 | 12 MiB por portada |
| `COVER_MIN_WIDTH` | 320 | Ancho mínimo de portada |
| `COVER_MIN_HEIGHT` | 180 | Alto mínimo de portada |
| `PANORAMA_MAX_BYTES` | 20971520 | 20 MiB por panorámica |
| `PANORAMA_MIN_WIDTH` | 1024 | Ancho mínimo de panorámica |
| `PANORAMA_MIN_HEIGHT` | 512 | Alto mínimo de panorámica |
| `IMAGE_MAX_DIMENSION` | 8192 | Máximo por lado para cualquier carga |
| `IMAGE_MAX_PIXELS` | 33554432 | Máximo de píxeles totales, ancho × alto |
| `PANORAMA_RATIO_TOLERANCE` | 0.01 | Tolerancia relativa del 1% alrededor de 2:1 |

Se acepta `abs(ancho / (2 × alto) - 1) <= tolerancia`. Con 0.01, la relación ancho/alto admitida es **1.98 a 2.02**, incluidos ambos extremos. Los mínimos de dimensiones se siguen aplicando. La configuración admite tolerancia entre 0 y 0.05; `manage.py check` detecta límites no positivos y tolerancias fuera de rango. Reinicia el servidor después de cambiar límites.

**La proporción 2:1 no garantiza por sí sola que una imagen sea esférica o equirectangular.** Debe cubrir 360° horizontal y 180° vertical en proyección equirectangular completa. Una fotografía plana estirada puede pasar la comprobación matemática y no sirve como panorama. Revisa visualmente horizonte, unión de los extremos, cenit y nadir. No se analiza automáticamente el contenido geográfico.

Las demos se generan en PNG 2048 × 1024, de aproximadamente 40 KB cada una. Para fotografías reales, una exportación JPEG 4096 × 2048 es un punto de partida dentro de los límites; comprueba su calidad y rendimiento en el dispositivo. El visor sigue comprobando el límite de textura de la GPU y usa la misma tolerancia de proporción que el servidor.

## Originales y miniaturas

Las cargas se guardan con nombres UUID únicos en `media/covers/originals/` y `media/panoramas/originals/`. Se mantienen los bytes originales; subir dos archivos llamados igual o reemplazar una imagen no sobrescribe el archivo anterior.

Se generan miniaturas WebP de hasta 640 × 360 para Admin y tarjetas, bajo `media/thumbnails/`. No sustituyen la panorámica del visor. El visor solicita la imagen de cada escena cuando se abre y libera la textura anterior; no precarga la segunda escena.

No hay borrado automático de archivos al eliminar registros, quitar imágenes o reemplazarlas. Esto incluye miniaturas y posibles archivos huérfanos de una operación fallida: las transacciones de la base no revierten el sistema de archivos. Cualquier limpieza debe ser deliberada, con respaldo y comprobando antes las referencias. Conserva juntos la base y `media/`; ambos están excluidos de Git.

## Importación y contenido heredado

```sh
.venv/bin/python manage.py migrate
.venv/bin/python scripts/generate_panoramas.py
.venv/bin/python manage.py import_phase1
```

No se carga ni descarga contenido en migraciones. El comando valida todos los archivos de los recorridos nuevos antes de escribir registros. Si faltan las imágenes técnicas, indica que hay que generarlas. Copia sus originales al almacenamiento de cargas y crea miniaturas. Es posible repetirlo sin duplicados ni cambios en recorridos ya existentes, incluso si se cambió su slug conservando la clave de importación.

`content/tours.json` y `tours/legacy.py` son exclusivamente la fuente y el lector del importador. No se editan para mantener el catálogo diario. Los scripts que modifiquen modelos deben usar `save()` completo por instancia; las operaciones masivas y `update_fields` se bloquean porque omiten validación. No modifiques estas tablas mediante SQL directo.

## Portada general e identidad

El logo original sigue íntegro en `static/images/logo.png`. La portada general del Inicio mantiene la configuración de fase 1 en `content/site.json`, fuera de los campos de recorrido:

```json
{
  "hero_desktop": "media/covers/esquipulas-mirador-amplia.webp",
  "hero_mobile": "media/covers/esquipulas-mirador-movil.webp",
  "hero_alt": "Vista amplia de Esquipulas desde el mirador"
}
```

Estas imágenes generales se colocan manualmente en las rutas indicadas. El formulario y los validadores de cargas de Admin corresponden a portadas de recorridos y panorámicas, no a esta configuración general. Si aún no hay fotografía, conserva sus campos en `null`: aparece el diseño existente con «imagen pendiente». La imagen debe corresponder a su descripción; verifica el recorte en computadora y móvil. Esta fase no incorpora audio ni video.
