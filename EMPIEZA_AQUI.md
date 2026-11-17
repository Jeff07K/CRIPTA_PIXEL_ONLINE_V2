# CRIPTA PIXEL ONLINE — EDICIÓN V2 · ENEMIGOS Y ESPECIALES

**Este ZIP es el juego completo.** No combina versiones anteriores ni archivos adicionales.

## 1. En Ubuntu: empieza por Solitario

1. Extrae todo el ZIP en una carpeta nueva. No mezcles archivos con las versiones previas.
2. En el administrador de archivos de Ubuntu, entra a `CRIPTA_PIXEL_ONLINE_V2` y elige **Abrir en terminal**.
3. Comprueba que Python y SQLite están disponibles:

   ```bash
   python3 --version
   python3 -c "import sqlite3; print('SQLite OK')"
   ```

   **No utilices `python3.14` si vuelve a aparecer `No module named _sqlite3`**. En las pruebas anteriores, `python3` sí iniciaba el servidor.
4. La versión V2 ya trae los sprites preparados (no necesitas instalar Pillow). Los **esqueletos y duendes caminan en cuatro direcciones**, tienen poses de ataque y daño, y **Q muestra un efecto distinto según la habilidad**.
5. Ejecuta el servidor web:

   ```bash
   python3 server_web.py --host 127.0.0.1 --web-port 8080
   ```

6. Deja la terminal abierta. En Firefox, Chrome o Brave visita:

   `http://127.0.0.1:8080`

7. Registra una cuenta de prueba, entra a **El viaje del héroe** y prueba:

   | Tecla | Acción |
   | --- | --- |
   | W A S D / flechas | Desplazarse (4 direcciones animadas) |
   | Espacio | Espada / ataque normal |
   | Q | Ataque especial elegido antes de empezar |
   | E | Escudo / defensa con mitigación aleatoria |
   | Botón ZOOM | 100 %, 112 %, 130 % |

## 2. Probar Cooperativo y PvP

1. En un navegador crea una cuenta A e inicia Cooperativo.
2. Abre un perfil privado o un navegador distinto para cuenta B (dos cuentas independientes).
3. En el segundo perfil, introduce el código de 6 caracteres de la sala, con **la misma dirección del servidor**.
4. El anfitrión inicia la expedición con 2–4 jugadores. Prueba color rojo, azul, verde y naranja.
5. Para PvP, crea una sala nueva y repite con 2–4 personas. Los rankings son distintos por modo.

**Importante:** cuando uno de los dos integrantes abandona una partida cooperativa de solo dos, el servidor termina la expedición y el otro jugador ve la pantalla de resultados. No es un fallo del navegador.

## 3. Ejecutar pruebas automáticas

```bash
python3 -m unittest discover -s tests -v
```

**Prueba recomendada para V2:** en Solitario llega hasta un enemigo goblin o skeleton y observa sus pasos y dirección de mirada; selecciona uno de los cuatro especiales para observar el efecto Q. Si buscas los cuatro efectos, haz partidas de prueba con especiales diferentes (solo se equipa uno antes de cada partida).

No necesitas instalar Pygame para la versión web. `pygame-ce` solo sirve para el cliente gráfico de escritorio opcional (`client.py`), cuya ejecución visual no fue verificada en este entorno. `Pillow` se utiliza únicamente si quieres regenerar manualmente los spritesheets.

## 4. Para jugar desde Windows y Ubuntu en redes diferentes, SIN depender de tu portátil

Debes publicar el **servidor Python en un alojamiento externo**, no abrir solamente una web estática. Abre `PUBLICAR_EN_INTERNET.md` y sigue los pasos de GitHub + Render. La configuración del ZIP incluye un servicio de pago y un disco persistente para las cuentas y los rankings; **no se ha contratado ni desplegado por ti**.

Después del despliegue, ambos jugadores usan la misma dirección HTTPS pública en sus navegadores. Windows **no necesita permisos de administrador** ni Python.

## 5. Si algo no funciona

- `No module named _sqlite3`: utiliza otra instalación de Python con SQLite; comprueba `python3 -c "import sqlite3"`.
- `Address already in use`: otro programa utiliza el puerto 8080; detén el proceso anterior o ejecuta con `--web-port 8090` y abre `http://127.0.0.1:8090`.
- Los sprites viejos todavía aparecen: pulsa **Ctrl+Mayús+R**.
- Sala no existe: abre el mismo servidor con ambas cuentas, crea una sala nueva y copia su código actual.
- El juego no abre desde otra red: la dirección `127.0.0.1` solo funciona dentro del equipo anfitrión. Necesitas la URL pública del hosting.
- Pantalla vacía: comprueba que el servidor está abierto y visita `/api/status` en esa misma dirección; envía captura del error si persiste.

## 6. Qué no se ha garantizado

Las pruebas incluidas validan la lógica de combate, spritesheets, varias sesiones HTTP y las pantallas web bajo Chromium con puente de peticiones. **No** demuestran un despliegue público ya activo, que Pygame funcione en todas las tarjetas gráficas, ni pruebas físicas entre Windows/Ubuntu por Internet. Una caída del servidor cancela las partidas activas; las cuentas y rankings se conservan si la base SQLite se encuentra en un disco persistente.
