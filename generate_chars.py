from PIL import Image, ImageDraw, ImageFont
font = ImageFont.truetype('xvmsymbol.ttf', 32)
img = Image.new('RGB', (1600, 1600), 'white')
draw = ImageDraw.Draw(img)
x, y = 10, 10
for i in range(0x21, 0x110):
    c = chr(i)
    draw.text((x, y), f"{c} {hex(i)}", font=font, fill='black')
    x += 150
    if x > 1500:
        x = 10
        y += 40
img.save('xvm_chars.png')
