"""Smoke con Chromium + puente HTTP de Python.
Permite probar JS/WebCanvas si Chromium está administrado y bloquea localhost.
No sustituye las pruebas de equipos físicos por Internet.
Deps de desarrollo: playwright, chromium instalados en el equipo de pruebas.
"""
from __future__ import annotations
import base64, json, os, re, sys, tempfile, time
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from server import GameServer
from server_web import BrowserGateway

tmp=tempfile.TemporaryDirectory()
game=GameServer('127.0.0.1',0,str(Path(tmp.name)/'browser.db'))
game.start();gateway=BrowserGateway(game,'127.0.0.1',0);gateway.start()
base=f'http://127.0.0.1:{gateway.port}'
errors=[]
assets={p.stem:'data:image/png;base64,'+base64.b64encode(p.read_bytes()).decode('ascii') for p in (ROOT/'assets').glob('*.png')}
html=(ROOT/'web/index.html').read_text('utf-8')
html=html.replace('<link rel="stylesheet" href="/style.css">','').replace('<script src="/app.js" defer></script>','')
html=re.sub(r'src="/assets/([\w-]+)\.png(?:\?v=[^\"]+)?"',lambda m:'src="'+assets[m[1]]+'"',html)
js=(ROOT/'web/app.js').read_text('utf-8')
js=js.replace("const $ = id =>",'const assetUrls = '+json.dumps(assets)+';\nconst $ = id =>')
js=js.replace("img.src='/assets/'+k+'.png?v=animation-v2';", "img.src=assetUrls[k];")
js=js.replace("im.src='/assets/'+(i<arr.length?'knight_'+(loadouts[i]?.color||['rojo','azul','verde','naranja'][i]):'ghost')+'.png?v=animation7';", "im.src=assetUrls[i<arr.length?'knight_'+(loadouts[i]?.color||['rojo','azul','verde','naranja'][i]):'ghost'];")
css=(ROOT/'web/style.css').read_text('utf-8')

def bridge(source,path,body,method):
    req=Request(base+(path or '/'),data=body.encode() if method=='POST' else None,method=method,
                headers={'Content-Type':'application/json'} if method=='POST' else {})
    try:
        with urlopen(req,timeout=7) as resp:return {'status':resp.status,'ok':True,'data':json.load(resp)}
    except HTTPError as e:return {'status':e.code,'ok':False,'data':json.loads(e.read())}

try:
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
        pages=[]
        for i in range(2):
            ctx=browser.new_context(viewport={'width':1510,'height':1060},device_scale_factor=1)
            p=ctx.new_page();pages.append(p)
            p.on('pageerror',lambda e:errors.append(str(e)))
            p.expose_binding('pythonBridge',bridge)
            p.set_content(html,wait_until='domcontentloaded')
            p.add_style_tag(content=css)
            p.add_script_tag(content="window.fetch=function(path,init={}){return window.pythonBridge(path,init.body||'',init.method||'GET').then(r=>({status:r.status,ok:r.ok,json:async()=>r.data}));};")
            p.add_script_tag(content="Object.defineProperty(window,'sessionStorage',{configurable:true,value:(()=>{const m={};return {getItem:k=>m[k]||null,setItem:(k,v)=>m[k]=String(v),removeItem:k=>delete m[k]};})()});")
            p.add_script_tag(content=js)
            p.locator('#online.connected').wait_for(timeout=12000)
            p.wait_for_timeout(500)
            for suffix in ['knight_rojo_sheet','slime_sheet','goblin_sheet','skeleton_sheet','fx_brutal_sheet','fx_distancia_sheet','fx_veneno_sheet','fx_paralisis_sheet']:
                assert p.evaluate('(k) => app.images[k].complete && app.images[k].naturalWidth>0',suffix), suffix
        one,two=pages
        def signup(page,user):
            page.locator('#username').fill(user)
            page.locator('#password').fill('password1234')
            page.locator('#register-btn').click()
            page.locator('#home:not([hidden])').wait_for(timeout=14000)
        signup(one,'KnightAliceV7');signup(two,'KnightBobV7')
        one.screenshot(path=str(ROOT/'CAPTURA_MENU_REAL.png'),full_page=True)
        one.locator('input[name="special"][value="veneno"]').check()
        one.locator('#create-solo').click()
        one.locator('#game:not([hidden])').wait_for(timeout=13000)
        one.wait_for_timeout(700)
        before=one.locator('#world').screenshot()
        one.keyboard.down('d');one.wait_for_timeout(310)
        assert one.evaluate("app.state.players.find(p=>p.key===app.key).moving")
        one.wait_for_timeout(165)
        after=one.locator('#world').screenshot()
        assert before != after,'Canvas image did not change when moving'
        one.keyboard.up('d')
        one.keyboard.press('q')
        one.wait_for_function("app.specialEffects.some(f=>f.name==='veneno')",timeout=3500)
        assert one.evaluate("app.images['fx_veneno_sheet'].naturalWidth===768")
        one.keyboard.press('e')
        one.wait_for_timeout(200)
        assert 's' in one.locator('#hud-special').inner_text(),one.locator('#hud-special').inner_text()
        one.screenshot(path=str(ROOT/'CAPTURA_PARTIDA_ANIMADA.png'),full_page=True)
        assert one.evaluate("app.images['knight_rojo_sheet'].naturalHeight===1344")
        assert one.evaluate("app.images['goblin_sheet'].naturalHeight===640")
        assert one.evaluate("app.images['skeleton_sheet'].naturalHeight===640")
        assert one.evaluate("(function(){let p={kind:'goblin',face:'up',moving:true,hp:50,attack_seq:0,hurt_seq:0};return animatedPose('probe-goblin',p,false,performance.now()/1000).row===7})()")
        print('SOLO',one.locator('#game-title').inner_text(),one.locator('#hud-special').inner_text(),one.locator('#hud-defense').inner_text())
        one.on('dialog',lambda d:d.accept());one.locator('#leave-game').click()
        one.locator('#home:not([hidden])').wait_for(timeout=15000)
        one.locator('input[name="special"][value="paralisis"]').check()
        one.locator('#create-coop').click();one.locator('#lobby:not([hidden])').wait_for(timeout=12000)
        code=one.locator('#invite-code').inner_text()
        two.locator('input[name="special"][value="distancia"]').check()
        two.locator('#room-code').fill(code);two.locator('#join-room').click()
        two.locator('#lobby:not([hidden])').wait_for(timeout=12000)
        one.wait_for_function('document.querySelector("#party-count").textContent.includes("2 / 4")',timeout=10000)
        one.screenshot(path=str(ROOT/'CAPTURA_SALA_ANIMADA.png'),full_page=True)
        one.locator('#start-game').click()
        for p in (one,two):p.locator('#game:not([hidden])').wait_for(timeout=12000)
        one.wait_for_timeout(600)
        one.screenshot(path=str(ROOT/'CAPTURA_COOPERATIVO_ANIMADO.png'),full_page=True)
        assert one.evaluate('app.state.players.length===2')
        print('COOP',code,[x['name'] for x in one.evaluate('app.state.players')])
        # Los dos navegadores abandonan la expedición y prueban el modo PvP real.
        one.locator('#leave-game').click();one.locator('#home:not([hidden])').wait_for(timeout=15000)
        two.on('dialog',lambda d:d.accept())
        two.wait_for_timeout(400)
        if two.locator('#results').is_visible():two.locator('#results-home').click()
        elif two.locator('#game').is_visible():two.locator('#leave-game').click()
        elif two.locator('#lobby').is_visible():two.locator('#exit-lobby').click()
        two.locator('#home:not([hidden])').wait_for(timeout=12000)
        one.locator('#create-pvp').click();one.locator('#lobby:not([hidden])').wait_for(timeout=12000)
        pvp_code=one.locator('#invite-code').inner_text()
        two.locator('#room-code').fill(pvp_code);two.locator('#join-room').click()
        two.locator('#lobby:not([hidden])').wait_for(timeout=12000)
        one.wait_for_function('document.querySelector("#party-count").textContent.includes("2 / 4")',timeout=10000)
        one.locator('#start-game').click()
        for page in (one,two):page.locator('#game:not([hidden])').wait_for(timeout=12000)
        assert one.evaluate("app.state.mode==='pvp' && app.state.players.length===2")
        two.screenshot(path=str(ROOT/'CAPTURA_PVP_ANIMADO.png'),full_page=True)
        print('PVP',pvp_code,one.locator('#game-title').inner_text())
        assert not errors,errors
        print('CHROMIUM OK: 2 pestañas independientes, Solo + Q/E + movimiento, Coop y PvP, spritesheets cargados, 0 errores JavaScript')
        browser.close()
finally:
    gateway.stop();game.stop();tmp.cleanup()
if errors:raise RuntimeError(errors)
