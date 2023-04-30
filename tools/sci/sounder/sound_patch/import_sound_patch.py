import argparse
import csv

from sci_common import SIERRA_PATCH_HEADER
from utils import logger
from sound_patch.patch_objects import AdlibInstrument


def write_adlib_patch(patchfile, instruments_dicts):
    instruments = []
    current_program = -1
    rhythm_key_map = b''
    for ins_dict in instruments_dicts:
        program = ins_dict['program']
        if program == 'rhythm_key_map':
            rhythm_key_map = bytes.fromhex(ins_dict['id'])
        elif int(program) >= 190:
            logger.error(
                f'Encountered illegal program number {ins_dict["program"]} - bigger than maximal value (189)')
        elif int(program) > current_program:
            add_empty_instruments(instruments, int(program))
            instruments.append(AdlibInstrument(dict=ins_dict))
            current_program = int(program)
        else:
            logger.error(
                f'Encountered illegal program number {ins_dict["program"]} after previous number {current_program}')

    if 1 < current_program  < 47:
        add_empty_instruments(instruments, 48)
    elif 49 < current_program  < 95:
        add_empty_instruments(instruments, 96)
    elif 97 < current_program  < 190:
        add_empty_instruments(instruments, 190)
        if not rhythm_key_map:
            logger.warning('Adding "rhythm_key_map" of zeroes. If something else is needed, contact Zvika')
            rhythm_key_map = bytes(62)


    assert len(instruments) in [48, 96, 190]  # TODO support adding instruments
    with open(patchfile, "wb") as out_file:
        out_file.write(SIERRA_PATCH_HEADER)
        for i, ins in enumerate(instruments):
            if len(instruments) == 96 and i == 48:
                out_file.write(b'\xab\xcd')
            out_file.write(bytes(ins))
        out_file.write(rhythm_key_map)


def add_empty_instruments(instruments, dest):
    for i in range(dest - len(instruments) ):
        instruments.append(AdlibInstrument())


def import_adlib_patch(csvfile, patchfile):
    with open(csvfile, newline='') as csv_f:
        instruments_dicts = [{k: v for k, v in row.items()}
                             for row in csv.DictReader(csv_f, skipinitialspace=True)]
    write_adlib_patch(patchfile, instruments_dicts)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     description=f'Imports Adlib sound patches from csv file to SCI files (3.pat, or similar)', )
    parser.add_argument("csvfile", help=f"path to read .csv file from")
    parser.add_argument("patchfile", help="path to write the patch file to (e.g. './3.pat')")
    args = parser.parse_args()

    import_adlib_patch(args.csvfile, args.patchfile)
