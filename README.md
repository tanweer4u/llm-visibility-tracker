# ACKO Brand Visibility Tracker

Automatically tracks how often ACKO and 14 competitor brands appear in AI-generated responses from ChatGPT and Gemini, across 15 car insurance prompts. Runs every 2 days and logs everything to a Google Sheet.

---

## What You Will Need Before You Start

Go through this checklist before doing anything else. Each item has a link to sign up if you don't have it yet.

- [ ] A **Google account** (Gmail) — you almost certainly already have one
- [ ] An **OpenAI account** — sign up at https://platform.openai.com/signup (free to create; requires ~$5 credit to use GPT-4o)
- [ ] A **GitHub account** — free, sign up at https://github.com/signup (GitHub is the platform that stores your code and runs the automation)
- [ ] All the project files on your computer — they should be in a folder called `acko-brand-tracker`

---

## What This Project Does

Every 2 days, this tool automatically:

1. Asks 15 real questions about car insurance in India to **ChatGPT (GPT-4o)**
2. Asks the same 15 questions to **Google Gemini** (with live Google Search built in, so its answers reflect what's currently on the web)
3. Scans every response for mentions of ACKO and 14 other insurance brands
4. Records what changed since the last run (did ACKO appear? did a competitor drop out?)
5. Writes all data to a **Google Sheet** with 5 organised tabs, including an executive dashboard

You can also run it manually at any time — no waiting for the schedule.

---

## What Is GitHub Actions? (Read This First)

**GitHub** is a website that stores code. Think of it like Google Drive, but for code files.

**GitHub Actions** is a feature built into GitHub that can automatically run your Python script on a schedule — without you needing to open your computer or do anything. Here is how it works:

1. You store your project files on GitHub (a "repository")
2. One of those files — `.github/workflows/tracker.yml` — is a schedule file that tells GitHub: *"every 2 days at 8 AM, run main.py automatically"*
3. GitHub reads that file, spins up a temporary computer in the cloud, installs Python, runs your script, and then shuts down
4. You never have to touch anything — it just happens

The only setup you do once is: upload the files, add your API keys as Secrets, and click "Run" once to test it.

---

## Step 1 — Get Your OpenAI API Key

The OpenAI API key lets your script call ChatGPT.

1. Go to **https://platform.openai.com/api-keys**
2. Sign in with your OpenAI account
3. Click the button **"Create new secret key"** (blue button, may have a `+` symbol)
4. Give it a name — for example, `ACKO Tracker`
5. Click **Create**
6. You will see a long string starting with **`sk-`** — this is your API key
   - **Copy it immediately and save it somewhere safe** (a private note or password manager)
   - You will never be able to see it again after closing this window
7. Make sure billing is enabled:
   - Go to **https://platform.openai.com/account/billing**
   - Add a payment method and add at least $5 credit
   - GPT-4o costs roughly $0.005 per prompt — 15 prompts every 2 days is less than $1/month

---

## Step 2 — Get Your Gemini API Key (Free)

The Gemini API lets your script query Google's AI with live web search built in — the same technology behind Google AI Mode.

1. Go to **https://aistudio.google.com/app/apikey**
2. Sign in with your Google account
3. Click the blue **"Create API key"** button
4. In the dropdown, choose **"Create API key in new project"** (easiest option)
5. Your API key appears on screen — a long string of random letters and numbers
6. **Click the copy icon next to it** and save it somewhere safe

No billing needed. The free tier covers this tracker entirely:
- **Free limit:** 1,500 requests per day
- **This tracker uses:** ~8 requests per day
- **Your cost:** $0

---

## Step 3 — Set Up Google Sheets Access (Service Account)

A "service account" is like a robot Google account that your script uses to write data to your spreadsheet automatically. You create it once and never touch it again.

### Part A: Go to Google Cloud Console and Create a Project

1. Go to **https://console.cloud.google.com/**
2. Sign in with your Google account
3. At the very top of the page, click the project dropdown — it may say **"Select a project"** or show a project name
4. A window pops up. Click **"New Project"** (top right of the popup)
5. Under "Project name", type `acko-tracker` — then click **"Create"**
6. Wait a few seconds. When it finishes, click the notification or select the new project from the dropdown at the top

### Part B: Enable the Required APIs

You need to switch on two Google services for this project.

1. In the left sidebar, click **"APIs & Services"** → **"Library"**
2. In the search box, type `Google Sheets API`
3. Click the result, then click the blue **"Enable"** button
4. Go back to the Library (click the back arrow or click "Library" in the sidebar again)
5. Search for `Google Drive API`
6. Click the result, then click **"Enable"**

### Part C: Create a Service Account

1. In the left sidebar, click **"IAM & Admin"** → **"Service Accounts"**
2. Click **"+ Create Service Account"** at the top
3. Fill in:
   - **Service account name:** `acko-tracker`
   - The **Service account ID** fills in automatically — leave it as is
4. Click **"Create and Continue"**
5. On the next screen ("Grant this service account access"), click **"Continue"** — you can skip this
6. On the final screen, click **"Done"**

### Part D: Download the Key File

1. You will now see your service account listed. Click on its **email address** — it looks like `acko-tracker@acko-tracker-xxxxx.iam.gserviceaccount.com`
2. **Copy this email address** and save it — you will need it in Step 4
3. Click the **"Keys"** tab at the top of the page
4. Click **"Add Key"** → **"Create new key"**
5. Select **"JSON"** and click **"Create"**
6. A file downloads automatically to your computer — named something like `acko-tracker-abc123.json`
7. Open this file with **Notepad** (Windows) or **TextEdit** (Mac)
   - It looks like a wall of text starting with `{` and ending with `}`
8. Press **Ctrl+A** (Windows) or **Cmd+A** (Mac) to select everything, then **Ctrl+C** / **Cmd+C** to copy it
9. **Save this copied text** — you will paste it into GitHub in Step 6

---

## Step 4 — Create and Share Your Google Sheet

1. Go to **https://sheets.google.com**
2. Click the large **"+"** button to create a new blank spreadsheet
3. Click "Untitled spreadsheet" at the top and rename it to `ACKO Brand Visibility Tracker`
4. Look at the URL in your browser — it looks like this:
   ```
   https://docs.google.com/spreadsheets/d/LONG_ID_HERE/edit
   ```
   **Copy the `LONG_ID_HERE` part** — this is your Spreadsheet ID (save it safely)
5. Click the **"Share"** button (blue button, top right)
6. In the **"Add people and groups"** box, paste the service account email you copied in Step 3 Part D
7. Make sure the permission dropdown shows **"Editor"**
8. Click **"Send"** — if it warns that no email will be sent, that is fine, click OK

The script will automatically create all 5 tabs the first time it runs. You do not need to create them manually.

---

## Step 5 — Create a GitHub Repository and Upload the Files

### Part A: Create a GitHub Account (if you don't have one)

1. Go to **https://github.com/signup**
2. Enter your email, create a password, and choose a username
3. Verify your email address when GitHub sends you a confirmation email
4. On the "Welcome" screen, you can skip the personalisation questions — just click "Skip personalisation" or "Continue"

### Part B: Create a New Repository

A repository is a folder on GitHub that holds all your project files.

1. Once logged in, click the **"+"** icon in the top right corner of GitHub
2. Click **"New repository"**
3. Fill in:
   - **Repository name:** `acko-brand-tracker`
   - **Description:** (optional) `ACKO brand visibility tracker`
   - **Visibility:** Select **"Private"** — this keeps your code and file structure private
4. **Do not tick** any of the initialisation checkboxes (no README, no .gitignore, no licence)
5. Click the green **"Create repository"** button

You will land on an empty repository page.

### Part C: Upload the Main Project Files

1. On the empty repository page, click the link that says **"uploading an existing file"**
   - If you don't see it, click **"Add file"** → **"Upload files"**
2. Open the `acko-brand-tracker` folder on your computer
3. Select and drag these 7 files into the upload area on GitHub:
   - `main.py`
   - `config.py`
   - `brand_detector.py`
   - `chatgpt_client.py`
   - `google_client.py`
   - `sheets_client.py`
   - `requirements.txt`
   - `README.md`
4. At the bottom of the page, leave the commit message as is and click **"Commit changes"**

### Part D: Upload the Workflow File (This Is the Key Step for Automation)

The file `.github/workflows/tracker.yml` is what tells GitHub Actions to run your script automatically. It must be placed in a specific folder path — you cannot just drag and drop it like the others.

1. On your repository page, click **"Add file"** → **"Create new file"**
2. In the filename box at the top, type exactly:
   ```
   .github/workflows/tracker.yml
   ```
   As you type the `/` characters, GitHub will automatically create the folder structure — you will see `.github /` and `workflows /` appear as folder "breadcrumbs" above the box. This is correct.
3. Now open the `tracker.yml` file from your computer with Notepad (Windows) or TextEdit (Mac)
4. Select all the text (**Ctrl+A** then **Ctrl+C** on Windows, or **Cmd+A** then **Cmd+C** on Mac)
5. Click inside the large text area on GitHub and paste (**Ctrl+V** or **Cmd+V**)
6. Scroll down and click **"Commit new file"**

### Part E: Verify the Upload Worked

1. Click the **"Actions"** tab in the top navigation bar of your repository
2. You should see a workflow listed called **"ACKO Brand Visibility Tracker"**
   - If you see it: ✓ the workflow file was uploaded correctly
   - If the Actions tab says "Get started with GitHub Actions" with no workflow listed: the `.github/workflows/tracker.yml` file was not uploaded correctly — go back to Part D and try again

---

## Step 6 — Add Your API Keys as GitHub Secrets

GitHub Secrets store your API keys safely. They are encrypted and never visible in your code or run logs — not even to you after you save them.

1. Go to your repository page on GitHub
2. Click **"Settings"** in the top navigation bar (last item, with a gear icon)
3. In the left sidebar, scroll down to **"Security"** and click **"Secrets and variables"**
4. Click **"Actions"** in the submenu
5. You will see a section called **"Repository secrets"** — click the green **"New repository secret"** button

Add each of the following secrets one at a time:

| Secret Name | What to paste | Where you got it |
|---|---|---|
| `OPENAI_API_KEY` | Your OpenAI key (starts with `sk-`) | Step 1 |
| `GEMINI_API_KEY` | Your Gemini API key | Step 2 |
| `GOOGLE_SHEETS_CREDENTIALS` | The entire contents of your JSON key file | Step 3 Part D |
| `SPREADSHEET_ID` | The long ID from your Google Sheet URL | Step 4 |

For each secret:
1. Click **"New repository secret"**
2. In the **"Name"** box, type the secret name exactly as shown above — capital letters, underscores, no spaces
3. In the **"Secret"** box, paste the value
4. Click **"Add secret"**

When done, you should see all 4 secrets listed under "Repository secrets".

---

## Step 7 — Run It for the First Time

Before the automation runs on its own schedule, do a manual test to confirm everything is connected correctly.

1. Go to your repository on GitHub
2. Click the **"Actions"** tab
3. In the left sidebar, click **"ACKO Brand Visibility Tracker"**
4. On the right side, click the grey **"Run workflow"** button
5. A small dropdown appears. You will see:
   - A branch selector (leave it as `main`)
   - **"Run in self-test mode?"** — change this to `true`
6. Click the green **"Run workflow"** button
7. The page will refresh and show a new run with a **yellow circle** (meaning it is running)
8. Click on the run to watch it live
9. It takes 1–2 minutes. When it finishes:
   - **Green tick (✓)** = everything worked
   - **Red X (✗)** = something failed — click on the failed step to see the error message, then check "Common Problems" below

### What to check after a successful test run

Open your Google Sheet. You should now see:
- A tab called **"Raw Data"** with 2 rows of data (1 prompt tested on 2 platforms)
- A tab called **"Dashboard"** with a run summary at the top
- Tabs called "ACKO Visibility Summary", "Brand Leaderboard", and "Change Log" (they may be empty or have headers only — that is normal at this stage)

If you see this, your setup is complete. The full 15-prompt run will happen automatically every 2 days.

---

## How to Check If Your Automation Is Running

1. Go to your GitHub repository
2. Click the **"Actions"** tab
3. You will see a list of every run — scheduled and manual. Each has:
   - **Green tick (✓)** — completed successfully
   - **Red X (✗)** — failed; click to see what went wrong
   - **Yellow circle** — currently running
4. Click any run, then click the **"track-visibility"** job inside it
5. Click **"Run brand visibility tracker"** to expand the full log
6. A successful run ends with something like:
   ```
   ═════════════════════════════════════════════════════════════════
   RUN COMPLETE
     Timestamp         : 2026-04-01 02:31:00 UTC
     Rows processed    : 30 / 30 expected
     Errors            : 0
     Changes detected  : 3
     Sheet updated     : Yes
     Auto-fixes        : None
   ═════════════════════════════════════════════════════════════════
   ```

**When does it run automatically?**
Every 2 days at approximately 8:00 AM India Standard Time (2:30 AM UTC). GitHub may delay scheduled runs by up to 15 minutes during busy periods — this is normal.

---

## How to Read the Dashboard

Open your Google Sheet and click the **"Dashboard"** tab.

- **THIS RUN** — when the last run happened, how many prompts were processed, errors, and whether any auto-fixes were applied
- **ALL-TIME KEY METRICS:**
  - **ACKO overall mention rate** — across all runs and platforms, what % of responses mentioned ACKO
  - **ACKO rank among all brands** — rank 1 = most mentioned; rank 5 = 4 brands mentioned more often
  - **Top 3 competitors** — the brands appearing most often across all responses (excluding ACKO)
  - **Prompts where ACKO never mentioned** — how many of the 15 prompts have produced zero ACKO mentions across all runs
- **BRAND MENTION COUNTS (TOP 10)** — quick leaderboard; ACKO's row is highlighted in amber

Other tabs:
- **Raw Data** — every single data point, every run, every platform
- **ACKO Visibility Summary** — per-prompt ACKO mention rates broken down by platform
- **Brand Leaderboard** — all 15 brands ranked by total mentions, with trend arrows
- **Change Log** — only rows where something changed vs the prior run

---

## What Happens If Something Breaks?

The system is built to recover automatically from the most common problems.

**If one API call fails mid-run:**
The error is logged and the script moves on to the next prompt. One failure never stops the rest of the run. The error message appears in the "Run Errors" column of the Raw Data tab.

**If a Google Sheet tab is accidentally deleted:**
The script detects this at the start of the next run and recreates the missing tab with the correct headers automatically.

**If Google Sheets is completely unreachable:**
The script saves all the data to a file called `run_output_fallback.json`. You can download this from the "Artifacts" section at the bottom of the Actions run page — it stays available for 30 days.

**The run summary on the Dashboard tab tells you:**
- How many errors occurred
- Which platforms were queried
- Whether any automatic fixes were applied that run

**The only two situations where you need to step in manually:**

1. **An API key expired or ran out of credit** — the system cannot renew keys for you. See Common Problems below.
2. **The Google Sheet was deleted or your service account lost Editor access** — re-share the sheet from Step 4, or create a new one.

---

## Common Problems

### Problem 1: "401 Unauthorized" or "invalid_api_key" for ChatGPT

**What it means:** Your OpenAI API key is wrong or has expired.

**How to fix it:**
1. Go to **https://platform.openai.com/api-keys**
2. Check if your key is listed and active
3. If not, click **"Create new secret key"**, copy the new key (starts with `sk-`)
4. Go to GitHub → your repo → Settings → Secrets and variables → Actions
5. Find **OPENAI_API_KEY**, click **"Update"**, paste the new key, click **"Update secret"**

### Problem 2: "Invalid API key" or "API_KEY_INVALID" for Gemini

**What it means:** Your Gemini API key is wrong or has been deleted.

**How to fix it:**
1. Go to **https://aistudio.google.com/app/apikey**
2. Check if your key is listed — if so, copy it again
3. If missing, click **"Create API key"** to generate a new one
4. Go to GitHub → your repo → Settings → Secrets and variables → Actions
5. Find **GEMINI_API_KEY**, click **"Update"**, paste the new key, click **"Update secret"**

### Problem 3: "GOOGLE_SHEETS_CREDENTIALS is not valid JSON"

**What it means:** The service account key file was pasted incompletely or got garbled.

**How to fix it:**
1. Find the JSON file you downloaded in Step 3 Part D (named something like `acko-tracker-abc123.json`)
2. Open it with Notepad (Windows) or TextEdit (Mac)
3. Press **Ctrl+A** then **Ctrl+C** (Windows) or **Cmd+A** then **Cmd+C** (Mac) to copy everything
4. Go to GitHub → Settings → Secrets → find **GOOGLE_SHEETS_CREDENTIALS** → click **"Update"**
5. Click inside the secret box, press **Ctrl+A** to select everything already there, then paste with **Ctrl+V**
6. Click **"Update secret"**

### Problem 4: The run completes but the Google Sheet is empty

**What it means:** The script cannot find your spreadsheet. Either the ID is wrong, or the service account was not given Editor access.

**How to fix it:**
1. Open your Google Sheet in a browser
2. Look at the URL: `https://docs.google.com/spreadsheets/d/THIS_IS_THE_ID/edit`
3. Copy `THIS_IS_THE_ID` exactly
4. Update the **SPREADSHEET_ID** GitHub Secret with this value
5. Also check: click **"Share"** on the sheet and confirm the service account email (ending in `@...iam.gserviceaccount.com`) is listed as an **Editor**

### Problem 5: The Actions tab shows no workflow / says "Get started with GitHub Actions"

**What it means:** The `tracker.yml` file was not uploaded to the correct folder path.

**How to fix it:**
1. In your repository, click the **"Code"** tab
2. Look for a folder called `.github` — click into it, then into `workflows`
3. If the folder or file is missing:
   - Click **"Add file"** → **"Create new file"**
   - In the filename box, type `.github/workflows/tracker.yml` (the folders create automatically as you type)
   - Open `tracker.yml` from your computer with Notepad, copy all the text, and paste it into the editor
   - Click **"Commit new file"**
4. Go back to the **"Actions"** tab — the workflow should now appear

---

## Glossary

**API key** — A long string of random characters, like a password, that proves to an online service that you have permission to use it. Keep it private and never share it.

**Service account** — A special Google account designed for programs (not people) to use. It has its own email address and can be given access to Google Sheets, just like sharing with a regular person.

**GitHub** — A website that stores code. Think of it like Google Drive, but specifically for code files, with version history.

**GitHub Actions** — A feature of GitHub that runs your code automatically on a schedule, using a temporary computer in the cloud. You never have to press "run" yourself.

**Repository** — A project folder stored on GitHub, containing all your files and their full history of changes.

**GitHub Secret** — An encrypted value stored in GitHub (like an API key) that gets passed to your script when it runs. It is never visible in logs or code.

**Workflow file** — The `.github/workflows/tracker.yml` file that tells GitHub Actions what to do and when to do it.

**Cron schedule** — A coded way to specify a repeating time schedule. `30 2 */2 * *` means "2:30 AM, every 2 days" — you do not need to understand the syntax, it is already configured for you.

**JSON file** — A text file that stores structured data using curly braces `{}` and colons `:`. Your Google service account credentials file is a JSON file.

**Environment variable** — A value passed to a program from the outside environment (like an API key injected at runtime), rather than written directly into the code.

**Search grounding** — A Gemini feature that makes the AI search the web in real time before generating its answer, so responses reflect current information rather than just training data.

---

*Built with Python · OpenAI API · Google Gemini API · Google Sheets API · GitHub Actions*
