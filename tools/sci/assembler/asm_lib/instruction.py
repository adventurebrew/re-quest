from opcodes import SciOpcodes
from misc import Kernels


class Instruction:
    # TODO mark jump labels?
    def __init__(self, opcode, operands, offset, mode='disasm', label=None, kernels=None):
        self.str = None
        self.label = label
        self.exported = False
        self.legal = True
        self.offset = offset
        self.opcode = opcode
        self.mode = mode
        if mode == 'asm':
            self.operands = operands
            length_range = self.opcode.instruction_length_range()
            if self.opcode in [SciOpcodes.op_lofsa, SciOpcodes.op_lofss]:
                self.length = length_range['max']
                self.operands_lens = [self.length - 1]
                self.extra = 0
            elif self.opcode in [SciOpcodes.op_call]:
                self.length = length_range['max']
                self.operands_lens = [self.length - 2, 1]
                self.extra = 0
            elif self.opcode in [SciOpcodes.op_callk]:
                self.length = length_range['min']
                self.operands_lens = [self.length - 2, 1]
                self.extra = 1
            elif self.opcode.is_relative():
                self.length = length_range['max']
                self.operands_lens = [self.length - 1]
                self.extra = 0
            else:
                self.length = 1
                self.operands_lens = []
                for operand in operands:
                    self.operands_lens.append(len(operand))
                    self.length += len(operand)
                if self.opcode == SciOpcodes.op_calle:
                    if self.length % 2 == 1:
                        self.length += 1
                    if self.length == 4:
                        self.operands_lens = [1, 1, 1]
                    elif self.length == 6:
                        self.operands_lens = [2, 2, 1]
                    else:
                        raise ValueError

                assert length_range['min'] == self.length or self.length == length_range['max']
                self.extra = length_range['max'] - self.length
                if self.extra > 1:
                    self.extra = 1
        elif mode == 'disasm':
            self.operands_width = [len(operands)]
            if self.opcode in [SciOpcodes.op_pushi, SciOpcodes.op_ldi, SciOpcodes.op_link]:
                self.operands = int.from_bytes(operands, byteorder='little', signed=self.opcode.is_signed())
            elif self.opcode == SciOpcodes.op_call:
                offset = int.from_bytes(operands[:-1], byteorder='little', signed=self.opcode.is_signed())
                self.operands = [self.offset + len(operands) + 1 + offset, operands[-1]]
            elif self.opcode.is_relative():
                offset = int.from_bytes(operands, byteorder='little', signed=self.opcode.is_signed())
                self.operands = self.offset + len(operands) + 1 + offset
            elif self.opcode in [SciOpcodes.op_lofsa, SciOpcodes.op_lofss]:
                # see comment at opcodes.py
                self.operands = int.from_bytes(operands, byteorder='little', signed=self.opcode.is_signed())
            elif self.opcode in [SciOpcodes.op_callb, SciOpcodes.op_super]:
                self.operands = ', '.join([hex(o) for o in operands])
            elif self.opcode == SciOpcodes.op_callk:
                if len(operands) == 2:
                    self.operands = f'{kernels.get_kernel(operands[0])}, {hex(operands[1])}'
                    self.operands_width = [1, 1]
                else:
                    assert len(operands) == 3
                    kernel = int.from_bytes(operands[0:2], byteorder='little')
                    self.operands = f'{kernels.get_kernel(kernel)}, {hex(operands[2])}'
                    self.operands_width = [2, 1]
            elif self.opcode == SciOpcodes.op_calle:
                if len(operands) == 3:
                    self.operands = [o for o in operands]  # byte -> list of int
                    self.operands_width = [1, 1, 1]
                else:
                    assert len(operands) == 5
                    self.operands = [int.from_bytes(operands[0:2], byteorder='little'),
                                     int.from_bytes(operands[2:4], byteorder='little'),
                                     operands[4]]
                    self.operands_width = [2, 2, 1]
            elif self.opcode == SciOpcodes.op_lea:
                if len(operands) == 2:
                    self.operands = [o for o in operands]  # byte -> list of int
                    self.operands_width = [1, 1]
                else:
                    assert len(operands) == 4
                    self.operands = [int.from_bytes(operands[0:2], byteorder='little'),
                                     int.from_bytes(operands[2:4], byteorder='little'),]
                    self.operands_width = [2, 2]
            elif self.opcode.num_of_operands() == 0:
                self.operands = ""
            elif self.opcode >= SciOpcodes.op_lag:
                self.operands = int.from_bytes(operands[0:2], byteorder='little')
            elif self.opcode.num_of_operands() == 1:
                self.operands = operands[0]
            else:
                raise NotImplementedError
        else:
            raise ValueError

    def set_label(self):
        if not self.label:
            self.label = f'code_{self.offset}'

    def __repr__(self):
        if self.label:
            label = self.label
        else:
            label = f'code_{self.offset}'
        return f'{label}  ; {repr(self.opcode)}'

    def str_dump(self):
        def operand_dump(operand, i=0):
            if self.opcode.is_relative():
                return str(operand)
            elif isinstance(operand, str):
                return operand
            else:
                assert isinstance(operand, int)
                if operand >= 0:
                    return f'0x%0{2 * self.operands_width[i]}x' % operand
                else:
                    return str(operand)

        result = ''
        if self.exported:
            result += '; exported\n'
        if self.label:
            result += self.label + ':\n'
        result += f'\t\t{repr(self.opcode)}\t'

        if type(self.operands) is list:
            result += ', '.join([operand_dump(operand, i) for i, operand in enumerate(self.operands)])
        else:
            result += operand_dump(self.operands)

        if self.str is not None:
            result += f'\t\t; "{self.str}"'
        if not self.legal:
            result += "\t; Illegal!"
        if self.opcode == SciOpcodes.op_ret:
            result += '\n'
        return result


if __name__ == '__main__':
    print("This script shouldn't be directly called")
    import sys

    sys.exit(1)
