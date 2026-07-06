#!/usr/bin/env python3
"""
patch_g20_macro_fetcher_manual_seed.py

Run this in the repository root. It patches g20_macro_fetcher.py in-place and
creates g20_macro_fetcher.py.bak_manual_seed.
"""
from pathlib import Path
import py_compile
import re

TARGET = Path("g20_macro_fetcher.py")
BACKUP = Path("g20_macro_fetcher.py.bak_manual_seed")
PARSER_BLOCK = '# manual_seed_parser_block.py missing\n'
OUTPUT_BLOCK = '    # Write CSV outputs\n    macro_cols = ["market", "indicator", "date", "value", "unit", "source", "source_type", "notes"]\n    diag_cols = ["run_utc", "market", "indicator", "source", "status", "value", "reason", "endpoint"]\n    manual_cols = ["run_utc", "market", "indicator", "reason"]\n    source_cols = ["market", "indicator", "source", "source_type", "endpoint", "notes"]\n\n    # ------------------------------------------------------------\n    # Manual macro seed integration: SG/JP rates, CPI, unemployment\n    # ------------------------------------------------------------\n    manual_macro_df = pd.DataFrame()\n    manual_rates_df = pd.DataFrame()\n    try:\n        manual_seed_df = load_manual_macro_seed()\n        manual_macro_df, manual_rates_df = split_manual_seed_for_outputs(manual_seed_df)\n\n        if manual_macro_df is not None and not manual_macro_df.empty:\n            for rec in manual_macro_df.to_dict("records"):\n                row = {c: rec.get(c, "") for c in macro_cols}\n                MACRO_ROWS.append(row)\n\n        diag(\n            "PACK",\n            "Manual seed",\n            "macro_seed_inputs",\n            "accepted",\n            reason=f"manual_macro_rows={0 if manual_macro_df is None else len(manual_macro_df)}, manual_rate_rows={0 if manual_rates_df is None else len(manual_rates_df)}",\n            endpoint="macro_seed_inputs/",\n        )\n\n    except Exception as e:\n        diag(\n            "PACK",\n            "Manual seed",\n            "macro_seed_inputs",\n            "failed",\n            reason=str(e),\n            endpoint="macro_seed_inputs/",\n        )\n\n    # Main macro output\n    write_csv(OUT_DIR / "macro_data.csv", MACRO_ROWS, macro_cols)\n\n    # 12M macro history output for Inflation / Unemployment / PMI etc.\n    try:\n        macro_hist_df = pd.DataFrame(MACRO_ROWS)\n        if not macro_hist_df.empty:\n            macro_hist_df["date"] = pd.to_datetime(macro_hist_df["date"], errors="coerce")\n            macro_hist_df["value"] = pd.to_numeric(macro_hist_df["value"], errors="coerce")\n            macro_hist_df = macro_hist_df.dropna(subset=["market", "indicator", "date", "value"])\n            macro_hist_df = macro_hist_df.sort_values(["market", "indicator", "date"])\n            macro_hist_df = macro_hist_df.drop_duplicates(["market", "indicator", "date"], keep="last")\n            macro_hist_df = macro_hist_df.groupby(["market", "indicator"], group_keys=False).tail(12)\n            macro_hist_df["date"] = macro_hist_df["date"].dt.strftime("%Y-%m-%d")\n            write_csv(OUT_DIR / "macro_history_12m.csv", macro_hist_df.to_dict("records"), macro_cols)\n        else:\n            write_csv(OUT_DIR / "macro_history_12m.csv", [], macro_cols)\n    except Exception as e:\n        diag("PACK", "macro_history_12m.csv", "builder", "failed", reason=str(e), endpoint="macro_history_12m.csv")\n        write_csv(OUT_DIR / "macro_history_12m.csv", [], macro_cols)\n\n    # 252D rates history output from manual SG/JP rates seed\n    try:\n        if manual_rates_df is not None and not manual_rates_df.empty:\n            manual_rates_df["date"] = pd.to_datetime(manual_rates_df["date"], errors="coerce")\n            manual_rates_df["value"] = pd.to_numeric(manual_rates_df["value"], errors="coerce")\n            manual_rates_df = manual_rates_df.dropna(subset=["market", "indicator", "date", "value"])\n            manual_rates_df = manual_rates_df.sort_values(["market", "indicator", "date"])\n            manual_rates_df = manual_rates_df.drop_duplicates(["market", "indicator", "date"], keep="last")\n            manual_rates_df = manual_rates_df.groupby(["market", "indicator"], group_keys=False).tail(252)\n            manual_rates_df["date"] = manual_rates_df["date"].dt.strftime("%Y-%m-%d")\n            write_csv(\n                OUT_DIR / "rates_history_252d.csv",\n                manual_rates_df.to_dict("records"),\n                list(manual_rates_df.columns),\n            )\n        else:\n            write_csv(\n                OUT_DIR / "rates_history_252d.csv",\n                [],\n                ["market", "indicator", "date", "value", "unit", "source", "source_type", "frequency", "notes"],\n            )\n    except Exception as e:\n        diag("PACK", "rates_history_252d.csv", "builder", "failed", reason=str(e), endpoint="rates_history_252d.csv")\n        write_csv(\n            OUT_DIR / "rates_history_252d.csv",\n            [],\n            ["market", "indicator", "date", "value", "unit", "source", "source_type", "frequency", "notes"],\n        )\n\n    write_csv(OUT_DIR / "diagnostics.csv", DIAGNOSTIC_ROWS, diag_cols)\n    write_csv(OUT_DIR / "manual_required.csv", MANUAL_ROWS, manual_cols)\n    write_csv(OUT_DIR / "source_catalogue.csv", SOURCE_ROWS, source_cols)\n'


def remove_existing_parser(text: str) -> str:
    start = text.find("# Global20Engine manual macro seed parser block")
    if start == -1:
        return text
    src = text.find("# Source catalogue", start)
    if src != -1:
        return text[:start].rstrip() + "\n\n" + text[src:]
    end = text.find("# End Global20Engine manual macro seed parser block", start)
    if end != -1:
        end = text.find("\n", end)
        return text[:start].rstrip() + "\n\n" + text[end+1:]
    return text


def insert_parser(text: str) -> str:
    marker = "# Source catalogue"
    pos = text.find(marker)
    if pos == -1:
        m = re.search(r"\ndef\s+build_source_catalogue\s*\(", text)
        if not m:
            raise RuntimeError("Could not find Source catalogue / build_source_catalogue insertion point.")
        pos = m.start()
    return text[:pos].rstrip() + "\n\n" + PARSER_BLOCK.strip() + "\n\n" + text[pos:]


def replace_output_block(text: str) -> str:
    start = text.find("    # Write CSV outputs")
    if start == -1:
        raise RuntimeError("Could not find '    # Write CSV outputs' block.")
    end = text.find("    readme_rows = [", start)
    if end == -1:
        raise RuntimeError("Could not find '    readme_rows = [' after Write CSV outputs block.")
    return text[:start] + OUTPUT_BLOCK.rstrip() + "\n\n" + text[end:]


def update_zip_list(text: str) -> str:
    additions = []
    if '"macro_history_12m.csv"' not in text:
        additions.append('                "macro_history_12m.csv",')
    if '"rates_history_252d.csv"' not in text:
        additions.append('                "rates_history_252d.csv",')
    if not additions:
        return text
    anchor = '                "macro_data.csv",'
    pos = text.find(anchor)
    if pos == -1:
        return text
    line_end = text.find("\n", pos)
    return text[:line_end+1] + "\n".join(additions) + "\n" + text[line_end+1:]


def main():
    if not TARGET.exists():
        raise SystemExit("ERROR: g20_macro_fetcher.py not found in current folder.")
    original = TARGET.read_text(encoding="utf-8")
    if not BACKUP.exists():
        BACKUP.write_text(original, encoding="utf-8")
    text = remove_existing_parser(original)
    text = insert_parser(text)
    text = replace_output_block(text)
    text = update_zip_list(text)
    TARGET.write_text(text, encoding="utf-8")
    py_compile.compile(str(TARGET), doraise=True)
    print("OK: g20_macro_fetcher.py patched and py_compile passed.")
    print(f"Backup saved as: {BACKUP}")


if __name__ == "__main__":
    main()
