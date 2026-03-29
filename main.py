"""
main.py
=======
Orchestrates the ACKO Brand Visibility Tracker.

Usage
-----
  python main.py              # full run (15 prompts × all platforms)
  python main.py --self-test  # single-prompt smoke test (repeat up to 3×)

Self-diagnosis checklist (runs every time)
------------------------------------------
1. Verify all required environment variables are set
2. Ping each platform API — skip unavailable platforms, don't abort the run
3. Validate Google Sheet access and ensure all 5 tabs exist
4. After the run, validate row count matches expected
5. Write a run summary block to the Dashboard tab
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime

import brand_detector
import chatgpt_client
import google_client
import sheets_client
from config import PLATFORMS, PROMPTS

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)-8s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

FALLBACK_JSON = "run_output_fallback.json"

# ---------------------------------------------------------------------------
# Step 1 — Environment variable check
# ---------------------------------------------------------------------------
_REQUIRED_VARS = {
    "OPENAI_API_KEY":            "OpenAI API key (for ChatGPT)",
    "GEMINI_API_KEY":            "Gemini API key (for Google Gemini with Search grounding)",
    "GOOGLE_SHEETS_CREDENTIALS": "Google Sheets service account JSON",
    "SPREADSHEET_ID":            "Google Spreadsheet ID (from the sheet URL)",
}


def check_environment() -> bool:
    missing = [f"  • {k} — {v}" for k, v in _REQUIRED_VARS.items() if not os.environ.get(k, "").strip()]
    if not missing:
        logger.info("✓ All required environment variables are present.")
        return True

    logger.error("MISSING REQUIRED ENVIRONMENT VARIABLES:\n%s", "\n".join(missing))
    logger.error(
        "\nPlain English: Some API keys or credentials have not been set up.\n"
        "Please read the README section 'Step 6 — Add GitHub Secrets' and make sure\n"
        "every item listed above is saved as a secret in your GitHub repository.\n"
        "Stopping now — nothing will run until these are provided."
    )
    return False


# ---------------------------------------------------------------------------
# Step 2 — API connectivity tests
# ---------------------------------------------------------------------------

def test_apis() -> list[str]:
    """
    Test each platform API.  Return a list of platform names that are ready.
    Broken platforms are logged clearly but do not abort the run.
    """
    available: list[str] = []

    logger.info("Testing ChatGPT (OpenAI) API …")
    ok, msg = chatgpt_client.test_connection()
    if ok:
        logger.info("  ✓ ChatGPT: %s", msg)
        available.append("ChatGPT")
    else:
        logger.warning("  ✗ ChatGPT UNAVAILABLE — skipping for this run.\n    Reason: %s", msg)

    logger.info("Testing Google Search API …")
    ok, msg = google_client.test_connection()
    if ok:
        logger.info("  ✓ Google AI Mode: %s", msg)
        available.append("Google AI Mode")
    else:
        logger.warning("  ✗ Google AI Mode UNAVAILABLE — skipping for this run.\n    Reason: %s", msg)

    return available


# ---------------------------------------------------------------------------
# Step 3 — Google Sheet validation
# ---------------------------------------------------------------------------

def validate_sheet(auto_fixes: list[str]) -> tuple[bool, object | None]:
    logger.info("Connecting to Google Sheet …")
    ok, existing_tabs, spreadsheet = sheets_client.validate_sheet_access()

    if not ok:
        logger.error(
            "Cannot access Google Sheet.\n"
            "Plain English: The system could not open your Google Sheet. "
            "Here is what to check:\n"
            "  Step 1 — Open your Google Sheet in a browser.\n"
            "  Step 2 — Look at the URL — it looks like:\n"
            "            https://docs.google.com/spreadsheets/d/LONG_ID_HERE/edit\n"
            "  Step 3 — Copy the LONG_ID_HERE part.\n"
            "  Step 4 — Go to GitHub → your repo → Settings → Secrets and variables "
            "→ Actions → find SPREADSHEET_ID → click Update → paste the ID.\n"
            "  Step 5 — Make sure you shared the Google Sheet with your service account "
            "email address (it ends in @...iam.gserviceaccount.com) and gave it "
            "'Editor' access (just like sharing with a normal person)."
        )
        return False, None

    logger.info("  ✓ Sheet opened.  Existing tabs: %s", existing_tabs)

    logger.info("Ensuring all 5 required tabs exist …")
    created = sheets_client.ensure_tabs_exist(spreadsheet)
    if created:
        msg = f"Auto-fix: created missing tab(s): {', '.join(created)}"
        logger.info("  ✓ %s", msg)
        auto_fixes.append(msg)
    else:
        logger.info("  ✓ All tabs present.")

    return True, spreadsheet


# ---------------------------------------------------------------------------
# Core run
# ---------------------------------------------------------------------------

def run_tracker(test_mode: bool = False) -> bool:
    """
    Execute the full tracking pipeline.
    Returns True if data was written to Google Sheets, False otherwise.
    """
    run_ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    logger.info("=" * 65)
    logger.info("ACKO Brand Visibility Tracker — run started: %s", run_ts)
    logger.info("=" * 65)

    auto_fixes:  list[str] = []
    run_errors:  list[str] = []

    # ── Step 1: environment check ──
    logger.info("\n── STEP 1: Environment variables")
    if not check_environment():
        sys.exit(1)

    # ── Step 2: API tests ──
    logger.info("\n── STEP 2: API connectivity")
    available_platforms = test_apis()
    if not available_platforms:
        logger.error("No platforms are available.  Cannot run.  Stopping.")
        sys.exit(1)

    # ── Step 3: Sheet validation ──
    logger.info("\n── STEP 3: Google Sheet validation")
    sheet_ok, spreadsheet = validate_sheet(auto_fixes)
    if not sheet_ok:
        sys.exit(1)

    # ── Step 4: Load previous data for change detection ──
    logger.info("\n── STEP 4: Loading previous run data")
    prev_data = sheets_client.get_all_raw_data(spreadsheet)
    prev_brand_counts = sheets_client._compute_brand_counts(prev_data)
    if prev_data:
        logger.info("  Found %d existing record(s).", len(prev_data))
    else:
        logger.info("  No previous data — this appears to be the first run.")

    # ── Step 5: Query all prompts × platforms ──
    prompts_to_run = PROMPTS[:1] if test_mode else PROMPTS
    expected_rows  = len(prompts_to_run) * len(available_platforms)
    logger.info(
        "\n── STEP 5: Querying %d prompt(s) × %d platform(s) = %d expected row(s)",
        len(prompts_to_run), len(available_platforms), expected_rows,
    )

    new_raw_rows:    list[list] = []
    change_log_rows: list[list] = []

    for p_idx, prompt in enumerate(prompts_to_run):
        p_num = p_idx + 1
        logger.info("\n  [Prompt %d/%d] %s…", p_num, len(prompts_to_run), prompt[:70])

        for platform in available_platforms:
            error_msg    = ""
            response_txt = ""

            # — API call —
            try:
                if platform == "ChatGPT":
                    response_txt = chatgpt_client.get_chatgpt_response(prompt)
                else:
                    response_txt = google_client.get_google_ai_response(prompt)

                if not response_txt or not response_txt.strip():
                    response_txt = "Unexpected response format: empty string returned"
                    error_msg    = "Empty API response"
                    logger.warning("    [%s] Empty response.", platform)
                else:
                    logger.info("    [%s] ✓ %d chars received.", platform, len(response_txt))

            except Exception as exc:
                error_msg    = str(exc)
                response_txt = f"API call failed: {error_msg}"
                run_errors.append(f"Prompt {p_num}/{platform}: {error_msg}")
                logger.error("    [%s] ✗ Error: %s", platform, error_msg)

            # — Brand analysis —
            try:
                analysis = brand_detector.analyze_response(response_txt)
            except Exception as exc:
                logger.error("    Brand analysis error: %s", exc)
                analysis = {
                    "acko_mentioned":  "No",
                    "acko_position":   "Error during analysis",
                    "acko_sentiment":  "Error",
                    "brands_mentioned": [],
                    "brand_count":     0,
                    "unlisted_brands": [],
                }

            # — Change detection —
            previous = sheets_client.get_previous_run_data_from_list(prev_data, p_num, platform)
            change_flag, change_detail = sheets_client.detect_changes(analysis, previous)

            # — Build row —
            row = [
                run_ts,
                p_num,
                prompt,
                platform,
                analysis["acko_mentioned"],
                analysis["acko_position"],
                analysis["acko_sentiment"],
                ", ".join(analysis["brands_mentioned"]),
                analysis["brand_count"],
                ", ".join(analysis["unlisted_brands"]),
                change_flag,
                change_detail,
                response_txt[:5000],   # cap very long strings
                error_msg,
            ]
            new_raw_rows.append(row)

            if change_flag == "Yes":
                change_log_rows.append([
                    run_ts, p_num, prompt[:100], platform, change_detail
                ])

            # Brief pause between API calls to be a good citizen
            time.sleep(0.5)

    # ── Step 6: Row count validation ──
    actual_rows = len(new_raw_rows)
    if actual_rows != expected_rows:
        warn = (
            f"Row count mismatch: expected {expected_rows}, got {actual_rows}. "
            "Some API calls may have been skipped due to errors."
        )
        logger.warning("  ⚠ %s", warn)
        run_errors.append(warn)
        # Log mismatch to Change Log
        change_log_rows.append([
            run_ts, "N/A", "DATA VALIDATION", "ALL PLATFORMS", warn
        ])
    else:
        logger.info("\n  ✓ Row count matches expected (%d).", actual_rows)

    # ── Step 7: Write to Google Sheets ──
    logger.info("\n── STEP 7: Writing to Google Sheets")
    sheet_write_ok = False

    try:
        sheets_client.append_raw_data(spreadsheet, new_raw_rows)
        sheets_client.update_change_log(spreadsheet, change_log_rows)

        # Pull combined data (old + new) for summary recalculations
        all_data = sheets_client.get_all_raw_data(spreadsheet)

        sheets_client.update_acko_summary(spreadsheet, all_data)
        logger.info("  ✓ ACKO Visibility Summary updated.")

        sheets_client.update_brand_leaderboard(spreadsheet, all_data, prev_brand_counts)
        logger.info("  ✓ Brand Leaderboard updated.")

        run_summary = {
            "timestamp":     run_ts,
            "total_prompts": len(prompts_to_run),
            "errors":        len(run_errors),
            "platforms":     ", ".join(available_platforms),
            "auto_fixes":    "; ".join(auto_fixes) if auto_fixes else "None",
        }
        sheets_client.update_dashboard(spreadsheet, run_summary, all_data)
        logger.info("  ✓ Dashboard updated.")

        sheet_write_ok = True

    except Exception as exc:
        logger.error("  ✗ Failed to write to Google Sheets: %s", exc)
        logger.error("  Saving fallback JSON to %s …", FALLBACK_JSON)

        fallback = {
            "run_timestamp":  run_ts,
            "auto_fixes":     auto_fixes,
            "run_errors":     run_errors,
            "rows":           new_raw_rows,
            "change_log":     change_log_rows,
        }
        try:
            with open(FALLBACK_JSON, "w", encoding="utf-8") as fh:
                json.dump(fallback, fh, indent=2, default=str)
            logger.info("  Fallback saved.")
        except Exception as fe:
            logger.error("  Could not save fallback JSON either: %s", fe)

    # ── Final summary ──
    logger.info(
        "\n%s\nRUN COMPLETE\n"
        "  Timestamp         : %s\n"
        "  Rows processed    : %d / %d expected\n"
        "  Errors            : %d\n"
        "  Changes detected  : %d\n"
        "  Sheet updated     : %s\n"
        "  Auto-fixes        : %s\n%s",
        "=" * 65, run_ts,
        actual_rows, expected_rows,
        len(run_errors),
        len(change_log_rows),
        "Yes" if sheet_write_ok else "No — fallback JSON saved",
        "; ".join(auto_fixes) if auto_fixes else "None",
        "=" * 65,
    )

    if run_errors:
        logger.warning("Errors this run:\n%s", "\n".join(f"  • {e}" for e in run_errors))

    return sheet_write_ok


# ---------------------------------------------------------------------------
# Self-test mode (retries up to 3 times)
# ---------------------------------------------------------------------------

def self_test() -> bool:
    logger.info("=" * 65)
    logger.info("SELF-TEST MODE — verifying the full pipeline with 1 prompt")
    logger.info("=" * 65)

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        logger.info("\nSelf-test attempt %d / %d …", attempt, max_attempts)
        try:
            success = run_tracker(test_mode=True)
            if success:
                logger.info("SELF-TEST PASSED ✓  The pipeline is working correctly.")
                return True
            logger.warning("Attempt %d completed but Google Sheet write failed.", attempt)
        except SystemExit:
            logger.warning("Attempt %d exited early (environment or API error).", attempt)
        except Exception as exc:
            logger.error("Attempt %d raised an unexpected error: %s", attempt, exc)

        if attempt < max_attempts:
            logger.info("Waiting 5 seconds before next attempt …")
            time.sleep(5)

    logger.error(
        "\n%s\nSELF-TEST FAILED after %d attempts.\n\n"
        "Plain English — here is exactly what to check:\n\n"
        "  1. OPENAI_API_KEY\n"
        "     • Go to: https://platform.openai.com/api-keys\n"
        "     • Make sure at least one active API key is listed.\n"
        "     • If not, click 'Create new secret key', copy it (starts with sk-),\n"
        "       and paste it into your GitHub Secret named OPENAI_API_KEY.\n\n"
        "  2. GOOGLE_API_KEY + GOOGLE_CSE_ID\n"
        "     • Go to: https://console.cloud.google.com/\n"
        "     • Select your project → APIs & Services → Library\n"
        "     • Search for 'Custom Search API' and make sure it shows 'Enabled'.\n"
        "     • Then go to APIs & Services → Credentials to find your API key.\n"
        "     • Your CSE ID is at: https://programmablesearchengine.google.com/\n\n"
        "  3. GOOGLE_SHEETS_CREDENTIALS\n"
        "     • This should be the full text of your service-account JSON key file.\n"
        "     • Go to: https://console.cloud.google.com/ → IAM & Admin → Service Accounts\n"
        "     • Click your service account → Keys tab → Add Key → JSON → download it.\n"
        "     • Copy the entire file contents and paste into the GitHub Secret.\n\n"
        "  4. SPREADSHEET_ID\n"
        "     • Open your Google Sheet in a browser.\n"
        "     • The URL looks like: https://docs.google.com/spreadsheets/d/ID_HERE/edit\n"
        "     • Copy ID_HERE and paste it into the SPREADSHEET_ID GitHub Secret.\n"
        "     • Also: share the sheet with your service account email as 'Editor'.\n\n"
        "If you have checked all of the above and it still fails, open an issue on\n"
        "the GitHub repository and paste the error messages from the Actions log.\n"
        "%s",
        "=" * 65, max_attempts, "=" * 65,
    )
    return False


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ACKO Brand Visibility Tracker")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run a single-prompt smoke test (up to 3 retries) to verify the setup.",
    )
    args = parser.parse_args()

    if args.self_test:
        ok = self_test()
        sys.exit(0 if ok else 1)
    else:
        ok = run_tracker(test_mode=False)
        sys.exit(0 if ok else 1)
