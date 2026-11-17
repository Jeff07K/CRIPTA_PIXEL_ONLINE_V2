"""Decoraciones pixel art originales de los cuatro entornos.
Pillow solo se necesita para regenerar los PNG, no para ejecutar el juego.
"""
from PIL import Image,ImageDraw
from pathlib import Path
A=Path(__file__).resolve().parent/'assets'
def rect(d,*args):d.rectangle(args[:4],fill=args[4])
def poly(d,pts,col):d.polygon(pts,fill=col)

def forest():
 im=Image.new('RGBA',(64,72));d=ImageDraw.Draw(im)
 # Tronco y raíces oscuros con iluminación de la izquierda
 rect(d,27,32,39,67,'#203c35');rect(d,29,33,37,65,'#7f5e45');rect(d,30,34,32,60,'#b18a56')
 poly(d,[(31,56),(24,68),(21,68),(28,53)],'#594436');poly(d,[(34,55),(42,68),(45,68),(38,51)],'#624632')
 # Copa en tres capas de píxeles, sin texturas difusas
 poly(d,[(9,28),(17,15),(26,15),(28,7),(39,6),(47,15),(51,15),(60,27),(56,43),(49,48),(19,49),(8,41)],'#173c37')
 poly(d,[(10,28),(18,18),(28,18),(32,9),(39,10),(47,19),(52,19),(57,28),(52,39),(44,44),(18,43)],'#2e754b')
 poly(d,[(12,27),(18,19),(30,19),(32,13),(40,13),(43,21),(51,21),(54,28),(49,32),(28,33),(21,38),(12,35)],'#44945c')
 rect(d,20,20,31,22,'#6bab67');rect(d,36,16,43,19,'#89ca78');rect(d,18,33,23,35,'#62b36c');rect(d,43,34,49,37,'#245c45')
 rect(d,16,43,23,46,'#19543f');rect(d,43,39,51,42,'#1c6146')
 return im

def ice():
 im=Image.new('RGBA',(64,72));d=ImageDraw.Draw(im)
 # Pedestal helado, cristales cian con contorno azul profundo.
 poly(d,[(8,64),(12,51),(26,48),(28,36),(35,33),(42,46),(52,49),(58,65),(47,69),(15,69)],'#304e6a')
 poly(d,[(12,62),(16,52),(27,49),(33,39),(38,47),(50,51),(54,63)],'#638eac')
 poly(d,[(19,55),(22,29),(33,11),(41,28),(44,56),(39,64),(24,65)],'#305978')
 poly(d,[(23,53),(27,28),(33,15),(36,50),(32,63),(25,61)],'#7ac9df')
 poly(d,[(33,15),(39,29),(42,54),(35,61)],'#bff3f3')
 poly(d,[(4,52),(11,36),(20,45),(23,61),(14,67)],'#386b8b');poly(d,[(8,51),(12,41),(17,47),(18,59)],'#92dbe9')
 poly(d,[(42,51),(49,34),(57,49),(60,61),(47,64)],'#2c6584');poly(d,[(46,50),(50,40),(55,53)],'#b2f4f4')
 for x,y in [(9,28),(54,18),(48,11),(13,12)]:rect(d,x,y,x+2,y+2,'#d5ffff')
 return im

def fire():
 im=Image.new('RGBA',(64,72));d=ImageDraw.Draw(im)
 # Obsidiana fracturada y magma, piezas dibujadas pixel por pixel.
 poly(d,[(6,61),(12,41),(28,35),(32,23),(42,36),(55,43),(60,62),(50,69),(13,69)],'#241e2f')
 poly(d,[(13,58),(19,43),(28,39),(35,30),(44,42),(53,54),(48,64),(21,64)],'#51323a')
 poly(d,[(31,35),(35,29),(37,43),(47,51),(44,56),(32,46)],'#b54a31')
 poly(d,[(33,35),(35,33),(37,42),(42,50)],'#ffb24f')
 poly(d,[(14,49),(19,46),(22,54),(18,59)],'#ff8739')
 rect(d,9,63,54,65,'#8c392f')
 # Pequeño brasero de lava contenido en la roca
 poly(d,[(19,40),(22,27),(28,23),(30,12),(38,23),(44,29),(40,42)],'#a12d30')
 poly(d,[(24,37),(26,28),(31,25),(32,17),(37,27),(40,31),(36,40)],'#ff7d30')
 poly(d,[(29,35),(31,25),(34,32),(35,37)],'#ffdc77')
 return im

def arena():
 im=Image.new('RGBA',(64,72));d=ImageDraw.Draw(im)
 poly(d,[(14,60),(15,33),(19,30),(45,30),(50,34),(50,61),(56,63),(56,68),(8,68),(8,63)],'#292942')
 rect(d,19,35,44,62,'#5a5371');rect(d,23,37,41,60,'#797592');rect(d,21,32,43,35,'#a49bbc')
 rect(d,14,27,50,33,'#25273b');rect(d,16,27,48,30,'#9d91b1')
 # Runa central dorada
 rect(d,31,42,33,55,'#e3b46c');rect(d,25,46,39,49,'#e3b46c');rect(d,30,44,34,50,'#fff2c1')
 rect(d,13,63,51,65,'#41425a')
 return im

if __name__=='__main__':
 for key,fn in [('terrain_forest',forest),('terrain_ice',ice),('terrain_fire',fire),('terrain_arena',arena)]:
  fn().save(A/f'{key}.png',optimize=True)
 print('Decoraciones de bosque, hielo, fuego y arena generadas')
