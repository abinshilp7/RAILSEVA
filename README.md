# RAILSEVA
# RailSeva AI — Complete Setup Guide

## What is RailSeva?

RailSeva is an AI-powered Indian Railways grievance portal. Passengers enter their PNR, speak or type a complaint in any of 22 Indian languages, and Google Gemini classifies it automatically — then emails the responsible railway authority.

---

## Folder Structure

```
RailSeva/
├── app.py          ← Flask backend (run this)
├── index.html      ← Frontend (served by Flask, do NOT open directly)
├── railseva.db     ← SQLite database (auto-created on first run)
└── README.md       ← This file
```

> ⚠️ **Both `app.py` and `index.html` must be in the same folder.**

---

## Step 1 — Install Python Dependencies

Open a terminal in the RailSeva folder and run:

```bash
pip install flask flask-cors google-generativeai Pillow
```

If you get a permissions error on Linux/Mac:

```bash
pip install flask flask-cors google-generativeai Pillow --user
```

---

## Step 2 — Get a Free Gemini API Key

1. Go to **https://aistudio.google.com/apikey**
2. Sign in with your Google account
3. Click **Create API Key**
4. Copy the key (it looks like `AIzaSy...`)

Open `app.py` and on **line 22**, replace:

```python
GEMINI_KEY = "YOUR_GEMINI_API_KEY"
```

with:

```python
GEMINI_KEY = "AIzaSyYourActualKeyHere"
```

---

## Step 3 — Set Up Email Notifications

This is the part most people get stuck on. Follow carefully.

### Why email needs a special password

Gmail does **not** allow apps to use your normal login password for SMTP. You must generate a special **App Password** — a 16-character code that only works for sending email from code.

### 3a — Enable 2-Factor Authentication on your Gmail

App Passwords only work if 2FA is on.

1. Go to **https://myaccount.google.com/security**
2. Under "How you sign in to Google", click **2-Step Verification**
3. Follow the steps to turn it on

### 3b — Generate an App Password

1. Go to **https://myaccount.google.com/apppasswords**
   *(If you don't see this page, 2FA is not enabled yet — do Step 3a first)*
2. In the "App name" field, type: `RailSeva`
3. Click **Create**
4. Google shows you a **16-character password** like `abcd efgh ijkl mnop`
5. Copy it — **you will only see it once**

### 3c — Put the App Password into app.py

Open `app.py`. Find these lines near the top (around line 28):

```python
SMTP_USER = "wk.wjhs.k.ss.ksb.g@gmail.com"   # real Gmail account that sends
SMTP_PASS = "YOUR_GMAIL_APP_PASSWORD"           # 16-char App Password
```

Replace them with:

```python
SMTP_USER = "wk.wjhs.k.ss.ksb.g@gmail.com"   # keep this as-is
SMTP_PASS = "abcdefghijklmnop"                  # paste your 16-char App Password (no spaces)
```

> The password goes in **without spaces** — remove the spaces Google shows you.

### What the recipient sees

Emails are sent **from** `wk.wjhs.k.ss.ksb.g@gmail.com` but the **"From" name and address displayed** to the recipient is `complaints@railseva.com`. This is called email masking and is already set up in the code.

```
From:    RailSeva Complaints <complaints@railseva.com>
Subject: [RailSeva] New Complaint — Coach-Cleanliness | RC-20260327-AB3XY12
To:      hygiene@railseva.in
```

### Who gets notified for each category?

| Category | Email sent to |
|---|---|
| Staff Behaviour | staff@railseva.in |
| Security | security@railseva.in |
| Coach Cleanliness | hygiene@railseva.in |
| Electrical Equipment | electrical@railseva.in |
| Corruption / Bribery | vigilance@railseva.in |
| Others | general@railseva.in |
| Not Valid Complaint | *(no email sent)* |

---

## Step 4 — Run the Server

In your terminal, inside the RailSeva folder:

```bash
python app.py
```

You should see:

```
✅ DB ready → railseva.db
═══════════════════════════════════════════════════════
  🚂  RailSeva AI Grievance Portal  v4
═══════════════════════════════════════════════════════
  → Frontend:   http://localhost:5000
  → Stats:      http://localhost:5000/api/stats
  → Complaints: http://localhost:5000/api/admin/complaints
═══════════════════════════════════════════════════════
```

---

## Step 5 — Open the Website

Open your browser and go to:

```
http://localhost:5000
```

> ⚠️ **Do NOT double-click index.html to open it.** It must be served by Flask at `localhost:5000`. The address bar must show `localhost:5000`, not a file path.

---

## Test PNRs

Use any of these 10-digit PNRs to test:

| PNR | Train |
|---|---|
| `4248765432` | Udyan Express (SBC → CSMT) |
| `1234567890` | Rajdhani Express (NDLS → BCT) |
| `9876543210` | Shatabdi Express (MAS → MYS) |
| `7777777777` | Vande Bharat (NDLS → BSB) |
| `5555555555` | Humsafar Express (HWH → NDLS) |
| `1111111111` | Garib Rath (HWH → PNBE) |

50 PNRs total are in the system — see `DUMMY_PNRS` in `app.py` for the full list.

---

## Test Complaints (for Gemini classification)

Try these to verify Gemini is classifying correctly:

| Say / Type | Expected Category |
|---|---|
| "There is waste in coach S7" | Coach-Cleanliness → Coach-Interior |
| "AC chal nahi raha, garam hai" | Electrical-Equipment → Air Conditioner |
| "Toilet bahut ganda hai" | Coach-Cleanliness → Toilets |
| "TTE ne 200 rupees maange" | Corruption/Bribery → Corruption/Bribery |
| "Someone is smoking in the coach" | Security → Smoking |
| "Fan is not working on berth 34" | Electrical-Equipment → Fans |
| "Cockroach dekha maine seat ke neeche" | Coach-Cleanliness → Cockroach/Rodents |
| "My bag was stolen" | Security → Theft |

---

## Tracking a Complaint

1. After filing, note the **ticket number** on the confirmation screen (format: `RC-YYYYMMDD-XXXXXXX`)
2. Click **Track Status** in the nav bar
3. Enter the ticket number and click **Track**

> Only complaints submitted while `app.py` was running are saved to the database. Offline/fallback tickets are not stored.

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `GET /` | GET | Serves index.html |
| `/api/verify-pnr` | POST | Validates a PNR |
| `/api/classify` | POST | Classifies a complaint via Gemini |
| `/api/submit` | POST | Saves complaint + sends email |
| `/api/track/<ticket>` | GET | Gets complaint status by ticket |
| `/api/admin/complaints` | GET | Lists all complaints |
| `/api/admin/update-status` | POST | Updates complaint status |
| `/api/stats` | GET | Returns complaint statistics |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError` | Run `pip install flask flask-cors google-generativeai Pillow` |
| `Port 5000 in use` | Change `port=5000` to `port=5001` at the bottom of `app.py` |
| PNR not found | Use one of the test PNRs listed above |
| Gemini classifies everything as "Others" | Check your GEMINI_KEY is correct and not expired |
| Email not sending | Check that SMTP_PASS is the 16-char App Password (not your Gmail login). Check terminal for `📧 ❌ Failed:` error message |
| `SMTPAuthenticationError` | Your App Password is wrong or 2FA is not enabled |
| `Connection refused` on website | Make sure `python app.py` is still running in the terminal |
| Microphone not working | Browser needs microphone permission — click Allow when prompted. Use Chrome or Edge |

### Checking email errors

When you submit a complaint, watch the terminal where `app.py` is running. You will see one of:

```
📧 ✅ Sent → hygiene@railseva.in           ← email worked
📧 ❌ Failed: [error message here]          ← something is wrong
📧 [SKIP] Email not configured             ← SMTP_PASS not set yet
```

The error message after `Failed:` will tell you exactly what is wrong.

---

## How Gemini Classification Works

The AI prompt includes 20+ concrete examples covering all complaint types in both Hindi and English. For example:

- `"Waste in coach S7"` → Coach-Cleanliness / Coach-Interior
- `"AC chal nahi raha, garam ho raha hai"` → Electrical-Equipment / Air Conditioner
- `"TTE ne paise maange"` → Corruption/Bribery

If Gemini is unavailable, a keyword-based fallback classifier handles basic complaints in English and Hinglish.

---

## Languages Supported

All 22 scheduled Indian languages: Hindi, Bengali, Telugu, Marathi, Tamil, Urdu, Gujarati, Kannada, Odia, Malayalam, Punjabi, Assamese, Maithili, Sanskrit, Kashmiri, Nepali, Sindhi, Konkani, Manipuri, Dogri, Bodo, Santhali — plus English.

No manual language selection needed — Gemini detects it automatically from speech or text.

---

*RailSeva AI · Sec2_P1 · COMP301 · Vidyashilp University · Powered by Google Gemini 1.5 Flash*
