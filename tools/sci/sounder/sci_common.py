import re
import io
from enum import Flag, Enum

import mido
from mido import MidiTrack

from utils import read_le, logger

SIERRA_SND_HEADER = b'\x84\0'
SIERRA_PATCH_HEADER = b'\x89\0'
TICKS_PER_BIT = 30


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
    # my notes are from SQ6 or SQ1VGA drivers disassemblies (unless stated otherwise)
    ADLIB = 0x00  # verified(sq6); also Pro AudioSpectrum(sq6); also SB(sq1); also MS Windows Sound System (sq5)
    # According to SCI16\INTERP\SOUND.C line 73, maybe AMIGA is 0x05 ; I'm still waiting to see such channel in practice...
    MAC = 0x06  # scummvm amigamac1.cpp (getPlayId())
    GM = 0x07  # verified(sq6) ; also GMGUS.DRV (Sierra aftermarket)
    UNKNOWN1 = 0x08
    GAME_BLASTER = 0x09  # verified(sq1)
    UNKNOWN2 = 0x0b
    MT_32 = 0x0c  # verified(sq6)
    SPEAKER = 0x12  # verified(sq1)
    PC_JR = 0x13  # verified(sq1 - tandy3v)
    UNKNOWN3 = 0x16  # eco quest, 185.snd   ; it's FMTOWNS, according to ScummVM, also common in KQ5 FMTOWNS
    UNKNOWN = 0xffff

    @classmethod
    def _missing_(cls, number):
        logger.warning(f"Encountered new unknown SCI1 device {hex(number)}")
        return cls(cls.UNKNOWN)


class ChannelInfo:
    def __init__(self, num, voices=None, devices=[], data_offset=None, size=None):
        self.num = num
        # voices is for SCI0 (Adlib)
        self.voices = voices
        # from here it's SCI1
        self.devices = devices
        self.data_offset = data_offset
        self.size = size
        self.repeated = 0

    def from_midi(self, midi_str, DevicesEnum):
        # init self according to info in midi_str
        m = re.match(r'Channel (.*), used by (.*)', midi_str)
        self.num = int(m.group(1).rstrip("'")) - 1
        self.devices = [DevicesEnum[d] for d in m.group(2).split(', ')]
        return self

    def __lt__(self, other):
        if self.num != other.num:
            return self.num < other.num
        elif self.device and other.device:
            return self.device.name < other.device.name
        else:
            return True  # arbitrary value, it doesn't matter

    def __repr__(self):
        result = f'Channel {self.num}'
        if self.devices:
            result += f' of {[d.name for d in self.devices]}'
        if self.voices:
            result += f' (using {self.voices} voices)'
        return result

    def get_channel_user(self):
        # internally channels start at 0; from user's perspective they start st 1
        if self.num == 'digital':
            result = 'digital'
        else:
            result = str(self.num + 1)
        result += "'" * self.repeated
        return result

    def get_key(self):
        if self.data_offset and self.size:
            return (self.num, self.data_offset, self.size)
        else:
            raise NotImplementedError


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


def read_messages(stream, size=None, name='SIERRA_SND'):
    # size=None is unlimited
    def read_enough():
        if size is None:
            return False
        else:
            return stream.tell() - start_point >= size

    track = MidiTrack()
    track.append(mido.MetaMessage(type='track_name', name=name))
    start_point = stream.tell()
    try:
        while not read_enough():
            delta = 0
            d = read_le(stream)
            logger.debug(f"read_messages: {stream.tell()}\t: d: {hex(d)}")
            while d == 0xf8:
                delta += 240
                d = read_le(stream)
                logger.debug(f"read_messages: {stream.tell()}\t: loop d: {hex(d)}")
            # assert d <= 0xef
            if d >= 0xf0:
                logger.warning(f'reading large time byte: {hex(d)}')
            delta += d
            logger.debug(f"read_messages: {stream.tell()}\t: delta: {hex(delta)}")

            # status
            d = read_le(stream)
            if d >= 0x80:
                status = d
                logger.debug(f"read_messages: {stream.tell()}\t: status: {hex(d)}")
            else:
                stream.seek(-1, io.SEEK_CUR)

            try:
                length = get_event_length(status) - 1
            except UnboundLocalError:
                raise ValueError("Running status, but without previous status")
            event = status.to_bytes(1, byteorder='little') + stream.read(length)
            try:
                msg = mido.Message.from_bytes(event)
                msg.time = delta
                logger.debug(f"read_messages: {stream.tell()}\t:  0x{event.hex()} \t, {msg}")
                track.append(msg)
            except ValueError:
                logger.warning(f"read_messages: encountered illegal event (0x{event.hex()}), ignoring")
    except EOFError:
        logger.debug(f'read_messages: {stream.tell()}\t EOF')
        pass

    return track
