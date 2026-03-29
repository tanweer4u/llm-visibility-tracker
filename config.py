"""
config.py
=========
Central configuration: prompts, brand list, search patterns, keywords, and sheet tab names.
"""

import re

# ---------------------------------------------------------------------------
# The 15 prompts to query on every run
# ---------------------------------------------------------------------------
PROMPTS = [
    "What are the best car insurance companies in India for a budget of ₹10,000?",
    "Which car insurance providers in India offer the best value for money right now?",
    "Top 5 car insurance companies in India with the highest claim settlement ratio?",
    "Which insurers are known for the fastest car insurance claim settlement in India?",
    "Compare ACKO, ICICI Lombard, and HDFC ERGO car insurance — which one should I choose?",
    "Which is better for car insurance in India: ACKO or Digit or Tata AIG?",
    "Policybazaar vs ACKO vs direct insurer websites — where should I buy car insurance?",
    "Which car insurance company is best for my 3-year-old hatchback in India?",
    "Suggest the best car insurance providers for a new car with full coverage and add-ons.",
    "Which insurers are ideal for low premium but good coverage for car insurance in India?",
    "Which car insurance companies offer the best zero depreciation and engine protection add-ons?",
    "Which insurers in India have the widest cashless garage network for car insurance?",
    "If I want to switch my car insurance provider, which companies should I consider in India?",
    "Which car insurance companies give the best renewal offers or NCB benefits?",
    "Which platform or insurer gives the cheapest comprehensive car insurance instantly in India?",
]

# ---------------------------------------------------------------------------
# Brands to track — in display order
# ---------------------------------------------------------------------------
TRACKED_BRANDS = [
    "ACKO",
    "ICICI Lombard",
    "HDFC ERGO",
    "Bajaj Allianz",
    "Tata AIG",
    "Digit Insurance",
    "New India Assurance",
    "Policybazaar",
    "Coverfox",
    "Reliance General",
    "Navi",
    "Go Digit",
    "SBI General",
    "Royal Sundaram",
    "Kotak Mahindra General",
]

# ---------------------------------------------------------------------------
# Regex search patterns per brand (case-insensitive).
# Includes common abbreviations and alternate spellings.
# ---------------------------------------------------------------------------
BRAND_SEARCH_PATTERNS = {
    "ACKO":                  re.compile(r'\bACKO\b', re.IGNORECASE),
    "ICICI Lombard":         re.compile(r'\bICICI\s*Lombard\b', re.IGNORECASE),
    "HDFC ERGO":             re.compile(r'\bHDFC\s*ERGO\b', re.IGNORECASE),
    "Bajaj Allianz":         re.compile(r'\bBajaj\s*Allianz\b', re.IGNORECASE),
    "Tata AIG":              re.compile(r'\bTata\s*AIG\b', re.IGNORECASE),
    "Digit Insurance":       re.compile(r'\bDigit\s*Insurance\b|\bGo\s*Digit\b|\bGoDigit\b', re.IGNORECASE),
    "New India Assurance":   re.compile(r'\bNew\s*India\s*Assurance\b|\bNew\s*India\b', re.IGNORECASE),
    "Policybazaar":          re.compile(r'\bPolicybazaar\b|\bPolicy\s*Bazaar\b', re.IGNORECASE),
    "Coverfox":              re.compile(r'\bCoverfox\b', re.IGNORECASE),
    "Reliance General":      re.compile(r'\bReliance\s*General\b', re.IGNORECASE),
    "Navi":                  re.compile(r'\bNavi\b(?!\s*Mumbai)', re.IGNORECASE),  # avoid "Navi Mumbai"
    "Go Digit":              re.compile(r'\bGo\s*Digit\b|\bGoDigit\b', re.IGNORECASE),
    "SBI General":           re.compile(r'\bSBI\s*General\b', re.IGNORECASE),
    "Royal Sundaram":        re.compile(r'\bRoyal\s*Sundaram\b', re.IGNORECASE),
    "Kotak Mahindra General": re.compile(r'\bKotak\s*Mahindra\s*General\b|\bKotak\s*General\b|\bKotak\s*Mahindra\b', re.IGNORECASE),
}

# Potential unlisted insurance brands to surface as "unlisted mentions"
KNOWN_UNLISTED_BRANDS = [
    "Oriental Insurance",
    "United India",
    "Star Health",
    "Chola MS",
    "Future Generali",
    "Shriram General",
    "Magma HDI",
    "Liberty General",
    "Iffco Tokio",
    "Bharti AXA",
    "Universal Sompo",
    "Raheja QBE",
    "Cholamandalam",
    "Care Health",
    "ManipalCigna",
    "Niva Bupa",
    "Zurich Kotak",
]

# ---------------------------------------------------------------------------
# Sentiment keywords
# ---------------------------------------------------------------------------
POSITIVE_KEYWORDS = [
    "best", "excellent", "great", "good", "recommend", "recommended", "top",
    "leading", "affordable", "cheap", "value", "fast", "quick", "reliable",
    "trusted", "popular", "winner", "better", "superior", "outstanding",
    "ideal", "perfect", "impressive", "highly rated", "well-rated",
    "5-star", "4-star", "hassle-free", "convenient", "easy",
]

NEGATIVE_KEYWORDS = [
    "worst", "bad", "poor", "expensive", "costly", "slow", "unreliable",
    "avoid", "complaint", "issue", "problem", "difficult", "complicated",
    "hidden", "overpriced", "not recommended", "disappointing", "inferior",
    "reject", "denied", "fraud", "scam",
]

# ---------------------------------------------------------------------------
# Platforms
# ---------------------------------------------------------------------------
PLATFORMS = ["ChatGPT", "Gemini"]

# ---------------------------------------------------------------------------
# Google Sheet tab names
# ---------------------------------------------------------------------------
TAB_NAMES = {
    "raw_data":      "Raw Data",
    "acko_summary":  "ACKO Visibility Summary",
    "leaderboard":   "Brand Leaderboard",
    "change_log":    "Change Log",
    "dashboard":     "Dashboard",
}

# ---------------------------------------------------------------------------
# Column headers for each tab
# ---------------------------------------------------------------------------
RAW_DATA_HEADERS = [
    "Run Date (UTC)",
    "Prompt #",
    "Prompt Text",
    "Platform",
    "ACKO Mentioned (Y/N)",
    "ACKO Position",
    "ACKO Sentiment",
    "All Brands Mentioned",
    "Brand Count",
    "Unlisted Brands",
    "Change Detected (Y/N)",
    "Change Details",
    "Full Response Text",
    "Run Errors",
]

ACKO_SUMMARY_HEADERS = [
    "Prompt #",
    "Prompt Text",
    "ChatGPT — ACKO Mentions",
    "ChatGPT — Total Runs",
    "ChatGPT — Mention Rate (%)",
    "Google — ACKO Mentions",
    "Google — Total Runs",
    "Google — Mention Rate (%)",
    "Overall Mention Rate (%)",
]

LEADERBOARD_HEADERS = [
    "Rank",
    "Brand",
    "Total Mentions",
    "% of Prompts Mentioned",
    "Trend vs Previous Run",
]

CHANGE_LOG_HEADERS = [
    "Date",
    "Prompt #",
    "Prompt Text",
    "Platform",
    "What Changed",
]
