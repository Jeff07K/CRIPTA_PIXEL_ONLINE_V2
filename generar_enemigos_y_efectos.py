"""Crea atlas pixel art originales para esqueleto, duende y cuatro especiales.

Se conserva el tamaño y las paletas de la versión base. Pillow se usa solo para
regenerar recursos (el servidor y el navegador no dependen de Pillow).

Ejecuta: python3 generar_enemigos_y_efectos.py
"""
from PIL import Image, ImageDraw
from pathlib import Path
import math

ROOT=Path(__file__).resolve().parent
AS=ROOT/'assets'
CELL=40
DIRECTIONS=('down','left','right','up')
ENEMY_STATES=('idle','walk','attack','hurt')
OUT='#21252c'
S_BONE='#efe9cb'; S_HL='#fff9db'; S_DARK='#a9a58f'; S_RED='#ef7669'
G_SKIN='#72ba4a'; G_LIGHT='#8bd45c'; G_DARK='#447735'; G_HAIR='#2b4c2e'; G_TUNIC='#906b3f'

def rect(d,x0,y0,x1,y1,c): d.rectangle((round(x0),round(y0),round(x1),round(y1)), fill=c)
def poly(d,pts,c): d.polygon([(round(x),round(y)) for x,y in pts],fill=c)

def bone_weapon(up=0,attack=False,frame=0):
    layer=Image.new('RGBA',(40,40));d=ImageDraw.Draw(layer)
    x=5; y=3+up
    rect(d,x+2,y,x+5,y+29,OUT)
    rect(d,x+3,y+2,x+4,y+25,S_BONE)
    rect(d,x+3,y+1,x+3,y+18,S_HL)
    poly(d,[(x+1,y+3),(x+3,y-1),(x+6,y+3)],'#bcd6df')
    rect(d,x,y+22,x+9,y+25,'#8a684d')
    rect(d,x+1,y+23,x+8,y+23,'#c59b65')
    if attack:
        layer=layer.rotate((0,-38,-82,-35)[frame],Image.Resampling.NEAREST,center=(9,29),expand=False)
    return layer

def goblin_weapon(attack=False,frame=0):
    layer=Image.new('RGBA',(40,40));d=ImageDraw.Draw(layer)
    rect(d,5,13,9,32,OUT);rect(d,6,13,8,32,'#845133')
    poly(d,[(3,12),(3,8),(6,5),(10,7),(13,10),(13,16),(10,19),(5,18)],OUT)
    poly(d,[(4,12),(5,9),(8,7),(11,10),(11,15),(8,17),(4,15)],'#7a5543')
    rect(d,5,10,7,11,'#b4ab85');rect(d,10,13,10,15,'#d5c3a1')
    if attack:layer=layer.rotate((0,-35,-77,-39)[frame],Image.Resampling.NEAREST,center=(8,30),expand=False)
    return layer

def skeleton_frame(direction,state,f):
    a=Image.new('RGBA',(CELL,CELL));d=ImageDraw.Draw(a)
    walking=state=='walk'; attacking=state=='attack'; hurt=state=='hurt'
    stride=(-3,0,3,0)[f] if walking else (0,0,0,0)[f]
    bob=(-1,0,-1,1)[f] if walking else (0,0,-1,0)[f] if state=='idle' else 0
    if hurt:bob=(0,1,2,0)[f]
    # Pies y rodillas articulados (dos poses opuestas, no escala de imagen).
    for i,x in enumerate((13,24)):
        dx=stride if i==0 else -stride
        yp=30+(2 if (dx>0 and walking) else -1 if (dx<0 and walking) else 0)
        rect(d,x+dx,yp,x+dx+6,37,OUT)
        rect(d,x+dx+1,yp+1,x+dx+5,35,S_DARK)
        rect(d,x+dx-1,36,x+dx+7,38,OUT)
        rect(d,x+dx,36,x+dx+6,37,S_BONE)
    # Arma detrás del cuerpo, sube al atacar.
    w=bone_weapon((-1 if walking and f in (0,2) else 0),attacking,f)
    a.alpha_composite(w)
    d=ImageDraw.Draw(a)
    # Columna torácica con costillas (frente) o sombras (espalda)
    rect(d,12,18+bob,30,32+bob,OUT)
    rect(d,13,19+bob,29,29+bob,S_DARK)
    if direction!='up':
        for yy in (20,24,28):
            rect(d,13,yy+bob,28,yy+bob+1,S_BONE)
            rect(d,17,yy+1+bob,24,yy+1+bob,OUT)
        rect(d,19,19+bob,21,29+bob,S_BONE)
    else:
        rect(d,15,21+bob,26,26+bob,S_BONE)
        rect(d,17,27+bob,23,29+bob,'#817f73')
    # Hombros al contra-movimiento con piernas
    arm=(-stride//3 if walking else 0)
    rect(d,10+arm,20+bob,13+arm,31+bob,OUT)
    rect(d,11+arm,21+bob,12+arm,30+bob,S_BONE)
    rect(d,29-arm,21+bob,32-arm,31+bob,OUT)
    rect(d,30-arm,22+bob,31-arm,30+bob,S_BONE)
    # Cráneo grande fiel a ojos rojos pixel art del original.
    rect(d,12,5+bob,30,21+bob,OUT)
    rect(d,13,7+bob,29,18+bob,S_BONE)
    rect(d,15,5+bob,27,8+bob,S_DARK)
    rect(d,16,7+bob,26,10+bob,S_HL)
    if direction=='up':
        rect(d,13,11+bob,29,18+bob,S_DARK)
        rect(d,16,13+bob,26,14+bob,S_BONE)
    elif direction in ('left','right'):
        rect(d,14,12+bob,20,17+bob,OUT)
        rect(d,16,13+bob,17,14+bob,S_RED)
        rect(d,25,15+bob,29,18+bob,S_DARK)
    else:
        rect(d,16,12+bob,20,17+bob,OUT);rect(d,23,12+bob,27,17+bob,OUT)
        rect(d,17,13+bob,18,14+bob,S_RED);rect(d,24,13+bob,25,14+bob,S_RED)
    rect(d,17,19+bob,26,21+bob,'#8d8a78');rect(d,20,19+bob,23,21+bob,OUT)
    # Escudo de madera/borde metálico en mano libre, con oscilación real.
    sy=25+bob+(1 if walking and f in (1,3) else 0)
    sx=31 if not attacking else 32
    poly(d,[(sx-4,sy-3),(sx+5,sy-3),(sx+7,sy),(sx+6,sy+9),(sx+1,sy+12),(sx-4,sy+8)],OUT)
    poly(d,[(sx-3,sy-2),(sx+4,sy-2),(sx+5,sy),(sx+4,sy+8),(sx+1,sy+10),(sx-3,sy+7)],'#b29d85')
    poly(d,[(sx-1,sy),(sx+3,sy),(sx+3,sy+7),(sx+1,sy+8),(sx-1,sy+6)],'#875d41')
    # Lateral y espalda tienen siluetas diferentes del frente.
    if direction=='left': a=a.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if hurt and f in (1,2):
        over=Image.new('RGBA',(40,40),(255,115,102,86))
        over.putalpha(a.getchannel('A').point(lambda v:int(v*.42)))
        a=Image.alpha_composite(a,over)
    return a

def goblin_frame(direction,state,f):
    a=Image.new('RGBA',(40,40));d=ImageDraw.Draw(a)
    walking=state=='walk';attacking=state=='attack';hurt=state=='hurt'
    stride=(-3,0,3,0)[f] if walking else 0
    bob=(-1,0,-1,1)[f] if walking else (0,0,-1,0)[f] if state=='idle' else 0
    if hurt:bob=(0,2,2,0)[f]
    # Pisada alternada, piernas y sombra de zapato independientes.
    for i,x in enumerate((13,26)):
        dx=stride if i==0 else -stride
        y=31+(2 if walking and dx>0 else -1 if walking and dx<0 else 0)
        rect(d,x+dx,y,x+dx+6,37,OUT)
        rect(d,x+dx+1,y+1,x+dx+5,35,'#3a5630')
        rect(d,x+dx-1,36,x+dx+8,39,OUT)
        rect(d,x+dx,36,x+dx+7,37,G_DARK)
    a.alpha_composite(goblin_weapon(attacking,f))
    d=ImageDraw.Draw(a)
    rect(d,11,23+bob,31,33+bob,OUT)
    rect(d,12,24+bob,30,31+bob,G_TUNIC)
    rect(d,15,24+bob,27,27+bob,'#b8874c')
    rect(d,11,31+bob,31,33+bob,'#334d32')
    # Brazos; oscilan al paso y se elevan al atacar.
    arms=(-stride//2 if walking else -3 if attacking and f==2 else 0)
    rect(d,8+arms,22+bob,13+arms,32+bob,OUT)
    rect(d,9+arms,23+bob,12+arms,30+bob,G_SKIN)
    rect(d,30-arms,22+bob,34-arms,31+bob,OUT)
    rect(d,31-arms,23+bob,33-arms,29+bob,G_DARK)
    # Cabeza y orejas puntiagudas independientes del torso.
    poly(d,[(9,17+bob),(0,12+bob),(0,8+bob),(9,10+bob),(11,4+bob),(18,3+bob),
            (24,3+bob),(31,8+bob),(39,10+bob),(39,14+bob),(31,19+bob),(29,25+bob),(11,25+bob)],OUT)
    poly(d,[(11,14+bob),(2,11+bob),(2,13+bob),(11,19+bob),(13,9+bob),(19,5+bob),
            (25,6+bob),(31,12+bob),(38,12+bob),(30,18+bob),(29,23+bob),(11,23+bob)],G_SKIN)
    poly(d,[(10,11+bob),(13,4+bob),(19,3+bob),(27,5+bob),(32,11+bob)],G_HAIR)
    rect(d,11,14+bob,31,19+bob,G_LIGHT)
    if direction=='up':
        rect(d,11,13+bob,30,23+bob,G_DARK)
        poly(d,[(12,11+bob),(18,7+bob),(25,7+bob),(30,12+bob)],G_HAIR)
    elif direction in ('left','right'):
        rect(d,24,16+bob,29,19+bob,'#f16868')
        rect(d,26,17+bob,28,18+bob,OUT)
        poly(d,[(30,20+bob),(35,19+bob),(31,24+bob)],G_SKIN)
        rect(d,24,23+bob,28,25+bob,OUT)
    else:
        rect(d,14,16+bob,18,19+bob,'#ef7671')
        rect(d,24,16+bob,28,19+bob,'#ef7671')
        rect(d,16,17+bob,17,18+bob,OUT);rect(d,26,17+bob,27,18+bob,OUT)
        rect(d,19,22+bob,24,24+bob,OUT)
        rect(d,20,22+bob,21,25+bob,S_HL);rect(d,23,22+bob,24,24+bob,S_HL)
    if direction=='left':a=a.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if hurt and f in (1,2):
        over=Image.new('RGBA',(40,40),(252,115,92,74));over.putalpha(a.getchannel('A').point(lambda v:int(v*.36)))
        a=Image.alpha_composite(a,over)
    return a

def generate_enemies():
    for name,render in (('skeleton',skeleton_frame),('goblin',goblin_frame)):
        sheet=Image.new('RGBA',(160,640),(0,0,0,0))
        for state_idx,state in enumerate(ENEMY_STATES):
            for dir_idx,direction in enumerate(DIRECTIONS):
                for frame in range(4):
                    cell=render(direction,state,frame)
                    sheet.alpha_composite(cell,(frame*40,(state_idx*4+dir_idx)*40))
        sheet.save(AS/(name+'_sheet.png'),optimize=True)
        sheet.crop((0,0,40,40)).save(AS/(name+'.png'),optimize=True)

def Pimg():return Image.new('RGBA',(96,96),(0,0,0,0))

def line(d,pts,c,width=3):d.line(pts,fill=c,width=width,joint='curve')
def spark(d,x,y,c,l=5):
    line(d,[(x-l,y),(x+l,y)],c,2);line(d,[(x,y-l),(x,y+l)],c,2)
    rect(d,x-1,y-1,x+1,y+1,'#ffffff')

def fx_brutal(f):
    im=Pimg();d=ImageDraw.Draw(im)
    progress=(f+1)/8
    # Dos medias lunas superpuestas para representar el tajo incendiario hacia la derecha.
    w=14+int(progress*18);h=28+int(progress*26)
    bb=[48-w,48-h,48+w,48+h]
    d.arc(bb,start=220-int(progress*25),end=485-int(progress*25),fill='#9d2638',width=9)
    d.arc([bb[0]+2,bb[1]+2,bb[2]-2,bb[3]-2],start=228-int(progress*25),end=478-int(progress*25),fill='#f45143',width=6)
    d.arc([bb[0]+6,bb[1]+6,bb[2]-6,bb[3]-6],start=236-int(progress*25),end=467-int(progress*25),fill='#ffdd84',width=4)
    for k in range(4):
        x=43+int(math.cos(k*2.2+f*.55)*(12+3*f));y=46+int(math.sin(k*2.2+f*.55)*(17+3*f))
        poly(d,[(x,y-7),(x+4,y-2),(x+2,y+3),(x-1,y+5),(x-2,y)],'#ff8c4c')
    if f in (2,3,4):spark(d,66,27,'#ffe6ab',6)
    return im

def fx_distancia(f):
    im=Pimg();d=ImageDraw.Draw(im)
    x=17+min(42,f*7)
    # Proyectil en forma de cometa azul; es una onda VISUAL, el alcance real permanece en servidor.
    d.arc((x-25,18,x+28,79),225,475,fill='#1f6bcb',width=9)
    d.arc((x-22,22,x+25,75),235,462,fill='#65c6ff',width=6)
    d.arc((x-17,27,x+21,70),246,451,fill='#e5fdff',width=3)
    poly(d,[(x+12,43),(x+27,48),(x+11,55),(x+17,49)],'#cef6ff')
    for k in range(3):
        a=18+f*5-k*15
        line(d,[(a,40+k*9),(a-8,40+k*9)],'#3da3f7',2)
    spark(d,min(85,x+31),48,'#bdeaff',3)
    return im

def fx_veneno(f):
    im=Pimg();d=ImageDraw.Draw(im);phase=f/7
    r=13+int(phase*27)
    d.ellipse((48-r,48-r,48+r,48+r),outline='#286d37',width=7)
    d.ellipse((49-r,49-r,47+r,47+r),outline='#8efc60',width=4)
    # Nube tóxica y tres burbujas que crecen y flotan.
    for j in range(4):
        x=34+j*9+int(math.sin(j*3+f*.7)*5)
        y=55-8*(j%2)-int(phase*10)
        rad=8+(j+f)%4
        d.ellipse((x-rad,y-rad,x+rad,y+rad),fill='#3b963f',outline='#a0f45c',width=2)
    # Símbolo de calavera dentro de la nube.
    d.rectangle((41,38,55,50),fill='#b8fe91')
    rect(d,43,43,46,46,'#2b6a35');rect(d,50,43,53,46,'#2b6a35')
    rect(d,46,50,50,54,'#b8fe91')
    for k in range(3):
        ang=(f*1.4+k*2.1)
        cx=48+math.cos(ang)*(16+f*3);cy=46+math.sin(ang)*(16+f*2)
        d.ellipse((cx-3,cy-3,cx+3,cy+3),outline='#c0ff86',width=2)
    return im

def fx_paralisis(f):
    im=Pimg();d=ImageDraw.Draw(im);r=16+min(24,f*4)
    d.ellipse((48-r,48-r,48+r,48+r),outline='#5631a2',width=7)
    d.arc((48-r,48-r,48+r,48+r),-40+f*13,225+f*13,fill='#d88cff',width=4)
    d.arc((48-r+5,48-r+5,48+r-5,48+r-5),90-f*15,280-f*15,fill='#f8d7ff',width=2)
    for j in range(4):
        angle=(math.pi*j/2)+f*.14
        cx=48+math.cos(angle)*r;cy=48+math.sin(angle)*r
        pts=[(cx-3,cy-7),(cx+3,cy-2),(cx-1,cy+1),(cx+4,cy+9)]
        line(d,pts,'#903bdb',5);line(d,pts,'#e4a8ff',2)
    for j in range(3):
        angle=f*.3+j*2.1
        spark(d,48+int(math.cos(angle)*25),48+int(math.sin(angle)*25),'#f3baff',3)
    return im

FX={'brutal':fx_brutal,'distancia':fx_distancia,'veneno':fx_veneno,'paralisis':fx_paralisis}
def generate_fx():
    for name,paint in FX.items():
        sheet=Image.new('RGBA',(96*8,96),(0,0,0,0))
        for f in range(8):sheet.alpha_composite(paint(f),(96*f,0))
        sheet.save(AS/f'fx_{name}_sheet.png',optimize=True)

def make_preview():
    p=Image.new('RGB',(1000,650),'#152034');d=ImageDraw.Draw(p)
    d.text((24,20),'CRIPTA PIXEL V2 / MOVIMIENTO ENEMIGOS + ESPECIALES Q',fill='#f8d392')
    for n,name in enumerate(('goblin','skeleton')):
        sh=Image.open(AS/f'{name}_sheet.png')
        x0=28+n*475
        d.rounded_rectangle((x0,52,x0+455,305),radius=12,fill='#253448',outline='#4b7990',width=2)
        d.text((x0+18,63),name.upper()+' / 4 DIRECCIONES / CAMINAR Y ATACAR',fill='white')
        for row in range(2):
            for frame in range(4):
                index=(4 if row==0 else 8)*40
                cell=sh.crop((frame*40,index,(frame+1)*40,index+40)).resize((84,84),Image.Resampling.NEAREST)
                p.paste(cell,(x0+30+frame*101,86+row*98),cell)
        d.text((x0+20,289),'Arriba: caminar    |    Abajo: atacar',fill='#b6cedd')
    d.text((24,340),'EFECTOS REALES / ATLAS DE 8 FOTOGRAMAS',fill='#f8d392')
    for i,name in enumerate(FX):
        x0=22+i*245
        d.rounded_rectangle((x0,373,x0+226,612),radius=10,fill='#253448',outline='#4b7990',width=2)
        im=Image.open(AS/f'fx_{name}_sheet.png');cell=im.crop((96*5,0,96*6,96))
        cell=cell.resize((162,162),Image.Resampling.NEAREST)
        p.paste(cell,(x0+31,397),cell)
        d.text((x0+22,572),name.upper(),fill='#f9d88c')
    p.save(ROOT/'VISTA_MEJORAS_V2.png',optimize=True)

if __name__=='__main__':
    generate_enemies();generate_fx();make_preview()
    print('Atlas generados: duende, esqueleto (160x640), especiales x4 (768x96).')
