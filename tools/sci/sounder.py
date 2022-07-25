# spec: https://wiki.scummvm.org/index.php/SCI/Specifications/Sound/SCI0_Resource_Format

# TODO: cue, loop
# TODO: read ancient snd format?
# TODO: digital sample and channel
# TODO: The MT-32 always plays channel 9, the MIDI percussion channel, regardless of whether or not the channel is flagged for the device. Other MIDI devices may also do this.
# TODO: sci0: play only specific device
# TODO: sci1: choose device to play/save_midi
# TODO: sci0: write
# TODO: sci1: write

# "C:\Users\Zvika\Documents\OLD_COMPUTER\users-zvika\Zvika\gk1_fluid.mid" --play
# "C:\Zvika\ScummVM-dev\HebrewAdventure\checking\sound.062" --play
# "C:\Zvika\ScummVM-dev\HebrewAdventure\checking\106.snd" --input_version SCI1+

import argparse
import warnings
from pathlib import Path
from enum import Flag, Enum
import io
from copy import deepcopy

import mido
import rtmidi  # pip install python-rtmidi
from mido import MidiFile, MidiTrack

SIERRA_SND_HEADER = b'\x84\0'
NUM_OF_CHANNELS = 16
TICKS_PER_BIT = 30

SCI1_DEVICE_GM = 7


def read_le(stream, length=1):
    b = stream.read(length)
    if b == b'':
        raise EOFError
    return int.from_bytes(b, byteorder='little')


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
    MT32 = 0x0c
    SPEAKER = 0x12
    PS1 = 0x13


def show_ports():
    print(mido.get_output_names())


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
    start_point = stream.tell()
    try:
        while not read_enough():
            delta = 0
            d = read_le(stream)
            while d == 0xf8:
                delta += 240
                d = read_le(stream)
            assert d <= 0xe9
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
                print('value error. previous status: ' + hex(status) + ". " + event.hex())
    except EOFError:
        pass

    return track


def read_snd_file(p, input_version, info):
    stream = io.BytesIO(p.read_bytes())
    assert stream.read(2) == SIERRA_SND_HEADER
    stream = io.BytesIO(stream.read())  # chop the first 2 bytes - it's only confusing for offsets
    if input_version == 'SCI0':
        return read_sci0_snd_file(stream, info)
    elif input_version == 'SCI1+':
        return read_sci1_snd_file(stream, info)
    else:
        raise NotImplementedError


def read_sci0_snd_file(stream, info):
    digital_sample = read_le(stream)
    if digital_sample != 0:
        warnings.warn(
            "Sound file has a digital sample; currently not supported and ignored. Contact Zvika, or raise an issue")
    channels = []
    for ch in range(NUM_OF_CHANNELS):
        voices = read_le(stream)
        hardware = SCI0_Devices(read_le(stream))
        if hardware:
            if info:
                print(f'Channel {ch} has {voices} voices; used by {hardware}')
            channels.append([ch, voices, hardware])
    midfile = MidiFile(ticks_per_beat=TICKS_PER_BIT)
    track = read_messages(stream)
    midfile.tracks.append(track)
    # TODO incorporate channels info into midfile
    return midfile


def read_sci1_snd_file(stream, info):
    midfile = MidiFile(ticks_per_beat=TICKS_PER_BIT)
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

    # TODO treat all devices! currently taking only GM
    for channel in device_tracks[SCI1_DEVICE_GM]:
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
            midtrack = read_messages(stream, channel['size'])
            midfile.tracks.append(midtrack)

    return midfile


def read_midi_file(p):
    midfile = MidiFile(p)
    for track in midfile.tracks:
        for i, msg in enumerate(track):
            if msg.is_meta and msg.type == 'text':
                try:
                    track[i] = mido.Message.from_str(msg.text)
                except:
                    pass

    return midfile


def read_input(input_file, input_version, info):
    p = Path(input_file)
    if p.suffix == '.mid':
        return read_midi_file(p)
    elif p.suffix == '.snd' or p.stem == 'sound':
        return read_snd_file(p, input_version, info)
    else:
        raise NameError("Received illegal file: " + input_file)


def play(midfile, port=None, verbose=False):
    if port is None:
        port = mido.open_output()
    else:
        print(f'Using {args.port} for MIDI playback')
        port = mido.open_output(args.port)

    for msg in midfile.play():
        if verbose:
            print(msg)
        port.send(msg)


def save_midi(midfile, input_file):
    midfile_copy = deepcopy(midfile)
    for track in midfile_copy.tracks:
        for i, msg in enumerate(track):
            if msg.is_realtime:
                track[i] = mido.MetaMessage(type='text', text=str(msg))

    filename = input_file + ".mid"
    midfile_copy.save(filename)
    print("Saved " + filename)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     description="Sierra SCI 'snd' manager - export, import and play")
    parser.add_argument("input_file", help="input file to handle (either SCI: 'sound.*', '*.snd', or MIDI: '*.mid')")
    parser.add_argument("--input_version", "-i", choices=['SCI0_EARLY', 'SCI0', 'SCI1+'], default='SCI0',
                        help="sound format version. ")
    parser.add_argument("--play", "-p", action='store_true', help="play the input file")
    parser.add_argument("--verbose", "-v", action='store_true', help="show midi messages as they are played")
    parser.add_argument("--info", "-f", action='store_true', help="prints info about the file")
    parser.add_argument("--save_midi", "-m", action='store_true', help="save as .mid file")
    parser.add_argument("--show_ports", "-s", action='store_true', help="show available MIDI ports")
    parser.add_argument("--port", "-t", help="select MIDI port to use, instead of the default one")
    args = parser.parse_args()

    if args.input_version == 'SCI0_EARLY':
        raise NotImplementedError("Early SCI0 isn't implemented yet. Contact Zvika, or raise an issue if you need this")

    if args.show_ports:
        show_ports()

    midfile = read_input(args.input_file, args.input_version, args.info)

    if args.save_midi:
        save_midi(midfile, args.input_file)

    if args.play:
        play(midfile, args.port, args.verbose)
