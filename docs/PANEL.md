# Panel visual · fase 4

Abre **http://127.0.0.1:8000/panel/**. Usa la misma cuenta que en Django Admin. `/admin/` sigue disponible para gestionar usuarios, grupos, permisos y tareas técnicas. El panel tiene plantillas propias, conserva el logo y las tipografías locales, y usa azul `#132238`, blanco cálido `#fbf9f6` y dorado `#fece57`.

## Actualizar la instalación de fase 3

No hay migraciones nuevas ni cambios de dependencias. No regeneres ni reimportes contenido. Conserva `.env`, `db.sqlite3` y `media/`.

```sh
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
npm run build
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

Reinicia el servidor si estaba funcionando sin recarga automática. Si ya está escuchando en el puerto 8000, no inicies otra copia. `npm run build` prepara los recursos locales existentes; no instala dependencias nuevas.

Si todavía no tienes una cuenta, créala de forma interactiva:

```sh
.venv/bin/python manage.py createsuperuser
```

No se crean usuarios ni contraseñas predeterminados. El panel reutiliza autenticación, sesiones y permisos de Django. Cerrar sesión envía POST con CSRF y también cierra la sesión compartida con `/admin/`.

## Flujo cotidiano

1. En **Categorías**, crea la categoría que utilizarás, si no existe.
2. Pulsa **Crear recorrido**. Completa nombre, descripción y categoría, y guarda en **Borrador**. La portada es opcional. La dirección se genera del nombre si la dejas vacía; conserva la dirección de un recorrido existente para mantener sus enlaces.
3. Dentro del recorrido, en **Escenas**, pulsa **Añadir escena**. Ponle nombre, sube su panorámica y guarda. Repite para la segunda escena. Usa el campo **Orden**, por ejemplo 0 y 1: el número menor aparece primero.
4. Abre **Editar puntos** en la primera escena. Activa **Añadir punto**, haz clic en la panorámica, indica una etiqueta y selecciona la segunda escena. Guarda el punto. Repite en la segunda escena para crear el regreso a la primera.
5. Para orientar cada escena, arrastra para mirar, pulsa **Usar esta vista al iniciar** y después **Guardar orientación**. **Restaurar vista guardada** permite comprobarla. El editor conserva todas las herramientas de fase 3, incluida la reubicación y eliminación confirmada de puntos.
6. **Probar datos guardados** o **Vista previa privada** permite recorrer escenas sin publicar. Un aviso distingue esta prueba del visor público. Sus rutas y panorámicas privadas requieren los permisos correspondientes. El editor vuelve al recorrido; la prueba vuelve al editor, o al recorrido para usuarios de consulta.
7. Regresa al recorrido, selecciona la **Escena inicial** y el estado. **Antes de publicar** muestra qué falta. El servidor vuelve a comprobar las relaciones y todas las imágenes al guardar. Para imágenes técnicas elige **Demostración**; para un recorrido completo de un lugar real, **Disponible**.
8. Comprueba el resultado en **Ver sitio**. Puedes editarlo otra vez desde el panel sin cambiar sus rutas públicas.

**Resumen** usa cifras reales de recorridos disponibles, borradores, próximos y escenas. Las demostraciones tienen su propio estado y no se suman a disponibles. “Recientes” significa últimos registros creados, por identificador de creación; no se inventan fechas ni estadísticas de visitas. Solo se muestran cifras de modelos que el usuario puede consultar.

**Recorridos** muestra miniaturas, categorías, estados, cantidad de escenas y acciones autorizadas. La búsqueda ignora mayúsculas y acentos; se combina con categoría y estado. Los resultados están paginados de doce en doce. Los estados vacíos indican cómo comenzar o limpiar filtros.

En móvil, abre el menú con el botón superior. Se puede cerrar con Escape o tocando fuera. El foco vuelve al botón. Los campos tienen etiquetas, errores asociados y foco visible; los botones principales permanecen accesibles mientras recorres formularios largos.

## Guardado y archivos

Los formularios muestran errores junto a cada campo. Con JavaScript, una respuesta de validación o un fallo de conexión conserva texto y archivos seleccionados, incluida su vista previa, para reintentar. Los campos quedan temporalmente sin interacción durante el envío. Solo una confirmación del servidor da lugar al mensaje de guardado. Si la sesión vence, puedes iniciar sesión en otra pestaña y volver a intentar, sin recargar el formulario que conserva los cambios.

Antes de salir, recargar o cerrar sesión se advierte de cambios pendientes. Abrir un enlace en otra pestaña con cambios pendientes avisa que allí se verá contenido guardado. Los formularios también funcionan sin JavaScript; en ese caso, tras un error de carga, el navegador obliga a volver a seleccionar los archivos. No es un almacenamiento automático de borradores del formulario: cerrar la aplicación de manera forzada puede perder cambios sin guardar.

- **Portada:** JPEG, PNG o WebP. Los límites configurados se muestran junto al campo.
- **Panorámica:** JPEG o PNG. “Sube una panorámica esférica completa en formato 2:1”. Por defecto: mínimo 1024 × 512, máximo 20 MiB, proporción 2:1 con tolerancia relativa ±1 %. La proporción por sí sola no garantiza que una foto cubra la esfera completa.
- Se reutilizan los validadores de fase 2 para contenido real del archivo, formato, dimensiones, peso, orientación EXIF y proporción. Véase [CONTENIDO.md](CONTENIDO.md).
- Se conservan originales y nombres únicos. Las miniaturas son derivados ligeros. Reemplazar archivos o eliminar registros no borra archivos físicos.
- Los textos editoriales se escapan y se muestran como texto plano. No se añade interpretación de HTML.

## Permisos

Todas las cuentas del panel deben ser activas y tener **Es personal** marcado. El superusuario o un responsable con permiso de usuarios/grupos asigna permisos en `/admin/`.

| Tarea | Permisos necesarios |
| --- | --- |
| Consultar recorridos o categorías | Ver o cambiar el modelo correspondiente |
| Crear recorrido o categoría | Añadir el modelo correspondiente |
| Editar información, portada o publicación | Cambiar recorrido |
| Consultar escenas dentro de un recorrido | Ver/cambiar recorrido y ver/cambiar escena |
| Añadir o cambiar una escena | Ver/cambiar recorrido y añadir/cambiar escena, respectivamente |
| Previsualizar y acceder a panorámicas privadas | Ver o cambiar cada uno de: recorrido, escena y punto de navegación |
| Abrir el editor visual | Permisos de previsualización y al menos uno: añadir/cambiar/eliminar punto o cambiar escena |
| Crear, modificar o eliminar un punto | Permisos del editor más añadir, cambiar o eliminar punto, respectivamente |
| Guardar orientación inicial | Permisos de previsualización y cambiar escena |
| Eliminar registros | Eliminar el modelo y los registros dependientes que se eliminarían, igual que Django Admin; para escenas también consultar recorrido |

Los permisos se aplican en el servidor a páginas y endpoints; ocultar un enlace no es la protección. Las peticiones de escritura llevan CSRF. GET no modifica contenido. Los endpoints de edición validan además recorrido de origen/destino, coordenadas finitas y revisiones del editor. Un usuario de consulta puede ver formularios deshabilitados; un POST manual sigue recibiendo 403.

Un editor cotidiano puede recibir ver/añadir/cambiar para categorías, recorridos, escenas y puntos. Otorga eliminar solo cuando corresponda. No necesita permisos de gestión de usuarios o grupos.

## Eliminación y publicación

- **Borrador:** no aparece en el sitio público; la URL pública devuelve 404.
- **Próximo:** tarjeta visible sin visor público.
- **Demostración y Disponible:** requieren escena inicial válida y panorámicas válidas en todas las escenas.
- Una escena publicada no puede perder su panorámica. Para eliminarla, vuelve el recorrido a borrador, cambia o vacía la escena inicial y elimina o cambia los puntos de otras escenas que la usan como destino.
- Una categoría en uso no se elimina: primero cambia la categoría de sus recorridos.
- Cada eliminación tiene una pantalla de confirmación con las cantidades afectadas, o explica el bloqueo. La operación vuelve a comprobar relaciones y permisos en POST.
- La eliminación de un recorrido también afecta sus escenas y puntos. El panel usa el recolector de Django Admin para exigir los permisos de todos los modelos afectados y respetar sus protecciones.

## Implementación y pruebas

No se modifican los modelos ni la migración inicial. `tours/panel.py` organiza acceso, consultas y formularios; `tours/panel_forms.py` adapta presentación y campos; `tours/panel_urls.py` define las rutas. Las reglas siguen en los modelos/validadores y el editor sigue en `tours/editor.py`. La plantilla del editor recibe enlaces según se abra desde Admin o panel. No se duplica su JavaScript ni se cambia la conversión angular.

Plantillas propias en `templates/panel/`; widget de archivo en `tours/templates/panel/file_input.html`; estilos y comportamiento en `static/css/panel.css` y `static/js/panel.js`. El catálogo y el visor público conservan sus plantillas y controles.

```sh
.venv/bin/python manage.py test
npm run test:panel
npm run test:editor
npm run test:e2e
```

Las tres suites de navegador usan bases y archivos temporales independientes: panel en 8014, editor en 8013 y público en 8015. La del panel genera una contraseña aleatoria para probar el inicio de sesión real; la cuenta y sus datos se eliminan al terminar. El manifiesto temporal de sesión tiene permisos de lectura/escritura solo para el propietario y está excluido de Git. No se toca la cuenta ni el contenido de la instalación local. `TEST_BASE_URL` permite dirigir explícitamente las pruebas públicas a otro servidor; estas esperan el catálogo original de demostración.

Capturas en `artifacts/panel-summary.png`, `panel-tours.png`, `panel-edit.png`, `panel-login.png`, `panel-mobile-summary.png` y `panel-mobile-edit.png`. Las capturas corresponden a la base temporal de demostración, no a las estadísticas de tu instalación. Reporte del panel en `artifacts/panel-report/index.html`. Resultados completos en [VERIFICACION.md](VERIFICACION.md).

La prueba física en Meta Quest 2, Safari/iPhone y otros dispositivos reales continúa pendiente. La entrega se limita a la fase 4; no incluye push ni despliegue.
