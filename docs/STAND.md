# Fase 5 · Modo stand

Un operador controla la sesión desde la computadora, un participante abre la web en su Quest 2 y una ventana de espectador muestra la escena confirmada y la mirada del participante. La televisión se conecta **a la computadora como segunda pantalla**. No hay PCVR, captura de pantalla, cable de video al Quest ni transmisión de menús del sistema.

La implementación continúa la fase 4 (`9408289`). Mantiene el panel, Admin, editor, datos, logo y visor normal. La prueba física de Quest 2, especialmente la orientación inmersiva, **sigue pendiente**.

## Actualización desde fase 4

Desde la carpeta del proyecto, conserva `.env`, `db.sqlite3` y `media/`. Respalda juntos la base y los archivos antes de actualizar. No regeneres ni reimportes el contenido existente.

```sh
uv sync --locked
npm ci
npm run build
.venv/bin/python manage.py migrate
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
```

Sin `uv`, sustituye su comando por:

```sh
.venv/bin/python -m pip install --require-hashes -r requirements.lock
```

La única migración nueva es `stand/0001_initial`: estado vigente de la sesión, escena solicitada/confirmada, secuencia, caducidad y resúmenes HMAC de credenciales. No modifica recorridos, imágenes ni usuarios. Genera permisos estándar de Django. No importa datos ni hace descargas.

Nuevas dependencias directas: **Channels 4.3.2 con Daphne y channels-redis 4.3.0; redis-py 6.4.0**. Daphne 4.2.3 y sus dependencias transitivas están fijados en los archivos de bloqueo. Se necesita además **Redis 7.4**, fuera del proceso Python. Se eligieron WebSockets para notificar cambios y transportar orientación con baja latencia; Redis permite presencia, exclusión de conexiones y comunicación entre procesos. Es el backend de canales mantenido oficialmente para este uso; un backend en memoria no coordinaría procesos separados. [Documentación oficial de Channels](https://channels.readthedocs.io/en/stable/topics/channel_layers.html).

## Servicios para una prueba local en computadora

Inicia Docker Desktop y ejecuta:

```sh
docker compose -f compose.stand.yml up -d
docker compose -f compose.stand.yml exec redis redis-cli ping
.venv/bin/python manage.py runserver 127.0.0.1:8000 --noreload
```

El segundo comando debe responder `PONG`. Reinicia cualquier servidor anterior a esta fase: `runserver` ahora usa Daphne/ASGI y acepta WebSockets. No uses `--noworker` ni un servidor WSGI para el stand. La ejecución aquí documentada es una prueba local supervisada, no un despliegue de producción.

- Operador: `http://127.0.0.1:8000/panel/stand/`.
- Vinculación: `http://127.0.0.1:8000/stand/`.
- El espectador se abre con el botón del operador; su dirección sola no da acceso.
- Para parar Redis: `docker compose -f compose.stand.yml down`.

Si ya dispones de Redis local, puedes usarlo mediante `STAND_REDIS_URL`. No ejecutes dos servicios intentando ocupar el mismo puerto. La configuración Compose limita el puerto a `127.0.0.1:6379`, sin volúmenes y con RDB/AOF desactivados. No abras Redis en la red del evento.

## Usuarios y permisos

Se usa la cuenta y sesión existentes de Django. En `/admin/`, un superusuario puede asignar a personal activo los permisos de **sesión de stand**:

| Permiso | Operación |
| --- | --- |
| `stand.view_standsession` | Ver sus sesiones y estado |
| `stand.add_standsession` | Crear sesión |
| `stand.change_standsession` | Dirigir, finalizar, renovar código sin usar y abrir espectador; también permite consultar |

Para un operador normal, asigna los tres. No necesita permisos de modificar recorridos ni de administrar usuarios. Cada operador accede a sus propias sesiones; un superusuario puede acceder a todas. Una sesión activa por operador impide duplicados al repetir Crear sesión. Los permisos se comprueban en páginas, escrituras y conexiones, no solo en el menú. Cerrar la sesión de Django revoca la conexión del operador al siguiente latido.

No se crean cuentas o contraseñas predeterminadas. Si aún no tienes administrador:

```sh
.venv/bin/python manage.py createsuperuser
```

## Operación con computadora, Quest y televisión

1. Conecta la televisión a la computadora mediante su salida de pantalla habitual y selecciona **extender escritorio**. Mantén el panel en la pantalla del operador.
2. Abre **Modo stand**, selecciona un recorrido **Disponible** o **Demostración** completo y pulsa **Crear sesión**. Los borradores y próximos no se ofrecen ni se aceptan por el servidor.
3. En el navegador del Quest, abre la dirección HTTPS de `/stand/` e introduce el código de ocho caracteres. No introduzcas la contraseña administrativa en el visor.
4. El código caduca a los cinco minutos y sirve una sola vez. Puedes **Renovar código sin usar**. Después de vincular, otro intento con ese código se rechaza; para otro participante/visor, finaliza y crea una nueva sesión.
5. Comprueba **Visor conectado**. «Vinculado · Desconectado» significa que se usó el código, pero ya no llegan latidos. Dos pestañas del mismo visor no pueden ocupar la sesión simultáneamente: la segunda muestra un aviso y no expulsa a la primera.
6. Pulsa **Abrir pantalla del público**, arrastra esa nueva ventana a la televisión y pulsa **Pantalla completa**. Verás una vista de espera hasta recibir la primera escena confirmada. Abrir otra ventana revoca la credencial de espectador anterior; la nueva ventana toma su lugar y la anterior muestra que perdió el acceso.
7. Pulsa **Iniciar recorrido**. El participante pulsa por sí mismo **Entrar en VR** cuando esté listo. Ninguna orden del panel solicita entrada remota en WebXR.
8. Las miniaturas envían escenas; el selector y **Cambiar recorrido** envían otro recorrido. «Orden enviada» no significa «aplicada»: espera la confirmación del visor. El participante puede mirar libremente y navegar por puntos o selector; esos cambios se reflejan en ambas pantallas.
9. **Volver al inicio** regresa a la escena inicial y cierra los paneles de información/avisos de la aplicación. Conserva la mirada y la sesión WebXR; no recalibra físicamente el visor. Los cambios usan un fundido breve sin orientar automáticamente la cabeza.
10. **Finalizar sesión** pide confirmación, avisa a ambas pantallas e invalida sus credenciales. No fuerza la salida del sistema WebXR; el participante puede usar Salir de VR o el control del sistema. La sesión también caduca tras cuatro horas por defecto.

En computadora puedes ensayar los tres roles con perfiles o ventanas privadas independientes. La ventana de espectador no tiene controles de escena ni administración; arrastrar el ratón en ella no mueve la mirada del participante. Su imagen es la representación monoscópica de la panorámica de nuestra web, no una copia exacta de cada ojo, del HUD ni del sistema operativo del Quest.

## HTTPS y WSS válidos para el Quest

`localhost` dentro del Quest se refiere al propio Quest. `http://192.168.x.x:8000` no proporciona el contexto seguro requerido para VR. El dispositivo debe poder resolver y alcanzar un nombre HTTPS cuyo certificado sea **válido, no caducado y confiable para su navegador**.

Prepara en la red privada un proxy HTTPS que soporte WebSocket Upgrade, un nombre DNS que resuelva a la computadora y un certificado con ese nombre. Puedes usar un certificado emitido por una autoridad reconocida o una autoridad interna previamente instalada y confiable en el dispositivo; un certificado autofirmado con advertencia no basta. El DNS, certificado y confianza del Quest deben comprobarse antes del evento. No se han creado certificados, túneles ni servicios públicos como parte de esta fase.

Ejemplo para un proxy Caddy ya instalado, sustituyendo el nombre y las rutas por valores reales:

```caddyfile
https://stand.tu-dominio.example {
    tls /ruta/privada/fullchain.pem /ruta/privada/privkey.pem
    reverse_proxy 127.0.0.1:8000 {
        header_up X-Forwarded-Proto https
    }
}
```

`stand.tu-dominio.example` es un marcador, no un dominio configurado. Caddy debe ser el único punto de entrada de la red y debe sustituir el encabezado indicado. Django puede continuar escuchando únicamente en `127.0.0.1:8000`. La clave privada queda fuera del repositorio. Con un archivo ya preparado, el comando de ejecución es `caddy run --config /ruta/privada/Caddyfile`.

Adapta estas variables en tu `.env`, conservando la clave secreta y el resto de configuración:

```dotenv
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,stand.tu-dominio.example
DJANGO_CSRF_TRUSTED_ORIGINS=https://stand.tu-dominio.example
STAND_ALLOWED_ORIGINS=https://stand.tu-dominio.example
DJANGO_SESSION_COOKIE_SECURE=true
DJANGO_CSRF_COOKIE_SECURE=true
DJANGO_TRUST_PROXY=true
DJANGO_SECURE_SSL_REDIRECT=true
```

Reinicia Django. Abre operador, vinculación y espectador por **ese origen HTTPS**; las cookies seguras no funcionarán desde el acceso HTTP anterior. Los WebSockets eligen `wss://` automáticamente. `DJANGO_TRUST_PROXY` solo se debe activar para un proxy controlado que sustituya `X-Forwarded-Proto`; no confíes en encabezados enviados directamente por visitantes. Verifica que la red permita llegar al puerto HTTPS de la computadora y que no tenga aislamiento entre clientes. No expongas el puerto de Django ni Redis fuera de la computadora en este esquema.

Los orígenes WebSocket se comparan por esquema, host y puerto, sin comodines. Si utilizas un puerto HTTPS distinto de 443, inclúyelo tanto en la URL como en ambos ajustes de orígenes. [Protección de origen en Channels](https://channels.readthedocs.io/en/stable/topics/security.html).

El límite de vinculación usa la IP de la conexión, **no confía en X-Forwarded-For**: 8 intentos por minuto e IP y 60 globales por minuto. Detrás del proxy todos pueden compartir el mismo límite de IP; para este stand de un visor resulta suficiente, pero configura también un límite por cliente en tu proxy si das acceso a una red mayor. No registres cuerpos de vinculación, cookies, mensajes WebSocket ni cabeceras de autorización.

## Recuperación de fallos

| Situación | Qué muestra / qué hacer |
| --- | --- |
| Se interrumpe Wi-Fi o el transporte | Se conserva la imagen ya cargada con aviso. El espectador avisa que dejó de actualizarse. Se reintenta automáticamente con espera creciente, hasta 5 s entre intentos |
| Regresa la conexión | Se recupera únicamente el estado vigente. Si el operador cambió varias veces de escena, se carga la última; no se reproducen órdenes pendientes antiguas |
| Error al cargar una imagen | El operador recibe Error del visor y conserva la última escena confirmada. Revisa conexión/archivo y usa Reintentar en el visor o envía otra escena |
| Redis detenido | No se confirma una operación que depende de sincronización. Inícialo, espera reconexión; las sesiones y la última orden siguen en SQLite. Los latidos y la mirada se reconstruyen |
| Redis reiniciado antes de vincular | El código visible se perdió de memoria. Usa Renovar código sin usar; el anterior deja de valer |
| Segunda pestaña del visor | Cierra la pestaña que ocupa la sesión y recarga la correcta. Una conexión perdida tarda aproximadamente 8 s en caducar; espera antes de recargar si aún aparece ocupada |
| Pantalla de espectador cerrada | Usa Abrir pantalla del público de nuevo. Revoca la credencial anterior; después de su desconexión la nueva puede ocupar la sesión |
| Cambió el contenido a borrador o falta un archivo | Se deja de enviar el recorrido y se bloquean nuevas cargas. El operador debe elegir otro recorrido completo o finalizar |
| Sesión finalizada/caducada | La reconexión no reactiva credenciales. Crea una nueva sesión y vuelve a vincular |
| Pérdida del contexto gráfico WebGL | Se informa al operador. Reintenta/recarga el visor; puede requerir pulsar Entrar en VR de nuevo por decisión del participante |

Conservar una imagen en memoria durante una caída **no es funcionamiento sin internet**. Esta fase no añade caché offline ni garantiza reconexión cuando el servidor, la red o los archivos siguen inaccesibles. No se ha medido rendimiento con Quest físico o con la red del evento.

## Protocolo e integridad

- **Autoridad:** una fila `StandSession` en SQLite conserva la orden vigente y la última escena confirmada. Redis mantiene exclusiones temporales, presencia, código sin usar y la última orientación. Bloqueos de Redis y transacciones serializan cambios de una sesión.
- **Órdenes:** POST con CSRF, UUID, secuencia esperada, acción y destino. Cada cambio aceptado incrementa `seq`. Repetir el UUID y contenido de la última orden devuelve el mismo resultado; modificar su contenido se rechaza. Una orden antigua con secuencia desactualizada devuelve conflicto y exige revisar el estado.
- **Confirmación:** la respuesta HTTP solo significa aceptada. El visor envía `applied` con secuencia y escena después de cargar/decodificar/asignar la panorámica. Solo entonces cambian `applied_seq` y la escena confirmada. Un error conserva la confirmación anterior. El espectador sigue la escena confirmada, incluso mientras se prepara otro recorrido.
- **Carreras operador/participante:** se acepta primero el evento válido que adquiere el bloqueo. El visitante solo puede navegar desde una secuencia ya aplicada. Una orden del operador que llega después con secuencia obsoleta se rechaza con 409, sin sobrescribir silenciosamente la navegación. Cuando hay una orden pendiente, una navegación o confirmación vieja del visitante se ignora. La interfaz recupera el nuevo estado y permite reintentar deliberadamente.
- **Recuperación:** los mensajes internos notifican que cambió el estado; nunca forman una cola de órdenes. Cada conexión/latido consulta la fila vigente. Las cargas anteriores se cancelan con identificadores de generación. No se recrean sesiones al recargar la página.
- **Presencia:** ping del cliente cada 2 s; el servidor vence conexiones sin actividad en unos 8 s. La cesión de una única conexión por rol usa TTL y un identificador privado por conexión: una conexión vieja no puede borrar el bloqueo de su reemplazo. Cerrar una ventana avisa a las otras. «Conectado» indica latidos, no prueba que el participante esté mirando; el espectador también comprueba recepción reciente de orientación.
- **Roles:** operador con sesión Django y permisos actualizados; visor y espectador con tokens aleatorios distintos en cookies HttpOnly, SameSite=Strict, limitadas a su ruta de sesión, Secure cuando HTTPS está configurado. Solo HMAC en la base. No se pasan secretos por URL, JSON público o JavaScript. Finalizar/expirar invalida ambos. El visor acepta únicamente ping, navegación, confirmación, error enumerado y orientación. El espectador solo puede enviar ping.
- **Límites:** mensajes hasta 2048 caracteres, máximo 25 por segundo, tipo y campos permitidos, coordenadas finitas, cuaternión normalizado y secuencia/escena coherentes. La vinculación de ocho caracteres aleatorios excluye caracteres ambiguos y se consume atómicamente.
- **Contenido:** la capa existente de publicación valida recorridos completos. No se sirven borradores por stand. Las imágenes del stand también comprueban la credencial y pertenencia en cada solicitud. El texto editorial se presenta como texto, no HTML.
- **Orientación:** como el visor existente, cielo con rotación Y de −90°, yaw positivo hacia la izquierda y pitch positivo hacia arriba. Se transmite el cuaternión mundial de la cámara `[x,y,z,w]`. En pantalla normal se usa `camera.getWorldQuaternion`; en WebXR se extrae la rotación de `renderer.xr.getCamera().matrixWorld` durante `tock`, después del render. El motor ya compuso la pose de cabeza con el transformado del rig; no se suma el rig de nuevo ni se leen los Euler de `look-controls`. El espectador aplica el cuaternión a una cámara sin controles de ratón y suaviza con `slerp`, evitando la discontinuidad ±180°. [WebXRManager de Three.js](https://threejs.org/docs/pages/WebXRManager.html).
- **Frecuencia/privacidad:** aproximadamente 10 orientaciones/s, máximo aceptado 12,5/s, solo mientras la escena está cargada y conectada. Redis conserva exclusivamente la última pose durante hasta 8 s; no hay histórico ni movimientos en SQLite. Compose desactiva persistencia RDB/AOF. Si usas otro Redis, mantén desactivada la persistencia y evita su registro de comandos para estas claves. No hay grabación, analítica ni envío de imágenes de pantalla.

## Pruebas y límites

```sh
docker compose -f compose.stand.yml up -d
.venv/bin/python manage.py test
npm run test:stand
npm run test:e2e
npm run test:editor
npm run test:panel
```

Las pruebas usan base, medios, cuentas y claves Redis temporales. El servidor de stand escucha solo en `127.0.0.1:8016`; limpia exclusivamente su prefijo Redis, nunca ejecuta `FLUSHALL`. Los manifiestos, cookies de prueba, capturas y trazas se excluyen de Git. Chrome usa renderizado gráfico por software.

La suite del stand comprueba transporte WebSocket real con Redis y contextos independientes, confirmación y navegación, cambio de recorrido, códigos caducados/reutilizados, desconexión/reconexión, error de imagen y pérdida gráfica simulada sin falsa confirmación, roles, finalización, vista móvil y captura de las tres pantallas. Las pruebas de servidor complementan permisos, CSRF, origen hostil, eventos malformados/no finitos, exclusión de un segundo visor y cierre de sesión administrativa. La prueba de cámara XR es una **simulación matemática** con matrices de cabeza/rig y giro lateral, vertical y roll.

### Prueba física pendiente antes del evento

1. Con Quest 2 real, abrir HTTPS/WSS válido, vincular y entrar en VR mediante el botón.
2. Comparar televisión y mirada al girar horizontalmente, inclinar arriba/abajo, inclinar lateralmente la cabeza y cruzar ±180°. Verificar que el rig no duplique giros y que la TV represente el eje central de la mirada.
3. Navegar con ambos mandos. Enviar cambios desde el operador mientras el participante mira en una dirección distinta; comprobar fundido, horizonte estable y ausencia de rotación impuesta.
4. Probar Volver al inicio, cancelación y salida/entrada de WebXR. Confirmar que nunca se recalibre ni se inicie VR por una orden remota.
5. Suspender/reactivar el visor, interrumpir y restaurar Wi-Fi, reiniciar Redis y probar recuperación sin órdenes antiguas, conexiones duplicadas ni falsas confirmaciones.
6. Comprobar pantalla extendida, legibilidad, red real, fluidez, calidad de imágenes y comodidad durante una sesión prolongada. No se garantiza latencia o rendimiento hasta medirlo en el equipo del evento.
