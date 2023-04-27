import filecmp
import tempfile
from pathlib import Path
from unittest import TestCase

from sound_patch.export_sound_patch import export_adlib_patch
from sound_patch.import_sound_patch import import_adlib_patch

test_files = Path('patch_files')


def helper_adding_instrument(number):
    _, csv_file = tempfile.mkstemp()
    _, new_patch_file = tempfile.mkstemp()
    _, new_csv_file = tempfile.mkstemp()

    orig_patch = test_files / 'pq2' / 'patch.003'
    export_adlib_patch(orig_patch, csv_file)
    with open(csv_file, 'a') as file:
        file.write(
            f'{number},bakerloo-cup-alabama,6,False,0,0,6,7,0,True,1,11,27,False,False,False,1,0,0,0,38,11,3,True,2,11,8,False,True,False,1,0')

    import_adlib_patch(csv_file, new_patch_file)
    export_adlib_patch(new_patch_file, new_csv_file)

    try:
        Path(csv_file).unlink()
        Path(new_patch_file).unlink()
        Path(new_csv_file).unlink()
    except:
        pass


class Test(TestCase):
    def test_export_and_import_adlib_patch(self):
        _, csv_file = tempfile.mkstemp()
        _, new_patch_file = tempfile.mkstemp()

        for game in test_files.glob('*'):
            for orig_patch in game.glob('*'):
                export_adlib_patch(orig_patch, csv_file)
                import_adlib_patch(csv_file, new_patch_file)
                self.assertTrue(filecmp.cmp(orig_patch, new_patch_file),
                                msg=f'Adlib patch test failed for {orig_patch}')

                try:
                    Path(csv_file).unlink()
                    Path(new_patch_file).unlink()
                except:
                    pass

    def test_adding_instrument_illegal_smaller(self):
        with self.assertLogs('sounder', level='ERROR') as cm:
            helper_adding_instrument(40)
        self.assertEqual(['ERROR:sounder:Encountered illegal program number 40 after previous number 47'], cm.output)

    def test_adding_instrument_illegal_out_of_scope(self):
        with self.assertLogs('sounder', level='ERROR') as cm:
            helper_adding_instrument(190)
        self.assertEqual(['ERROR:sounder:Encountered illegal program number 190 - bigger than maximal value (189)'],
                         cm.output)

    def test_adding_instrument_to_96(self):
        helper_adding_instrument(95)

    def test_adding_instrument_to_190(self):
        helper_adding_instrument(189)
