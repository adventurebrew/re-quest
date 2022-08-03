import tempfile
from unittest import TestCase

from tools.sci.sounder import *

# in order to run, please put relevant sound.* or *.snd file under 'sound files/*/*/'
# and have some 'sound files/a.mp3'

ignored_list = [
    Path(r'sound files/sci1/sq6/ignored'),
    Path(r'sound files\sci0\sq3\sound.071'),
]

test_files = Path('sound files')
audio_file = test_files / 'a.mp3'

class Test(TestCase):
    def test_read_snd_file_auto_detect(self):
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

    def test_save_sci0_early(self):
        _, save_file = tempfile.mkstemp()
        for kind in test_files.glob('*'):
            for game in kind.glob('*'):
                for p in game.glob('*'):
                    if p not in ignored_list:
                        with self.assertNoLogs('sounder', level='ERROR'):
                            midi_wave = read_snd_file(p, 'AUTO_DETECT', info=False)
                            save_sci0(midi_wave, p, save_file, is_early=True)
        try:
            Path(save_file).unlink()
        except:
            pass

    def test_save_sci0(self):
        _, save_file = tempfile.mkstemp()
        for kind in test_files.glob('*'):
            for game in kind.glob('*'):
                for p in game.glob('*'):
                    if p not in ignored_list:
                        with self.assertNoLogs('sounder', level='ERROR'):
                            midi_wave = read_snd_file(p, 'AUTO_DETECT', info=False)
                            save_sci0(midi_wave, p, save_file, is_early=False)
        try:
            Path(save_file).unlink()
        except:
            pass

    def test_save_sci1(self):
        _, save_file = tempfile.mkstemp()
        for kind in test_files.glob('*'):
            for game in kind.glob('*'):
                for p in game.glob('*'):
                    if p not in ignored_list:
                        with self.assertNoLogs('sounder', level='ERROR'):
                            midi_wave = read_snd_file(p, 'AUTO_DETECT', info=False)
                            save_sci1(midi_wave, p, save_file)
        try:
            Path(save_file).unlink()
        except:
            pass

    def test_save_midi(self):
        _, save_file = tempfile.mkstemp()
        for kind in test_files.glob('*'):
            for game in kind.glob('*'):
                for p in game.glob('*'):
                    if p not in ignored_list:
                        with self.assertNoLogs('sounder', level='ERROR'):
                            midi_wave = read_snd_file(p, 'AUTO_DETECT', info=False)
                            save_midi(midi_wave['midifile'], p, save_file)
        try:
            Path(save_file).unlink()
        except:
            pass

    def test_save_wav(self):
        _, save_file = tempfile.mkstemp()
        for kind in test_files.glob('*'):
            for game in kind.glob('*'):
                for p in game.glob('*'):
                    if p not in ignored_list:
                        with self.assertNoLogs('sounder', level='ERROR'):
                            midi_wave = read_snd_file(p, 'AUTO_DETECT', info=False)
                            save_wave(midi_wave['wave'], p, save_file)
        try:
            Path(save_file).unlink()
        except:
            pass

    def test_add_sample(self):
        _, save_file = tempfile.mkstemp()
        for kind in test_files.glob('*'):
            for game in kind.glob('*'):
                for p in game.glob('*'):
                    if p not in ignored_list:
                        with self.assertNoLogs('sounder', level='ERROR'):
                            midi_wave = read_input(p, 'AUTO_DETECT', str(audio_file.absolute()), info=False)
                            save_sci0(midi_wave, p, save_file, is_early=True)
                            save_sci0(midi_wave, p, save_file, is_early=False)
                            save_sci1(midi_wave, p, save_file)
        try:
            Path(save_file).unlink()
        except:
            pass
