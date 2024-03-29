import argparse
import glob
import os
import pandas as pd
import xlsxwriter
from pathlib import Path

import assembler.script_disasm
import strings_export
import messages_export
import texts_export
import vocab_export

import config


def write_excel(csvdir):
    # Sierra is using ASCII codes below 32 for special symbols.
    # the default engine, Openpyxl, refuses to cooperate with this
    # Googling revealed that xlsxwriter is less conservative about that.
    writer = pd.ExcelWriter(os.path.join(csvdir, "translation.xlsx"), engine='xlsxwriter')

    for filename in glob.glob(os.path.join(csvdir, "*.csv")):
        df_csv = pd.read_csv(filename)

        (_, f_name) = os.path.split(filename)
        # (f_shortname, _) = os.path.splitext(f_name)
        tab_name = [e for e in config.csvs_info if e[1] == f_name][0][0]

        df_csv.to_excel(writer, tab_name, index=False)

    writer.save()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter,
                                     description='Exports resources for translation',
                                     epilog='''

1. You need to work with Kawa's latest SCICompanion 
    (at lease 3.2.3.2, from http://helmet.kafuka.org/sci/SCICompanion.exe)
2. Enable Game->Properties->Manage resources as patch files->Yes
3. Script->Manage decompilation->Decompile->Yes

''')
    parser.add_argument("gamedir", help="directory containing the game files (as patches - see below)")
    parser.add_argument("csvdir", help="directory to write .csv, combined .xlsx files and assembly .sca files")
    args = parser.parse_args()

    Path(args.csvdir).mkdir(exist_ok=True)

    # first, let's make a disassembly
    asm_path = Path(args.csvdir) / 'asm' / 'orig'
    assembler.script_disasm.disasm_all(args.gamedir, asm_path)

    strings_export.strings_export(asm_path, args.csvdir)
    texts_export.texts_export(args.gamedir, args.csvdir)
    try:
        vocab_export.vocab_export(args.gamedir, args.csvdir)
    except FileNotFoundError as e:
        if Path(e.filename).stem != 'vocab':
            print("export_all.py: ", e)
    messages_export.messages_export(args.gamedir, args.csvdir)

    write_excel(args.csvdir)

