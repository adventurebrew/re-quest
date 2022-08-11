import io
import re
from ast import literal_eval

import mido
from mido import MidiFile, MidiTrack

from sci_common import SIERRA_SND_HEADER, TICKS_PER_BIT, SCI1_Devices, ChannelInfo
from sci_common import get_sierra_delay_bytes, read_messages
from utils import read_le, logger, write_le

SCI1_DIGITAL_CHANNEL_MARKER = 0xfe


def read_sci1_snd_file(stream, info):
    midifile = MidiFile(ticks_per_beat=TICKS_PER_BIT)
    info_track = MidiTrack()
    info_track.append(mido.MetaMessage(type='track_name', name='MIDI_SCI1_HEADER'))

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
            logger.info(
                "encountered so called 'digital track', not supported (also ignored by ScummVM and SCICompanion)")
            _ = read_le(stream, 6)
            assert read_le(stream) == 0xff

    devices = {}
    channels = {}
    for track in device_tracks:
        channels_info = []
        for channel in device_tracks[track]:
            stream.seek(channel['data_offset'])
            ch = read_le(stream)
            if ch != SCI1_DIGITAL_CHANNEL_MARKER:
                ch = ch % 16
            else:
                ch = 'digital'
            channels_info.append(ChannelInfo(num=ch, device=SCI1_Devices(track)))
            if ch not in channels:
                channels[ch] = channel
            else:
                if channels[ch] != channel:
                    logger.warning(f"SCI1 channels - channel {ch} repeated with different values")
        devices[SCI1_Devices(track)] = channels_info
        msg = f"Device {SCI1_Devices(track).name} uses channels: {[c.get_channel_user() for c in channels_info]}"
        info_track.append(mido.MetaMessage(type='device_name', name=msg))
        if info:
            logger.info(msg)
    midifile.tracks.append(info_track)

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

    return {'midifile': midifile, 'devices': devices, 'wave': wave, 'input_version': 'SCI1+'}


def save_sci1(midi_wave, input_file, save_file):
    midifile = midi_wave['midifile']

    devices = {}

    for orig_device in midi_wave['devices']:
        try:
            device = SCI1_Devices[orig_device.name]
            devices[device] = midi_wave['devices'][orig_device]
        except KeyError:
            logger.info(f"SAVE SCI1: Ignoring device {orig_device.name}, doesn't have a SCI1 counterpart")

    # TODO: move this out of here
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

    channel_messages = {}
    for ch in channel_nums:
        if ch != SCI1_DIGITAL_CHANNEL_MARKER:
            channel_messages[ch] = []
            timer = 0
            for msg in messages:
                if not msg.is_meta and (msg.is_realtime or msg.channel == ch):
                    delta = msg.time - timer
                    timer = msg.time
                    m = msg.copy()
                    m.time = delta
                    channel_messages[ch].append(m)

    for ch in channel_messages:
        channel_messages[ch] = ensure_channel_preamble(channel_messages[ch], ch)

    with io.BytesIO() as channels_stream:
        for ch in channel_nums:
            channel_offsets[ch] = channels_stream.tell()
            if ch != SCI1_DIGITAL_CHANNEL_MARKER:
                write_le(channels_stream, ch)  # TODO flags
                write_le(channels_stream, 0x1)  # TODO poly and prio
                for msg in channel_messages[ch]:
                    assert msg.is_realtime or msg.channel == ch
                    logger.debug('delay: ' + get_sierra_delay_bytes(msg.time).hex())
                    logger.debug('msg:' + msg.bin().hex())
                    channels_stream.write(get_sierra_delay_bytes(msg.time))
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
        channels = [ChannelInfo(num=ch) for ch in channel_nums]
        devices[SCI1_Devices.GM] = channels
        devices[SCI1_Devices.ADLIB] = channels
        devices[SCI1_Devices.SPEAKER] = [ChannelInfo(num=channel_nums[0])]

    # sq3, sound.016, some devices contains non existing channels - clean them
    for device in devices:
        for channel_info in devices[device]:
            if channel_info.num not in channel_nums:
                logger.info(
                    f"Device {device.name} claims to use channel {channel_info.get_channel_user()} ; but it's empty - removing from save")
                devices[device] = [d for d in devices[device] if d.num != channel_info.num]

    # add "digital track" - not sure what it does, but SQ6 has it for all sounds
    devices['digital_track'] = [None]

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
            if device != 'digital_track':
                write_le(f, device.value)
                device_channels = [c.num for c in devices[device]]
                for channel in device_channels:
                    write_le(f, 0x0, 2)  # unknown
                    write_le(f, channel_offsets[channel] + header_size, 2)
                    write_le(f, channel_sizes[channel], 2)
                write_le(f, 0xff)
            else:
                # "digital track"
                # I have no idea what it does, and what's the meaning of    0x4b    0x0     0x0     0x0     0x0     0x0
                # but 124 out of 129 sound files in SQ6 have these numbers:
                write_le(f, 0xf0)  # digital track marker
                write_le(f, 0x4b)
                write_le(f, 0x0, 5)
                write_le(f, 0xff)  # end of "channel"
        write_le(f, 0xff)
        assert f.tell() == 2 + header_size  # 2 is the SIERRA_SND_HEADER

        # write channels data
        f.write(channels_bytes)
    logger.info(f'Saved {save_file}')


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


def ensure_channel_preamble(ch_messages, ch):
    # Midi channels must start with the following events in this order:
    #  Program change
    #  Volume
    #  Pan
    # SCI apparently doesn't look at the actual midi codes, but just plucks out the values.
    program_change = None
    volume_ctrl = None
    pan_ctrl = None

    for msg in ch_messages:
        if msg.type in ['note_on', 'note_off']:
            break
        elif msg.type == 'program_change':
            program_change = msg
        elif msg.type == 'control_change' and msg.control == 7:
            volume_ctrl = msg
        elif msg.type == 'control_change' and msg.control == 10:
            pan_ctrl = msg

    if program_change is None:
        program_change = mido.Message('program_change', channel=ch, program=0)  # TODO other program?
    if volume_ctrl is None:
        volume_ctrl = mido.Message('control_change', channel=ch, control=7, value=127)
    if pan_ctrl is None:
        pan_ctrl = mido.Message('control_change', channel=ch, control=10, value=64)

    for msg in reversed([program_change, volume_ctrl, pan_ctrl]):
        try:
            ch_messages.remove(msg)
        except ValueError:
            pass
        ch_messages.insert(0, msg)

    return ch_messages
