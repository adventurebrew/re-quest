import humanhash


def cast(val):
    try:
        return int(val)
    except ValueError:
        return val == 'True'


class AdlibOp:
    def __init__(self, op=None, dict=None):
        if op:
            assert dict is None
            self.kb_scale_level = op[0] & 0x3
            self.frequency_mult = op[1] & 0xf
            self.unknown1 = op[2]
            self.attack_rate = op[3] & 0xf
            self.sustain_level = op[4] & 0xf
            self.envelope_type = bool(op[5])
            self.decay_rate = op[6] & 0xf
            self.release_rate = op[7] & 0xf
            self.total_level = op[8] & 0x3f
            self.amplitude_mod = bool(op[9])
            self.vibrato = bool(op[10])
            self.kb_scale_rate = bool(op[11])
            self.unknown2 = op[12]
            self.waveform = None
            self.orig_data = op
        elif dict:
            self.__dict__.update({k: cast(dict[k]) for k in dict})
        else:
            self.kb_scale_level = 0
            self.frequency_mult = 0
            self.unknown1 = 0
            self.attack_rate = 0
            self.sustain_level = 0
            self.envelope_type = False
            self.decay_rate = 0
            self.release_rate = 0
            self.total_level = 0
            self.amplitude_mod = False
            self.vibrato = 0
            self.kb_scale_rate = False
            self.unknown2 = 0
            self.waveform = 0

    def __bytes__(self):
        return bytes([
            self.kb_scale_level,
            self.frequency_mult,
            self.unknown1,
            self.attack_rate,
            self.sustain_level,
            self.envelope_type,
            self.decay_rate,
            self.release_rate,
            self.total_level,
            self.amplitude_mod,
            self.vibrato,
            self.kb_scale_rate,
            self.unknown2,
            self.waveform
        ])

    def dict(self):
        result = self.__dict__.copy()
        del result['orig_data']
        return result


class AdlibInstrument:
    def __init__(self, op1=None, op2=None, dict=None):
        if op1 or op2:
            assert op1 and op2
            self.ops = [op1, op2]
            self.mod_feedback = op1.orig_data[2] & 7
            self.mod_algorithm = not bool(op1.orig_data[12])
        elif dict:
            assert op1 is None and op2 is None
            self.mod_feedback = cast(dict['mod_feedback'])
            self.mod_algorithm = cast(dict['mod_algorithm'])
            self.ops = [
                AdlibOp(dict={k.removeprefix('op_0_'): dict[k] for k in dict if k.startswith('op_0')}),
                AdlibOp(dict={k.removeprefix('op_1_'): dict[k] for k in dict if k.startswith('op_1')})
            ]
        else:
            self.ops = [AdlibOp(), AdlibOp()]
            self.mod_feedback = 0
            self.mod_algorithm = False

    def __bytes__(self):
        result = bytearray(bytes(self.ops[0]))
        wave_form_0 = result.pop()

        result += bytearray(bytes(self.ops[1]))
        wave_form_1 = result.pop()

        result[2] = self.mod_feedback
        result[12] = not self.mod_algorithm

        result += bytes([wave_form_0, wave_form_1])

        return bytes(result)

    def dict(self):
        result = {'id': self.human_hash()}
        result.update(self.__dict__.copy())
        del result['ops']
        for i, op in enumerate(self.ops):
            op_dict = op.dict()
            result.update({f'op_{i}_{k}': op_dict[k] for k in op_dict})

        return result

    def human_hash(self):
        return humanhash.humanize(bytes(self).hex(), words=3)
