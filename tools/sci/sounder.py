# spec:
# https://wiki.scummvm.org/index.php/SCI/Specifications/Sound/SCI0_Resource_Format
# https://sciprogramming.com/community/index.php?topic=2072

# create environment with all packages:
# conda create -n sounder -c conda-forge mido pyaudio wxpython python=3.10
# conda activate sounder
# pip install python-rtmidi gooey

# TODO: gooey: update widgets from each other (file chosen - change devices to play)
# TODO: info: channels (also for midi)
# TODO: sci1: choose device to save_midi
# TODO: sci0: choose device to save_midi

# TODO: maybe use pydub / ffmpeg / https://pypi.org/project/av/ to support extra digital formats
# TODO: gui: menu?
# TODO: gui: icons

# TODO: verify cue, loop in writing (sound.200)
# TODO: debug adding digital sample to SCI1 file that hadn't such
# TODO: verify converting MIDI to SND (first 10 bytes, etc.)
# TODO: The MT-32 always plays channel 9 (https://sciprogramming.com/community/index.php?topic=2074.0)
# TODO: sci0: write adlib - voices?
# TODO: early: saving with digital behaves weird

import sys
import io
import re
import time
import threading
import functools
import wave
import logging
from pathlib import Path
from enum import Flag, Enum
from copy import deepcopy
from ast import literal_eval
from glob import glob

import mido
import rtmidi  # pip install python-rtmidi
import mido.backends.rtmidi
from mido import MidiFile, MidiTrack
from mido.midifiles.tracks import _to_abstime, _to_reltime
import pyaudio

from gooey import Gooey, GooeyParser

import gooey_misc

SIERRA_SND_HEADER = b'\x84\0'
NUM_OF_CHANNELS = 16
TICKS_PER_BIT = 30

SCI1_DIGITAL_CHANNEL_MARKER = 0xfe

debug = False

# with PyInstaller, the print output isn't flushed - force it
# TODO check if can be removed, now that we're using logger
print = functools.partial(print, flush=True)


def setup_logger():
    logger = logging.getLogger('sounder')
    if debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    logger_handler = logging.StreamHandler()
    logger_handler.addFilter(lambda record: record.levelno != logging.INFO)
    logger_handler.setFormatter(logging.Formatter('%(levelname)s:%(name)s:%(message)s'))
    logger.addHandler(logger_handler)

    logger_info_handler = logging.StreamHandler(sys.stdout)
    logger_info_handler.addFilter(lambda record: record.levelno == logging.INFO)
    logger.addHandler(logger_info_handler)

    return logger


logger = setup_logger()


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
    UNKNOWN3 = 0x16  # eco quest, 185.snd
    UNKNOWN = 0xffff

    @classmethod
    def _missing_(cls, number):
        logger.warning(f"Encountered new unknown SCI1 device {hex(number)}")
        return cls(cls.UNKNOWN)


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
            except ValueError:
                logger.exception('value error. status: ' + hex(status) + ". event: " + event.hex())
    except EOFError:
        pass

    return track


def read_snd_file(p, input_version, info):
    if input_version != "AUTO_DETECT":
        return read_snd_file_with_version(p, input_version, info)
    else:
        if p.suffix == '.snd':
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
    read_le(stream, 10)  # waste offsets 34-43
    if info:
        if freq and length:
            logger.info(f'Digital sample - freq: {freq} Hz, length: {length / freq:.1f} sec ({length} bytes)')
        else:
            logger.warning(f'Digital sample - something seems wrong - freq: {freq} Hz, length: ({length} bytes)')
    data = stream.read(length)
    return {'freq': freq, 'data': data}


def read_sci1_digital(stream, info):
    prio = read_le(stream)  # unused
    freq = read_le(stream, 2)
    length = read_le(stream, 2)
    offset = read_le(stream, 2)  # from end of header
    end = read_le(stream, 2)
    stream.seek(offset)
    if info:
        logger.info(f'Digital sample - freq: {freq} Hz, length: {length / freq:.1f} sec ({length} bytes)')
    data = stream.read(length)
    return {'freq': freq, 'data': data}


def play_wave(wave):
    if wave:
        audio = pyaudio.PyAudio()
        stream = audio.open(format=audio.get_format_from_width(1),
                            channels=1,
                            rate=wave['freq'],
                            output=True)
        stream.write(wave['data'])
        stream.stop_stream()
        stream.close()
        audio.terminate()


def save_wave(wave_dict, input_file, save_file):
    if wave_dict:
        if not save_file:
            save_file = input_file + ".wav"

        with wave.open(save_file, 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(1)
            w.setframerate(wave_dict['freq'])
            w.writeframes(wave_dict['data'])
        logger.info(f'Saved {save_file}')


def read_sci0_snd_file(stream, sci0_early, info):
    digital_sample_byte = read_le(stream)
    if digital_sample_byte == 0:
        has_digital_sample = False
    elif digital_sample_byte == 2:
        has_digital_sample = True
    else:
        logger.warning(f"File has unrecognizable digital sample byte: {digital_sample_byte}")
        has_digital_sample = False

    devices = {}
    for ch in range(NUM_OF_CHANNELS):
        if has_digital_sample and ch == NUM_OF_CHANNELS - 1:
            last_non_digital_offset = read_be(stream, 2)  # note the big endian
            logger.debug(f'SCI0: digital offset: {hex(last_non_digital_offset)}')
            if last_non_digital_offset == 0:
                last_non_digital_offset = find_last_non_digital_offset(stream)
        else:
            if sci0_early:
                b = read_le(stream)
                voices = b // 16
                hardware = SCI0_Early_Devices(b % 16)
                if hardware:
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
            logger.info(f'Device {device.name} uses {devices[device]}')
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

    return {'midifile': midifile, 'devices': devices, 'wave': wave}


def read_sci1_snd_file(stream, info):
    midifile = MidiFile(ticks_per_beat=TICKS_PER_BIT)
    device_tracks = {}
    while True:
        track_type = read_le(stream)
        track_channels = []
        if track_type == 0xff:
            # end of tracks
            break
        if track_type != 0xf0:
            while True:
                channel_marker = read_le(stream)
                if channel_marker == 0xff:
                    # end of channels in track
                    device_tracks[track_type] = track_channels
                    break
                unknown_2nd = read_le(stream)
                data_offset = read_le(stream, 2)
                size = read_le(stream, 2)
                assert size > 0
                track_channels.append({
                    'data_offset': data_offset,
                    'size': size
                })

        else:
            # digital track, not supported
            logger.info("encountered digital track, not supported (also ignored by ScummVM and SCICompanion)")
            _ = read_le(stream, 6)
            assert read_le(stream) == 0xff

    devices = {}
    channels = {}
    for track in device_tracks:
        channel_nums = []
        for channel in device_tracks[track]:
            stream.seek(channel['data_offset'])
            ch = read_le(stream)
            if ch != SCI1_DIGITAL_CHANNEL_MARKER:
                ch = ch % 16 + 1
            else:
                ch = 'digital'
            channel_nums.append(ch)
            if ch not in channels:
                channels[ch] = channel
            else:
                if channels[ch] != channel:
                    raise ValueError("SCI1 channels - channel repeated with different values")
        devices[SCI1_Devices(track)] = channel_nums
        if info:
            logger.info(f'Device {SCI1_Devices(track).name} uses channels: {channel_nums}')

    wave = None
    for channel in channels.values():
        stream.seek(channel['data_offset'])
        channel_number = read_le(stream)
        if channel_number == SCI1_DIGITAL_CHANNEL_MARKER:
            assert wave is None
            wave = read_sci1_digital(stream, info)
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

    return {'midifile': midifile, 'devices': devices, 'wave': wave}


def clean_stops(messages):
    # required for SCI0, if there is digital channel - it's identified by looking for 0xFC (or 2)
    # but we might have more 0xFC-s in our file, if each track had it's own 'stop' command
    # this leaves only the last STOP (0xFC) command
    result = []
    redundant_stops = len([m for m in messages if m.type == 'stop']) - 1  # remove all but one
    stops = 0
    for msg in messages:
        if msg.type != 'stop':
            result.append(msg)
        else:
            stops += 1
            if stops > redundant_stops:
                result.append(msg)
    assert len([m for m in result if m.type == 'stop']) == 1
    return result


def save_sci0(midi_wave, input_file, save_file, is_early):
    midifile = midi_wave['midifile']
    digital = midi_wave['wave']

    # get devices information
    devices = {}
    if is_early:
        for orig_device in midi_wave['devices']:
            try:
                device = SCI0_Early_Devices[orig_device.name]
                devices[device] = [c - 1 for c in midi_wave['devices'][orig_device] if c != 'digital']
            except KeyError:
                logger.info(
                    f"SAVE SCI0 (EARLY): Ignoring device {orig_device}, doesn't have a SCI0 (EARLY) counterpart")
    else:
        for orig_device in midi_wave['devices']:
            try:
                device = SCI0_Devices[orig_device.name]
                devices[device] = [c - 1 for c in midi_wave['devices'][orig_device] if c != 'digital']
            except KeyError:
                logger.info(f"SAVE SCI0: Ignoring device {orig_device}, doesn't have a SCI0 counterpart")

    # prepare midi data first
    with io.BytesIO() as f:
        messages = mido.merge_tracks(midifile.tracks)
        if digital:
            messages = clean_stops(messages)
        for msg in messages:
            if not msg.is_meta:
                logger.debug('delay: ' + get_sierra_delay_bytes(msg.time).hex())
                logger.debug('msg:' + msg.bin().hex())
                f.write(get_sierra_delay_bytes(msg.time))
                f.write(msg.bin())
        midi_data = f.getvalue()

    if not save_file:
        save_file = input_file + ".snd"
    with open(save_file, 'wb') as f:
        f.write(SIERRA_SND_HEADER)
        # write header
        if digital:
            write_le(f, 0x2)
        else:
            write_le(f, 0x0)
        for ch in range(NUM_OF_CHANNELS):
            if is_early:
                voices = 0  # TODO
                b = voices * 16
                hw = SCI0_Early_Devices(0)
                for device in devices:
                    if ch in devices[device] and device != SCI0_Early_Devices.MT_32:
                        hw |= device
                write_le(f, b + hw.value)
            else:
                # regular SCI0
                if digital and ch == NUM_OF_CHANNELS - 1:
                    # I tried using the offset mechanism described at Ravi's spec
                    # sv.exe crashed; reading SCICompanion and ScummVM code, it seems that neither support that method
                    write_le(f, 0x0, 2)
                else:
                    write_le(f, 0)  # TODO write voices for ADLIB
                    hw = SCI0_Devices(0)
                    for device in devices:
                        if ch in devices[device]:
                            hw |= device
                    write_le(f, hw.value)

        # write midi data
        f.write(midi_data)

        # write digital
        if digital:
            # assert f.tell() - 1 == len(SIERRA_SND_HEADER) + last_non_digital_offset
            # we don't know the meaning of most of the 44 bytes header
            write_le(f, 0x0, 14)  # waste offsets 0-13
            write_le(f, digital['freq'], 2)  # write offset 14,15
            write_le(f, 0x0, 16)  # waste offsets 16-31
            write_le(f, len(digital['data']), 2)  # write offset 32,33
            write_le(f, 0x0, 10)  # waste offsets 34-43
            f.write(digital['data'])

    logger.info(f'Saved {save_file}')


def save_sci1(midi_wave, input_file, save_file):
    midifile = midi_wave['midifile']

    devices = {}

    for orig_device in midi_wave['devices']:
        try:
            device = SCI1_Devices[orig_device.name]
            channels = midi_wave['devices'][orig_device]
            devices[device] = [c if c != 'digital' else SCI1_DIGITAL_CHANNEL_MARKER + 1 for c in channels]
        except KeyError:
            logger.info(f"SAVE SCI1: Ignoring device {orig_device.name}, doesn't have a SCI1 counterpart")

    # get devices information from midi information track (if exists - probably created by us, when reading a SCI0 file)
    if not devices:
        for msg in midifile.tracks[0]:
            if msg.type == 'device_name' and msg.name.startswith('Device '):
                m = re.match(r'Device (.*) uses (\[.*)', msg.name)
                if m:
                    try:
                        device = SCI1_Devices[m.group(1)]
                        channels = literal_eval(m.group(2))
                        devices[device] = channels
                    except KeyError:
                        logger.info(f"SAVE SCI1+: Ignoring device {m.group(1)}, doesn't have a SCI1 counterpart")

    # SCI1 makes heavy use of GM - add such track if doesn't exist
    if SCI1_Devices.GM not in devices and SCI1_Devices.MT_32 in devices:
        devices[SCI1_Devices.GM] = devices[SCI1_Devices.MT_32]
        logger.info(f"SAVE SCI1+: Adding GM device, as duplication of MT-32")

    # unify all messages from all tracks; change time from delta to absolute
    messages = []
    timer = 0
    for msg in mido.merge_tracks(midifile.tracks):
        timer += msg.time
        msg.time = timer
        messages.append(msg)

    # prepare channels data, will be written to file later
    channel_offsets = {}
    channel_sizes = {}
    channel_nums = sorted(list(set([m.channel for m in messages if not m.is_realtime and not m.is_meta])))
    if midi_wave['wave'] and SCI1_DIGITAL_CHANNEL_MARKER not in channel_nums:
        channel_nums.append(SCI1_DIGITAL_CHANNEL_MARKER)
    with io.BytesIO() as channels_stream:
        for ch in channel_nums:
            channel_offsets[ch] = channels_stream.tell()
            if ch != SCI1_DIGITAL_CHANNEL_MARKER:
                write_le(channels_stream, ch)  # TODO flags
                write_le(channels_stream, 0x1)  # TODO poly and prio
                timer = 0
                for msg in messages:
                    if not msg.is_meta and (msg.is_realtime or msg.channel == ch):
                        delta = msg.time - timer
                        timer = msg.time
                        logger.debug('delay: ' + get_sierra_delay_bytes(delta).hex())
                        logger.debug('msg:' + msg.bin().hex())
                        channels_stream.write(get_sierra_delay_bytes(delta))
                        channels_stream.write(msg.bin())
            else:
                digital = midi_wave['wave']
                write_le(channels_stream, ch)  # no flags
                write_le(channels_stream, 0x0)  # prio, no poly
                write_le(channels_stream, digital['freq'], 2)
                write_le(channels_stream, len(digital['data']), 2)  # length
                write_le(channels_stream, 0x0, 2)  # offset from end of header
                write_le(channels_stream, len(digital['data']), 2)  # end of sample
                channels_stream.write(digital['data'])
            channel_sizes[ch] = channels_stream.tell() - channel_offsets[ch]
        channels_bytes = channels_stream.getvalue()

    # make devices table, if doesn't exists
    if channel_nums and not devices:
        logger.info(
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
        # write header
        for device in devices:
            write_le(f, device.value)
            try:
                device_channels = [c['ch'] - 1 for c in devices[device]]
            except TypeError:
                device_channels = [c - 1 for c in devices[device]]
            for channel in device_channels:
                write_le(f, 0x0, 2)  # unknown
                write_le(f, channel_offsets[channel] + header_size, 2)
                write_le(f, channel_sizes[channel], 2)
            write_le(f, 0xff)
        write_le(f, 0xff)
        assert f.tell() == 2 + header_size  # 2 is the SIERRA_SND_HEADER

        # write channels data
        f.write(channels_bytes)
    logger.info(f'Saved {save_file}')


def read_wav_file(input_wav):
    result = {}
    with wave.open(input_wav, 'rb') as w:
        if w.getnchannels() != 1:
            assert ValueError(
                "Currently, wave file must have 1 channel (mono); (on the fly conversion will be supported later)")
        if w.getsampwidth() != 1:
            assert ValueError("Currently, wave file must be 8-bit; (on the fly conversion will be supported later)")
        if w.getcomptype() != 'NONE':
            assert ValueError(
                "Currently, wave file must be uncompressed; (on the fly conversion will be supported later)")
        result['freq'] = w.getframerate()
        result['data'] = w.readframes(w.getnframes())
    return result


def read_input(input_file, input_version, input_wav, info):
    p = Path(input_file)
    if p.suffix.lower() == '.mid':
        midifile = read_midi_file(p)
        result = {'midifile': midifile, 'wave': None}
    elif p.suffix.lower() == '.snd' or p.stem.startswith('sound'):
        result = read_snd_file(p, input_version, info)
    else:
        raise NameError("Received unsupported file (it should start with sound. or end with .mid/.snd) " + input_file)
    if info:
        logger.info(f"Midi length: {result['midifile'].length:.1f} seconds")

    if input_wav:
        result['wave'] = read_wav_file(input_wav)
    return result


def show_progress(length):
    for i in range(round(length)):
        time.sleep(1)
        logger.info(f'seconds: {i + 1}/{length}')


def select_channels(midifile, channels):
    result = MidiFile(type=midifile.type, ticks_per_beat=midifile.ticks_per_beat)
    for orig_track in midifile.tracks:
        messages = []
        for msg in _to_abstime(orig_track):
            try:
                if msg.channel in channels:
                    messages.append(msg)
            except AttributeError:
                messages.append(msg)
        track = MidiTrack(_to_reltime(messages))
        result.tracks.append(track)
    return result


def get_midi_channels_of_device(play_device, devices):
    if play_device == 'ALL CHANNELS IN FILE':
        result = []
        for device_channels in devices.values():
            for c in device_channels:
                if c != 'digital':
                    try:
                        result.append(c['ch'] - 1)
                    except TypeError:
                        result.append(c - 1)
        return sorted(list(set(result)))

    else:
        relevant_devices = [d for d in devices if play_device in d.name]
        if not relevant_devices:
            return []
        else:
            assert len(relevant_devices) == 1
            relevant_device = devices[relevant_devices[0]]
            try:
                return [c['ch'] - 1 for c in relevant_device if c != 'digital']
            except TypeError:
                return [c - 1 for c in relevant_device if c != 'digital']


def play_midi(midi_wave, play_device, port=None, verbose=False):
    if port is None:
        port = mido.open_output()
    else:
        logger.info(f'Using {port} for MIDI playback')
        port = mido.open_output(port)

    channels = get_midi_channels_of_device(play_device, midi_wave['devices'])
    midifile = select_channels(midi_wave['midifile'], channels)

    logger.info(f'Playing {play_device}, length {midifile.length:.1f} seconds')

    if gooey_misc.gooey_enabled:
        logger.info(f'seconds: {0}/{round(midifile.length)}')
        progress_thread = threading.Thread(target=show_progress, args=(midifile.length,))
        progress_thread.start()

    for msg in midifile.play():
        if verbose:
            logger.info(msg)
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
    logger.info("Saved " + save_file)


gooey_misc.run_gooey_only_if_no_args()
gooey_misc.add_read_only_dropdown()
gooey_misc.force_english()
gooey_misc.progress_bar_dont_display_remaining_time()


# gooey_misc.args_replace_underscore_with_spaces()  # TODO: it makes FileChooser to ignore wildcards


def get_all_devices():
    devices = sorted(list(
        set([d.name for d in SCI0_Early_Devices] + [d.name for d in SCI0_Devices] + [d.name for d in SCI1_Devices])))
    devices.remove('UNKNOWN')
    devices.insert(0, 'ALL CHANNELS IN FILE')
    return devices


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
                            help="select which device to play. note: this list also shows irrelevant devices. run with '--info' to see which devices actually exist in this file")
    play_group.add_argument("--port", "-t", choices=mido.get_output_names(), widget="ReadOnlyDropdown",
                            help="select MIDI port to use, instead of the default one")

    save_group = parser.add_argument_group("Save options", )
    save_group.add_argument("--save", "-s", choices=['SCI0_EARLY', 'SCI0', 'SCI1+', 'MIDI'],
                            help="save as format (default: don't save)", widget='ReadOnlyDropdown')
    save_group.add_argument("--save_file",
                            help="saved file name (default: original name + 'snd' or + 'midi')",
                            widget="FileSaver")

    digital_group = parser.add_argument_group("Digital sample options",
                                              "Optional related to digital sample (if exists), or adding one")
    digital_group.add_argument("--input_wav",
                               help="add file's contents as digital sample, or replace existing one",
                               widget="FileChooser", gooey_options={
            'wildcard':
                'Wave files (*.wav)|*.wav|'
                # TODO: all audio files
                'All Files (*.*)|*.*',
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

    # run over all supplied input_files (list), and open all '*' expressions
    for input_file in [item for sublist in args.input_files for item in glob(sublist)]:
        if args.info:
            logger.info(f'\n{input_file}\t{args.input_version}')

        midi_wave = read_input(input_file, args.input_version, args.input_wav, args.info)

        if args.save:
            if args.save == "MIDI":
                save_midi(midi_wave['midifile'], input_file, args.save_file)

            if args.save in ["SCI0", "SCI0_EARLY"]:
                save_sci0(midi_wave, input_file, args.save_file, args.save == 'SCI0_EARLY')

            if args.save == "SCI1+":
                save_sci1(midi_wave, input_file, args.save_file)

        if args.play:
            play_midi(midi_wave, args.play_device, args.port, args.verbose)

        if args.play_wav:
            play_wave(midi_wave['wave'])

        if args.save_wav:
            save_wave(midi_wave['wave'], input_file, args.save_wav_file)


if __name__ == "__main__":
    main()
