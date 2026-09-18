# Mantener el contenido sin cambiar plantillas

`content/tours.json` contiene el catálogo. `content/site.json` contiene las imágenes de la portada del inicio. Django valida el catálogo en `manage.py check`, al iniciar el servidor y al leerlo para las páginas.

## Archivos

El logo adjunto está copiado íntegramente en `static/images/logo.png`. Si se reemplaza, utiliza el archivo definitivo, conserva su proporción y el texto alternativo. El proyecto no lo redibuja.

Coloca las fotografías, panorámicas y audios reales en `media/`, excluido de Git. Crea las subcarpetas `covers/`, `panoramas/` y `audio/` según necesites. En desarrollo Django sirve `/media/` si `DJANGO_DEBUG=true`; en una publicación futura habría que servir estos archivos explícitamente. No añadas grandes archivos al repositorio.

Las rutas en JSON son relativas: `media/panoramas/mirador-01.jpg` se resuelve a `/media/panoramas/mirador-01.jpg`. Las rutas sin prefijo `media/` se buscan en los estáticos; por ejemplo `panoramas/demo-azul.png`. No uses URLs externas, rutas absolutas ni `..`.

## Portada de inicio

```json
{
  "hero_desktop": "media/covers/esquipulas-mirador-amplia.webp",
  "hero_mobile": "media/covers/esquipulas-mirador-movil.webp",
  "hero_alt": "Vista amplia de Esquipulas desde el mirador"
}
```

El contenido real debe corresponder a esa descripción. Prepara una vista amplia de **toda Esquipulas desde el mirador**: formato apaisado para computadora y un recorte vertical específico para celular. El elemento `<picture>` cambia de archivo a 640 px; `object-fit: cover` llena el espacio y una capa oscura mantiene legible el título. Sitúa los detalles esenciales fuera de la zona cubierta por el texto y verifica ambos tamaños. Si aún no hay imagen, conserva los campos en `null`; aparece el fondo abstracto con «imagen pendiente».

## Recorridos

Cada recorrido tiene `id`, `slug`, `name`, `description`, `category`, `cover`, `status`, `initial_scene` y `scenes`.

| Campo | Reglas |
| --- | --- |
| `id`, `slug` | Únicos entre recorridos. Minúsculas ASCII, números y guiones; no espacios |
| `name`, `description` | Texto real revisado, sin HTML necesario |
| `category` | `demostracion`, `vistas`, `patrimonio` o `espacios` |
| `cover` | Ruta relativa o `null`; se muestra una portada pendiente si falta |
| `status` | `demo` para escenarios técnicos; `available` para recorridos reales preparados; `upcoming` para próximos |
| `initial_scene` | ID de una escena del recorrido; `null` para próximos |
| `scenes` | Lista de escenas; vacía para próximos |

Para habilitar Mirador, añade escenas reales y su `initial_scene`, configura una portada y cambia `status` de `upcoming` a `available`. El catálogo mostrará «Disponible» y un enlace al visor automáticamente. Conserva la demostración separada e identificada: no la renombres como un lugar real para quitarle la advertencia.

## Escenas y puntos

```json
{
  "id": "vista-principal",
  "name": "Vista principal",
  "panorama": "media/panoramas/mirador-01.jpg",
  "orientation": {"yaw": 0, "pitch": 0},
  "text": "Descripción del contenido real, verificada antes de publicarse.",
  "audio": null,
  "hotspots": [
    {"id": "a-segunda-vista", "label": "Ir a la segunda vista", "position": [0, 0, -3.5], "destination": "segunda-vista"}
  ]
}
```

Este fragmento necesita una segunda escena con ID `segunda-vista` en el mismo recorrido y un punto de retorno. Los ID de escena son únicos dentro del recorrido; los de puntos, dentro de la escena. `yaw` admite de −180 a 180 grados y `pitch` de −90 a 90. Cero mira al frente (`−Z`), yaw positivo gira a la izquierda y pitch positivo mira arriba. Los valores son referencias de la imagen, **no norte geográfico**.

`position` contiene coordenadas `[x, y, z]` de la escena. Usa distancias cercanas a 3–5 unidades; el rayo tiene alcance de 15. No representan metros medidos. La cámara estacionaria arranca en el origen. Ejemplos: frente `[0, 0, -3.5]`, izquierda `[-3.5, 0, 0]`, derecha `[3.5, 0, 0]`, atrás `[0, 0, 3.5]`. Eleva `y` para subir un punto. La escena ámbar tiene yaw 90° y su punto está a la izquierda del origen, por lo que aparece al frente al entrar.

Para un punto definido por yaw y pitch en radianes y una distancia `r`:

```text
x = -r × sin(yaw) × cos(pitch)
y =  r × sin(pitch)
z = -r × cos(yaw) × cos(pitch)
```

En VR se conserva la orientación natural de la cabeza; no se fuerza la inclinación de la cámara para evitar una rotación artificial. El giro inicial horizontal se aplica al conjunto de cámara/mandos. Valida comodidad, posición y legibilidad físicamente.

## Panorámicas

- Deben cubrir 360° horizontal y 180° vertical mediante proyección equirectangular completa **2:1**. Una imagen plana estirada no sirve.
- Empieza con 4096 × 2048 JPG o WebP optimizado; comprueba calidad, peso y límites del dispositivo antes de subir resolución. El visor valida la proporción exacta y el tamaño máximo de textura disponible.
- Las demos se regeneran con `.venv/bin/python scripts/generate_panoramas.py`: PNG 2048 × 1024 de aproximadamente 40 KB cada una.
- El visor solicita una panorámica al entrar en su escena. Al sustituirla, libera textura, imagen y URL temporal; aborta solicitudes anteriores y limita su espera. Conserva la anterior si falla la siguiente, muestra un error y permite reintentar. En VR la recuperación está dentro del espacio 3D.
- La miniatura de demostración del catálogo puede cargar la imagen pequeña para su tarjeta. El visor no precarga la segunda panorámica.

Sin `audio` no se crea reproductor. Si se configura audio, usa archivo local y proporciona descripción; el reproductor requiere una acción del visitante, se detiene al cambiar de escena y al entrar en VR. Esta fase no ofrece audio inmersivo ni narración oficial.

## Validación

Después de modificar JSON, ejecuta `.venv/bin/python manage.py check` y `.venv/bin/python manage.py test`. Se validan ID, duplicados, categorías, estados, escenas iniciales, destinos, rutas relativas, orientaciones finitas y posiciones válidas. La existencia, decodificación y proporción de una imagen se comprueban al cargar el visor, con error recuperable si no es utilizable. Verifica manualmente las nuevas portadas y textos en celular y computadora.
