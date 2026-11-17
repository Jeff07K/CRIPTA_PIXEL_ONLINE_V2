# Registro de cambios — Cripta Pixel Online V2

## Esta es una versión del juego, no una imagen de presentación

### Animación de duendes y esqueletos
- Se reemplazaron `assets/goblin_sheet.png` y `assets/skeleton_sheet.png` por atlas pixel art de 160×640 con cuatro fotogramas por estado y orientación (quieto, caminar, atacar y recibir daño; abajo, izquierda, derecha, arriba).
- El servidor Python envía ahora orientación vertical u horizontal basada en la dirección real hacia el jugador. La colisión, velocidad y daño siguen siendo autoritativos del servidor.
- Los clientes web (`web/app.js`) y Pygame opcional (`client.py`) leen los nuevos atlas y activan el estado de ataque real en lugar de simularlo como daño.

### Q: efectos visuales exclusivos por habilidad
- Se añadieron cuatro archivos `assets/fx_<tipo>_sheet.png`, ocho fotogramas cada uno (768×96), diseñados en el estilo pixel art del juego.
- Brutal: tajo rojo y dorado; Distancia: onda azul; Veneno: gas y burbujas verdes; Parálisis: anillo violeta y electricidad.
- Los clientes representan el efecto a partir de `special_seq` recibido del servidor; los sondeos repetidos **no** crean nuevas ejecuciones. La mecánica, los tiempos de recarga, los efectos de estado y el daño **no cambian**.
- El veneno y la parálisis sobre los enemigos tienen ahora indicadores animados específicos.

### Compatibilidad
- Se conservan Solitario, Cooperativo (2–4), PvP, cuentas, salas y rankings independientes.
- `generar_animaciones.py` ya no sobrescribe los atlas V2 al regenerar el resto de criaturas.
- Regeneración opcional: `python3 -m pip install Pillow` y `python3 generar_enemigos_y_efectos.py`. No se requiere Pillow ni Pygame para ejecutar **el juego web**.

### Verificación y limitaciones
- La batería de 42 pruebas pasa con Pillow instalado; si no está instalado, las verificaciones de píxeles que lo requieran se omiten.
- Chromium probó dos sesiones independientes sobre servidor Python local con puente HTTP, incluyendo Q, E, Solitario, Cooperativo y PvP.
- Aún hay que probar manualmente la edición V2 entre Ubuntu/Windows físicos y desplegarla en una cuenta cloud. El ZIP **no** incluye una URL pública ya funcionando.
