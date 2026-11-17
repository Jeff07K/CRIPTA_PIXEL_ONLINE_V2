"""Regression checks for cumulative V4 performance and two-second shield.

No external cloud is contacted. Browser tests are separate from these checks.
"""
from __future__ import annotations
import json
import shutil
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.request import urlopen

from server import DEFENSE_DURATION, DEFENSE_COOLDOWN, Room, GameServer
from server_web import BrowserPeer, BrowserGateway

ROOT = Path(__file__).resolve().parents[1]


class BrowserPacketOptimization(unittest.TestCase):
    @staticmethod
    def snapshot(code='a1b2c3', floor=1, x=112):
        return {'type':'game_state', 'code':code, 'mode':'solo', 'floor':floor,
                'map':['.'*28 for _ in range(18)],
                'players':[{'key':'me', 'x':x, 'y':112}], 'enemies':[]}

    def test_full_map_first_then_compact_until_floor_change(self):
        p=BrowserPeer()
        p.send(self.snapshot());first=p.drain()[0]
        self.assertIn('map',first)
        p.send(self.snapshot(x=120));compact=p.drain()[0]
        self.assertNotIn('map',compact)
        self.assertEqual(compact['players'][0]['x'],120)
        p.send(self.snapshot(floor=2))
        self.assertIn('map',p.drain()[0])
        p.send(self.snapshot(code='newroom',floor=2))
        self.assertIn('map',p.drain()[0])

    def test_coalesced_updates_still_deliver_first_map(self):
        p=BrowserPeer()
        p.send(self.snapshot(x=112))
        p.send(self.snapshot(x=154))
        data=p.drain()
        self.assertEqual(len(data),1)
        self.assertIn('map',data[0])
        self.assertEqual(data[0]['players'][0]['x'],154)

    def test_network_payload_is_smaller_without_terrain(self):
        p=BrowserPeer()
        p.send(self.snapshot())
        initial=p.drain()[0]
        p.send(self.snapshot(x=126))
        compact=p.drain()[0]
        before=len(json.dumps(initial,separators=(',',':')))
        after=len(json.dumps(compact,separators=(',',':')))
        self.assertGreater(before-after,500)
        self.assertLess(after/before,0.70)

    def test_wait_events_endpoint_wakes_on_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            g=GameServer('127.0.0.1',0,str(Path(tmp)/'game.db'))
            g.start(); web=BrowserGateway(g,'127.0.0.1',0);web.start()
            try:
                peer=web.new_session(); peer.drain()
                outcome={}
                def waiting():
                    t=time.monotonic()
                    with urlopen(f'http://127.0.0.1:{web.port}/api/events?wait=1&session={peer.token}',timeout=4) as resp:
                        outcome['body']=json.load(resp)
                    outcome['elapsed']=time.monotonic()-t
                job=threading.Thread(target=waiting)
                job.start();time.sleep(.14)
                peer.send({'type':'notice','value':5});job.join(timeout=3)
                self.assertFalse(job.is_alive())
                self.assertEqual(outcome['body']['events'][0]['type'],'notice')
                self.assertLess(outcome['elapsed'],.95)
            finally:
                web.stop();g.stop()


class DefenseAndVisuals(unittest.TestCase):
    def test_guard_is_two_seconds_and_cooldown_preserved(self):
        self.assertEqual(DEFENSE_DURATION,2.0)
        self.assertEqual(DEFENSE_COOLDOWN,3.0)
        class Player:
            key='a'; username='alice'; special='brutal'
        r=Room('TEST','solo',Player());r.start()
        p=next(iter(r.players.values()))
        t=time.monotonic()
        r._defend(p,t)
        self.assertAlmostEqual(p['block_until'],t+2.0)
        self.assertAlmostEqual(p['defense_cd'],t+3.0)
        r._defend(p,t+2.1)
        self.assertAlmostEqual(p['block_until'],t+2.0)
        self.assertGreater(r.snapshot()['players'][0]['block_remaining'],1.8)
        r._defend(p,t+3.01)
        self.assertAlmostEqual(p['block_until'],t+5.01)

    def test_visual_source_keeps_sprites_and_uses_interpolation(self):
        js=(ROOT/'web/app.js').read_text()
        self.assertIn('function recordPositions(state)',js)
        self.assertIn('function smoothPosition(id,x,y,dt,isLocal=false)',js)
        self.assertIn('function moveVisual(pos,dx,dy,map)',js)
        self.assertIn('requestAnimationFrame(animate)',js)
        self.assertIn('new EventSource',js)
        self.assertIn('drawImage(sheet,pose.frame*cell',js)
        self.assertIn("fx_'+fx.name+'_sheet",js)
        self.assertIn('app.minimapBase.layer',js)
        self.assertIn("'block_remaining'",(ROOT/'server.py').read_text())

    def test_ui_documents_two_second_guard(self):
        html=(ROOT/'web/index.html').read_text()
        self.assertIn('E: escudo de 2 segundos, recarga de 3 s',html)
        self.assertNotIn('E: defensa de 1 segundo',html)

    @unittest.skipUnless(shutil.which('node'),'Node.js not installed: skip JS movement-math test')
    def test_js_prediction_respects_terrain_and_remote_interpolation(self):
        js=(ROOT/'web/app.js').read_text()
        start=js.index('const ACTOR_SPEED=')
        end=js.index('const SCARF_COLORS=',start)
        pure=js[start:end]
        test=r'''
        const assert=require('assert');
        const TILE=32;
        let ms=1000;
        const performance={now:()=>ms};
        const map=Array.from({length:18},(_,y)=>Array.from({length:28},(_,x)=>(x===0||x===27||y===0||y===17)?'#':'.'));
        map[5][5]='X';
        const grid=map.map(r=>r.join(''));
        const app={positionHistory:new Map(),view:new Map(),pressed:new Set(['right']),touch:new Set(),rttMs:80,
          key:'me',state:{map:grid,players:[{key:'me',paralyzed:false}]}};
        '''+pure+r'''
        const blocked=moveVisual({x:135,y:176},80,0,grid);
        assert(blocked.x<=150.001,'Visual prediction crossed obstacle');
        let sample={players:[{key:'me',x:112,y:112}],enemies:[{id:1,x:200,y:200}]};
        recordPositions(sample);
        const predicted=smoothPosition('pme',112,112,.016,true);
        assert(predicted.x>112,'Local movement did not react immediately');
        ms=1100;sample={players:[{key:'me',x:120,y:112}],enemies:[{id:1,x:207,y:200}]};
        recordPositions(sample);
        const enemy=smoothPosition('e1',207,200,.016,false);
        assert(enemy.x>=199.9&&enemy.x<=207.1,'Remote interpolation overshot');
        const before={...sample.players[0]};
        smoothPosition('pme',120,112,.016,true);
        assert.deepStrictEqual(sample.players[0],before,'Prediction mutated authoritative state');
        console.log('JS movement visual math: OK');
        '''
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'check.js';file.write_text(test)
            run=subprocess.run(['node',str(file)],capture_output=True,text=True,timeout=7)
            self.assertEqual(run.returncode,0,run.stdout+'\n'+run.stderr)

if __name__=='__main__':
    unittest.main()
