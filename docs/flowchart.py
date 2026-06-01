"""
JBI INFORM flowchart: parser → layout → PDF + draw.io.
All edges are orthogonal (H/V only).  Multi-column for tall charts.
"""
from __future__ import annotations
import os, re, math, textwrap
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# ── AST ───────────────────────────────────────────────────────────────────────

@dataclass
class IfNode:
    cond: str
    yes_body: list
    elseif_branches: list   # [(cond, body), ...]
    else_body: list

@dataclass
class SwitchNode:
    expr: str
    cases: list             # [(label_str, body), ...]

@dataclass
class CallNode:
    job: str

@dataclass
class JumpNode:
    label: str

@dataclass
class LabelNode:
    name: str

@dataclass
class StmtNode:
    text: str

# ── TOKENISER / PARSER ────────────────────────────────────────────────────────

_R_IF  = re.compile(r'^IFTHENEXP\s*(.*)',  re.I)
_R_EI  = re.compile(r'^ELSEIFEXP\s*(.*)',  re.I)
_R_SW  = re.compile(r'^SWITCHCASE\s*(.*)', re.I)
_R_CS  = re.compile(r'^CASE\s+(.*)',       re.I)
_R_CL  = re.compile(r'^CALL\s+JOB:(\S+)', re.I)
_R_JP  = re.compile(r'^JUMP\s+\*(\S+)',   re.I)
_R_LB  = re.compile(r'^\*(\S+)')
_R_CMT = re.compile(r"^'")

_STOP = frozenset(['ELSE', 'ELSEIFEXP', 'ENDIF', 'SWEND', 'CASE', 'DEFAULT'])


_MAX_JBI_SIZE = 50 * 1024 * 1024   # 50 MiB hard cap — JBI files are KB-sized in practice


def _tokenise(path: str) -> List[str]:
    """Read a JBI file and return the INFORM instruction tokens from its //INST block."""
    tokens: List[str] = []
    in_inst = False
    try:
        # Reject pathologically large inputs to avoid DoS via crafted JBI.
        if os.path.getsize(path) > _MAX_JBI_SIZE:
            return tokens
        with open(path, encoding='utf-8', errors='replace') as f:
            for raw in f:
                line = raw.strip()
                if line == '//INST':
                    in_inst = True; continue
                if not in_inst: continue
                if line.startswith('//') or line.startswith('///'): continue
                if _R_CMT.match(line): continue
                if line in ('NOP', 'END', ''): continue
                tokens.append(line)
    except Exception:
        pass
    return tokens


def _parse(tokens: List[str], pos: int = 0) -> Tuple[list, int]:
    """Recursively parse tokens into a nested statement AST (IF/WHILE/SWITCH blocks)."""
    body: list = []
    while pos < len(tokens):
        tok   = tokens[pos]
        upper = tok.upper().split()[0] if tok.split() else ''
        if upper in _STOP:
            break

        m = _R_IF.match(tok)
        if m:
            cond = m.group(1).strip(); pos += 1
            yes, pos = _parse(tokens, pos)
            elseifs: list = []; else_body: list = []
            while pos < len(tokens):
                cur = tokens[pos].upper()
                if cur == 'ENDIF':
                    pos += 1; break
                elif cur == 'ELSE':
                    pos += 1; else_body, pos = _parse(tokens, pos)
                elif tokens[pos].upper().startswith('ELSEIFEXP'):
                    em = _R_EI.match(tokens[pos])
                    ec = em.group(1).strip() if em else ''
                    pos += 1; eb, pos = _parse(tokens, pos)
                    elseifs.append((ec, eb))
                else:
                    break
            body.append(IfNode(cond, yes, elseifs, else_body)); continue

        m = _R_SW.match(tok)
        if m:
            expr = m.group(1).strip(); pos += 1
            cases: list = []
            while pos < len(tokens):
                cur = tokens[pos].upper()
                if cur == 'SWEND':
                    pos += 1; break
                elif cur == 'DEFAULT':
                    pos += 1; cb, pos = _parse(tokens, pos); cases.append(('DEFAULT', cb))
                else:
                    csm = _R_CS.match(tokens[pos])
                    if csm:
                        lbl = csm.group(1).strip(); pos += 1
                        cb, pos = _parse(tokens, pos); cases.append((lbl, cb))
                    else:
                        pos += 1
            body.append(SwitchNode(expr, cases)); continue

        m = _R_CL.match(tok)
        if m: body.append(CallNode(m.group(1))); pos += 1; continue

        m = _R_JP.match(tok)
        if m: body.append(JumpNode(m.group(1))); pos += 1; continue

        m = _R_LB.match(tok)
        if m: body.append(LabelNode(m.group(1))); pos += 1; continue

        body.append(StmtNode(tok[:60])); pos += 1

    return body, pos


def parse_jbi(path: str) -> list:
    """Parse a JBI file into a nested statement AST."""
    return _parse(_tokenise(path))[0]


# ── STATEMENT CLASSIFICATION ──────────────────────────────────────────────────

_R_MOVE  = re.compile(r'^MOV[LJCS]\b', re.I)
_R_ALARM = re.compile(r'^SET(UALM|UALARM|ALRM)\b', re.I)
_R_IO    = re.compile(r'^(SET|DOUT|DIN|WAIT|AOUT|AIN|PULSE|TIMER|MSG)\b', re.I)


def _classify(text: str) -> str:
    """Classify an instruction line into a flowchart node kind (term/proc/move/io/...)."""
    t = text.strip()
    if _R_MOVE.match(t):  return 'move'
    if _R_ALARM.match(t): return 'alarm'
    if _R_IO.match(t):    return 'io'
    return 'proc'


# ── LAYOUT CONSTANTS ──────────────────────────────────────────────────────────

_BW      = 140    # default box width (pt)
_BH      = 30     # default box height (pt)
_DW_MIN  = 164    # minimum diamond width
_DH_MIN  = 48     # minimum diamond height
_GV      = 26     # vertical gap between nodes
_GH      = 50     # gap: diamond right edge → YES branch left edge
_CHAR_W  = 4.1    # approximate pt per char at 7pt font
_LINE_H  = 12     # pt per text line in diamond
_WRAP_D  = 20     # max chars per line for diamond wrapping
_COL_MAX = 820    # max layout height before multi-column (pt)
_COL_GAP = 70     # horizontal gap between columns (pt)


# ── DATA CLASSES ──────────────────────────────────────────────────────────────

@dataclass
class Shape:
    kind: str
    cx: float; cy: float
    w: float;  h: float
    text: str
    sid: int = 0
    red_border: bool = False   # True for CALL in non-MAIN flowcharts

@dataclass
class Edge:
    x1: float; y1: float
    x2: float; y2: float
    lbl: str  = ''
    h_first: bool = False      # YES branches → go horizontal first
    src_sid: int = 0           # source shape sid (0 = unattached)
    dst_sid: int = 0           # target shape sid (0 = unattached)
    via_x: Optional[float] = None  # route H→V(at via_x)→H, used by merge edges
                                   # so they never cross the stacked YES boxes

@dataclass
class FC:
    name: str
    shapes: List[Shape] = field(default_factory=list)
    edges:  List[Edge]  = field(default_factory=list)
    width:  float = 0.0
    height: float = 0.0


_sid_counter = 0

def _next_sid() -> int:
    """Return the next unique shape id (monotonic counter)."""
    global _sid_counter
    _sid_counter += 1
    return _sid_counter


# ── DIAMOND SIZING ────────────────────────────────────────────────────────────

def _diamond_fit(text: str) -> Tuple[str, float, float]:
    """Return (wrapped_text, width, height) so text fits inside the rhombus."""
    wrapped = '\n'.join(textwrap.wrap(text, _WRAP_D)) if len(text) > _WRAP_D else text
    lines   = wrapped.split('\n')
    max_len = max(len(l) for l in lines) if lines else 1
    n       = len(lines)
    # Inscribed rect of rhombus(w,h) = (w/2, h/2).
    # We need inscribed rect ≥ text area + padding.
    dw = max(float(_DW_MIN), max_len * _CHAR_W * 2 + 30)
    dh = max(float(_DH_MIN), n * _LINE_H * 2 + 16)
    return wrapped, round(dw), round(dh)


def _wrap(text: str, chars: int = 22) -> str:
    """Word-wrap text to a maximum number of characters per line."""
    return '\n'.join(textwrap.wrap(text, chars)) if len(text) > chars else text


# ── LAYOUT ────────────────────────────────────────────────────────────────────

def _layout_seq(ast: list, fc: FC, x: float, y: float,
                prev_exit: Optional[Tuple[float, float]] = None,
                is_main: bool = False) -> Tuple[float, float, Optional[Tuple[float, float]], bool]:
    """
    Layout nodes top-to-bottom from (x, y).
    Adds orthogonal-capable edges between consecutive nodes.
    Returns (max_right_x, bottom_y, last_exit_point, terminated).
    `terminated` is True if the sequence ends with a flow-terminating node
    (JumpNode); the caller should NOT add a merge-back edge from this branch.
    """
    max_x = x
    terminated = False
    for node in ast:
        nb = len(fc.shapes)
        try:
            bx, by, exit_cx = _layout_node(node, fc, x, y, is_main)
        except Exception:
            # Defensive: never propagate layout errors; advance y minimally.
            bx, by, exit_cx = x + _BW, y + _BH, x + _BW / 2
        if bx > max_x:
            max_x = bx
        if len(fc.shapes) > nb:
            first = fc.shapes[nb]
            ex, ey = first.cx, first.cy - first.h / 2
            if prev_exit is not None and not terminated:
                fc.edges.append(Edge(prev_exit[0], prev_exit[1], ex, ey))
            prev_exit = (exit_cx, by)
        else:
            if prev_exit is not None:
                prev_exit = (exit_cx, by)
        # Track flow termination: after a JUMP no fall-through edge should be drawn.
        if isinstance(node, JumpNode):
            terminated = True
        else:
            terminated = False
        y = by + _GV
    return max_x, y - _GV, prev_exit, terminated


def _layout_node(node, fc: FC, x: float, y: float,
                 is_main: bool = False) -> Tuple[float, float, float]:
    """Returns (max_x, bottom_y, exit_cx) where exit_cx is the x of the flow exit."""
    if isinstance(node, LabelNode):
        fc.shapes.append(Shape('label', x + _BW/2, y + _BH/2, _BW, _BH,
                               f'*{node.name}', _next_sid()))
        return x + _BW, y + _BH, x + _BW/2

    if isinstance(node, JumpNode):
        fc.shapes.append(Shape('jump', x + _BW/2, y + _BH/2, _BW, _BH,
                               f'→ *{node.label}', _next_sid()))
        return x + _BW, y + _BH, x + _BW/2

    if isinstance(node, CallNode):
        kind = 'call_plain' if is_main else 'call'
        fc.shapes.append(Shape(kind, x + _BW/2, y + _BH/2, _BW, _BH,
                               _wrap(node.job, 22), _next_sid()))
        return x + _BW, y + _BH, x + _BW/2

    if isinstance(node, StmtNode):
        kind = _classify(node.text)
        fc.shapes.append(Shape(kind, x + _BW/2, y + _BH/2, _BW, _BH,
                               _wrap(node.text, 22), _next_sid()))
        return x + _BW, y + _BH, x + _BW/2

    if isinstance(node, IfNode):
        max_x, merge_y = _layout_if(node, fc, x, y, is_main)
        return max_x, merge_y, x + _BW/2   # exit always at main-column centre

    if isinstance(node, SwitchNode):
        max_x, bottom_y = _layout_sw(node, fc, x, y, is_main)
        return max_x, bottom_y, x + _BW/2

    return x + _BW, y + _BH, x + _BW/2


def _layout_if(node: IfNode, fc: FC, x: float, y: float,
               is_main: bool = False) -> Tuple[float, float]:
    """
    IF/ELSEIF chain: diamonds stacked vertically (NO path).
    Diamonds are centred on the main-flow axis (merge_cx) so that the NO edges
    are purely vertical and the connection to the next sequential element is
    a straight line (no Z-curve).
    YES bodies are placed to the right; each body starts below the previous
    one's bottom to prevent vertical overlap between ELSEIF branches.
    """
    all_branches = [(node.cond, node.yes_body)]
    for ec, eb in node.elseif_branches:
        all_branches.append((ec, eb))

    # Uniform diamond width ensures all NO edges share the same centre x.
    sizes  = [_diamond_fit(cond) for cond, _ in all_branches]
    max_dw = max(s[1] for s in sizes)

    # Main-flow axis: sequential boxes are centred here.
    merge_cx = x + _BW / 2
    # Diamond right edge (diamond centred on merge_cx).
    d_right  = merge_cx + max_dw / 2
    # YES branch column left edge.
    yes_x    = d_right + _GH
    # Rightmost extent so far (grows with YES branch content).
    max_x    = d_right

    current_y  = y
    diamonds:  List[Shape] = []
    yes_exits: List[Tuple[float, float, bool]] = []   # (bottom_y, exit_cx, terminated)
    # Floor for next YES body's top to prevent vertical overlap between branches.
    min_yes_y  = y

    for (cond, yes_body), (wrapped, _, dh) in zip(all_branches, sizes):
        dw = max_dw
        # Centre diamond on the main-flow column.
        d  = Shape('diamond', merge_cx, current_y + dh/2, dw, dh, wrapped, _next_sid())
        fc.shapes.append(d)
        diamonds.append(d)

        # YES body y: ideal = diamond-centre alignment; actual = max(ideal, floor).
        yes_y_ideal = current_y + (dh - _BH) / 2
        yes_y       = max(yes_y_ideal, min_yes_y)

        if yes_body:
            nb_yes = len(fc.shapes)
            rx, by, yes_seq_exit, yes_term = _layout_seq(
                yes_body, fc, yes_x, yes_y, prev_exit=None, is_main=is_main)
            # YES edge: L-shape from diamond RIGHT edge → top-centre of first YES shape.
            if len(fc.shapes) > nb_yes:
                fy = fc.shapes[nb_yes]
                fc.edges.append(Edge(d_right,       current_y + dh / 2,
                                     fy.cx, fy.cy - fy.h / 2, 'YES', h_first=True,
                                     src_sid=d.sid, dst_sid=fy.sid))
            else:
                fc.edges.append(Edge(d_right, current_y + dh / 2,
                                     yes_x + _BW/2, current_y + dh / 2, 'YES', h_first=True,
                                     src_sid=d.sid))
            exit_cx   = yes_seq_exit[0] if yes_seq_exit else (yes_x + _BW / 2)
            yes_exits.append((by, exit_cx, yes_term))
            min_yes_y = by + _GV          # next YES body must start below this bottom
            if rx > max_x:
                max_x = rx
        else:
            yes_exits.append((current_y + dh, yes_x + _BW / 2, False))
            min_yes_y = max(min_yes_y, current_y + dh + _GV)

        current_y += dh + _GV

    # ELSE body (NO path of last diamond, directly below diamond stack).
    else_terminated = False
    if node.else_body:
        ld = diamonds[-1]
        nb_else = len(fc.shapes)
        rx, by, _else_exit, else_terminated = _layout_seq(
            node.else_body, fc, x, current_y, is_main=is_main)
        if len(fc.shapes) > nb_else:
            fe = fc.shapes[nb_else]
            fc.edges.append(Edge(ld.cx, ld.cy + ld.h / 2,
                                 fe.cx, fe.cy - fe.h / 2, 'NO',
                                 src_sid=ld.sid, dst_sid=fe.sid))
        else:
            fc.edges.append(Edge(ld.cx, ld.cy + ld.h / 2, merge_cx, current_y, 'NO',
                                 src_sid=ld.sid))
        if rx > max_x:
            max_x = rx
        merge_y = by + _GV
    else:
        merge_y = current_y

    # Guarantee merge_y is below every YES-branch bottom (prevents backward edges).
    if yes_exits:
        # Only consider non-terminated branches; terminated ones don't merge here.
        non_term = [b for b, _, term in yes_exits if not term]
        if non_term:
            max_yes_bot = max(non_term)
            merge_y     = max(merge_y, max_yes_bot + _GV)

    # NO edges between consecutive diamonds (same cx = merge_cx → purely vertical).
    for i in range(len(diamonds) - 1):
        da, db = diamonds[i], diamonds[i + 1]
        fc.edges.append(Edge(da.cx, da.cy + da.h / 2, db.cx, db.cy - db.h / 2, 'NO',
                             src_sid=da.sid, dst_sid=db.sid))

    # Final NO edge: last diamond bottom → merge point.
    # Diamond cx == merge_cx → straight vertical arrow.
    if not node.else_body:
        ld = diamonds[-1]
        fc.edges.append(Edge(ld.cx, ld.cy + ld.h / 2, merge_cx, merge_y, 'NO',
                             src_sid=ld.sid))

    # YES-branch bottoms → merge point.
    # Route through a dedicated vertical "lane" placed in the gap between the
    # diamond column and the YES column (H→V→H).  This keeps the merge edges
    # OUT of the YES-box column, so an upper branch's merge edge never runs
    # vertically through the box of a lower branch (the old Z-route did, making
    # stacked YES boxes look wrongly chained together).  Skip branches that
    # terminate with JUMP (flow already exited).
    merge_lane_x = d_right + _GH / 2
    for by2, bcx, term in yes_exits:
        if term:
            continue
        if abs(by2 - merge_y) > 2 or abs(bcx - merge_cx) > 2:
            fc.edges.append(Edge(bcx, by2, merge_cx, merge_y, via_x=merge_lane_x))

    return max_x, merge_y


def _layout_sw(node: SwitchNode, fc: FC, x: float, y: float,
               is_main: bool = False) -> Tuple[float, float]:
    """SWITCHCASE: diamond at top (on the main-flow column), one column per CASE."""
    sw_text, dw, dh = _diamond_fit(f'SWITCH\n{node.expr}')
    # Centre the diamond on the main-flow column (x + _BW/2), exactly like IF
    # diamonds, so the edge coming in from the preceding box is purely vertical
    # (centring on x + dw/2 made wider diamonds drift sideways → entry Z-jog).
    cx_main = x + _BW / 2
    sw = Shape('diamond', cx_main, y + dh/2, dw, dh, sw_text, _next_sid())
    fc.shapes.append(sw)

    n = len(node.cases)
    if n == 0:
        return max(x + _BW, cx_main + dw/2), y + dh  # type: ignore[return-value]

    col_w      = _BW + _GH
    max_right  = max(x + _BW, cx_main + dw/2)
    max_bottom = y + dh + _GV
    for i, (lbl, cbody) in enumerate(node.cases):
        # First case sits on the main column (vertical edge from the diamond),
        # the rest fan out to the right.
        cx2  = x + i * col_w
        ltxt = f'CASE\n{lbl}' if lbl != 'DEFAULT' else 'DEFAULT'
        cl   = Shape('label', cx2 + _BW/2, y + dh + _GV + _BH/2, _BW, _BH, ltxt, _next_sid())
        fc.shapes.append(cl)
        fc.edges.append(Edge(sw.cx, sw.cy + dh/2, cx2 + _BW/2, y + dh + _GV, lbl))
        body_y = y + dh + _GV + _BH + _GV
        if cbody:
            rx, by, _ = _layout_seq(cbody, fc, cx2, body_y, is_main=is_main)
            max_right  = max(max_right, rx)
            max_bottom = max(max_bottom, by)
        else:
            max_bottom = max(max_bottom, y + dh + _GV + _BH)
        max_right = max(max_right, cx2 + _BW)

    return max_right, max_bottom


# ── POST-LAYOUT HELPERS ───────────────────────────────────────────────────────

def _attach_sids(fc: FC, tol: float = 1.5) -> None:
    """
    For any edge missing src_sid/dst_sid, infer them by matching endpoint
    coordinates to a shape boundary port (top / bottom / left-mid / right-mid).
    Enables shape-aware column routing downstream.
    """
    # Build port table once.
    ports: List[Tuple[int, float, float]] = []
    for s in fc.shapes:
        hw, hh = s.w / 2, s.h / 2
        ports.append((s.sid, s.cx,        s.cy - hh))
        ports.append((s.sid, s.cx,        s.cy + hh))
        ports.append((s.sid, s.cx - hw,   s.cy     ))
        ports.append((s.sid, s.cx + hw,   s.cy     ))

    def _find(x: float, y: float) -> int:
        """Return the shape id of the port nearest to (x, y) within tolerance."""
        best, bdist = 0, tol
        for sid, px, py in ports:
            d = abs(px - x) + abs(py - y)
            if d < bdist:
                bdist = d
                best  = sid
        return best

    for e in fc.edges:
        if not e.src_sid:
            e.src_sid = _find(e.x1, e.y1)
        if not e.dst_sid:
            e.dst_sid = _find(e.x2, e.y2)


def _dedup_edges(fc: FC) -> None:
    """
    Remove fully-redundant collinear edges. An edge B is redundant when:
      - A and B are both purely vertical (same x) or both purely horizontal (same y);
      - B's span is fully contained in A's span;
      - A and B end at the same terminal point (so dropping B keeps the arrowhead).
    Conservative: any edge with a label is kept.
    """
    edges = fc.edges
    n = len(edges)
    to_drop: set = set()
    eps = 0.5

    def _seg(e: 'Edge'):
        """Classify an edge as vertical or horizontal and return its normalized span."""
        if abs(e.x1 - e.x2) < eps:
            return 'V', (e.x1 + e.x2) / 2, min(e.y1, e.y2), max(e.y1, e.y2)
        if abs(e.y1 - e.y2) < eps:
            return 'H', (e.y1 + e.y2) / 2, min(e.x1, e.x2), max(e.x1, e.x2)
        return None  # Z / L-shape — skip

    segs = [(_seg(e), i) for i, e in enumerate(edges)]

    for i in range(n):
        si = segs[i][0]
        if si is None or i in to_drop:
            continue
        for j in range(n):
            if i == j or j in to_drop:
                continue
            sj = segs[j][0]
            if sj is None or si[0] != sj[0] or abs(si[1] - sj[1]) > eps:
                continue
            # Same orientation and axis line: check if j is contained in i.
            contained = (sj[2] >= si[2] - eps and sj[3] <= si[3] + eps)
            if not contained:
                continue
            # Preserve label-carrying edge if the container has no label.
            if edges[j].lbl and not edges[i].lbl:
                continue
            len_i = si[3] - si[2]
            len_j = sj[3] - sj[2]
            strictly_shorter = len_j < len_i - eps
            same_length      = abs(len_j - len_i) <= eps
            # Drop the strictly shorter one; for exact duplicates,
            # drop the one with the higher index (deterministic).
            if strictly_shorter or (same_length and j > i):
                to_drop.add(j)

    if to_drop:
        fc.edges = [e for k, e in enumerate(edges) if k not in to_drop]


# ── MULTI-COLUMN REDISTRIBUTION ───────────────────────────────────────────────

def _redistribute_columns(fc: FC, end_edge_idx: Optional[int]) -> None:
    """
    If fc.height > _COL_MAX, rearrange shapes into side-by-side columns.

    Columns are chosen so that no shape straddles a column boundary
    (boundaries are placed in the gaps between shapes).  Cross-column
    edges are dropped using shape-id membership (NOT coordinate-only),
    avoiding the dangling-arrow bug where the edge's coordinates fall in
    one column but its target shape lives in another.
    """
    if fc.height <= _COL_MAX:
        return

    # ── 1. Choose column boundaries that snap to shape gaps ──────────────────
    # Sort shapes by cy. Walk top-down; close current column at last shape
    # whose bottom is ≤ running_top + _COL_MAX.
    shapes_sorted = sorted(fc.shapes, key=lambda s: s.cy)
    col_of: dict = {}     # sid -> col index
    boundaries: List[float] = [0.0]  # boundary y values: col 0 starts at 0

    current_top = 0.0
    current_col = 0
    for s in shapes_sorted:
        s_top = s.cy - s.h / 2
        s_bot = s.cy + s.h / 2
        if s_bot - current_top > _COL_MAX and col_of:
            # Close current column at gap above s.
            boundaries.append(s_top)
            current_col += 1
            current_top = s_top
        col_of[s.sid] = current_col

    n_cols = current_col + 1
    if n_cols <= 1:
        return  # everything fits after gap snapping; no need to redistribute.

    # ── 2. Compute per-column max right-x for layout offset ──────────────────
    col_rx = [0.0] * n_cols
    for s in fc.shapes:
        c  = col_of[s.sid]
        rx = s.cx + s.w / 2
        if rx > col_rx[c]:
            col_rx[c] = rx

    col_xoff = [0.0] * n_cols
    for i in range(1, n_cols):
        col_xoff[i] = col_xoff[i-1] + col_rx[i-1] + _COL_GAP

    # ── 3. Shift shapes ──────────────────────────────────────────────────────
    for s in fc.shapes:
        c = col_of[s.sid]
        if c > 0:
            s.cx += col_xoff[c]
            s.cy -= boundaries[c]

    # ── 4. Process edges using shape-id membership ───────────────────────────
    def _edge_col(e: 'Edge') -> Tuple[int, int]:
        """Return the (source, destination) column indices of an edge."""
        c1 = col_of.get(e.src_sid)
        c2 = col_of.get(e.dst_sid)
        # Fallback to coordinate-based lookup if sid is missing.
        if c1 is None:
            c1 = _coord_col(e.y1)
        if c2 is None:
            c2 = _coord_col(e.y2)
        return c1, c2

    def _coord_col(y: float) -> int:
        """Map a y-coordinate to its column index using the column boundaries."""
        for c in range(n_cols - 1, -1, -1):
            if y >= boundaries[c]:
                return c
        return 0

    kept: List[Edge] = []
    end_edge_dropped = False
    for idx, e in enumerate(fc.edges):
        c1, c2 = _edge_col(e)
        if c1 != c2:
            if idx == end_edge_idx:
                end_edge_dropped = True
            # Cross-column edge: drop silently.
            continue
        c = c1
        if c > 0:
            e.x1 += col_xoff[c]; e.y1 -= boundaries[c]
            e.x2 += col_xoff[c]; e.y2 -= boundaries[c]
        kept.append(e)

    # ── 5. Add END stub ONLY when the original end edge was actually dropped ─
    if end_edge_dropped and fc.shapes:
        end_s = fc.shapes[-1]   # END is always the last shape (sid=last)
        stub_y1 = end_s.cy - end_s.h / 2 - min(12, _GV)
        kept.append(Edge(end_s.cx, stub_y1,
                         end_s.cx, end_s.cy - end_s.h / 2,
                         dst_sid=end_s.sid))

    fc.edges = kept

    # ── 6. Update bounding box ───────────────────────────────────────────────
    if fc.shapes:
        all_rx = [s.cx + s.w/2 for s in fc.shapes]
        all_by = [s.cy + s.h/2 for s in fc.shapes]
        fc.width  = max(all_rx) + 20
        fc.height = max(all_by) + 20


# ── MAIN LAYOUT ENTRY POINT ───────────────────────────────────────────────────

def layout_jbi(name: str, ast: list) -> FC:
    """Lay out a parsed JBI AST into positioned flowchart nodes and edges (an FC)."""
    global _sid_counter
    _sid_counter = 0
    fc      = FC(name=name)
    is_main = name.upper() == 'MAIN'

    s_start = Shape('term', _BW/2, _BH/2, _BW, _BH, 'START', _next_sid())
    fc.shapes.append(s_start)
    start_exit = (s_start.cx, s_start.cy + _BH/2)

    y0 = _BH + _GV
    if ast:
        max_x, bottom_y, last_exit, last_terminated = _layout_seq(
            ast, fc, 0, y0, prev_exit=start_exit, is_main=is_main)
        end_y = bottom_y + _GV
    else:
        max_x, bottom_y, last_exit = _BW, y0, start_exit
        last_terminated = False
        end_y = y0

    s_end = Shape('term', _BW/2, end_y + _BH/2, _BW, _BH, 'END', _next_sid())
    fc.shapes.append(s_end)

    end_edge: Optional[Edge] = None
    if last_exit and not last_terminated:
        end_edge = Edge(last_exit[0], last_exit[1],
                        s_end.cx, s_end.cy - _BH/2,
                        dst_sid=s_end.sid)
        fc.edges.append(end_edge)

    fc.width  = max(max_x, _BW) + 20
    fc.height = end_y + _BH + 20

    end_edge_idx = len(fc.edges) - 1 if end_edge else None
    _attach_sids(fc)
    _redistribute_columns(fc, end_edge_idx)
    _dedup_edges(fc)
    return fc


# ── PDF RENDERING ─────────────────────────────────────────────────────────────

# Colour palette (bright, solar)
_C = {
    'term':       '#A85C42',   # terracotta
    'proc':       '#6B6B6B',   # neutral gray
    'move':       '#F9A825',   # amber/yellow   (MOVL/MOVJ)
    'io':         '#ECEFF1',   # near-white     (SET/DOUT/DIN/WAIT)
    'alarm':      '#C62828',   # deep red       (SETUALM)
    'call':       '#2E7D32',   # forest green   (CALL JOB – non MAIN)
    'call_plain': '#388E3C',   # lighter green  (CALL JOB – MAIN)
    'diamond':    '#EF6C00',   # deep orange
    'label':      '#4527A0',   # deep indigo    (*Lxxx)
    'jump':       '#4527A0',   # same as label  (JUMP)
}
_C_TEXT = {          # foreground for shapes where bg is light
    'io':   '#1A1A1A',
    'move': '#4A3000',
}
_C_BORDER = {        # extra border colour
    'call': '#C62828',   # red border for non-MAIN CALL
}

_FONT_SZ  = 7     # pt, text in shapes
_EDGE_LW  = 0.7   # line width for edges
_SHAPE_LW = 0.0   # no border on filled shapes (except io/call)


def _to_rl_factory(ox: float, oy: float, ph: float):
    """Return a converter: (layout_x, layout_y) → (rl_x, rl_y)."""
    def _to(cx, cy):
        """Convert layout coordinates to ReportLab page coordinates."""
        return ox + cx, ph - oy - cy
    return _to


def _draw_arrowhead(c, x2, y2, dx, dy):
    """Draw filled arrowhead at (x2, y2) pointing in direction (dx, dy)."""
    length = math.hypot(dx, dy)
    if length < 0.1:
        return
    ux, uy = dx / length, dy / length
    aw, ah = 4, 7
    p = c.beginPath()
    p.moveTo(x2, y2)
    p.lineTo(x2 - ah*ux + aw/2*uy, y2 - ah*uy - aw/2*ux)
    p.lineTo(x2 - ah*ux - aw/2*uy, y2 - ah*uy + aw/2*ux)
    p.close()
    c.drawPath(p, fill=1, stroke=0)


def _draw_ortho_edge(c, x1r, y1r, x2r, y2r, h_first: bool, lbl: str,
                     font_name: str, draw_arrow: bool = True, via_xr=None):
    """Draw an orthogonal (H/V only) edge with arrowhead and optional label."""
    from reportlab.lib import colors as rc
    eps = 0.8
    c.setStrokeColor(rc.HexColor('#333333'))
    c.setFillColor(rc.HexColor('#333333'))
    c.setLineWidth(_EDGE_LW)

    # Explicit lane routing (H → V at via_xr → H): used by IF/ELSEIF merge
    # edges so they bypass the stacked YES-box column entirely.
    if via_xr is not None and abs(via_xr - x1r) > eps:
        p = c.beginPath()
        p.moveTo(x1r, y1r)
        p.lineTo(via_xr, y1r)
        p.lineTo(via_xr, y2r)
        p.lineTo(x2r, y2r)
        c.drawPath(p, stroke=1, fill=0)
        if draw_arrow:
            _draw_arrowhead(c, x2r, y2r, x2r - via_xr, 0)
        if lbl:
            c.setFont(font_name, 6)
            c.setFillColor(rc.HexColor('#444444'))
            c.drawCentredString((via_xr + x2r) / 2 + 5, y2r + 3, lbl)
        return

    # Determine path segments
    same_x = abs(x1r - x2r) < eps
    same_y = abs(y1r - y2r) < eps

    if same_x or same_y:
        # Single straight segment
        p = c.beginPath()
        p.moveTo(x1r, y1r)
        p.lineTo(x2r, y2r)
        c.drawPath(p, stroke=1, fill=0)
        arr_dx, arr_dy = x2r - x1r, y2r - y1r
        # Place label slightly off the midpoint of the straight segment.
        mid_x, mid_y   = (x1r + x2r)/2, (y1r + y2r)/2
    elif h_first:
        # L-shape: horizontal then vertical
        p = c.beginPath()
        p.moveTo(x1r, y1r)
        p.lineTo(x2r, y1r)
        p.lineTo(x2r, y2r)
        c.drawPath(p, stroke=1, fill=0)
        arr_dx, arr_dy = 0, y2r - y1r
        # Label on the horizontal segment.
        mid_x, mid_y   = (x1r + x2r)/2, y1r
    else:
        # Z-shape: vertical → horizontal → vertical.
        # Route the horizontal segment close to the TARGET (just outside its
        # entry edge) rather than at the midpoint.  This keeps the horizontal
        # out of the source-column shape area, avoiding crossings.
        gap   = 12.0
        span  = y1r - y2r        # >0 means target is below in display
        if abs(span) <= 2 * gap:
            mid_y_r = (y1r + y2r) / 2
        elif span > 0:
            # Layout-direction-down arrow: target sits lower in rl coords,
            # i.e. y2r < y1r.  Place horizontal just above target.
            mid_y_r = y2r + gap
        else:
            mid_y_r = y2r - gap
        p = c.beginPath()
        p.moveTo(x1r, y1r)
        p.lineTo(x1r, mid_y_r)
        p.lineTo(x2r, mid_y_r)
        p.lineTo(x2r, y2r)
        c.drawPath(p, stroke=1, fill=0)
        arr_dx, arr_dy = 0, y2r - mid_y_r
        # Place label on the horizontal segment.
        mid_x, mid_y   = (x1r + x2r)/2, mid_y_r

    if draw_arrow:
        _draw_arrowhead(c, x2r, y2r, arr_dx, arr_dy)

    if lbl:
        c.setFont(font_name, 6)
        c.setFillColor(rc.HexColor('#444444'))
        c.drawCentredString(mid_x + 5, mid_y + 3, lbl)


def _draw_shape(c, s: Shape, to_rl, font_name: str):
    """Render one Shape on the canvas."""
    from reportlab.lib import colors as rc

    rx, ry = to_rl(s.cx, s.cy)
    hw, hh = s.w / 2, s.h / 2

    fill_hex  = _C.get(s.kind, '#6B6B6B')
    fg_hex    = _C_TEXT.get(s.kind, '#FFFFFF')
    fill_c    = rc.HexColor(fill_hex)
    fg_c      = rc.HexColor(fg_hex)

    c.setFillColor(fill_c)
    c.setStrokeColor(fill_c)
    c.setLineWidth(0)

    if s.kind == 'term':
        r = hh * 0.9
        c.roundRect(rx - hw, ry - hh, s.w, s.h, r, fill=1, stroke=0)

    elif s.kind == 'diamond':
        p = c.beginPath()
        p.moveTo(rx,      ry + hh)
        p.lineTo(rx + hw, ry)
        p.lineTo(rx,      ry - hh)
        p.lineTo(rx - hw, ry)
        p.close()
        c.drawPath(p, fill=1, stroke=0)

    elif s.kind == 'call':
        # Green fill + red border (predefined-process / sub-routine)
        c.rect(rx - hw, ry - hh, s.w, s.h, fill=1, stroke=0)
        c.setStrokeColor(rc.HexColor(_C_BORDER['call']))
        c.setLineWidth(1.4)
        c.rect(rx - hw, ry - hh, s.w, s.h, fill=0, stroke=1)
        c.setLineWidth(0.4)
        c.setStrokeColor(rc.HexColor('#FFFFFF'))
        c.rect(rx - hw + 3, ry - hh + 2, s.w - 6, s.h - 4, fill=0, stroke=1)
        c.setLineWidth(0)

    elif s.kind == 'io':
        # White / near-white fill with gray border
        c.rect(rx - hw, ry - hh, s.w, s.h, fill=1, stroke=0)
        c.setStrokeColor(rc.HexColor('#90A4AE'))
        c.setLineWidth(0.6)
        c.rect(rx - hw, ry - hh, s.w, s.h, fill=0, stroke=1)
        c.setLineWidth(0)

    elif s.kind in ('call_plain', 'proc', 'move', 'alarm', 'label', 'jump'):
        c.rect(rx - hw, ry - hh, s.w, s.h, fill=1, stroke=0)

    else:
        c.rect(rx - hw, ry - hh, s.w, s.h, fill=1, stroke=0)

    # Text
    lines  = s.text.split('\n')
    lh     = _FONT_SZ + 2.5
    total  = lh * len(lines)
    ty     = ry + total / 2 - _FONT_SZ
    c.setFillColor(fg_c)
    for ln in lines:
        c.setFont(font_name, _FONT_SZ)
        c.drawCentredString(rx, ty, ln)
        ty -= lh


def _draw_fc_on_canvas(c, fc: FC, ox: float, oy: float, ph: float, lang: str):
    """Draw all edges then all shapes onto the canvas."""
    try:
        from docs.utils import pdf_font
        font = pdf_font(lang)
    except Exception:
        font = 'Helvetica'
    to_rl = _to_rl_factory(ox, oy, ph)

    # Pre-compute: when several edges land at the exact same point we only
    # want a single arrowhead.  The first edge drawn at a given endpoint
    # gets the arrowhead; the others draw the line only.
    seen_endpoint: set = set()

    # Edges first (below shapes)
    for e in fc.edges:
        try:
            x1r, y1r = to_rl(e.x1, e.y1)
            x2r, y2r = to_rl(e.x2, e.y2)
            key = (round(x2r, 1), round(y2r, 1))
            draw_arrow = key not in seen_endpoint
            seen_endpoint.add(key)
            via_xr = to_rl(e.via_x, e.y1)[0] if e.via_x is not None else None
            _draw_ortho_edge(c, x1r, y1r, x2r, y2r,
                             e.h_first, e.lbl, font,
                             draw_arrow=draw_arrow, via_xr=via_xr)
        except Exception:
            # Never let a single bad edge abort the rendering of a whole page.
            continue

    # Shapes on top
    for s in fc.shapes:
        try:
            _draw_shape(c, s, to_rl, font)
        except Exception:
            continue


# ── PDF DOCUMENT ──────────────────────────────────────────────────────────────

def generate_pdf(fcs: list, out_path: str, lang: str = 'IT',
                 title: str = 'Flowchart', toc_title: str = 'Sommario',
                 page_offset: int = 0, include_toc: bool = True):
    """
    page_offset: added to every page number printed in the PDF.
    include_toc: when False, omit the internal TOC page so this PDF can be
        embedded inside Completa without producing a duplicate summary.
    """
    from reportlab.lib.pagesizes import A4, A3, landscape as rl_landscape
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib import colors as rc
    from docs.pdf_header import draw_page_header, TOP_MARGIN_MM
    from docs.utils import pdf_font

    font_name = pdf_font(lang)
    font_bold = pdf_font(lang, bold=True)
    ACCENT      = rc.HexColor('#A85C42')
    GRAY      = rc.HexColor('#aaaaaa')

    ML = 15 * mm; MR = 15 * mm
    MT = TOP_MARGIN_MM * mm; MB = 18 * mm

    pw_a4, ph_a4 = A4

    tmp = out_path + '.tmp.pdf'
    c   = rl_canvas.Canvas(tmp)

    class _Doc:
        def __init__(self, ps):
            """Initialise a minimal doc-like object exposing pagesize and margins."""
            self.pagesize    = ps
            self.leftMargin  = ML
            self.rightMargin = MR
            self.page        = 0

    # ── TOC (only when standalone) ────────────────────────────────────────────
    if include_toc:
        c.setPageSize(A4)
        doc = _Doc(A4); doc.page = 1 + page_offset
        draw_page_header(c, doc)

        c.setFont(font_bold, 14); c.setFillColor(ACCENT)
        c.drawCentredString(pw_a4/2, ph_a4 - MT - 14, title)
        c.setFont(font_bold, 11); c.setFillColor(rc.black)
        c.drawString(ML, ph_a4 - MT - 36, toc_title)

        y_toc = ph_a4 - MT - 58
        for i, fc in enumerate(fcs):
            pg = i + 2 + page_offset
            c.setFont(font_name, 10); c.setFillColor(ACCENT)
            c.drawString(ML + 10, y_toc, fc.name)
            c.setFillColor(rc.black)
            c.drawRightString(pw_a4 - MR, y_toc, str(pg))
            # dotted leader
            tx = ML + 10 + c.stringWidth(fc.name, font_name, 10) + 4
            c.setStrokeColor(rc.HexColor('#cccccc')); c.setDash(1, 3)
            c.line(tx, y_toc + 3, pw_a4 - MR - 22, y_toc + 3)
            c.setDash()
            c.linkRect('', f'fc_{fc.name}', (ML, y_toc-2, pw_a4-MR, y_toc+12), relative=0)
            y_toc -= 16
            if y_toc < MB + 20:
                break

        c.setFont(font_name, 8); c.setFillColor(GRAY)
        c.drawCentredString(pw_a4/2, MB/2, str(1 + page_offset))
        c.showPage()

    # Page number offset for fc pages: with TOC fcs start at page 2, without TOC at page 1.
    _fc_pg_base = 2 if include_toc else 1

    # ── Flowchart pages ───────────────────────────────────────────────────────
    # Best-effort logger import: never let logging issues block PDF generation.
    try:
        import logger as _logger
    except Exception:
        _logger = None

    for i, fc in enumerate(fcs):
        pg_num = i + _fc_pg_base + page_offset

        try:
            # Choose page size
            pw_a4l, ph_a4l = rl_landscape(A4)
            pw_a3,  ph_a3  = A3

            def _fits(pw, ph, _fc=fc):
                """True if the flowchart fits within the given page size minus margins."""
                return _fc.width <= pw - ML - MR and _fc.height <= ph - MT - MB

            if _fits(pw_a4, ph_a4):
                psize = A4
            elif _fits(pw_a4l, ph_a4l):
                psize = rl_landscape(A4)
            elif _fits(pw_a3, ph_a3):
                psize = A3
            else:
                psize = rl_landscape(A3)

            c.setPageSize(psize)
            pw, ph = psize
            uw = pw - ML - MR; uh = ph - MT - MB
            sx = min(1.0, uw / max(fc.width, 1))
            sy = min(1.0, uh / max(fc.height, 1))
            scale = min(sx, sy)

            c.bookmarkPage(f'fc_{fc.name}')

            doc2 = _Doc(psize); doc2.page = pg_num
            try:
                draw_page_header(c, doc2)
            except Exception:
                pass

            c.setFont(font_bold, 10); c.setFillColor(ACCENT)
            c.drawString(ML, ph - MT - 13, fc.name)

            c.saveState()
            c.translate(ML, MB)
            c.scale(scale, scale)
            ph_fc = uh / scale
            _draw_fc_on_canvas(c, fc, 0, 0, ph_fc, lang)
            c.restoreState()

            c.setFont(font_name, 8); c.setFillColor(GRAY)
            c.drawCentredString(pw/2, MB/2, str(pg_num))
            c.drawRightString(pw - MR, MB/2, fc.name)
            c.showPage()
        except Exception as exc:
            # A single broken flowchart must not break the whole document.
            if _logger is not None:
                try:
                    _logger.warning('log_flowchart_error',
                                    f'{fc.name}: {exc}')
                except Exception:
                    pass
            # Make sure we leave the canvas in a renderable state for next page.
            try:
                c.restoreState()
            except Exception:
                pass
            try:
                c.showPage()
            except Exception:
                pass

    c.save()
    try:
        if os.path.exists(out_path):
            os.remove(out_path)
        os.rename(tmp, out_path)
    except Exception:
        try:
            os.replace(tmp, out_path)
        except Exception:
            pass


# ── DRAW.IO XML ───────────────────────────────────────────────────────────────

_DIO_STYLE = {
    'term':       'rounded=1;fillColor=#A85C42;fontColor=#fff;strokeColor=#A85C42;',
    'proc':       'rounded=0;fillColor=#6B6B6B;fontColor=#fff;strokeColor=#6B6B6B;',
    'move':       'rounded=0;fillColor=#F9A825;fontColor=#4A3000;strokeColor=#F9A825;',
    'io':         'rounded=0;fillColor=#ECEFF1;fontColor=#1A1A1A;strokeColor=#90A4AE;',
    'alarm':      'rounded=0;fillColor=#C62828;fontColor=#fff;strokeColor=#C62828;',
    'call':       'shape=process;fillColor=#2E7D32;fontColor=#fff;strokeColor=#C62828;',
    'call_plain': 'rounded=0;fillColor=#388E3C;fontColor=#fff;strokeColor=#388E3C;',
    'diamond':    'rhombus;fillColor=#EF6C00;fontColor=#fff;strokeColor=#EF6C00;',
    'label':      'rounded=0;fillColor=#4527A0;fontColor=#fff;strokeColor=#4527A0;',
    'jump':       'rounded=0;fillColor=#4527A0;fontColor=#fff;strokeColor=#4527A0;',
}
_SC = 0.75   # pt → px


def generate_drawio(fcs: list, out_path: str):
    """Write the given flowcharts to a draw.io XML file."""
    import xml.etree.ElementTree as ET

    root = ET.Element('mxGraphModel', compressed='false', dx='1422', dy='762',
                      grid='1', gridSize='10', guides='1', tooltips='1',
                      connect='1', arrows='1', fold='1', page='1',
                      pageScale='1', pageWidth='1169', pageHeight='827')

    x_off = 0
    for fc in fcs:
        r = ET.SubElement(root, 'root')
        ET.SubElement(r, 'mxCell', id='0')
        ET.SubElement(r, 'mxCell', id='1', parent='0')

        for s in fc.shapes:
            sid   = f'{fc.name}_{s.sid}'
            style = _DIO_STYLE.get(s.kind, _DIO_STYLE['proc'])
            cell  = ET.SubElement(r, 'mxCell', id=sid,
                                  value=s.text.replace('\n', '&#xa;'),
                                  style=style, vertex='1', parent='1')
            g = ET.SubElement(cell, 'mxGeometry',
                              x=str(int((x_off + s.cx - s.w/2) * _SC)),
                              y=str(int((s.cy - s.h/2) * _SC)),
                              width=str(int(s.w * _SC)),
                              height=str(int(s.h * _SC)))
            g.set('as', 'geometry')

        for ei, e in enumerate(fc.edges):
            cell = ET.SubElement(r, 'mxCell',
                                 id=f'{fc.name}_e{ei}', value=e.lbl,
                                 style='edgeStyle=orthogonalEdgeStyle;',
                                 edge='1', parent='1', source='', target='')
            g = ET.SubElement(cell, 'mxGeometry', relative='1')
            g.set('as', 'geometry')
            pts = ET.SubElement(g, 'Array')
            pts.set('as', 'points')
            for ex, ey in [(e.x1, e.y1), (e.x2, e.y2)]:
                p = ET.SubElement(pts, 'mxPoint')
                p.set('x', str(int((x_off + ex) * _SC)))
                p.set('y', str(int(ey * _SC)))

        x_off += fc.width + 100

    tree = ET.ElementTree(root)
    ET.indent(tree, space='  ')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        tree.write(f, encoding='unicode', xml_declaration=False)


# ── PUBLIC ENTRY POINT ────────────────────────────────────────────────────────

def build_flowcharts(folder: str) -> List[FC]:
    """Build flowchart (FC) objects for every JBI file in a folder."""
    fcs: List[FC] = []
    try:
        names = sorted(f for f in os.listdir(folder) if f.upper().endswith('.JBI'))
    except Exception:
        return fcs

    # Best-effort logger: a failure here must never block flowchart building.
    try:
        import logger as _logger
    except Exception:
        _logger = None

    for name in names:
        path = os.path.join(folder, name)
        stem = os.path.splitext(name)[0]
        try:
            ast = parse_jbi(path)
            fc  = layout_jbi(stem, ast)
            fcs.append(fc)
        except Exception as exc:
            if _logger is not None:
                try:
                    _logger.warning('log_flowchart_error', f'{stem}: {exc}')
                except Exception:
                    pass
    return fcs
