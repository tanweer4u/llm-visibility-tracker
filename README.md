# LLM Brand Visibility Tracker

An automated pipeline that tracks how often **ACKO** and 14 competitor brands appear in AI-generated responses from ChatGPT and Google AI Mode, across 15 high-intent car insurance queries in India.

Runs every 2 days on a schedule. Logs all data to a Google Sheets dashboard formatted for executive readability. No manual work required after setup.

Built to solve a real problem: most businesses have no affordable way to measure their LLM visibility. Commercial tools for this cost ₹50,000–₹2,00,000/month. This pipeline does the same job for under $10/month in API costs, using a Claude subscription you likely already have.

---

## What It Does

Every 2 days, the pipeline runs automatically and:

1. **Queries ChatGPT** via the OpenAI API with all 15 prompts and captures the full response
2. **Queries Google AI Mode** via the Google Custom Search API and extracts AI Overview snippets where available
3. **Detects brands** in every response, recording which brands appear, in what order, and with what sentiment
4. **Compares against the previous run** and flags any changes: new brands appearing, ACKO dropping out, position shifts
5. **Writes everything to Google Sheets** across 5 structured tabs, with the Dashboard tab formatted for C-Suite sharing
6. **Self-diagnoses** at the start of every run: validates API keys, checks Sheet structure, recreates missing tabs, and logs a run summary to the Dashboard

---

## Cost: Under $10/Month

| Component | Cost |
|-----------|------|
| OpenAI API (gpt-4o, 15 prompts every 2 days) | ~$1–3/month |
| Google Custom Search API | Free (100 queries/day free tier) |
| Google Sheets API | Free |
| GitHub Actions scheduling | Free (within free tier) |
| **Total** | **Under $10/month** |

Compare to commercial alternatives: Profound AI and Peec AI charge ₹50,000–₹2,00,000/month for equivalent LLM visibility tracking.

---

## Architecture

```
main.py (orchestrator)
|
+-- Phase 1: Pre-flight checks
|   +-- Validate all GitHub Secrets are present
|   +-- Ping OpenAI and Google APIs with test calls
|   +-- Verify Google Sheet exists and all 5 tabs are intact (recreate if missing)
|
+-- Phase 2: Query ChatGPT
|   +-- chatgpt_client.py sends all 15 prompts to gpt-4o, captures full responses
|
+-- Phase 3: Query Google AI Mode
|   +-- google_client.py calls Custom Search API, extracts AI Overview snippets
|
+-- Phase 4: Brand Detection
|   +-- brand_detector.py scans each response for 15 tracked brands + any unlisted brands
|       +-- Records position of first mention per brand
|       +-- Scores ACKO sentiment (Positive / Neutral / Negative) via keyword check
|       +-- Flags any brand not in the tracked list
|
+-- Phase 5: Change Detection
|   +-- sheets_client.py reads previous run data and diffs against current run
|       +-- Logs what changed: new brand appeared, ACKO dropped out, position shifted
|
+-- Phase 6: Write to Google Sheets
    +-- Tab 1 Raw Data: appends all rows from this run
    +-- Tab 2 ACKO Visibility Summary: updates mention rate per prompt
    +-- Tab 3 Brand Leaderboard: re-ranks all brands by total mentions + trend
    +-- Tab 4 Change Log: appends only rows where something changed
    +-- Tab 5 Dashboard: writes run summary block + key metrics for executive view
```

---

## Google Sheets Dashboard Structure

| Tab | What It Contains |
|-----|-----------------|
| **Raw Data** | Every data point from every run, appended as new rows |
| **ACKO Visibility Summary** | ACKO mention rate per prompt across all runs and platforms |
| **Brand Leaderboard** | All 15+ brands ranked by total mentions, with Up/Down/Same trend vs previous run |
| **Change Log** | Only the rows where something changed since the last run |
| **Dashboard** | Executive summary: ACKO overall mention rate, rank among competitors, top 3 rivals, run history |

The Dashboard tab is auto-formatted via the Sheets API: bold headers, colour-coded ACKO rows, frozen header rows, and a run summary block at the top showing timestamp, platforms queried, errors encountered, and any auto-fixes applied.

---

## The 15 Prompts Being Tracked

| # | Prompt |
|---|--------|
| 1 | What are the best car insurance companies in India for a budget of Rs 10,000? |
| 2 | Which car insurance providers in India offer the best value for money right now? |
| 3 | Top 5 car insurance companies in India with the highest claim settlement ratio? |
| 4 | Which insurers are known for the fastest car insurance claim settlement in India? |
| 5 | Compare ACKO, ICICI Lombard, and HDFC ERGO car insurance: which one should I choose? |
| 6 | Which is better for car insurance in India: ACKO or Digit or Tata AIG? |
| 7 | Policybazaar vs ACKO vs direct insurer websites: where should I buy car insurance? |
| 8 | Which car insurance company is best for my 3-year-old hatchback in India? |
| 9 | Suggest the best car insurance providers for a new car with full coverage and add-ons. |
| 10 | Which insurers are ideal for low premium but good coverage for car insurance in India? |
| 11 | Which car insurance companies offer the best zero depreciation and engine protection add-ons? |
| 12 | Which insurers in India have the widest cashless garage network for car insurance? |
| 13 | If I want to switch my car insurance provider, which companies should I consider in India? |
| 14 | Which car insurance companies give the best renewal offers or NCB benefits? |
| 15 | Which platform or insurer gives the cheapest comprehensive car insurance instantly in India? |

---

## Brands Being Tracked

ACKO · ICICI Lombard · HDFC ERGO · Bajaj Allianz · Tata AIG · Digit Insurance · New India Assurance · Policybazaar · Coverfox · Reliance General · Navi · Go Digit · SBI General · Royal Sundaram · Kotak Mahindra General

Any brand that appears in an AI response but is not in this list is automatically flagged as an unlisted brand and logged separately.

---

## Data Captured Per Run

For every prompt x platform combination:

| Field | Description |
|-------|-------------|
| Run Date & Time | Timestamp of the query |
| Platform | ChatGPT or Google AI Mode |
| ACKO Mentioned | Yes / No |
| ACKO Position | 1st mention, 2nd mention, not mentioned |
| ACKO Sentiment | Positive / Neutral / Negative |
| All Brands Mentioned | In order of first appearance |
| Brand Count | Total tracked brands in that response |
| Unlisted Brands | Any insurance brand not in the tracking list |
| Change Detected | Yes / No vs the previous run |
| Change Details | What specifically changed |
| Full Response Text | Complete AI-generated answer |

---

## Key Design Decisions

**Self-healing runs over fragile automation**
Every run starts with a pre-flight check that validates API connectivity and Sheet structure before any queries are made. If a tab is missing from the Sheet, it is recreated automatically. If one API is down, that platform is skipped for that run and the rest continues. The run never crashes completely because of a single failure.

**Change detection as the core signal**
Raw mention counts are useful but change detection is what a content team actually acts on. The pipeline diffs every response against the previous run for the same prompt and platform, so stakeholders see immediately when ACKO drops out of a response or a new competitor appears.

**Sentiment scoring without an extra LLM call**
Rather than making an additional API call for sentiment analysis, brand_detector.py uses a keyword dictionary approach: positive signals (recommended, best, top, leading), negative signals (expensive, complaint, slow, rejected), and neutral as the default. This keeps costs low and the logic fully auditable.

**Unlisted brand detection**
The pipeline does not only track the 15 defined brands. It also scans for any insurance-adjacent brand name it does not recognise and flags it. This surfaces emerging competitors or aggregators that were not on the radar when the tracker was first built.

**Dashboard formatted for non-technical stakeholders**
The Sheets API writes formatting directly: bold headers, frozen rows, ACKO rows highlighted, and a plain-English run summary at the top of the Dashboard tab. The goal is a sheet that can be shared with a CMO or CFO without any manual cleanup.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Orchestration | Python 3.12 |
| ChatGPT queries | OpenAI API (gpt-4o) |
| Google AI Mode queries | Google Custom Search JSON API |
| Brand detection | Python (regex + keyword dictionary) |
| Dashboard output | Google Sheets API v4 |
| Scheduling | GitHub Actions (cron, every 2 days) |
| Secrets management | GitHub Actions Secrets |

---

## Project Structure

```
acko-brand-tracker/
+-- main.py                    # Pipeline orchestrator
+-- chatgpt_client.py          # OpenAI API integration
+-- google_client.py           # Google Custom Search API integration
+-- sheets_client.py           # Google Sheets read/write + formatting
+-- brand_detector.py          # Brand detection, position, sentiment logic
+-- config.py                  # All 15 prompts and the brand tracking list
+-- requirements.txt           # Python dependencies
+-- .github/
|   +-- workflows/
|       +-- tracker.yml        # GitHub Actions schedule (every 2 days, 8 AM IST)
+-- README.md
```

---

## Setup Prerequisites

- Python 3.12+
- A GitHub account (free)
- An OpenAI account with API credit loaded ($5 covers months of use at this query volume)
- A Google Cloud project with the Custom Search API, Sheets API, and Drive API enabled
- A Google Sheet created in your Drive (blank is fine: the script builds all tabs on first run)

---

## Setup Guide

### Step 1: Get Your OpenAI API Key

1. Go to **https://platform.openai.com** and sign in
2. Click your profile icon (top right) and select **API keys**
3. Click **+ Create new secret key**, give it a name, and click **Create**
4. Copy the key immediately (starts with `sk-`): you cannot view it again after closing this screen
5. Add credits: click **Billing** in the left menu, then **Add payment method**

---

### Step 2: Get Your Google Custom Search API Key and Search Engine ID

**Create a Programmable Search Engine:**
1. Go to **https://programmablesearchengine.google.com** and click **Add**
2. Select **Search the entire web** and give it any name
3. After creation, copy the **Search Engine ID** shown on screen

**Enable the API and create a key:**
1. Go to **https://console.cloud.google.com**
2. Search for **Custom Search API** and click **Enable**
3. Go to **Credentials**, click **+ Create Credentials**, select **API Key**, and copy the key

---

### Step 3: Set Up Google Sheets Access via Service Account

1. In Google Cloud Console, enable the **Google Sheets API** and **Google Drive API**
2. Go to **Credentials**, click **+ Create Credentials**, and select **Service account**
3. Give it any name, click through, and click **Done**
4. Click the service account email, go to the **Keys** tab, click **Add Key**, select **JSON**, and download the file
5. Open your Google Sheet, click **Share**, paste the service account email address, and give it **Editor** access

---

### Step 4: Add GitHub Secrets

In your repository: **Settings** > **Secrets and variables** > **Actions** > **New repository secret**

| Secret Name | Value |
|-------------|-------|
| `OPENAI_API_KEY` | Your OpenAI key (starts with `sk-`) |
| `GOOGLE_API_KEY` | Your Google Custom Search API key |
| `GOOGLE_CSE_ID` | Your Search Engine ID |
| `GOOGLE_SHEETS_CREDENTIALS` | Full contents of the JSON file from Step 3 (open in Notepad, copy all, paste) |
| `GOOGLE_SHEET_ID` | The string between `/d/` and `/edit` in your Google Sheet URL |

---

### Step 5: Run It

```bash
# Clone the repo
git clone https://github.com/tanweer4u/acko-brand-tracker
cd acko-brand-tracker
pip install -r requirements.txt

# Set your API key locally for testing
export OPENAI_API_KEY=your_key_here

# Run the full pipeline
python main.py

# Run a single test prompt only (faster for initial setup check)
python main.py --test
```

Or trigger it manually from the **Actions** tab in GitHub: click the workflow and select **Run workflow**.

---

## What Happens If Something Breaks

The pipeline is designed to self-diagnose and recover. Before every run it checks API connectivity and Sheet structure. During every run, a failed API call is logged and skipped rather than crashing the whole job. After every run, a plain-English summary is written to the Dashboard tab.

**The two situations that require manual intervention:**

1. **API key expired or out of credit**: the Dashboard will show "401 Unauthorized". Generate a new key on the relevant platform and update the GitHub Secret.
2. **Google Sheet access revoked**: the Dashboard will show "403 Forbidden". Re-share the Sheet with the service account email and give it Editor access.

---

## Methodology and Limitations

**ChatGPT** responses are fetched via the OpenAI API using `gpt-4o`. These are fresh, real responses generated at query time, not cached.

**Google AI Mode** responses are fetched via the Google Custom Search JSON API. This returns AI Overview snippets when available, but the API does not guarantee an AI Overview for every query. When unavailable, the run logs "AI Overview not available" for that entry. This is a known tradeoff of the API-based approach vs full browser automation: it keeps costs near zero but means Google coverage is best-effort rather than guaranteed.

---

## Skills Demonstrated

- **Agentic pipeline design**: multi-phase orchestration with pre-flight checks, per-phase error handling, and a self-healing run loop
- **Multi-API integration**: OpenAI, Google Custom Search, Google Sheets, and Google Drive coordinated in a single automated workflow
- **Scheduled automation**: GitHub Actions cron job with manual trigger override, secrets management, and structured run logging
- **GEO/AEO measurement**: practical implementation of LLM brand visibility tracking, change detection, and sentiment scoring without expensive third-party tools
- **Stakeholder-ready output**: Google Sheets dashboard formatted programmatically for executive readability, including conditional formatting, frozen headers, and plain-English run summaries

---

## About

Built by **Tanveer** | Senior Content and SEO Leader with 12 years of experience in Indian fintech and insurance, including scaling organic traffic to 22M monthly visits at BankBazaar and leading GEO/AEO content strategy at ACKO Insurance.

Most businesses investing in GEO/AEO have no affordable way to measure whether their strategy is working inside AI responses. This project builds that measurement layer from scratch, adaptable to any brand, category, or set of queries. The insurance use case here is one implementation of a framework that works for any business tracking its LLM visibility without paying for expensive external tools.

**Connect:** [LinkedIn](https://www.linkedin.com/in/12195249/) · [GitHub](https://github.com/tanweer4u)
