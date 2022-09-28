# based on (improved) code from 'font_mirror.py'
# didn't copy code relevant for mirroring, and font writing
# reference: http://sci.sierrahelp.com/Documentation/SCISpecifications/15-SCIFontResource.html

# public API:
# create Font from file
# font.dump() # dump to screen all chars
# font.write(b'some text\nmaybe on few lines') # returns NP array
# font.write_image(img, b'same') # creates 'img' file with BYTES text
# can change default colors, see methods signatures

import io
import math
from pathlib import Path
import numpy as np

from PIL import Image

SIERRA_FONT_HEADER = b'\x87\x00'


def read_le(stream, length=1):
    b = stream.read(length)
    if b == b'':
        # logger.debug(f'read_le: {stream.tell()}\t EOF')   #TODO
        raise EOFError
    return int.from_bytes(b, byteorder='little')


def read_be(stream, length=1):
    b = stream.read(length)
    if b == b'':
        # logger.debug(f'read_le: {stream.tell()}\t EOF')   #TODO
        raise EOFError
    return int.from_bytes(b, byteorder='big')


def read_at(stream, idx, length=1):
    stream.seek(idx)
    return read_le(stream, length)


def get_data(stream, width):
    num_of_bytes = math.ceil(width / 8)
    data = read_be(stream, length=num_of_bytes)
    bits = bin(data)[2:].zfill(num_of_bytes * 8)
    bits = bits[:width]
    return [b == '1' for b in bits]


class Char:
    def __init__(self, stream, char_code):
        self.char_code = char_code
        self.lines = []

        index = read_at(stream, 6 + char_code * 2, length=2)
        width = read_at(stream, index)
        num_of_lines = read_le(stream)
        for _ in range(num_of_lines):
            data = get_data(stream, width)
            self.lines.append(data)

    def __repr__(self):
        return f"Char {hex(self.char_code)} '{chr(self.char_code)}'"

    def dump(self):
        for line in self.lines:
            for char in line:
                if char:
                    print("*", end='')
                else:
                    print(" ", end='')
            print()

    def write(self, color=100, background=0):
        result = []
        for line in self.lines:
            l = []
            for char in line:
                if char:
                    l.append(color)
                else:
                    l.append(background)
            result.append(l)
        return np.array(result, dtype=np.uint8)


class Font:
    def __init__(self, fontfile):
        stream = io.BytesIO(Path(fontfile).read_bytes())
        assert stream.read(2) == SIERRA_FONT_HEADER
        stream = io.BytesIO(stream.read())  # chop the first 2 bytes - it's only confusing for offsets

        # we have problems with the last chars, ignoring them, as they aren't interesting for me
        self.num_of_chars = min(read_at(stream, 2, length=2), 255)
        self.general_height = read_le(stream)
        self.chars = []
        for char_code in range(self.num_of_chars):
            self.chars.append(Char(stream, char_code))

    def dump(self):
        for char in self.chars:
            print(char)
            char.dump()
            print()

    def dump_image(self, img):
        text = b''
        for char in self.chars:
            if char.char_code % 16 == 0:
                text += b'\n'
            text += char.char_code.to_bytes(1, byteorder='little')
        text = text.strip()
        self.write_image(img, text)

    def pad_height(self, matrices, background):
        max_height = 0
        for m in matrices:
            max_height = max(m.shape[0], max_height, self.general_height)
        result = []
        for m in matrices:
            result.append(
                np.pad(m, ((0, max_height - m.shape[0]), (0, 0)), constant_values=background)
            )
        return result

    def pad_all(self, matrices, background):
        max_height = 0
        max_width = 0
        for m in matrices:
            max_height = max(m.shape[0], max_height, self.general_height)
            max_width = max(m.shape[1], max_width)
        result = []
        for m in matrices:
            result.append(
                np.pad(m, ((0, max_height - m.shape[0]), (0, max_width - m.shape[1])), constant_values=background)
            )
        return result

    def write_line(self, text, color, background):
        if not text:
            text = ' '
        chars = []
        for c in text:
            chars.append(self.chars[c].write(color, background))
        return np.concatenate(self.pad_height(chars, background), axis=1)

    def write(self, text, color=100, background=0):
        lines = []
        for line in text.split(b'\n'):
            lines.append(self.write_line(line, color, background))
        return np.concatenate(self.pad_all(lines, background), axis=0)

    def write_image(self, img, text, color=0, background=255):
        arr = self.write(text, color, background)
        image = Image.fromarray(arr, mode='L')
        image.save(img)


if __name__ == '__main__':
    # font = Font(r"C:\Zvika\ScummVM-dev\HebrewAdventure\sq3\patches\font.600")
    for num in [0]:  # , 3, 4, 7, 8, 30, 40, 50, 60, 70, 71, 210, 265, 340, 460, 490, 491, 492, 999]:
        font = Font(fr"C:\GOG Games\SQ6\Space Quest 6.patches\{num}.fon")
        # font.dump()
        s = b'Zvika\nHaramaty\n01234567890\nABCDEFGHIJKLMNOPQRSTUVWXYZ\nabcdefghijklmnopqrstuvwxyz'
        print(font.write(s))
        font.write_image(f'text_{num}.png', s)
        font.dump_image(f'font_{num}.png')
