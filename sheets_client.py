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
  Dashboard             — executive summary (written as values, not formulas)
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
# Tab bootstrap
# ---------------------------------------------------------------------------

def _safe_format(ws, range_str: str, fmt: dict) -> None:
    """Apply cell formatting; swallow errors so data writes are never blocked."""
    try:
        ws.format(range_str, fmt)
    except Exception as exc:
        logger.debug("Formatting skipped (%s): %s", range_str, exc)


def _ensure_tab(spreadsheet, title: str, headers: list[str]) -> gspread.Worksheet:
    """Return the worksheet with *title*, creating it (with headers) if absent."""
    try:
        ws = spreadsheet.worksheet(title)
        # If the tab exists but is completely empty, write headers
        if ws.row_count == 0 or not ws.get_all_values():
            if headers:
                ws.append_row(headers)
                _safe_format(ws, "1:1", {"textFormat": {"bold": True}})
        return ws
    except gspread.WorksheetNotFound:
        logger.warning("Tab '%s' not found — creating it now.", title)
        ws = spreadsheet.add_worksheet(title=title, rows=2000, cols=30)
        if headers:
            ws.append_row(headers)
            _safe_format(ws, "1:1", {"textFormat": {"bold": True}})
        time.sleep(1)   # brief pause to let the Sheets API settle
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
            # Tab exists — ensure headers are present
            ws = spreadsheet.worksheet(title)
            vals = ws.get_all_values()
            if not vals and headers:
                ws.append_row(headers)
                _safe_format(ws, "1:1", {"textFormat": {"bold": True}})

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


# ---------------------------------------------------------------------------
# Change detection helpers (operate on in-memory lists, no extra API calls)
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
    Compare *current_analysis* (from brand_detector) with *previous_record*
    (a dict from get_all_records).

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

    # Position change only when ACKO is present in both runs
    if prev_acko == "Yes" and curr_acko == "Yes":
        prev_pos = previous_record.get("ACKO Position", "")
        curr_pos = current_analysis["acko_position"]
        if prev_pos and curr_pos and prev_pos != curr_pos:
            changes.append(f"ACKO position changed: {prev_pos} → {curr_pos}")

    # Brand set changes
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
# ACKO Visibility Summary
# ---------------------------------------------------------------------------

def update_acko_summary(spreadsheet, all_raw_data: list[dict]) -> None:
    ws = _ensure_tab(spreadsheet, TAB_NAMES["acko_summary"], ACKO_SUMMARY_HEADERS)
    ws.clear()
    ws.append_row(ACKO_SUMMARY_HEADERS)
    _safe_format(ws, "1:1", {"textFormat": {"bold": True}})

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

        all_rows = gpt_rows + goo_rows
        overall_m = gm + oom
        overall_t = gt + oot
        overall_r = f"{round(overall_m / overall_t * 100, 1)}%" if overall_t else "0.0%"

        rows.append([pnum, prompt[:120], gm, gt, gr, oom, oot, oor, overall_r])

    if rows:
        ws.append_rows(rows, value_input_option="RAW")


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
    _safe_format(ws, "1:1", {"textFormat": {"bold": True}})

    curr_counts  = _compute_brand_counts(all_raw_data)
    prompt_cover = _compute_prompt_coverage(all_raw_data)
    total_prompts = len(PROMPTS)

    sorted_brands = sorted(curr_counts.items(), key=lambda x: x[1], reverse=True)

    rows = []
    acko_row_idx = None
    for rank, (brand, count) in enumerate(sorted_brands, 1):
        pct = round(len(prompt_cover.get(brand, set())) / total_prompts * 100, 1)
        trend = "Same"
        if prev_brand_counts:
            prev = prev_brand_counts.get(brand, 0)
            if count > prev:
                trend = "Up ↑"
            elif count < prev:
                trend = "Down ↓"
        rows.append([rank, brand, count, f"{pct}%", trend])
        if brand == "ACKO":
            acko_row_idx = rank  # 1-based; header is row 1, so data starts at row 2

    if rows:
        ws.append_rows(rows, value_input_option="RAW")

    # Highlight ACKO row in light amber
    if acko_row_idx is not None:
        sheet_row = acko_row_idx + 1  # +1 for header
        _safe_format(ws, f"A{sheet_row}:E{sheet_row}", {
            "backgroundColor": {"red": 1.0, "green": 0.93, "blue": 0.60}
        })


# ---------------------------------------------------------------------------
# Change Log
# ---------------------------------------------------------------------------

def update_change_log(spreadsheet, change_rows: list[list]) -> None:
    if not change_rows:
        return
    ws = _ensure_tab(spreadsheet, TAB_NAMES["change_log"], CHANGE_LOG_HEADERS)
    ws.append_rows(change_rows, value_input_option="RAW")
    logger.info("Appended %d row(s) to Change Log.", len(change_rows))


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def update_dashboard(
    spreadsheet,
    run_summary: dict,
    all_raw_data: list[dict],
) -> None:
    ws = _ensure_tab(spreadsheet, TAB_NAMES["dashboard"], [])
    ws.clear()

    total_records = len(all_raw_data)
    acko_yes      = sum(1 for r in all_raw_data if r.get("ACKO Mentioned (Y/N)") == "Yes")
    acko_rate     = round(acko_yes / total_records * 100, 1) if total_records else 0.0

    # Brand rank
    curr_counts   = _compute_brand_counts(all_raw_data)
    sorted_brands = sorted(curr_counts.items(), key=lambda x: x[1], reverse=True)
    brand_names   = [b for b, _ in sorted_brands]
    acko_rank     = (brand_names.index("ACKO") + 1) if "ACKO" in brand_names else "N/A"

    # Top 3 competitors (exclude ACKO)
    top3 = [b for b, c in sorted_brands if b != "ACKO" and c > 0][:3]

    # Prompts where ACKO was NEVER mentioned
    never_count = 0
    for i in range(len(PROMPTS)):
        pnum = i + 1
        p_records = [r for r in all_raw_data if str(r.get("Prompt #")) == str(pnum)]
        if p_records and all(r.get("ACKO Mentioned (Y/N)") == "No" for r in p_records):
            never_count += 1

    # Unique run dates (proxy for "total runs")
    unique_dates = len({str(r.get("Run Date (UTC)", ""))[:10] for r in all_raw_data})

    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    blocks: list[list] = [
        ["ACKO BRAND VISIBILITY TRACKER — EXECUTIVE DASHBOARD"],
        [f"Last updated: {now_str}"],
        [""],
        ["── THIS RUN ──────────────────────────────────────────"],
        ["Run timestamp",          run_summary.get("timestamp", "N/A")],
        ["Prompts processed",      run_summary.get("total_prompts", 0)],
        ["Errors encountered",     run_summary.get("errors", 0)],
        ["Platforms queried",      run_summary.get("platforms", "N/A")],
        ["Auto-fixes applied",     run_summary.get("auto_fixes", "None")],
        [""],
        ["── ALL-TIME KEY METRICS ──────────────────────────────"],
        ["Total run dates logged",          unique_dates],
        ["ACKO overall mention rate",       f"{acko_rate}%"],
        ["ACKO rank among all brands",      acko_rank],
        ["Top 3 competitors (by mentions)", ", ".join(top3) if top3 else "N/A"],
        ["Prompts where ACKO never mentioned", never_count],
        [""],
        ["── BRAND MENTION COUNTS (TOP 10) ─────────────────────"],
        ["Brand", "Total Mentions"],
    ]
    for brand, count in sorted_brands[:10]:
        blocks.append([brand, count])

    ws.update(range_name="A1", values=blocks)

    # Bold the title and section headers
    _safe_format(ws, "A1:B1", {
        "textFormat": {"bold": True, "fontSize": 14},
        "backgroundColor": {"red": 0.13, "green": 0.30, "blue": 0.65},
    })
    # Freeze top 2 rows
    try:
        ws.freeze(rows=2)
    except Exception:
        pass

    # Highlight ACKO row in brand table if present
    for idx, (brand, _) in enumerate(sorted_brands[:10]):
        if brand == "ACKO":
            row_num = len(blocks) - 10 + idx + 1  # approximate sheet row
            _safe_format(ws, f"A{row_num}:B{row_num}", {
                "backgroundColor": {"red": 1.0, "green": 0.93, "blue": 0.60}
            })
            break
