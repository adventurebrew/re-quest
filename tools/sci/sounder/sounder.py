# spec:
# https://wiki.scummvm.org/index.php/SCI/Specifications/Sound/SCI0_Resource_Format
# https://sciprogramming.com/community/index.php?topic=2072

# create environment with all packages:
# conda create -n sounder -c conda-forge mido pyaudio wxpython python=3.10
# conda activate sounder
# pip install python-rtmidi gooey

# TODO: sci1: channels warning (sq6/104.snd) [channels per device]
# TODO: midi: read write devices
# TODO: gui: get rid of "ok" sounds

# TODO: license
# TODO: github: issues - templates?

# TODO: verify cue, loop in writing (sound.200)
# TODO: sci0: write adlib - voices?

# TODO: adlib player? (https://pypi.org/project/PyOPL/)
# TODO: https://github.com/nwhitehead/pyfluidsynth  ?


import io
import tempfile
import logging
import webbrowser
from pathlib import Path
from glob import glob

import mido
import mido.backends.rtmidi
import wx

from gooey import Gooey, GooeyParser, local_resource_path

import gooey_misc
from digital import play_wave, save_wave, read_wav_file, convert_audio_to_low_wav
from midi import play_midi, read_midi_file, save_midi
from sci_common import SIERRA_SND_HEADER, SCI0_Early_Devices, SCI0_Devices, SCI1_Devices
from sci0 import read_sci0_snd_file, save_sci0
from sci1 import read_sci1_snd_file, save_sci1
from utils import logger

VERSION = "0.4"


def read_snd_file(p, input_version, info):
    if input_version != "AUTO_DETECT":
        return read_snd_file_with_version(p, input_version, info)
    else:
        if p.suffix.lower() == '.snd':
            order = ['SCI1+', 'SCI0', 'SCI0_EARLY']
        else:
            order = ['SCI0', 'SCI0_EARLY', 'SCI1+']
        for version in order:
            logger.info(f'\n****   Trying {version}    *****')
            try:
                return read_snd_file_with_version(p, version, info)
            except:
                pass
        raise ValueError("Couldn't find file's version, or file is corrupted")


def read_snd_file_with_version(p, input_version, info):
    stream = io.BytesIO(p.read_bytes())
    assert stream.read(2) == SIERRA_SND_HEADER
    stream = io.BytesIO(stream.read())  # chop the first 2 bytes - it's only confusing for offsets
    if input_version.startswith('SCI0'):
        return read_sci0_snd_file(stream, input_version, info)
    elif input_version == 'SCI1+':
        return read_sci1_snd_file(stream, info)
    else:
        raise NotImplementedError


def read_input(input_file, input_version, input_digital, info):
    p = Path(input_file)
    if not p.exists():
        raise FileExistsError(f"File doesn't exist: {p.absolute()}")
    if p.suffix.lower() == '.mid':
        midifile = read_midi_file(p)
        result = {'midifile': midifile, 'wave': None}
    elif p.suffix.lower() == '.snd' or p.stem.lower().startswith('sound'):
        result = read_snd_file(p, input_version, info)
    else:
        raise NameError("Received unsupported file (it should start with sound. or end with .mid/.snd) " + input_file)
    if info:
        messages = mido.merge_tracks(result['midifile'].tracks)
        channel_nums = sorted(list(set([m.channel for m in messages if not m.is_realtime and not m.is_meta])))
        logger.info(f"Channels actually used in messages: {[c + 1 for c in channel_nums]}")
        logger.info(f"Midi length: {result['midifile'].length:.1f} seconds")

    if input_digital:
        try:
            result['wave'] = read_wav_file(input_digital)
        except:
            logger.info("Audio file isn't an 8 bit .wav file; trying to convert")
            _, temp_wav_file = tempfile.mkstemp(suffix='.wav')
            input_digital = convert_audio_to_low_wav(input_digital, temp_wav_file)
            result['wave'] = read_wav_file(input_digital)
            try:
                Path(input_digital).unlink()
            except:
                pass

    return result


def get_all_devices():
    devices = sorted(list(
        set([d.name for d in SCI0_Early_Devices] + [d.name for d in SCI0_Devices] + [d.name for d in SCI1_Devices])))
    devices.remove('UNKNOWN')
    devices.insert(0, 'ALL CHANNELS IN FILE')
    return devices


def get_sound_devices_in_file(input_file, input_version):
    p = Path(input_file)
    if p.suffix.lower() == ".mid":
        return ['ALL CHANNELS IN FILE']
    try:
        logging.disable(logging.CRITICAL)  # disable all loggers, as this check should be silent
        midi_wave = read_snd_file(p, input_version, info=False)
        logging.disable(logging.NOTSET)  # returns all loggers to normal
        return ['ALL CHANNELS IN FILE'] + [k.name for k in midi_wave['devices'].keys()]
    except:
        pass
    return get_all_devices()


gooey_misc.run_gooey_only_if_no_args()
gooey_misc.add_read_only_dropdown()
gooey_misc.force_english()
gooey_misc.progress_bar_dont_display_remaining_time()
gooey_misc.my_widget_updates(get_sound_devices_in_file)
gooey_misc.args_replace_underscore_with_spaces()
gooey_misc.add_func_to_menu()


def menu_exit(item, *args, **kwargs):
    args[0][0].EventObject.GetWindow().Close()


def html_window(item, *args, **kwargs):
    def OnLinkClicked(linkInfo):
        # by default, HtmlWindow tries to open links in itself
        # it looks bad, and not working for https
        # instead, send them to user's browser
        webbrowser.open(linkInfo.Href)

    frame = wx.Frame(parent=None, title="User Guide", size=(600, 800))
    html = wx.html.HtmlWindow(frame)
    html.OnLinkClicked = OnLinkClicked
    html.LoadPage(local_resource_path('usage.html'))
    frame.Show()


@Gooey(clear_before_run=True,
       progress_regex=r"^seconds: (?P<current>.*)/(?P<total>.*)$",
       progress_expr="current / total * 100",
       hide_progress_msg=True,
       timing_options={
           'show_time_remaining': True,
           'hide_time_remaining_on_complete': True,
       },
       show_stop_warning=False,
       default_size=(600, 800),
       program_name='Sounder',
       program_description="Sierra SCI 'snd' manager - load, save and play\n(run with '--help' for command line interface)",
       image_dir=local_resource_path('misc'),
       menu=[
           # new menu group
           {'name': 'File',
            'items': [
                # new menu item
                {
                    'type': 'Link',
                    'menuTitle': 'Report an issue, or suggest a feature',
                    'url': 'https://github.com/adventurebrew/re-quest/issues'
                },
                # new menu item
                {
                    'type': 'Function',
                    'menuTitle': 'Exit',
                    'func': menu_exit,
                }
            ]},
           # new menu group
           {'name': 'Help',
            'items': [
                # new menu item
                {
                    'type': 'Function',
                    'menuTitle': "User Guide",
                    'func': html_window,
                },
                # new menu item
                {
                    'type': 'AboutDialog',
                    'menuTitle': 'About',
                    'name': 'Sounder',
                    'description': "Sierra SCI 'snd' manager",
                    'version': VERSION,
                    'copyright': '2022',
                    'website': 'https://github.com/adventurebrew/re-quest/tools/sci/sounder',
                    # 'license': 'MIT'
                    'developer': 'Zvika Haramaty',
                },
            ]
            }]
       )
def main():
    parser = GooeyParser(description="Sierra SCI 'snd' manager - load, save and play",
                         epilog='GUI starts if no arguments are supplied')

    input_group = parser.add_argument_group("Input options", )
    input_group.add_argument("input_files",
                             help="input file(s) to load;\neither SCI ('sound.*', '*.snd'), or MIDI ('*.mid')",
                             nargs='+',
                             widget="MultiFileChooser", gooey_options={
            'wildcard':
                'All supported files (*.snd;sound.*;*.mid)|*.snd;sound.*;*.mid|'
                'Sierra Sound files (*.snd;sound.*)|*.snd;sound.*|'
                'Midi Files (*.mid)|*.mid|'
                'All Files (*.*)|*.*',
        })
    input_group.add_argument("--input_version", "-i", choices=['AUTO_DETECT', 'SCI0_EARLY', 'SCI0', 'SCI1+'],
                             default='AUTO_DETECT',
                             help="sound format version", widget='ReadOnlyDropdown')

    play_group = parser.add_argument_group("Play options", )
    play_group.add_argument("--play", "-p", action='store_true', help="play the music from input file")
    play_group.add_argument("--verbose", "-v", action='store_true', help="show midi messages as they are played")
    play_group.add_argument("--play_device", choices=get_all_devices(), widget="ReadOnlyDropdown",
                            default='ALL CHANNELS IN FILE',
                            help="select which device to play")
    play_group.add_argument("--port", "-t", choices=mido.get_output_names(), widget="ReadOnlyDropdown",
                            help="select MIDI port to use, instead of the default one")

    save_group = parser.add_argument_group("Save options", )
    save_group.add_argument("--save", "-s", choices=['SCI0_EARLY', 'SCI0', 'SCI1+', 'MIDI'],
                            help="save as format (default: don't save)", widget='ReadOnlyDropdown')
    save_group.add_argument("--save_file",
                            help="saved file name (default: original name + 'snd' or + 'midi')",
                            widget="FileSaver")
    save_group.add_argument("--save_midi_device", choices=get_all_devices(), widget="ReadOnlyDropdown",
                            default='ALL CHANNELS IN FILE',
                            help="if saving as .mid, select which device's channels to save")

    digital_group = parser.add_argument_group("Digital sample options",
                                              "Optional related to digital sample (if exists), or adding one")
    digital_group.add_argument("--input_digital",
                               help="add file's contents as digital sample, or replace existing one (can be any audio/video file)",
                               widget="FileChooser", gooey_options={
            'wildcard':
                'All Files (*.*)|*.*|'
                'Wave files (*.wav)|*.wav',
            # TODO: all audio files?
        })
    digital_group.add_argument("--play_wav", action='store_true', help="play the digital sample")
    digital_group.add_argument("--save_wav", action='store_true', help="save the digital sample as .wav file")
    digital_group.add_argument("--save_wav_file",
                               help="digital sample saved file name (default: original name + 'wav')",
                               widget="FileSaver")

    misc_group = parser.add_argument_group("Miscellaneous options", )
    misc_group.add_argument("--info", "-f", action='store_true', help="print info about the file", gooey_options={
        'initial_value': True
    })
    args = parser.parse_args()

    input_files = []
    for file in args.input_files:
        if '*' in file:
            input_files.extend(glob(file))
        else:
            input_files.append(file)

    for input_file in input_files:
        if args.info:
            logger.info(f'\n{input_file}\t{args.input_version}')

        midi_wave = read_input(input_file, args.input_version, args.input_digital, args.info)

        if args.save:
            if args.save == "MIDI":
                save_midi(midi_wave, input_file, args.save_file, args.save_midi_device)

            if args.save in ["SCI0", "SCI0_EARLY"]:
                save_sci0(midi_wave, input_file, args.save_file, args.save == 'SCI0_EARLY')

            if args.save == "SCI1+":
                save_sci1(midi_wave, input_file, args.save_file)

        if args.play:
            play_midi(midi_wave, args.play_device, args.port, args.verbose, gooey_enabled=gooey_misc.gooey_enabled)

        if args.play_wav:
            play_wave(midi_wave['wave'])

        if args.save_wav:
            save_wave(midi_wave['wave'], input_file, args.save_wav_file)


if __name__ == "__main__":
    main()
