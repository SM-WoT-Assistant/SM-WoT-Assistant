from PIL import Image
import os

icons_dir = 'extracted_icons'

tanks = [
    ('r97_object_140.png', 'Объект 140'),
    ('r148_object_430_u.png', 'Объект 430У'),
]

print('Анализ изображений после crop(bbox):')
for fname, name in tanks:
    path = os.path.join(icons_dir, fname)
    if os.path.exists(path):
        img = Image.open(path).convert("RGBA")
        print(f'\n{name} ({fname}):')
        print(f'  Оригинальный размер: {img.size}')
        bbox = img.getbbox()
        if bbox:
            cropped = img.crop(bbox)
            print(f'  BBox: {bbox}')
            print(f'  Размер после crop: {cropped.size}')
            print(f'  Прозрачные поля: лево={bbox[0]}, верх={bbox[1]}, право={img.width-bbox[2]}, низ={img.height-bbox[3]}')
