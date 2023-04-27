# handles Sound patches - 'bank' of instruments and other data required by each sound device
import argparse
import csv
import io
from pathlib import Path

from sci_common import SIERRA_PATCH_HEADER
from sound_patch.patch_objects import AdlibOp, AdlibInstrument
from utils import logger, read_le


def read_gm_patch(p):
    # reads a GM patch file (usually 4.pat)
    stream = io.BytesIO(p.read_bytes())
    assert stream.read(2) == SIERRA_PATCH_HEADER
    stream = io.BytesIO(stream.read())  # chop the first 2 bytes - it's only confusing for offsets

    stream.seek(1153)
    midi_size = read_le(stream, 2)

    print('midi size is', midi_size)

    while True:
        command = read_le(stream)
        assert command >= 0x80
        print(hex(command))
        # TODO...


def read_adlib_patch(p):
    # reads an Adlib patch file (usually 3.pat)
    stream = io.BytesIO(Path(p).read_bytes())
    assert stream.read(2) == SIERRA_PATCH_HEADER
    # chop the first 2 bytes - it's only confusing for offsets
    data = stream.read()
    if len(data) == 1344:
        num_of_instruments = 48
    elif len(data) == 2690:
        num_of_instruments = 96
    elif len(data) == 5382:
        num_of_instruments = 190
    else:
        num_of_instruments = 0
        logger.error(f"Illegal Adlib patch file, of size {len(data) + 2} ; cannot read it")

    stream = io.BytesIO(data)

    result = []
    for i in range(num_of_instruments):
        if num_of_instruments == 96 and i == 48:
            stream.read(2)

        op1 = AdlibOp(op=stream.read(13))
        op2 = AdlibOp(op=stream.read(13))

        op1.waveform = read_le(stream) & 3
        op2.waveform = read_le(stream) & 3

        result.append(AdlibInstrument(op1=op1, op2=op2))

    if num_of_instruments == 190:
        # SCI1.1 and later
        result.append({'program': 'rhythm_key_map', 'id': stream.read(62).hex()})

    assert stream.read() == b''

    return result


def export_adlib_patch(patchfile, csvfile):
    data = read_adlib_patch(patchfile)
    with open(csvfile, 'w', newline='', ) as output_file:
        dict_writer = csv.DictWriter(output_file, fieldnames=['program'] + list(data[0].dict().keys()))
        dict_writer.writeheader()

        for i, instrument in enumerate(data):
            try:
                instrument.program = i
                dict_writer.writerow(instrument.dict())
            except AttributeError:
                dict_writer.writerow(instrument)


if __name__ == '__main__':
    # TODO del
    # read_gm_patch(Path(r"C:\Users\Zvika\Downloads\EQ1CD\4.pat"))

    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     description=f'Exports Adlib sound patches from SCI files (3.pat, or similar) to csv file', )
    parser.add_argument("patchfile", help="path of patch file (e.g. '../3.pat')")
    parser.add_argument("csvfile", help=f"path (including name) to write .csv file (e.g. 'adlib_patch.csv')")
    args = parser.parse_args()

    export_adlib_patch(args.patchfile, args.csvfile)
