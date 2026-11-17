"""Prueba proceso real cloud_server + reinicio + persistencia SQLite.
No publica nada ni consume un servicio externo.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.request import Request,urlopen
from urllib.error import URLError

ROOT=Path(__file__).resolve().parents[1]

def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1',0))
        return s.getsockname()[1]

class CloudSmokeTests(unittest.TestCase):
    def test_restart_preserves_account_and_web_assets(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'data.sqlite'
            port=free_port()
            base=f'http://127.0.0.1:{port}'
            env=os.environ.copy()
            env.update(PORT=str(port),CRIPTA_DB_PATH=str(path),PYTHONUNBUFFERED='1')
            def start():
                process=subprocess.Popen([sys.executable,'cloud_server.py'],cwd=str(ROOT),env=env,
                                         stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                for _ in range(75):
                    if process.poll() is not None:raise AssertionError('Cloud server terminó antes de abrir su puerto')
                    try:
                        with urlopen(base+'/api/status',timeout=.3) as response:
                            if json.load(response).get('ok'):return process
                    except (URLError,ConnectionError,TimeoutError,OSError):pass
                    time.sleep(.08)
                process.terminate();process.wait(timeout=5)
                raise AssertionError('Cloud server no respondió /api/status')
            def stop(process):
                process.terminate()
                try:process.wait(timeout=6)
                except subprocess.TimeoutExpired:
                    process.kill();process.wait(timeout=3)
            def post(path,payload):
                req=Request(base+path,data=json.dumps(payload).encode('utf8'),
                            method='POST',headers={'Content-Type':'application/json'})
                with urlopen(req,timeout=3) as response:return json.load(response)
            def events(token):
                with urlopen(base+'/api/events?session='+token,timeout=3) as response:return json.load(response)['events']
            process=start()
            try:
                with urlopen(base+'/assets/knight_rojo_sheet.png',timeout=3) as response:
                    self.assertEqual(response.read(8),b'\x89PNG\r\n\x1a\n')
                tok=post('/api/connect',{})['session']
                post('/api/action',{'session':tok,'action':{'type':'register','username':'CloudTester42','password':'password123'}})
                self.assertTrue(any(x.get('type')=='register_result' and x.get('ok') for x in events(tok)))
                self.assertTrue(path.exists())
            finally:stop(process)
            process=start()
            try:
                tok=post('/api/connect',{})['session']
                post('/api/action',{'session':tok,'action':{'type':'login','username':'CloudTester42','password':'password123'}})
                self.assertTrue(any(x.get('type')=='login_result' and x.get('ok') for x in events(tok)))
            finally:stop(process)

if __name__=='__main__':unittest.main()
