import io

import mido
from mido import MidiFile, MidiTrack

from sci_common import SIERRA_SND_HEADER, TICKS_PER_BIT, SCI0_Early_Devices, SCI0_Devices, ChannelInfo
from sci_common import get_sierra_delay_bytes, read_messages
from utils import read_le, logger, read_be, write_le, get_all_channels

NUM_OF_CHANNELS = 16


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


def read_sci0_snd_file(stream, input_version, info):
    sci0_early = input_version == 'SCI0_EARLY'
    digital_sample_byte = read_le(stream)
    logger.debug(f'read_sci0_snd_file: digital_sample_byte : {hex(digital_sample_byte)}')
    if digital_sample_byte == 0:
        has_digital_sample = False
    elif digital_sample_byte == 2:
        has_digital_sample = True
    else:
        logger.warning(f"File has unrecognizable digital sample byte: {digital_sample_byte}")
        has_digital_sample = False

    if sci0_early and has_digital_sample:
        # spec isn't clear
        # I *assume* that there isn't a digital offset in the channels
        last_non_digital_offset = find_last_non_digital_offset(stream)

    devices = {}
    for ch in range(NUM_OF_CHANNELS):
        if not sci0_early:
            if has_digital_sample and ch == NUM_OF_CHANNELS - 1:
                last_non_digital_offset = read_be(stream, 2)  # note the big endian
                logger.debug(f'read_sci0_snd_file: digital offset: {hex(last_non_digital_offset)}')
                if last_non_digital_offset == 0:
                    last_non_digital_offset = find_last_non_digital_offset(stream)
            else:
                voices = read_le(stream)
                hardware = SCI0_Devices(read_le(stream))
                possible_devices = SCI0_Devices
        else:
            # sci0_early
            b = read_le(stream)
            voices = b // 16
            hardware = SCI0_Early_Devices(b % 16)
            logger.debug(f'read_sci0_snd_file: {stream.tell()} \t : 0x{b} - voices: {voices} , hw: {hardware}')
            if hardware:
                hardware |= SCI0_Early_Devices.MT_32
            if SCI0_Early_Devices.ADLIB in hardware and SCI0_Early_Devices.CONTROL_CHANNEL in hardware:
                # according to Ravi's spec, and ScummVM adlib driver, ADLIB ignores the channel if it's also a CONTROL
                hardware &= ~SCI0_Early_Devices.ADLIB
            possible_devices = SCI0_Early_Devices

        if hardware:
            for device in possible_devices:
                if device in hardware:
                    channels = devices.get(device, [])
                    channels.append(ChannelInfo(num=ch, voices=voices))
                    devices[device] = channels

    if not sci0_early:
        for device in [SCI0_Devices.MT_32, SCI0_Devices.GM]:
            if device in devices and 9 in get_all_channels(devices) and 9 not in [c.num for c in devices[device]]:
                devices[device].append(ChannelInfo(num=9))
                logger.info(f"Adding percussion channel (10) to {device.name}")

    if not devices:
        logger.warning("No devices information found")

    midifile = MidiFile(ticks_per_beat=TICKS_PER_BIT)
    info_track = MidiTrack()
    info_track.append(mido.MetaMessage(type='track_name', name='MIDI_SCI0_HEADER'))
    for device in devices:
        msg = f"Device {device.name} uses channels {', '.join([c.get_channel_user() for c in devices[device]])} with voices {[c.voices for c in devices[device]]}"
        info_track.append(mido.MetaMessage(type='device_name', name=msg))
        if info:
            logger.info(msg)
    if len(devices.get(SCI0_Devices.SPEAKER, [])) > 1:
        raise ValueError("speaker has more than 1 channel; probably SCI sound version mismatch or corrupted file")
    midifile.tracks.append(info_track)

    if has_digital_sample:
        track = read_messages(stream, last_non_digital_offset - stream.tell() + 1)
        wave = read_sci0_digital(stream, info)
    else:
        track = read_messages(stream)
        wave = None
    midifile.tracks.append(track)

    return {'midifile': midifile, 'devices': devices, 'wave': wave, 'input_version': input_version}


def save_sci0(midi_wave, input_file, save_file, is_early):
    midifile = midi_wave['midifile']
    digital = midi_wave['wave']

    # get devices information
    devices = {}
    if is_early:
        for orig_device in midi_wave['devices']:
            try:
                device = SCI0_Early_Devices[orig_device.name]
                devices[device] = midi_wave['devices'][orig_device]
            except KeyError:
                logger.info(
                    f"SAVE SCI0 (EARLY): Ignoring device {orig_device}, doesn't have a SCI0 (EARLY) counterpart")
    else:
        for orig_device in midi_wave['devices']:
            try:
                device = SCI0_Devices[orig_device.name]
                devices[device] = midi_wave['devices'][orig_device]
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
                    if ch in [c for c in devices[device]] and device != SCI0_Early_Devices.MT_32:
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
