import argparse
import csv
from pathlib import Path
from bidi.algorithm import get_display  # pip install python-bidi

from fontlib import Font


def views_import_to_images(csvdir, fontdir, imagesdir, encoding):
    with open(Path(csvdir) / 'views.csv', newline='', encoding='utf-8') as csvfile:
        data = [{k: v for k, v in row.items()}
                for row in csv.DictReader(csvfile, skipinitialspace=True)]
    imagespath = Path(imagesdir)
    for row in data:
        if row['translation'] and row['font']:
            fontfile = Path(fontdir) / f"{row['font']}.fon"
            font = Font(fontfile)
            text = get_display(row['translation']).encode(encoding)
            font.write_image(imagespath / f"translated_view_{row['view']}_loop_{row['loop']}_cel_{row['cel']}.png",
                             text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     description="Imports views from csv file - BUT CREATES IMAGE FILES", )
    parser.add_argument("csvdir", help=f"directory to read 'views.csv' from")
    parser.add_argument("fontdir", help=f"directory to read '*.fon' from")
    parser.add_argument("imagesdir", help=f"directory to write '*.png' files to")
    parser.add_argument("--encoding", default='windows-1255', help='translation encoding')
    args = parser.parse_args()

    views_import_to_images(args.csvdir, args.fontdir, args.imagesdir, args.encoding)
