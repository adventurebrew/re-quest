# spec: https://wiki.scummvm.org/index.php/SCI/Specifications/Sound/SCI0_Resource_Format

# TODO: cue, loop
# TODO: read midi file as input
# TODO: read new snd format
# TODO: read ancient snd format?
# TODO: digital sample
# TODO: The MT-32 always plays channel 9, the MIDI percussion channel, regardless of whether or not the channel is flagged for the device. Other MIDI devices may also do this.
# TODO: play only specific device

# "C:\Users\Zvika\Documents\OLD_COMPUTER\users-zvika\Zvika\gk1_fluid.mid" --play
# "C:\Zvika\ScummVM-dev\HebrewAdventure\checking\sound.062"
# "C:\Zvika\ScummVM-dev\HebrewAdventure\checking\106.snd"

import argparse
import warnings
from pathlib import Path
from enum import Flag
import time

from sorcery import dict_of
import mido
import rtmidi  # pip install python-rtmidi
from mido import MidiFile

SIERRA_SND_HEADER = b'\x84\0'
NUM_OF_CHANNELS = 16
TICKS_PER_SECOND = 1 / 60


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


def read_snd_file(p):
    idx = 0
    snd_bytes = p.read_bytes()
    assert snd_bytes[:2] == SIERRA_SND_HEADER
    idx += 2
    digital_sample = snd_bytes[idx]
    if digital_sample != 0:
        warnings.warn(
            "Sound file has a digital sample; currently not supported and ignored. Contact Zvika, or raise an issue")
    idx += 1
    channels = []
    for ch in range(NUM_OF_CHANNELS):
        voices = snd_bytes[idx]
        hardware = Devices(snd_bytes[idx + 1])
        idx += 2
        if hardware:
            channels.append(dict_of(ch, voices, hardware))
    for ch in channels:
        print(ch)
    messages = []
    try:
        while True:
            delta = 0
            while snd_bytes[idx] == 0xf8:
                delta += 240
                idx += 1
            assert snd_bytes[idx] <= 0xe9
            delta += snd_bytes[idx]
            idx += 1

            # status
            if snd_bytes[idx] >= 0x80:
                status = snd_bytes[idx]
                idx += 1
            length = get_event_length(status) - 1
            event = status.to_bytes(1, byteorder='little') + snd_bytes[idx:idx + length]
            try:
                msg = mido.Message.from_bytes(event)
                msg.time = delta
                # print(msg)
                messages.append(msg)
            except ValueError as e:
                print(e)
                print('value error. previous status: ' + hex(status) + ". " + snd_bytes[idx:idx + length].hex())
            idx += length
    except IndexError:
        return dict_of(channels, messages)


def read_input(input_file):
    p = Path(input_file)
    if p.suffix == '.mid':
        return MidiFile(p)
    elif p.suffix == '.snd' or p.stem == 'sound':
        return read_snd_file(p)
    else:
        raise NameError("Received illegal file: " + input_file)


def play(data):
    # to play MIDI file data:
    # for msg in data.play():
    #     print(msg)
    #     port.send(msg)
    for msg in data['messages']:
        time.sleep(msg.time * TICKS_PER_SECOND)
        print(msg)
        port.send(msg)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     description="Sierra SCI 'snd' manager - export, import and play")
    parser.add_argument("input_file", help="input file to handle (either SCI: 'sound.*', '*.snd', or MIDI: '*.mid')")
    parser.add_argument("--play", "-p", action='store_true', help="play the input file")
    parser.add_argument("--show_ports", "-s", action='store_true', help="show available MIDI ports")
    parser.add_argument("--port", "-t", help="select MIDI port to use, instead of the default one")
    args = parser.parse_args()

    if args.show_ports:
        show_ports()

    if args.port:
        print(f'Using {args.port} for MIDI playback')
        port = mido.open_output(args.port)
    else:
        port = mido.open_output()

    data = read_input(args.input_file)

    if args.play:
        play(data)
