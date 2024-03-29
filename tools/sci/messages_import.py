# based on http://sciprogramming.com/community/index.php?topic=1986.msg14363#msg14363
# also, CP437 is assumed, based on http://sciprogramming.com/community/index.php?topic=1790.msg11815#msg11815

import argparse
import csv
import io
import os
import binascii

import config

SIERRA_MESSAGE_HEADER = b'\x8f\00'
TRADUSCI_MESSAGE_HEADER = b'\x0f\00'
SIERRA_CODEPAGE = 'CP437'


def error(s):
    import sys
    print("ERROR: ", s)
    sys.exit(1)


def read_le(l, idx):
    return l[idx] + l[idx + 1] * 256


def update_msg(original, entries):
    assert bytes(original[:2]) in {SIERRA_MESSAGE_HEADER, TRADUSCI_MESSAGE_HEADER}, bytes(original[:2])
    lob = original[2:]
    index = 0
    version = read_le(lob, index)
    index += 2

    # pad bytes
    index += 2

    # Kawa's taxonomy :-)
    if version <= 2101:
        kind = "lame"
    elif version <=3411:
        kind = "ok"
    else:
        kind = "best"

    if kind == "ok":
        index += 2
    elif kind == "best":
        index += 4

    amount = read_le(lob, index)
    index += 2
    assert amount == len(entries)

    padding_size = 0
    if kind == 'ok':
        # 3 bytes padding
        padding_size = 3
    if kind == 'best':
        # 4 bytes of references - currently ignored
        padding_size = 4

    with io.BytesIO() as ostr, io.BytesIO() as mstr:
        offs = []
        entry_size = 4 if kind == 'lame' else 7 + padding_size
        base = index + entry_size * amount
        extra = base + 2
        ostr.write(SIERRA_MESSAGE_HEADER + lob[:index])
        for entry in entries:
            offs.append(mstr.tell() + base)
            message = entry[config.messages_keys['translation']].encode('windows-1255')
            origm = entry[config.messages_keys['original']].encode(SIERRA_CODEPAGE)
            if not message:
                message = origm
            mstr.write(message + b'\0')
            extra += len(origm) + 1
        for idx, (off, entry) in enumerate(zip(offs, entries)):
            if kind in ['ok', 'best']:
                keys = [config.messages_keys[x] for x in ('noun', 'verb', 'condition', 'sequence', 'talker')]
                index_entry = (
                    bytes([my_int(entry[key]) for key in keys]) +
                    off.to_bytes(2, byteorder='little', signed=False) +
                    binascii.unhexlify(entry[config.messages_keys['padding']])
                )
            else:
                keys = [config.messages_keys[x] for x in ('noun', 'verb')]
                index_entry = (
                    bytes([my_int(entry[key]) for key in keys]) +
                    off.to_bytes(2, byteorder='little', signed=False)
                )
            ostr.write(index_entry)
            # assert original.startswith(ostr.getvalue()), (
            #     idx,
            #     off,
            #     entry,
            #     index_entry,
            #     original[index + 11 * idx: index + 12 * idx]
            # )
        ostr.write(mstr.getvalue())
        # assert extra == ostr.tell(), (extra, ostr.tell())
        # assert ostr.getvalue() == original[:extra], (original[:extra], ostr.getvalue())
        return ostr.getvalue() + original[extra:]


def my_int(s):
    if s:
        return int(float(s))
    else:
        return s


def messages_import(csvdir, input_game_dir, output_game_dir):
    with open(os.path.join(csvdir, config.messages_csv_filename), newline='', encoding='utf-8-sig') as csvfile:
        texts = [{k: v for k, v in row.items()}
                 for row in csv.DictReader(csvfile, skipinitialspace=True)]
    rooms = sorted(list(set([my_int(entry[config.messages_keys['room']]) for entry in texts if entry[config.messages_keys['room']]])))
    for room in rooms:
        entries = [entry for entry in texts if my_int(entry[config.messages_keys['room']]) == room]

        # if set([entry[config.messages_keys['translation']] for entry in entries]) == {''}:
        #     # there is no translated entry, no need to do anything, skip this room
        #     continue

        # print(room)

        filename = f"{room}.MSG"
        orig_filename = os.path.join(input_game_dir, filename)
        patch_filename = os.path.join(output_game_dir, filename)

        with open(orig_filename, 'rb') as f:
            original = f.read()

        content = update_msg(original, entries)
        # assert content == original
        with open(patch_filename, 'wb') as output:
            output.write(content)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     description='Imports text messages from csv file to messages files (*.msg)',)
    parser.add_argument("csvdir", help=f"directory to read {config.texts_csv_filename} from")
    parser.add_argument("input_game_dir", help="directory containing CLEAN game dir (probably used for 'export_all') - won't be modified")
    parser.add_argument("output_game_dir", help="copy of 'input_game_dir', that will be modified by this script, and manually recompiled in SCICompanion")
    args = parser.parse_args()

    messages_import(args.csvdir, args.input_game_dir, args.output_game_dir)
