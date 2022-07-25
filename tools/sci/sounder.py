# spec: https://wiki.scummvm.org/index.php/SCI/Specifications/Sound/SCI0_Resource_Format

# TODO: cue, loop
# TODO: read new snd format
# TODO: read ancient snd format?
# TODO: digital sample
# TODO: The MT-32 always plays channel 9, the MIDI percussion channel, regardless of whether or not the channel is flagged for the device. Other MIDI devices may also do this.
# TODO: play only specific device
# TODO: --info

# "C:\Users\Zvika\Documents\OLD_COMPUTER\users-zvika\Zvika\gk1_fluid.mid" --play
# "C:\Zvika\ScummVM-dev\HebrewAdventure\checking\sound.062" --play
# "C:\Zvika\ScummVM-dev\HebrewAdventure\checking\106.snd"

import argparse
import warnings
from pathlib import Path
from enum import Flag
import io

import mido
import rtmidi  # pip install python-rtmidi
from mido import MidiFile, MidiTrack

SIERRA_SND_HEADER = b'\x84\0'
NUM_OF_CHANNELS = 16
TICKS_PER_BIT = 30


def read_le(stream, length=1):
    b = stream.read(length)
    if b == b'':
        raise EOFError
    return int.from_bytes(b, byteorder='little')


class Devices(Flag):
    MT_32 = 0x01
    FB_01 = 0x02
    ADLIB = 0x04
    CASIO = 0x08
    PC_JR = 0x10
    SPEAKER = 0x20
    AMIGA = 0x40
    GM = 0x80


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


def read_messages(stream):
    midfile = MidiFile(ticks_per_beat=TICKS_PER_BIT)
    track = MidiTrack()
    midfile.tracks.append(track)
    try:
        while True:
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
                if msg.is_realtime:
                    warnings.warn("ignoring realtime message: " + str(msg))  # TODO: add it as meta
                else:
                    track.append(msg)
            except ValueError as e:
                print(e)
                print('value error. previous status: ' + hex(status) + ". " + event.hex())
    except EOFError:
        return midfile


def read_snd_file(p, input_version):
    stream = io.BytesIO(p.read_bytes())
    assert stream.read(2) == SIERRA_SND_HEADER
    if input_version == 'SCI0':
        return read_sci0_snd_file(stream)
    elif input_version == 'SCI1+':
        return read_sci1_snd_file(stream)
    else:
        raise NotImplementedError


def read_sci0_snd_file(stream):
    digital_sample = read_le(stream)
    if digital_sample != 0:
        warnings.warn(
            "Sound file has a digital sample; currently not supported and ignored. Contact Zvika, or raise an issue")
    channels = []
    for ch in range(NUM_OF_CHANNELS):
        voices = read_le(stream)
        hardware = Devices(read_le(stream))
        if hardware:
            channels.append([ch, voices, hardware])
    midfile = read_messages(stream)
    # TODO incorporate channels info into midfile
    return midfile


def read_sci1_snd_file(idx, snd_bytes):
    # marker = snd_bytes[idx]
    # idx += 1
    # track_count = 0
    # while marker != 0xff:
    #     track_count += 1
    #     channel_marker = snd_bytes[idx]
    #     idx += 1
    #     while channel_marker != 0xff:
    #         idx += 5
    #         channel_marker = snd_bytes[idx]
    #         idx += 1
    #     marker = snd_bytes[idx]
    #     idx += 1
    #
    # #TODO ugly - get rid of previous code and the following line
    # idx = 2
    # for i in range(track_count):
    #     track_type = snd_bytes[idx]
    #     idx += 1
    while True:
        track_type = snd_bytes[idx]
        idx += 1
        if track_type != 0xf0:
            idx += 2  # 2 unknown bytes, ignoring
            data_offset = int.from_bytes(snd_bytes[idx:idx + 1], byteorder='little')
            idx += 2
            print('offset', data_offset)
            size = int.from_bytes(snd_bytes[idx:idx + 1], byteorder='little')
            idx += 2
            print('size', size)
            assert size > 0
            # TODO have we already processed this channel?

        else:
            # digital track, not supported
            idx += 6
        print(f'closing channel. last byte is: {snd_bytes[idx]}')
        idx += 1
    # tracks = []
    # while True:
    #     type = snd_bytes[idx]
    #     print(hex(type))
    #     idx += 1
    #     if type == 0xff:
    #         break
    #     if type == 0xf0:
    #         # digitial track. not supported in ScummVM, skipping
    #         idx += 6
    #         print('skipping digital track')
    #     else:
    #         raise NotImplementedError
    #         offset = int.from_bytes(snd_bytes[idx:idx + 1], byteorder='little')
    #         idx + 2
    #         print(offset)
    #         size = int.from_bytes(snd_bytes[idx:idx + 3], byteorder='little')
    #         print(size)
    #         assert size > 0
    midfile = read_messages(snd_bytes, 0x41a)
    return midfile


def read_input(input_file, input_version):
    p = Path(input_file)
    if p.suffix == '.mid':
        return MidiFile(p)
    elif p.suffix == '.snd' or p.stem == 'sound':
        return read_snd_file(p, input_version)
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
    filename = input_file + ".mid"
    midfile.save(filename)
    print("Saved " + filename)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     description="Sierra SCI 'snd' manager - export, import and play")
    parser.add_argument("input_file", help="input file to handle (either SCI: 'sound.*', '*.snd', or MIDI: '*.mid')")
    parser.add_argument("--input_version", "-i", choices=['SCI0_EARLY', 'SCI0', 'SCI1+'], default='SCI0',
                        help="sound format version. ")
    parser.add_argument("--play", "-p", action='store_true', help="play the input file")
    parser.add_argument("--verbose", "-v", action='store_true', help="show midi messages as they are played")
    parser.add_argument("--save_midi", "-m", action='store_true', help="save as .mid file")
    parser.add_argument("--show_ports", "-s", action='store_true', help="show available MIDI ports")
    parser.add_argument("--port", "-t", help="select MIDI port to use, instead of the default one")
    args = parser.parse_args()

    if args.input_version == 'SCI0_EARLY':
        raise NotImplementedError("Early SCI0 isn't implemented yet. Contact Zvika, or raise an issue if you need this")

    if args.show_ports:
        show_ports()

    midfile = read_input(args.input_file, args.input_version)

    if args.save_midi:
        save_midi(midfile, args.input_file)

    if args.play:
        play(midfile, args.port, args.verbose)
