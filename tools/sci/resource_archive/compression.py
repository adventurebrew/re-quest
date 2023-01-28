

# SCI Resource Decompression algorithms, based on SCICompanion implementation:
# https://github.com/Kawa-oneechan/SCICompanion/blob/master/SCICompanionLib/Src/Util/Codec.cpp

def decompress_lzw(src, decomp_size, complength):
    bitlen = 9
    bitmask = 0x01FF
    bitctr = 0
    bytectr = 0
    maxtoken = 0x200

    tokenlist = [0 for _ in range(4096)]
    tokenlengthlist = [0 for _ in range(4096)]
    tokenctr = 0x102

    tokenlastlength = 0
    destctr = 0

    output = bytearray(decomp_size)

    while bytectr < complength:

        tokenmaker = src[bytectr] >> bitctr
        bytectr += 1
        if bytectr < complength:
            tokenmaker |= src[bytectr] << (8 - bitctr)
            tokenmaker %= 2**32
        if bytectr + 1 < complength:
            tokenmaker |= src[bytectr + 1] << (16 - bitctr)
            tokenmaker %= 2**32

        token = tokenmaker & bitmask
        assert token % 4096 == token, token

        bitctr += bitlen - 8

        bytectr += bitctr // 8
        bitctr %= 8

        if token == 0x101:
            break

        if token == 0x100:
            maxtoken = 0x200
            bitlen = 9
            bitmask = 0x01FF
            tokenctr = 0x0102
        else:

            if token > 0xFF:
                if token >= tokenctr:
                    raise ValueError('bad token')
                else:
                    tokenlastlength = tokenlengthlist[token] + 1
                    if destctr + tokenlastlength > decomp_size:
                        raise ValueError('write beyond size')
                    for i in range(tokenlastlength):
                        output[destctr] = output[tokenlist[token] + i]
                        destctr += 1
            else:
                tokenlastlength = 1
                if destctr >= decomp_size:
                    raise ValueError('write beyond size - single byte')
                output[destctr] = token
                destctr += 1

            if tokenctr == maxtoken:
                if bitlen < 12:
                    bitlen += 1
                    bitmask <<= 1
                    bitmask |= 1
                    maxtoken <<= 1
                else:
                    continue

            tokenlist[tokenctr] = destctr - tokenlastlength
            tokenlengthlist[tokenctr] = tokenlastlength
            tokenctr += 1

    assert len(output) == decomp_size, (len(output), decomp_size)
    return bytes(output)


class DecompressHuffman:
    def getc2(self, node, src, complength):

        nodesrc = 0

        while node[nodesrc + 1] != 0:
            value = src[self.bytectr] << self.bitctr
            self.bitctr += 1
            if self.bitctr == 8:
                self.bitctr = 0
                self.bytectr += 1

            if value & 0x80:
                nextc = node[nodesrc + 1] & 0x0F
                if nextc == 0:
                    result = src[self.bytectr] << self.bitctr
                    self.bytectr += 1
                    result %= 4096
                    if self.bytectr > complength:
                        raise ValueError()
                    elif self.bytectr < complength:
                        result |= src[self.bytectr] >> (8 - (self.bitctr))

                    result &= 0x0FF
                    return result | 0x100
            else:
                nextc = node[nodesrc + 1] >> 4
            nodesrc += nextc << 1
        return int.from_bytes(
            node[nodesrc : nodesrc + 2], byteorder='little', signed=True
        )

    def decompress_huffman(self, src, length, complength):

        self.bitctr = 0

        numnodes = src[0]
        terminator = src[1]

        self.bytectr = 2 + (numnodes << 1)

        nodesBoundsChecked = src[2:-2]

        output = bytearray()

        while True:
            c = self.getc2(nodesBoundsChecked, src, complength)
            if c == 0x100 | terminator:
                break
            output.append(c % 256)
        assert len(output) == length, (len(output), length)
        return bytes(output)
