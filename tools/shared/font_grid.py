import itertools

import numpy as np
from PIL import Image

BGS = [b'0', b'n']
BASE_XOFF = 8
BASE_YOFF = 8
TILE_W = 48 + BASE_XOFF
TILE_H = 48 + BASE_YOFF
GRID_SIZE = 16

palette = [((53 + x) ** 2 * 13 // 5) % 256 for x in range(256 * 3)]


def convert_to_pil_image(char, size=None):
    # print('CHAR:', char)
    npp = np.array(char, dtype=np.uint8)
    if size:
        width, height = size
        npp.resize(height, width)
    im = Image.fromarray(npp, mode='P')
    return im


def get_bg_color(row_size, f, bgs=BGS):
    def get_bg(idx):
        return ord(bgs[f(idx) % len(bgs)])
    return get_bg


def read_image_grid(filename, w=TILE_W, h=TILE_H, grid_size=GRID_SIZE):
    bim = Image.open(filename)

    for row in range(grid_size):
        for col in range(grid_size):
            area = (col * w, row * h, (col + 1) * w, (row + 1) * h)
            yield bim.crop(area)


def checkered_grid(nchars, w=TILE_W, h=TILE_H, grid_size=GRID_SIZE, transparency=0, bgs=BGS):
    assert nchars <= grid_size ** 2, nchars

    bim = convert_to_pil_image([[transparency] * w * grid_size] * h * grid_size)
    get_bg = get_bg_color(grid_size, lambda idx: idx + int(idx / grid_size), bgs=bgs)

    # nchars does not have to match real number of characters nor max. index
    for i in range(nchars):
        ph = convert_to_pil_image([[get_bg(i)] * w] * h)
        bim.paste(ph, box=((i % grid_size) * w, int(i / grid_size) * h))

    return bim


def create_char_grid(nchars, chars, w=TILE_W, h=TILE_H, grid_size=GRID_SIZE, base_xoff=BASE_XOFF, base_yoff=BASE_YOFF, transparency=0, bgs=BGS):
    bim = checkered_grid(nchars, w=w, h=h, grid_size=grid_size, transparency=transparency, bgs=bgs)

    # idx is character index in ascii table
    for idx, im in chars:
        assert idx < nchars
        xbase = (idx % grid_size) * w + base_xoff
        ybase = (idx // grid_size) * h + base_yoff
        bim.paste(convert_to_pil_image(im), box=(xbase, ybase))

    return bim


def count_in_row(pred, row):
    return sum(1 for _ in itertools.takewhile(pred, row))


def resize_frame(im, base_xoff=BASE_XOFF, base_yoff=BASE_YOFF):
    frame = list(np.asarray(im))
    BG = frame[-1][-1]

    char_is_bg = lambda c: c == BG
    line_is_bg = lambda line: all(c == BG for c in line)

    if set(itertools.chain.from_iterable(frame)) == {BG}:
        return None

    x1 = min(count_in_row(char_is_bg, line) for line in frame)
    x2 = len(frame[0]) - min(count_in_row(char_is_bg, reversed(line)) for line in frame)
    y1 = count_in_row(line_is_bg, frame)
    y2 = len(frame) - count_in_row(line_is_bg, reversed(frame))

    crop_area = (x1, y1, x2, y2)

    if crop_area == (0, 0, len(frame[0]), len(frame)):
        return None

    off_area = (x1 - base_xoff, y1 - base_yoff, x2 - base_xoff, y2 - base_yoff)

    fields = ('x1', 'y1', 'x2', 'y2')
    loc = dict(zip(fields, off_area))

    return loc, np.asarray(im.crop(crop_area))


def save_font(chars, char_images, font_path):
    im = create_char_grid(chars.stop, zip(chars, char_images))
    im.putpalette(palette)
    im.save(font_path)


def load_font(font_path):
    frames = read_image_grid(font_path)
    return [resize_frame(frame) for frame in frames]
