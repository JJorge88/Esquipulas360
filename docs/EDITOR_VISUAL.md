# Editor visual de escenas — fase 3

El editor añade una herramienta a Django Admin para colocar puntos y elegir la orientación inicial mirando la panorámica. Usa A-Frame 1.8.0, las imágenes y los modelos existentes. No cambia el estado de publicación ni crea migraciones.

## Abrirlo

1. Inicia sesión en `/admin/` con un usuario autorizado.
2. Abre **Escenas** y selecciona una escena guardada.
3. Guarda cualquier modificación pendiente del formulario de Admin.
4. Pulsa **Editar puntos visualmente** en las herramientas superiores de esa escena.

Puedes editar escenas de recorridos en borrador. Si la escena aún no tiene panorámica, el editor indica que debes cargarla desde Admin. Para añadir un punto tiene que existir otra escena del mismo recorrido.

## Añadir y modificar puntos

- Arrastra con ratón o con un dedo para mirar alrededor. Esto no añade puntos.
- Pulsa **Añadir punto** y luego haz un clic o toque breve sobre la panorámica. Aparece un marcador de vista previa.
- Escribe la **etiqueta** y elige la **escena de destino**. El selector ofrece únicamente otras escenas del mismo recorrido.
- Pulsa **Guardar punto**. El mensaje «Punto guardado» aparece solo después de que el servidor confirme la operación.
- Selecciona un punto desde la lista o haciendo clic en su marcador. En edición, seleccionarlo no cambia de escena. La lista también centra la vista en el punto.
- Cambia etiqueta o destino, o pulsa **Cambiar posición** y haz un nuevo clic. Termina con **Guardar punto** o **Cancelar**.
- **Eliminar punto** solicita confirmación. Cancelarla conserva el punto; confirmarla envía la eliminación al servidor.

Solo se prepara un punto a la vez. Cambiar de punto o iniciar otro mientras hay cambios solicita confirmación para descartarlos. El marcador y los números informativos de posición permiten revisar el resultado; no es necesario escribir ángulos.

Un clic de colocación debe recorrer como máximo 6 píxeles y durar como máximo 800 ms. Si arrastras, sales del lienzo, cancelas el gesto o usas más de un dedo, no se coloca un punto. Moverse y volver al lugar inicial sigue contando como arrastre.

## Elegir la vista inicial

1. Mira hacia la dirección deseada.
2. Pulsa **Usar esta vista al iniciar**. La dirección queda pendiente, indicada en el panel.
3. Pulsa **Guardar orientación** para guardarla, o **Cancelar orientación** para volver a la anterior.
4. **Restaurar vista guardada** vuelve a la dirección almacenada; pide confirmación si descarta una orientación pendiente.

Los puntos y la orientación tienen guardados separados. Guardar la orientación no guarda ni descarta un punto en edición.

Se reutilizan los campos `yaw` y `pitch`: grados, horizontal −180° a +180° (positivo hacia la izquierda) y vertical −90° a +90° (positivo hacia arriba). El clic se convierte desde un rayo de la cámara al espacio de la panorámica; no depende de la dirección inicial ni del giro actual del visitante. El radio visual de los marcadores sigue siendo 3.5 unidades. Consulta las fórmulas en [CONTENIDO.md](CONTENIDO.md).

El editor y el visor comparten las funciones de orientación, conversión y control táctil en `panorama-core.js`. En VR se mantiene el comportamiento anterior: la cabeza controla la inclinación. El editor se utiliza en pantalla; la vista de prueba conserva los controles WebXR del visor.

## Probar sin publicar

**Probar datos guardados** abre otra pestaña con el visor existente y una indicación permanente **PRUEBA PRIVADA · Solo datos guardados**. Puedes seguir los puntos y usar el selector de escenas para probar ida y vuelta. Empieza por la escena desde la que abriste el editor, incluso si el recorrido aún no tiene escena inicial elegida.

Los cambios pendientes permanecen en la pestaña del editor y no aparecen en la prueba; el editor muestra un aviso. Después de guardar más cambios, vuelve a abrir o recarga la prueba para verlos. La vista privada consulta la base y nunca recibe la edición pendiente desde el navegador.

La prueba no publica borradores ni modifica datos mediante GET. Las páginas públicas siguen ocultando borradores y devolviendo 404 para sus recorridos. Si una escena de destino todavía no tiene imagen, la prueba presenta el error recuperable habitual del visor.

## Permisos y privacidad

Se conserva la autenticación y los permisos estándar de Django; no se añaden cuentas ni contraseñas predeterminadas.

| Acción | Requisitos |
| --- | --- |
| Abrir prueba privada y cargar sus panorámicas | Usuario activo y personal (`is_staff`); permiso de ver o cambiar cada uno de: recorrido, escena y punto de navegación |
| Abrir editor o consultar sus datos | Los permisos anteriores y al menos uno para añadir/cambiar/eliminar puntos o cambiar escenas |
| Crear puntos | Además, `tours.add_navigationpoint` |
| Modificar etiqueta, destino o ubicación | Además, `tours.change_navigationpoint` |
| Eliminar puntos | Además, `tours.delete_navigationpoint` |
| Guardar orientación inicial | Además, `tours.change_scene` |

El enlace se muestra solo a usuarios que pueden entrar, y cada página y operación vuelve a comprobar permisos en el servidor. Un usuario de solo lectura puede ver una prueba privada si tiene los tres permisos de lectura; no puede entrar al editor ni guardar cambios. Los botones que su usuario no puede utilizar quedan desactivados u ocultos según la acción.

Las rutas están bajo `/admin/tours/scene/<id>/`. La página `editor/`, sus datos `editor/data/`, `preview/` y `panorama/` son privadas y no se almacenan en caché. El editor y la prueba usan la ruta protegida de panorámicas, no enlaces de archivos en su JSON. Se mantienen el almacenamiento de originales y las rutas públicas de fase 2; esta fase no añade un sistema general de archivos confidenciales ni cambia el servicio de `/media/`.

Las escrituras usan POST para crear, PATCH para editar y orientar, y DELETE para eliminar, todas con protección CSRF. El servidor rechaza etiquetas vacías, campos extra, destinos ajenos o iguales al origen, puntos de otra escena y coordenadas fuera de rango, no numéricas o no finitas. Se siguen usando los formularios y `save()` validado de fase 2; guardar orientación conserva el resto de los campos de la escena.

## Errores y cambios pendientes

El editor conserva etiqueta, destino y posición ante un error de validación, conexión o permisos. No muestra éxito sin respuesta válida del servidor. Si la sesión caduca, inicia sesión en otra pestaña y reintenta. No recargues una edición pendiente para resolver un error de conexión.

Cada punto nuevo utiliza una clave aleatoria estable durante su edición: si el servidor guardó y la respuesta se perdió, reintentar no crea otro punto. Las revisiones de puntos y orientación detectan cambios guardados desde otra ventana y evitan sobrescribirlos silenciosamente. Ante un conflicto, conserva tu edición y revisa la versión guardada en otra pestaña antes de decidir qué mantener.

Salir por el enlace al administrador pide confirmación cuando hay cambios. Recargar o cerrar utiliza el aviso de cambios pendientes del navegador; su presentación depende del navegador. No existe guardado automático ni almacenamiento local sin conexión. Cerrar forzosamente el navegador o el sistema no garantiza recuperar una edición sin guardar.

Los cambios confirmados en un recorrido ya publicado están disponibles para los visitantes que vuelvan a cargarlo. Trabaja en borrador si necesitas preparar varios cambios antes de mostrarlos.

## Actualización y pruebas

Desde fase 2 no hay dependencias nuevas, cambios de versiones ni nuevas migraciones. Reinicia el servidor para cargar los archivos actualizados. Puedes verificar:

```sh
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py test
npm run build
npm run test:e2e
npm run test:editor
```

La suite pública usa la demostración local de fase 2. La suite del editor crea su propia base y archivos temporales en el puerto 8013, importa la demostración y prepara borradores desechables. Su usuario de prueba tiene contraseña inutilizable y su sesión temporal se elimina al cerrar el servidor; no modifica usuarios ni recorridos de la instalación real.

Las capturas del editor se guardan en `artifacts/editor-desktop.png` y `artifacts/editor-mobile.png`. Reporte del editor: `npx playwright show-report artifacts/editor-report`. Los fallos quedan en `artifacts/editor-test-results/`. Estos archivos se excluyen de Git.

La prueba física en Meta Quest 2 continúa pendiente. No se añaden audio, video, pagos, modo guiado, funcionamiento sin internet ni despliegue.
