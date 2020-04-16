from glob import glob
import sys
import binascii


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
    # if not len(sys.argv) > 1:
    #     print('missing arguments')
    #     exit(1)

    # fname = sys.argv[1]
    # with open(fname, 'rb') as f:
    #     for line in convert(f):
    #         print(fname + '\t' + line)
    
    files = glob('./*.msg')
    for fname in files:
        try:
            with open(fname, 'rb') as f:
                for line in convert(f):
                    print(fname + '\t' + line)
        except:
            raise ValueError(fname)
            exit(1)
