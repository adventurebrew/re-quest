import io
from struct import unpack, calcsize, pack_into, unpack_from, pack

PIC_OPX_EMBEDDED_VIEW = 1
PIC_OPX_SET_PALETTE = 2
PIC_OP_OPX = 254

EXTRA_MAGIC_SIZE = 15
PAL_SIZE = 1284
VIEW_HEADER_COLORS_8BIT = 0x80


def decodeRLE(rledata, pixeldata, dsize):
    pos = 0
    size = 0

    outbuffer = bytearray(dsize)

    while pos < dsize:
        nextbyte = rledata[0]
        rledata = rledata[1:]
        outbuffer[pos] = nextbyte
        pos += 1
        size += 1
        masked = nextbyte & 0xC0
        if masked in {0x00, 0x40}:
            outbuffer[pos : pos + nextbyte] = pixeldata[:nextbyte]
            pixeldata = pixeldata[nextbyte:]
            pos += nextbyte
        elif masked == 0x80:
            nextbyte = pixeldata[0]
            pixeldata = pixeldata[1:]
            outbuffer[pos] = nextbyte
            pos += 1

    return size, pos - size, bytes(outbuffer)


def getRLEsize(rledata, dsize):
    pos = 0
    size = 0

    while pos < dsize:
        nextbyte = rledata[0]
        rledata = rledata[1:]
        pos += 1
        size += 1

        masked = nextbyte & 0xC0
        if masked in {0x00, 0x40}:
            pos += nextbyte
        elif masked == 0x80:
            pos += 1

    return size


def reorderPic(src: bytes, dsize: int):
    dest = bytearray(dsize)
    seeker = bytes(src)
    writer = memoryview(dest)

    writer[0] = PIC_OP_OPX
    writer[1] = PIC_OPX_SET_PALETTE
    writer = writer[2:]

    writer[:256] = bytes(range(256))
    writer = writer[256:]

    pack_into('<I', writer, 0, 0)
    writer = writer[4:]

    view_size, view_start, data_size = unpack_from('<HHH', seeker)
    seeker = seeker[6:]

    viewdata = seeker[:7]
    seeker = seeker[7:]

    writer[: 4 * 256] = seeker[: 4 * 256]
    seeker = seeker[4 * 256 :]
    writer = writer[4 * 256 :]

    if view_start != PAL_SIZE + 2:
        writer[: view_start - PAL_SIZE - 2] = seeker[: view_start - PAL_SIZE - 2]
        seeker = seeker[view_start - PAL_SIZE - 2 :]
        writer = writer[view_start - PAL_SIZE - 2 :]

    extra = view_start + EXTRA_MAGIC_SIZE + view_size
    if dsize != extra:
        dest[extra:dsize] = seeker[: dsize - extra]
        seeker = seeker[dsize - extra :]

    data_start = bytearray(data_size)
    for i in range(data_size):
        data_start[i] = seeker[i]
    seeker = seeker[data_size:]

    writer = memoryview(dest)[view_start:]
    pack_into(
        '<5BH', writer, 0, PIC_OP_OPX, PIC_OPX_EMBEDDED_VIEW, 0, 0, 0, view_size + 8
    )
    writer = writer[7:]

    writer[:7] = viewdata
    writer = writer[7:]

    writer[0] = 0
    writer = writer[1:]
    _, _, writer[:view_size] = decodeRLE(seeker, data_start, view_size)

    return bytes(dest)


def buildCelHeaders(stream, dest, writer, celindex, cc_lengths, max):
    for c in range(max):
        dest[writer : writer + 6] = stream.read(6)
        writer += 6
        dest[writer : writer + 2] = pack("<H", ord(stream.read(1)))
        writer += 2
        writer += cc_lengths[celindex]
        celindex += 1
    return writer


def read_struct(fmt, stream):
    return unpack(fmt, stream.read(calcsize(fmt)))


def reorderView(src: bytes) -> bytearray:
    with io.BytesIO(src) as stream:
        lh_last = None
        dest = bytearray(len(src))
        cellengths = read_struct('<H', stream)[0] + 2
        loopheaders, lh_present = stream.read(2)
        lh_mask, unknown, pal_offset, cel_total = read_struct('<4H', stream)
        cc_pos = [None for _ in range(cel_total)]
        cc_lengths = list(unpack_from(f"<{cel_total}H", src, cellengths))
        dest[:8] = pack(
            "<2B3H", loopheaders, VIEW_HEADER_COLORS_8BIT, lh_mask, unknown, pal_offset
        )
        lh_ptr = writer = 8
        writer += 2 * loopheaders
        dest[lh_ptr:writer] = b'\0' * 2 * loopheaders
        celcounts = list(stream.read(lh_present))
        lb = 1
        celindex = 0
        pix_ptr = cellengths + (2 * cel_total)
        w = 0
        for _ in range(loopheaders):
            if lh_mask & lb:
                dest[lh_ptr : lh_ptr + 2] = pack("<H", lh_last)
                lh_ptr += 2
            else:
                lh_last = writer
                dest[lh_ptr : lh_ptr + 2] = pack("<H", lh_last)
                lh_ptr += 2
                dest[writer : writer + 4] = pack("<2H", celcounts[w], 0)
                writer += 4
                chptr = writer + (2 * celcounts[w])
                for c in range(celcounts[w]):
                    dest[writer : writer + 2] = pack("<H", chptr)
                    writer += 2
                    cc_pos[celindex + c] = chptr
                    chptr += (
                        8 + unpack_from("<H", src, cellengths + 2 * (celindex + c))[0]
                    )
                writer = buildCelHeaders(
                    stream, dest, writer, celindex, cc_lengths, celcounts[w]
                )
                celindex += celcounts[w]
                w += 1
            lb <<= 1
        for c in range(cel_total):
            pix_ptr += getRLEsize(src[pix_ptr:], cc_lengths[c])
        rle_ptr = cellengths + (2 * cel_total)
        for c in range(cel_total):
            cbase, csize = cc_pos[c] + 8, cc_lengths[c]
            size, pos, dest[cbase : cbase + csize] = decodeRLE(
                src[rle_ptr:], src[pix_ptr:], csize
            )
            rle_ptr += size
            pix_ptr += pos
        if pal_offset:
            dest[writer : writer + 3] = b'PAL'
            writer += 3
            dest[writer : writer + 256] = bytes(range(256))
            writer += 256
            # stream.seek(-4, 1)
            dest[writer : writer + (4 * 256) + 4] = b'\0\0\0\0' + stream.read(
                (4 * 256) + 4
            )
            writer += (4 * 256) + 4
    return bytes(dest[:writer])
