# Publicar Cripta Pixel Online sin depender del portátil

Este proyecto necesita **alojamiento de backend Python**: un hosting de páginas HTML estáticas no ejecutará la lógica ni conservará las salas. Los visitantes solo requieren navegador, así que Windows no necesita permisos de administrador.

## A. Antes de subirlo

1. Verifica Solitario, Cooperativo y PvP localmente con `python3 server_web.py --host 127.0.0.1 --web-port 8080`.
2. Ejecuta `python3 -m unittest discover -s tests -v` y comprueba que aparece `OK`.
3. Confirma que el ZIP incluye `cloud_server.py`, `render.yaml`, `server.py`, `server_web.py`, `protocol.py`, `web/` y `assets/`.
4. **No subas ninguna base de datos real ni contraseñas**. El proyecto se entrega sin `cripta.db`. No reutilices contraseñas personales en una demo estudiantil pública.

## B. Crear repositorio con los archivos de esta versión

1. Ve a https://github.com y accede a tu cuenta.
2. Crea un repositorio nuevo con un nombre como `cripta-pixel-online`, inicialmente vacío.
3. Selecciona **Add file → Upload files** y carga el contenido completo de la carpeta `CRIPTA_PIXEL_ONLINE_V2` (no el ZIP en sí). `render.yaml` debe quedar en la **raíz** del repositorio.
4. Confirma el commit. Puedes usar Git desde Ubuntu si la interfaz web no admite una carpeta completa; también puedes subir archivos en lotes manteniendo estructura.
5. Comprueba que `assets/goblin_sheet.png`, `assets/skeleton_sheet.png`, `assets/fx_veneno_sheet.png` y `web/app.js` estén visibles en GitHub.

## C. Configurar Render

1. Entra en https://dashboard.render.com y conecta tu cuenta GitHub cuando se solicite.
2. Selecciona **New → Blueprint** y el repositorio recién creado.
3. Render leerá `render.yaml`. Examina el coste antes de aprobarlo: `plan: 0.5c-512mb` es computación **de pago**, con disco persistente `/var/data` de 1 GB y una sola instancia.
4. La variable `CRIPTA_DB_PATH=/var/data/cripta.db` obliga a SQLite a guardar cuentas y puntuaciones en el disco persistente.
5. Aprueba el despliegue solo cuando estés de acuerdo con el coste del servicio y del almacenamiento. No se crean recursos de pago automáticamente por descargar este ZIP.
6. En **Logs**, confirma que aparezcan mensajes de servidor Python y de HTTP listo. Espera al estado **Live**.
7. Copia la URL HTTPS real que Render asigne, similar a `https://tu-juego.onrender.com` (ejemplo ilustrativo; no existe hasta desplegarlo).

## D. Comprobar conexión multijugador por Internet

1. En Ubuntu abre la URL HTTPS pública y después añade `/api/status`. Debe devolver JSON con `"ok":true`.
2. En Windows (aunque sea otra red Wi-Fi) abre **exactamente la misma URL** en Chrome/Edge/Firefox. No requiere instalación ni administrador.
3. Cada jugador crea una cuenta distinta. En Ubuntu crea una sala **Cooperativo**, copia el código y entra desde Windows. El anfitrión inicia cuando hayan al menos dos personas.
4. Abandona, crea sala **PvP** y repite. Comprueba en cada equipo movimiento, defensa E, Q, HP y ranking.
5. Apaga tu portátil de Ubuntu y abre la URL desde Windows: en un alojamiento externo correctamente activo debería seguir disponible.

## E. Advertencias importantes

- **No está alojado aún**. Publicarlo requiere tu cuenta y aceptar los términos del servicio.
- Render Free duerme los servicios inactivos y no permite discos persistentes. Para las cuentas SQLite se eligió una instancia con disco de pago; revisa los precios actuales en https://render.com/pricing .
- Este diseño usa una sola instancia: las salas y la lógica de tiempo real viven en memoria. Si Render reinicia o despliega una versión nueva, las partidas en curso se terminan aunque SQLite conserve usuarios y resultados completados.
- No expongas `server_web.py` directamente por HTTP en Internet: utiliza el **HTTPS** del hosting.
- Los servicios administrados pueden tener límites, latencia o interrupciones; no hay garantía de disponibilidad del 100 %.

Documentación oficial: https://render.com/docs/blueprint-spec , https://render.com/docs/disks , https://render.com/docs/free .
