from PIL import Image, ImageOps

# Test the actual image processing
tank_img = Image.open('extracted_icons/r97_object_140.png').convert("RGBA")
print(f'Original size: {tank_img.size}')

# Normalize to 380x304
std_w, std_h = 380, 304
temp = ImageOps.contain(tank_img, (std_w, std_h), Image.LANCZOS)
canvas = Image.new("RGBA", (std_w, std_h), (0, 0, 0, 0))
x = (std_w - temp.width) // 2
y = (std_h - temp.height) // 2
canvas.paste(temp, (x, y), temp)
tank_img = canvas
print(f'After normalization: {tank_img.size}')

# Scale to work area
card_w, card_h = 170, 120
work_w = int(card_w * 1.3)
work_h = int(card_h * 0.75)
print(f'Work area: {work_w}x{work_h}')
tank_img = ImageOps.contain(tank_img, (work_w, work_h), Image.LANCZOS)
print(f'After scaling to work area: {tank_img.size}')

# Calculate y_offset
y_offset = 5  # Fixed distance from top
print(f'y_offset = {y_offset}')
print(f'Tank will be positioned at y={y_offset}, extends to y={y_offset + tank_img.height}')
print(f'Visible in card (y=0 to y={card_h}): y={max(0, y_offset)} to y={min(card_h, y_offset + tank_img.height)}')
