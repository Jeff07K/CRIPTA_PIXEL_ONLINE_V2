"""Genera spritesheets exactos de 48px a partir del caballero aprobado.
Requiere Pillow solo para regenerar los recursos; NO para ejecutar el juego.
Ejecutar desde la raiz: python3 generar_animaciones.py
"""
from __future__ import annotations
from PIL import Image, ImageDraw
from pathlib import Path
import hashlib, json, math

ROOT=Path(__file__).resolve().parent
AS=ROOT/'assets'
FRAME=48
STATES=('idle','walk','attack','special','block','hurt','dead')
DIRECTIONS=('down','left','right','up')
COLORS={
 'rojo':{'scarf':'#df4352','light':'#fa6470','dark':'#982d42'},
 'azul':{'scarf':'#267cdb','light':'#54a8fb','dark':'#15519f'},
 'verde':{'scarf':'#279e52','light':'#66d47a','dark':'#176f40'},
 'naranja':{'scarf':'#e9791d','light':'#ffac43','dark':'#a94a19'},
}
P={'outline':'#1e2635','shadow':'#292e42','hair':'#432c2e','hair_light':'#714232','hair_mid':'#55372e',
 'skin':'#f4bf92','skin_light':'#ffce9b','skin_shadow':'#bb825e','armor':'#327fb3','armor_light':'#57acd6','armor_dark':'#274a73',
 'pants':'#283a57','boots':'#192638','boot_light':'#394a65','steel':'#d5e8ef','steel_white':'#f4faff','steel_dark':'#6e899d',
 'gold':'#e4a948','gold_light':'#ffe28a'}

def R(d,x0,y0,x1,y1,c): d.rectangle((int(x0),int(y0),int(x1),int(y1)),fill=c)
def poly(d,xy,c): d.polygon([(int(a),int(b)) for a,b in xy],fill=c)

def sword(layer,style,frame,dir):
    d=ImageDraw.Draw(layer)
    # Espada original vertical, con brillo frío. El giro modifica también la empuñadura.
    R(d,37,4,42,26,P['outline']);R(d,38,6,41,23,P['steel_dark']);R(d,38,6,39,23,P['steel_white']);
    poly(d,[(37,6),(40,1),(43,6)],P['outline']);poly(d,[(39,6),(40,2),(41,6)],P['steel_white']);
    R(d,33,24,45,27,P['outline']);R(d,34,24,43,25,P['gold']);R(d,39,27,42,33,P['outline']);R(d,40,27,41,31,P['gold']);
    if style in ('attack','special'):
        angles=(0,35,83,45) if style=='attack' else (0,48,106,73)
        angle=angles[frame]
        layer=layer.rotate(angle, resample=Image.Resampling.NEAREST, center=(40,28),expand=False)
    if dir=='up':
        # espada detrás de la silueta
        pass
    return layer

def shield(img,cx,cy,raised=False):
    d=ImageDraw.Draw(img)
    cx=int(cx);cy=int(cy)
    # Escudo reducido que no oculta rostro y conserva el contorno del sprite original.
    poly(d,[(cx-8,cy-8),(cx+6,cy-8),(cx+8,cy-5),(cx+7,cy+6),(cx+1,cy+11),(cx-6,cy+7),(cx-9,cy+2)],P['outline'])
    poly(d,[(cx-6,cy-7),(cx+5,cy-7),(cx+7,cy-4),(cx+6,cy+5),(cx,cy+9),(cx-5,cy+5),(cx-7,cy+1)],P['gold'])
    poly(d,[(cx-4,cy-5),(cx+3,cy-5),(cx+5,cy-3),(cx+4,cy+4),(cx,cy+7),(cx-4,cy+3)],P['steel_dark'])
    poly(d,[(cx-3,cy-4),(cx+2,cy-4),(cx+3,cy-1),(cx+2,cy+4),(cx-3,cy+2)],P['steel'])
    R(d,cx-3,cy-4,cx-1,cy-2,P['steel_white'])
    if raised:
        R(d,cx-8,cy-9,cx+6,cy-9,P['gold_light'])

def draw_down(src,color,state,frame):
    c=COLORS[color];out=Image.new('RGBA',(48,48));d=ImageDraw.Draw(out)
    active=state=='walk';st=(-3,0,3,0)[frame] if active else 0
    bob=(-1,0,-1,1)[frame] if active else (0,0,-1,0)[frame] if state=='idle' else 0
    if state=='hurt':bob=(0,-1,0,1)[frame]
    if state=='dead':
        base=draw_down(src,color,'idle',0)
        transformed=base.rotate(87,Image.Resampling.NEAREST,expand=False,center=(23,28))
        out.alpha_composite(transformed,(0,7))
        for x in (6,19,34):R(d,x,44,x+6,45,'#39485c')
        return out
    # Polvo sutil detrás de los zapatos; animación pixelada real de pasos alternos.
    if active and frame in (0,2):
        R(d,8 if frame==0 else 32,43,11 if frame==0 else 35,44,'#8da9a188')
    for side in (0,1):
        dx=(st if side==0 else -st)
        x=(10 if side==0 else 25)+dx
        y=(37 if side==0 else 37)+(2 if side==0 and st>0 or side==1 and st<0 else 0)
        R(d,x,y,x+12,y+8,P['outline']);R(d,x+2,y+1,x+10,y+6,P['pants']);
        R(d,x,y+6,x+13,y+9,P['boots']);R(d,x+2,y+6,x+10,y+7,P['boot_light'])
    # Espada trasera y manga.
    sw=sword(Image.new('RGBA',(48,48)),state,frame,'down')
    out.alpha_composite(sw)
    d=ImageDraw.Draw(out)
    # capa y cola de bufanda según marcha.
    tail=(-2,0,2,0)[frame] if active else (0,1,0,-1)[frame]
    poly(d,[(9,25+bob),(14,25+bob),(12+tail,38+bob),(5+tail,39+bob),(5+tail,32+bob)],c['dark'])
    poly(d,[(9,26+bob),(13,28+bob),(10+tail,36+bob),(6+tail,35+bob)],c['scarf'])
    # torso base fiel a las sombras del original, dibujado detrás de la cara.
    R(d,11,26+bob,35,38+bob,P['outline']);R(d,13,26+bob,33,36+bob,P['armor']);
    R(d,14,27+bob,25,31+bob,P['armor_light']);R(d,24,31+bob,31,37+bob,P['armor_dark']);
    R(d,11,36+bob,35,39+bob,P['shadow']);R(d,14,37+bob,32,38+bob,P['pants']);
    # brazo izq sigue la cadencia de las piernas.
    lx=4+(-st//2 if active else 0)
    R(d,lx,25+bob,lx+7,34+bob,P['outline']);R(d,lx+1,26+bob,lx+5,31+bob,P['skin_shadow']);R(d,lx+2,26+bob,lx+5,29+bob,P['skin']);
    # Cuello y bufanda frontal.
    R(d,8,23+bob,36,29+bob,c['dark']);R(d,10,23+bob,34,26+bob,c['scarf']);
    R(d,18,24+bob,31,25+bob,c['light']);R(d,25,26+bob,28,32+bob,c['scarf']);
    # Cabeza es la original recortada (pixel por pixel) para conservar rostro y cabello.
    head=src.crop((4,1,36,24))
    out.alpha_composite(head,(4,1+bob))
    # Ajuste bufanda al borde de la mejilla, preservando ojos y cabello.
    d=ImageDraw.Draw(out)
    R(d,8,24+bob,34,26+bob,c['scarf']);R(d,20,24+bob,28,24+bob,c['light']);
    # escudo en la mano libre; durante E se adelanta frente al torso.
    sx=19 if state=='block' else 8
    sy=31 if state=='block' else 33+bob+(1 if active and frame in (1,3) else 0)
    shield(out,sx,sy,raised=state=='block')
    # Espada emergente frente a manga, sin reemplazar rostro.
    if state in ('attack','special') and frame in (1,2):
        if state=='special':R(d,34,11,36,14,'#d6bdff')
    if state=='hurt' and frame in (1,2):
        tint=Image.new('RGBA',(48,48),'#ff6e6866')
        tint.putalpha(out.getchannel('A').point(lambda a:int(a*.38)))
        out=Image.alpha_composite(out,tint)
    return out

def draw_back(src,color,state,frame):
    c=COLORS[color];out=Image.new('RGBA',(48,48));d=ImageDraw.Draw(out)
    st=(-3,0,3,0)[frame] if state=='walk' else 0
    bob=(-1,0,-1,1)[frame] if state=='walk' else 0
    if state=='dead':return draw_down(src,color,'dead',frame)
    for side in (0,1):
        x=(11 if side==0 else 25)+(st if side==0 else -st)
        R(d,x,37,x+11,46,P['outline']);R(d,x+1,38,x+10,42,P['pants']);R(d,x,43,x+12,46,P['boots'])
    out.alpha_composite(sword(Image.new('RGBA',(48,48)),state,frame,'up'))
    d=ImageDraw.Draw(out)
    R(d,10,23+bob,36,39+bob,P['outline']);R(d,12,24+bob,34,37+bob,P['armor_dark']);
    R(d,14,25+bob,31,30+bob,P['armor']);R(d,15,31+bob,31,34+bob,P['armor_light']);
    # bufanda atada visible desde atrás.
    R(d,9,23+bob,37,27+bob,c['dark']);R(d,10,24+bob,35,26+bob,c['scarf'])
    poly(d,[(28,26+bob),(34,27+bob),(37+st//2,39+bob),(31+st//2,42+bob)],c['scarf'])
    # cuello y cabeza de espaldas con mismo tono y contorno de cabello.
    R(d,9,9+bob,35,24+bob,P['outline']);R(d,11,10+bob,33,24+bob,P['hair']);
    R(d,8,7+bob,36,17+bob,P['hair']);R(d,12,4+bob,32,8+bob,P['hair_light']);
    R(d,7,11+bob,11,20+bob,P['hair']);R(d,33,11+bob,38,20+bob,P['hair']);
    R(d,13,15+bob,32,16+bob,P['hair_mid']);
    shield(out,8 if state!='block' else 19,32 if state!='block' else 30,raised=state=='block')
    if state=='hurt' and frame in (1,2):
        overlay=Image.new('RGBA',(48,48),(252,78,76,80));overlay.putalpha(out.getchannel('A').point(lambda v:v//3));out=Image.alpha_composite(out,overlay)
    return out

def draw_side(src,color,state,frame,direction='right'):
    # La vista de perfil conserva los colores del caballero, con una sola pupila visible.
    c=COLORS[color];out=Image.new('RGBA',(48,48));d=ImageDraw.Draw(out)
    stride=(-3,0,3,0)[frame] if state=='walk' else 0
    bob=(-1,0,-1,1)[frame] if state=='walk' else 0
    if state=='dead':
        out=draw_down(src,color,'dead',frame)
        return out.transpose(Image.Transpose.FLIP_LEFT_RIGHT) if direction=='left' else out
    for i,xx in enumerate((16,27)):
        xx+=(stride if i==0 else -stride)
        R(d,xx,36,xx+9,45,P['outline']);R(d,xx+1,37,xx+7,43,P['pants']);R(d,xx,43,xx+10,46,P['boots'])
    out.alpha_composite(sword(Image.new('RGBA',(48,48)),state,frame,'right'))
    d=ImageDraw.Draw(out)
    poly(d,[(11,22+bob),(15,22+bob),(12+stride//2,37+bob),(5+stride//2,40+bob)],c['dark'])
    R(d,12,25+bob,34,38+bob,P['outline']);R(d,14,26+bob,33,35+bob,P['armor']);
    R(d,14,27+bob,23,30+bob,P['armor_light']);R(d,22,31+bob,31,34+bob,P['armor_dark'])
    # perfil facial, mismo cabello castaño con flequillo.
    R(d,11,9+bob,33,23+bob,P['outline']);R(d,13,11+bob,32,22+bob,P['skin']);
    R(d,9,7+bob,35,15+bob,P['hair']);R(d,13,4+bob,32,9+bob,P['hair_light']);
    R(d,8,10+bob,15,20+bob,P['hair']);R(d,32,9+bob,36,14+bob,P['hair_mid']);
    R(d,26,15+bob,30,20+bob,P['outline']);R(d,27,16+bob,28,17+bob,P['steel_white']);
    R(d,32,21+bob,35,23+bob,P['skin_shadow']);R(d,29,23+bob,31,24+bob,'#aa6a60');
    R(d,11,23+bob,35,27+bob,c['dark']);R(d,12,23+bob,34,25+bob,c['scarf']);
    poly(d,[(12,25+bob),(16,26+bob),(13+stride//2,36+bob),(7+stride//2,37+bob)],c['scarf'])
    shield(out,18 if state=='block' else 32,31+bob,raised=state=='block')
    if state=='hurt' and frame in (1,2):
        over=Image.new('RGBA',(48,48),(255,92,74,90));over.putalpha(out.getchannel('A').point(lambda a:a//3));out=Image.alpha_composite(out,over)
    if direction=='left':out=out.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    return out

def draw_player(src,color,state,frame,direction):
    if direction=='down':return draw_down(src,color,state,frame)
    if direction=='up':return draw_back(src,color,state,frame)
    return draw_side(src,color,state,frame,direction)

def make_players():
    for color in COLORS:
        src=Image.open(AS/'maestros'/f'knight_{color}.png').convert('RGBA')
        sheet=Image.new('RGBA',(FRAME*4,FRAME*len(STATES)*len(DIRECTIONS)),(0,0,0,0))
        for state_idx,state in enumerate(STATES):
            for direction_idx,direction in enumerate(DIRECTIONS):
                row=state_idx*len(DIRECTIONS)+direction_idx
                for frame in range(4):
                    cell=draw_player(src,color,state,frame,direction)
                    sheet.alpha_composite(cell,(FRAME*frame,FRAME*row))
        sheet.save(AS/f'knight_{color}_sheet.png',optimize=True)
        # Los menús también muestran sprite definitivo derivado del primer frame de idle.
        idle=sheet.crop((0,0,48,48))
        idle.save(AS/f'knight_{color}.png',optimize=True)
    (AS/'hero.png').write_bytes((AS/'knight_rojo.png').read_bytes())

def make_enemies():
    # Goblin y skeleton tienen atlas direccionales propios en generar_enemigos_y_efectos.py.
    # No sobrescribirlos al regenerar los otros sprites.
    for name in ('slime','bat','flame','boss','ghost'):
        base=Image.open(AS/f'{name}.png').convert('RGBA')
        sheet=Image.new('RGBA',(40*4,40*3),(0,0,0,0))
        for row,state in enumerate(('idle','move','hurt')):
            for f in range(4):
                cell=Image.new('RGBA',(40,40))
                # Deformaciones intencionales en cuadrícula, sin interpolación borrosa.
                if name in ('slime','ghost'):
                    sx,sy=((36,34),(38,31),(35,34),(38,32))[f] if state=='move' else ((36,33),(37,32),(36,33),(37,32))[f]
                elif name=='bat':
                    sx,sy=((39,30),(34,37),(39,31),(33,37))[f]
                elif name=='flame':
                    sx,sy=((36,35),(34,39),(38,32),(35,38))[f]
                else:
                    sx,sy=((36,37),(35,38),(36,36),(35,38))[f] if state=='move' else ((36,36),(37,35),(36,36),(37,35))[f]
                tmp=base.resize((sx,sy),Image.Resampling.NEAREST)
                # mover la figura alrededor de sus pies; para enemigos no se altera el centro de colisión.
                xpos=(40-sx)//2+(1 if state=='move' and f==1 else -1 if state=='move' and f==3 else 0)
                yoffset=40-sy-(2 if name=='bat' and f in (0,2) else 0)
                cell.alpha_composite(tmp,(xpos,yoffset))
                if state=='hurt' and f in (1,2):
                    overlay=Image.new('RGBA',(40,40),(255,117,112,85));overlay.putalpha(cell.getchannel('A').point(lambda a:a//3));cell=Image.alpha_composite(cell,overlay)
                sheet.alpha_composite(cell,(40*f,40*row))
        sheet.save(AS/f'{name}_sheet.png',optimize=True)

def make_previews():
    from PIL import ImageFont
    font=ImageFont.load_default()
    preview=Image.new('RGB',(1100,620),'#121b2c');d=ImageDraw.Draw(preview)
    d.text((24,20),'CRIPTA PIXEL ONLINE   /   ANIMACIONES INTEGRADAS',font=font,fill='#ffcf83')
    dirs=('down','left','right','up')
    colors=list(COLORS)
    for i,c in enumerate(colors):
        sheet=Image.open(AS/f'knight_{c}_sheet.png')
        x=35+i*270
        d.rounded_rectangle((x,54,x+242,295),radius=11,fill='#243249',outline='#5f7693',width=2)
        d.text((x+17,65),'BUFANDA '+c.upper(),font=font,fill='#e7f2ff')
        for direction in range(4):
            f=sheet.crop((2*48,direction*48,3*48,(direction+1)*48))
            f=f.resize((96,96),Image.Resampling.NEAREST)
            preview.paste(f,(x+16+(direction%2)*115,93+(direction//2)*92),f)
    d.text((25,324),'CICLO DE CAMINATA: 4 POSES REALES (POR DIRECCION)',font=font,fill='#ffcf83')
    sheet=Image.open(AS/'knight_rojo_sheet.png')
    for f in range(4):
        frame=sheet.crop((f*48,4*48,(f+1)*48,5*48)).resize((140,140),Image.Resampling.NEAREST)
        x=95+f*250
        d.rounded_rectangle((x-15,354,x+164,556),radius=12,fill='#20334a',outline='#536a87')
        preview.paste(frame,(x+5,364),frame)
        d.text((x+43,516),f'FRAME {f+1}',font=font,fill='#bfe7dd')
    preview.save(ROOT/'VISTA_ANIMACIONES_REALES.png')

if __name__=='__main__':
    make_players();make_enemies();make_previews()
    print('Spritesheets generados:',len(COLORS),'caballeros, 7 criaturas; vista previa.')
