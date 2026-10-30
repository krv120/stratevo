"""Generate a text-only brand sharing graphic; no fictitious factory/customer imagery."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
root=Path(__file__).resolve().parents[1]/'web'
(root/'images').mkdir(exist_ok=True)
image=Image.new('RGB',(1200,630),'#070c16');draw=ImageDraw.Draw(image)
font_path='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
font=lambda size:ImageFont.truetype(font_path,size)
draw.rectangle((0,0,18,630),fill='#3979ee')
draw.text((82,67),'STRATEVO',font=font(38),fill='#c6d9fb')
draw.text((78,193),'China sourcing.',font=font(76),fill='white')
draw.text((78,289),'Clearer decisions.',font=font(76),fill='#90b6fa')
draw.line((82,448,1100,448),fill='#354662',width=2)
draw.text((82,488),'Requirements  /  Comparison  /  Evidence',font=font(27),fill='#d1dced')
image.save(root/'images'/'stratevo-social.jpg',quality=90,optimize=True)
(root/'favicon.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"><rect width="48" height="48" rx="10" fill="#1458d2"/><path transform="translate(7 8)" fill="white" d="M32 2H13C3 2 0 11 8 16L22 24H5L1 31H21C32 31 35 22 26 16L13 9H28Z"/></svg>')
