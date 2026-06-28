#!/usr/bin/env python3
"""
Move the Streamlit expander block labelled "12M Macro & Market Trend Snapshot"
to the last position within the valuation/diagnostics group.

Default target file: sg_tactical_wealth_allocator.py
Override with: APP_FILE=your_file.py python tools/patch_reorder_12m_snapshot_section.py

The script is intentionally conservative:
- creates a .bak backup
- only patches if all four target labels are found
- only patches if each label is inside a detectable expander block
- exits with a clear error if structure is not recognised
"""

from __future__ import annotations

import os
import re
from pathlib import Path

APP_FILE = Path(os.environ.get("APP_FILE", "sg_tactical_wealth_allocator.py"))

TARGET_LABEL = "12M Macro & Market Trend Snapshot"
DESIRED_ORDER = [
    "Quantitative Valuation Channels",
    "Drawdown Basis Comparison",
    "Risk Score & Trigger Diagnostics",
    TARGET_LABEL,
]
ALL_LABELS = [TARGET_LABEL] + DESIRED_ORDER[:-1]


def leading_spaces(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def find_label_line(lines: list[str], label: str) -> int:
    matches = [i for i, line in enumerate(lines) if label in line]
    if not matches:
        raise RuntimeError(f"Label not found: {label}")
    if len(matches) > 1:
        print(f"WARNING: Multiple occurrences found for {label}; using first occurrence at line {matches[0] + 1}")
    return matches[0]


def find_expander_start(lines: list[str], label_idx: int, label: str) -> int:
    # Common Streamlit pattern:
    # with st.expander("📊 12M Macro & Market Trend Snapshot", expanded=False):
    for i in range(label_idx, max(-1, label_idx - 40), -1):
        line = lines[i]
        if "expander" in line and ("st." in line or "with " in line or label in line):
            return i
    raise RuntimeError(f"Could not find expander block start for label: {label}")


def find_block_end(lines: list[str], start_idx: int) -> int:
    start_indent = leading_spaces(lines[start_idx])
    for i in range(start_idx + 1, len(lines)):
        stripped = lines[i].strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        # End when indentation returns to same or lower level.
        if leading_spaces(lines[i]) <= start_indent:
            return i
    return len(lines)


def main() -> None:
    if not APP_FILE.exists():
        raise SystemExit(f"ERROR: target app file not found: {APP_FILE}")

    text = APP_FILE.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    info = {}
    for label in ALL_LABELS:
        label_idx = find_label_line(lines, label)
        start = find_expander_start(lines, label_idx, label)
        end = find_block_end(lines, start)
        info[label] = {"label_idx": label_idx, "start": start, "end": end}

    current_order = [label for label, data in sorted(info.items(), key=lambda kv: kv[1]["start"])]
    print("Current order:")
    for label in current_order:
        print(f"- {label}")

    if current_order == DESIRED_ORDER:
        print("No change required: section is already in desired order.")
        return

    if TARGET_LABEL not in current_order:
        raise SystemExit("ERROR: target 12M snapshot label not found in detected order.")

    # Move only the 12M snapshot block to after Risk Score & Trigger Diagnostics.
    src_start = info[TARGET_LABEL]["start"]
    src_end = info[TARGET_LABEL]["end"]
    block = lines[src_start:src_end]

    remaining = lines[:src_start] + lines[src_end:]

    # Recalculate risk block location after removal.
    temp_text = "".join(remaining)
    temp_lines = temp_text.splitlines(keepends=True)
    risk_label = "Risk Score & Trigger Diagnostics"
    risk_label_idx = find_label_line(temp_lines, risk_label)
    risk_start = find_expander_start(temp_lines, risk_label_idx, risk_label)
    risk_end = find_block_end(temp_lines, risk_start)

    patched = temp_lines[:risk_end] + block + temp_lines[risk_end:]
    patched_text = "".join(patched)

    if patched_text == text:
        print("No textual change produced; exiting without write.")
        return

    backup = APP_FILE.with_suffix(APP_FILE.suffix + ".bak")
    backup.write_text(text, encoding="utf-8")
    APP_FILE.write_text(patched_text, encoding="utf-8")

    print(f"Patched: moved '{TARGET_LABEL}' to the last position in the section group.")
    print(f"Backup written: {backup}")


if __name__ == "__main__":
    main()
