import argparse
from dataclasses import astuple, dataclass
import json
import struct
import sys
from typing import Optional

from sci.resource_archive.loader import load_resources


MESSAGE_PATTERNS = ["message.*", "*.msg"]
SIERRA_CODEPAGE = 'CP437'

PATCH80 = 0x008F
PATCH = 0x000F

SCI_01 = 0x00000800
SCI_02_B = 0x00000B00
SCI_02_C = 0x00000C00
SCI_02_D = 0x00000D00
SCI_05 = 0x00000F00
SCI_06 = 0x00001000
SCI32_100 = 0x00001300

TRADUSCI_SIGN = b'TraduSCI'    
TRADUSCI1_SIGN = b'TraduSCI 1.0 di Enrico Rolfi (Endroz)'
TRADUSCI2_SIGN = b'TraduSCI2 1.1 di Enrico Rolfi (Endroz)'

SIERRA = 0
OLDTRADUSCI = 1
TRADUSCI2 = 2

UINT16LE = struct.Struct('<H')
UINT32LE = struct.Struct('<I')

def read_uint16le(stream):
    return UINT16LE.unpack(stream.read(UINT16LE.size))[0]

def read_uint32le(stream):
    return UINT32LE.unpack(stream.read(UINT32LE.size))[0]

def read_until_null(stream):
    result = bytearray()
    while True:
        char = stream.read(1)
        if not char or char == b'\x00':
            break
        result.extend(char)
    return bytes(result)


def escape_quotes(msg):
    msg = msg.replace('"', '""')
    return f'"{msg}"'


@dataclass
class MessageHeader:
    version_id: int
    comment_pos: Optional[int]
    last_msg_num: Optional[int]
    phrases_count: Optional[int]


def read_header(stream):
    version_id = read_uint32le(stream)
    comment_pos = None
    last_msg_num = None
    if version_id & 0xFFFFFF00 > SCI_01:
        comment_pos = read_uint16le(stream)
    if version_id & 0xFFFFFF00 >= SCI_05:
        last_msg_num = read_uint16le(stream)
    phrases_count = read_uint16le(stream)
    return MessageHeader(version_id, comment_pos, last_msg_num, phrases_count)




# Based on TraduSCI source code available at https://erolfi.wordpress.com/tradusci/
def load_msg_file(stream):
    offset = 0
    patch_id = read_uint16le(stream)

    if patch_id in {PATCH, PATCH80}:
        offset = 2
    
    stream.seek(offset)
    header = read_header(stream)

    mversion = header.version_id & 0xFFFFFF00
    assert mversion in {SCI_01, SCI_02_B, SCI_02_C, SCI_02_D, SCI_05, SCI_06, SCI32_100}, hex(mversion)
    if mversion in {SCI_01, SCI_02_B, SCI_02_C, SCI_02_D, SCI_05} and patch_id == PATCH:
        print(f'WARNING: should not have 0x{PATCH:04X} in header for older SCI version')


    t_count = header.phrases_count
    comments = [{} for _ in range(t_count)]
    phrases = [{} for _ in range(t_count)]
    nouns = [0 for _ in range(256)]
    verbs = [0 for _ in range(256)]
    conditions = [0 for _ in range(256)]
    talkers = [0 for _ in range(256)]

    unk_b_count1 = 5
    unk_b_count2 = 9

    if mversion == SCI_01:
        unk_b_count1 = 2
        unk_b_count2 = 2
    elif mversion in {SCI_02_B, SCI_02_C, SCI_02_D}:
        unk_b_count2 = 8
    
    tradusci2_data_pos = 0

    oldpos = stream.tell()
    stream.seek((unk_b_count2 + 2) * t_count, 1)

    temp_sign = read_until_null(stream)

    tradusci_session = {}

    if temp_sign == TRADUSCI1_SIGN:
        tradusci_format = OLDTRADUSCI
        has_comments = stream.read(1)
        tradusci_session['current_string'] = read_uint16le(stream)
        tradusci_session['font_size'] = 18
    elif temp_sign == TRADUSCI2_SIGN:
        tradusci_format = TRADUSCI2
        has_comments = stream.read(1)
        tradusci_session['current_string'] = read_uint16le(stream)
        tradusci2_data_pos = read_uint32le(stream)
        tradusci_session['font_size'] = 18
        if read_uint16le(stream) == 0xF00F:
            tradusci_session['font_size'] = ord(stream.read(1))
        tradusci_session['order'] = 0  # ByIndex
        if read_uint16le(stream) == 0xE00E:
            tradusci_session['order'] = ord(stream.read(1))
        tradusci_session['window'] = b''
        if read_uint16le(stream) == 0xBAAB:
            tradusci_session['window'] = stream.read(3 + 8)

    elif temp_sign[:8] == TRADUSCI_SIGN:
        raise ValueError('newer tradusci version')
    else:
        tradusci_format = SIERRA
        tradusci_session['current_string'] = 0
        tradusci_session['font_size'] = 18

    stream.seek(oldpos)

    for i in range(t_count):
        phrases[i]['meta'] = stream.read(unk_b_count1)

        jumpvalue = read_uint16le(stream)
        oldpos = stream.tell()

        stream.seek(offset + jumpvalue)

        if tradusci_format == SIERRA:
            phrases[i]['string'] = read_until_null(stream)

        else:
            temp_str = read_until_null(stream)
            if tradusci_format == TRADUSCI2:
                jumpvalue = stream.tell()
                stream.seek(tradusci2_data_pos)

                translated = ord(stream.read(1))
                if translated:
                    if tradusci_format == TRADUSCI2:
                        stream.seek(-1, 1)

                    phrases[i]['string'] = read_until_null(stream)
                    phrases[i]['translation'] = temp_str
                else:
                    phrases[i]['string'] = temp_str

                if tradusci_format == TRADUSCI2:
                    tradusci2_data_pos = stream.tell()

        if tradusci_format == OLDTRADUSCI:
            jumpvalue = stream.tell()

        stream.seek(oldpos)
        phrases[i]['meta'] += stream.read(unk_b_count2 - unk_b_count1)

    if mversion != SCI_01:
        nouns[0] = 0  # '<generic>'
        verbs[0] = 0  # '<generic>'
        conditions[0] = 0  # '<generic>'

    if tradusci_format == TRADUSCI2:
        talkers[0] = 0  # '<generic>'
        if tradusci_format == TRADUSCI2:
            stream.seek(tradusci2_data_pos)

            try:
                temp_tag = read_uint16le(stream)
            except struct.error:
                temp_tag = 0

            if temp_tag == 0xD00D:
                for names in (nouns, verbs, conditions, talkers):
                    idx = ord(stream.read(1))
                    while idx != 0:
                        names[idx] = read_until_null(stream)
                        idx = ord(stream.read(1))
                temp_tag = read_uint16le(stream)
                if temp_tag != 0xD0D0:
                    raise ValueError(temp_tag)
            else:
                stream.seek(tradusci2_data_pos)

        rewind = stream.tell()
        if read_until_null(stream) == b'AMAP':
            raise NotImplementedError('Loaded audio map info was not implemented')
            # audmap_name = read_until_null(stream)
            # ushort = read_uint16le(stream)
            # audmap = {'id': 0, 'size': 0}

            # initoffs = tuple(stream.read(4))

            # for i in range(ushort):
            #     print(stream.read(7))
        else:
            stream.seek(rewind)

        futurebox = stream.read()
        if futurebox:
            raise ValueError(futurebox)

    if mversion > SCI_01:
        stream.seek(4 + offset)
        jumpvalue = read_uint16le(stream)
        assert jumpvalue == header.comment_pos, (jumpvalue, header.comment_pos)
        jumpvalue += 6 + offset
    
    if tradusci_format == SIERRA:
        stream.seek(0, 2)
        has_comments = jumpvalue < stream.tell()

    if has_comments:
        stream.seek(jumpvalue)
        if mversion == SCI_01:
            unk_b_count1 = 2
            unk_b_count2 = 0
        elif mversion in {SCI_02_B, SCI_02_C, SCI_02_D}:
            unk_b_count1 = 0
            unk_b_count2 = 0
        else:
            unk_b_count1 = 0
            unk_b_count2 = 6
        
        for i in range(t_count):
            comments[i]['meta'] = stream.read(unk_b_count1)
            comments[i]['string'] = read_until_null(stream)

            comments[i]['meta'] += stream.read(unk_b_count2 - unk_b_count1)

    return header, mversion, phrases, comments


def generate_rows(phrases, comments, mversion, encoding):
    for phrase, comment in zip(phrases, comments):
        noun = 0 if mversion == SCI_01 else phrase['meta'][0]
        verb = 0 if mversion == SCI_01 else phrase['meta'][1]
        condition = 0 if mversion == SCI_01 else phrase['meta'][2]
        sequence = 0 if mversion == SCI_01 else phrase['meta'][3]
        talker = phrase['meta'][0] if mversion == SCI_01 else phrase['meta'][4]
        padding = phrase['meta'][1:] if mversion == SCI_01 else phrase['meta'][5:]
        original = phrase.get('string', b'')
        translation = phrase.get('translation', b'')
        comment_padding = comment.get('meta', b'')
        comment_text = comment.get('string', b'')
        yield (
            noun,
            verb,
            condition,
            sequence,
            talker,
            padding.hex(),
            escape_quotes(original.decode(**encoding)),
            escape_quotes(translation.decode(**encoding)),
            comment_padding.hex(),
            escape_quotes(comment_text.decode(**encoding)),
        )


def extract_messages(gamedir, output, encoding, stub):
    filenames = list(load_resources(
        gamedir,
        patterns=MESSAGE_PATTERNS,
        # patches=None,
    ))

    encoding = {
        'encoding': encoding,
        'errors': 'surrogateescape',
    }

    headers = (
        'file',
        'noun',
        'verb',
        'condition',
        'sequence',
        'talker',
        'padding',
        'text',
        'translation',
        'comment_padding',
        'comment_text',
    )

    stub_info = {}
    with open(output, 'w', encoding='utf-8', errors='surrogateescape') as out:
        print(*headers, sep=',', file=out)
        for fname in filenames:
            if not (fname.stem.isnumeric() or fname.suffix.lstrip('.').isnumeric()):
                continue
            print(f'Loading messages from {fname}', file=sys.stderr)
            with fname.open('rb') as stream:
                header, mversion, phrases, comments = load_msg_file(stream)
                stub_info[fname.name] = astuple(header)
                for info in generate_rows(phrases, comments, mversion, encoding):
                    print(fname.name, *info, sep=',', file=out)
    with open(stub, 'w', encoding='utf-8') as stubfile:
        stubfile.write(json.dumps(stub_info))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description='Exports text from messages files (*.msg) to csv file',
    )
    parser.add_argument(
        'gamedir',
        help='directory containing the game files',
    )
    parser.add_argument(
        '-o',
        '--output',
        default='messages.csv',
        help='csv file to export the messages to',
    )
    parser.add_argument(
        '-e',
        '--encoding',
        default=SIERRA_CODEPAGE,
        help='codepage to decode the messages',
    )
    parser.add_argument(
        '-s',
        '--stub',
        default='stub.json',
        help='stub file for message headers',
    )
    args = parser.parse_args()

    extract_messages(args.gamedir, args.output, args.encoding, args.stub)
