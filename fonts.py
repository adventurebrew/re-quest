#!/usr/bin/env python3

import os
import sys
import math
import io

from operator import itemgetter

import numpy as np

from PIL import Image

def read_uint16le(stream):
    return int.from_bytes(stream.read(2), byteorder='little', signed=False)

def bitmask_to_bytes(bitmask, nbytes, height):
    def convert_line(line):
        l = bitmask[line * nbytes:(line + 1) * nbytes]
        return ''.join(f'{c:08b}' for c in l).replace('0', '_').replace('1', '@')
    return [convert_line(line) for line in range(height)]

def convert_to_pil_image(liner, width, height):
    npp = np.array([ord(x) for x in liner], dtype=np.uint8)
    npp.resize(height, width)
    im = Image.fromarray(npp, mode='P')
    return im

def get_bg_color(row_size, f):
    BGS = ['0', 'n']

    def get_bg(idx):
        return BGS[f(idx) % len(BGS)]
    return get_bg

def resize_pil_image(w, h, bg, im):
    nbase = convert_to_pil_image(str(bg) * w * h, w, h)
    # nbase.paste(im, box=itemgetter('x1', 'y1', 'x2', 'y2')(loc))
    nbase.paste(im, box=(0,0))
    return nbase

def convert(stream):
    zeroes = read_uint16le(stream)
    assert zeroes == 0
    numchar = read_uint16le(stream)
    height = read_uint16le(stream)
    print(numchar, height)
    offsets = [read_uint16le(stream) for _ in range(numchar)]
    print(stream.tell())


    w = 16
    h = 24
    grid_size = 16

    enpp = np.array([[0] * w * grid_size] * h * grid_size, dtype=np.uint8)
    bim = Image.fromarray(enpp, mode='P')

    get_bg = get_bg_color(grid_size, lambda idx: idx + int(idx / grid_size))

    for idx, off in enumerate(offsets):
        stream.seek(off, 0)
        width = ord(stream.read(1))
        cheight = ord(stream.read(1))
        nbytes = (width + 7) // 8
        bitmask = stream.read(cheight * nbytes)


        liner = ''.join(x[:width] for x in bitmask_to_bytes(bitmask, nbytes, cheight))
        im = convert_to_pil_image(liner, width, cheight)
        im = resize_pil_image(w, h, get_bg(idx), im)
        bim.paste(im, box=((idx % grid_size) * w, int(idx / grid_size) * h))
            # im.save(f'try/char_{idx:03d}.png')
        # print(off, stream.tell())
    bim.save('font.png')

if __name__ == '__main__':
    if not len(sys.argv) > 1:
        print('missing arguments')
        exit(1)

    fname = sys.argv[1]
    with open(fname, 'rb') as f:
        convert(f)
    