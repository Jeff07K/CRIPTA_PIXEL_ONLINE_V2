"""Vista animada de cuatro cuadros, extraídos del juego, sin inventar arte nuevo."""
from pathlib import Path
from PIL import Image, ImageDraw,ImageFont
root=Path(__file__).resolve().parent
colors=['rojo','azul','verde','naranja']
font=ImageFont.load_default()
frames=[]
for i in range(4):
    canvas=Image.new('RGB',(960,250),'#121b2b')
    d=ImageDraw.Draw(canvas)
    for j,c in enumerate(colors):
        x=24+j*236
        d.rounded_rectangle((x,25,x+213,224),radius=10,fill='#25344a',outline='#647e9d',width=2)
        d.rectangle((x+15,168,x+200,190),fill='#345946')
        d.rectangle((x+15,190,x+200,196),fill='#20352d')
        sheet=Image.open(root/'assets'/f'knight_{c}_sheet.png')
        sprite=sheet.crop((48*i,48*4,48*(i+1),48*5)).resize((120,120),Image.Resampling.NEAREST)
        canvas.paste(sprite,(x+50,47),sprite)
        d.text((x+52,201),c.upper(),font=font,fill='#f7e7b5')
        d.text((x+15,34),f'PASO {i+1} / 4',font=font,fill='#e5eaf2')
    frames.append(canvas)
frames[0].save(root/'DEMO_CAMINATA_REAL.gif',save_all=True,append_images=frames[1:],duration=[130,130,130,130],loop=0,optimize=False)
print('GIF generado con 4 fotogramas de caminata; contenido extraído de atlas real')
