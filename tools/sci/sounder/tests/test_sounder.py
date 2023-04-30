# in order to run, please put relevant sound.*, *.snd and *.mid files under 'sound files/{sci0,sci0_early,sci1,mid}/*/'
# and have some 'sound files/a.mp3'
import filecmp
import tempfile
from unittest import TestCase
from pathlib import Path

import mido

from sounder import read_input, read_snd_file
from sci0 import save_sci0
from sci1 import save_sci1
from midi import save_midi, read_midi_file
from digital import save_wave

ignored_list = [
    Path(r'sound files/sci1/sq6/ignored'),
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
                            result = read_input(p, 'AUTO_DETECT', input_digital=None, info=False)
                            # print(p, result['input_version'], result['wave'] is not None)
                            if kind.stem == 'sci0_early':
                                self.assertEqual(result['input_version'], 'SCI0_EARLY')
                            elif kind.stem == 'sci0':
                                self.assertEqual(result['input_version'], 'SCI0')
                            elif kind.stem == 'sci1':
                                self.assertEqual(result['input_version'], 'SCI1+')
                            elif kind.stem == 'mid':
                                self.assertEqual(type(result['midifile']), mido.MidiFile)
                            else:
                                self.fail()

    def test_save_sci0_early(self):
        _, save_file = tempfile.mkstemp()
        for kind in test_files.glob('*'):
            for game in kind.glob('*'):
                for p in game.glob('*'):
                    if p not in ignored_list:
                        with self.assertNoLogs('sounder', level='ERROR'):
                            midi_wave = read_input(p, 'AUTO_DETECT', input_digital=None, info=False)
                            save_sci0(midi_wave, p, save_file, is_early=True)
                            read_snd_file(Path(save_file), 'AUTO_DETECT', info=False)
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
                            midi_wave = read_input(p, 'AUTO_DETECT', input_digital=None, info=False)
                            save_sci0(midi_wave, p, save_file, is_early=False)
                            read_snd_file(Path(save_file), 'AUTO_DETECT', info=False)
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
                            midi_wave = read_input(p, 'AUTO_DETECT', input_digital=None, info=False)
                            save_sci1(midi_wave, p, save_file)
                            read_snd_file(Path(save_file), 'AUTO_DETECT', info=False)
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
                            midi_wave = read_input(p, 'AUTO_DETECT', input_digital=None, info=False)
                            save_midi(midi_wave, p, save_file, save_midi_device='ALL CHANNELS IN FILE')
                            read_midi_file(Path(save_file))
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
                            midi_wave = read_input(p, 'AUTO_DETECT', input_digital=None, info=False)
                            save_wave(midi_wave['wave'], p, save_file)
        try:
            Path(save_file).unlink()
        except:
            pass

    def test_z_add_sample(self):
        _, save_file = tempfile.mkstemp()
        for kind in test_files.glob('*'):
            for game in kind.glob('*'):
                for p in game.glob('*'):
                    if p not in ignored_list:
                        with self.assertNoLogs('sounder', level='ERROR'):
                            midi_wave = read_input(p, 'AUTO_DETECT', str(audio_file.absolute()), info=False)

                            save_sci0(midi_wave, p, save_file, is_early=True)
                            read_snd_file(Path(save_file), 'AUTO_DETECT', info=False)

                            save_sci0(midi_wave, p, save_file, is_early=False)
                            read_snd_file(Path(save_file), 'AUTO_DETECT', info=False)

                            save_sci1(midi_wave, p, save_file)
                            read_snd_file(Path(save_file), 'AUTO_DETECT', info=False)

        try:
            Path(save_file).unlink()
        except:
            pass

    def test_z_sci1_midi_sci0(self):
        # test that sci1->midi->sci0 == sci1->sci0
        self.helper_midi_in_the_middle('sci1', 'SCI1+', 'SCI0')

    def test_z_sci0_midi_sci1(self):
        # test that sci0->midi->sci1 == sci0->sci1
        # TODO it fails with sq3/sound.018
        self.helper_midi_in_the_middle('sci0', 'SCI0', 'SCI1+')

    def helper_midi_in_the_middle(self, orig_dir, orig_type, dest):
        if dest == 'SCI0':
            save_func = save_sci0
        elif dest == 'SCI1+':
            save_func = save_sci1

        _, midi_file = tempfile.mkstemp(suffix='.mid')
        _, save_file1 = tempfile.mkstemp(suffix='.snd')
        _, save_file2 = tempfile.mkstemp(suffix='.snd')
        for game in (test_files / orig_dir).glob('*'):
            for p in game.glob('*'):
                if p not in ignored_list:
                    with self.assertNoLogs('sounder', level='ERROR'):
                        print(p)

                        midi_wave = read_input(p, orig_type, input_digital=None, info=False)
                        save_func(midi_wave, p, save_file1)

                        save_midi(midi_wave, p, midi_file, save_midi_device='ALL CHANNELS IN FILE')
                        midi_wave = read_input(midi_file, orig_type, input_digital=None, info=False)
                        save_func(midi_wave, midi_file, save_file2)

                        self.assertTrue(filecmp.cmp(save_file1, save_file2),
                                        msg=f"Saving {orig_type} directly as {dest} isn't equal as saving {orig_type}->MIDI->{dest}, for  {p}")

        try:
            Path(midi_file).unlink()
            Path(save_file1).unlink()
            Path(save_file2).unlink()
        except:
            pass
