# NOTE! currently only working on SQ6 (and probably its era as well)

# install Tesseract from https://github.com/UB-Mannheim/tesseract/wiki

import argparse
import io
import re
from enum import Enum
from itertools import chain
from pathlib import Path

from PIL import Image
import numpy as np
import pandas as pd
import pytesseract

SIERRA_VIEW_HEADER = b'\x80'
SIERRA_PAL_HEADER = b'\x8b\x00'


class ViewTypes(Enum):
    # Amiga not supported!
    EGA = 0x0
    VGA = 0x80
    VGA11 = 0x80000  # it's not a Sierra value!


class CompressionTypes(Enum):
    NONE = 0
    RLE = 138
    INVALID = 1000


def read_le(stream, length=1):
    b = stream.read(length)
    if b == b'':
        # logger.debug(f'read_le: {stream.tell()}\t EOF')   #TODO
        raise EOFError
    return int.from_bytes(b, byteorder='little')


def read_at(stream, idx, length=1):
    stream.seek(idx)
    return read_le(stream, length)


def get_view_type(stream):
    view_type = ViewTypes(read_le(stream))
    if view_type == ViewTypes.VGA:
        # TODO how do we really differentiate them??
        view_type = ViewTypes.VGA11
    return view_type


def write_image(cel, view, loop_num, cel_num, viewspath, default_palette):
    # TODO write colored picture, with game's palettes
    buffer = b''
    for row in cel:
        for pixel in row:
            color = default_palette[pixel]
            # assert color['used']  #TODO
            buffer += bytes([color['r']])
            buffer += bytes([color['g']])
            buffer += bytes([color['b']])
    new_image = Image.frombytes('RGB', (len(cel[0]), len(cel)), buffer)
    im_path = viewspath / f'view_{view}_loop_{loop_num}_cel_{cel_num}.png'
    new_image.save(im_path)
    return im_path


def write_view(p, viewspath, default_palette):
    result = []
    assert p.suffix == '.v56'
    view = p.stem
    OFFSET = 0x1a
    resource_size = p.stat().st_size
    stream = io.BytesIO(p.read_bytes())
    assert stream.read(1) == SIERRA_VIEW_HEADER
    view_type = get_view_type(stream)
    if view_type != ViewTypes.VGA11:
        raise NotImplementedError

    view_header_size = read_at(stream, OFFSET, length=2)
    loop_count = read_at(stream, OFFSET + 2)
    assert loop_count >= 1
    loop_header_size = read_at(stream, OFFSET + 12)
    x_resolution = read_at(stream, OFFSET + 14, length=2)
    y_resolution = read_at(stream, OFFSET + 16, length=2)
    for loop_num in range(loop_count):
        mirror_x = False  # TODO respect mirror_x
        loop_header = OFFSET + 2 + view_header_size + (loop_header_size * loop_num)
        if read_at(stream, loop_header + 0) != 0xff:  # it's actually -1
            if read_at(stream, loop_header + 1) == 1:
                mirror_x = True
        cel_count = read_at(stream, loop_header + 2)
        # assert cel_count >= 1 # TODO it fails on SQ6, view 0, loop 1 - needs investigation, probably because it's mirrored
        hunk_palette_offset = read_at(stream, loop_header + 8, length=4)
        for cel_num in range(cel_count):
            cel_header_offset = OFFSET + \
                                read_at(stream, loop_header + 12, length=4) + \
                                read_at(stream, OFFSET + 13) * cel_num
            width = read_at(stream, cel_header_offset + 0, length=2)
            height = read_at(stream, cel_header_offset + 2, length=2)
            x_mod_todo = read_at(stream, cel_header_offset + 4, length=2)
            y_mod_todo = read_at(stream, cel_header_offset + 6, length=2)
            skip_color = read_at(stream, cel_header_offset + 8)
            compression_type = CompressionTypes(read_at(stream, cel_header_offset + 9))
            assert compression_type == CompressionTypes.RLE
            flags = read_at(stream, cel_header_offset + 10, length=2)
            assert flags == 0
            data_offset = OFFSET + read_at(stream, cel_header_offset + 24, length=4)
            uncompressed_data_offset = OFFSET + read_at(stream, cel_header_offset + 28, length=4)
            control_offset = OFFSET + read_at(stream, cel_header_offset + 32, length=4)
            cel = []
            for y in range(height):
                row_offset = read_at(stream, control_offset + y * 4, length=4)
                if y + 1 < height:
                    row_compressed_size = read_at(stream, control_offset + (y + 1) * 4, length=4) - row_offset
                else:
                    row_compressed_size = resource_size - row_offset - data_offset
                stream.seek(data_offset + row_offset)
                row = io.BytesIO(stream.read(row_compressed_size))
                literal_offset = read_at(stream, control_offset + height * 4 + y * 4, length=4)
                if y + 1 < height:
                    literal_row_size = read_at(stream, control_offset + height * 4 + (y + 1) * 4,
                                               length=4) - literal_offset
                else:
                    literal_row_size = resource_size - literal_offset - uncompressed_data_offset
                stream.seek(uncompressed_data_offset + literal_offset)
                literal = io.BytesIO(stream.read(literal_row_size))
                row_pixels = []
                num_of_pixels = 0
                while num_of_pixels < width:
                    control_byte = read_le(row)
                    length = control_byte
                    if control_byte & 0x80:
                        # Run-length encoded
                        length &= 0x3f
                        if control_byte & 0x40:
                            # Fill with skip color
                            row_pixels.extend([skip_color] * length)
                        else:
                            row_pixels.extend([read_le(literal)] * length)
                    else:
                        # Uncompressed
                        for _ in range(length):
                            row_pixels.append(read_le(literal))
                    num_of_pixels += length
                # print(''.join([chr(p + 40) for p in row_pixels]))
                cel.append(row_pixels)
            impath = write_image(cel, view, loop_num, cel_num, viewspath, default_palette)
            result.append(impath)
    return result


def extract_text(view):
    for psm in [None, 6]:
        if psm is None:
            result = pytesseract.image_to_string(Image.open(view))
        else:
            result = pytesseract.image_to_string(Image.open(view), config=f'--psm {psm}')
        if result:
            return result
    return ''


def get_height(view):
    im = Image.open(view)
    width, height = im.size
    return height


def write_excel(views, csvdir):
    excel_path = Path(csvdir) / 'views.xlsx'
    data = []
    for view in views:
        r = re.match('view_(\d+)_loop_(\d+)_cel_(\d+)', view.stem)
        view_num = int(r.group(1))
        loop = int(r.group(2))
        cel = int(r.group(3))
        text = extract_text(view)
        data.append({
            'view': view_num,
            'loop': loop,
            'cel': cel,
            'text': text,
            'translation': '',
            'image': '',
        })
    df = pd.DataFrame(data)
    writer = pd.ExcelWriter(excel_path, engine='xlsxwriter')
    df.to_excel(writer, sheet_name='Sheet1')
    worksheet = writer.sheets['Sheet1']
    for row, view in enumerate(views):
        # write in row+1, 6th column (from 0), 'Move and size with cells'
        worksheet.insert_image(row + 1, 6, view, {'object_position': 1})
        worksheet.set_row_pixels(row + 1, get_height(view) + 15)  # 15 pixels for spacing

    writer.save()


def read_pal(gamepath, pal_num):
    p = gamepath / f'{pal_num}.pal'
    stream = io.BytesIO(p.read_bytes())
    assert stream.read(2) == SIERRA_PAL_HEADER
    stream = io.BytesIO(stream.read())  # chop the first 2 bytes - it's only confusing for offsets
    num_of_palettes = read_at(stream, 10)
    assert num_of_palettes == 1
    pal_pointer = 13 + (2 * num_of_palettes)
    start_color = read_at(stream, pal_pointer + 10)
    num_of_colors = read_at(stream, pal_pointer + 14, length=2)
    used = bool(read_at(stream, pal_pointer + 16))
    shared_used = bool(read_at(stream, pal_pointer + 17))
    version = read_at(stream, pal_pointer + 18, length=4)

    last_color = start_color + num_of_colors
    assert last_color <= 256

    stream.seek(pal_pointer + 22)

    colors = []
    for i in range(256):
        colors.append({'used': False, 'r': 0, 'g': 0, 'b': 0})
    for k in range(num_of_colors):
        i = start_color + k
        if shared_used:
            colors[i]['used'] = used
        else:
            colors[i]['used'] = read_le(stream)
        colors[i]['r'] = read_le(stream)
        colors[i]['g'] = read_le(stream)
        colors[i]['b'] = read_le(stream)
    return colors


def view_export(gamepath, csvdir):
    views = []
    viewspath = Path(csvdir) / 'views'
    viewspath.mkdir(exist_ok=True)
    default_palette = read_pal(gamepath, 999)
    for p in chain(gamepath.glob('view.*'), gamepath.glob('970.v56')):  # TODO replace 999 with *
        views.extend(write_view(p, viewspath, default_palette))
    write_excel(views, csvdir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     description='=== CURRENTLY WORKING ONLY SQ6 (AND PROBABLY ITS ERA) ===\n'
                                                 'Exports views from *.v56 or view.* files to an Excel file\n'
                                                 "Note that this script *isn't* part of translation's 'export_all' flow", )
    parser.add_argument("gamedir", help="directory containing the game files (as patches - see 'export_all' help)")
    parser.add_argument("csvdir", help="directory to write messages.csv")
    parser.add_argument("--tesseract", "-t",
                        help="path of installed Tesseract (download from https://github.com/UB-Mannheim/tesseract/wiki)",
                        default=r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    args = parser.parse_args()

    pytesseract.pytesseract.tesseract_cmd = args.tesseract

    view_export(Path(args.gamedir), args.csvdir)
