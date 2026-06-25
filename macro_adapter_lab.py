
# macro_rate_diagnostics_lab.py
# Global20Engine Rate Diagnostics Lab v7 - MAS HTML POST with no-lxml table parser

import csv
import io
import re
import urllib.parse
import urllib.request
from datetime import datetime

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Global20Engine Rate Diagnostics Lab", layout="wide")

USER_AGENT = "Mozilla/5.0 Global20Engine-RateDiagnosticsLab/7.0"
TIMEOUT = 30
MAS_DIR_URL = "https://eservices.mas.gov.sg/statistics/dir/domesticinterestrates.aspx"


def request_text(url, label, accept="*/*", data=None, method=None, headers_extra=None):
    started = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    try:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": accept,
            "Accept-Encoding": "identity",
        }
        if headers_extra:
            headers.update(headers_extra)
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
            return {
                "label": label,
                "ok": True,
                "status": getattr(resp, "status", ""),
                "content_type": resp.headers.get("Content-Type", ""),
                "bytes": len(raw),
                "started_utc": started,
                "url": url,
                "text": raw.decode("utf-8", errors="replace"),
                "error": "",
            }
    except Exception as e:
        return {
            "label": label,
            "ok": False,
            "status": "",
            "content_type": "",
            "bytes": 0,
            "started_utc": started,
            "url": url,
            "text": "",
            "error": repr(e),
        }


def strip_tags(x):
    x = re.sub(r"<script\b.*?</script>", " ", str(x), flags=re.I | re.S)
    x = re.sub(r"<style\b.*?</style>", " ", x, flags=re.I | re.S)
    x = re.sub(r"<[^>]+>", " ", x)
    x = x.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", x).strip()


def attr_dict(tag):
    attrs = {}
    for a in re.finditer(r"([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*(['\"])(.*?)\2", tag, flags=re.S):
        attrs[a.group(1).lower()] = a.group(3)
    return attrs


def clean_number(x):
    if x is None:
        return None
    s = str(x).strip().strip('"').strip("'")
    if not s or s.upper() in {"N.A.", "N/A", "NA", "NULL", "NONE", "-", "--", "."}:
        return None
    s = re.sub(r"\[[^\]]*\]", "", s)
    s = s.replace("+", "").replace("%", "").replace(",", "").replace("−", "-").replace("–", "-")
    try:
        return float(s)
    except Exception:
        return None


def parse_date_any(x):
    s = str(x).strip().strip('"').strip("'")
    if re.fullmatch(r"\d{8}", s):
        return pd.to_datetime(f"{s[:4]}-{s[4:6]}-{s[6:8]}", errors="coerce")
    if re.fullmatch(r"\d{6}", s):
        return pd.to_datetime(f"{s[:4]}-{s[4:6]}-01", errors="coerce")
    return pd.to_datetime(s, errors="coerce")


def classify_html(text):
    t = (text or "").lower()
    if "maintenance" in t or "service is currently unavailable" in t:
        return "HTML maintenance/unavailable page"
    if "domestic interest rates" in t and "sora" in t:
        return "MAS Domestic Interest Rates form/result page"
    if "doctype html" in t or "<html" in t:
        return "HTML page"
    if not text:
        return "empty response"
    return "non-JSON/text response"


def extract_input_fields(html):
    inputs = []
    for m in re.finditer(r"<input\b[^>]*>", html, flags=re.I | re.S):
        tag = m.group(0)
        attrs = attr_dict(tag)
        after = html[m.end():m.end()+650]
        before = html[max(0, m.start()-300):m.start()]
        label_text = ""
        lab_for = attrs.get("id", "")
        if lab_for:
            lm = re.search(r"<label\b[^>]*for\s*=\s*(['\"])" + re.escape(lab_for) + r"\1[^>]*>(.*?)</label>", html, flags=re.I | re.S)
            if lm:
                label_text = strip_tags(lm.group(2))
        if not label_text:
            # In this MAS page, label often follows immediately after checkbox input.
            label_text = strip_tags(after[:260]) or strip_tags(before[-260:])
        inputs.append({
            "type": attrs.get("type", ""),
            "id": attrs.get("id", ""),
            "name": attrs.get("name", ""),
            "value": attrs.get("value", ""),
            "checked": "checked" in tag.lower(),
            "label_text": label_text[:320],
            "tag_sample": tag[:300],
        })
    return pd.DataFrame(inputs)


def extract_selects_full(html):
    rows = []
    for m in re.finditer(r"<select\b[^>]*>(.*?)</select>", html, flags=re.I | re.S):
        full = m.group(0)
        start = re.search(r"<select\b[^>]*>", full, flags=re.I | re.S).group(0)
        attrs = attr_dict(start)
        options = []
        selected_value = ""
        for om in re.finditer(r"<option\b([^>]*)>(.*?)</option>", m.group(1), flags=re.I | re.S):
            oattrs = attr_dict("<option " + om.group(1) + ">")
            txt = strip_tags(om.group(2))
            val = oattrs.get("value", txt)
            selected = "selected" in om.group(1).lower()
            if selected:
                selected_value = val
            options.append({"value": val, "text": txt, "selected": selected})
        rows.append({
            "name": attrs.get("name", ""),
            "id": attrs.get("id", ""),
            "selected_value": selected_value,
            "options": options,
            "options_count": len(options),
            "options_sample": str(options[:15]),
        })
    return pd.DataFrame(rows)


def extract_tables_regex(html):
    summaries = []
    all_rows = []
    for ti, tm in enumerate(re.finditer(r"<table\b[^>]*>(.*?)</table>", html, flags=re.I | re.S)):
        table_html = tm.group(1)
        rows = []
        for trm in re.finditer(r"<tr\b[^>]*>(.*?)</tr>", table_html, flags=re.I | re.S):
            cells = []
            for cm in re.finditer(r"<(?:td|th)\b[^>]*>(.*?)</(?:td|th)>", trm.group(1), flags=re.I | re.S):
                cells.append(strip_tags(cm.group(1)))
            if cells:
                rows.append(cells)
                row_dict = {f"col_{i}": v for i, v in enumerate(cells)}
                row_dict["__table_index"] = ti
                row_dict["__row_index"] = len(rows) - 1
                all_rows.append(row_dict)
        flat = " ".join(" ".join(r) for r in rows)
        summaries.append({
            "table_index": ti,
            "rows": len(rows),
            "max_cols": max([len(r) for r in rows], default=0),
            "contains_sora": bool(re.search(r"SORA|Compounded", flat, flags=re.I)),
            "contains_2026": "2026" in flat,
            "sample": flat[:900],
        })
    return pd.DataFrame(summaries), pd.DataFrame(all_rows)


def extract_loose_sora_lines(html):
    text = strip_tags(html)
    # Expose lines/windows around SORA, dates and percentage-like values.
    candidates = []
    for m in re.finditer(r".{0,160}(?:SORA|Compounded|2026|2025).{0,260}", text, flags=re.I):
        chunk = m.group(0)
        nums = re.findall(r"[-+]?\d+(?:\.\d+)?\s*%?", chunk)
        dates = re.findall(r"\b(?:\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}|\d{4}-\d{2}-\d{2}|\d{8})\b", chunk)
        candidates.append({"chunk": chunk[:600], "numbers": str(nums[:20]), "dates": str(dates[:10])})
    return pd.DataFrame(candidates[:300])


def build_post_payload(html, start_year="2026", start_month="Jan", end_year="2026", end_month="Jun", mode="Display"):
    inputs = extract_input_fields(html)
    selects = extract_selects_full(html)
    payload = {}
    notes = []

    # Hidden and default text values.
    for _, r in inputs.iterrows():
        name = str(r.get("name", ""))
        if not name:
            continue
        typ = str(r.get("type", "")).lower()
        val = str(r.get("value", ""))
        if typ in {"hidden", "text"}:
            payload[name] = val

    # Select values.
    for _, r in selects.iterrows():
        name = str(r.get("name", ""))
        if not name:
            continue
        opts = r.get("options", [])
        lower = (name + " " + str(r.get("id", ""))).lower()
        target_text = None
        if "start" in lower and "year" in lower:
            target_text = start_year
        elif "end" in lower and "year" in lower:
            target_text = end_year
        elif "start" in lower and "month" in lower:
            target_text = start_month
        elif "end" in lower and "month" in lower:
            target_text = end_month
        val = str(r.get("selected_value", ""))
        if target_text:
            for opt in opts:
                if str(opt.get("text", "")).lower().startswith(str(target_text).lower()) or str(opt.get("value", "")).lower().startswith(str(target_text).lower()):
                    val = str(opt.get("value", ""))
                    break
        if val:
            payload[name] = val

    # SORA-related checkboxes.
    sora_checks = []
    for _, r in inputs.iterrows():
        typ = str(r.get("type", "")).lower()
        name = str(r.get("name", ""))
        label = str(r.get("label_text", ""))
        value = str(r.get("value", "on")) or "on"
        if typ == "checkbox" and name and re.search(r"\bSORA\b|Compounded SORA|SORA Index", label, flags=re.I):
            payload[name] = value
            sora_checks.append({"name": name, "value": value, "label_text": label})
    notes.append(f"SORA checkbox count={len(sora_checks)}")

    # Prefer the requested button.
    buttons = inputs[inputs["type"].astype(str).str.lower().isin(["submit", "button"])] if not inputs.empty and "type" in inputs else pd.DataFrame()
    chosen_button = None
    for _, r in buttons.iterrows():
        name = str(r.get("name", ""))
        val = str(r.get("value", ""))
        label = str(r.get("label_text", ""))
        hay = val + " " + label + " " + name
        if name and re.search(mode, hay, flags=re.I):
            chosen_button = (name, val or mode)
            break
    if chosen_button:
        payload[chosen_button[0]] = chosen_button[1]
        notes.append(f"button={chosen_button}")
    else:
        notes.append(f"no obvious {mode} button found")

    return payload, pd.DataFrame(sora_checks), "; ".join(notes)


def run_mas_html_probe(start_year="2026", start_month="Jan", end_year="2026", end_month="Jun", do_post=True, button_mode="Display"):
    get_r = request_text(MAS_DIR_URL, "MAS Domestic Interest Rates HTML GET", accept="text/html,*/*")
    html = get_r["text"] if get_r["ok"] else ""
    get_diag = {k: v for k, v in get_r.items() if k != "text"}
    get_diag["classification"] = classify_html(html)

    inputs = extract_input_fields(html)
    selects_full = extract_selects_full(html)
    get_table_summary, get_table_rows = extract_tables_regex(html)
    loose_get = extract_loose_sora_lines(html)

    clues = []
    for pat in [r"__doPostBack\([^)]*\)", r"WebResource\.axd[^'\"]+", r"ScriptResource\.axd[^'\"]+", r"[A-Za-z0-9_./-]+\.ashx[^'\"]*", r"[A-Za-z0-9_./-]+\.aspx[^'\"]*", r"SORA", r"comp_sora_1m|comp_sora_3m|comp_sora_6m|sora_index"]:
        matches = re.findall(pat, html, flags=re.I)
        clues.append({"pattern": pat, "matches_count": len(matches), "sample": str(matches[:20])[:1000]})

    post_diag = pd.DataFrame()
    post_table_summary = pd.DataFrame()
    post_table_rows = pd.DataFrame()
    post_sora_rows = pd.DataFrame()
    post_loose = pd.DataFrame()
    post_sample = pd.DataFrame()
    payload_df = pd.DataFrame()
    sora_checks_df = pd.DataFrame()
    payload_notes = ""

    if do_post and html:
        payload, sora_checks_df, payload_notes = build_post_payload(html, start_year, start_month, end_year, end_month, button_mode)
        payload_df = pd.DataFrame([{
            "key": k,
            "value_sample": ("<VIEWSTATE hidden>" if k.upper().startswith("__VIEWSTATE") else str(v)[:160])
        } for k, v in payload.items()])
        encoded = urllib.parse.urlencode(payload).encode("utf-8")
        post_r = request_text(
            MAS_DIR_URL,
            f"MAS Domestic Interest Rates HTML POST {button_mode}",
            accept="text/html,*/*",
            data=encoded,
            method="POST",
            headers_extra={"Content-Type": "application/x-www-form-urlencoded", "Referer": MAS_DIR_URL},
        )
        post_html = post_r["text"] if post_r["ok"] else ""
        pdg = {k: v for k, v in post_r.items() if k != "text"}
        pdg["classification"] = classify_html(post_html)
        pdg["payload_notes"] = payload_notes
        post_diag = pd.DataFrame([pdg])
        post_table_summary, post_table_rows = extract_tables_regex(post_html)
        if not post_table_rows.empty:
            mask = post_table_rows.astype(str).apply(lambda col: col.str.contains("SORA|Compounded|2026|2025", regex=True, na=False)).any(axis=1)
            post_sora_rows = post_table_rows[mask].copy() if mask.any() else pd.DataFrame()
        post_loose = extract_loose_sora_lines(post_html)
        post_sample = pd.DataFrame([{"url": MAS_DIR_URL, "sample": post_html[:7000]}])

    return {
        "get_diag": pd.DataFrame([get_diag]),
        "inputs": inputs,
        "selects": selects_full.drop(columns=["options"], errors="ignore"),
        "get_table_summary": get_table_summary,
        "get_table_rows": get_table_rows,
        "get_loose": loose_get,
        "clues": pd.DataFrame(clues),
        "payload": payload_df,
        "sora_checks": sora_checks_df,
        "payload_notes": payload_notes,
        "post_diag": post_diag,
        "post_table_summary": post_table_summary,
        "post_table_rows": post_table_rows,
        "post_sora_rows": post_sora_rows,
        "post_loose": post_loose,
        "post_sample": post_sample,
    }


# Optional JP confirmation retained.
def parse_boj_csv(text, target_code="STRDCLUCON"):
    recs = []
    for i, row in enumerate(csv.reader(io.StringIO(text))):
        if not row or row[0] != target_code:
            continue
        date_idx = next((j for j, cell in enumerate(row) if re.fullmatch(r"\d{8}", str(cell).strip())), None)
        if date_idx is None:
            continue
        date = parse_date_any(row[date_idx])
        value = None
        for k in range(date_idx + 1, len(row)):
            n = clean_number(row[k])
            if n is not None:
                value = n
                break
        if pd.notna(date) and value is not None:
            recs.append({"line_no": i, "code": target_code, "date": date, "value": value, "raw": ",".join(row[:min(len(row), date_idx + 5)])})
    return pd.DataFrame(recs)


def run_boj_confirm():
    start = (pd.Timestamp.today() - pd.DateOffset(months=18)).strftime("%Y%m")
    url = "https://www.stat-search.boj.or.jp/api/v1/getDataCode?" + urllib.parse.urlencode({"format": "csv", "lang": "en", "db": "FM01", "startDate": start, "code": "STRDCLUCON"})
    r = request_text(url, "BOJ FM01 STRDCLUCON csv", accept="text/csv,*/*")
    diag = {k: v for k, v in r.items() if k != "text"}
    parsed = parse_boj_csv(r["text"], "STRDCLUCON") if r["ok"] else pd.DataFrame()
    row = None
    if not parsed.empty:
        latest = parsed.sort_values("date").iloc[-1]
        row = {"market": "JP", "indicator": "Rates", "date": latest["date"].strftime("%Y-%m-%d"), "value": float(latest["value"]), "unit": "%", "source": "BOJ FM01 STRDCLUCON", "source_type": "Official / API Lab", "notes": "BOJ FM01 Uncollateralized Overnight Call Rate Average Daily."}
    return row, pd.DataFrame([diag]), parsed


st.title("Global20Engine Rate Diagnostics Lab")
st.caption("SG MAS HTML GET/POST probe without lxml dependency + JP BOJ confirmation.")

with st.sidebar:
    st.header("MAS HTML POST settings")
    sy = st.text_input("Start year", "2026")
    sm = st.text_input("Start month", "Jan")
    ey = st.text_input("End year", "2026")
    em = st.text_input("End month", "Jun")
    button_mode = st.selectbox("Button mode", ["Display", "Download"], index=0)
    do_post = st.checkbox("Attempt controlled ASP.NET POST", value=True)

c1, c2 = st.columns(2)
with c1:
    run_html = st.button("Run SG MAS HTML GET/POST probe", use_container_width=True)
with c2:
    run_jp = st.button("Confirm JP BOJ parser", use_container_width=True)

if run_html:
    st.header("SG MAS HTML GET/POST probe")
    res = run_mas_html_probe(sy, sm, ey, em, do_post, button_mode)

    st.subheader("GET endpoint diagnostics")
    st.dataframe(res["get_diag"], use_container_width=True)
    st.subheader("GET regex table summaries")
    st.dataframe(res["get_table_summary"], use_container_width=True)
    st.subheader("Input fields discovered")
    st.dataframe(res["inputs"], use_container_width=True)
    st.subheader("Select fields discovered")
    st.dataframe(res["selects"], use_container_width=True)
    st.subheader("HTML clue scan")
    st.dataframe(res["clues"], use_container_width=True)
    st.subheader("Loose GET SORA/date/value text windows")
    st.dataframe(res["get_loose"], use_container_width=True)

    if do_post:
        st.subheader("POST payload summary")
        st.write(res["payload_notes"])
        st.dataframe(res["payload"], use_container_width=True)
        st.subheader("SORA checkboxes selected for POST")
        st.dataframe(res["sora_checks"], use_container_width=True)
        st.subheader("POST endpoint diagnostics")
        st.dataframe(res["post_diag"], use_container_width=True)
        st.subheader("POST regex table summaries")
        st.dataframe(res["post_table_summary"], use_container_width=True)
        st.subheader("POST parsed table rows")
        st.dataframe(res["post_table_rows"].head(300), use_container_width=True)
        st.subheader("POST candidate SORA result rows")
        st.dataframe(res["post_sora_rows"].head(300), use_container_width=True)
        st.subheader("Loose POST SORA/date/value text windows")
        st.dataframe(res["post_loose"].head(300), use_container_width=True)
        with st.expander("Raw POST HTML first 7,000 characters", expanded=False):
            st.dataframe(res["post_sample"], use_container_width=True)

if run_jp:
    st.header("JP BOJ parser confirmation")
    row, diag, parsed = run_boj_confirm()
    if row:
        st.success("JP BOJ parser confirmed.")
        st.dataframe(pd.DataFrame([row]), use_container_width=True)
    else:
        st.error("JP BOJ parser did not return a row in this run.")
    st.subheader("Endpoint diagnostics")
    st.dataframe(diag, use_container_width=True)
    st.subheader("Parsed observations")
    st.dataframe(parsed.tail(100), use_container_width=True)

st.markdown("""
### Source-governance interpretation
- MAS remains the official primary SG source.
- This test avoids `pandas.read_html` / `lxml` and uses simple table/text extraction.
- MAS HTML POST is still diagnostic only until a clean date/value SORA row is proven.
""")
