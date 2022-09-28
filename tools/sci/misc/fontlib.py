# partial support...
# ripped code from 'font_mirror.py'

import io
import math
from pathlib import Path

SIERRA_FONT_HEADER = b'\x87\x00'


def read_le(stream, length=1):
    b = stream.read(length)
    if b == b'':
        # logger.debug(f'read_le: {stream.tell()}\t EOF')   #TODO
        raise EOFError
    return int.from_bytes(b, byteorder='little')


def read_at(stream, idx, length=1):
    stream.seek(idx)
    return read_le(stream, length)


def get_data(stream, width):
    num_of_bytes = math.ceil(width / 8)
    data = read_le(stream, length=num_of_bytes)
    bits = bin(data)[2:].zfill(num_of_bytes * 8)
    bits = bits[:width]
    return bits


class Char:
    def __init__(self, stream, char_code):
        self.char_code = char_code
        self.lines = []

        index = read_at(stream, 6 + char_code * 2, length=2)
        width = read_at(stream, index)
        num_of_lines = read_le(stream)
        for _ in range(num_of_lines):
            data = get_data(stream, width)
            # data = data[::-1]  # reverse (mirror) the string
            self.lines.append(data)

    def __repr__(self):
        return f"Char {hex(self.char_code)} '{chr(self.char_code)}'"

    def dump(self):
        for line in self.lines:
            print(line.replace("0", " ").replace("1", "*"))


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


if __name__ == '__main__':
    font = Font(r"C:\Zvika\ScummVM-dev\HebrewAdventure\sq3\patches\font.600")
    font = Font(r"C:\GOG Games\SQ6\Space Quest 6.patches\30.fon")
    font.dump()
