"""Reference arithmetic for the observed HALL decay raw-coefficient helper.

This maps the internal byte passed to the helper to the observed coefficient
GPR group. It deliberately does not map the LCD value (0..99) to that byte.
"""


def _signed32(value):
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value & 0x80000000 else value


def _signed16(value):
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def coefficient_registers(raw_coefficient: int, parameter_tag: int = 0x08) -> dict[int, int]:
    if not 0 <= raw_coefficient <= 0x7F:
        raise ValueError("raw coefficient must be a 7-bit nonnegative value")
    if not 0 <= parameter_tag <= 0xFF:
        raise ValueError("parameter tag must be a byte")
    d2 = raw_coefficient << 8
    d3 = _signed32(-d2)
    # 68000 MULS.W multiplies signed low words into a 32-bit result.
    product = _signed32(_signed16(d2) * _signed16(d3))
    d5 = _signed32(product + 0x3FFFFFFF)
    arithmetic_shifted = d5 >> 7
    gpr03 = (d2 << 8) & 0xFFFFFF
    return {
        0x03: gpr03,
        0x04: (-gpr03) & 0xFFFFFF,
        0x05: arithmetic_shifted & 0xFFFFFF,
        0x5B: ((parameter_tag << 16) | raw_coefficient) & 0xFFFFFF,
        0x6E: (raw_coefficient << 16) & 0xFFFFFF,
    }
