import io
from contextlib import contextmanager
import struct
from typing import IO, Iterator, NamedTuple

from pakal.archive import ArchiveIndex, BaseArchive, make_opener

from .compression import DecompressHuffman, decompress_comp3, decompress_dcl, decompress_lzs
from .codec import reorderPic, reorderView

LOOKUP_ENTRY = struct.Struct('<BH')
MAP_ENTRY_SCI10 = struct.Struct('<HI')
MAP_ENTRY_SCI11 = struct.Struct('<2HB')
RESOURCE_ENTRY = struct.Struct('<B4H')
RESOURCE_ENTRY32 = struct.Struct('<BH2IH')


class SCI1LookupEntry(NamedTuple):
    res_type: int
    offset: int


class SCI1FileEntry(NamedTuple):
    resid: int
    res_type: int
    volume: int
    offset: int


# https://github.dev/Kawa-oneechan/SCICompanion/blob/32c8763499cb9d1938fd16991a23e2d5acf2e9b3/SCICompanionLib/Src/Resources/ResourceUtil.cpp#L27-L44
RES_TYPE = {
    0: 'v56',
    1: 'p56',
    2: 'scr',
    3: 'tex',
    4: 'snd',
    5: 'mem',
    6: 'voc',
    7: 'fon',
    8: 'cur',
    9: 'pat',
    10: 'bit',
    11: 'pal',
    12: 'cda',
    13: 'aud',
    14: 'syn',
    15: 'msg',
    16: 'map',
    17: 'hep',
}


RES_TYPE32 = {
    0: 'v56',
    1: 'p56',
    2: 'scr',
    3: 'tex',
    4: 'snd',
    5: 'etc',
    6: 'voc',
    7: 'fon',
    8: 'cur',
    9: 'pat',
    10: 'bmp',
    11: 'pal',
    12: 'au2',
    13: 'aud',
    14: 'syn',
    15: 'msg',
    16: 'map',
    17: 'hep',
    18: 'a36',
    19: 's36',
    20: 'trn',
    21: 'rbt',
    22: 'vmd',
    24: 'duk',
    25: 'clu',
    26: 'tga',
    27: 'zzz',
}


def resid_to_name32(resid: int, res_type: int):
    return f'{resid}.{RES_TYPE32[res_type]}'


def resid_to_name(resid: int, res_type: int):
    return f'{resid}.{RES_TYPE[res_type - 0x80]}'


def extract(ctx, stream: IO[bytes]):
    lookup = []
    while True:
        entry = stream.read(LOOKUP_ENTRY.size)
        if not entry:
            raise EOFError()
        res_type, offset = LOOKUP_ENTRY.unpack(entry)
        if res_type == 0xFF:
            end_lookup_offset = offset
            break

        lookup.append(SCI1LookupEntry(
            res_type,
            offset,
        ))

    ends = [e.offset for e in lookup[1:]] + [end_lookup_offset]

    possible_entry_maps = {MAP_ENTRY_SCI10, MAP_ENTRY_SCI11}

    if any(entry.res_type < 0x80 for entry in lookup):
        map_entry_s = MAP_ENTRY_SCI10
        ctx['sci_version'] = 2
    else:

        for entry, end_offset in zip(lookup, ends):
            size = end_offset - entry.offset
            if size % 5 != 0:
                possible_entry_maps.discard(MAP_ENTRY_SCI11)
            elif size % 6 != 0:
                possible_entry_maps.discard(MAP_ENTRY_SCI10)
        
        if len(possible_entry_maps) != 1:
            raise ValueError('Could not detect resource version')

        map_entry_s = list(possible_entry_maps)[0]
        ctx['sci_version'] = 1.1 if map_entry_s == MAP_ENTRY_SCI11 else 1

    for entry, end_offset in zip(lookup, ends):
        stream.seek(entry.offset)
        data = stream.read(end_offset - entry.offset)
        for value in map_entry_s.iter_unpack(data):
            resid, offset = value[:2]
            volume = 0
            if map_entry_s == MAP_ENTRY_SCI11:
                offset += value[2] << 16
                offset <<= 1
            else:
                volume = offset >> 28
                offset &= 0x0FFFFFFF
            if ctx['sci_version'] == 2:
                yield resid_to_name32(resid, entry.res_type), SCI1FileEntry(resid, entry.res_type, volume, offset)
            else:
                yield resid_to_name(resid, entry.res_type), SCI1FileEntry(resid, entry.res_type, volume, offset)


class SCI1Archive(BaseArchive[SCI1FileEntry]):
    def _create_index(self) -> ArchiveIndex[SCI1FileEntry]:
        ctx = {}
        res = dict(extract(ctx, self._stream))
        self.sci_version = ctx['sci_version']
        return res

    @contextmanager
    def read_entry32(self, entry: SCI1FileEntry) -> Iterator[IO[bytes]]:
        archive = (
            self._filename.parent / f'RESSCI.{entry.volume:03d}'
        )
        with self._io.open(archive, 'rb') as stream:
            stream.seek(entry.offset)
            res_entry = stream.read(RESOURCE_ENTRY32.size)
            res_type, resid, comp_size, decomp_size, method = RESOURCE_ENTRY32.unpack(res_entry)
            assert (res_type, resid) == (entry.res_type, entry.resid), (resid, entry.resid, res_type, entry.res_type)
            header = res_type.to_bytes(
                2, signed=False, byteorder='little'
            )
            print(entry, method, hex(comp_size), hex(decomp_size), hex(entry.offset))
            if comp_size < decomp_size:
                if method == 32:
                    decomp_data = decompress_lzs(
                        stream.read(comp_size),
                        decomp_size,
                        comp_size,
                    )
                else:
                    raise ValueError(method)
            else:
                decomp_data = stream.read(comp_size)
            yield io.BytesIO(header + decomp_data)


    # https://github.com/scummvm/scummvm/blob/f41cc33dffa980616226fb7fcddd8c08efce846c/engines/sci/resource/resource.cpp#L2278-L2281
    # // SCI0 volume format:  {wResId wPacked+4 wUnpacked wCompression} = 8 bytes
    # // SCI1 volume format:  {bResType wResNumber wPacked+4 wUnpacked wCompression} = 9 bytes
    # // SCI1.1 volume format:  {bResType wResNumber wPacked wUnpacked wCompression} = 9 bytes
    # // SCI32 volume format :  {bResType wResNumber dwPacked dwUnpacked wCompression} = 13 bytes
    @contextmanager
    def _read_entry(self, entry: SCI1FileEntry) -> Iterator[IO[bytes]]:
        if not self._filename:
            raise ValueError('Must open via filename')
        if self.sci_version >= 2:
            with self.read_entry32(entry) as resource:
                yield resource
            return
        archive = (
            self._filename.parent / f'{self._filename.stem}.{entry.volume:03d}'
        )
        with self._io.open(archive, 'rb') as stream:
            stream.seek(entry.offset)
            res_entry = stream.read(RESOURCE_ENTRY.size)
            res_type, resid, comp_size, decomp_size, method = RESOURCE_ENTRY.unpack(res_entry)
            if self.sci_version <=1:
                comp_size -= 4
            header = res_type.to_bytes(
                2, signed=False, byteorder='little'
            )
            if self.sci_version > 1:
                # https://sciprogramming.com/community/index.php?topic=1966.msg15135#msg15135
                if res_type - 0x80 in {0, 1, 11}:
                    header = (res_type | 0x8000).to_bytes(
                        2, signed=False, byteorder='little'
                    ) + b'\0\0'
                if res_type - 0x80 in {0, 1}:
                    header += b'\0' * 22
            assert (res_type, resid) == (entry.res_type, entry.resid), (resid, entry.resid, res_type, entry.res_type)
            # print(hex(resid), resid_to_name(resid), method)
            if method == 0:
                assert decomp_size == comp_size, (decomp_size, comp_size, method)
                decomp_data = stream.read(decomp_size)
            elif method in {2, 3, 4}:
                decomp_data = decompress_comp3(
                    stream.read(comp_size), decomp_size, comp_size
                )
                if method == 3:
                    decomp_data = reorderView(decomp_data)
                if method == 4:
                    decomp_data = reorderPic(decomp_data, decomp_size)
            elif method == 1:
                decomp_data = DecompressHuffman().decompress_huffman(
                    stream.read(comp_size),
                    decomp_size,
                    comp_size,
                )
            elif method in {18, 19, 20}:
                decomp_data = decompress_dcl(
                    stream.read(comp_size),
                    decomp_size,
                    comp_size,
                )
            else:
                raise ValueError(method)
            yield io.BytesIO(header + decomp_data)


open = make_opener(SCI1Archive)
