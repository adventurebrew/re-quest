from unittest import TestCase

from tools.sci.sounder import *

ignored_list = [
    Path(r'sound files\sci0\sq3\sound.071'),
]


class Test(TestCase):
    def test_read_snd_file_auto_detect(self):
        logging.disable(logging.WARNING)
        test_files = Path('sound files')
        for kind in test_files.glob('*'):
            for game in kind.glob('*'):
                for p in game.glob('*'):
                    if p not in ignored_list:
                        with self.assertNoLogs('sounder', level='ERROR'):
                            result = read_snd_file(p, 'AUTO_DETECT', info=False)
                            # print(p, result['input_version'], result['wave'] is not None)
                            if kind.stem == 'sci0_early':
                                self.assertEqual(result['input_version'], 'SCI0_EARLY')
                            elif kind.stem == 'sci0':
                                self.assertEqual(result['input_version'], 'SCI0')
                            elif kind.stem == 'sci1':
                                self.assertEqual(result['input_version'], 'SCI1+')
                            else:
                                self.fail()
