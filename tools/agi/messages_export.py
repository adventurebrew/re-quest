#TODO: verify that it's still working, after the changes
#TODO: e.g., messages_keys probably isn't working now that it's dict...

import argparse
import csv
import glob
import os
import re

from config import messages_csv_filename, messages_keys


def messages_export(srcdir, pattern, csvdir, ignore):
    with open(os.path.join(csvdir, messages_csv_filename), 'w', encoding='utf-8', newline='') as output_file:
        dict_writer = csv.DictWriter(output_file, fieldnames=messages_keys.values())
        dict_writer.writeheader()

        for (room, filename) in \
                sorted(
                    [(int(re.search(r'Logic(\d+).lgc', os.path.basename(f)).group(1)),
                      f)
                     for f in glob.iglob(os.path.join(srcdir, pattern))]):
            if room not in ignore:
                with open(filename) as f:
                    room = re.search(r'Logic(\d+).lgc', os.path.basename(filename)).group(1)
                    for line in f:
                        if '#message' in line:
                            r = re.search(r'#message\s+(\d+)\s+"(.*)"', line)
                            idx = r.group(1)
                            message = r.group(2).replace('\\"', '"')

                            dict_writer.writerow({
                                messages_keys['room']: room,
                                messages_keys['idx']: idx,
                                messages_keys['original']: message,
                                messages_keys['translation']: '',
                                messages_keys['comments']: '',
                            })



if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     description='Exports text messages from logic files to csv file',
                                     epilog='''
Logic files have all the texts messages (strings) at the end of the file.
This exports all these messages to a csv file, to be translated.
''')
    parser.add_argument("srcdir", help="src directory containing the logic files")
    parser.add_argument("--pattern", default='*.lgc', help="logic files pattern")
    parser.add_argument("csvdir", help="directory to write messages.csv")
    parser.add_argument("--ignore", metavar='N', type=int, nargs='+', default=(), help="logic file to be ignored (for PQ1, 105 can be ignored)")
    args = parser.parse_args()

    messages_export(args.srcdir, args.pattern, args.csvdir, args.ignore)

