# PUBLICACIÓN GRATIS — ACTUALIZACIÓN

El repositorio también puede desplegarse en **Render Free + Neon Free**. Lee `PUBLICAR_EN_INTERNET.md`. En Ubuntu continúa funcionando con SQLite. Para la nube se instala `requirements-cloud.txt` dentro de Docker y se usa `DATABASE_URL` de Neon configurada SOLO en Render. No hay disco de pago.

# Cripta Pixel Online — Edición V2: Enemigos animados y especiales renovados

**Juego 2D de mazmorras y arena para navegador (cliente HTML5 + servidor Python).**

## Funciones principales

- Solitario: 1 persona, 3 pisos, enemigos y jefe final.
- Cooperativo: 2–4 personas mediante código de sala, desde equipos separados.
- PvP: 2–4 jugadores, primera persona en lograr 5 eliminaciones o resultado al terminar los 180 segundos.
- Registro e inicio de sesión con PBKDF2, usuarios y rankings por fecha y modo en SQLite.
- Caballero basado en el sprite aprobado, con 4 bufandas (rojo, azul, verde, naranja), espada y escudo compacto.
- Spritesheets de **7 estados × 4 direcciones × 4 fotogramas** por caballero: reposo, caminata, ataque, Q, defensa E, daño y derrota.
- **Duendes y esqueletos**: spritesheets nuevos de **4 direcciones × 4 estados (quieto, caminar, atacar, daño) × 4 fotogramas**, con articulación de pies y brazos y ataques distintos, no un simple estiramiento de la imagen. Los demás enemigos conservan sus animaciones.
- **Los cuatro especiales Q tienen efectos pixel art propios y animados**: tajo rojo de Brutal, onda azul de Distancia, nube venenosa verde y runa eléctrica violeta de Parálisis. Los efectos aparecen al recibir del servidor el evento de uso. Se mantienen los valores y reglas de daño del juego.
- El servidor orienta enemigos según el eje dominante de persecución, mejorando la coherencia entre movimiento y animación.
- Decoraciones por bioma (bosque, hielo, fuego y arena), minimapa, zoom de cámara, partículas de impacto, indicadores de recarga y efectos de sonido sintetizados y silenciables.
- Las colisiones, daño, enemigos, bloqueos y puntuaciones son calculados en el **servidor**. El cliente dibuja el mundo y envía controles.

## Comandos básicos

```bash
python3 -c "import sqlite3; print('SQLite OK')"
python3 server_web.py --host 127.0.0.1 --web-port 8080
```

Abre **http://127.0.0.1:8080** en el mismo equipo. Para verificar la lógica:

```bash
python3 -m unittest discover -s tests -v
```

En Ubuntu y Windows se puede usar el navegador sin instalación de cliente. Para usar Pygame de escritorio opcional, instala `pygame-ce` (requisitos en `requirements.txt`) y ejecuta `client.py` apuntando al servidor TCP correspondiente.

Consulta **`EMPIEZA_AQUI.md`** para pasos claros y **`PUBLICAR_EN_INTERNET.md`** para alojamiento fuera del portátil.

## Mecánicas de combate

| Entrada | Efecto | Reglas |
| --- | --- | --- |
| Espacio | Golpe normal de espada | 32 PVE / 34 PvP, recarga 0,44 s |
| Q – Brutal | Daño normal × 1,6 | Consume 5 HP incluso si falla |
| Q – Distancia | Alcance × 2 | Daño normal × 0,75 |
| Q – Veneno | Golpe normal + veneno | 25 % de HP restante/s durante 3 s, no acumulable |
| Q – Parálisis | Golpe normal + inmovilización | 3 s, afecta movimiento |
| E | Escudo defensivo | Dura 1 s, reduce de 0,5 % a 90 % de cada golpe directo, recarga 3 s |

Los cuatro ataques Q tienen recarga de 6 segundos. El especial se elige antes de empezar cada partida y se bloquea durante ella.

## Arte / animaciones

- **`assets/knight_<color>_sheet.png`:** atlas 192×1344 píxeles, 4 columnas × 28 filas, celdas de 48×48.
- **`assets/goblin_sheet.png` y `assets/skeleton_sheet.png`:** nuevos atlas **160×640**, 4 columnas × 16 filas, celdas de 40×40; cuatro estados × cuatro orientaciones.
- **Otros `assets/<enemigo>_sheet.png`:** atlas 160×120, 4 columnas × 3 filas, celdas de 40×40.
- **`assets/fx_<especial>_sheet.png`:** 4 atlas de efectos, cada uno **768×96** (8 fotogramas de 96×96).
- **`assets/terrain_*.png`:** 4 decoraciones de obstáculos por entorno, 64×72.
- `generar_animaciones.py`, `generar_enemigos_y_efectos.py` y `generar_escenarios.py` permiten regenerar el arte si tienes Pillow instalado. Ejecuta primero `generar_animaciones.py` y después `generar_enemigos_y_efectos.py`; el generador antiguo no sobrescribe los atlas V2 de goblin ni esqueleto.
- `assets/maestros/` contiene los cuatro PNG de referencia previos a la generación para que la regeneración sea determinista.
- `VISTA_ANIMACIONES_REALES.png` y `DEMO_CAMINATA_REAL.gif` están construidos a partir de los spritesheets auténticos; no son imágenes conceptuales.

## Arquitectura y límites

`server.py` contiene el bucle autoritativo de juego TCP, salas y persistencia SQLite. `server_web.py` permite conexiones de navegador por HTTP; `web/app.js` controla entradas y dibujo Canvas. `cloud_server.py` escucha el puerto configurado por `PORT` en un proveedor cloud y mantiene una única instancia de servidor.

Las partidas activas están en memoria, así que no sobreviven a reinicios. SQLite persiste solo si el archivo de base de datos está en almacenamiento persistente. El servicio público requiere HTTPS proporcionado por el hosting. La versión web no necesita Pygame ni librerías Python externas.

## Pruebas

- Pruebas unitarias estándar: `python3 -m unittest discover -s tests -v`.
- Prueba visual opcional en Chromium + Playwright (requiere instalar esas herramientas): `python3 PRUEBA_NAVEGADOR.py`.
- Las capturas reales del recorrido están en `CAPTURA_*.png`.

En esta edición se verificaron **42 pruebas automáticas** con `unittest` y un recorrido real de Chromium (dos sesiones, Solitario, Cooperativo, PvP, Q y E). El archivo `DEMO_ENEMIGOS_Y_ESPECIALES.gif` se produce a partir de los spritesheets incluidos, no de una imagen conceptual.

**La prueba visual automatizada no sustituye la prueba manual con dos computadores físicos ni verifica un despliegue en Render.**
