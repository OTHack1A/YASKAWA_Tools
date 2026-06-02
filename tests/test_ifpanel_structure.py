"""Structural tests for IFPANEL.DAT generation.

These tests guarantee that the file produced by ``write_ifpanel`` always has the
exact fixed structure the YRC1000 teach pendant requires, so the file can be
copied back to the controller without a load error. They run without Qt and
without the private R1 dump (a synthetic reference is built in-memory), so they
work in CI too. When the R1 reference dump is present locally, an extra
byte-exact round-trip check is performed against it.

Run:  python -m pytest tests/test_ifpanel_structure.py   (or just execute this file)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from docs.ifpanel import (  # noqa: E402
    PANEL_COUNT, FIELD_COUNT, cell_ids, parse_ifpanel, write_ifpanel,
    _empty_panel, _empty_row,
    F_SETUP, F_SHAPE, F_SUBTYPE, F_COLOR, F_N1_L1, F_N2_L1, F_TCOLOR,
    F_IN_TYPE, F_IN_ADDR, F_IN_SUB, F_OUT_TYPE, F_OUT_ADDR, F_OUT_SUB,
    F_INTERLOCK, F_UNK1, F_UNK2, F_UNK3, F_N1_L2, F_N2_L2,
)

CELLS_PER_PANEL = len(cell_ids())          # 32
LINES_PER_PANEL = CELLS_PER_PANEL + 2      # header + name + 32 rows = 34
TOTAL_LINES = PANEL_COUNT * LINES_PER_PANEL  # 510


def _assert_structure(raw_bytes):
    """Assert raw IFPANEL.DAT bytes match the fixed teach-pendant structure."""
    # 1. CRLF only — never a bare LF and never a doubled CR (the old bug).
    assert b"\r\r\n" not in raw_bytes, "doubled CR (\\r\\r\\n) — teach pendant rejects this"
    assert raw_bytes.count(b"\n") == raw_bytes.count(b"\r\n"), "found a bare LF without CR"
    # 2. File ends with exactly one CRLF.
    assert raw_bytes.endswith(b"\r\n"), "file must end with CRLF"
    assert not raw_bytes.endswith(b"\r\n\r\n"), "file must not end with a blank line"

    text = raw_bytes.decode("latin-1")
    lines = text.split("\r\n")[:-1]  # drop the empty element after the trailing CRLF
    assert len(lines) == TOTAL_LINES, f"expected {TOTAL_LINES} lines, got {len(lines)}"

    expected_ids = cell_ids()
    for p in range(PANEL_COUNT):
        base = p * LINES_PER_PANEL
        assert lines[base] == f"//IFPANEL {p + 1}", f"bad panel header at panel {p + 1}: {lines[base]!r}"
        assert lines[base + 1].startswith("///NAME "), f"bad name line at panel {p + 1}: {lines[base + 1]!r}"
        # The name line must contain exactly one separating comma (l1,l2).
        assert lines[base + 1].count(",") == 1, f"name line must have exactly one comma at panel {p + 1}: {lines[base + 1]!r}"
        for r in range(CELLS_PER_PANEL):
            row = lines[base + 2 + r]
            fields = row.split(",")
            assert len(fields) == FIELD_COUNT, (
                f"panel {p + 1} row {r}: expected {FIELD_COUNT} fields, got {len(fields)}: {row!r}")
            assert fields[0] == expected_ids[r], (
                f"panel {p + 1} row {r}: expected cell id {expected_ids[r]}, got {fields[0]!r}")


def test_default_panels_structure(tmp_path):
    panels = [_empty_panel(i) for i in range(PANEL_COUNT)]
    out = tmp_path / "IFPANEL.DAT"
    write_ifpanel(str(out), panels)
    _assert_structure(out.read_bytes())


def test_adversarial_input_stays_structurally_valid(tmp_path):
    """User text with commas / newlines / over-long names must not break the row structure."""
    panels = [_empty_panel(i) for i in range(PANEL_COUNT)]
    # Group name with a comma and a newline — must be sanitized, structure intact.
    panels[0]["name_l1"] = "ZONA 1, LATO A\r\nX"
    panels[0]["name_l2"] = "GROUP,2"
    # A button cell whose text words contain commas and are over-long.
    row = _empty_row("1A")
    row[5] = "START,STOP"          # N1_L1 with a comma
    row[6] = "VERYLONGWORD12345"   # over TEXT_MAX_LEN
    row[7] = "C\r\nD"              # embedded CRLF
    row[19] = "L2,WORD"            # N1_L2 with a comma
    panels[0]["cells"]["1A"] = row
    out = tmp_path / "IFPANEL.DAT"
    write_ifpanel(str(out), panels)
    raw = out.read_bytes()
    _assert_structure(raw)
    # And it must still parse back into PANEL_COUNT panels.
    reparsed = parse_ifpanel(str(out))
    assert len(reparsed) == PANEL_COUNT


def test_missing_and_extra_cells_are_normalized(tmp_path):
    """Panels missing some cells (or with junk cells) still produce 32 ordered rows."""
    panels = [_empty_panel(i) for i in range(PANEL_COUNT)]
    panels[3]["cells"] = {"1A": _empty_row("1A")}  # only one cell present
    panels[4]["cells"] = {}                          # no cells at all
    out = tmp_path / "IFPANEL.DAT"
    write_ifpanel(str(out), panels)
    _assert_structure(out.read_bytes())


def test_too_few_panels_are_padded(tmp_path):
    panels = [_empty_panel(0)]  # only one panel supplied
    out = tmp_path / "IFPANEL.DAT"
    write_ifpanel(str(out), panels)
    _assert_structure(out.read_bytes())


def test_valid_cell_field_layout(tmp_path):
    """A VALID button cell must place IN/OUT at the R1-verified field indices.

    Regression guard for the "syntax error 3110" bug: a phantom interlock field
    shifted IN_TYPE/IN_ADDR/OUT_TYPE/OUT_ADDR by one column, so the controller
    rejected the file. The exported row must read exactly like an R1 VALID cell:
        1A,1,7,1,0,Apri,Pinza,,0,1,1,10143,0,1,10143,0,0,0,0,Apri,Pinza,,0
    (security is auto-managed; here we only assert IN/OUT positions + reserved 0).
    """
    panels = [_empty_panel(i) for i in range(PANEL_COUNT)]
    row = _empty_row("1A")
    row[F_SETUP] = 1
    row[F_SHAPE] = 7
    row[F_SUBTYPE] = 1
    row[F_COLOR] = 0
    row[F_N1_L1] = "Apri"
    row[F_N2_L1] = "Pinza"
    row[F_TCOLOR] = 0
    row[F_INTERLOCK] = 1          # stale/invalid value — must be forced to 0
    row[F_IN_TYPE] = 1
    row[F_IN_ADDR] = 10143
    row[F_OUT_TYPE] = 1
    row[F_OUT_ADDR] = 10143
    row[F_N1_L2] = "Apri"
    row[F_N2_L2] = "Pinza"
    panels[0]["cells"]["1A"] = row

    out = tmp_path / "IFPANEL.DAT"
    write_ifpanel(str(out), panels)
    line = next(l for l in out.read_bytes().decode("latin-1").split("\r\n")
                if l.startswith("1A,"))
    f = line.split(",")

    assert f[F_IN_TYPE] == "1",      f"IN_TYPE must be at index {F_IN_TYPE}: {line!r}"
    assert f[F_IN_ADDR] == "10143",  f"IN_ADDR must be at index {F_IN_ADDR}: {line!r}"
    assert f[F_IN_SUB] == "0",       f"IN_SUB must be 0 at index {F_IN_SUB}: {line!r}"
    assert f[F_OUT_TYPE] == "1",     f"OUT_TYPE must be at index {F_OUT_TYPE}: {line!r}"
    assert f[F_OUT_ADDR] == "10143", f"OUT_ADDR must be at index {F_OUT_ADDR}: {line!r}"
    assert f[F_OUT_SUB] == "0",      f"OUT_SUB must be 0 at index {F_OUT_SUB}: {line!r}"
    for idx in (F_INTERLOCK, F_UNK1, F_UNK2, F_UNK3):
        assert f[idx] == "0", f"reserved field {idx} must be 0 (was {f[idx]!r}): {line!r}"


def test_zero_io_type_clears_address(tmp_path):
    """If a signal type is 'none' (0), its address must be forced to 0."""
    panels = [_empty_panel(i) for i in range(PANEL_COUNT)]
    row = _empty_row("1A")
    row[F_SETUP] = 1
    row[F_IN_TYPE] = 0
    row[F_IN_ADDR] = 999       # orphan address with no type
    row[F_OUT_TYPE] = 0
    row[F_OUT_ADDR] = 888
    panels[0]["cells"]["1A"] = row
    out = tmp_path / "IFPANEL.DAT"
    write_ifpanel(str(out), panels)
    line = next(l for l in out.read_bytes().decode("latin-1").split("\r\n")
                if l.startswith("1A,"))
    f = line.split(",")
    assert f[F_IN_ADDR] == "0",  f"orphan IN_ADDR must be cleared: {line!r}"
    assert f[F_OUT_ADDR] == "0", f"orphan OUT_ADDR must be cleared: {line!r}"


def test_roundtrip_against_r1_reference():
    """If the private R1 dump is present, regeneration must be byte-identical."""
    ref = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "R1", "IFPANEL.DAT")
    if not os.path.isfile(ref):
        return  # reference not available (e.g. in CI) — skip silently
    import tempfile
    panels = parse_ifpanel(ref)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".DAT") as tf:
        tmp = tf.name
    try:
        write_ifpanel(tmp, panels)
        with open(ref, "rb") as a, open(tmp, "rb") as b:
            assert a.read() == b.read(), "regenerated file is not byte-identical to R1 reference"
    finally:
        os.unlink(tmp)


if __name__ == "__main__":
    import tempfile

    class _TP:
        def __init__(self, d):
            self._d = d

        def __truediv__(self, name):
            return _P(os.path.join(self._d, name))

    class _P:
        def __init__(self, p):
            self._p = p

        def __str__(self):
            return self._p

        def read_bytes(self):
            with open(self._p, "rb") as fh:
                return fh.read()

    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                if "tmp_path" in fn.__code__.co_varnames[: fn.__code__.co_argcount]:
                    with tempfile.TemporaryDirectory() as d:
                        fn(_TP(d))
                else:
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
