> IMPORTANTE: este paquete contiene los **sprites del caballero original del usuario**, con bufandas y escudo. Consulta primero `EMPIEZA_AQUI.md`. Los montajes visuales de versiones anteriores fueron retirados para evitar confusión.

# GUÍA COMPLETA: CRIPTA PIXEL ONLINE — EDICIÓN CABALLEROS

**Lee este documento en orden.** Esta guía está pensada para una persona que utiliza **Ubuntu 24.04** y quiere que sus compañeros entren desde **Windows o Linux, sin permisos de administrador** y, finalmente, con el portátil del creador apagado.

## 0. Lo que ya recibes y lo que aún no se ha hecho

**Entregado en este ZIP:** juego y servidor Python, interfaz web, personajes de cuatro colores, los tres modos y rankings, Q y E, logo del slime, 28 pruebas automáticas y archivos de despliegue para Render.

**No incluido:** cuenta de GitHub, cuenta de Render, pago del hosting, dirección HTTPS publicada, validación entre ordenadores físicos reales, ni garantía de servicio 24/7. El servidor estará en Internet y será independiente de tu portátil **solo después de que tú lo publiques en el hosting**.

**Importante:** las salas y los jugadores conectados viven en RAM; se pierden si el proceso del servidor se reinicia. Las cuentas y los resultados sí persisten si el disco de Render está correctamente conectado. Es un proyecto educativo; no lo abras masivamente al público sin revisión de seguridad, pruebas de carga y un plan de copias de seguridad.

## 1. ¿Qué archivo descargo y cómo lo descomprimo?

1. Descarga `Cripta_Pixel_Online_Caballeros.zip`.
2. En Ubuntu, abre **Archivos → Descargas** y haz clic derecho sobre el ZIP → **Extraer aquí**.
3. Abre la carpeta extraída `Cripta_Pixel_Online_Version_4`.
4. Comprueba que en esa carpeta ves **estos archivos directamente**: `server.py`, `server_web.py`, `cloud_server.py`, `render.yaml`, las carpetas `web`, `assets` y `tests`.
5. Evita abrir un script dentro del ZIP sin descomprimirlo: necesita acceder a las otras carpetas.

## 2. Verificación inicial en Ubuntu (sin instalar dependencias del juego web)

Dentro de la carpeta del proyecto, haz clic derecho sobre una zona vacía → «Abrir en una terminal».

Ejecuta, **una línea cada vez**:

```bash
python3 --version
python3 -c "import sqlite3; print('SQLite OK')"
python3 -m unittest discover -s tests -v
```

Se recomienda Python 3.12 en Ubuntu 24.04 y se requiere **Python 3.10 o superior con SQLite funcionando**. Si aparece `ModuleNotFoundError: No module named '_sqlite3'`, deja de usar esa instalación concreta de Python (en tu caso anterior, `python3.14` no funcionaba) y utiliza el `python3` del sistema que sí importe `sqlite3`.

La salida esperada de las pruebas en esta entrega termina en algo similar a:

```text
Ran 28 tests in ...s
OK
```

**Las pruebas automáticas no sustituyen comprobar el juego visualmente y desde dos redes diferentes.**

## 3. Arrancar una partida LOCAL en Ubuntu, sin publicar todavía

En la terminal de la carpeta del proyecto:

```bash
bash INICIAR_WEB_UBUNTU.sh
```

O, de forma equivalente:

```bash
python3 server_web.py --host 127.0.0.1 --web-port 8080
```

Deja abierta esa terminal; cerrar el proceso detiene el servidor local. Abre **otra ventana** del navegador en el mismo Ubuntu y escribe:

```text
http://127.0.0.1:8080/api/status
```

Debe responder con JSON que incluya `"ok":true`. Después abre:

```text
http://127.0.0.1:8080
```

Si el puerto 8080 está ocupado, puedes elegir otro:

```bash
python3 server_web.py --host 127.0.0.1 --web-port 8090
```

Y entra en `http://127.0.0.1:8090`.

**No uses `127.0.0.1` desde otro ordenador.** Esa IP significa «este mismo ordenador». Para redes diferentes, pasa a la sección de publicación cloud (sección 8).

## 4. Registrar usuario y entrar

1. En la pantalla inicial, escribe un usuario de **3 a 18 caracteres**: letras, dígitos y guion bajo (`_`). Ejemplo: `Caballero01`.
2. Escribe una contraseña de **6 a 72 caracteres**. Para pruebas, utiliza una contraseña **distinta de tus contraseñas personales**.
3. Pulsa **CREAR MI CUENTA** una sola vez; el servidor crea la cuenta y después inicia sesión automáticamente.
4. Si ya tienes cuenta, ingresa usuario y contraseña y pulsa **ENTRAR AL JUEGO**.
5. Si escribes el mismo usuario desde dos dispositivos al mismo tiempo, el servidor rechaza el segundo inicio de sesión. **Cada persona necesita su cuenta propia**.

## 5. Elegir el ataque especial antes de la partida

En el menú principal, debajo de las tres tarjetas de modo, está el panel **ELIGE UN ATAQUE ESPECIAL (Q)**. Marca uno de los cuatro controles:

| Especial | Acción al presionar Q | Consecuencia |
|---|---|---|
| GOLPE BRUTAL | 160 % del daño normal | Pierdes 5 HP incluso si no alcanzas a nadie. |
| CORTE A DISTANCIA | Doble alcance | Hace 75 % del daño normal. |
| GOLPE VENENOSO | Ataque normal y veneno | Veneno: pierde 25 % de la **vida restante** cada segundo durante 3 segundos. No se apila consigo mismo. |
| GOLPE PARALIZANTE | Ataque normal y parálisis | Impide desplazarse durante 3 segundos. El objetivo todavía puede atacar desde su posición. |

Todos los especiales tienen **6 segundos de recarga desde que se usan**. Su aplicación a los enemigos y jugadores está calculada por el servidor, no por el navegador.

**Elección de color:** todos son el mismo CABALLERO, con bufanda roja, azul, verde o naranja. En esta edición el color **se asigna automáticamente por orden de entrada** (1.º rojo, 2.º azul, 3.º verde, 4.º naranja). **El jugador no elige el color manualmente**. En Solitario el caballero tiene la bufanda roja.

En una sala Cooperativa/PvP, puedes cambiar tu especial en el selector **TU ESPECIAL ANTES DE EMPEZAR**. Cuando el anfitrión inicia la partida, el servidor lo bloquea; no puedes cambiar de habilidad en medio de la ronda.

## 6. Controles y defensa

| Tecla | Acción |
|---|---|
| W / A / S / D | Movimiento arriba, izquierda, abajo y derecha. |
| Flechas | Alternativa para moverte. |
| ESPACIO | Ataque normal a los enemigos o jugadores cercanos. |
| Q | Usa el ataque especial elegido **antes** de la ronda. |
| E | Activa defensa durante **1 segundo**; recarga de **3 segundos**. |
| ESC | Sale de la partida mediante el botón de abandonar (en cliente web). |

La defensa E no vuelve invulnerable al jugador. Durante ese segundo, **cada ataque directo recibido** reduce su daño una cantidad aleatoria uniforme entre **0,5 % y 90 %**, calculada en Python. **El veneno que ya está activo sigue haciendo daño y no se reduce con E**. Los ataques directos tienen un daño mínimo de 1 HP después de calcular la reducción. La barra lateral muestra cuándo Q o E vuelven a estar disponibles.

Hay también botones táctiles para mover, atacar, usar Q y defenderte en dispositivos con pantalla táctil.

**Daños de referencia en esta edición:** normal de mazmorras = 32 HP; normal PvP = 34 HP; se redondea el daño fraccionario al entero más próximo (0,5 hacia arriba). El golpe normal se puede repetir aproximadamente cada 0,44 segundos.

## 7. Los tres modos y sus rankings separados

### 7.1 EL VIAJE DEL HÉROE (Solitario)

1. Inicia sesión.
2. Elige un especial en el menú.
3. Pulsa **JUGAR EN SOLITARIO**.
4. No hay sala de espera: el nivel se inicia de inmediato con tu caballero rojo.
5. Derrota a los monstruos para avanzar por tres pisos (bosque, hielo, fuego). En el último hay un jefe.
6. Si mueres termina la partida; si superas el tercer piso obtienes una victoria.
7. El resultado se registra en la pestaña **SOLO** del ranking diario.

### 7.2 EXPEDICIÓN AL ABISMO (Cooperativo)

1. Una persona inicia sesión, elige un especial y pulsa **CREAR PARTIDA COOPERATIVA**.
2. Aparece un código de seis caracteres (ejemplo **A4C209**, solo ilustrativo).
3. Otro jugador abre **la misma URL del servidor**, inicia sesión con cuenta distinta, elige su especial e introduce el código en **ENTRA A SU SALA**.
4. Se requieren **2 a 4 jugadores**. Cada uno usa una bufanda distinta y puede llevar un especial distinto.
5. En la sala de espera puedes cambiar tu especial antes del inicio.
6. El anfitrión pulsa **INICIAR PARTIDA**; todos comparten enemigos, pisos y jefe.
7. El ranking **COOPERATIVO** guarda los puntos y victorias de cada jugador por separado. Todavía no existe un ranking de equipos permanentes.

### 7.3 ARENA SIN PIEDAD (PvP)

1. Una persona crea **CREAR COMBATE PVP**.
2. De 1 a 3 jugadores adicionales se unen con el código.
3. Cada cual equipa un especial. El anfitrión inicia con **mínimo 2 y máximo 4 jugadores**.
4. La victoria se decide al alcanzar cinco eliminaciones o al cumplirse tres minutos; si se acaba el tiempo, gana el que tenga más bajas. Los empates pueden quedar sin ganador.
5. El ranking **PVP** tiene puntos y victorias independientes de los otros dos modos.

### Cómo funciona el ranking diario

Cada registro queda asociado a la fecha de **America/Bogota** y a uno de los tres modos. Se agregan puntos, victorias, número de partidas y récord individual de esa fecha. El ranking cambia de día automáticamente; **los registros históricos no se eliminan**. El sistema no guarda los puntos de partidas abandonadas antes de finalizar.

## 8. PUBLICARLO EN INTERNET para NO depender del portátil

**Esta sección requiere que tú completes el alta en GitHub y Render.** No hay una URL pública incluida en el ZIP. No exige que el computador Windows tenga administrador ni que instale programas. Los jugadores finales solo usan Chrome, Firefox o Edge.

### 8.1 Crear un repositorio en GitHub (desde cualquier navegador)

1. Abre https://github.com y regístrate o inicia sesión.
2. Haz clic en el botón `+` → **New repository** (Nuevo repositorio).
3. Nombre sugerido: `cripta-pixel-online`.
4. Para una demo puede ser **Private** si el alojamiento tiene permiso para acceder, o **Public** si quieres mostrar el código; **revisa cuidadosamente qué vas a compartir**.
5. Crea el repositorio. Si vas a subir archivos mediante el navegador, puedes comenzar con el repositorio vacío.
6. Busca la opción **uploading an existing file** (subir archivo existente) o **Add file → Upload files**.
7. **Sube los archivos y carpetas que están DENTRO de `Cripta_Pixel_Online_Version_4`, no el ZIP, y no una carpeta contenedora adicional.** `render.yaml` debe quedar en la **raíz del repositorio** junto a `cloud_server.py`.
8. Comprueba en GitHub que aparezcan `render.yaml`, `cloud_server.py`, `server.py`, `server_web.py`, `protocol.py`, `web/`, `assets/` y `tests/`.
9. No subas `cripta.db`, ningún archivo `*.db-wal`, tus contraseñas, claves API ni archivos `.env`. El `.gitignore` incluido evita esos archivos si utilizas Git en lugar del navegador.
10. Pulsa **Commit changes** y confirma que todos los archivos estén visibles.

Si GitHub no permite arrastrar carpetas desde tu administrador de archivos, abre el repositorio y utiliza el mecanismo de carga múltiple o Git desde tu Ubuntu. Alternativa mediante terminal, **solo después de crear el repositorio y reemplazando TU_USUARIO por el tuyo**:

```bash
git init
git add .
git commit -m "Cripta Pixel Online: caballeros y especiales"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/cripta-pixel-online.git
git push -u origin main
```

Para `git push` necesitarás autenticarte con GitHub (no uses una contraseña de tu cuenta como autenticación de terminal); la carga desde navegador evita tener que configurar Git local. Puedes omitir completamente los comandos Git si subes los archivos desde GitHub web.

### 8.2 Configurar Render

1. Abre https://dashboard.render.com y crea tu cuenta / inicia sesión.
2. Conecta tu cuenta de GitHub y autoriza el acceso al repositorio.
3. Selecciona **New → Blueprint**.
4. Selecciona el repositorio `cripta-pixel-online`, la rama que contiene `render.yaml` (normalmente `main`) y confirma que Render detecta el Blueprint.
5. Lee atentamente la vista previa: el archivo incluido solicita **una única instancia Python del plan starter** y un **disco persistente de 1 GB** montado en `/var/data`. El archivo de BD se guarda en `/var/data/cripta.db`.
6. **Este despliegue puede tener un costo mensual por servicio y almacenamiento.** Consulta el precio actual en Render antes de aprobar. No aceptes ningún cargo si no cuentas con autorización o presupuesto.
7. Selecciona **Apply / Deploy** para iniciar el despliegue. Espera el estado **Live**; en **Logs**, comprueba el inicio del servidor.
8. Render asignará una URL `https://NOMBRE-REAL.onrender.com` (es un patrón; no es la URL de este proyecto hasta que completes el despliegue).
9. Abre `https://NOMBRE-REAL.onrender.com/api/status`. Debe incluir `"ok":true`.
10. Abre `https://NOMBRE-REAL.onrender.com`, crea usuarios de prueba y ejecuta una partida de Solitario.
11. En otro equipo y otra red, abre **exactamente la misma URL HTTPS**, crea otra cuenta y prueba la sala Cooperativa.
12. Para comprobar que ya **no depende de tu portátil**, una vez publicado con el estado Live, apaga Ubuntu y entra al mismo enlace desde Windows u otro móvil conectado a Internet.

**No necesitas iniciar `server_web.py` en tu portátil una vez tengas Render publicado**. El hospedaje debe permanecer activo para servir el juego. El plan gratuito sin disco persistente no conserva permanentemente las cuentas SQLite. Un disco persistente requiere un plan compatible, no funciona con varias instancias y los despliegues pueden interrumpir partidas activas. La app **no** recupera automáticamente partidas tras reiniciar.

Fuentes oficiales sobre disco y configuración de Render: https://render.com/docs/disks y https://render.com/docs/blueprint-spec .

### 8.3 ¿Qué deben hacer los amigos que usan Windows sin administrador?

**Solo esto:** abrir el enlace HTTPS de Render en el navegador, crear una cuenta distinta, elegir un especial, unirse a la sala o jugar Solitario. **No necesitan Python, Git, Tailscale, Cloudflare Tunnel ni instalar Pygame**.

## 9. Cómo validar dos ordenadores de verdad

**Prueba 1: Solitario** — abre una cuenta desde Windows, comprueba que puedes empezar sin otro jugador; mueve el caballero con W, ataca con Espacio, prueba Q y E; revisa la barra lateral.

**Prueba 2: Cooperativo** — abre dos navegadores en redes distintas (Ubuntu Wi-Fi A, Windows Wi-Fi B), inicia sesión con cuentas distintas; el primero crea la sala, el segundo se une con el código; comprueba bufandas distintas, ataque Q distinto y movimientos sincronizados.

**Prueba 3: PvP** — crea otra sala nueva, entra con dos cuentas y comprueba que un golpe directo hace daño al rival, que E mitiga daño sin cancelarlo y que el contador de bajas aparece.

**Prueba 4: Ranking** — termina una ronda (si la abandonas no contará), abre el ranking del modo jugado y verifica que no esté mezclado con las otras dos pestañas.

**Prueba 5: Persistencia** — termina una ronda, revisa ranking, reinicia solo el proceso de Render cuando tengas una ventana de mantenimiento, inicia sesión y comprueba que cuentas y ranking siguen en la base de datos. **Este paso interrumpe cualquier partida en curso.**

## 10. Solución de errores comunes

| Síntoma | Comprobación y corrección |
|---|---|
| `No module named '_sqlite3'` | La instalación de Python es incompleta; utiliza `python3` que sí pueda `import sqlite3`. En Ubuntu 24.04, el Python 3.12 de sistema suele funcionar. |
| `Address already in use` | El puerto ya está ocupado. Cierra el proceso anterior o usa `--web-port 8090` y ajusta la URL local. |
| `No existe esa sala` | Verifica que ambos usan **la misma URL HTTPS**, que el código es nuevo y que la sala no terminó o se reinició el servidor. |
| El navegador muestra el menú antiguo | Comprueba que GitHub tiene **el ZIP más reciente DESCOMPRIMIDO** y que Render terminó el nuevo deploy. Pulsa Ctrl+Shift+R. |
| Q no hace nada | Debes estar **en una partida**, haber elegido un especial antes del inicio y esperar sus 6 s de recarga. Mira el HUD `Q ... LISTO`/`Q ... Ns`. |
| E no parece bloquear todo | Es correcto: E solo reduce daño directo por un porcentaje aleatorio. No elimina el 100 % de daño. |
| El servidor muestra `ok:false` / 502 | Mira `Events` y `Logs` de Render. Comprueba que el servicio está en `Live`, que el disco está montado y que `PORT` corresponde al puerto del proveedor. |
| Se borran los usuarios tras reinicio | El proveedor podría tener almacenamiento efímero; confirma disco persistente en `/var/data` y `CRIPTA_DB_PATH=/var/data/cripta.db`. |
| Se pierden las partidas tras un despliegue | Las salas solo están en RAM: es una limitación actual. Los resultados ya finalizados permanecen en SQLite si el disco funciona. |
| Windows no puede instalar programas | No hace falta: **solo navegador** para jugar al juego alojado en Render. |
| El cliente Pygame no conecta con Render | Por diseño, el puerto TCP opcional del cliente de escritorio está cerrado al exterior del servicio cloud. **Usa el cliente web** para jugadores remotos. |

## 11. Seguridad y límites honestos de la entrega

- Autenticación con contraseñas derivadas usando PBKDF2 y salt por usuario. Es un proyecto académico, **no** una auditoría completa de seguridad.
- HTTPS lo proporciona Render una vez desplegado correctamente; en local `http://127.0.0.1` no usa TLS y debe quedar solo para pruebas.
- No uses contraseñas que ya empleas para banco, correo o redes sociales.
- Las partidas, controles, resultados y rankings se calculan en Python; los clientes no envían coordenadas absolutas ni puntuaciones.
- El prototipo web utiliza **HTTP polling** (muchas peticiones cortas) y no WebSocket. Cumple comunicación remota cliente-servidor, pero no garantiza la latencia de un servidor de juegos profesional.
- Las pruebas nuevas verifican servidor, protocolo y una simulación de dos navegadores usando un puente HTTP de pruebas; no equivalen a ensayos de dos ordenadores físicos ni a una publicación real.
- Falta un sistema de recuperación de partidas interrumpidas y pruebas de carga con muchos usuarios simultáneos.
- En producción pública se recomiendan límites por IP, mitigación de abuso, mejores mecanismos de sesión, copias de seguridad y observabilidad.

---

**Resultado esperado después de completar el alojamiento:** una sola URL HTTPS y un servidor Python en la nube. Tus amigos pueden jugar desde cualquier computadora con navegador, sin permisos de administrador. Tu portátil ya no necesita estar encendido.
