"""V4.1 regression tests: movement must not jitter under irregular snapshot arrival.

Pure-client tests execute with Node.js; they do not claim Internet/Render latency.
No game rules or database credentials are touched.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CLIENT=ROOT/'web'/'app.js'


def run_js(source: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        script=Path(tmp)/'verify.js'
        script.write_text(source,encoding='utf8')
        result=subprocess.run(['node',str(script)],capture_output=True,text=True,timeout=15)
        if result.returncode:
            raise AssertionError(result.stdout+'\n'+result.stderr)
        return result.stdout


@unittest.skipUnless(shutil.which('node'),'Requires Node.js for browser movement math')
class VisualMovementV41Tests(unittest.TestCase):
    def test_linear_motion_with_jitter_never_rewinds(self):
        js=CLIENT.read_text()
        pure=js[js.index('const ACTOR_SPEED='):js.index('const SCARF_COLORS=')]
        setup='''
const assert=require('node:assert/strict');
const TILE=32;
let clock=0;
const performance={now:()=>clock};
const grid=Array.from({length:18},(_,y)=>Array.from({length:28},(_,x)=>(x===0||x===27||y===0||y===17)?'#':'.').join(''));
const app={positionHistory:new Map(),view:new Map(),pressed:new Set(),touch:new Set(),rttMs:120,key:'me',
           state:{map:grid,players:[{key:'me',paralyzed:false,hp:100}]}};
'''
        test='''
const packets=[0,85,163,265,420,515,590,702,843,916,1055];
const offset=115;
let cursor=0,prev=112,largest=0;
for(clock=0;clock<=1250;clock+=16){
 while(cursor<packets.length&&packets[cursor]<=clock){
   // Authoritative actor moves continuously, but packet delivery is irregular.
   const eventTime=packets[cursor];
   const state={players:[],enemies:[{id:1,x:112+Math.max(0,eventTime-offset)*.08,y:160,moving:true}]};
   recordPositions(state);cursor++;
 }
 const result=smoothPosition('e1',app.positionHistory.get('e1').latest.x,160,.016,false);
 const jump=Math.abs(result.x-prev);
 largest=Math.max(largest,jump);
 assert(result.x>=prev-.06,`Remote walked backward at ${clock}ms: ${result.x} < ${prev}`);
 prev=result.x;
}
assert(largest<8,`Remote position jump too large: ${largest}`);
console.log('remote jitter monotonic OK');
'''
        self.assertIn('remote jitter monotonic OK',run_js(setup+pure+test))

    def test_local_prediction_does_not_snap_backward_under_latency(self):
        js=CLIENT.read_text()
        pure=js[js.index('const ACTOR_SPEED='):js.index('const SCARF_COLORS=')]
        setup='''
const assert=require('node:assert/strict');
const TILE=32;
let clock=0;
const performance={now:()=>clock};
const grid=Array.from({length:18},(_,y)=>Array.from({length:28},(_,x)=>(x===0||x===27||y===0||y===17)?'#':'.').join(''));
const app={positionHistory:new Map(),view:new Map(),pressed:new Set(['right']),touch:new Set(),rttMs:220,key:'me',
           state:{map:grid,players:[{key:'me',paralyzed:false,hp:100}]}};
'''
        test='''
let prev=112,err=0;
const arrivals=[0,116,218,355,460,550,673,788,900,1007,1120];
let cursor=0;
for(clock=0;clock<=1190;clock+=16){
  while(cursor<arrivals.length&&arrivals[cursor]<=clock){
    const stamp=arrivals[cursor];
    // Server sees input after 150ms; jitter adds arbitrary packet lag.
    const x=112+Math.max(0,stamp-150)*.145;
    recordPositions({players:[{key:'me',x,y:112,moving:true}],enemies:[]});
    app.state.players=[{key:'me',x,y:112,paralyzed:false,hp:100}];cursor++;
  }
  const serverX=app.positionHistory.get('pme').latest.x;
  const p=smoothPosition('pme',serverX,112,.016,true);
  err=Math.max(err,prev-p.x);
  assert(p.x>=prev-.1,`Local avatar jumped backwards: ${p.x} < ${prev}`);
  prev=p.x;
}
assert(err<.1);
// Releasing the key allows smooth authoritative reconciliation, no teleport.
app.pressed.clear();
const before=app.view.get('pme').x;
clock+=16;
const after=smoothPosition('pme',app.positionHistory.get('pme').latest.x,112,.016,true).x;
assert(Math.abs(after-before)<4,`Release caused sudden jump: ${after-before}`);
console.log('local reconciliation monotonic OK');
'''
        self.assertIn('local reconciliation monotonic OK',run_js(setup+pure+test))

    def test_release_is_sent_while_previous_request_is_pending(self):
        js=CLIENT.read_text()
        pure=js[js.index('function requestInput(priority=false)'):js.index('setInterval(()=>requestInput()',js.index('function requestInput(priority=false)'))]
        test='''
const assert=require('node:assert/strict');
let now=1000;
const Date={now:()=>now};
const app={scene:'game',session:'example',pressed:new Set(['right']),touch:new Set(),
  inputBusy:false,attackQueued:false,specialQueued:false,defendQueued:false,
  lastMove:{dx:0,dy:0,at:0},inputSeq:1000000};
const actions=[];
const send=(action)=>{actions.push(action);return new Promise(()=>{});};
'''+pure+'''
requestInput();
assert.equal(actions.length,1);
assert.equal(actions[0].dx,1);
app.pressed.clear();
app.inputBusy=true; // unrelated heartbeat request is still outstanding
now+=30;
requestInput();
assert.equal(actions.length,2,'Release was blocked by an earlier request');
assert.equal(actions[1].dx,0);
assert(actions[1].seq>actions[0].seq);
console.log('immediate stop request OK');
'''
        self.assertIn('immediate stop request OK',run_js(test))

    def test_original_game_rules_remain_in_place(self):
        server=(ROOT/'server.py').read_text()
        self.assertIn('DEFENSE_DURATION = 2.0',server)
        self.assertIn('DEFENSE_COOLDOWN = 3.0',server)
        self.assertIn("GAME_MODES = ('solo', 'coop', 'pvp')",server)
        self.assertIn("p['last_input'] = time.monotonic()",server)


if __name__=='__main__':
    unittest.main()
