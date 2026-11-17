#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
python3 server_web.py --host 127.0.0.1 --web-port 8080
