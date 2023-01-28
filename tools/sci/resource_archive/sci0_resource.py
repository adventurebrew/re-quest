import io
from contextlib import contextmanager
import struct
from typing import IO, Iterator, NamedTuple

from pakal.archive import ArchiveIndex, BaseArchive, make_opener

from .compression import DecompressHuffman, decompress_lzw

MAP_ENTRY = struct.Struct('<HI')
RESOURCE_ENTRY = struct.Struct('<4H')


class SCI0FileEntry(NamedTuple):
    resid: int
    archive_num: int
    offset: int


RES_TYPE = {
    0: 'view',
    1: 'pic',
    2: 'script',
    3: 'text',
    4: 'sound',
    5: 'memory',
    6: 'vocab',
    7: 'font',
    8: 'cursor',
    9: 'patch',
    10: 'bitmap',
    11: 'palette',
    12: 'cda',
    13: 'audio',
    14: 'syn',
    15: 'message',
    16: 'map',
    17: 'heap',
}


def resid_to_name(resid: int):
    res_type = (resid & 0xF800) >> 11
    res_num = resid & 0x7FF
    return f'{RES_TYPE[res_type]}.{res_num:03d}'


def extract(stream: IO[bytes]):
    while True:
        entry = stream.read(MAP_ENTRY.size)
        if not entry:
            raise EOFError()
        if entry == b'\xFF\xFF\xFF\xFF\xFF\xFF':
            break
        resid, archive = MAP_ENTRY.unpack(entry)

        yield resid_to_name(resid), SCI0FileEntry(
            resid,
            (archive & 0xFC000000) >> 26,
            archive & 0x3FFFFFF,
        )


class SCI0Archive(BaseArchive[SCI0FileEntry]):
    def _create_index(self) -> ArchiveIndex[SCI0FileEntry]:
        return dict(extract(self._stream))

    @contextmanager
    def _read_entry(self, entry: SCI0FileEntry) -> Iterator[IO[bytes]]:
        if not self._filename:
            raise ValueError('Must open via filename')
        archive = (
            self._filename.parent / f'{self._filename.stem}.{entry.archive_num:03d}'
        )
        with self._io.open(archive, 'rb') as stream:
            stream.seek(entry.offset)
            res_entry = stream.read(RESOURCE_ENTRY.size)
            resid, comp_size, decomp_size, method = RESOURCE_ENTRY.unpack(res_entry)
            comp_size -= 4
            header = (0x80 | ((resid & 0xF800) >> 11)).to_bytes(
                2, signed=False, byteorder='little'
            )
            assert resid == entry.resid, (resid, entry.resid)
            # print(hex(resid), resid_to_name(resid), method)
            if method == 0:
                assert decomp_size == comp_size, (decomp_size, comp_size, method)
                decomp_data = stream.read(decomp_size)
            elif method == 1:
                decomp_data = decompress_lzw(
                    stream.read(comp_size), decomp_size, comp_size
                )
            else:
                decomp_data = DecompressHuffman().decompress_huffman(
                    stream.read(comp_size),
                    decomp_size,
                    comp_size,
                )
            yield io.BytesIO(header + decomp_data)


open = make_opener(SCI0Archive)
