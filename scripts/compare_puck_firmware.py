#!/usr/bin/env python3
"""Structural comparison of two plaintext ARM Thumb puck images."""

from __future__ import annotations

import hashlib
import re
import struct
import sys
from collections import Counter, deque
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_LITTLE_ENDIAN, CS_MODE_THUMB, Cs
from capstone.arm import ARM_CC_AL, ARM_CC_INVALID, ARM_INS_B, ARM_INS_BL, ARM_INS_BLX

VECTOR_BASE = 0x100
VECTOR_COUNT = 64


def u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def roots(data: bytes) -> list[int]:
    result = []
    end = min(len(data), VECTOR_BASE + VECTOR_COUNT * 4)
    for offset in range(VECTOR_BASE + 4, end, 4):
        value = u32(data, offset)
        if value & 1 and (value & ~1) < len(data):
            result.append(value & ~1)
    return sorted(set(result))


def canonical(insn, size: int) -> str:
    operand = insn.op_str
    if insn.id in (ARM_INS_B, ARM_INS_BL, ARM_INS_BLX):
        operand = re.sub(r"#0x[0-9a-f]+", "#TARGET", operand)
    else:
        def replace(match):
            value = int(match.group(1), 16)
            return "#ADDR" if value < size or 0x20000000 <= value < 0x20040000 else match.group(0)
        operand = re.sub(r"#0x([0-9a-f]+)", replace, operand)
    return f"{insn.mnemonic} {operand}".rstrip()


def discover(data: bytes) -> dict[int, dict]:
    disassembler = Cs(CS_ARCH_ARM, CS_MODE_THUMB | CS_MODE_LITTLE_ENDIAN)
    disassembler.detail = True
    pending = deque(roots(data))
    seen = set()
    functions = {}
    while pending:
        start = pending.popleft() & ~1
        if start in seen or start >= len(data):
            continue
        seen.add(start)
        instructions = []
        blocks = deque([start])
        visited = set()
        while blocks and len(instructions) < 5000:
            pc = blocks.popleft()
            if pc in visited or pc >= len(data):
                continue
            visited.add(pc)
            for insn in disassembler.disasm(data[pc:min(len(data), pc + 2048)], pc):
                instructions.append(insn)
                immediate = None
                if insn.operands and insn.operands[-1].type == 2:  # ARM_OP_IMM
                    immediate = insn.operands[-1].imm & ~1
                if insn.id in (ARM_INS_BL, ARM_INS_BLX) and immediate is not None and immediate < len(data):
                    pending.append(immediate)
                if insn.id == ARM_INS_B:
                    if immediate is not None and immediate < len(data):
                        blocks.append(immediate)
                    if insn.cc in (ARM_CC_AL, ARM_CC_INVALID):
                        break
                if (insn.mnemonic in ("bx", "pop") and "pc" in insn.op_str) or (insn.mnemonic == "bx" and insn.op_str == "lr") or insn.mnemonic == "udf":
                    break
        ordered = [dict((item.address, item) for item in instructions)[address] for address in sorted({item.address for item in instructions})]
        normalized = "\n".join(canonical(item, len(data)) for item in ordered)
        functions[start] = {
            "instructions": len(ordered),
            "bytes": sum(item.size for item in ordered),
            "end": max((item.address + item.size for item in ordered), default=start),
            "hash": hashlib.sha256(normalized.encode()).hexdigest(),
        }
    return functions


def unmatched(functions: dict, shared: Counter) -> list[tuple]:
    remaining = shared.copy()
    result = []
    for address, info in functions.items():
        if remaining[info["hash"]]:
            remaining[info["hash"]] -= 1
        else:
            result.append((info["instructions"], address, info))
    return sorted(result, reverse=True)


def main() -> int:
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} OLD.bin NEW.bin", file=sys.stderr)
        return 2
    old_data, new_data = (Path(path).read_bytes() for path in sys.argv[1:])
    old, new = discover(old_data), discover(new_data)
    old_hashes = Counter(info["hash"] for info in old.values())
    new_hashes = Counter(info["hash"] for info in new.values())
    shared = old_hashes & new_hashes
    common = sum(shared.values())
    print(f"old roots={len(roots(old_data))} functions={len(old)} instructions={sum(v['instructions'] for v in old.values())}")
    print(f"new roots={len(roots(new_data))} functions={len(new)} instructions={sum(v['instructions'] for v in new.values())}")
    print(f"normalized exact function matches={common}")
    print(f"old unmatched={len(old) - common}, new unmatched={len(new) - common}")
    for label, values in (("old", unmatched(old, shared)), ("new", unmatched(new, shared))):
        print(f"\nLargest unmatched {label} functions:")
        for count, address, info in values[:25]:
            print(f"  {address:#08x} insns={count:4d} bytes={info['bytes']:5d} end={info['end']:#08x}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
