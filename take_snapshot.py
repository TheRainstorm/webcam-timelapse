import argparse
import datetime
import logging
import os
import requests
from PIL import Image, ImageDraw, ImageFont

def add_text(input_path, output_path, now, font_size=24, place='left-top'):
    # add datetime
    img = Image.open(input_path)
    draw = ImageDraw.Draw(img)
    text = f"{now.strftime('%Y-%m-%d %H:%M:%S')}"
    
    # set text font
    font_path = 'FZHTK.TTF'
    font = ImageFont.truetype(font_path, font_size)
    text_width, text_height = draw.textsize(text, font=font)
    
    margin = 10
    # set text position
    if place == 'left-top':
        text_position = (margin, margin)
    elif place == 'right-top':
        text_position = (img.width-text_width-margin, margin)
    elif place == 'left-bottom':
        text_position = (margin, img.height-text_height-margin)
    elif place == 'right-bottom':
        text_position = (img.width-text_width-margin, img.height-text_height-margin)

    # set text color
    text_color = (255, 255, 255)

    # add text
    draw.text(text_position, text, font=font, fill=text_color)
    img.save(output_path)

def download_snapshot(snapshot_url, output_dir, font_size=24, place='left-top'):
    now = datetime.datetime.now()
    year = str(now.year)
    month = str(now.month)
    day = str(now.day)
    filename = f"{now.strftime('%Y-%m-%d-%H-%M-%S')}.jpg"
    filepath = os.path.join(output_dir, year, month, day, filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    r = requests.get(snapshot_url)
    if r.status_code == 200:
        with open(filepath, 'wb') as f:
            f.write(r.content)
    else:
        logging.warning(f"Failed to download snapshot at {filename}")
    add_text(filepath, filepath, now, font_size=font_size, place=place)
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Take a snapshot of the current state of the system')
    parser.add_argument('-u', '--snapshot-url', help='URL to take the snapshot from')
    parser.add_argument('-o', '--output-dir', help='Directory to save the snapshot')
    parser.add_argument('--font-size', type=int, default=24, help='Font size of the datetime text')
    parser.add_argument('-p', '--place', choices=['left-top', 'right-top', 'left-bottom', 'right-bottom'],
                        help='Position to place the datetime text')
    args = parser.parse_args()
    download_snapshot(args.snapshot_url, args.output_dir, font_size=args.font_size, place=args.place)
    