#!/usr/bin/env python3
"""Generate the README figures: the evidence-card hero and the host/kernel boundary figure.

Standard library only, deterministic, no network. Writes four files next to this directory:

    docs/assets/hero-light.svg    docs/assets/hero-dark.svg
    docs/assets/where-light.svg   docs/assets/where-dark.svg

Run ``python docs/assets/src/make_figures.py`` (or ``--write``) to regenerate them, or ``--check`` to
regenerate in memory and exit 1 if any committed file differs (``tests/test_figures.py`` runs
the check on every CI test job).

Every outcome string in the figures traces to a committed file:

- ``CARD_ROWS``: the three lines printed by the example under "Decide, serialize, replay" in
  ``README.md``. ``tests/test_figures.py`` runs that example and compares its output with
  ``CARD_ROWS``.
- ``OUTCOMES``: the five statuses are ``_DECISIONS`` in ``src/evalopt_graph/kernel.py``. The
  ``ACCEPTED`` reason is the README example's output; the other four reason codes are cases of
  ``test_terminal_states_remain_distinct`` in ``tests/test_kernel.py``.
- ``replay()`` is ``AcceptanceDecision.replay`` in ``src/evalopt_graph/kernel.py``: it
  recomputes the decision from the stored policy and input and compares the whole record.

Text is real SVG ``<text>`` in system font stacks; there are no web fonts, styles, scripts or
raster images. Each file carries a ``<title>`` and a ``<desc>`` with the figure's full text.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

ASSETS = Path(__file__).resolve().parents[1]

SERIF = "Georgia, 'Times New Roman', serif"
MONO = "ui-monospace, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"
SANS = "system-ui, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"

# --- copy -------------------------------------------------------------------------------------

EYEBROW = ("evalopt-graph", "acceptance policy kernel")
THESIS = ("Do the gates, claims", "and evidence satisfy", "the acceptance policy?")
SUBLINE = (
    "A zero-dependency kernel turns host-supplied",
    "records into one replayable decision with",
    "stable reason codes.",
)
CARD_HEADER = 'POLICY · required_gates = ("tests", "lint")'
# (observed gates, status, reasons): status + " " + reasons is the README example's printed line.
CARD_ROWS = (
    ("tests PASS · lint PASS", "ACCEPTED", "('policy_satisfied',)"),
    ("tests FAIL · lint PASS", "FAILED", "('required_gate_failed:tests',)"),
    ("gates pass · tests_weakened", "BLOCKED", "('tests_weakened',)"),
)
CARD_FOOTER = ("README example · decisions are content-addressed;", "replay() re-checks them later")

WHERE_TITLE = "Where evalopt-graph sits"
WHERE_SUBLINE = (
    "Your host runs the checks and supplies the observations; "
    "the kernel applies the policy and returns one of five outcomes."
)
HOST_LABEL = "YOUR HOST · CI JOB, AGENT HOOK OR VERIFIER"
KERNEL_LABEL = "KERNEL · ZERO RUNTIME DEPENDENCIES"
HOST_WORK = (
    ("Runs the checks", "tests, lint → PASS/FAIL"),
    ("Detects weakened tests", "tests_weakened=True"),
    ("Collects evidence", "claims · attestations"),
)
POLICY_BOX = ("GovernancePolicy", "gates, trust, freshness")
INPUT_BOX = ("AcceptanceInput", "immutable observation")
STORED_BOX = ("Stored by the host", "policy, input, decision")
HOST_NOTE = ("Evalopt does not run checks", "or discover weakened tests.")
KERNEL_BOX = (
    "evaluate_acceptance(policy, input)",
    ("pure: same policy + input → same decision", "no LLM in the loop · fail-closed defaults"),
)
DECISION_HEADER = "AcceptanceDecision · status, reasons, hashes"
# One reason code per status: README example output or a case in tests/test_kernel.py.
OUTCOMES = (
    ("ACCEPTED", "policy_satisfied"),
    ("BLOCKED", "tests_weakened"),
    ("FAILED", "required_gate_failed:tests"),
    ("UNSUPPORTED", "required_gate_unavailable:tests"),
    ("UNVERIFIED", "central_claim_unverified:c1"),
)
REPLAY_BOX = (
    "replay(policy, input)",
    "recomputes the decision; True only if identical",
    "consistency with the stored input, not its truth",
)
LATER = "later"


# --- palettes ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Palette:
    ground: str
    text: str
    sub: str
    muted: str
    accent: str
    card: str
    card_text: str
    card_muted: str
    green: str
    red: str
    amber: str
    host_lane: str
    kernel_lane: str
    box: str
    box_stroke: str
    arrow: str
    kernel_box: str
    kernel_title: str
    kernel_text: str


LIGHT = Palette(
    ground="#F4F1EA",
    text="#16211D",
    sub="#3E3D38",
    muted="#6B6A65",
    accent="#0E6E66",
    card="#16211D",
    card_text="#E9E4D8",
    card_muted="#A8A397",
    green="#7FD1A8",
    red="#F0A48A",
    amber="#E8B14A",
    host_lane="#ECE8DD",
    kernel_lane="#E4DFD2",
    box="#FFFFFF",
    box_stroke="#D9D4C7",
    arrow="#6B6A65",
    kernel_box="#16211D",
    kernel_title="#4FC3B6",
    kernel_text="#F4F1EA",
)

DARK = Palette(
    ground="#0F1512",
    text="#F0ECE2",
    sub="#CFC9BC",
    muted="#A8A397",
    accent="#4FC3B6",
    card="#F4F1EA",
    card_text="#16211D",
    card_muted="#6B6A65",
    green="#1F7A4D",
    red="#B8431F",
    amber="#8A5A00",
    host_lane="#161E1A",
    kernel_lane="#1B2621",
    box="#0F1512",
    box_stroke="#34403A",
    arrow="#A8A397",
    kernel_box="#F4F1EA",
    kernel_title="#0E6E66",
    kernel_text="#16211D",
)

# Outcome colours inside the boundary figure (on the box colour, not on the hero card).
WHERE_STATUS = {
    "light": {
        "ACCEPTED": "#1F7A4D",
        "BLOCKED": "#8A5A00",
        "FAILED": "#B8431F",
        "UNSUPPORTED": "#16211D",
        "UNVERIFIED": "#16211D",
    },
    "dark": {
        "ACCEPTED": "#7FD1A8",
        "BLOCKED": "#E8B14A",
        "FAILED": "#F0A48A",
        "UNSUPPORTED": "#F0ECE2",
        "UNVERIFIED": "#F0ECE2",
    },
}


# --- SVG helpers ------------------------------------------------------------------------------


def _num(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


def _attrs(**values: object) -> str:
    parts = []
    for key, value in values.items():
        if value is None:
            continue
        name = key.rstrip("_").replace("_", "-")
        rendered = _num(value) if isinstance(value, float | int) and not isinstance(value, bool) else value
        parts.append(f'{name}="{escape(str(rendered), {chr(34): "&quot;"})}"')
    return " ".join(parts)


def rect(x: float, y: float, w: float, h: float, fill: str, rx: float = 0, **extra: object) -> str:
    return f"<rect {_attrs(x=x, y=y, width=w, height=h, rx=rx or None, fill=fill, **extra)}/>"


def text(
    x: float,
    y: float,
    content: str | list[tuple[str, dict[str, object]]],
    *,
    family: str,
    size: float,
    fill: str,
    weight: int | None = None,
    anchor: str | None = None,
    spacing: float | None = None,
) -> str:
    attrs = _attrs(
        x=x,
        y=y,
        font_family=family,
        font_size=size,
        font_weight=weight,
        fill=fill,
        text_anchor=anchor,
        letter_spacing=spacing,
    )
    if isinstance(content, str):
        body = escape(content)
    else:
        body = "".join(
            f"<tspan {_attrs(**style)}>{escape(chunk)}</tspan>" if style else escape(chunk)
            for chunk, style in content
        )
    return f"<text {attrs}>{body}</text>"


def line(points: list[tuple[float, float]], stroke: str, marker: str | None, dashed: bool = False) -> str:
    d = "M " + " L ".join(f"{_num(x)} {_num(y)}" for x, y in points)
    return (
        "<path "
        + _attrs(
            d=d,
            fill="none",
            stroke=stroke,
            stroke_width=2,
            stroke_linecap="round",
            stroke_linejoin="round",
            stroke_dasharray="7 6" if dashed else None,
            marker_end=f"url(#{marker})" if marker else None,
        )
        + "/>"
    )


def marker(marker_id: str, fill: str) -> str:
    return (
        f'<marker id="{marker_id}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="11" '
        f'markerHeight="11" markerUnits="userSpaceOnUse" orient="auto">'
        f'<path d="M 0 0 L 10 5 L 0 10 Z" fill="{fill}"/></marker>'
    )


def document(width: int, height: int, title: str, desc: str, body: list[str]) -> str:
    head = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">'
    )
    lines = [head, f'<title id="title">{escape(title)}</title>', f'<desc id="desc">{escape(desc)}</desc>']
    lines.extend(body)
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def _baseline(top: float, line_height: float, size: float) -> float:
    """Baseline that centres capital letters inside a line box."""
    return top + line_height / 2 + size * 0.35


# --- hero -------------------------------------------------------------------------------------

HERO_W, HERO_H = 1600, 520


def hero_text() -> tuple[str, str]:
    title = f"{EYEBROW[0]} · {EYEBROW[1]}: {' '.join(THESIS)}"
    rows = "; ".join(f"{gates} → {status} {reasons}" for gates, status, reasons in CARD_ROWS)
    desc = f"{' '.join(SUBLINE)} Evidence card: {CARD_HEADER}. {rows}. {' '.join(CARD_FOOTER)}."
    return title, desc


def hero(p: Palette) -> str:
    body = [rect(0, 0, HERO_W, HERO_H, p.ground, rx=18)]
    pad_x, pad_y = 72, 56
    inner_h = HERO_H - 2 * pad_y
    card_w, gap = 660, 56
    col_x = pad_x

    # Left column: eyebrow, thesis, subline, centred vertically.
    eyebrow_size, eyebrow_lh = 22, 22 * 1.25
    thesis_size, thesis_lh = 62, 62 * 1.12
    sub_size, sub_lh = 27, 27 * 1.4
    stack_gap = 22
    total = eyebrow_lh + stack_gap + thesis_lh * len(THESIS) + stack_gap + sub_lh * len(SUBLINE)
    y = pad_y + (inner_h - total) / 2
    body.append(
        text(
            col_x,
            _baseline(y, eyebrow_lh, eyebrow_size),
            [
                (EYEBROW[0], {"fill": p.accent, "font_weight": 700}),
                (" · " + EYEBROW[1], {}),
            ],
            family=MONO,
            size=eyebrow_size,
            fill=p.muted,
            spacing=0.4,
        )
    )
    y += eyebrow_lh + stack_gap
    for chunk in THESIS:
        body.append(
            text(
                col_x,
                _baseline(y, thesis_lh, thesis_size),
                chunk,
                family=SERIF,
                size=thesis_size,
                fill=p.text,
                weight=700,
            )
        )
        y += thesis_lh
    y += stack_gap
    for chunk in SUBLINE:
        body.append(
            text(col_x, _baseline(y, sub_lh, sub_size), chunk, family=SANS, size=sub_size, fill=p.sub)
        )
        y += sub_lh

    # Right column: the evidence card.
    card_x = HERO_W - pad_x - card_w
    assert card_x - col_x >= 740 + gap - 1, "left column narrower than the artboard"
    body.append(rect(card_x, pad_y, card_w, inner_h, p.card, rx=16))
    cx = card_x + 34
    head_size, head_lh = 17, 17 * 1.4
    row_size, row_lh = 22, 22 * 1.55
    foot_size, foot_lh = 16, 16 * 1.45
    head_gap, row_gap = 20, 16
    total = (
        head_lh
        + head_gap
        + len(CARD_ROWS) * 2 * row_lh
        + (len(CARD_ROWS) - 1) * row_gap
        + head_gap
        + foot_lh * len(CARD_FOOTER)
    )
    y = pad_y + (inner_h - total) / 2
    body.append(
        text(
            cx,
            _baseline(y, head_lh, head_size),
            CARD_HEADER,
            family=MONO,
            size=head_size,
            fill=p.card_muted,
            spacing=1.36,
        )
    )
    y += head_lh + head_gap
    colours = {"ACCEPTED": p.green, "FAILED": p.red, "BLOCKED": p.amber}
    for index, (gates, status, reasons) in enumerate(CARD_ROWS):
        body.append(
            text(cx, _baseline(y, row_lh, row_size), gates, family=MONO, size=row_size, fill=p.card_text)
        )
        y += row_lh
        body.append(
            text(
                cx,
                _baseline(y, row_lh, row_size),
                [
                    ("→ ", {}),
                    (status, {"fill": colours[status], "font_weight": 700}),
                    (" ", {}),
                    (reasons, {"fill": p.card_muted}),
                ],
                family=MONO,
                size=row_size,
                fill=p.card_text,
            )
        )
        y += row_lh
        if index < len(CARD_ROWS) - 1:
            y += row_gap
    y += head_gap
    for chunk in CARD_FOOTER:
        body.append(
            text(cx, _baseline(y, foot_lh, foot_size), chunk, family=MONO, size=foot_size, fill=p.card_muted)
        )
        y += foot_lh

    title, desc = hero_text()
    return document(HERO_W, HERO_H, title, desc, body)


# --- where it sits ----------------------------------------------------------------------------

WHERE_W, WHERE_H = 1600, 856
LABEL = 22  # smallest essential label size: about 11.5 px at the 838 px README width


def where_text() -> tuple[str, str]:
    title = f"{WHERE_TITLE}: {WHERE_SUBLINE}"
    work = ", ".join(f"{name.lower()} ({detail})" for name, detail in HOST_WORK)
    outcomes = ", ".join(f"{status} ({reason})" for status, reason in OUTCOMES)
    desc = (
        f"Two lanes. Host lane: the host {work}; it holds the {POLICY_BOX[0]} ({POLICY_BOX[1]}) "
        f"and builds an {INPUT_BOX[0]} ({INPUT_BOX[1]}). {HOST_NOTE[0]} {HOST_NOTE[1]} "
        f"Kernel lane: {KERNEL_BOX[0]} is {KERNEL_BOX[1][0]}; {KERNEL_BOX[1][1]}. "
        f"It returns an {DECISION_HEADER}, in one of five states: {outcomes}. "
        f"The host stores policy, input and decision. {LATER.capitalize()}, {REPLAY_BOX[0]} "
        f"{REPLAY_BOX[1]}: {REPLAY_BOX[2]}."
    )
    return title, desc


def _box(
    x: float,
    y: float,
    w: float,
    h: float,
    p: Palette,
    head: str,
    sub: str,
    *,
    head_mono: bool,
    sub_mono: bool,
) -> list[str]:
    gap = 10
    total = LABEL + gap + LABEL
    top = y + (h - total) / 2
    return [
        rect(x, y, w, h, p.box, rx=10, stroke=p.box_stroke, stroke_width=1.5),
        text(
            x + 18,
            top + LABEL * 0.8,
            head,
            family=MONO if head_mono else SANS,
            size=LABEL,
            fill=p.text,
            weight=700,
        ),
        text(
            x + 18,
            top + LABEL + gap + LABEL * 0.8,
            sub,
            family=MONO if sub_mono else SANS,
            size=LABEL,
            fill=p.sub,
        ),
    ]


def where(p: Palette, mode: str) -> str:
    body = [
        "<defs>",
        marker("arrow", p.arrow),
        marker("arrow-accent", p.accent),
        "</defs>",
        rect(0, 0, WHERE_W, WHERE_H, p.ground, rx=18),
        text(64, 78, WHERE_TITLE, family=SERIF, size=38, fill=p.text, weight=700),
        text(64, 118, WHERE_SUBLINE, family=SANS, size=LABEL, fill=p.sub),
    ]
    lane_top, lane_bottom = 150, 826
    host_x0, host_x1 = 40, 800
    kern_x0, kern_x1 = 830, 1560
    body.append(rect(host_x0, lane_top, host_x1 - host_x0, lane_bottom - lane_top, p.host_lane, rx=12))
    body.append(rect(kern_x0, lane_top, kern_x1 - kern_x0, lane_bottom - lane_top, p.kernel_lane, rx=12))
    body.append(text(host_x0 + 24, 192, HOST_LABEL, family=MONO, size=LABEL, fill=p.muted, spacing=1.6))
    body.append(text(kern_x0 + 24, 192, KERNEL_LABEL, family=MONO, size=LABEL, fill=p.muted, spacing=1.6))

    # Host lane: the work the host does, then the two values it hands to the kernel.
    work_x, work_w, work_h, work_gap, row_top = 64, 360, 96, 14, 214
    mids = []
    for index, (name, detail) in enumerate(HOST_WORK):
        top = row_top + index * (work_h + work_gap)
        body.extend(_box(work_x, top, work_w, work_h, p, name, detail, head_mono=False, sub_mono=True))
        mids.append(top + work_h / 2)
    work_bottom = row_top + len(HOST_WORK) * work_h + (len(HOST_WORK) - 1) * work_gap
    col_x, col_w = 476, 300
    policy_top, policy_h = row_top, work_h
    input_top = row_top + work_h + 34
    input_h = work_bottom - input_top
    body.extend(_box(col_x, policy_top, col_w, policy_h, p, *POLICY_BOX, head_mono=True, sub_mono=False))
    body.extend(_box(col_x, input_top, col_w, input_h, p, *INPUT_BOX, head_mono=True, sub_mono=False))
    bus_x = 450
    input_mid = input_top + input_h / 2
    for mid in mids:
        body.append(line([(work_x + work_w, mid), (bus_x, mid)], p.arrow, None))
    body.append(line([(bus_x, mids[0]), (bus_x, mids[-1])], p.arrow, None))
    body.append(line([(bus_x, input_mid), (col_x - 2, input_mid)], p.arrow, "arrow"))

    # Kernel lane: evaluate_acceptance() and its five outcomes.
    kbox_x, kbox_w, kbox_h = kern_x0 + 24, kern_x1 - kern_x0 - 48, 130
    body.append(rect(kbox_x, row_top, kbox_w, kbox_h, p.kernel_box, rx=12, stroke=p.accent, stroke_width=3))
    k_title, k_lines = KERNEL_BOX
    body.append(
        text(kbox_x + 22, row_top + 44, k_title, family=MONO, size=24, fill=p.kernel_title, weight=700)
    )
    for index, chunk in enumerate(k_lines):
        body.append(
            text(kbox_x + 22, row_top + 80 + index * 30, chunk, family=SANS, size=LABEL, fill=p.kernel_text)
        )
    policy_mid = policy_top + policy_h / 2
    elbow_x = (host_x1 + kern_x0) / 2 - 3
    body.append(line([(col_x + col_w, policy_mid), (kbox_x - 3, policy_mid)], p.arrow, "arrow"))
    body.append(
        line(
            [
                (col_x + col_w, input_mid),
                (elbow_x, input_mid),
                (elbow_x, row_top + 96),
                (kbox_x - 3, row_top + 96),
            ],
            p.arrow,
            "arrow",
        )
    )

    out_bus = kbox_x + 22
    chip_x, chip_h, chip_gap = kbox_x + 56, 42, 6
    chip_w = kbox_x + kbox_w - chip_x
    chip_top = row_top + kbox_h + 58
    body.append(
        text(chip_x, chip_top - 16, DECISION_HEADER, family=MONO, size=LABEL, fill=p.text, weight=700)
    )
    chip_mids = []
    colours = WHERE_STATUS[mode]
    for index, (status, reason) in enumerate(OUTCOMES):
        top = chip_top + index * (chip_h + chip_gap)
        mid = top + chip_h / 2
        chip_mids.append(mid)
        body.append(rect(chip_x, top, chip_w, chip_h, p.box, rx=8, stroke=p.box_stroke, stroke_width=1.2))
        body.append(
            text(chip_x + 16, mid + 8, status, family=MONO, size=LABEL, fill=colours[status], weight=700)
        )
        body.append(text(chip_x + 186, mid + 8, reason, family=MONO, size=LABEL, fill=p.sub))
    for mid in chip_mids:
        body.append(line([(out_bus, mid), (chip_x - 2, mid)], p.accent, "arrow-accent"))

    # Bottom row: the host stores the record; replay() recomputes it later.
    b_top, b_h = 690, 120
    b_mid = b_top + b_h / 2
    corridor = 660
    store_mid = col_x + col_w / 2
    body.append(
        line(
            [
                (out_bus, row_top + kbox_h),
                (out_bus, corridor),
                (store_mid, corridor),
                (store_mid, b_top - 2),
            ],
            p.accent,
            "arrow-accent",
        )
    )
    body.append(
        text(
            (store_mid + out_bus) / 2,
            corridor - 10,
            "decision",
            family=MONO,
            size=LABEL,
            fill=p.muted,
            anchor="middle",
        )
    )
    body.append(text(work_x, b_mid - 4, HOST_NOTE[0], family=SANS, size=LABEL, fill=p.sub))
    body.append(text(work_x, b_mid + 26, HOST_NOTE[1], family=SANS, size=LABEL, fill=p.sub))
    body.extend(_box(col_x, b_top, col_w, b_h, p, *STORED_BOX, head_mono=False, sub_mono=False))
    body.append(rect(kbox_x, b_top, kbox_w, b_h, p.box, rx=10, stroke=p.box_stroke, stroke_width=1.5))
    body.append(
        text(kbox_x + 22, b_top + 38, REPLAY_BOX[0], family=MONO, size=LABEL, fill=p.text, weight=700)
    )
    body.append(text(kbox_x + 22, b_top + 72, REPLAY_BOX[1], family=SANS, size=LABEL, fill=p.text))
    body.append(text(kbox_x + 22, b_top + 102, REPLAY_BOX[2], family=SANS, size=LABEL, fill=p.sub))
    body.append(line([(col_x + col_w, b_mid), (kbox_x - 3, b_mid)], p.arrow, "arrow", dashed=True))
    body.append(
        text(
            (host_x1 + kern_x0) / 2, b_mid - 18, LATER, family=MONO, size=LABEL, fill=p.muted, anchor="middle"
        )
    )

    title, desc = where_text()
    return document(WHERE_W, WHERE_H, title, desc, body)


# --- entry point ------------------------------------------------------------------------------


def render() -> dict[str, str]:
    return {
        "hero-light.svg": hero(LIGHT),
        "hero-dark.svg": hero(DARK),
        "where-light.svg": where(LIGHT, "light"),
        "where-dark.svg": where(DARK, "dark"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="fail if a committed figure is stale")
    mode.add_argument("--write", action="store_true", help="write the figures (the default)")
    args = parser.parse_args(argv)
    stale = []
    for name, content in render().items():
        path = ASSETS / name
        expected = content.encode("utf-8")
        if args.check:
            current = path.read_bytes().replace(b"\r\n", b"\n") if path.exists() else None
            if current != expected:
                stale.append(name)
        else:
            path.write_bytes(expected)
            print(f"wrote {path.relative_to(ASSETS.parents[1]).as_posix()}")
    if stale:
        print("stale figures (run python docs/assets/src/make_figures.py): " + ", ".join(stale))
        return 1
    if args.check:
        print("figures are current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
