
# macro_rate_diagnostics_lab.py
# Global20Engine Rate Diagnostics Lab v6 - SG MAS HTML GET/POST probe + TE + JP

import csv
import io
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Global20Engine Rate Diagnostics Lab", layout="wide")

USER_AGENT = "Mozilla/5.0 Global20Engine-RateDiagnosticsLab/6.0"
TIMEOUT = 30

MAS_RESOURCE_ID = "9a0bf149-308c-4bd2-832d-76c8e6cb47ed"
MAS_DIR_URL = "https://eservices.mas.gov.sg/statistics/dir/domesticinterestrates.aspx"

MAS_URLS = [
    {"label": "MAS generic eservices route", "url": "https://eservices.mas.gov.sg/api/action/datastore/search.json?" + urllib.parse.urlencode({"resource_id": MAS_RESOURCE_ID, "limit": "5000"})},
    {"label": "MAS GitHub open-source exact route - comp_sora_1m", "url": "https://eservices.mas.gov.sg/api/action/datastore/search.json?" + urllib.parse.urlencode({"resource_id": MAS_RESOURCE_ID, "limit": "100", "fields": "end_of_day,comp_sora_1m", "sort": "end_of_day desc"})},
    {"label": "MAS GitHub open-source broad SORA fields", "url": "https://eservices.mas.gov.sg/api/action/datastore/search.json?" + urllib.parse.urlencode({"resource_id": MAS_RESOURCE_ID, "limit": "100", "fields": "end_of_day,sora,sora_index,comp_sora_1m,comp_sora_3m,comp_sora_6m", "sort": "end_of_day desc"})},
]

TE_INDICATOR_CANDIDATES = ["sora", "singapore overnight rate average", "compounded sora", "interest rate", "interbank rate"]


def request_text(url, label, accept="*/*", data=None, method=None, headers_extra=None):
    started = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    try:
        headers = {"User-Agent": USER_AGENT, "Accept": accept, "Accept-Encoding": "identity"}
        if headers_extra:
            headers.update(headers_extra)
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
            return {"label": label, "ok": True, "status": getattr(resp, "status", ""), "content_type": resp.headers.get("Content-Type", ""), "bytes": len(raw), "started_utc": started, "url": url, "text": raw.decode("utf-8", errors="replace"), "error": ""}
    except Exception as e:
        return {"label": label, "ok": False, "status": "", "content_type": "", "bytes": 0, "started_utc": started, "url": url, "text": "", "error": repr(e)}


def clean_number(x):
    if x is None:
        return None
    s = str(x).strip().strip('"').strip("'")
    if not s or s.upper() in {"N.A.", "N/A", "NA", "NULL", "NONE", "-", "--", "."}:
        return None
    s = re.sub(r"\[[^\]]*\]", "", s).replace("+", "").replace("%", "").replace(",", "").replace("−", "-").replace("–", "-")
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


def attr_dict(tag):
    attrs = {}
    for a in re.finditer(r"([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*(['\"])(.*?)\2", tag, flags=re.S):
        attrs[a.group(1).lower()] = a.group(3)
    return attrs


def strip_tags(x):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(x))).strip()


def extract_input_fields(html):
    inputs = []
    for m in re.finditer(r"<input\b[^>]*>", html, flags=re.I | re.S):
        tag = m.group(0)
        attrs = attr_dict(tag)
        # label/nearby text: useful for checkbox mapping
        after = html[m.end():m.end()+500]
        before = html[max(0, m.start()-250):m.start()]
        label_text = ""
        lab_for = attrs.get("id", "")
        if lab_for:
            lm = re.search(r"<label\b[^>]*for\s*=\s*(['\"])" + re.escape(lab_for) + r"\1[^>]*>(.*?)</label>", html, flags=re.I | re.S)
            if lm:
                label_text = strip_tags(lm.group(2))
        if not label_text:
            lm = re.search(r"<label\b[^>]*>(.*?)</label>", after, flags=re.I | re.S)
            label_text = strip_tags(lm.group(1)) if lm else strip_tags((before + " " + after)[:250])
        inputs.append({
            "type": attrs.get("type", ""),
            "id": attrs.get("id", ""),
            "name": attrs.get("name", ""),
            "value": attrs.get("value", ""),
            "checked": "checked" in tag.lower(),
            "label_text": label_text[:300],
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
        rows.append({"name": attrs.get("name", ""), "id": attrs.get("id", ""), "selected_value": selected_value, "options": options, "options_count": len(options), "options_sample": str(options[:15])})
    return pd.DataFrame(rows)


def read_html_tables(html):
    summaries, previews = [], []
    try:
        tables = pd.read_html(io.StringIO(html)) if html else []
        for i, t in enumerate(tables):
            contains_sora = t.astype(str).apply(lambda col: col.str.contains("SORA|sora|Compounded", regex=True, na=False)).any().any()
            summaries.append({"table_index": i, "rows": len(t), "cols": len(t.columns), "columns": ", ".join(map(str, t.columns))[:500], "contains_sora": contains_sora})
            tt = t.copy(); tt["__table_index"] = i; previews.append(tt.head(50))
    except Exception as e:
        summaries.append({"table_index": "error", "rows": 0, "cols": 0, "columns": "", "contains_sora": False, "error": repr(e)})
    return pd.DataFrame(summaries), pd.concat(previews, ignore_index=True) if previews else pd.DataFrame()


def extract_sora_result_candidates(tables_df):
    if tables_df is None or tables_df.empty:
        return pd.DataFrame()
    # Very cautious: expose rows containing SORA or likely date+numeric fields. Do not auto-promote yet.
    out = tables_df.copy()
    mask = out.astype(str).apply(lambda col: col.str.contains("SORA|sora|Compounded|2026|2025", regex=True, na=False)).any(axis=1)
    return out[mask].copy() if mask.any() else pd.DataFrame()


def build_post_payload(html, start_year="2026", start_month="Jan", end_year="2026", end_month="Jun"):
    inputs = extract_input_fields(html)
    selects = extract_selects_full(html)
    payload = {}
    notes = []

    # Preserve all hidden values and default text values.
    for _, r in inputs.iterrows():
        name = str(r.get("name", ""))
        if not name:
            continue
        typ = str(r.get("type", "")).lower()
        val = str(r.get("value", ""))
        if typ in {"hidden", "text"}:
            payload[name] = val

    # Select values: infer by option text/name.
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
                    val = str(opt.get("value", "")); break
        if val:
            payload[name] = val

    # Check all SORA-related checkboxes only.
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

    # Click DISPLAY or DOWNLOAD button if obvious. Prefer DISPLAY.
    buttons = inputs[inputs["type"].astype(str).str.lower().isin(["submit", "button"])] if not inputs.empty and "type" in inputs else pd.DataFrame()
    chosen_button = None
    for _, r in buttons.iterrows():
        name = str(r.get("name", "")); val = str(r.get("value", "")); label = str(r.get("label_text", ""))
        if name and re.search(r"display", val + " " + label, flags=re.I):
            chosen_button = (name, val or "DISPLAY"); break
    if chosen_button is None:
        for _, r in buttons.iterrows():
            name = str(r.get("name", "")); val = str(r.get("value", "")); label = str(r.get("label_text", ""))
            if name and re.search(r"download", val + " " + label, flags=re.I):
                chosen_button = (name, val or "DOWNLOAD"); break
    if chosen_button:
        payload[chosen_button[0]] = chosen_button[1]
        notes.append(f"button={chosen_button}")
    else:
        notes.append("no obvious display/download button found")

    return payload, pd.DataFrame(sora_checks), "; ".join(notes)


def run_mas_html_probe(start_year="2026", start_month="Jan", end_year="2026", end_month="Jun", do_post=False):
    get_r = request_text(MAS_DIR_URL, "MAS Domestic Interest Rates HTML GET", accept="text/html,*/*")
    get_diag = {k: v for k, v in get_r.items() if k != "text"}
    get_diag["classification"] = classify_html(get_r["text"])
    html = get_r["text"] if get_r["ok"] else ""
    get_tables, get_previews = read_html_tables(html)
    inputs = extract_input_fields(html)
    selects = extract_selects_full(html)

    clues = []
    clue_patterns = [r"__doPostBack\([^)]*\)", r"WebResource\.axd[^'\"]+", r"ScriptResource\.axd[^'\"]+", r"[A-Za-z0-9_./-]+\.ashx[^'\"]*", r"[A-Za-z0-9_./-]+\.aspx[^'\"]*", r"SORA", r"comp_sora_1m|comp_sora_3m|comp_sora_6m|sora_index"]
    for pat in clue_patterns:
        matches = re.findall(pat, html, flags=re.I)
        clues.append({"pattern": pat, "matches_count": len(matches), "sample": str(matches[:20])[:1000]})

    post_diag = pd.DataFrame()
    post_tables = pd.DataFrame()
    post_previews = pd.DataFrame()
    payload_df = pd.DataFrame()
    sora_checks_df = pd.DataFrame()
    post_sample = pd.DataFrame()
    post_candidates = pd.DataFrame()
    payload_notes = ""

    if do_post and html:
        payload, sora_checks_df, payload_notes = build_post_payload(html, start_year, start_month, end_year, end_month)
        payload_df = pd.DataFrame([{"key": k, "value_sample": (str(v)[:120] if not k.upper().startswith("__VIEWSTATE") else "<VIEWSTATE hidden>")} for k, v in payload.items()])
        encoded = urllib.parse.urlencode(payload).encode("utf-8")
        post_r = request_text(MAS_DIR_URL, "MAS Domestic Interest Rates HTML POST", accept="text/html,*/*", data=encoded, method="POST", headers_extra={"Content-Type": "application/x-www-form-urlencoded", "Referer": MAS_DIR_URL})
        pdg = {k: v for k, v in post_r.items() if k != "text"}; pdg["classification"] = classify_html(post_r["text"]); pdg["payload_notes"] = payload_notes
        post_diag = pd.DataFrame([pdg])
        post_tables, post_previews = read_html_tables(post_r["text"] if post_r["ok"] else "")
        post_candidates = extract_sora_result_candidates(post_previews)
        post_sample = pd.DataFrame([{"url": MAS_DIR_URL, "sample": (post_r["text"][:5000] if post_r["ok"] else "")}])

    return {
        "get_diag": pd.DataFrame([get_diag]),
        "get_tables": get_tables,
        "get_previews": get_previews,
        "inputs": inputs,
        "selects": selects.drop(columns=["options"], errors="ignore"),
        "clues": pd.DataFrame(clues),
        "get_sample": pd.DataFrame([{"url": MAS_DIR_URL, "sample": html[:5000]}]),
        "post_diag": post_diag,
        "post_tables": post_tables,
        "post_previews": post_previews,
        "payload": payload_df,
        "sora_checks": sora_checks_df,
        "post_sample": post_sample,
        "post_candidates": post_candidates,
        "payload_notes": payload_notes,
    }


# ---------------- MAS JSON route diagnostic ----------------
def run_mas_route_diag():
    diagnostics, samples, parsed_all, records_previews = [], [], [], []
    for route in MAS_URLS:
        label, url = route["label"], route["url"]
        r = request_text(url, label, accept="application/json,text/html,*/*")
        d = {k: v for k, v in r.items() if k != "text"}
        d["route_label"] = label
        if not r["ok"]:
            d["parse_result"] = "request failed"
        elif "json" not in r.get("content_type", "").lower():
            d["classification"] = classify_html(r["text"])
            d["parse_result"] = "not JSON"
        else:
            d["parse_result"] = "JSON route returned; parser not expanded in this view"
        diagnostics.append(d); samples.append({"route_label": label, "url": url, "sample": r["text"][:3000]})
    return pd.DataFrame(diagnostics), pd.DataFrame(samples)


# ---------------- JP BOJ confirmation ----------------
def parse_boj_csv(text, target_code="STRDCLUCON"):
    recs = []
    for i, row in enumerate(csv.reader(io.StringIO(text))):
        if not row or row[0] != target_code: continue
        date_idx = next((j for j, cell in enumerate(row) if re.fullmatch(r"\d{8}", str(cell).strip())), None)
        if date_idx is None: continue
        date = parse_date_any(row[date_idx])
        value = None
        for k in range(date_idx + 1, len(row)):
            n = clean_number(row[k])
            if n is not None: value = n; break
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
    return row, pd.DataFrame([diag]), pd.DataFrame([{"url": url, "sample": r["text"][:3000]}]), parsed


st.title("Global20Engine Rate Diagnostics Lab")
st.caption("SG MAS route test + SG MAS HTML GET/POST probe + JP BOJ confirmation.")

with st.sidebar:
    st.header("MAS HTML POST settings")
    sy = st.text_input("Start year", "2026")
    sm = st.text_input("Start month", "Jan")
    ey = st.text_input("End year", "2026")
    em = st.text_input("End month", "Jun")
    do_post = st.checkbox("Attempt controlled ASP.NET POST", value=True)

c1, c2, c3 = st.columns(3)
with c1:
    run_sg = st.button("Run SG MAS route diagnostic", use_container_width=True)
with c2:
    run_html = st.button("Run SG MAS HTML GET/POST probe", use_container_width=True)
with c3:
    run_jp = st.button("Confirm JP BOJ parser", use_container_width=True)

if run_sg:
    st.header("SG MAS route diagnostic")
    diag, samples = run_mas_route_diag()
    st.subheader("Endpoint diagnostics")
    st.dataframe(diag, use_container_width=True)
    with st.expander("Raw MAS response samples", expanded=True):
        st.dataframe(samples, use_container_width=True)

if run_html:
    st.header("SG MAS HTML GET/POST probe")
    res = run_mas_html_probe(sy, sm, ey, em, do_post)
    st.subheader("GET endpoint diagnostics")
    st.dataframe(res["get_diag"], use_container_width=True)
    st.subheader("GET pandas.read_html table summaries")
    st.dataframe(res["get_tables"], use_container_width=True)
    st.subheader("Input fields discovered")
    st.dataframe(res["inputs"], use_container_width=True)
    st.subheader("Select fields discovered")
    st.dataframe(res["selects"], use_container_width=True)
    st.subheader("HTML clue scan")
    st.dataframe(res["clues"], use_container_width=True)
    with st.expander("Raw GET HTML first 5,000 characters", expanded=False):
        st.dataframe(res["get_sample"], use_container_width=True)

    if do_post:
        st.subheader("POST payload summary")
        st.write(res["payload_notes"])
        st.dataframe(res["payload"], use_container_width=True)
        st.subheader("SORA checkboxes selected for POST")
        st.dataframe(res["sora_checks"], use_container_width=True)
        st.subheader("POST endpoint diagnostics")
        st.dataframe(res["post_diag"], use_container_width=True)
        st.subheader("POST pandas.read_html table summaries")
        st.dataframe(res["post_tables"], use_container_width=True)
        st.subheader("POST parsed table previews")
        st.dataframe(res["post_previews"], use_container_width=True)
        st.subheader("POST candidate SORA result rows")
        st.dataframe(res["post_candidates"], use_container_width=True)
        with st.expander("Raw POST HTML first 5,000 characters", expanded=False):
            st.dataframe(res["post_sample"], use_container_width=True)

if run_jp:
    st.header("JP BOJ parser confirmation")
    row, diag, samples, parsed = run_boj_confirm()
    if row:
        st.success("JP BOJ parser confirmed.")
        st.dataframe(pd.DataFrame([row]), use_container_width=True)
    else:
        st.error("JP BOJ parser did not return a row in this run.")
    st.subheader("Endpoint diagnostics")
    st.dataframe(diag, use_container_width=True)
    st.subheader("Parsed observations")
    st.dataframe(parsed.tail(100), use_container_width=True)
    with st.expander("Raw BOJ sample", expanded=False):
        st.dataframe(samples, use_container_width=True)

st.markdown("""
### Source-governance interpretation
- MAS remains the official primary SG source.
- MAS HTML POST probe is a controlled official-page fallback test, not production until clean date/value rows are proven.
- No login, no CAPTCHA bypass, no broad crawling, one official MAS page only.
""")
