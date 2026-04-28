from PIL import Image, ImageOps

# Test actual y_offset
tank_img = Image.open('extracted_icons/r97_object_140.png').convert("RGBA")
print(f'Original: {tank_img.size}')

# Normalize
std_w, std_h = 380, 304
temp = ImageOps.contain(tank_img, (std_w, std_h), Image.LANCZOS)
canvas = Image.new("RGBA", (std_w, std_h), (0, 0, 0, 0))
x = (std_w - temp.width) // 2
y = (std_h - temp.height) // 2
canvas.paste(temp, (x, y), temp)
tank_img = canvas
print(f'After normalize: {tank_img.size}')

# Scale to work area
card_w, card_h = 170, 120
work_w = int(card_w * 1.3)
work_h = int(card_h * 0.75)
print(f'Work area: {work_w}x{work_h}')
tank_img = ImageOps.contain(tank_img, (work_w, work_h), Image.LANCZOS)
print(f'After scaling: {tank_img.size}')

# Calculate y_offset with different lift values
for lift_px in [0, 50, 100]:
    y_offset = 0 - lift_px
    print(f'\n_detail_image_lift_px={lift_px}: y_offset={y_offset}')
    print(f'  Tank top at y={y_offset}, bottom at y={y_offset + tank_img.height}')
    print(f'  Card: y=0 to y={card_h}')
    if y_offset >= 0:
        print(f'  Visible: y={y_offset} to y={min(card_h, y_offset + tank_img.height)} (TOP of tank visible)')
    else:
        print(f'  Visible: y=0 to y={y_offset + tank_img.height} (BOTTOM of tank visible)')
