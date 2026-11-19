"""V4.2 regressions for network movement rubber-banding and in-game exit.

The Node checks exercise the actual JavaScript functions, without a remote Render
connection. No database credentials or production server are involved.
"""
from __future__ import annotations
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLIENT = ROOT / 'web' / 'app.js'


def node(source):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / 'regression.js'
        path.write_text(source, encoding='utf-8')
        result = subprocess.run(['node', str(path)], capture_output=True, text=True, timeout=12)
        if result.returncode:
            raise AssertionError(result.stdout + '\n' + result.stderr)
        return result.stdout


def movement_source():
    js = CLIENT.read_text(encoding='utf-8')
    return js[js.index('const ACTOR_SPEED='):js.index('const SCARF_COLORS=')]


@unittest.skipUnless(shutil.which('node'), 'Node.js required')
class MovementAndExitV42Tests(unittest.TestCase):
    def test_stalled_authoritative_player_does_not_rubber_band(self):
        source = r'''
const assert=require('node:assert/strict');
const TILE=32;let clock=0;const performance={now:()=>clock};
const grid=Array.from({length:18},(_,y)=>Array.from({length:28},(_,x)=>(x===0||x===27||y===0||y===17)?'#':'.').join(''));
const app={positionHistory:new Map(),view:new Map(),pressed:new Set(['right']),touch:new Set(),rttMs:250,key:'me',
  state:{map:grid,players:[{key:'me',x:112,y:112,paralyzed:false,hp:100}]}};
''' + movement_source() + r'''
// When the server does not move (stalled network or collision), V4.1 drifted
// 136 pixels and then snapped backward by 133, every ~1.1 seconds.
let last=112,furthest=112,largestReverse=0;
for(clock=0;clock<=4500;clock+=16){
  if(clock%80===0)recordPositions({players:[{key:'me',x:112,y:112,moving:false}],enemies:[]});
  const p=smoothPosition('pme',112,112,.016,true);
  furthest=Math.max(furthest,p.x);
  largestReverse=Math.max(largestReverse,last-p.x);
  last=p.x;
}
assert(furthest-112<=30,'Client prediction ran away from server: '+(furthest-112));
assert(largestReverse<3,'Visible backward snap: '+largestReverse);
console.log('bounded prediction: OK');
'''
        self.assertIn('bounded prediction: OK', node(source))

    def test_long_network_gap_does_not_teleport_on_recovery(self):
        source = r'''
const assert=require('node:assert/strict');
const TILE=32;let clock=0;const performance={now:()=>clock};
const grid=Array.from({length:18},(_,y)=>Array.from({length:28},(_,x)=>(x===0||x===27||y===0||y===17)?'#':'.').join(''));
const app={positionHistory:new Map(),view:new Map(),pressed:new Set(['right']),touch:new Set(),rttMs:300,key:'me',
  state:{map:grid,players:[{key:'me',x:112,y:112,paralyzed:false,hp:100}]}};
''' + movement_source() + r'''
let previous=112,maxJump=0,maxLead=0;
let authX=112;
for(clock=0;clock<=3100;clock+=16){
  // No authoritative progress for the first 1000 ms. Then the network
  // delivers updates whose positions move smoothly at 145px/s.
  if(clock%80===0){
    authX=112+Math.max(0,clock-1000)*.145;
    recordPositions({players:[{key:'me',x:authX,y:112,moving:clock>1000}],enemies:[]});
  }
  const p=smoothPosition('pme',authX,112,.016,true);
  maxJump=Math.max(maxJump,Math.abs(p.x-previous));
  maxLead=Math.max(maxLead,p.x-authX);previous=p.x;
}
assert(maxJump<5,'Recovery jump exceeded expected one-frame movement: '+maxJump);
assert(maxLead<30,'Prediction exceeded bounded lead: '+maxLead);
console.log('reconnection no snap: OK');
'''
        self.assertIn('reconnection no snap: OK', node(source))

    def test_release_reconciles_gradually_not_teleport(self):
        source = r'''
const assert=require('node:assert/strict');
const TILE=32;let clock=0;const performance={now:()=>clock};
const grid=Array.from({length:18},(_,y)=>Array.from({length:28},(_,x)=>(x===0||x===27||y===0||y===17)?'#':'.').join(''));
const app={positionHistory:new Map(),view:new Map(),pressed:new Set(['right']),touch:new Set(),rttMs:240,key:'me',
  state:{map:grid,players:[{key:'me',x:112,y:112,paralyzed:false,hp:100}]}};
''' + movement_source() + r'''
let before;
for(clock=0;clock<=400;clock+=16){
 if(clock%80===0)recordPositions({players:[{key:'me',x:112,y:112,moving:false}],enemies:[]});
 before=smoothPosition('pme',112,112,.016,true).x;
}
app.pressed.clear();clock+=16;
const after=smoothPosition('pme',112,112,.016,true).x;
assert(before-after<3.1,'Release jumped backward: '+(before-after));
for(let i=0;i<25;i++){clock+=16;smoothPosition('pme',112,112,.016,true);}
assert(Math.abs(app.view.get('pme').x-112)<.2,'Released player failed to reconcile');
console.log('release converges gently: OK');
'''
        self.assertIn('release converges gently: OK', node(source))

    def test_exit_button_sends_once_no_native_confirm_and_handles_error(self):
        js=CLIENT.read_text(encoding='utf-8')
        leave=js[js.index('async function leave(){'):js.index("$('results-home').addEventListener",js.index('async function leave(){'))]
        code=r'''
const assert=require('node:assert/strict');
const handlers={},elems={};
function $(id){return elems[id]||(elems[id]={textContent:id==='leave-game'?'ABANDONAR':'',disabled:false,
  addEventListener(type,fn){handlers[id+':'+type]=fn;}});}
const app={scene:'game',leaving:false,pressed:new Set(['right']),touch:new Set(),
  room:{code:'A1B2C3'},state:{code:'A1B2C3'},ignoredRoomCode:'',view:new Map(),positionHistory:new Map(),
  animations:new Map(),previousHP:new Map(),specialEffects:[],effectSeq:new Map(),particles:[],floorKey:'OLD',hudRoster:'old',
  minimapBase:{key:'OLD'},lastMove:{dx:1,dy:0,at:10}};
let calls=0,resolver=null,toastMessage='';
const send=()=>{calls++;return new Promise(resolve=>{resolver=resolve;});};
const scene=(name)=>{app.scene=name;};
const toast=(msg)=>{toastMessage=msg;};
const confirm=()=>{throw Error('Native confirm must not be called on mobile');};
'''+leave+r'''
;(async()=>{
 const t1=handlers['leave-game:click']();
 const t2=handlers['leave-game:click']();
 assert.equal(calls,1,'Double click sent duplicate leave requests');
 assert.equal($('leave-game').textContent,'SALIENDO...');
 assert.equal($('leave-game').disabled,true);
 resolver(true);await t1;await t2;
 assert.equal(app.scene,'home');assert.equal(app.room,null);
 assert.equal(app.positionHistory.size,0);
 assert.equal(app.ignoredRoomCode,'A1B2C3');
 assert.equal($('leave-game').textContent,'ABANDONAR');
 assert.equal($('leave-game').disabled,false);
 // A failure must keep the game open and show retry feedback.
 app.scene='game';app.room={code:'A1B2C3'};app.state={code:'A1B2C3'};
 const t3=handlers['leave-game:click']();resolver(false);await t3;
 assert.equal(app.scene,'game');assert.equal(app.room.code,'A1B2C3');
 assert.match(toastMessage,/No se pudo abandonar/);
 console.log('exit success, duplicate prevention and failure handling: OK');
})().catch(error=>{console.error(error);process.exit(1)});
'''
        self.assertIn('exit success, duplicate prevention and failure handling: OK',node(code))

    def test_late_room_packets_cannot_reopen_game_after_exit(self):
        js=CLIENT.read_text(encoding='utf-8')
        handler=js[js.index('function handleMessage(event){'):js.index('function validateCredentials()')]
        code=r'''
const assert=require('node:assert/strict');
const app={leaving:false,ignoredRoomCode:'A1B2C3',room:null,state:null,scene:'home'};
'''+handler+r'''
handleMessage({type:'room_state',code:'A1B2C3',status:'playing'});
handleMessage({type:'game_state',code:'A1B2C3',players:[{key:'me'}]});
assert.equal(app.scene,'home');assert.equal(app.room,null);assert.equal(app.state,null);
app.leaving=true;
handleMessage({type:'room_state',code:'SOMENEW',status:'playing'});
assert.equal(app.room,null);
console.log('late room events ignored: OK');
'''
        self.assertIn('late room events ignored: OK',node(code))

    def test_no_game_mechanics_or_database_changes(self):
        html=(ROOT/'web'/'index.html').read_text(encoding='utf-8')
        server=(ROOT/'server.py').read_text(encoding='utf-8')
        self.assertIn('/app.js?v=movement-v42',html)
        self.assertIn('id="leave-game" type="button"',html)
        self.assertIn('DEFENSE_DURATION = 2.0',server)
        self.assertIn('DEFENSE_COOLDOWN = 3.0',server)
        self.assertIn("GAME_MODES = ('solo', 'coop', 'pvp')",server)

if __name__=='__main__':
    unittest.main()
