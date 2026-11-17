# Demostración verificable para evaluación universitaria

## Preparación del servidor

1. Descomprimir el ZIP y entrar en la carpeta `Cripta_Pixel_ONLINE_EDICION_ANIMADA`.
2. Ejecutar `python3 -c "import sqlite3; print('SQLite OK')"`.
3. Ejecutar `python3 -m unittest discover -s tests -v` y mostrar resultado de 37 pruebas `OK`.
4. Iniciar `python3 server_web.py --host 127.0.0.1 --web-port 8080`.
5. Abrir `http://127.0.0.1:8080` en navegador.

## Demostrar los tres modos

- **Solitario:** seleccionar Q, entrar sin sala de espera, caminar con las cuatro direcciones, atacar con Espacio, usar Q y defender con E. Mostrar mapa, barras de recarga, zoom, minimapa y personajes.
- **Cooperativo:** abrir segundo navegador o perfil privado, crear segunda cuenta, crear sala con la primera, unirse por código, iniciar 2 jugadores, verificar colores de bufanda distintos y enemigos compartidos.
- **PvP:** abandonar la expedición, crear una sala nueva, dos jugadores, movimiento y ataques; mostrar ranking PvP separado.
- **Ranking:** mostrar pestañas Solitario/Cooperativo/PvP; señalar que la clasificación se agrupa por día de Colombia y se guarda en SQLite al terminar partidas.

## Evidencia visual integrada

`CAPTURA_MENU_REAL.png`, `CAPTURA_PARTIDA_ANIMADA.png`, `CAPTURA_COOPERATIVO_ANIMADO.png`, `CAPTURA_PVP_ANIMADO.png` y `DEMO_CAMINATA_REAL.gif`. Las capturas proceden de Chromium en el entorno de pruebas con puente HTTP Python, no de equipos reales en Internet.

## Arquitectura

Cliente web HTML/CSS/Canvas y JavaScript → API HTTP del servidor Python (`server_web.py`) → motor autoritativo (`server.py`) → SQLite (`users`/`results`). El servidor envía posiciones, eventos de ataque y estado de vida; los clientes reproducen las animaciones, pero **no tienen autoridad para adjudicar daño ni puntos**.

## Limitaciones que deben declararse

El juego no está publicado todavía. El alojamiento permanente con SQLite requiere servicio cloud con disco persistente, normalmente de pago. Las partidas activas no sobreviven al reinicio de servidor. El cliente gráfico opcional en Pygame no fue probado visualmente en este entorno. No se ha validado la conexión física entre Windows y Ubuntu a través de Internet.
