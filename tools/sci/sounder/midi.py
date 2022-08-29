import math
import threading
import time
import re
from copy import deepcopy
from ast import literal_eval

import mido
from mido import MidiFile, MidiTrack
from mido.midifiles.tracks import _to_abstime, _to_reltime

from utils import logger, get_all_channels
from sci_common import SCI1_Devices, ChannelInfo


def is_regular_msg(m):
    return not m.is_realtime and not m.is_meta and m.type != 'sysex'


def get_midi_channels_of_device(play_device, devices, ):
    if play_device == 'ALL CHANNELS IN FILE':
        return get_all_channels(devices)
    else:
        relevant_devices = [d for d in devices if play_device in d.name]
        if not relevant_devices:
            return []
        else:
            assert len(relevant_devices) == 1
            relevant_device = devices[relevant_devices[0]]
            return [c.num for c in relevant_device if c != 'digital']


def select_channels_from_all_tracks(midifile, channels):
    result = MidiFile(type=1, ticks_per_beat=midifile.ticks_per_beat)
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


def select_channels_for_device(midi_wave, device):
    midifile = midi_wave['midifile']
    if device == 'ALL CHANNELS IN FILE':
        return midifile
    elif midifile.tracks[0].name == 'MIDI_SCI1_HEADER':
        result = MidiFile(type=1, ticks_per_beat=midifile.ticks_per_beat)
        result.tracks = [t for t in midifile.tracks if device in t.name or t.name == 'MIDI_SCI1_HEADER']
        return result
    else:
        channels = get_midi_channels_of_device(device, midi_wave['devices'])
        return select_channels_from_all_tracks(midifile, channels)


def play_midi(midi_wave, play_device, port=None, verbose=False, gooey_enabled=False):
    if port is None:
        port = mido.open_output()
    else:
        logger.info(f'Using {port} for MIDI playback')
        port = mido.open_output(port)

    midifile = select_channels_for_device(midi_wave, play_device)

    logger.info(f'Playing {play_device}, length {midifile.length:.1f} seconds')

    if gooey_enabled:
        logger.info(f'seconds: {0}/{math.ceil(midifile.length)}')
        progress_thread = threading.Thread(target=show_progress, args=(midifile.length,))
        progress_thread.start()

    for msg in midifile.play():
        if verbose:
            logger.info(msg)
        port.send(msg)


def get_midi_devices(midifile):
    devices = {}
    # get devices information from midi information track (if exists - probably created by us, when reading a SCI0 file)
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

    if not devices:
        # make devices table, if devices information not found in midi file
        channel_nums = sorted(list(set([m.channel for m in mido.merge_tracks(midifile.tracks) if is_regular_msg(m)])))
        if channel_nums:
            logger.info(
                "Couldn't find devices information in first track; using arbitrary values. Contact Zvika if you wish to have control over this")
            channels = [ChannelInfo(num=ch) for ch in channel_nums]
            devices[SCI1_Devices.GM] = channels
            devices[SCI1_Devices.ADLIB] = channels
            devices[SCI1_Devices.SPEAKER] = [ChannelInfo(num=channel_nums[0])]

    return devices


def read_midi_file(p):
    midifile = MidiFile(p)
    for track in midifile.tracks:
        for i, msg in enumerate(track):
            if msg.is_meta and msg.type == 'text':
                try:
                    track[i] = mido.Message.from_str(msg.text)
                except:
                    pass

    return {'midifile': midifile, 'wave': None, 'devices': get_midi_devices(midifile)}


def save_midi(midi_wave, input_file, save_file, save_midi_device):
    midifile = select_channels_for_device(midi_wave, save_midi_device)

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


def show_progress(length):
    for i in range(round(length)):
        time.sleep(1)
        logger.info(f'seconds: {i + 1}/{length}')
