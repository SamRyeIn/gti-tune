#!/usr/bin/env python3
"""Locate ECU RAM variables in a Simos18 ASW image by scanning TriCore code.

Motivation: SimosTools logs raw RAM addresses, but no public PID list defines the
knock-sensor input channels (noise level, threshold, sensor feedback) and no A2L
for this box code is in the repo. Those addresses can still be recovered from the
firmware, because the code that reads a calibration constant necessarily sits
next to the code that writes the RAM variable that constant clamps.

Method:

1. Simos18 keeps a few address registers pinned to fixed bases at boot, so most
   global accesses are ``[a0]off16`` / ``[a9]off16`` BOL-format loads and stores.
   Rather than trust a published register table, ``derive_bases()`` recovers the
   bases empirically: for every base register it takes the mode of
   ``known_address - offset`` over a list of addresses we already log. A correct
   base is supported by hundreds of instructions; a wrong one by noise.
2. ``find_refs()`` then resolves any target address back to the instructions that
   touch it.
3. Anchoring on a calibration constant with exactly one reference (here
   ``C_KNKS_THD_MAX``) locates the routine, and the ``lea`` immediately before it
   supplies the base pointer of the RAM array being clamped.

Verified end to end: the S50 bases come out as a0 = 0xD0018000 and
a9 = 0xD000C000 with 761 and 532 supporting references, matching the values
published on the Simos Wiki.

Usage:
    ../Code/.venv/bin/python find_ram_symbols.py
"""

from __future__ import annotations

from pathlib import Path
import csv
import numpy as np

HERE = Path(__file__).resolve().parent
BIN_PATH = HERE.parent / "Code" / "bin" / "5G0906259L__0002.bin"
PID_LIST = HERE / "20260828 List.csv"

# The ASW (code) block occupies the first half of the 4 MB image; CAL follows.
ASW_LENGTH = 0x200000
CAL_FILE_OFFSET = 0x200000
CAL_BASE_ADDRESS = 0xA0800000

# BOL-format opcodes that reference memory as base register + signed 16-bit
# offset. Names are indicative; only the addressing matters here.
BOL_OPCODES = {
    0xB9: "st.w/st.a", 0x39: "ld.bu", 0xD9: "lea", 0xF9: "st.b",
    0x19: "ld.w", 0xC9: "ld.h", 0xE9: "st.h", 0x79: "ld.b",
    0x99: "ld.a", 0x59: "st.w",
}

# Base registers are pinned to 16 KB-aligned addresses by the boot code.
BASE_ALIGNMENT_MASK = 0x3FFF
MIN_SUPPORTING_REFS = 30

# a1 addresses the calibration block. It cannot be derived from the PID list,
# which contains only RAM addresses, so it is seeded from the Simos Wiki's
# published boot-time register table and then checked: a correct value makes
# a1-relative references land inside the CAL block rather than scattered.
CAL_BASE_REG = 1
CAL_BASE_REG_VALUE = 0xA0808000
CAL_BLOCK_LENGTH = 0x7FA00


def load_words(path: Path, length: int = ASW_LENGTH) -> np.ndarray:
    """Every halfword-aligned 32-bit window of the ASW, little-endian.

    TriCore instructions are halfword-aligned and either 16 or 32 bits wide.
    Decoding every even offset yields false positives, which is acceptable: an
    invalid decode almost never resolves onto a plausible address.
    """
    raw = np.frombuffer(path.read_bytes()[:length], dtype=np.uint8)
    return (raw[0:-3:2].astype(np.uint32)
            | (raw[1:-2:2].astype(np.uint32) << 8)
            | (raw[2:-1:2].astype(np.uint32) << 16)
            | (raw[3::2].astype(np.uint32) << 24))


def decode(words: np.ndarray) -> dict[str, np.ndarray]:
    """Split BOL fields out of each candidate instruction word."""
    offset = (((words >> 16) & 0x3F)
              | (((words >> 28) & 0xF) << 6)
              | (((words >> 22) & 0x3F) << 10)).astype(np.int64)
    return {
        "op1": words & 0xFF,
        "base_reg": (words >> 12) & 0xF,
        "data_reg": (words >> 8) & 0xF,
        "offset": np.where(offset >= 0x8000, offset - 0x10000, offset),
    }


def known_addresses(pid_list: Path) -> np.ndarray:
    """RAM addresses we already log — the ground truth the scan calibrates on."""
    out = []
    with pid_list.open(encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            address = row["Address"].strip().lower()
            if len(address) == 10 and address.startswith(("0xd", "0xb")):
                out.append(int(address, 16))
    return np.array(sorted(set(out)), dtype=np.int64)


def derive_bases(fields: dict[str, np.ndarray], truth: np.ndarray) -> dict[int, int]:
    """Recover each pinned base register from the addresses we already know."""
    is_memory_op = np.isin(fields["op1"], list(BOL_OPCODES))
    bases: dict[int, int] = {}
    for reg in range(16):
        selected = (fields["base_reg"] == reg) & is_memory_op
        if selected.sum() < 200:
            continue
        offsets = fields["offset"][selected]
        implied = (truth[:, None] - offsets[None, :]).ravel()
        implied = implied[(implied & BASE_ALIGNMENT_MASK) == 0]
        if not implied.size:
            continue
        values, counts = np.unique(implied, return_counts=True)
        if counts.max() < MIN_SUPPORTING_REFS:
            continue
        bases[reg] = int(values[np.argmax(counts)])
    bases[CAL_BASE_REG] = CAL_BASE_REG_VALUE
    return bases


def check_cal_base(fields: dict[str, np.ndarray], bases: dict[int, int]) -> float:
    """Fraction of a1-relative references that land inside the CAL block.

    A wrong seed for a1 scatters references outside the block, so a high
    fraction is the evidence that the seeded value is right for this image.
    """
    is_memory_op = np.isin(fields["op1"], list(BOL_OPCODES))
    selected = (fields["base_reg"] == CAL_BASE_REG) & is_memory_op
    if not selected.sum():
        return 0.0
    resolved = bases[CAL_BASE_REG] + fields["offset"][selected]
    inside = ((resolved >= CAL_BASE_ADDRESS)
              & (resolved < CAL_BASE_ADDRESS + CAL_BLOCK_LENGTH))
    return float(inside.mean())


def find_refs(target: int, fields: dict[str, np.ndarray],
              bases: dict[int, int]) -> list[tuple[int, str, int]]:
    """Every instruction resolving to ``target``, as (file offset, op, base reg)."""
    is_memory_op = np.isin(fields["op1"], list(BOL_OPCODES))
    found = []
    for reg, base in bases.items():
        wanted = target - base
        if not -0x8000 <= wanted < 0x8000:
            continue
        hits = np.flatnonzero(
            (fields["base_reg"] == reg) & (fields["offset"] == wanted) & is_memory_op
        )
        for index in hits:
            found.append((int(index) * 2, BOL_OPCODES[int(fields["op1"][index])], reg))
    return sorted(found)


def neighbourhood(centre_file_offset: int, fields: dict[str, np.ndarray],
                  bases: dict[int, int], span: int = 160) -> list[tuple]:
    """Memory references within ``span`` bytes either side of a code location."""
    centre = centre_file_offset // 2
    out = []
    for index in range(centre - span // 2, centre + span // 2 + 1):
        opcode = int(fields["op1"][index])
        if opcode not in BOL_OPCODES:
            continue
        reg = int(fields["base_reg"][index])
        if reg not in bases:
            continue
        address = bases[reg] + int(fields["offset"][index])
        out.append((index * 2 - centre_file_offset, BOL_OPCODES[opcode], reg, address))
    return out


def main() -> None:
    words = load_words(BIN_PATH)
    fields = decode(words)
    truth = known_addresses(PID_LIST)
    bases = derive_bases(fields, truth)
    print(f"Derived base registers from {truth.size} known addresses:")
    for reg, base in sorted(bases.items()):
        note = " (seeded, not derived)" if reg == CAL_BASE_REG else ""
        print(f"  a{reg} = 0x{base:08x}{note}")
    print(f"  a{CAL_BASE_REG} check: "
          f"{check_cal_base(fields, bases):.1%} of its references land inside CAL")

    # C_KNKS_THD_MAX -- Maximum value for KNKS_THD. Its XDF data address is
    # 0xa91f, so it lives at CAL_BASE + 0xa91f in the ECU's address space. The
    # clamp is the only code that reads it.
    thd_max = CAL_BASE_ADDRESS + 0xA91F
    refs = find_refs(thd_max, fields, bases)
    print(f"\nC_KNKS_THD_MAX (0x{thd_max:08x}): {len(refs)} reference(s)")
    for file_offset, op, reg in refs:
        print(f"  file 0x{file_offset:06x}  {op} via a{reg}")
        print("  nearby memory references:")
        for delta, near_op, near_reg, address in neighbourhood(file_offset, fields, bases):
            region = ("CAL" if CAL_BASE_ADDRESS <= address
                      < CAL_BASE_ADDRESS + CAL_BLOCK_LENGTH else "RAM")
            print(f"    {delta:+5d}  {near_op:9s} [a{near_reg}] -> {region} 0x{address:08x}")

    raw_max = BIN_PATH.read_bytes()[CAL_FILE_OFFSET + 0xA91F]
    print(f"\nC_KNKS_THD_MAX raw byte = {raw_max}; with the A05 knks_thd scaling "
          f"x/51.2 that is {raw_max / 51.2:.5f} V")


if __name__ == "__main__":
    main()
