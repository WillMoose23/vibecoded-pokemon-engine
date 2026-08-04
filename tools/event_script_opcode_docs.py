# FEATURE-MAP-049: structured opcode documentation lines for map editor doc pane and Help tab.
from __future__ import annotations

import copy
import json
from typing import Any, Callable

MeasureFn = Callable[[str], int]


def _wrap_words(text: str, measure_line: MeasureFn, max_w: int) -> list[str]:
    """Word-wrap to ``max_w`` using ``measure_line`` (px width).

    Leading spaces before the first word are kept on the first physical line; continuation lines use ``first_prefix + "    "`` when ``first_prefix`` is non-empty, else four spaces, so JSON-shaped lines stay visually indented after wrap.
    """
    raw = (text or "").replace("\t", " ").rstrip()
    if not raw:
        return [""]
    lead = 0
    while lead < len(raw) and raw[lead] == " ":
        lead += 1
    first_prefix = raw[:lead]
    core = raw[lead:].lstrip()
    if not core:
        return [first_prefix] if first_prefix else [""]
    words = core.split()
    cont_prefix = (first_prefix + "    ") if first_prefix else "    "
    lines: list[str] = []
    cur = ""
    first_line = True

    def line_prefix() -> str:
        return first_prefix if first_line else cont_prefix

    for w in words:
        cand = (cur + " " + w).strip() if cur else w
        if measure_line(line_prefix() + cand) <= max_w:
            cur = cand
            continue
        if cur:
            lines.append(line_prefix() + cur)
            first_line = False
            cur = ""
        cur = w
        if measure_line(line_prefix() + cur) > max_w:
            lines.append(line_prefix() + cur)
            first_line = False
            cur = ""
    if cur:
        lines.append(line_prefix() + cur)
    return lines if lines else [""]


def _param_type_hint(v: Any) -> str:
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "number"
    if isinstance(v, str):
        return "string"
    if v is None:
        return "null"
    if isinstance(v, (list, dict)):
        return "JSON"
    return "value"


def build_structured_doc_lines(
    op: str,
    doc: dict[str, Any],
    inner_w: int,
    measure_line: MeasureFn,
) -> list[str]:
    """Build plain-text lines for one opcode: name, description, JSON function shape (multi-line, indent=4), params, example.

    ``doc`` is the merged documentation dict (see ``event_script_schema.op_documentation``).
    ``inner_w`` is the content column width in pixels; ``measure_line`` returns rendered string width. Rows that gain a two-space prefix after ``_wrap_words`` pass a reduced max width so the final line fits (**BUG-MAP-030**).
    """
    lines: list[str] = []
    pad_2 = measure_line("  ")
    label = str(doc.get("label", op))
    status = str(doc.get("status", "implemented"))
    cat = str(doc.get("category", "")).strip()
    lines.append(f"{label}  [{status}]")
    lines.append(f"Opcode id: {op}")
    if cat:
        lines.append(f"Category: {cat}")
    lines.append("")
    desc = str(doc.get("description", "")).strip()
    if desc:
        lines.append("Description:")
        for ln in _wrap_words(desc, measure_line, max(40, inner_w - 8 - pad_2)):
            lines.append(f"  {ln}" if ln else "  ")
        lines.append("")
    da = doc.get("default_args")
    args_d = da if isinstance(da, dict) else {}
    req_raw = doc.get("required_params")
    required: set[str] = set()
    if isinstance(req_raw, list):
        required = {str(x) for x in req_raw if isinstance(x, str) and x.strip()}
    ah = doc.get("args_help")
    help_keys: list[str] = []
    if isinstance(ah, dict):
        help_keys = [str(k) for k in ah.keys()]
    all_keys = list(dict.fromkeys(list(args_d.keys()) + help_keys))
    fn_obj = {op: copy.deepcopy(args_d)}
    fn_lines = json.dumps(fn_obj, indent=4, ensure_ascii=False).split("\n")
    lines.append("Function (one script_1 entry = one single-key object):")
    for raw_ln in fn_lines:
        lines.append(raw_ln if raw_ln.startswith(" ") else f"  {raw_ln}")
    lines.append("")
    lines.append("Parameters:")
    if not all_keys:
        lines.append("  (none)")
    else:
        opt_keys = [k for k in all_keys if k not in required]
        man_keys = [k for k in all_keys if k in required]

        def one_line(k: str, kind: str) -> str:
            purpose = ""
            if isinstance(ah, dict) and k in ah:
                purpose = str(ah[k]).strip()
            typ = _param_type_hint(args_d[k]) if k in args_d else "value"
            extra = f" — {purpose}" if purpose else ""
            return f"[{kind}] {k} ({typ}){extra}"

        for k in sorted(man_keys):
            for ln in _wrap_words(one_line(k, "required"), measure_line, max(40, inner_w - pad_2)):
                lines.append(f"  {ln}")
        for k in sorted(opt_keys):
            for ln in _wrap_words(one_line(k, "optional"), measure_line, max(40, inner_w - pad_2)):
                lines.append(f"  {ln}")
    lines.append("")
    ex = [{op: copy.deepcopy(args_d)}]
    ex_lines = json.dumps(ex, indent=4, ensure_ascii=False).split("\n")
    lines.append("Example (script_1 fragment):")
    for el in ex_lines:
        # Preserve json.dumps indentation for every nested `{` / `[`; do not word-wrap (wrap destroys structure).
        lines.append(el if el.startswith(" ") else f"  {el}")
    return [x for x in lines if x is not None]


def build_help_segments_for_op(
    op: str,
    doc: dict[str, Any],
    wrap_w: int,
    measure_line: MeasureFn,
) -> list[tuple[str, str, str | None]]:
    """Return (kind, text, extra) tuples for ``MapEditor._help_build_lines`` script_ops tab."""
    raw = build_structured_doc_lines(op, doc, wrap_w, measure_line)
    if not raw:
        return []
    out: list[tuple[str, str, str | None]] = [("head", raw[0], None)]
    for ln in raw[1:]:
        if not ln.strip():
            out.append(("sp", "", None))
        else:
            out.append(("body", ln, None))
    out.append(("sp", "", None))
    return out
