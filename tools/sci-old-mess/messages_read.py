#!/usr/bin/env python3

from glob import glob
import sys
import binascii
import itertools
import struct

from operator import itemgetter


def decode(bts):
    return bts.decode('cp862', 'backslashreplace').replace('"', '`')

def readcstr(f):
    return b''.join(iter(lambda: f.read(1), b'\00'))

def read_uint16le(stream):
    return int.from_bytes(stream.read(2), byteorder='little', signed=False)

def get_data(f):
    return f.read(5), read_uint16le(f), f.read(4)

def read_text_at(f, offset):
    f.seek(offset, 0)
    t = readcstr(f)
    # print(t)
    return decode(t) # .decode('cp862', 'backslashreplace')

def convert(f):
    version = read_uint16le(f)
    zeroes = read_uint16le(f)
    off = read_uint16le(f)

    something = read_uint16le(f)
    num_of_messages = read_uint16le(f)

    index = [get_data(f) for i in range(num_of_messages)]
    texts = [read_text_at(f, addr) for _, addr, _ in index]
    assert f.tell() - 6 == off
    debug = [decode(binascii.hexlify(readcstr(f))) for i in range(num_of_messages)]

    for (pre, _, post), text, deb in zip(index, texts, debug):
        yield decode(binascii.hexlify(pre)) + '\t\"' + text + '\"\t' + decode(binascii.hexlify(post)) + '\t' + deb

if __name__ == '__main__':
    if not len(sys.argv) > 1:
        print('missing arguments')
        exit(1)

    fname = sys.argv[1]
    with open(fname, 'r', encoding='cp1255') as f:
        all_lines = [line.split('\t') for line in f.readlines()]
        files = itertools.groupby(all_lines, key=itemgetter(0))
        for fname, lines in files:
            lines = list(lines)
            nlines = len(lines)

            version = struct.pack('<H', 5010)
            
            addr = 10 + nlines * 11

            something = b'\00\00'

            texts = b''
            debugs = b''
            index = b''

            # with open(f'orig/{fname}', 'rb') as orig_file:
            #     ooversion = read_uint16le(orig_file)
            #     oozeroes = read_uint16le(orig_file)
            #     oooff = read_uint16le(orig_file)
            #     something = orig_file.read(2)
            #     orig_file.seek(oooff + 6, 0)
            #     debugs = orig_file.read()

            for tname, pre, text, post, debug in lines:
                ctext = text.replace('$|~|$', '\r\n').replace('`', '"').encode('cp862') + b'\00'
                texts += ctext
                index += binascii.unhexlify(pre) + struct.pack('<H', addr) + binascii.unhexlify(post)
                addr += len(ctext)
                if debug[-1] == '\n':
                    debug = debug[:-1]
                debugs += binascii.unhexlify(debug.encode('cp862', 'backslashreplace')) + b'\00'

            # header = b'\x0f\x00' + version + b'\00\00' + struct.pack('<H', addr + 6) + something + struct.pack('<H', nlines)
            header = b'\x0f\x00' + version + b'\00\00' + struct.pack('<H', addr + 6) + b'\00\00' + struct.pack('<H', nlines)
    
            with open(f'patch/{fname}', 'wb') as out_file:
                out_file.write(header + index + texts + debugs)
