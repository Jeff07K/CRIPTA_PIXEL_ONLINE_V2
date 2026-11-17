# CRIPTA PIXEL ONLINE V2 — Publicación GRATUITA (Render + Neon)

**Costo de la configuración propuesta: $0** mientras se permanezca dentro de los límites gratuitos de cada servicio. No se crea un disco de Render. La base permanente es **PostgreSQL de Neon**; en Ubuntu se conserva SQLite.

## 0. Qué cambia y qué NO cambia

- Solo se modificaron la selección de base de datos, Dockerfile y `render.yaml`. Gráficos, modos, especiales y puntuación no se reescribieron.
- `DATABASE_URL` **solo se configura en los secretos de Render**. Nunca la subas a GitHub, no la envíes por chat ni muestres la contraseña en capturas.
- Los jugadores entran por navegador sin instalar nada en Windows.
- Los resultados **completados** y las cuentas se guardan en Neon; las **partidas activas y sesiones** siguen en memoria y se pierden al reiniciarse el servicio.
- Render Free se suspende tras inactividad, puede tardar en responder al reactivarse y tiene límites de horas, memoria y ancho de banda. No es una garantía de 24/7.

## 1. Actualiza el repositorio

Si recibiste el parche ZIP, descomprímelo **en la raíz de una copia local del repositorio**; reemplaza los archivos que coincidan y conserva `web/` y `assets/` existentes. Los cambios necesarios son `server.py`, `cloud_server.py`, `db_postgres.py`, `Dockerfile`, `requirements-cloud.txt`, `render.yaml` y esta guía.

Para comprobarlo en Ubuntu:

```bash
python3 -m unittest discover -s tests -v
```

Luego realiza `git add`, `git commit` y `git push origin main` (ver guía de la respuesta en ChatGPT si necesitas paso a paso). **No subas `cripta.db`, `.env`, ni la cadena privada de Neon.**

## 2. Neon, donde ya creaste el plan Free

1. En https://console.neon.tech abre tu proyecto `CRIPTA_PIXEL_ONLINE_V2`.
2. Haz clic en el botón verde **Connect**.
3. Elige `production`, el rol y base de datos disponibles, y copia la **connection string** PostgreSQL que empieza por `postgresql://`.
4. Debe incluir la contraseña y `sslmode=require` (o seguridad superior). **No la pegues en ningún archivo del repositorio.**
5. Mantén la cadena en privado para introducirla exclusivamente en Render.

Neon creará las tablas `users` y `results` automáticamente en el primer arranque del juego que conecte correctamente.

## 3. Render (crear Web Service, no Static Site)

1. En https://dashboard.render.com entra en **New → Web Service** y selecciona `Jeff07K/CRIPTA_PIXEL_ONLINE_V2`.
2. `Name`: puede ser `cripta-pixel-online-v2`; `Branch`: `main`.
3. `Language`: **Docker**. `Root Directory`: vacío.
4. **Compute: Free ($0/month)**. Si ves `Starter $7/month` o cualquier monto, no hagas el despliegue.
5. `Environment Variables` → añade `DATABASE_URL` y pega la cadena privada copiada de Neon.
6. No configures un disco, `CRIPTA_DB_PATH`, ni los `DATABASE_URL` en GitHub. `PORT` no hace falta: Render lo asigna y `cloud_server.py` lo lee.
7. `Health Check Path` (si aparece): `/api/status`.
8. Pulsa **Deploy Web Service** SOLO si el plan mostrado es **Free $0** y la variable `DATABASE_URL` está configurada.
9. Revisa `Logs`; deberían aparecer `Persistencia: PostgreSQL de Neon` y `[CLOUD] Listo`.

> Como alternativa, `New → Blueprint` lee `render.yaml` actualizado, que declara `plan: free`, Docker, y `DATABASE_URL` con `sync: false` para que se introduzca solo en Render. No uses el `render.yaml` antiguo que solicitaba disco pagado.

## 4. Verifica que realmente funciona por Internet

1. Render mostrará una URL `https://NOMBRE.onrender.com` (Render asigna el nombre real).
2. Abre `https://NOMBRE.onrender.com/api/status` y espera `"ok":true`.
3. Abre el enlace sin `/api/status` en Ubuntu y en Windows. Dos cuentas diferentes pueden compartir una sala Cooperativo, código de sala, PvP y ranking.
4. Crea una cuenta de prueba, termina una partida y comprueba una puntuación. Despliega de nuevo o deja dormir el servidor; al iniciar sesión otra vez la cuenta y los resultados completos deben permanecer en Neon.
5. En Neon → **Tables**, tras registrar una cuenta, deberían existir `users` y `results`.

## 5. Diagnóstico

- `Falta DATABASE_URL en Render`: añade la variable secreta en el servicio (Environment), guarda y redeploy.
- `No module named psycopg`: comprueba que el nuevo Dockerfile copie e instale `requirements-cloud.txt`, y que el Build de Render utilice el último commit.
- `could not translate host name`, `password authentication failed` o `timeout`: revisa en Render la variable, sin publicar su valor ni su contraseña. Neon requiere SSL.
- `502/503` durante un momento: revisa los logs y considera que Render Free necesita despertar después de inactividad.
- `No existe esa sala`: ambos deben usar **la misma URL HTTPS** y crear una sala nueva; tras un reinicio las salas en memoria desaparecen.
- `Render cobra $7`: **detén el proceso**; elige **Free**, no Starter.

## 6. Limitaciones verificadas

- Las **46 pruebas locales** abarcan regresiones de juego y simulación SQL de PostgreSQL. **La conexión remota real a Neon aún no se ha probado** porque no se usaron ni solicitaron credenciales.
- Render Free y Neon Free tienen límites variables según sus términos. Render suspende los servicios web Free tras períodos de inactividad; los primeros visitantes pueden esperar al reactivarse.
- Las salas, posiciones y sesiones no se persisten en Postgres. No uses la app para cuentas o datos sensibles; las garantías de seguridad para un juego público abierto aún requieren revisión adicional.

Fuentes oficiales: https://render.com/docs/free  |  https://render.com/docs/blueprint-spec  |  https://neon.com/docs/connect/connect-from-any-app
