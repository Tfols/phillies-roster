"""
Generates PWA icons for the Phillies Roster app.
Run once before pushing to GitHub:  python generate_icons.py
Requires: Pillow  (pip install Pillow)
"""
import os
from PIL import Image, ImageDraw, ImageFont

PHILLIES_RED  = '#E81828'
PHILLIES_NAVY = '#002D72'
WHITE         = '#FFFFFF'

FONT_CANDIDATES = [
    # Linux / WSL
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf',
    '/usr/share/fonts/TTF/DejaVuSans-Bold.ttf',
    # macOS
    '/System/Library/Fonts/Helvetica.ttc',
    # Windows (accessed through WSL)
    '/mnt/c/Windows/Fonts/arialbd.ttf',
    'C:/Windows/Fonts/arialbd.ttf',
]


def load_font(size: int) -> ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            pass
    return ImageFont.load_default()


def make_icon(size: int) -> Image.Image:
    img  = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Red rounded-rectangle background
    radius = size // 6
    draw.rounded_rectangle([0, 0, size - 1, size - 1],
                           radius=radius, fill=PHILLIES_RED)

    # Thin white border
    bw = max(2, size // 48)
    draw.rounded_rectangle([bw, bw, size - bw - 1, size - bw - 1],
                           radius=radius - bw, outline=WHITE, width=bw)

    # "P" glyph centred
    font_size = int(size * 0.62)
    font = load_font(font_size)
    text = 'P'
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (size - tw) // 2 - bbox[0]
    y = (size - th) // 2 - bbox[1] - int(size * 0.02)   # slight upward nudge
    draw.text((x, y), text, fill=WHITE, font=font)

    return img


os.makedirs('static/icons', exist_ok=True)

for sz in (192, 512):
    icon = make_icon(sz)
    # Save as RGB PNG (required for iOS apple-touch-icon)
    icon.convert('RGB').save(f'static/icons/icon-{sz}.png', 'PNG', optimize=True)
    print(f'  Created static/icons/icon-{sz}.png')

print('Icons generated.')
