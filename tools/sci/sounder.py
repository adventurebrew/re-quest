# spec: https://wiki.scummvm.org/index.php/SCI/Specifications/Sound/SCI0_Resource_Format
# SCI1+ additions from:
# https://github.com/icefallgames/SCICompanion/blob/f1a603b48b1aa7abf94f78574a8f69a653e2ca62/SCICompanionLib/Src/Resources/Sound.cpp#L1483

# TODO: sci1: read digital sample
# TODO: sci1: write digital sample
# TODO: The MT-32 always plays channel 9, the MIDI percussion channel, regardless of whether or not the channel is flagged for the device. Other MIDI devices may also do this.
# TODO: sci0: play only specific device
# TODO: sci1: choose device to play/save_midi
# TODO: sci0: write (regular + digital)
# TODO: sci0_early: write
# TODO: verify cue, loop in writing (sound.200)
# TODO: maybe use pydub / ffmpeg / https://pypi.org/project/av/ to support extra digital formats

# TODO: logging ; add info logging for sci0 digital offset not zero
# TODO: info: channels (also for midi)
# TODO: early: register mt_32 only for existing channels
# TODO: gui: menu?
# TODO: pyinstaller

import sys
import warnings
import io
import re
import time
import threading
from pathlib import Path
from enum import Flag, Enum
from copy import deepcopy
from ast import literal_eval
import wave

import mido
import rtmidi  # pip install python-rtmidi
from mido import MidiFile, MidiTrack
import pyaudio

from gooey import Gooey, GooeyParser

import gooey_misc

SIERRA_SND_HEADER = b'\x84\0'
NUM_OF_CHANNELS = 16
TICKS_PER_BIT = 30


def read_le(stream, length=1):
    b = stream.read(length)
    if b == b'':
        raise EOFError
    return int.from_bytes(b, byteorder='little')


def read_be(stream, length=1):
    b = stream.read(length)
    if b == b'':
        raise EOFError
    return int.from_bytes(b, byteorder='big')


def write_le(stream, data, length=1):
    stream.write(data.to_bytes(length=length, byteorder='little'))


class SCI0_Early_Devices(Flag):
    ADLIB = 0x01
    PC_JR = 0x02
    SPEAKER = 0x04  # my educated guess; haven't seen it anywhere else
    CONTROL_CHANNEL = 0x08
    MT_32 = 0x80000  # it's not a Sierra value! In Sierra, MT_32 always responded


class SCI0_Devices(Flag):
    MT_32 = 0x01
    FB_01 = 0x02
    ADLIB = 0x04
    CASIO = 0x08
    PC_JR = 0x10
    SPEAKER = 0x20
    AMIGA = 0x40
    GM = 0x80


class SCI1_Devices(Enum):
    ADLIB = 0x00
    MAC = 0x06
    GM = 0x07
    UNKNOWN1 = 0x08
    GAME_BLASTER = 0x09
    UNKNOWN2 = 0x0b
    MT_32 = 0x0c
    SPEAKER = 0x12
    PC_JR = 0x13


def get_sierra_delay_bytes(delay):
    result = b''
    while delay >= 240:
        result += int.to_bytes(0xf8, length=1, byteorder='little')
        delay %= 240
    assert delay <= 0xef
    result += int.to_bytes(delay, length=1, byteorder='little')
    return result


def get_event_length(status):
    op = status // 16
    if op in [0xc, 0xd]:
        return 2
    elif op == 0xf:
        return 1
    else:
        return 3


# size=None is unlimited
def read_messages(stream, size=None):
    def read_enough():
        if size is None:
            return False
        else:
            return stream.tell() - start_point >= size

    track = MidiTrack()
    track.append(mido.MetaMessage(type='track_name', name='SIERRA_SND'))
    start_point = stream.tell()
    try:
        while not read_enough():
            delta = 0
            d = read_le(stream)
            while d == 0xf8:
                delta += 240
                d = read_le(stream)
            assert d <= 0xef
            delta += d

            # status
            d = read_le(stream)
            if d >= 0x80:
                status = d
            else:
                stream.seek(-1, io.SEEK_CUR)

            length = get_event_length(status) - 1
            event = status.to_bytes(1, byteorder='little') + stream.read(length)
            try:
                msg = mido.Message.from_bytes(event)
                msg.time = delta
                track.append(msg)
            except ValueError as e:
                print(e)
                print('value error. status: ' + hex(status) + ". event: " + event.hex())
    except EOFError:
        pass

    return track


def read_snd_file(p, input_version, info):
    stream = io.BytesIO(p.read_bytes())
    assert stream.read(2) == SIERRA_SND_HEADER
    stream = io.BytesIO(stream.read())  # chop the first 2 bytes - it's only confusing for offsets
    if input_version.startswith('SCI0'):
        return read_sci0_snd_file(stream, input_version == 'SCI0_EARLY', info)
    elif input_version == 'SCI1+':
        return read_sci1_snd_file(stream, info)
    else:
        raise NotImplementedError


def find_last_non_digital_offset(stream):
    # the digital header will come after one or two 0xfc (stop)
    orig_location = stream.tell()
    while read_le(stream) != 0xfc:
        pass
    while read_le(stream) == 0xfc:
        pass
    # now we're exactly one byte after the beginning of the header
    # the last non digital byte is one byte before the beginning of the header
    result = stream.tell() - 2
    stream.seek(orig_location, io.SEEK_SET)
    return result


def read_sci0_digital(stream, info):
    # we don't know the meaning of most of the 44 bytes header
    read_le(stream, 14)  # waste offsets 0-13
    freq = read_le(stream, 2)  # read offset 14,15
    read_le(stream, 16)  # waste offsets 16-31
    length = read_le(stream, 2)  # read offset 32,33
    read_le(stream, 10) # waste offsets 34-43
    if info:
        print(f'Digital sample - freq: {freq} Hz, length: {length/freq:.1f} sec ({length} bytes)')
    data = stream.read(length)
    return {'freq': freq, 'data': data}


def play_wave(wave):
    audio = pyaudio.PyAudio()
    stream = audio.open(format=audio.get_format_from_width(1),
                        channels=1,
                        rate=wave['freq'],
                        output=True)
    stream.write(wave['data'])
    stream.stop_stream()
    stream.close()
    audio.terminate()


def save_wave(data, freq, filename):
    with wave.open(filename, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(1)
        w.setframerate(freq)
        w.writeframes(data)


def read_sci0_snd_file(stream, sci0_early, info):
    digital_sample_byte = read_le(stream)
    if digital_sample_byte == 0:
        has_digital_sample = False
    elif digital_sample_byte == 2:
        has_digital_sample = True
    else:
        warnings.warn(f"File has unrecognizable digital sample byte: {digital_sample_byte}")
        has_digital_sample = False

    devices = {}
    for ch in range(NUM_OF_CHANNELS):
        if has_digital_sample and ch == NUM_OF_CHANNELS - 1:
            last_non_digital_offset = read_be(stream, 2)  # note the big endian
            if last_non_digital_offset == 0:
                last_non_digital_offset = find_last_non_digital_offset(stream)
        else:
            if sci0_early:
                b = read_le(stream)
                voices = b // 16
                hardware = SCI0_Early_Devices(b % 16)
                hardware |= SCI0_Early_Devices.MT_32
                if SCI0_Early_Devices.ADLIB in hardware and SCI0_Early_Devices.CONTROL_CHANNEL in hardware:
                    # according to Ravi's spec, and ScummVM adlib driver, ADLIB ignores the channel if it's also a CONTROL
                    hardware &= ~SCI0_Early_Devices.ADLIB
                possible_devices = SCI0_Early_Devices
            else:
                voices = read_le(stream)
                hardware = SCI0_Devices(read_le(stream))
                possible_devices = SCI0_Devices
            if hardware:
                for device in possible_devices:
                    if device in hardware:
                        channels = devices.get(device, [])
                        channels.append({'ch': ch + 1, 'voices': voices})
                        devices[device] = channels

    midifile = MidiFile(ticks_per_beat=TICKS_PER_BIT)
    info_track = MidiTrack()
    info_track.append(mido.MetaMessage(type='track_name', name='MIDI_SCI0_HEADER'))
    for device in devices:
        info_track.append(mido.MetaMessage(type='device_name', name=f'Device {device.name} uses {devices[device]}'))
        if info:
            print(f'Device {device.name} uses {devices[device]}')
    if len(devices.get(SCI0_Devices.SPEAKER, [])) > 1:
        sys.exit("\nERROR: Speaker has more than 1 channel; probably SCI sound version mismatch or corrupted file")
    midifile.tracks.append(info_track)

    if has_digital_sample:
        track = read_messages(stream, last_non_digital_offset - stream.tell() + 1)
        wave = read_sci0_digital(stream, info)
    else:
        track = read_messages(stream)
        wave = None
    midifile.tracks.append(track)

    return {'midifile': midifile, 'wave': wave}


def read_sci1_snd_file(stream, info):
    midifile = MidiFile(ticks_per_beat=TICKS_PER_BIT)
    device_tracks = {}
    while True:
        track_type = read_le(stream)
        channels = []
        if track_type == 0xff:
            break
        if track_type != 0xf0:
            while True:
                channel_marker = read_le(stream)
                if channel_marker == 0xff:
                    device_tracks[track_type] = channels
                    break
                unknown_2nd = read_le(stream)
                data_offset = read_le(stream, 2)
                size = read_le(stream, 2)
                assert size > 0
                channels.append({
                    'channel_marker': channel_marker,
                    'data_offset': data_offset,
                    'size': size
                })
                # TODO have we already processed this channel?

        else:
            # digital track, not supported
            _ = read_le(stream, 6)
            assert read_le(stream) == 0xff

    if info:
        for track in device_tracks:
            channel_nums = []
            for channel in device_tracks[track]:
                stream.seek(channel['data_offset'])
                channel_nums.append(read_le(stream) % 16 + 1)
            print(f'Device {SCI1_Devices(track).name} uses channels: {channel_nums}')

    # TODO treat all devices! currently taking only GM/MT32
    try:
        device_track = device_tracks[SCI1_Devices.GM.value]
    except KeyError:
        device_track = device_tracks[SCI1_Devices.MT_32.value]
    for channel in device_track:
        stream.seek(channel['data_offset'])
        channel_number = read_le(stream)
        if channel_number == 0xfe:
            warnings.warn(
                "Sound file has a digital channel; currently not supported and ignored. Contact Zvika, or raise an issue")
        else:
            number = channel_number % 16
            # TODO should we do anything with the flags, poly, and prio?
            flags = channel_number >> 4
            if number == 9:
                flags |= 2
            poly_and_prio = read_le(stream)
            poly = poly_and_prio % 16
            prio = poly_and_prio >> 4
            midtrack = read_messages(stream, channel['size'] - 2)  # we already read channel_number, poly_and_prio
            midifile.tracks.append(midtrack)

    return {'midifile': midifile, 'wave': None}


def save_sci1(midifile, input_file, save_file):
    devices = {}
    for msg in midifile.tracks[0]:
        if msg.type == 'device_name' and msg.name.startswith('Device '):
            m = re.match(r'Device (.*) uses (\[.*)', msg.name)
            if m:
                try:
                    device = SCI1_Devices[m.group(1)]
                    channels = literal_eval(m.group(2))
                    devices[device] = channels
                except KeyError:
                    print(f"SAVE SCI1+: Ignoring device {m.group(1)}, doesn't have a SCI1 counterpart")

    # unify all messages from all tracks; change time from delta to absolute
    messages = []
    timer = 0
    for msg in mido.merge_tracks(midifile.tracks):
        timer += msg.time
        msg.time = timer
        messages.append(msg)

    channel_offsets = {}
    channel_sizes = {}
    channel_nums = sorted(list(set([m.channel for m in messages if not m.is_realtime and not m.is_meta])))
    with io.BytesIO() as channels_stream:
        for ch in channel_nums:
            timer = 0
            channel_offsets[ch] = channels_stream.tell()
            # print('ch', ch, end='\t')
            write_le(channels_stream, ch)  # TODO flags
            # print('poly_prio', 1, end='\t')
            write_le(channels_stream, 0x1)  # TODO poly and prio
            for msg in messages:
                if not msg.is_meta and (msg.is_realtime or msg.channel == ch):
                    delta = msg.time - timer
                    timer = msg.time
                    # print('delay', get_sierra_delay_bytes(delta).hex())
                    # print('msg', msg.bin().hex())
                    channels_stream.write(get_sierra_delay_bytes(delta))
                    channels_stream.write(msg.bin())
            channel_sizes[ch] = channels_stream.tell() - channel_offsets[ch]
        channels_bytes = channels_stream.getvalue()

    if not devices:
        print(
            "Couldn't find devices information in first track; using arbitrary values. Contact Zvika if you wish to have control over this")
        channels = [{'ch': ch + 1} for ch in channel_nums]
        devices[SCI1_Devices.GM] = channels
        devices[SCI1_Devices.ADLIB] = channels
        devices[SCI1_Devices.SPEAKER] = [{'ch': channel_nums[0] + 1}]

    header_size = sum([1  # track type
                       + len(devices[d]) * 6  # (2 unknown, 2 offset, 2 size) for each channel
                       + 1  # ending 0xff - no more channels
                       for d in devices
                       ]
                      ) + 1  # ending 0xff - no more tracks

    if not save_file:
        save_file = input_file + ".snd"
    with open(save_file, 'wb') as f:
        f.write(SIERRA_SND_HEADER)
        for device in devices:
            write_le(f, device.value)
            device_channels = [c['ch'] - 1 for c in devices[device]]
            for channel in device_channels:
                write_le(f, 0x0, 2)  # unknown
                write_le(f, channel_offsets[channel] + header_size, 2)
                write_le(f, channel_sizes[channel], 2)
            write_le(f, 0xff)
        write_le(f, 0xff)
        assert f.tell() == 2 + header_size  # 2 is the SIERRA_SND_HEADER
        f.write(channels_bytes)
    print(f'Saved {save_file}')


def read_input(input_file, input_version, info):
    p = Path(input_file)
    if p.suffix.lower() == '.mid':
        midifile = read_midi_file(p)
        result = {'midifile': midifile, 'wave': None}
    elif p.suffix.lower() == '.snd' or p.stem.startswith('sound'):
        result = read_snd_file(p, input_version, info)
    else:
        raise NameError("Received unsupported file (it should start with sound. or end with .mid/.snd) " + input_file)
    if info:
        print(f"Midi length: {result['midifile'].length:.1f} seconds")
    return result


def show_progress(length):
    for i in range(round(length)):
        time.sleep(1)
        print(f'seconds: {i + 1}/{length}')


def play_midi(midifile, port=None, verbose=False):
    if port is None:
        port = mido.open_output()
    else:
        print(f'Using {port} for MIDI playback')
        port = mido.open_output(port)

    if gooey_misc.gooey_enabled:
        print(f'seconds: {0}/{round(midifile.length)}')
        progress_thread = threading.Thread(target=show_progress, args=(midifile.length,))
        progress_thread.start()

    for msg in midifile.play():
        if verbose:
            print(msg)
        port.send(msg)


def read_midi_file(p):
    midifile = MidiFile(p)
    for track in midifile.tracks:
        for i, msg in enumerate(track):
            if msg.is_meta and msg.type == 'text':
                try:
                    track[i] = mido.Message.from_str(msg.text)
                except:
                    pass

    return midifile


def save_midi(midifile, input_file, save_file):
    midifile_copy = deepcopy(midifile)
    for track in midifile_copy.tracks:
        for i, msg in enumerate(track):
            if msg.is_realtime or \
                    (msg.type == 'program_change' and msg.channel == 15) or \
                    (msg.type == 'control_change' and msg.control == 0x60):
                track[i] = mido.MetaMessage(type='text', text=str(msg))

    if not save_file:
        save_file = input_file + ".mid"
    midifile_copy.save(save_file)
    print("Saved " + save_file)


gooey_misc.run_gooey_only_if_no_args()
gooey_misc.add_read_only_dropdown()
gooey_misc.force_english()
gooey_misc.progress_bar_dont_display_remaining_time()


# gooey_misc.args_replace_underscore_with_spaces()  # TODO: it makes FileChooser to ignore wildcards


@Gooey(clear_before_run=True,
       progress_regex=r"^seconds: (?P<current>.*)/(?P<total>.*)$",
       progress_expr="current / total * 100",
       hide_progress_msg=True,
       timing_options={
           'show_time_remaining': True,
           'hide_time_remaining_on_complete': True,
       },
       default_size=(600, 800),
       program_description="Sierra SCI 'snd' manager - load, save and play\n(run with '--help' for command line interface)")
def main():
    parser = GooeyParser(description="Sierra SCI 'snd' manager - load, save and play",
                         epilog='GUI starts if no arguments are supplied')

    input_group = parser.add_argument_group("Input Options", )
    input_group.add_argument("input_file",
                             help="input file to load\neither SCI ('sound.*', '*.snd'), or MIDI ('*.mid')",
                             widget="FileChooser", gooey_options={
            'wildcard':
                'All supported files (*.snd;sound.*;*.mid)|*.snd;sound.*;*.mid|'
                'Sierra Sound files (*.snd;sound.*)|*.snd;sound.*|'
                'Midi Files (*.mid)|*.mid|'
                'All Files (*.*)|*.*',
        })
    input_group.add_argument("--input_version", "-i", choices=['SCI0_EARLY', 'SCI0', 'SCI1+'], default='SCI0',
                             help="sound format version. ", widget='ReadOnlyDropdown')

    play_group = parser.add_argument_group("Play Options", )
    play_group.add_argument("--play", "-p", action='store_true', help="play the input file")
    play_group.add_argument("--verbose", "-v", action='store_true', help="show midi messages as they are played")
    play_group.add_argument("--port", "-t", choices=mido.get_output_names(), widget="ReadOnlyDropdown",
                            help="select MIDI port to use, instead of the default one")

    save_group = parser.add_argument_group("Save Options", )
    save_type_group = save_group.add_mutually_exclusive_group(gooey_options={
        'title': 'Save as',
        'initial_selection': 0,
    })
    save_type_group.add_argument("--dont_save", action='store_true', help="don't save (default)", )
    save_type_group.add_argument("--save_midi", "-m", action='store_true', help="save as .mid file")
    save_type_group.add_argument("--save_sci1", "-1", action='store_true', help="save as .snd SCI1+ file")
    save_group.add_argument("--save_file",
                            help="saved file name (default: original name + 'snd' or + 'midi)",
                            widget="FileSaver")

    misc_group = parser.add_argument_group("Miscellaneous Options", )
    misc_group.add_argument("--info", "-f", action='store_true', help="print info about the file", gooey_options={
        'initial_value': True
    })
    args = parser.parse_args()

    midi_wave = read_input(args.input_file, args.input_version, args.info)

    if args.save_midi:
        save_midi(midi_wave['midifile'], args.input_file, args.save_file)

    if args.save_sci1:
        save_sci1(midi_wave, args.input_file, args.save_file)

    if args.play:
        play_midi(midi_wave['midifile'], args.port, args.verbose)
        play_wave(midi_wave['wave'])


if __name__ == "__main__":
    main()
