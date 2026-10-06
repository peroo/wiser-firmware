#!/usr/bin/env python3
"""Dump selected method bodies from a managed .NET assembly."""

import argparse

import dnfile
from dncil.cil.body.reader import read_method_body_from_bytes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("assembly")
    parser.add_argument("needle", nargs="?", default="")
    args = parser.parse_args()
    pe = dnfile.dnPE(args.assembly)
    needle = args.needle.lower()

    def token_name(value):
        value = getattr(value, "value", value)
        if not isinstance(value, int):
            return repr(value)
        table_id, row_id = value >> 24, value & 0xFFFFFF
        if table_id == 0x70:
            try:
                return repr(pe.net.user_strings.get(row_id).value)
            except Exception:
                return f"string(0x{value:08x})"
        tables = {1: "TypeRef", 2: "TypeDef", 4: "Field", 6: "MethodDef", 10: "MemberRef", 27: "TypeSpec", 43: "MethodSpec"}
        name = tables.get(table_id)
        if name:
            try:
                row = getattr(pe.net.mdtables, name).rows[row_id - 1]
                member = getattr(row, "Name", None)
                return f"{name}::{member}" if member else f"{name}[{row_id}]"
            except Exception:
                pass
        return f"0x{value:08x}"

    for typedef in pe.net.mdtables.TypeDef.rows:
        type_name = f"{typedef.TypeNamespace}.{typedef.TypeName}"
        for index in typedef.MethodList:
            method = index.row
            full_name = f"{type_name}::{method.Name}"
            if needle and needle not in full_name.lower():
                continue
            print(f"\n### {full_name} RVA=0x{method.Rva:x}")
            if not method.Rva:
                continue
            try:
                body = read_method_body_from_bytes(pe.get_data(method.Rva, 65536))
                for instruction in body.instructions:
                    operand = "" if instruction.operand is None else token_name(instruction.operand)
                    print(f"IL_{instruction.offset:04x}: {instruction.opcode.name} {operand}")
            except Exception as exc:
                print(f"[decode error: {exc}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
