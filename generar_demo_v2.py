"""Demostración extraída exclusivamente de los fotogramas reales incluidos en assets/."""
from PIL import Image,ImageDraw,ImageFont
from pathlib import Path
ROOT=Path(__file__).resolve().parent;AS=ROOT/'assets'
try:font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf',14)
except OSError:font=ImageFont.load_default()
try:small=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',11)
except OSError:small=ImageFont.load_default()
labels=['GOBLIN · CAMINAR','ESQUELETO · CAMINAR','BRUTAL','DISTANCIA','VENENO','PARÁLISIS']
panel=[(20,48,220,254),(240,48,440,254),(460,48,610,254),(625,48,775,254),(20,275,210,470),(230,275,420,470)]
g=Image.open(AS/'goblin_sheet.png');s=Image.open(AS/'skeleton_sheet.png')
fxs={name:Image.open(AS/f'fx_{name}_sheet.png') for name in ('brutal','distancia','veneno','paralisis')}
frames=[]
for fr in range(8):
    out=Image.new('RGB',(800,500),'#111b2b');d=ImageDraw.Draw(out)
    d.text((22,14),'CRIPTA PIXEL ONLINE · ANIMACIONES REALES V2',font=font,fill='#ffd48e')
    cells=[(20,46,212,254),(232,46,424,254),(444,46,614,254),(620,46,786,254),
           (20,274,394,480),(410,274,786,480)]
    for i,b in enumerate(cells):
        d.rounded_rectangle(b,10,fill='#25344a',outline='#588aaf',width=2)
    for i,(name,sh) in enumerate((('Duende',g),('Esqueleto',s))):
        x=35+212*i
        d.text((x,63),name+' / caminar',font=small,fill='#b5e3ff')
        row=4 # walking down
        frame=(fr//2)%4
        im=sh.crop((frame*40,row*40,(frame+1)*40,(row+1)*40)).resize((134,134),Image.Resampling.NEAREST)
        out.paste(im,(x+15,97),im)
        d.text((x+25,228),f'Fotograma {frame+1} / 4',font=small,fill='#b8de9b')
    for j,(name,sh) in enumerate(fxs.items()):
        x=455+177*j if j<2 else 38+393*(j-2)
        y=46 if j<2 else 276
        d.text((x,y+15),name.upper(),font=small,fill='#ffd48e')
        im=sh.crop((fr*96,0,(fr+1)*96,96)).resize((125,125),Image.Resampling.NEAREST)
        out.paste(im,(x+14,y+50),im)
    frames.append(out)
frames[0].save(ROOT/'DEMO_ENEMIGOS_Y_ESPECIALES.gif',save_all=True,append_images=frames[1:],duration=125,loop=0,optimize=True)
print('GIF generado:',ROOT/'DEMO_ENEMIGOS_Y_ESPECIALES.gif')
