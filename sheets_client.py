"""
sheets_client.py
================
All Google Sheets read/write operations.

Tabs managed
------------
  Raw Data              — append-only log of every prompt run
  ACKO Visibility Summary — per-prompt ACKO mention rates
  Brand Leaderboard     — ranked brand mention counts
  Change Log            — rows where something changed vs prior run
  Dashboard             — run-over-run comparison + current status
"""

import os
import json
import logging
import time
from datetime import datetime

import gspread
from gspread.exceptions import APIError
from google.oauth2.service_account import Credentials

from config import (
    TRACKED_BRANDS,
    PROMPTS,
    TAB_NAMES,
    RAW_DATA_HEADERS,
    ACKO_SUMMARY_HEADERS,
    LEADERBOARD_HEADERS,
    CHANGE_LOG_HEADERS,
)

logger = logging.getLogger(__name__)

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# ---------------------------------------------------------------------------
# Color palette (Google Sheets RGB 0–1 scale)
# ---------------------------------------------------------------------------
_C_HEADER_BG    = {"red": 0.13, "green": 0.27, "blue": 0.53}   # dark blue
_C_HEADER_FG    = {"red": 1.0,  "green": 1.0,  "blue": 1.0}    # white
_C_SECTION_BG   = {"red": 0.27, "green": 0.45, "blue": 0.74}   # medium blue
_C_SECTION_FG   = {"red": 1.0,  "green": 1.0,  "blue": 1.0}    # white
_C_ACKO_AMBER   = {"red": 1.0,  "green": 0.93, "blue": 0.60}   # amber
_C_GREEN_BG     = {"red": 0.82, "green": 0.94, "blue": 0.82}   # light green
_C_RED_BG       = {"red": 0.96, "green": 0.80, "blue": 0.80}   # light red
_C_ALT_ROW      = {"red": 0.94, "green": 0.96, "blue": 1.0}    # soft blue-white
_C_WHITE        = {"red": 1.0,  "green": 1.0,  "blue": 1.0}    # white
_C_TITLE_BG     = {"red": 0.07, "green": 0.18, "blue": 0.38}   # very dark navy


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def _get_credentials() -> Credentials:
    raw = os.environ.get("GOOGLE_SHEETS_CREDENTIALS", "").strip()
    if not raw:
        raise ValueError(
            "GOOGLE_SHEETS_CREDENTIALS environment variable is not set. "
            "Please add the service account JSON as a GitHub Secret."
        )
    try:
        info = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "GOOGLE_SHEETS_CREDENTIALS is not valid JSON. "
            "Make sure you pasted the full contents of your service account key file."
        ) from exc
    return Credentials.from_service_account_info(info, scopes=_SCOPES)


def get_spreadsheet():
    """Return an authenticated gspread Spreadsheet object."""
    sheet_id = os.environ.get("SPREADSHEET_ID", "").strip()
    if not sheet_id:
        raise ValueError(
            "SPREADSHEET_ID environment variable is not set. "
            "Copy the long ID from your Google Sheet URL and add it as a GitHub Secret."
        )
    creds = _get_credentials()
    gc    = gspread.authorize(creds)
    return gc.open_by_key(sheet_id)


def validate_sheet_access() -> tuple[bool, list[str], object | None]:
    """
    Try to open the spreadsheet.
    Returns (success, list_of_tab_titles, spreadsheet_or_None).
    """
    try:
        spreadsheet = get_spreadsheet()
        titles = [ws.title for ws in spreadsheet.worksheets()]
        return True, titles, spreadsheet
    except Exception as exc:
        logger.error("Cannot access Google Sheet: %s", exc)
        return False, [], None


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _safe_format(ws, range_str: str, fmt: dict) -> None:
    """Apply cell formatting; swallow errors so data writes are never blocked."""
    try:
        ws.format(range_str, fmt)
    except Exception as exc:
        logger.debug("Formatting skipped (%s): %s", range_str, exc)


def _fmt_header(ws, range_str: str) -> None:
    """Apply the standard dark-blue bold header style."""
    _safe_format(ws, range_str, {
        "backgroundColor": _C_HEADER_BG,
        "textFormat": {
            "bold": True,
            "foregroundColor": _C_HEADER_FG,
            "fontSize": 10,
        },
        "horizontalAlignment": "CENTER",
    })


def _fmt_section(ws, range_str: str) -> None:
    """Apply medium-blue section header style."""
    _safe_format(ws, range_str, {
        "backgroundColor": _C_SECTION_BG,
        "textFormat": {
            "bold": True,
            "foregroundColor": _C_SECTION_FG,
            "fontSize": 10,
        },
    })


def _fmt_alt_rows(ws, start_row: int, end_row: int, num_cols: int) -> None:
    """
    Apply alternating row shading from start_row to end_row (1-indexed, inclusive).
    Even rows → soft blue-white; odd rows → white.
    """
    last_col = chr(ord("A") + num_cols - 1)
    for row in range(start_row, end_row + 1):
        color = _C_ALT_ROW if row % 2 == 0 else _C_WHITE
        _safe_format(ws, f"A{row}:{last_col}{row}", {"backgroundColor": color})


# ---------------------------------------------------------------------------
# Tab bootstrap
# ---------------------------------------------------------------------------

def _ensure_tab(spreadsheet, title: str, headers: list[str]) -> gspread.Worksheet:
    """Return the worksheet with *title*, creating it (with headers) if absent."""
    try:
        ws = spreadsheet.worksheet(title)
        if ws.row_count == 0 or not ws.get_all_values():
            if headers:
                ws.append_row(headers)
                _fmt_header(ws, "1:1")
        return ws
    except gspread.WorksheetNotFound:
        logger.warning("Tab '%s' not found — creating it now.", title)
        ws = spreadsheet.add_worksheet(title=title, rows=2000, cols=30)
        if headers:
            ws.append_row(headers)
            _fmt_header(ws, "1:1")
        time.sleep(1)
        return ws


def ensure_tabs_exist(spreadsheet) -> list[str]:
    """
    Verify all 5 required tabs exist; create any that are missing.
    Returns a list of tab names that were created (empty if all existed).
    """
    existing = {ws.title for ws in spreadsheet.worksheets()}
    created  = []

    tab_configs = [
        (TAB_NAMES["raw_data"],     RAW_DATA_HEADERS),
        (TAB_NAMES["acko_summary"], ACKO_SUMMARY_HEADERS),
        (TAB_NAMES["leaderboard"],  LEADERBOARD_HEADERS),
        (TAB_NAMES["change_log"],   CHANGE_LOG_HEADERS),
        (TAB_NAMES["dashboard"],    []),
    ]

    for title, headers in tab_configs:
        if title not in existing:
            _ensure_tab(spreadsheet, title, headers)
            created.append(title)
        else:
            ws = spreadsheet.worksheet(title)
            vals = ws.get_all_values()
            if not vals and headers:
                ws.append_row(headers)
                _fmt_header(ws, "1:1")

    return created


# ---------------------------------------------------------------------------
# Raw Data
# ---------------------------------------------------------------------------

def append_raw_data(spreadsheet, rows: list[list]) -> None:
    """Batch-append *rows* to the Raw Data tab."""
    if not rows:
        return
    ws = _ensure_tab(spreadsheet, TAB_NAMES["raw_data"], RAW_DATA_HEADERS)
    ws.append_rows(rows, value_input_option="RAW")
    logger.info("Appended %d row(s) to Raw Data.", len(rows))


def get_all_raw_data(spreadsheet) -> list[dict]:
    """Return all records from Raw Data as a list of dicts (header row = keys)."""
    try:
        ws = spreadsheet.worksheet(TAB_NAMES["raw_data"])
        return ws.get_all_records()
    except Exception as exc:
        logger.warning("Could not read Raw Data: %s", exc)
        return []


def clear_raw_data(spreadsheet) -> int:
    """
    Delete all data rows from Raw Data, keeping the header row intact.
    Returns the number of rows removed.
    """
    try:
        ws = spreadsheet.worksheet(TAB_NAMES["raw_data"])
        all_values = ws.get_all_values()
        rows_removed = max(0, len(all_values) - 1)
        if rows_removed == 0:
            logger.info("Raw Data is already empty (header only).")
            return 0
        ws.clear()
        ws.append_row(RAW_DATA_HEADERS)
        _fmt_header(ws, "1:1")
        logger.info("Raw Data cleared — %d data rows removed, header preserved.", rows_removed)
        return rows_removed
    except Exception as exc:
        logger.error("Failed to clear Raw Data: %s", exc)
        raise


# ---------------------------------------------------------------------------
# Change detection helpers
# ---------------------------------------------------------------------------

def get_previous_run_data_from_list(
    all_data: list[dict],
    prompt_num: int,
    platform: str,
) -> dict | None:
    """Filter *all_data* for the most recent record matching prompt+platform."""
    matching = [
        r for r in all_data
        if (
            str(r.get("Prompt #", "")) == str(prompt_num)
            and r.get("Platform", "") == platform
        )
    ]
    return matching[-1] if matching else None


def detect_changes(current_analysis: dict, previous_record: dict | None) -> tuple[str, str]:
    """
    Compare *current_analysis* with *previous_record*.
    Returns (change_detected: "Yes"|"No", change_details: str).
    """
    if previous_record is None:
        return "No", "First run for this prompt + platform"

    changes: list[str] = []

    prev_acko = previous_record.get("ACKO Mentioned (Y/N)", "No")
    curr_acko = current_analysis["acko_mentioned"]

    if prev_acko != curr_acko:
        if curr_acko == "Yes":
            changes.append("ACKO appeared (was not mentioned previously)")
        else:
            changes.append("ACKO dropped out (was mentioned previously)")

    if prev_acko == "Yes" and curr_acko == "Yes":
        prev_pos = previous_record.get("ACKO Position", "")
        curr_pos = current_analysis["acko_position"]
        if prev_pos and curr_pos and prev_pos != curr_pos:
            changes.append(f"ACKO position changed: {prev_pos} → {curr_pos}")

    prev_brands_str = previous_record.get("All Brands Mentioned", "") or ""
    prev_brands = {b.strip() for b in prev_brands_str.split(",") if b.strip()}
    curr_brands = set(current_analysis.get("brands_mentioned", []))

    new_brands  = curr_brands - prev_brands
    gone_brands = prev_brands - curr_brands

    if new_brands:
        changes.append(f"New brands appeared: {', '.join(sorted(new_brands))}")
    if gone_brands:
        changes.append(f"Brands disappeared: {', '.join(sorted(gone_brands))}")

    if changes:
        return "Yes", "; ".join(changes)
    return "No", "No changes detected"


# ---------------------------------------------------------------------------
# Run grouping & metrics (used by Dashboard)
# ---------------------------------------------------------------------------

def _group_by_run(all_raw_data: list[dict]) -> list[tuple[str, list[dict]]]:
    """
    Group records by their exact "Run Date (UTC)" timestamp.
    Returns a list of (timestamp, records) tuples sorted chronologically.
    """
    groups: dict[str, list[dict]] = {}
    for record in all_raw_data:
        ts = str(record.get("Run Date (UTC)", "unknown")).strip()
        groups.setdefault(ts, []).append(record)
    return sorted(groups.items(), key=lambda x: x[0])


def _acko_rate(records: list[dict]) -> float | None:
    """Return ACKO mention rate (0–100) or None if no records."""
    if not records:
        return None
    yes = sum(1 for r in records if r.get("ACKO Mentioned (Y/N)") == "Yes")
    return round(yes / len(records) * 100, 1)


def _compute_run_metrics(timestamp: str, records: list[dict], run_num: int) -> dict:
    """Compute summary metrics for a single run."""
    platforms = sorted({r.get("Platform", "") for r in records if r.get("Platform")})

    chatgpt_rows = [r for r in records if r.get("Platform") == "ChatGPT"]
    gemini_rows  = [r for r in records if r.get("Platform") == "Google AI Mode"]

    # Brand counts for this run
    brand_counts: dict[str, int] = {}
    for r in records:
        brands_str = r.get("All Brands Mentioned", "") or ""
        for b in brands_str.split(","):
            b = b.strip()
            if b:
                brand_counts[b] = brand_counts.get(b, 0) + 1

    sorted_brands = sorted(brand_counts.items(), key=lambda x: x[1], reverse=True)
    brand_names   = [b for b, _ in sorted_brands]
    top_brand     = brand_names[0] if brand_names else "N/A"
    acko_rank     = (brand_names.index("ACKO") + 1) if "ACKO" in brand_names else None

    return {
        "run_num":      run_num,
        "timestamp":    timestamp,
        "date":         timestamp[:10] if len(timestamp) >= 10 else timestamp,
        "platforms":    ", ".join(platforms),
        "chatgpt_rate": _acko_rate(chatgpt_rows),
        "gemini_rate":  _acko_rate(gemini_rows),
        "overall_rate": _acko_rate(records),
        "acko_rank":    acko_rank,
        "top_brand":    top_brand,
        "total_rows":   len(records),
    }


def _describe_run_changes(prev: dict, curr: dict) -> tuple[str, str]:
    """
    Compare two consecutive run metrics.
    Returns (summary_string, direction: "up"|"down"|"same").
    """
    parts: list[str] = []
    direction = "same"

    p_rate = prev["overall_rate"] or 0.0
    c_rate = curr["overall_rate"] or 0.0

    if c_rate > p_rate:
        parts.append(f"ACKO rate ↑ {p_rate}% → {c_rate}%")
        direction = "up"
    elif c_rate < p_rate:
        parts.append(f"ACKO rate ↓ {p_rate}% → {c_rate}%")
        direction = "down"

    p_rank = prev["acko_rank"]
    c_rank = curr["acko_rank"]

    if isinstance(p_rank, int) and isinstance(c_rank, int):
        if c_rank < p_rank:
            parts.append(f"Rank improved #{p_rank} → #{c_rank}")
            if direction == "same":
                direction = "up"
        elif c_rank > p_rank:
            parts.append(f"Rank dropped #{p_rank} → #{c_rank}")
            if direction == "same":
                direction = "down"
    elif p_rank is not None and c_rank is None:
        parts.append("ACKO disappeared from rankings")
        direction = "down"
    elif p_rank is None and c_rank is not None:
        parts.append(f"ACKO entered rankings at #{c_rank}")
        direction = "up"

    summary = "; ".join(parts) if parts else "No change"
    return summary, direction


# ---------------------------------------------------------------------------
# ACKO Visibility Summary
# ---------------------------------------------------------------------------

def update_acko_summary(spreadsheet, all_raw_data: list[dict]) -> None:
    ws = _ensure_tab(spreadsheet, TAB_NAMES["acko_summary"], ACKO_SUMMARY_HEADERS)
    ws.clear()
    ws.append_row(ACKO_SUMMARY_HEADERS)
    _fmt_header(ws, "1:1")

    def _rate(data: list[dict]) -> tuple[int, int, str]:
        if not data:
            return 0, 0, "0.0%"
        mentions = sum(1 for r in data if r.get("ACKO Mentioned (Y/N)") == "Yes")
        total    = len(data)
        pct      = round(mentions / total * 100, 1)
        return mentions, total, f"{pct}%"

    rows = []
    for i, prompt in enumerate(PROMPTS):
        pnum = i + 1
        gpt_rows = [r for r in all_raw_data if str(r.get("Prompt #")) == str(pnum) and r.get("Platform") == "ChatGPT"]
        goo_rows = [r for r in all_raw_data if str(r.get("Prompt #")) == str(pnum) and r.get("Platform") == "Google AI Mode"]

        gm, gt, gr = _rate(gpt_rows)
        oom, oot, oor = _rate(goo_rows)

        all_rows_p = gpt_rows + goo_rows
        overall_m = gm + oom
        overall_t = gt + oot
        overall_r = f"{round(overall_m / overall_t * 100, 1)}%" if overall_t else "0.0%"

        rows.append([pnum, prompt[:120], gm, gt, gr, oom, oot, oor, overall_r])

    if rows:
        ws.append_rows(rows, value_input_option="RAW")
        # Alternating row colors (data starts at row 2)
        _fmt_alt_rows(ws, start_row=2, end_row=len(rows) + 1, num_cols=len(ACKO_SUMMARY_HEADERS))

    try:
        ws.freeze(rows=1)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Brand Leaderboard
# ---------------------------------------------------------------------------

def _compute_brand_counts(all_raw_data: list[dict]) -> dict[str, int]:
    """Count total mentions of each tracked brand across all records."""
    counts: dict[str, int] = {b: 0 for b in TRACKED_BRANDS}
    for record in all_raw_data:
        brands_str = record.get("All Brands Mentioned", "") or ""
        brands_in_row = {b.strip() for b in brands_str.split(",") if b.strip()}
        for brand in brands_in_row:
            if brand in counts:
                counts[brand] += 1
    return counts


def _compute_prompt_coverage(all_raw_data: list[dict]) -> dict[str, set]:
    """Return {brand: set_of_prompt_numbers} showing which prompts each brand appeared in."""
    coverage: dict[str, set] = {b: set() for b in TRACKED_BRANDS}
    for record in all_raw_data:
        brands_str = record.get("All Brands Mentioned", "") or ""
        pnum = record.get("Prompt #", 0)
        for brand_token in brands_str.split(","):
            brand = brand_token.strip()
            if brand in coverage:
                coverage[brand].add(pnum)
    return coverage


def update_brand_leaderboard(
    spreadsheet,
    all_raw_data: list[dict],
    prev_brand_counts: dict[str, int] | None = None,
) -> None:
    ws = _ensure_tab(spreadsheet, TAB_NAMES["leaderboard"], LEADERBOARD_HEADERS)
    ws.clear()
    ws.append_row(LEADERBOARD_HEADERS)
    _fmt_header(ws, "1:1")

    curr_counts  = _compute_brand_counts(all_raw_data)
    prompt_cover = _compute_prompt_coverage(all_raw_data)
    total_prompts = len(PROMPTS)

    sorted_brands = sorted(curr_counts.items(), key=lambda x: x[1], reverse=True)

    rows = []
    acko_sheet_row = None
    for rank, (brand, count) in enumerate(sorted_brands, 1):
        pct = round(len(prompt_cover.get(brand, set())) / total_prompts * 100, 1)
        trend = "—"
        if prev_brand_counts:
            prev = prev_brand_counts.get(brand, 0)
            if count > prev:
                trend = "Up ↑"
            elif count < prev:
                trend = "Down ↓"
            else:
                trend = "Same"
        rows.append([rank, brand, count, f"{pct}%", trend])
        if brand == "ACKO":
            acko_sheet_row = rank + 1  # +1 for header

    if rows:
        ws.append_rows(rows, value_input_option="RAW")
        # Alternating row shading
        _fmt_alt_rows(ws, start_row=2, end_row=len(rows) + 1, num_cols=len(LEADERBOARD_HEADERS))

    # Highlight ACKO row in amber (overrides alternating)
    if acko_sheet_row is not None:
        _safe_format(ws, f"A{acko_sheet_row}:E{acko_sheet_row}", {
            "backgroundColor": _C_ACKO_AMBER,
            "textFormat": {"bold": True},
        })

    # Color-code Trend column: green for Up, red for Down
    for i, (_, _, _, _, trend) in enumerate(rows):
        row_num = i + 2  # +1 header, +1 for 1-index
        if trend == "Up ↑":
            _safe_format(ws, f"E{row_num}", {"backgroundColor": _C_GREEN_BG})
        elif trend == "Down ↓":
            _safe_format(ws, f"E{row_num}", {"backgroundColor": _C_RED_BG})

    try:
        ws.freeze(rows=1)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Change Log
# ---------------------------------------------------------------------------

def update_change_log(spreadsheet, change_rows: list[list]) -> None:
    if not change_rows:
        return
    ws = _ensure_tab(spreadsheet, TAB_NAMES["change_log"], CHANGE_LOG_HEADERS)
    # Format the header row every time so newly-created tabs look good
    all_vals = ws.get_all_values()
    if all_vals:
        _fmt_header(ws, "1:1")
    ws.append_rows(change_rows, value_input_option="RAW")
    logger.info("Appended %d row(s) to Change Log.", len(change_rows))


# ---------------------------------------------------------------------------
# Dashboard — run-over-run comparison
# ---------------------------------------------------------------------------

def update_dashboard(
    spreadsheet,
    run_summary: dict,
    all_raw_data: list[dict],
) -> None:
    ws = _ensure_tab(spreadsheet, TAB_NAMES["dashboard"], [])
    ws.clear()

    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # ── Compute per-run metrics ──────────────────────────────────────────────
    run_groups  = _group_by_run(all_raw_data)
    run_metrics = [
        _compute_run_metrics(ts, records, i + 1)
        for i, (ts, records) in enumerate(run_groups)
    ]

    # Annotate each run with change vs previous
    for i, m in enumerate(run_metrics):
        if i == 0:
            m["change_summary"] = "Baseline run"
            m["direction"]      = "same"
        else:
            m["change_summary"], m["direction"] = _describe_run_changes(run_metrics[i - 1], m)

    # ── Current-status metrics (all-time) ───────────────────────────────────
    total_records = len(all_raw_data)
    acko_yes      = sum(1 for r in all_raw_data if r.get("ACKO Mentioned (Y/N)") == "Yes")
    acko_rate_all = round(acko_yes / total_records * 100, 1) if total_records else 0.0

    curr_counts   = _compute_brand_counts(all_raw_data)
    sorted_all    = sorted(curr_counts.items(), key=lambda x: x[1], reverse=True)
    all_brand_names = [b for b, _ in sorted_all]
    acko_rank_all = (all_brand_names.index("ACKO") + 1) if "ACKO" in all_brand_names else "N/A"
    top3_competitors = [b for b, c in sorted_all if b != "ACKO" and c > 0][:3]

    latest = run_metrics[-1] if run_metrics else None

    # ── Build sheet content ──────────────────────────────────────────────────
    blocks: list[list] = []

    # Row 1: Title
    blocks.append(["ACKO BRAND VISIBILITY TRACKER — DASHBOARD"])
    # Row 2: Updated timestamp
    blocks.append([f"Last updated: {now_str}"])
    blocks.append([""])

    # Section: Current Status
    blocks.append(["CURRENT STATUS"])
    blocks.append(["Metric", "Value"])
    blocks.append(["As of date",                 now_str[:10]])
    blocks.append(["Total runs logged",           len(run_metrics)])
    blocks.append(["Total data rows",             total_records])
    blocks.append(["ACKO overall mention rate",   f"{acko_rate_all}%"])
    blocks.append(["ACKO rank (all-time)",        acko_rank_all if acko_rank_all != "N/A" else "Not ranked"])
    blocks.append(["Top 3 competitors",           ", ".join(top3_competitors) if top3_competitors else "N/A"])
    if latest:
        blocks.append(["Latest run date",         latest["date"]])
        blocks.append(["Latest run platforms",    latest["platforms"]])
        lr_gpt = f"{latest['chatgpt_rate']}%" if latest["chatgpt_rate"] is not None else "N/A"
        lr_gem = f"{latest['gemini_rate']}%"  if latest["gemini_rate"]  is not None else "N/A"
        blocks.append(["Latest ChatGPT ACKO rate", lr_gpt])
        blocks.append(["Latest Gemini ACKO rate",  lr_gem])
    blocks.append([""])

    # Section: Run-over-run comparison
    if run_metrics:
        blocks.append(["RUN-OVER-RUN COMPARISON"])
        run_header = [
            "Run #", "Date", "Platforms",
            "ChatGPT ACKO%", "Gemini ACKO%", "Overall ACKO%",
            "ACKO Rank", "Top Brand", "vs Previous Run",
        ]
        blocks.append(run_header)

        for m in run_metrics:
            gpt_str  = f"{m['chatgpt_rate']}%" if m["chatgpt_rate"]  is not None else "N/A"
            gem_str  = f"{m['gemini_rate']}%"  if m["gemini_rate"]   is not None else "N/A"
            ovr_str  = f"{m['overall_rate']}%" if m["overall_rate"]  is not None else "N/A"
            rank_str = f"#{m['acko_rank']}"    if m["acko_rank"]     is not None else "Not ranked"
            blocks.append([
                m["run_num"],
                m["date"],
                m["platforms"],
                gpt_str,
                gem_str,
                ovr_str,
                rank_str,
                m["top_brand"],
                m["change_summary"],
            ])

    blocks.append([""])

    # Section: Top 10 brand counts (all-time)
    blocks.append(["ALL-TIME BRAND MENTION COUNTS (TOP 10)"])
    blocks.append(["Rank", "Brand", "Total Mentions"])
    for rank, (brand, count) in enumerate(sorted_all[:10], 1):
        blocks.append([rank, brand, count])

    # ── Write to sheet ───────────────────────────────────────────────────────
    ws.update(range_name="A1", values=blocks)

    # ── Apply formatting ─────────────────────────────────────────────────────

    # Row 1: Title bar (dark navy, large bold white text)
    _safe_format(ws, "A1:I1", {
        "backgroundColor": _C_TITLE_BG,
        "textFormat": {
            "bold": True,
            "foregroundColor": _C_HEADER_FG,
            "fontSize": 13,
        },
    })

    # Row 2: subtitle
    _safe_format(ws, "A2:I2", {
        "backgroundColor": {"red": 0.18, "green": 0.33, "blue": 0.60},
        "textFormat": {"foregroundColor": _C_HEADER_FG, "fontSize": 10},
    })

    # Locate key rows by scanning blocks content
    row_map: dict[str, int] = {}
    for i, row in enumerate(blocks, 1):
        if row and row[0] in (
            "CURRENT STATUS", "Metric", "RUN-OVER-RUN COMPARISON",
            "Run #", "ALL-TIME BRAND MENTION COUNTS (TOP 10)", "Rank",
        ):
            row_map[str(row[0])] = i

    # Section header rows
    for key in ("CURRENT STATUS", "RUN-OVER-RUN COMPARISON", "ALL-TIME BRAND MENTION COUNTS (TOP 10)"):
        if key in row_map:
            r = row_map[key]
            _fmt_section(ws, f"A{r}:I{r}")

    # Column-header rows within each section
    for key in ("Metric", "Run #", "Rank"):
        if key in row_map:
            r = row_map[key]
            _fmt_header(ws, f"A{r}:I{r}")

    # Color-code run rows by direction
    if "Run #" in row_map:
        run_header_row = row_map["Run #"]
        for idx, m in enumerate(run_metrics):
            data_row = run_header_row + 1 + idx
            if m["direction"] == "up":
                _safe_format(ws, f"A{data_row}:I{data_row}", {"backgroundColor": _C_GREEN_BG})
            elif m["direction"] == "down":
                _safe_format(ws, f"A{data_row}:I{data_row}", {"backgroundColor": _C_RED_BG})
            else:
                _safe_format(ws, f"A{data_row}:I{data_row}", {"backgroundColor": _C_ALT_ROW})

    # Highlight the "Rank" section: amber for ACKO row
    if "Rank" in row_map:
        brand_header_row = row_map["Rank"]
        for idx, (brand, _) in enumerate(sorted_all[:10]):
            if brand == "ACKO":
                acko_r = brand_header_row + 1 + idx
                _safe_format(ws, f"A{acko_r}:C{acko_r}", {
                    "backgroundColor": _C_ACKO_AMBER,
                    "textFormat": {"bold": True},
                })
                break

    # Freeze top 3 rows (title + subtitle + spacer)
    try:
        ws.freeze(rows=2)
    except Exception:
        pass

    # Widen column A for labels
    try:
        ws.set_column_width(0, 280)   # column A
    except Exception:
        pass
