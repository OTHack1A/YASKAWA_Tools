"""Tests for VAR.DAT position-variable (///P) parsing and lossless writing.

The export must reload on the robot, so the cardinal guarantee is: an unedited
export is byte-for-byte identical to the input, and editing one point changes
only that point's line.

Run:  python tests/test_posvar.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from docs.posvar import (  # noqa: E402
    parse_var_dat, write_var_dat, format_point_line, format_value,
    frame_label, CONFIG_LEN,
)

_VAR = (
    "//VAR\r\n"
    "///PFNUM 6,0,0,0\r\n"
    "///SHARE 0,0,0,0,0,4,0,0\r\n"
    "///P\r\n"
    '"PULSE"0,0,1,000000000000000000000000,0,0,0,-75007,-89458,0,-29036,96372,0,0\r\n'
    '"RECTAN"0,1,1,001010000000000000000000,0,19,68.284,68.284,394.000,178.4740,-1.2800,-43.5600,0.0000,0.0000\r\n'
    '"UNUSED"\r\n'
    '"RECTAN"0,1,9,000010000000000000000000,0,19,0.000,0.000,0.000,-133.5502,60.3071,15.8242,0.0000,0.0000\r\n'
    "///BP\r\n"
    "///EX\r\n"
)


def _make(folder):
    """Write the synthetic VAR.DAT into folder and return its path."""
    p = os.path.join(folder, "VAR.DAT")
    with open(p, "w", encoding="latin-1", newline="") as fh:
        fh.write(_VAR)
    return p


def test_parse_structure():
    """The ///P section yields one ordered point per slot with correct types."""
    with tempfile.TemporaryDirectory() as d:
        _make(d)
        data = parse_var_dat(d)
        pts = data["points"]
        assert len(pts) == 4, f"expected 4 slots, got {len(pts)}"
        assert pts[0]["type"] == "PULSE" and pts[0]["used"]
        assert pts[1]["type"] == "RECTAN" and pts[1]["tool"] == 19
        assert pts[2]["type"] == "UNUSED" and not pts[2]["used"]
        assert pts[3]["h2"] == 9
        assert frame_label(pts[1]) == "USER#01"
        assert frame_label(pts[3]) == "USER#09"
        assert frame_label(pts[0]) == "PULSE"


def test_unedited_roundtrip_is_byte_identical():
    """Parsing then writing with no edits reproduces the file exactly."""
    with tempfile.TemporaryDirectory() as d:
        _make(d)
        data = parse_var_dat(d)
        out = os.path.join(d, "out", "VAR.DAT")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        n = write_var_dat(data, out)
        assert n == 0, "no points were edited, nothing should be rewritten"
        original = open(os.path.join(d, "VAR.DAT"), "rb").read()
        produced = open(out, "rb").read()
        assert produced == original, "unedited export must be byte-identical"


def test_single_edit_changes_only_one_line():
    """Editing one point rewrites only that line; others stay byte-identical."""
    with tempfile.TemporaryDirectory() as d:
        _make(d)
        data = parse_var_dat(d)
        p = data["points"][1]
        p["values"][0] = "100.5"   # X
        p["tool"] = 5
        p["dirty"] = True
        out = os.path.join(d, "VAR.DAT")
        write_var_dat(data, out)
        lines = open(out, encoding="latin-1").read().splitlines()
        # The RECTAN line is the 6th line (index 5)
        assert "100.500" in lines[5] and ",5," in lines[5]
        # PULSE line above is untouched
        assert lines[4].startswith('"PULSE"0,0,1,')


def test_real_r1_reference_roundtrip():
    """If the bundled R1/VAR.DAT is present, an unedited export is identical."""
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    folder = os.path.join(repo, "R1")
    if not os.path.isfile(os.path.join(folder, "VAR.DAT")):
        return  # reference not present — skip
    data = parse_var_dat(folder)
    original = open(os.path.join(folder, "VAR.DAT"), "rb").read()
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "VAR.DAT")
        write_var_dat(data, out)
        produced = open(out, "rb").read()
        assert produced == original, "R1 round-trip not byte-identical"


def test_value_formatting():
    """RECTAN values get fixed decimals; PULSE values are integers; commas ok."""
    assert format_value("RECTAN", 0, "1,5") == "1.500"     # X → 3 dp, comma→dot
    assert format_value("RECTAN", 3, "10") == "10.0000"    # Rx → 4 dp
    assert format_value("PULSE", 0, "12.9") == "13"        # rounds to int
    assert format_value("PULSE", 0, "") == "0"
    assert format_value("RECTAN", 0, "junk") == "0.000"


def test_unused_slot_activation_line():
    """A formerly-UNUSED slot promoted to RECTAN emits a valid 14-field line."""
    with tempfile.TemporaryDirectory() as d:
        _make(d)
        data = parse_var_dat(d)
        p = data["points"][2]            # the UNUSED slot
        p["type"] = "RECTAN"
        p["used"] = True
        p["h1"] = 1
        p["config"] = "0" * CONFIG_LEN
        p["values"] = [format_value("RECTAN", i, "0") for i in range(8)]
        p["dirty"] = True
        line = format_point_line(p)
        assert line.startswith('"RECTAN"')
        assert len(line.split(",")) == 14, "must have 6 header + 8 value fields"


def test_no_p_section_raises():
    """A VAR.DAT without a ///P section raises RuntimeError, never silently."""
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "VAR.DAT"), "w", encoding="latin-1", newline="") as fh:
            fh.write("//VAR\r\n///B\r\n0,0\r\n")
        try:
            parse_var_dat(d)
        except RuntimeError:
            return
        assert False, "expected RuntimeError for missing ///P section"


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS  {name}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL  {name}: {exc}")
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"ERROR {name}: {exc!r}")
    print("=" * 40)
    print("ALL PASS" if failures == 0 else f"{failures} FAILURE(S)")
    sys.exit(1 if failures else 0)
