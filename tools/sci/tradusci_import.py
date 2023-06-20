import argparse
import csv
from itertools import groupby
import operator
from pathlib import Path
import sys

from sci.resource_archive.loader import load_resources
from sci.tradusci_export import (
    MESSAGE_PATTERNS,
    SIERRA_CODEPAGE,
    PATCH80,
    PATCH,
    SCI_01,
    SCI_02_B,
    SCI_02_C,
    SCI_02_D,
    SCI_05,
    SCI32_100,
    UINT16LE,
    UINT32LE,
    read_uint16le,
    read_header,
)


def write_uint16le(num):
    return UINT16LE.pack(num)

def write_uint32le(num):
    return UINT32LE.pack(num)


# Based on TraduSCI source code available at https://erolfi.wordpress.com/tradusci/
def save_msg_file(header, lines):
    output = bytearray()

    mversion = header.version_id & 0xFFFFFF00
    patch_id = PATCH if mversion == SCI32_100 else PATCH80
    output += write_uint16le(patch_id)

    output += write_uint32le(header.version_id)
    if mversion > SCI_01:
        output += write_uint16le(0)  # comments_pos
    if mversion >= SCI_05:
        output += write_uint16le(header.unk_count)

    str_count = len(lines)
    output += write_uint16le(str_count)

    unk_b_count1 = 5
    unk_b_count2 = 9
    header_size = 10

    if mversion == SCI_01:
        unk_b_count1 = 2
        unk_b_count2 = 2
        header_size = 6
    elif mversion in {SCI_02_B, SCI_02_C, SCI_02_D}:
        unk_b_count2 = 8
        header_size = 8

    for line in lines:
        if mversion == SCI_01:
            output += bytes([line['talker'], bytes.fromhex(line['padding'])[0]])
            output += write_uint16le(0)
            output += bytes.fromhex(line['padding'][1:])
        else:
            meta = bytes([int(x) for x in operator.itemgetter('noun', 'verb', 'condition', 'sequence', 'talker')(line)])
            assert len(meta) == unk_b_count1
            output += meta
            output += write_uint16le(0)
            assert len(bytes.fromhex(line['padding'])) == unk_b_count2 - unk_b_count1, (line['padding'], unk_b_count2,  unk_b_count1)
            output += bytes.fromhex(line['padding'])

        has_comments = bool(line['comment_padding'])

    for idx, line in enumerate(lines):
        currlen = len(output) - 2

        translation = line.get('translation')
        print(line)
        if translation is not None:
            output += translation.replace('\n\n', '\r\n').encode('windows-1255') + b'\0'
        else:
            output += line['text'].replace('\n\n', '\r\n').encode(SIERRA_CODEPAGE) + b'\0'

        base_pos = 2+header_size+(idx*(unk_b_count2 + 2)) + unk_b_count1
        output[base_pos:base_pos+2] = write_uint16le(currlen)


    if mversion > SCI_01:
        comment_pos = len(output) - 8
        output[6:8] = write_uint16le(comment_pos)

    if has_comments:
        if mversion == SCI_01:
            unk_b_count1 = 2
            unk_b_count2 = 0
        elif mversion in {SCI_02_B, SCI_02_C, SCI_02_D}:
            unk_b_count1 = 0
            unk_b_count2 = 0
        else:
            unk_b_count1 = 0
            unk_b_count2 = 6

        for line in lines:
            padding = bytes.fromhex(line['comment_padding'])
            assert len(padding) == unk_b_count2, (len(padding), unk_b_count2)
            output += padding[:unk_b_count1]
            output += line['comment_text'].encode(SIERRA_CODEPAGE) + b'\0'
            output += padding[unk_b_count1:]
    return bytes(output)


def import_messages(gamedir, output, encoding):
    filenames = list(load_resources(
        gamedir,
        patterns=MESSAGE_PATTERNS,
        # patches=None,
    ))

    encoding = {
        'encoding': encoding,
        'errors': 'surrogateescape',
    }

    with open(output, 'r', encoding='utf-8', errors='surrogateescape') as text_stream:
        tsv_reader = csv.DictReader(text_stream, delimiter='\t')
        grouped = groupby(tsv_reader, key=operator.itemgetter('file'))
        for tfname, group in grouped:
            basename = Path(tfname).name
            group = list(group)
            print(f'Loading messages for {basename}', file=sys.stderr)
            for fname in filenames:
                if fname.name != basename:
                    continue
                with fname.open('rb') as stream:
                    offset = 0
                    patch_id = read_uint16le(stream)

                    if patch_id in {PATCH, PATCH80}:
                        offset = 2

                    stream.seek(offset)
                    header = read_header(stream)
                    with open(fname.name, 'wb') as out:
                        out.write(save_msg_file(header, group))


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
        '-i',
        '--input',
        default='messages.tsv',
        help='csv file to export the messages to',
    )
    parser.add_argument(
        '-e',
        '--encoding',
        default=SIERRA_CODEPAGE,
        help='codepage to decode the messages',
    )
    args = parser.parse_args()

    import_messages(args.gamedir, args.input, args.encoding)