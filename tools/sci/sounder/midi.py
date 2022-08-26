import math
import threading
import time
from copy import deepcopy

import mido
from mido import MidiFile, MidiTrack
from mido.midifiles.tracks import _to_abstime, _to_reltime

from utils import logger, get_all_channels


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
