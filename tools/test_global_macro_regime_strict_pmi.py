#!/usr/bin/env python3
"""
Global20Engine — Strict PMI test suite

Purpose
-------
Run local/CI validation before promoting the Global Macro Regime data fetcher.

Tests:
1. Production fetcher compiles.
2. Production fetcher no longer contains old app-default PMI fallback strings.
3. Strict PMI accepts clean macro_pack_latest/macro_data.csv PMI rows.
4. Strict PMI fails when a required PMI market is missing.
5. Strict PMI fails when PMI source/source_type/notes are seed/default/fallback/manual.

This test suite does not call external FRED/PMI sources. It only tests the strict PMI validation layer.
"""

from __future__ import annotations

import importlib.util
import py_compile
import tempfile
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGET = REPO_ROOT / "tools" / "update_global_macro_regime.py"

REQUIRED_COLUMNS = ["market", "indicator", "date", "value", "unit", "source", "source_type", "notes"]

CLEAN_ROWS = [
    ["US", "PMI", "2026-05-01", 54.0, "index", "ISM Manufacturing PMI via parsed release", "Parsed / Release", "Parsed PMI from source; period=May 2026."],
    ["SG", "PMI", "2026-05-01", 51.0, "index", "SIPMM Singapore Manufacturing PMI via parser", "Parsed / Secondary", "Parsed PMI from source; period=May 2026."],
    ["HK", "PMI", "2026-05-01", 50.4, "index", "S&P Global Hong Kong SAR PMI via parser", "Parsed / Secondary", "Parsed PMI from source; period=May 2026."],
    ["CN", "PMI", "2026-05-01", 50.0, "index", "NBS China Manufacturing PMI parsed release", "Parsed / Official", "Parsed PMI from source; period=May 2026."],
    ["MY", "PMI", "2026-05-01", 49.9, "index", "S&P Global Malaysia PMI parsed release", "Parsed / Release", "Parsed PMI from source; period=May 2026."],
    ["JP", "PMI", "2026-05-01", 50.4, "index", "Japan Manufacturing PMI parsed release", "Parsed / Secondary", "Parsed PMI from source; period=May 2026."],
]


def load_target_module():
    if not TARGET.exists():
        raise AssertionError(f"Missing target file: {TARGET}")
    spec = importlib.util.spec_from_file_location("update_global_macro_regime", TARGET)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_macro_data(base: Path, rows: list[list[object]]) -> Path:
    out_dir = base / "macro_pack_latest"
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows, columns=REQUIRED_COLUMNS)
    path = out_dir / "macro_data.csv"
    df.to_csv(path, index=False)
    return path


def patch_module_paths(module, base: Path):
    out_dir = base / "macro_pack_latest"
    module.OUT_DIR = out_dir
    module.MACRO_DATA_FILE = out_dir / "macro_data.csv"
    module.PMI_AUDIT_OUT = out_dir / "pmi_source_audit.csv"
    module.LATEST_OUT = out_dir / "global_macro_regime_latest.csv"
    module.DIAG_OUT = out_dir / "global_macro_regime_diagnostics.csv"


def expect_raises(fn, contains: str):
    try:
        fn()
    except Exception as exc:
        msg = str(exc)
        if contains not in msg:
            raise AssertionError(f"Expected error containing {contains!r}, got {msg!r}") from exc
        return
    raise AssertionError(f"Expected exception containing {contains!r}, but no exception was raised")


def test_compile():
    py_compile.compile(str(TARGET), doraise=True)


def test_no_old_app_default_pmi_fallback_strings():
    txt = TARGET.read_text(encoding="utf-8")
    forbidden = [
        "App PMI defaults composite",
        "DEFAULT_PMI_VALUES",
        "existing app PMI defaults",
    ]
    hits = [token for token in forbidden if token in txt]
    if hits:
        raise AssertionError("Old PMI fallback strings still present: " + ", ".join(hits))


def test_accepts_clean_pmi_rows():
    module = load_target_module()
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        write_macro_data(base, CLEAN_ROWS)
        patch_module_paths(module, base)
        pmi, status, source, latest_date, remarks, audit = module.build_growth_pmi_strict()
        expected = round(sum(float(r[3]) for r in CLEAN_ROWS) / len(CLEAN_ROWS), 3)
        if round(pmi, 3) != expected:
            raise AssertionError(f"Unexpected composite PMI: {pmi}; expected {expected}")
        if status != "Moderate":
            raise AssertionError(f"Unexpected PMI status: {status}")
        if source != "Monthly macro pack PMI composite":
            raise AssertionError(f"Unexpected source: {source}")
        if set(audit["coverage"].astype(str)) != {"OK"}:
            raise AssertionError("Clean rows should all audit as OK")


def test_rejects_missing_required_market():
    module = load_target_module()
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        rows = [r for r in CLEAN_ROWS if r[0] != "CN"]
        write_macro_data(base, rows)
        patch_module_paths(module, base)
        expect_raises(module.build_growth_pmi_strict, "Missing production-safe PMI rows")


def test_rejects_seed_source_type():
    module = load_target_module()
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        rows = [list(r) for r in CLEAN_ROWS]
        rows[0][6] = "Seed / Pack"
        write_macro_data(base, rows)
        patch_module_paths(module, base)
        expect_raises(module.build_growth_pmi_strict, "Missing production-safe PMI rows")


def test_rejects_app_default_source():
    module = load_target_module()
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        rows = [list(r) for r in CLEAN_ROWS]
        rows[1][5] = "App default / SIPMM-S&P proxy"
        write_macro_data(base, rows)
        patch_module_paths(module, base)
        expect_raises(module.build_growth_pmi_strict, "Missing production-safe PMI rows")


def main() -> int:
    tests = [
        test_compile,
        test_no_old_app_default_pmi_fallback_strings,
        test_accepts_clean_pmi_rows,
        test_rejects_missing_required_market,
        test_rejects_seed_source_type,
        test_rejects_app_default_source,
    ]
    failures = []
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except Exception as exc:
            failures.append((test.__name__, str(exc)))
            print(f"FAIL {test.__name__}: {exc}")
    if failures:
        print("\nSTRICT PMI TESTS FAILED")
        for name, err in failures:
            print(f"- {name}: {err}")
        return 2
    print("\nALL STRICT PMI TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
