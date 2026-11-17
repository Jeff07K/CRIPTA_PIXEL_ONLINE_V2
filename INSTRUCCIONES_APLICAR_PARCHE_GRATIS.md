# Actualiza tu repositorio existente — parche gratuito de Neon + Render

Este archivo forma parte del parche. **No es un juego nuevo**: conserva la V2 existente y actualiza únicamente alojamiento, persistencia y pruebas.

## Ubuntu: pasos seguros

1. Descarga el parche `CRIPTA_PIXEL_PARCHE_RENDER_NEON_GRATIS.zip`.
2. En Terminal, clona tu repositorio a una carpeta nueva (no sobreescribe tu proyecto local):

```bash
cd ~/Documentos
git clone https://github.com/Jeff07K/CRIPTA_PIXEL_ONLINE_V2.git CRIPTA_PIXEL_NUBE
cd CRIPTA_PIXEL_NUBE
```

3. Copia el ZIP del parche a la carpeta `CRIPTA_PIXEL_NUBE` desde tu gestor de archivos.
4. Ya dentro de `CRIPTA_PIXEL_NUBE`, ejecuta:

```bash
unzip -o CRIPTA_PIXEL_PARCHE_RENDER_NEON_GRATIS.zip
python3 -m unittest discover -s tests -v
```

5. Si termina en OK:

```bash
git status
git add server.py cloud_server.py db_postgres.py Dockerfile render.yaml requirements-cloud.txt tests/test_postgres_backend.py PUBLICAR_EN_INTERNET.md README.md EMPIEZA_AQUI.md REPORTE_PRUEBAS.md MANIFIESTO_SHA256.json INSTRUCCIONES_APLICAR_PARCHE_GRATIS.md
git commit -m "Activar Neon Postgres y Render Free sin discos de pago"
git push origin main
```

Si Git solicita autenticación de GitHub, utiliza tu método configurado (por ejemplo, GitHub CLI o token personal); **nunca compartas contraseñas ni tokens por chat**. Para GitHub con HTTPS, una contraseña de cuenta normal no sirve como credencial de push.

6. Revisa https://github.com/Jeff07K/CRIPTA_PIXEL_ONLINE_V2 y confirma que `render.yaml` ahora contiene `plan: free` y que existe `db_postgres.py`.
7. Regresa a Render, selecciona **Compute → Free**, agrega la variable de entorno privada `DATABASE_URL` desde Neon y despliega como **Web Service**, no Static Site.

## Seguridad

- NO subas el archivo `.env` ni ninguna cadena de conexión que incluya una contraseña.
- Copia `DATABASE_URL` desde Neon → Connect y pégala solo en Render → Environment Variables.
- No alteres los assets ni la carpeta `web/`; el parche no los necesita.

## Qué se probó

46 pruebas automatizadas locales pasaron. Se simularon consultas PostgreSQL con adaptador SQL de prueba. Falta comprobar el acceso remoto a tu Neon real tras el despliegue.
