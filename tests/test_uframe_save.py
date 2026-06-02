"""Tests for UFRAME.CND export robustness.

Regression guard for the bug where exporting to a *new* destination (a path that
does not exist yet) failed with "No such file or directory" because the writer
read its template from the destination path instead of the original source.

Run:  python tests/test_uframe_save.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from docs.uf_tools import write_uframe_cnd, parse_uframe_cnd  # noqa: E402

_TEMPLATE = (
    "//UFRAME 1\r\n"
    "///NAME OldName\r\n"
    "///TOOL 0\r\n"
    "////BUSER 0.000,0.000,0.000,0.0000,0.0000,0.0000\r\n"
    "//UFRAME 2\r\n"
    "///NAME Second\r\n"
    "////BUSER 1.000,2.000,3.000,4.0000,5.0000,6.0000\r\n"
)

_FRAMES = {
    1: {"name": "NewName", "x": 10.0, "y": 20.0, "z": 30.0,
        "rx": 1.0, "ry": 2.0, "rz": 3.0},
}


def _make_template(folder):
    src = os.path.join(folder, "UFRAME.CND")
    with open(src, "w", encoding="latin-1", newline="") as fh:
        fh.write(_TEMPLATE)
    return src


def test_export_to_new_destination():
    """Saving to a brand-new path (different folder) must succeed, not Errno 2."""
    with tempfile.TemporaryDirectory() as d:
        src = _make_template(d)
        dest = os.path.join(d, "exported", "deep", "UFRAME.CND")  # parent missing
        ok, err = write_uframe_cnd(dest, _FRAMES, src_path=src)
        assert ok, f"expected success, got error: {err!r}"
        assert os.path.isfile(dest), "destination file was not created"
        text = open(dest, encoding="latin-1").read()
        assert "NewName" in text, "updated name not written"
        assert "10.000,20.000,30.000" in text, "updated coords not written"


def test_inplace_overwrite_still_works():
    """Omitting src_path overwrites the file in place (backward compatible)."""
    with tempfile.TemporaryDirectory() as d:
        src = _make_template(d)
        ok, err = write_uframe_cnd(src, _FRAMES)
        assert ok, f"expected success, got error: {err!r}"
        text = open(src, encoding="latin-1").read()
        assert "NewName" in text


def test_added_frame_absent_from_template_is_written():
    """A configured frame the user added (not in the template) must be emitted.

    Regression guard for the "teach pendant loads nothing" bug: the GUI passes
    all 63 frame numbers, but the old writer only updated //UFRAME blocks already
    present in the source, so any newly configured frame was silently dropped.
    """
    with tempfile.TemporaryDirectory() as d:
        src = _make_template(d)  # template has only frames 1 and 2
        dest = os.path.join(d, "UFRAME.CND")
        frames = {
            1: {"name": "NewName", "x": 10.0, "y": 20.0, "z": 30.0,
                "rx": 1.0, "ry": 2.0, "rz": 3.0},
            # frame 5 is NOT in the template — must be synthesised
            5: {"name": "Added", "x": 111.0, "y": 222.0, "z": 333.0,
                "rx": 4.0, "ry": 5.0, "rz": 6.0},
            # frame 7 is empty/unconfigured — must be skipped (no bloat)
            7: {"name": "", "x": 0.0, "y": 0.0, "z": 0.0,
                "rx": 0.0, "ry": 0.0, "rz": 0.0},
        }
        ok, err = write_uframe_cnd(dest, frames, src_path=src)
        assert ok, f"expected success, got error: {err!r}"
        reparsed = {f["num"]: f for f in parse_uframe_cnd(dest)}
        assert 5 in reparsed, "added frame 5 was dropped"
        assert reparsed[5]["name"] == "Added"
        assert abs(reparsed[5]["x"] - 111.0) < 1e-6
        assert abs(reparsed[5]["rz"] - 6.0) < 1e-6
        assert 7 not in reparsed, "empty unconfigured frame should not be written"
        # frames are emitted in numeric order
        text = open(dest, encoding="latin-1").read()
        assert text.index("//UFRAME 1") < text.index("//UFRAME 2") < text.index("//UFRAME 5")


def test_missing_source_reports_error_cleanly():
    """A genuinely missing source returns (False, msg), never raises."""
    with tempfile.TemporaryDirectory() as d:
        dest = os.path.join(d, "UFRAME.CND")
        ok, err = write_uframe_cnd(dest, _FRAMES, src_path=os.path.join(d, "nope.CND"))
        assert ok is False and err, "missing source should fail gracefully"


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
