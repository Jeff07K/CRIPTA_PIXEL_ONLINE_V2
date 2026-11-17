"""Entrada del videojuego para alojamiento web (Render, Docker y proveedores similares).

Mantiene una sola instancia del GameServer por servicio y guarda usuarios y ranking
fuera del directorio efimero cuando se configura CRIPTA_DB_PATH o DATA_DIR.
El puerto TCP nativo se escucha solo en loopback; el acceso publico es HTTP(S).
"""
from __future__ import annotations

import os
from pathlib import Path
import signal
import threading
import time

from server import GameServer
from server_web import BrowserGateway


def settings_from_env() -> tuple[str, int, Path]:
    host = '0.0.0.0'
    port = int(os.environ.get('PORT', '10000'))
    if port < 0 or port > 65535:
        raise ValueError('PORT debe estar entre 0 y 65535')
    data_dir = Path(os.environ.get('DATA_DIR', './datos')).expanduser().resolve()
    db_path = Path(os.environ.get('CRIPTA_DB_PATH', str(data_dir / 'cripta.db'))).expanduser().resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return host, port, db_path


def run():
    host, port, db_path = settings_from_env()
    print(f'[CLOUD] Base de datos: {db_path}', flush=True)
    game = GameServer('127.0.0.1', 0, str(db_path))
    gateway = BrowserGateway(game, host, port)
    stop_event = threading.Event()

    def shutdown(_signal, _frame):
        stop_event.set()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    try:
        game.start()
        gateway.start()
        print(f'[CLOUD] Listo: HTTP en {host}:{gateway.port}. Usa HTTPS de tu proveedor.', flush=True)
        while not stop_event.wait(0.3):
            pass
    finally:
        print('[CLOUD] Cerrando servidor...', flush=True)
        gateway.stop()
        game.stop()


if __name__ == '__main__':
    run()
