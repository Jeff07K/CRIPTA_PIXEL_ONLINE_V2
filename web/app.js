'use strict';
/* Cliente web sin dependencias. Las reglas y todas las puntuaciones viven en Python.
   Peticiones HTTP al mismo servidor; varios navegadores son clientes independientes. */
const $ = id => document.getElementById(id);
const app = {
  session:null, key:'',name:'',scene:'auth',room:null,state:null,results:null,
  ranking:[],rankDay:'',rankMode:'solo', active:true, lastState:0,lastPoll:0,
  inputBusy:false,attackQueued:false,specialQueued:false,defendQueued:false,specialChoice:'brutal',pressed:new Set(),touch:new Set(),
  stream:null,streamActive:false,nextStreamTry:0,inputSeq:Date.now()*1000,lastMove:{dx:0,dy:0,at:0},
  view:new Map(),positionHistory:new Map(),worldProps:[],floorKey:'',tileCanvas:null,minimapBase:null,lastFrame:performance.now(),
  rttMs:80,perfFrames:0,perfSampleAt:performance.now(),fps:60,netIndicator:null,hudRoster:'',
  images:{}, frame:0,requestInProgress:false,animations:new Map(),particles:[],previousHP:new Map(),specialEffects:[],effectSeq:new Map(),shake:0,soundEnabled:true,audio:null,cameraZoom:1.12
};
const sprites = ['hero','knight_rojo','knight_azul','knight_verde','knight_naranja','slime','bat','goblin','skeleton','flame','boss','ghost',
  ...['rojo','azul','verde','naranja'].map(c=>'knight_'+c+'_sheet'),
  ...['slime','bat','goblin','skeleton','flame','boss','ghost'].map(c=>c+'_sheet'),
  ...['brutal','distancia','veneno','paralisis'].map(c=>'fx_'+c+'_sheet'),
  ...['forest','ice','fire','arena'].map(c=>'terrain_'+c)];
for (const k of sprites) {
  const img=new Image(); img.src='/assets/'+k+'.png?v=animation-v2'; app.images[k]=img;
}
// Audio sintetizado local: efectos originales, sin música ni recursos externos.
function sfx(type){
  if(!app.soundEnabled)return;
  try{
    const AC=window.AudioContext||window.webkitAudioContext;
    if(!AC)return;
    if(!app.audio)app.audio=new AC();
    const ac=app.audio;if(ac.state==='suspended')ac.resume().catch(()=>{});
    const osc=ac.createOscillator(),gain=ac.createGain();
    const now=ac.currentTime;
    const config={attack:[390,145,.07,'triangle'],special:[610,220,.19,'sawtooth'],guard:[250,440,.12,'sine'],hurt:[190,75,.14,'triangle'],kill:[450,760,.20,'triangle']}[type]||[270,150,.07,'sine'];
    osc.type=config[3];osc.frequency.setValueAtTime(config[0],now);osc.frequency.exponentialRampToValueAtTime(config[1],now+config[2]);
    gain.gain.setValueAtTime(.001,now);gain.gain.exponentialRampToValueAtTime(.10,now+.012);
    gain.gain.exponentialRampToValueAtTime(.001,now+config[2]);
    osc.connect(gain);gain.connect(ac.destination);osc.start(now);osc.stop(now+config[2]+.025);
  }catch(_ignored){}
}
const audioButton=document.createElement('button');
audioButton.className='sound-toggle';audioButton.type='button';
audioButton.title='Activar o silenciar efectos de sonido';audioButton.textContent='♫ SONIDO: SÍ';
audioButton.setAttribute('aria-pressed','true');
audioButton.addEventListener('click',()=>{
  app.soundEnabled=!app.soundEnabled;audioButton.textContent=app.soundEnabled?'♫ SONIDO: SÍ':'♫ SONIDO: NO';
  audioButton.setAttribute('aria-pressed',String(app.soundEnabled));
  if(app.soundEnabled)sfx('guard');
});
document.querySelector('.top-right')?.prepend(audioButton);
const W=896,H=576,TILE=32;
const canvas=$('world'),ctx=canvas.getContext('2d',{alpha:false});
const netIndicator=document.createElement('span');
netIndicator.id='network-indicator';
netIndicator.title='RTT aproximado de controles y fotogramas reales del navegador';
netIndicator.style.cssText='font-size:10px;color:#80e8a6;white-space:nowrap';
document.querySelector('#game .under-map')?.appendChild(netIndicator);
app.netIndicator=netIndicator;
ctx.imageSmoothingEnabled=false;
let toastTimeout;
function toast(message) {
  const box=$('toast'); box.textContent=String(message).slice(0,180);box.hidden=false;
  clearTimeout(toastTimeout);toastTimeout=setTimeout(()=>{box.hidden=true},4300);
}
function scene(name) {
  app.scene=name;
  for(const node of document.querySelectorAll('.screen'))node.hidden=(node.id!==name);
  if(name==='ranking') refreshRanking();
  if(name==='game'){app.lastState=Date.now();}
  window.scrollTo({top:0,behavior:'instant'});
}
function escapeText(value){return String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function setConnected(connected){
  const online=$('online');online.classList.toggle('connected',connected);
  online.innerHTML=connected?'<i></i> SERVIDOR ONLINE':'<i></i> SIN CONEXIÓN';
}
async function fetchJSON(path, init={}){
  const ac=new AbortController();const timeout=setTimeout(()=>ac.abort(),7000);
  try {
    const response=await fetch(path,{cache:'no-store',signal:ac.signal,...init});
    const data=await response.json();
    if(!response.ok)throw new Error(data.error||'HTTP '+response.status);
    return data;
  } finally {clearTimeout(timeout);}
}
const post=(path,data)=>fetchJSON(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
async function connect(){
  try {
    const data=await post('/api/connect',{});
    app.session=data.session;app.key=data.key;sessionStorage.setItem('cripta_session',app.session);setConnected(true);
    toast('Conectado. Crea tu usuario o inicia sesión.');
    return true;
  }catch(e){setConnected(false);toast('No se puede contactar al servidor: '+e.message);return false;}
}
async function send(action){
  if(!app.session){if(!await connect())return false;}
  const started=performance.now();
  try{await post('/api/action',{session:app.session,action});
    if(action.type==='input'){const ms=performance.now()-started;app.rttMs=.8*app.rttMs+.2*Math.min(1500,ms);}
    return true;}
  catch(e){if(e.message.includes('Sesion')||e.message.includes('401')){stopEventStream();app.session=null;setConnected(false);scene('auth');}
    else if(action.type!=='input')toast('Red: '+e.message);return false;}
}
 function stopEventStream(){
   if(app.stream){app.stream.close();app.stream=null;}
   app.streamActive=false;
 }
 function applyEvents(events){
   setConnected(true);app.lastPoll=Date.now();
   for(const event of events||[])handleMessage(event);
 }
 async function poll(){
   if(!app.session||app.requestInProgress)return;
   app.requestInProgress=true;
   try{
     const data=await fetchJSON('/api/events?wait=1&session='+encodeURIComponent(app.session));
     applyEvents(data.events);
   }catch(e){
     if(e.message.includes('Sesion')){stopEventStream();app.session=null;sessionStorage.removeItem('cripta_session');setConnected(false);scene('auth');toast('La sesión expiró. Inicia sesión nuevamente.');}
     else if(Date.now()-app.lastPoll>4500){setConnected(false);}
   }finally{app.requestInProgress=false;}
 }
 function startEventStream(){
   if(!window.EventSource||!app.session||app.stream)return;
   const stream=new EventSource('/api/stream?session='+encodeURIComponent(app.session));
   app.stream=stream;app.streamActive=false;
   stream.onopen=()=>{if(app.stream===stream){app.streamActive=true;setConnected(true);app.lastPoll=Date.now();}};
   stream.onmessage=ev=>{
     if(app.stream!==stream)return;
     try{applyEvents(JSON.parse(ev.data).events);}catch(_){/* Mal mensaje: esperar el siguiente. */}
   };
   stream.onerror=()=>{
     if(app.stream===stream){stopEventStream();app.nextStreamTry=Date.now()+10000;}
   };
 }
 // SSE evita esperar a la siguiente encuesta HTTP; /api/events conserva compatibilidad.
 async function pollLoop(){while(true){
   if(!app.session){await new Promise(r=>setTimeout(r,350));continue;}
   if(window.EventSource && !app.stream && Date.now()>=app.nextStreamTry)startEventStream();
   if(app.stream){await new Promise(r=>setTimeout(r,250));continue;}
   await poll();await new Promise(r=>setTimeout(r,95));
 }}
function handleMessage(event){
  const type=event.type;
  if(type==='hello')return;
  if(type==='error'){toast(event.message||'Error de servidor');return;}
  if(type==='register_result'){
    toast(event.message||'Registro procesado');
    if(event.ok){send({type:'login',username:$('username').value.trim(),password:$('password').value});}
    return;
  }
  if(type==='login_result'){
    toast(event.message||'Respuesta de inicio de sesión');
    if(event.ok){app.name=event.name;app.key=event.key;$('player-tag').textContent='✦ '+app.name.toUpperCase();$('player-tag').hidden=false;scene('home');}
    return;
  }
  if(type==='room_state'){
    app.room=event;
    const mine=(event.loadouts||[]).find(p=>p.name===app.name);
    if(mine&&app.scene!=='game')chooseSpecial(mine.special);
    if(event.status==='lobby'){renderLobby();scene('lobby');}
    if(event.status==='playing'&&app.scene!=='results'){scene('game');}
    return;
  }
  if(type==='game_state'){
    // Network snapshots can omit the unchanged terrain to reduce bandwidth.
    // A new room/floor must always arrive with a full terrain map.
    if(!event.map && app.state?.code===event.code && app.state?.floor===event.floor)event.map=app.state.map;
    if(!event.map)return; // A broken/out-of-order delta must not corrupt rendering.
    processCombatFeedback(event);
    recordPositions(event);
    app.state=event;app.lastState=Date.now();
    if(app.scene==='lobby'||(app.scene==='game')){
      if(app.scene!=='game')scene('game');
      if(!app.lastHudAt||Date.now()-app.lastHudAt>=150){updateGameHUD(event);app.lastHudAt=Date.now();}
    }
    return;
  }
  if(type==='game_over'){
    app.results=event;
    renderResults();scene('results');
    return;
  }
  if(type==='ranking'){
    if(event.mode!==app.rankMode)return;
    app.ranking=event.items||[];app.rankDay=event.date;
    if(app.scene==='ranking')renderRanking();return;
  }
  if(type==='left_room'){
    app.room=null;app.state=null;app.hudRoster='';app.view.clear();app.animations.clear();app.previousHP.clear();app.specialEffects=[];app.effectSeq.clear();app.particles=[];app.floorKey='';
    return;
  }
}
function validateCredentials(){
  const username=$('username').value.trim(),password=$('password').value;
  if(!/^[A-Za-z0-9_]{3,18}$/.test(username)){toast('Usuario: de 3 a 18 letras, números o guion bajo.');return null;}
  if(password.length<6||password.length>72){toast('Contraseña: entre 6 y 72 caracteres.');return null;}
  return {username,password};
}
$('login-form').addEventListener('submit',async e=>{e.preventDefault();const creds=validateCredentials();if(creds)await send({type:'login',...creds});});
$('register-btn').addEventListener('click',async()=>{const creds=validateCredentials();if(creds)await send({type:'register',...creds});});
function selectedSpecial(){return document.querySelector('input[name="special"]:checked')?.value||'brutal';}
function chooseSpecial(value){
  app.specialChoice=value;
  const choice=document.querySelector('input[name="special"][value="'+value+'"]');
  if(choice)choice.checked=true;
  $('lobby-special').value=value;
}
for(const r of document.querySelectorAll('input[name="special"]'))r.addEventListener('change',()=>chooseSpecial(selectedSpecial()));
$('lobby-special').addEventListener('change',async()=>{
  const value=$('lobby-special').value;
  const ok=await send({type:'equip_special',special:value});
  if(ok)chooseSpecial(value);
});
$('create-solo').addEventListener('click',()=>send({type:'create_room',mode:'solo',special:app.specialChoice}));
$('create-coop').addEventListener('click',()=>send({type:'create_room',mode:'coop',special:app.specialChoice}));
$('create-pvp').addEventListener('click',()=>send({type:'create_room',mode:'pvp',special:app.specialChoice}));
$('join-room').addEventListener('click',()=>{
  const code=$('room-code').value.trim().toUpperCase();if(!/^[A-F0-9]{6}$/.test(code)){toast('Introduce el código de 6 caracteres de la sala.');return;}
  send({type:'join_room',code,special:app.specialChoice});
});
$('room-code').addEventListener('keydown',e=>{if(e.key==='Enter')$('join-room').click();});
$('start-game').addEventListener('click',()=>send({type:'start_room'}));
async function leave(){await send({type:'leave_room'});app.state=null;app.room=null;app.view.clear();app.animations.clear();app.previousHP.clear();app.specialEffects=[];app.effectSeq.clear();app.particles=[];app.floorKey='';scene('home');}
$('exit-lobby').addEventListener('click',leave);
$('leave-game').addEventListener('click',()=>{if(confirm('¿Abandonar esta partida? Perderás tu progreso de esta ronda.'))leave();});
$('results-home').addEventListener('click',leave);
$('results-ranking').addEventListener('click',async()=>{await send({type:'leave_room'});app.room=null;app.state=null;app.rankMode=app.results?.mode||'solo';scene('ranking');});
$('show-rank').addEventListener('click',()=>scene('ranking'));
$('rank-back').addEventListener('click',()=>scene('home'));
$('rank-refresh').addEventListener('click',refreshRanking);
for (const b of document.querySelectorAll('[data-rank-mode]')) {
  b.addEventListener('click',()=>{app.rankMode=b.dataset.rankMode;app.ranking=[];renderRanking();refreshRanking();});
}
$('copy-code').addEventListener('click',async()=>{
  const code=app.room?.code||'';
  try {if(!navigator.clipboard)throw Error('El navegador no permite copiar en HTTP');await navigator.clipboard.writeText(code);toast('Código '+code+' copiado.');}
  catch {toast('Código de tu sala: '+code+' (puedes copiarlo manualmente).');}
});
function renderLobby(){
  const room=app.room;if(!room)return;
  $('invite-code').textContent=room.code;
  $('lobby-mode').textContent=room.mode==='coop'?'⚔ EXPEDICIÓN COOPERATIVA':'♜ COMBATE PVP';
  const arr=room.players||[];
  const loadouts=room.loadouts||[];
  $('lobby-special').value=app.specialChoice;
  $('party-count').textContent=arr.length+' / 4';
  const slots=$('party-slots');slots.innerHTML='';
  for(let i=0;i<4;i++){
    const node=document.createElement('div');node.className='party-slot'+(i>=arr.length?' empty':'');
    const im=document.createElement('img');im.src='/assets/'+(i<arr.length?'knight_'+(loadouts[i]?.color||['rojo','azul','verde','naranja'][i]):'ghost')+'.png?v=animation7';im.alt='';node.appendChild(im);
    const text=document.createElement('span');
    const names={brutal:'Brutal',distancia:'Distancia',veneno:'Veneno',paralisis:'Parálisis'};
    text.textContent=i<arr.length?arr[i]+' · '+(names[loadouts[i]?.special]||'Brutal'):'CUPO LIBRE';
    node.appendChild(text);slots.appendChild(node);
  }
  const host=room.host===app.name;
  const btn=$('start-game');btn.disabled=!(host&&arr.length>=2&&arr.length<=4);
  btn.textContent=host?(arr.length>=2?'INICIAR PARTIDA ↗':'NECESITAS OTRO JUGADOR'):'ESPERANDO AL ANFITRIÓN';
  $('host-note').textContent=host?'Eres el anfitrión. Inicia cuando el equipo esté listo.':'El anfitrión '+room.host+' controla el inicio de la partida.';
}
function refreshRanking(){if(app.session&&app.name)send({type:'ranking',mode:app.rankMode});}
function renderRanking(){
  const names={solo:'SOLITARIO',coop:'COOPERATIVO',pvp:'PVP'};
  for(const b of document.querySelectorAll('[data-rank-mode]')){const active=b.dataset.rankMode===app.rankMode;b.classList.toggle('selected',active);b.setAttribute('aria-pressed',String(active));}
  $('rank-date').textContent='Clasificación: '+names[app.rankMode]+' · Día: '+(app.rankDay||'consultando…')+' (hora Colombia)';
  const parent=$('rank-list');parent.innerHTML='';
  if(!app.ranking.length){const p=document.createElement('p');p.className='empty';p.textContent='Todavía no hay partidas terminadas hoy. ¡Sé el primero!';parent.appendChild(p);return;}
  app.ranking.forEach((r,i)=>{
    const row=document.createElement('div');row.className='rank-row';
    const values=['#'+String(i+1).padStart(2,'0'),r.name,Number(r.points).toLocaleString('es-CO'),r.wins,r.games];
    values.forEach((v,j)=>{const el=document.createElement(j===2?'b':'span');el.textContent=v;row.appendChild(el);});
    parent.appendChild(row);
  });
}
function renderResults(){
  const r=app.results;if(!r)return;
  const victory=r.mode==='pvp'?!!r.winner:r.reason==='victory';
  $('result-mark').textContent=r.reason==='victory'?'✦ MAZMORRAS SUPERADAS':r.mode==='pvp'?'◆ ARENA FINALIZADA':'◆ FIN DE LA EXPEDICIÓN';
  $('result-title').innerHTML=victory?(r.mode==='coop'?'VICTORIA <em>DEL EQUIPO</em>':r.mode==='solo'?'¡HÉROE <em>VICTORIOSO!</em>':'CAMPEÓN: <em>'+escapeText(r.winner)+'</em>'):'PARTIDA <em>FINALIZADA</em>'; 
  $('result-info').textContent='Puntuaciones guardadas en el servidor · Clasificación del día '+r.date;
  const parent=$('result-list');parent.innerHTML='';
  const heading=document.createElement('div');heading.className='result-row heading';
  ['JUGADOR','PUNTOS','BAJAS','VICTORIAS'].forEach(s=>{const el=document.createElement('span');el.textContent=s;heading.appendChild(el);});
  parent.appendChild(heading);
  [...r.players].sort((a,b)=>b.score-a.score).forEach(p=>{
    const row=document.createElement('div');row.className='result-row';
    [p.name,p.score,p.kills,p.wins].forEach(val=>{const el=document.createElement('span');el.textContent=String(val);row.appendChild(el);});parent.appendChild(row);
  });
}
function updateGameHUD(state){
  const pve=state.mode!=='pvp';
  $('game-title').innerHTML=state.mode==='solo'?'AVENTURA <em>SOLITARIA</em>':state.mode==='coop'?'EXPEDICIÓN <em>COOPERATIVA</em>':'ARENA <em>JUGADOR VS JUGADOR</em>';
  $('floor-indicator').textContent=pve?'PISO '+state.floor+' / '+state.max_floors:'ARENA PVP';
  $('remaining').textContent=pve?'ENEMIGOS RESTANTES: '+state.enemies.length:'TIEMPO: '+state.remaining+' S';
  $('hud-party-title').textContent=state.mode==='solo'?'MI PERSONAJE':state.mode==='coop'?'MI ESCUADRÓN':'COMBATIENTES';
  $('game-objective').textContent=pve?'Derrota los monstruos de cada piso y al jefe final sin perder toda tu vida.':'El primero en lograr 5 eliminaciones gana, o el que más tenga en 3 minutos.';
  const me=state.players.find(p=>p.key===app.key);
  if(me){
    $('my-score').textContent=Number(me.score).toLocaleString('es-CO');$('my-kills').textContent=me.kills;
    const names={brutal:'GOLPE BRUTAL',distancia:'CORTE A DISTANCIA',veneno:'VENENO',paralisis:'PARÁLISIS'};
    $('hud-special').textContent='Q · '+(names[me.special]||'ESPECIAL')+' · '+(me.special_ready_in>0?me.special_ready_in+'s':'LISTO');
    $('special-meter').style.width=(100*(1-Math.min(6,me.special_ready_in)/6)).toFixed(1)+'%';
    $('defense-meter').style.width=(100*(1-Math.min(3,me.defense_ready_in)/3)).toFixed(1)+'%';
    $('hud-defense').textContent='E · '+(me.blocking?'ESCUDO '+(me.block_remaining??0).toFixed(1)+'s'+(me.block_reduction?' (último '+me.block_reduction+' %)':''):me.defense_ready_in>0?me.defense_ready_in+'s':'LISTA');
    $('touch-special').disabled=me.special_ready_in>0||me.hp<=0;
    $('touch-defend').disabled=me.defense_ready_in>0||me.hp<=0;
  }
  const hud=$('hud-party');
  const roster=state.players.map(p=>p.key+':'+p.name+':'+p.color).join('|');
  if(app.hudRoster!==roster){
    app.hudRoster=roster;hud.replaceChildren();
    for(const p of state.players){
      const el=document.createElement('div');el.className='hud-player';el.dataset.key=p.key;
      const name=document.createElement('div');name.className='hud-name';
      const b=document.createElement('strong');b.textContent=p.name+' ['+(p.color||'rojo')+']'+(p.key===app.key?' ★':'');
      const hp=document.createElement('span');name.append(b,hp);el.appendChild(name);
      const bar=document.createElement('div');bar.className='hp-track';
      const fill=document.createElement('div');bar.appendChild(fill);el.appendChild(bar);hud.appendChild(el);
    }
  }
  for(const [i,p] of state.players.entries()){
    const el=hud.children[i],hp=el.querySelector('span'),fill=el.querySelector('.hp-track > div');
    if(hp.textContent!==p.hp+' HP')hp.textContent=p.hp+' HP';
    const width=Math.max(0,Math.min(100,p.hp))+'%';
    if(fill.style.width!==width)fill.style.width=width;
    const color=p.hp<35?'#fd8b8b':'#80e8a6';
    if(fill.style.background!==color)fill.style.background=color;
  }
  drawMiniMap(state);
  const msg=$('world-message');msg.hidden=!state.message;msg.textContent=state.message||'';
}
function drawMiniMap(state){
  const mini=$('minimap');if(!mini||!state?.map)return;
  const g=mini.getContext('2d');g.imageSmoothingEnabled=false;
  const tile=6,w=168,h=108;
  // Cache the static dungeon once; repaint only actors on each HUD refresh.
  const key=state.code+'|'+state.mode+'|'+state.floor;
  if(!app.minimapBase || app.minimapBase.key!==key){
    const layer=document.createElement('canvas');layer.width=w;layer.height=h;
    const bg=layer.getContext('2d');bg.imageSmoothingEnabled=false;
    bg.fillStyle='#0c1523';bg.fillRect(0,0,w,h);
    for(let y=0;y<state.map.length;y++)for(let x=0;x<state.map[y].length;x++){
      const c=state.map[y][x];
      bg.fillStyle=c==='#'?'#344157':c==='X'?'#88919e':
        state.mode==='pvp'?'#3f4861':state.floor===1?'#31543f':state.floor===2?'#496f86':'#653e40';
      bg.fillRect(x*tile,y*tile,tile,tile);
    }
    app.minimapBase={key,layer};
  }
  g.drawImage(app.minimapBase.layer,0,0);
  for(const e of state.enemies){g.fillStyle=e.kind==='boss'?'#ffc76f':'#f17d78';g.fillRect(Math.round(e.x/TILE*tile)-2,Math.round(e.y/TILE*tile)-2,4,4);}
  for(const p of state.players){if(p.hp<=0)continue;g.fillStyle=playerColor(0,p.color);g.fillRect(Math.round(p.x/TILE*tile)-3,Math.round(p.y/TILE*tile)-3,6,6);
    if(p.key===app.key){g.strokeStyle='#faf4d9';g.lineWidth=1;g.strokeRect(Math.round(p.x/TILE*tile)-4,Math.round(p.y/TILE*tile)-4,8,8);}}
}
$('zoom-toggle').addEventListener('click',()=>{
  app.cameraZoom=app.cameraZoom===1?1.12:app.cameraZoom===1.12?1.3:1;
  $('zoom-toggle').textContent='ZOOM '+Math.round(app.cameraZoom*100)+' %';
});
// Controles para teclado / equipos tactiles.
const directionKeys={w:'up',ArrowUp:'up',s:'down',ArrowDown:'down',a:'left',ArrowLeft:'left',d:'right',ArrowRight:'right'};
window.addEventListener('keydown',e=>{
  if(app.scene!=='game')return;
  if(e.target instanceof HTMLInputElement)return;
  if(directionKeys[e.key]||directionKeys[e.key.toLowerCase()]){app.pressed.add(directionKeys[e.key]||directionKeys[e.key.toLowerCase()]);e.preventDefault();requestInput();}
  if(e.code==='Space'){if(!e.repeat){app.attackQueued=true;requestInput(true);}e.preventDefault();}
  if(e.code==='KeyQ'){if(!e.repeat){app.specialQueued=true;requestInput(true);}e.preventDefault();}
  if(e.code==='KeyE'){if(!e.repeat){app.defendQueued=true;requestInput(true);}e.preventDefault();}
  if(e.key==='Escape')$('leave-game').click();
});
window.addEventListener('keyup',e=>{const d=directionKeys[e.key]||directionKeys[e.key.toLowerCase()];if(d){app.pressed.delete(d);requestInput();}});
window.addEventListener('blur',()=>{app.pressed.clear();app.touch.clear();requestInput();});
for(const b of document.querySelectorAll('[data-move]')){
  const key=b.dataset.move;
  b.addEventListener('pointerdown',e=>{e.preventDefault();b.setPointerCapture(e.pointerId);app.touch.add(key);b.classList.add('pressed');requestInput();});
  const end=e=>{e.preventDefault();app.touch.delete(key);b.classList.remove('pressed');requestInput();};
  b.addEventListener('pointerup',end);b.addEventListener('pointercancel',end);b.addEventListener('lostpointercapture',()=>{app.touch.delete(key);b.classList.remove('pressed');requestInput();});
}
$('touch-attack').addEventListener('pointerdown',e=>{e.preventDefault();app.attackQueued=true;requestInput(true);});
$('touch-special').addEventListener('pointerdown',e=>{e.preventDefault();app.specialQueued=true;requestInput(true);});
$('touch-defend').addEventListener('pointerdown',e=>{e.preventDefault();app.defendQueued=true;requestInput(true);});
 // Solo emitir controles al cambiar de direccion, al usar Espacio/Q/E o cada 250 ms
 // si se mantiene el movimiento. Las acciones tienen prioridad y no esperan a
 // una peticion de movimiento lenta. seq protege frente a llegadas desordenadas.
 function requestInput(priority=false){
   if(app.scene!=='game'||!app.session)return;
   const s=new Set([...app.pressed,...app.touch]);
   const dx=Number(s.has('right'))-Number(s.has('left'));
   const dy=Number(s.has('down'))-Number(s.has('up'));
   const attack=app.attackQueued,special_attack=app.specialQueued,defend=app.defendQueued;
   const action=attack||special_attack||defend;
   const now=Date.now(), changed=dx!==app.lastMove.dx||dy!==app.lastMove.dy;
   if(!changed&&!action&&(!(dx||dy)||now-app.lastMove.at<250))return;
   if(app.inputBusy&&!priority&&!action)return;
   app.attackQueued=app.specialQueued=app.defendQueued=false;
   app.lastMove={dx,dy,at:now};
   const seq=app.inputSeq=Math.max(app.inputSeq+1,Date.now()*1000);
   if(!action)app.inputBusy=true;
   send({type:'input',seq,dx,dy,attack,special_attack,defend}).finally(()=>{
     if(!action){app.inputBusy=false;requestInput();}
   });
 }
 setInterval(()=>requestInput(),50);
setInterval(()=>{if(app.scene==='ranking')refreshRanking();},15000);
// Pixel-art graphics. Draws a deterministic, cached map; game positions come from Python.
const PALETTES={
  1:{base:'#386648',alt:'#426f51',wall:'#303849',seam:'#222c3d',rock:'#667c67',grass:'#7aa86c',bright:'#a2d17a',accent:'#8abe8d'},
  2:{base:'#477789',alt:'#518c9d',wall:'#334859',seam:'#263c4e',rock:'#81afc0',grass:'#a7dfe7',bright:'#d9f5ec',accent:'#63b9d0'},
  3:{base:'#714c49',alt:'#81534b',wall:'#432f40',seam:'#332838',rock:'#b3674f',grass:'#d88458',bright:'#ffbd6b',accent:'#f28d59'},
  pvp:{base:'#57566d',alt:'#626078',wall:'#343447',seam:'#292938',rock:'#8f819c',grass:'#a794ad',bright:'#cabae0',accent:'#9286b4'}
};
function rand(x,y,salt){let v=((x+1)*1274126177)^((y+3)*1656670031)^((salt+5)*97531);v=Math.imul(v^(v>>>16),2246822519);return ((v^(v>>>13))>>>0)/4294967295;}
function drawTile(g,x,y,cell,colors,salt){
  const xx=x*TILE,yy=y*TILE;g.fillStyle=rand(x,y,salt)>.77?colors.alt:colors.base;g.fillRect(xx,yy,TILE,TILE);
  if(cell==='#'){
    g.fillStyle=colors.wall;g.fillRect(xx,yy,TILE,TILE);
    g.fillStyle=colors.seam;g.fillRect(xx,yy+28,32,4);g.fillRect(xx+((y%2)*13),yy+3,3,19);
    g.fillStyle=colors.rock;g.fillRect(xx+3,yy+3,20,3);g.fillRect(xx+20,yy+10,9,2);
    if(rand(x,y,3)>.66){g.fillStyle=colors.bright;g.fillRect(xx+11,yy+7,3,2);}return;
  }
  if(rand(x,y,salt+1)>.28){
    g.fillStyle=colors.grass;
    g.fillRect(xx+6+(x*3%5),yy+8,4,3);g.fillRect(xx+20,yy+22,4,2);
  }
  if(rand(x,y,salt+5)>.76){
    g.fillStyle=colors.bright;g.fillRect(xx+12,yy+17,2,2);g.fillRect(xx+17,yy+14,3,2);
  }
  if(cell==='X'){
    g.fillStyle=colors.seam;g.fillRect(xx+1,yy+10,28,19);
    g.fillStyle=colors.rock;g.fillRect(xx+3,yy+7,25,17);g.fillRect(xx+7,yy+4,17,6);
    g.fillStyle=colors.bright;g.fillRect(xx+9,yy+7,12,4);
    g.fillStyle=colors.wall;g.fillRect(xx+19,yy+15,8,8);g.fillRect(xx+5,yy+22,13,4);
  }
  if(salt===3&&rand(x,y,salt+13)>.91&&cell==='.'){
    g.fillStyle='#d9582f';g.fillRect(xx+5,yy+23,19,4);g.fillStyle='#ffb64f';g.fillRect(xx+9,yy+24,8,2);
  }
}
function tileCache(state){
  const key=state.mode+'-'+state.floor+'-'+state.map.join('');
  if(key===app.floorKey&&app.tileCanvas)return;
  app.floorKey=key;app.view.clear();app.positionHistory.clear();app.minimapBase=null;app.animations.clear();app.previousHP.clear();app.specialEffects=[];app.effectSeq.clear();app.particles=[];app.worldProps=[];
  const layer=document.createElement('canvas');layer.width=W;layer.height=H;
  const g=layer.getContext('2d');g.imageSmoothingEnabled=false;
  const p=PALETTES[state.mode==='pvp'?'pvp':state.floor]||PALETTES[1];
  for(let y=0;y<state.map.length;y++)for(let x=0;x<state.map[y].length;x++)drawTile(g,x,y,state.map[y][x],p,state.floor);
  // Decoraciones se pintan sobre la capa y no modifican la cuadrícula de colisiones.
  const visual=state.mode==='pvp'?'arena':state.floor===1?'forest':state.floor===2?'ice':'fire';
  const deco=app.images['terrain_'+visual];
  for(let y=1;y<state.map.length-1;y++)for(let x=1;x<state.map[y].length-1;x++){
    const cell=state.map[y][x],px=x*TILE,py=y*TILE;
    if(cell==='X' && deco?.complete && deco.naturalWidth){
      // Props con oclusión real: se ordenan según la profundidad de su base.
      if(visual!=='forest'||rand(x,y,8)>.3)app.worldProps.push({x:px-16,y:py-40,foot:py+32,img:deco});
    } else if(cell==='.' && rand(x,y,57)>.935){
      // Pequeños detalles del suelo, no obstáculos de juego.
      if(visual==='forest'){
        g.fillStyle='#1e523e';g.fillRect(px+9,py+15,13,3);g.fillRect(px+12,py+12,2,7);g.fillRect(px+19,py+11,2,7);
        if(rand(x,y,60)>.5){g.fillStyle='#edc4a3';g.fillRect(px+11,py+8,5,3);g.fillStyle='#f8dc88';g.fillRect(px+13,py+7,2,2);}
      }else if(visual==='ice'){
        g.fillStyle='#a9e2ec';g.fillRect(px+11,py+14,12,3);g.fillRect(px+14,py+10,5,4);g.fillStyle='#e1fcfd';g.fillRect(px+15,py+9,3,3);
      }else if(visual==='fire'){
        g.fillStyle='#2f2735';g.fillRect(px+5,py+16,18,4);g.fillStyle='#c95435';g.fillRect(px+14,py+15,8,2);g.fillStyle='#ffb562';g.fillRect(px+18,py+16,3,2);
      }else{
        g.fillStyle='#baa1b5';g.fillRect(px+10,py+10,8,2);g.fillRect(px+15,py+13,3,6);
      }
    }
  }
  // Acentos decorativos sin colision en los bordes.
  for(const x of [4,10,17,23]){
    g.fillStyle='#2b2029';g.fillRect(x*32+11,11,10,22);
    g.fillStyle='#e78236';g.fillRect(x*32+10,13,12,10);
    g.fillStyle='#ffe28c';g.fillRect(x*32+14,15,5,8);
  }
  app.tileCanvas=layer;
}
// Visual interpolation and prediction never change the server-authoritative
// coordinates, collisions, HP, scores or combat rules.
const ACTOR_SPEED=145, REMOTE_DELAY_MS=105, MAX_REMOTE_EXTRAP_MS=65;
function recordPositions(state){
  const t=performance.now();
  const seen=new Set();
  for(const [prefix,list] of [['p',state.players],['e',state.enemies]])for(const ob of list){
    const key=prefix+(prefix==='p'?ob.key:ob.id);seen.add(key);
    const latest={x:ob.x,y:ob.y,t};
    const history=app.positionHistory.get(key);
    // Reset immediately on teleport, respawn or a new level.
    if(!history||Math.hypot(ob.x-history.latest.x,ob.y-history.latest.y)>100){
      app.positionHistory.set(key,{prev:latest,latest});app.view.delete(key);
    }else app.positionHistory.set(key,{prev:history.latest,latest});
  }
  for(const key of app.positionHistory.keys())if(!seen.has(key))app.positionHistory.delete(key);
}
function solidAt(map,x,y,radius=10){
  if(!map)return false;
  for(const px of [x-radius,x+radius])for(const py of [y-radius,y+radius]){
    const tx=Math.floor(px/TILE),ty=Math.floor(py/TILE);
    if(ty<0||ty>=map.length||tx<0||tx>=map[0].length||'#X'.includes(map[ty][tx]))return true;
  }
  return false;
}
function moveVisual(pos,dx,dy,map){
  // Match the server's axis-wise solid() rule; split long moves to avoid
  // crossing a narrow wall on a low frame-rate phone.
  const steps=Math.max(1,Math.ceil(Math.hypot(dx,dy)/8));
  for(let i=0;i<steps;i++){
    const sx=dx/steps,sy=dy/steps;
    if(!solidAt(map,pos.x+sx,pos.y))pos.x+=sx;
    if(!solidAt(map,pos.x,pos.y+sy))pos.y+=sy;
  }
  return pos;
}
function smoothPosition(id,x,y,dt,isLocal=false){
  const h=app.positionHistory.get(id),now=performance.now();
  if(!h){const direct={x,y};app.view.set(id,direct);return direct;}
  let p=app.view.get(id);
  if(!p||Math.hypot(p.x-x,p.y-y)>100){p={x,y};app.view.set(id,p);}
  if(isLocal){
    const s=new Set([...app.pressed,...app.touch]);
    let dx=Number(s.has('right'))-Number(s.has('left'));
    let dy=Number(s.has('down'))-Number(s.has('up'));
    if(app.state?.players.find(o=>o.key===app.key)?.paralyzed)dx=dy=0;
    const mag=Math.hypot(dx,dy);if(mag>0){dx/=mag;dy/=mag;}
    const freshness=now-h.latest.t;
    // Local rendering reacts on this frame; stop predicting on stale network.
    const beforeX=p.x,beforeY=p.y;
    if(freshness<420&&mag>0)moveVisual(p,dx*ACTOR_SPEED*dt,dy*ACTOR_SPEED*dt,app.state.map);
    p.predictedMoving=mag>0&&freshness<420&&Math.hypot(p.x-beforeX,p.y-beforeY)>.05;
    p.predictedFace=mag>0?(Math.abs(dx)>Math.abs(dy)?(dx>0?'right':'left'):(dy>0?'down':'up')):null;
    const lead=Math.max(0,Math.min(.19,Math.min(180,freshness)/1000+app.rttMs/2000));
    const projected=moveVisual({x,y},dx*ACTOR_SPEED*lead,dy*ACTOR_SPEED*lead,app.state.map);
    const error=Math.hypot(projected.x-p.x,projected.y-p.y);
    if(error>80){p.x=projected.x;p.y=projected.y;}
    else{const alpha=1-Math.exp(-dt*7);p.x+=(projected.x-p.x)*alpha;p.y+=(projected.y-p.y)*alpha;}
  }else{
    // Show remote actors slightly in the past, interpolating actual states,
    // rather than chasing snapshot destinations and stopping every 100 ms.
    const a=h.prev,b=h.latest,duration=b.t-a.t;
    const renderT=now-REMOTE_DELAY_MS;
    let tx=b.x,ty=b.y;
    if(duration>1&&renderT<b.t){
      const u=Math.max(0,Math.min(1,(renderT-a.t)/duration));
      tx=a.x+(b.x-a.x)*u;ty=a.y+(b.y-a.y)*u;
    }else if(duration>1 && now-b.t<180){
      const extra=Math.min(MAX_REMOTE_EXTRAP_MS,Math.max(0,renderT-b.t));
      const speedLimit=id.startsWith('p')?145:90;
      const vx=Math.max(-speedLimit,Math.min(speedLimit,(b.x-a.x)*1000/duration));
      const vy=Math.max(-speedLimit,Math.min(speedLimit,(b.y-a.y)*1000/duration));
      tx+=vx*extra/1000;ty+=vy*extra/1000;
    }
    p.x=tx;p.y=ty;
  }
  return p;
}
const SCARF_COLORS={rojo:'#f66e77',azul:'#69b9f3',verde:'#82e79c',naranja:'#ffae63'};
function playerColor(index,color){return SCARF_COLORS[color]||Object.values(SCARF_COLORS)[index%4];}
function healthBar(x,y,ratio,maxWidth,boss=false){
  const width=Math.min(1,Math.max(0,ratio))*maxWidth;
  ctx.fillStyle='#1b1925';ctx.fillRect(Math.round(x-maxWidth/2)-2,Math.round(y)-2,maxWidth+4,8);
  ctx.fillStyle=boss?'#f7a270':'#ec777b';ctx.fillRect(Math.round(x-maxWidth/2),Math.round(y),Math.round(width),4);
}
// Animación en 4 direcciones, ejecutada a 60 fps e independiente de la tasa HTTP.
// El servidor comunica cambios de estado; nunca se inventan daños desde el cliente.
const PLAYER_ANIMS=['idle','walk','attack','special','block','hurt','dead'];
const FACES={down:0,left:1,right:2,up:3};
function animatedPose(id,obj,isPlayer,t){
  let a=app.animations.get(id);
  if(!a){a={state:'idle',since:t,attackSeq:obj.attack_seq||0,specialSeq:obj.special_seq||0,
    blockSeq:obj.block_seq||0,hurtSeq:obj.hurt_seq||0,action:'',actionUntil:0};app.animations.set(id,a);}
  const sequences=[['special_seq','specialSeq','special',.36],['attack_seq','attackSeq','attack',.25],
                   ['hurt_seq','hurtSeq','hurt',.18],['block_seq','blockSeq','block',.18]];
  for(const [remote,local,action,seconds] of sequences){
    if((obj[remote]||0)!==a[local]){
      a[local]=obj[remote]||0;
      if(action!=='block'||obj.blocking){a.action=action;a.actionUntil=t+seconds;}
      if(isPlayer&&obj.key===app.key){
        if(action==='hurt'){app.shake=Math.max(app.shake,5);sfx('hurt');}
        else if(action==='block')sfx('guard');
        else sfx(action);
      }
    }
  }
  let current=isPlayer?(obj.hp<=0?'dead':obj.blocking?'block':obj.special_fx?'special':obj.swing?'attack':obj.hurt?'hurt':obj.moving?'walk':'idle'):
                       (obj.hurt?'hurt':obj.attacking?'attack':obj.moving?'walk':'idle');
  if(a.actionUntil>t && current!=='dead' && current!=='block')current=a.action;
  if(current!==a.state){a.state=current;a.since=t;}
  const elapsed=Math.max(0,t-a.since);
  let frame=0;
  if(current==='walk')frame=Math.floor(elapsed*(isPlayer?9:8))%4;
  else if(current==='idle')frame=Math.floor(elapsed*(isPlayer?2.3:3.2))%4;
  else if(current==='attack'||current==='special')frame=Math.min(3,Math.floor(elapsed*15));
  else if(current==='hurt')frame=Math.min(3,Math.floor(elapsed*17));
  else if(current==='block')frame=Math.floor(elapsed*6)%4;
  else if(current==='dead')frame=2;
  // Duende y esqueleto: 16 filas = (quieto, caminar, atacar, daño) x 4 orientaciones.
  const extended=!isPlayer&&(obj.kind==='goblin'||obj.kind==='skeleton');
  const enemyState=['idle','walk','attack','hurt'].indexOf(current);
  return {state:current,frame,row:isPlayer?PLAYER_ANIMS.indexOf(current)*4+(FACES[obj.face]??0):
    extended?Math.max(0,enemyState)*4+(FACES[obj.face]??0):
    current==='hurt'||current==='attack'?2:current==='walk'?1:0};
}
function spawnParticles(x,y,col,count=6,life=.48){
  if(app.particles.length>110)return;
  for(let i=0;i<count;i++){
    const ang=(Math.PI*2*i)/count+Math.sin(i*17)*.35;
    const sp=25+(i%4)*17;
    app.particles.push({x,y,vx:Math.cos(ang)*sp,vy:Math.sin(ang)*sp-18,life,max:life,color:col,size:i%3===0?4:3});
  }
}
function processCombatFeedback(snapshot){
  if(!snapshot?.players||!snapshot?.enemies)return;
  const next=new Map();
  for(const [kind,arr] of [['player',snapshot.players],['enemy',snapshot.enemies]]){
    for(const ob of arr){
      const id=(kind==='player'?'p'+ob.key:'e'+ob.id),hp=ob.hp;
      next.set(id,hp);
      const old=app.previousHP.get(id);
      if(old!==undefined&&old>hp&&app.state?.code===snapshot.code){
        const damage=old-hp;
        app.particles.push({x:ob.x,y:ob.y-38,vx:0,vy:-23,life:.64,max:.64,
          text:'-'+damage,color:kind==='player'?'#ff8b91':'#fff0a9'});
        spawnParticles(ob.x,ob.y-10,kind==='player'?'#ff8f84':'#ffe7ac',Math.min(9,3+Math.floor(damage/9)));
        if(hp===0)sfx('kill');
      }
      if(kind==='player'){
        const sequence=ob.special_seq||0;
        const prior=app.effectSeq.get(id);
        // La secuencia procede del servidor; ver el mismo snapshot varias veces no duplica VFX.
        if(prior!==undefined && sequence>prior && ob.special){
          app.specialEffects.push({name:ob.special,x:ob.x,y:ob.y,face:ob.face||'right',age:0,duration:.67});
          const color={brutal:'#ff7856',distancia:'#7fddff',veneno:'#8cec5d',paralisis:'#be9bff'}[ob.special]||'#ffe5a6';
          spawnParticles(ob.x,ob.y-16,color,12,.60);
        }
        app.effectSeq.set(id,sequence);
      }
    }
  }
  app.previousHP=next;
}
function drawEntity(entry,step,t){
  const {kind,obj,index}=entry;
  const id=kind==='enemy'?'e'+obj.id:'p'+obj.key;
  const pos=smoothPosition(id,obj.x,obj.y,step,kind==='player'&&obj.key===app.key),x=Math.round(pos.x),y=Math.round(pos.y);
  const isPlayer=kind==='player';const boss=!isPlayer&&obj.kind==='boss';
  const name=isPlayer?'knight_'+(obj.color||'rojo'):obj.kind;
  const sheet=app.images[name+'_sheet'];
  const legacy=app.images[!isPlayer?obj.kind:name];
  const visualObj=isPlayer&&obj.key===app.key ?
    {...obj,moving:pos.predictedMoving??obj.moving,face:pos.predictedFace||obj.face}:obj;
  const pose=animatedPose(id,visualObj,isPlayer,t);
  ctx.fillStyle='rgba(7,12,21,.44)';ctx.beginPath();ctx.ellipse(x,y+12,boss?26:18,6,0,0,Math.PI*2);ctx.fill();
  if(isPlayer){
    ctx.fillStyle=playerColor(index,obj.color);ctx.fillRect(x-22,y+13,44,3);
    if(obj.key===app.key){ctx.strokeStyle='#f5d879a6';ctx.lineWidth=2;ctx.strokeRect(x-26,y-33,52,53);}
  }
  let size=isPlayer?65:boss?83:obj.kind==='bat'?57:54;
  const drawX=x-size/2,drawY=y-size*.72;
  ctx.save();
  if(isPlayer&&obj.invuln&&Math.floor(t*9)%2)ctx.globalAlpha=.45;
  if(sheet?.complete&&sheet.naturalWidth && (isPlayer?sheet.naturalWidth>=192&&sheet.naturalHeight>=1344:
        (obj.kind==='goblin'||obj.kind==='skeleton')?sheet.naturalWidth>=160&&sheet.naturalHeight>=640:sheet.naturalWidth>=160&&sheet.naturalHeight>=120)){
    const cell=isPlayer?48:40;
    ctx.drawImage(sheet,pose.frame*cell,pose.row*cell,cell,cell,Math.round(drawX),Math.round(drawY),size,size);
  } else if(legacy?.complete&&legacy.naturalWidth){
    ctx.drawImage(legacy,Math.round(drawX),Math.round(drawY),size,size);
  } else {ctx.fillStyle=isPlayer?'#72c9e9':'#ed8a61';ctx.fillRect(x-13,y-15,26,28);}
  ctx.restore();
  if(isPlayer){
    if(obj.blocking){
      const pulse=.70+.18*Math.sin(t*13);
      ctx.strokeStyle='rgba(134,229,255,'+pulse+')';ctx.lineWidth=3;
      ctx.beginPath();ctx.arc(x,y-7,31,Math.PI*1.12,Math.PI*2.8);ctx.stroke();
      // Pixel shards rotate around the shield for the full two-second guard.
      for(let k=0;k<8;k++){
        const ang=t*1.75+k*Math.PI/4;
        const px=Math.round(x+Math.cos(ang)*32),py=Math.round(y-7+Math.sin(ang)*31);
        ctx.fillStyle=k%2?'#8fe5ff':'#e7fcff';ctx.fillRect(px-2,py-2,5,5);
        ctx.fillStyle='#4898c5';ctx.fillRect(px,py,2,2);
      }
      ctx.strokeStyle='#e1f9ff88';ctx.lineWidth=1;ctx.strokeRect(x-27,y-37,54,63);
    }
    if(obj.paralyzed){ctx.fillStyle='#c6e4ff';ctx.font='bold 17px monospace';ctx.textAlign='center';ctx.fillText('✧',x,y-53);}
    if(obj.poisoned){ctx.fillStyle='#a8f88a';ctx.fillRect(x-9,y-53,18,4);}
    if(obj.special_fx){
      const color=({brutal:'#ff8769',distancia:'#86eaff',veneno:'#a2fa78',paralisis:'#cbafff'})[obj.special_fx]||'#ffdd9a';
      ctx.strokeStyle=color;ctx.lineWidth=4;ctx.beginPath();ctx.arc(x,y-8,37+3*Math.sin(t*16),0,Math.PI*2);ctx.stroke();
      for(let k=0;k<6;k++){const an=t*4+k*Math.PI/3;ctx.fillStyle=color;ctx.fillRect(Math.round(x+Math.cos(an)*36),Math.round(y-8+Math.sin(an)*33),4,4);}
    }
    if(obj.swing){
      ctx.strokeStyle='#ffdfa4';ctx.lineWidth=5;ctx.beginPath();
      const a=obj.face==='left'?Math.PI:obj.face==='up'?-Math.PI/2:obj.face==='down'?Math.PI/2:0;
      ctx.arc(x,y-9,43,a-.6,a+.8);ctx.stroke();
    }
    ctx.textAlign='center';ctx.font='bold 12px monospace';ctx.fillStyle='#101622';ctx.fillText(obj.name.slice(0,13),x+1,y-50);
    ctx.fillStyle=playerColor(index,obj.color);ctx.fillText(obj.name.slice(0,13),x,y-52);
    healthBar(x,y-44,obj.hp/100,38);
  }else{
    if(obj.paralyzed){
      ctx.strokeStyle='#cc9bff';ctx.lineWidth=3;
      ctx.beginPath();ctx.ellipse(x,y-8,24+Math.sin(t*10)*3,26,0,0,Math.PI*2);ctx.stroke();
      for(let k=0;k<3;k++){const a=t*4+k*Math.PI*2/3;
        ctx.fillStyle='#ecd4ff';ctx.fillRect(x+Math.cos(a)*22,y-8+Math.sin(a)*22,4,5);}
    }
    if(obj.poisoned){
      ctx.fillStyle='#86e76d';
      for(let k=0;k<5;k++){const q=(t*.65+k*.23)%1;
        const px=Math.round(x+Math.sin(k*2.3)*18),py=Math.round(y+8-q*56);
        ctx.globalAlpha=.8-q*.5;ctx.fillRect(px,py,4+(k%2)*2,4+(k%2)*2);}
      ctx.globalAlpha=1;
    }
    if(obj.hp<obj.max_hp)healthBar(x,y-(boss?57:42),obj.hp/obj.max_hp,boss?66:36,boss);
  }
}
// Efectos únicos para Q: atlas 8 x 96 px, dirección confirmada por el servidor.
// Son visuales: el daño, alcance y estados alterados se calculan únicamente en Python.
function drawSpecialEffects(dt){
  for(let i=app.specialEffects.length-1;i>=0;i--){
    const fx=app.specialEffects[i];fx.age+=dt;
    if(fx.age>=fx.duration){app.specialEffects.splice(i,1);continue;}
    const sheet=app.images['fx_'+fx.name+'_sheet'];
    if(!sheet?.complete||sheet.naturalWidth<768)continue;
    const f=Math.min(7,Math.floor(fx.age/fx.duration*8));
    const facing=fx.face||'right';
    const axis={right:[1,0,0],left:[-1,0,Math.PI],down:[0,1,Math.PI/2],up:[0,-1,-Math.PI/2]}[facing]||[1,0,0];
    const range=fx.name==='distancia'?68:fx.name==='brutal'?38:30;
    const x=fx.x+axis[0]*range,y=fx.y-9+axis[1]*range;
    const size=fx.name==='distancia'?150:fx.name==='brutal'?124:118;
    ctx.save();ctx.translate(Math.round(x),Math.round(y));ctx.rotate(axis[2]);
    ctx.globalAlpha=Math.min(1,(fx.duration-fx.age)/.19);
    ctx.drawImage(sheet,f*96,0,96,96,-size/2,-size/2,size,size);
    ctx.restore();
  }
}
function drawParticles(dt){
  for(let i=app.particles.length-1;i>=0;i--){
    const p=app.particles[i];p.life-=dt;
    if(p.life<=0){app.particles.splice(i,1);continue;}
    p.x+=p.vx*dt;p.y+=p.vy*dt;p.vy+=(p.text?4:48)*dt;
    ctx.globalAlpha=Math.max(.05,p.life/p.max);
    if(p.text){ctx.textAlign='center';ctx.font='bold 18px monospace';ctx.fillStyle='#19212e';ctx.fillText(p.text,Math.round(p.x)+1,Math.round(p.y)+1);ctx.fillStyle=p.color;ctx.fillText(p.text,Math.round(p.x),Math.round(p.y));}
    else{ctx.fillStyle=p.color;ctx.fillRect(Math.round(p.x),Math.round(p.y),p.size,p.size);}
  }
  ctx.globalAlpha=1;
}
function paint(step,time){
  if(app.scene!=='game'||!app.state)return;
  const state=app.state;
  tileCache(state);
  ctx.imageSmoothingEnabled=false;ctx.clearRect(0,0,W,H);
  ctx.save();
  const zoom=app.cameraZoom;
  const mine=state.players.find(p=>p.key===app.key) || state.players[0];
  const visualMe=app.view.get('p'+app.key);
  const cameraX=Math.max(0,Math.min(W-W/zoom,(visualMe?.x??mine?.x??W/2)-W/zoom/2));
  const cameraY=Math.max(0,Math.min(H-H/zoom,(visualMe?.y??mine?.y??H/2)-H/zoom/2));
  ctx.scale(zoom,zoom);ctx.translate(-cameraX,-cameraY);
  if(app.shake>0){const mag=Math.ceil(app.shake);ctx.translate(Math.round(Math.sin(time*92)*mag),Math.round(Math.cos(time*67)*mag));app.shake=Math.max(0,app.shake-step*23);}
  ctx.drawImage(app.tileCanvas,0,0);
  // Ambientes animados (luces / partículas flotantes), sin alterar la simulación.
  for(let i=0;i<22;i++){
    const x=((i*59+Math.sin(time*.45+i)*15+W*2)%W)|0;
    const y=((i*93+time*(4+i%4))%H)|0;
    ctx.fillStyle=state.floor===3&&state.mode==='coop'?'#ffa65b66':state.floor===2?'#b1eefd77':'#d0f5a75d';
    ctx.fillRect(x,y,3,3);
  }
  const entries=[];
  state.enemies.forEach(e=>entries.push({kind:'enemy',obj:e,index:0}));
  state.players.forEach((p,i)=>entries.push({kind:'player',obj:p,index:i}));
  for(const p of app.worldProps)entries.push({kind:'prop',obj:p,index:0});
  entries.sort((a,b)=>(a.kind==='prop'?a.obj.foot:a.obj.y)-(b.kind==='prop'?b.obj.foot:b.obj.y));
  const present=new Set();
  for(const ent of entries){
    if(ent.kind==='prop'){
      if(ent.obj.img?.complete&&ent.obj.img.naturalWidth)ctx.drawImage(ent.obj.img,ent.obj.x,ent.obj.y,64,72);
    }else{
      present.add(ent.kind==='enemy'?'e'+ent.obj.id:'p'+ent.obj.key);drawEntity(ent,step,time);
    }
  }
  for(const key of app.view.keys())if(!present.has(key)){app.view.delete(key);app.animations.delete(key);app.effectSeq.delete(key);}
  drawSpecialEffects(step);drawParticles(step);
  ctx.restore();
  if(state.transition>0){ctx.fillStyle='#101421b7';ctx.fillRect(260,498,376,43);ctx.font='bold 18px monospace';ctx.textAlign='center';ctx.fillStyle='#ffe19d';ctx.fillText('SIGUIENTE PISO: '+state.transition+'s',W/2,525);}
  if(Date.now()-app.lastState>3800){ctx.fillStyle='#101421da';ctx.fillRect(196,248,504,85);ctx.font='bold 18px monospace';ctx.textAlign='center';ctx.fillStyle='#ffcf84';ctx.fillText('RECONEXIÓN / ESPERANDO AL SERVIDOR',W/2,296);}
}
function animate(now){
  const dt=Math.min(.07,(now-app.lastFrame)/1000||.016);app.lastFrame=now;
  app.perfFrames++;
  if(now-app.perfSampleAt>=1000){
    app.fps=Math.round(app.perfFrames*1000/(now-app.perfSampleAt));
    app.perfFrames=0;app.perfSampleAt=now;
    if(app.netIndicator)app.netIndicator.textContent='RED ~'+Math.round(app.rttMs)+' ms · '+app.fps+' FPS';
  }
  paint(dt,now/1000);requestAnimationFrame(animate);
}
requestAnimationFrame(animate);
// Recupera la misma sesion despues de actualizar la pagina (hasta 90s sin actividad).
async function restoreOrConnect(){
  const stored=sessionStorage.getItem('cripta_session');
  if(stored){
    try{
      const data=await fetchJSON('/api/state?session='+encodeURIComponent(stored));
      app.session=stored;app.key=data.key;app.name=data.name||'';setConnected(true);
      if(app.name){
        $('player-tag').textContent='✦ '+app.name.toUpperCase();$('player-tag').hidden=false;
        if(data.room){app.room=data.room;if(data.room.status==='lobby'){renderLobby();scene('lobby');}
          else if(data.game){app.state=data.game;scene('game');updateGameHUD(data.game);}
          else{await send({type:'leave_room'});app.room=null;scene('home');}}
        else{scene('home');}
      }
      return true;
    }catch(e){sessionStorage.removeItem('cripta_session');}
  }
  return connect();
}
restoreOrConnect().then(()=>pollLoop());
