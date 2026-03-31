"""
RailSeva — Flask Backend  v5
════════════════════════════════════════════════════════
Run:   python app.py
Open:  http://localhost:5000

What's new in v5:
  - PNRs stored in SQLite pnrs table (not hardcoded dict)
  - Complaint approval via magic link button in email
  - /api/admin/approve/<token> — one click to resolve from email
  - /admin — browser admin panel with approve buttons
  - /api/admin/add-pnr — add real PNRs without code changes
════════════════════════════════════════════════════════
"""

from flask import Flask, request, jsonify, send_from_directory, session, redirect, url_for
from flask_cors import CORS
from functools import wraps
import sqlite3, json, random, string, base64, secrets
from datetime import datetime
import google.generativeai as genai
from PIL import Image
import io
import resend

# ═══════════════════════════════════════════════════════════
#  CONFIG  ← fill these before running
# ═══════════════════════════════════════════════════════════
GEMINI_KEY     = "geminiapi"      # aistudio.google.com → Get API key
RESEND_API_KEY = "resendapi"        # resend.com → API Keys
ADMIN_EMAIL    = "abinbjohn.nvn@gmail.com"   # admin email (Resend sends here)
ADMIN_PASSWORD = "railseva2026"                # password for /admin panel

# The URL your app runs at — used for magic approval links in emails
# Local:    "http://localhost:5000"
# Deployed: "https://yourdomain.com"
BASE_URL = "http://localhost:5000"

genai.configure(api_key=GEMINI_KEY)
resend.api_key = RESEND_API_KEY
RESEND_FROM    = "RailSeva Complaints <onboarding@resend.dev>"

DB_PATH = "railseva.db"
app = Flask(__name__)
app.secret_key = secrets.token_hex(32)  # session encryption key
CORS(app)

# ═══════════════════════════════════════════════════════════
#  CATEGORY → AUTHORITY EMAIL
# ═══════════════════════════════════════════════════════════
CAT_EMAIL = {
    "Staff-Behaviour":      "staff@railseva.in",
    "Security":             "security@railseva.in",
    "Coach-Cleanliness":    "hygiene@railseva.in",
    "Electrical-Equipment": "electrical@railseva.in",
    "Corruption/Bribery":   "vigilance@railseva.in",
    "Others":               "general@railseva.in",
    "Not Valid Complaint":  None,
}

# ═══════════════════════════════════════════════════════════
#  ADMIN AUTH DECORATOR
# ═══════════════════════════════════════════════════════════
def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            if request.is_json:
                return jsonify({"success": False, "error": "Admin login required"}), 401
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated

# ═══════════════════════════════════════════════════════════
#  DATABASE SETUP
#  pnrs table       — stores all journey records
#  complaints table — stores all filed grievances
# ═══════════════════════════════════════════════════════════
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS pnrs (
            pnr        TEXT PRIMARY KEY,
            train_name TEXT NOT NULL,
            train_num  TEXT NOT NULL,
            from_stn   TEXT NOT NULL,
            to_stn     TEXT NOT NULL,
            date       TEXT NOT NULL,
            class      TEXT NOT NULL,
            quota      TEXT DEFAULT 'GN',
            pax        INTEGER DEFAULT 1
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket               TEXT UNIQUE NOT NULL,
            approve_token        TEXT UNIQUE,
            pnr                  TEXT NOT NULL,
            train_name           TEXT,
            train_num            TEXT,
            from_stn             TEXT,
            to_stn               TEXT,
            date                 TEXT,
            class                TEXT,
            complaint_text       TEXT NOT NULL,
            english_translation  TEXT,
            language             TEXT,
            category             TEXT,
            subcategory          TEXT,
            admin_summary        TEXT,
            authority_email      TEXT,
            status               TEXT DEFAULT 'Pending',
            has_media            INTEGER DEFAULT 0,
            created_at           TEXT NOT NULL,
            resolved_at          TEXT
        )
    """)

    # Seed 50 PNRs if table is empty
    c.execute("SELECT COUNT(*) FROM pnrs")
    if c.fetchone()[0] == 0:
        pnrs = [
            ("4248765432","Udyan Express","11302","SBC","CSMT","15 Oct 2026","2A","GN",2),
            ("1234567890","Rajdhani Express","12951","NDLS","BCT","20 Mar 2026","1A","GN",1),
            ("9876543210","Shatabdi Express","12007","MAS","MYS","10 Apr 2026","CC","GN",3),
            ("1111111111","Garib Rath","12217","HWH","PNBE","05 May 2026","3A","GN",4),
            ("2222222222","Duronto Express","12213","PUNE","NDLS","12 Mar 2026","2A","GN",2),
            ("3333333333","August Kranti Raj","12953","BCT","NDLS","18 Mar 2026","3A","GN",2),
            ("4444444444","Kerala Express","12625","TVC","NDLS","22 Mar 2026","SL","GN",5),
            ("5555555555","Humsafar Express","12274","HWH","NDLS","25 Mar 2026","3A","GN",2),
            ("6666666666","Tejas Express","82501","LKO","NDLS","28 Mar 2026","CC","GN",1),
            ("7777777777","Vande Bharat","22436","NDLS","BSB","01 Apr 2026","EC","GN",2),
            ("8888888888","Karnataka Express","12627","SBC","NDLS","03 Apr 2026","2A","GN",3),
            ("9999999999","Coromandel Express","12841","HWH","MAS","07 Apr 2026","2A","GN",2),
            ("1122334455","Mumbai Mail","11094","PUNE","BCT","09 Apr 2026","SL","GN",4),
            ("2233445566","Gitanjali Express","12859","HWH","CSTM","11 Apr 2026","3A","GN",2),
            ("3344556677","Deccan Queen","12124","PUNE","BCT","14 Apr 2026","CC","GN",1),
            ("4455667788","Mysore Express","16210","MYS","MAS","16 Apr 2026","2A","GN",2),
            ("5566778899","Nandi Express","12007","SBC","UBL","18 Apr 2026","SL","GN",3),
            ("6677889900","Hampi Express","16592","SBC","UBL","20 Apr 2026","3A","GN",2),
            ("7788990011","Brindavan Express","12639","MAS","SBC","22 Apr 2026","CC","GN",4),
            ("8899001122","Island Express","16315","TVC","CBE","24 Apr 2026","SL","GN",2),
            ("9900112233","Mangala Express","12617","ERS","NDLS","26 Apr 2026","2A","GN",3),
            ("1023456789","Golden Temple Mail","12904","ASR","BCT","28 Apr 2026","1A","GN",2),
            ("2034567891","Vivek Express","15905","DBG","KYQ","01 May 2026","SL","GN",6),
            ("3045678912","Konkan Kanya","10111","CSTM","MAO","03 May 2026","2A","GN",2),
            ("4056789123","Janshatabdi","12071","BCT","PUNE","05 May 2026","CC","GN",3),
            ("5067891234","Intercity Express","12079","SBC","MYS","07 May 2026","CC","GN",1),
            ("6078912345","Sampark Kranti","12450","UDZ","NDLS","09 May 2026","3A","GN",2),
            ("7089123456","Sabarmati Express","19166","ADI","HWH","11 May 2026","SL","GN",4),
            ("8090234567","Poorva Express","12303","HWH","NDLS","13 May 2026","2A","GN",2),
            ("9001345678","Mahanagari Express","11093","BCT","PNBE","15 May 2026","SL","GN",3),
            ("1112131415","Chandigarh Express","12245","CDG","NDLS","17 May 2026","2A","GN",2),
            ("2223242526","Howrah Express","12321","CSTM","HWH","19 May 2026","3A","GN",5),
            ("3334353637","Goa Express","12779","HYB","VAG","21 May 2026","SL","GN",2),
            ("4445464748","Gondwana Express","12411","NDLS","JBP","23 May 2026","2A","GN",3),
            ("5556575859","Pushpak Express","12533","LKO","BCT","25 May 2026","3A","GN",2),
            ("6667686970","Garib Nawaz SF","12915","ADI","NDLS","27 May 2026","2A","GN",4),
            ("7778798081","Lucknow Mail","12230","NDLS","LKO","29 May 2026","1A","GN",1),
            ("8889909192","Swarna Jayanti","12987","JP","SDAH","31 May 2026","3A","GN",3),
            ("9900010203","Amritsar Express","14673","ASR","JAT","02 Jun 2026","SL","GN",2),
            ("1020304050","Patna Express","12308","PNBE","NDLS","04 Jun 2026","2A","GN",3),
            ("2030405060","Bhopal Express","12155","NDLS","BPL","06 Jun 2026","CC","GN",2),
            ("3040506070","Avantika Express","12961","NDLS","INDB","08 Jun 2026","2A","GN",4),
            ("4050607080","Paschim Express","12925","ASR","BCT","10 Jun 2026","3A","GN",2),
            ("5060708090","Kashi Express","13010","BSB","HWH","12 Jun 2026","SL","GN",5),
            ("6070809001","Chambal Express","11072","INDB","CSTM","14 Jun 2026","3A","GN",3),
            ("7080901012","Janmabhoomi Express","12759","SC","VSKP","16 Jun 2026","2A","GN",2),
            ("8091012023","East Coast Express","18645","HWH","VSKP","18 Jun 2026","SL","GN",4),
            ("9012023034","Tirupati Express","12245","SBC","TPTY","20 Jun 2026","CC","GN",3),
            ("1023034045","Madurai Express","12637","MAS","MDU","22 Jun 2026","SL","GN",2),
            ("2034045056","Navyug Express","14115","NDLS","DEE","24 Jun 2026","2A","GN",1),
            ("3045056067","Intercity SF","12031","HWH","PNBE","26 Jun 2026","CC","GN",2),
        ]
        c.executemany("INSERT OR IGNORE INTO pnrs VALUES (?,?,?,?,?,?,?,?,?)", pnrs)
        print(f"  ✅ Seeded {len(pnrs)} PNRs into database")

    # ── Migration: add columns that may be missing in older DBs ──────────
    existing_cols = {row[1] for row in c.execute("PRAGMA table_info(complaints)")}
    if "approve_token" not in existing_cols:
        c.execute("ALTER TABLE complaints ADD COLUMN approve_token TEXT")
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_approve_token ON complaints(approve_token)")
        print("  ✅ Migrated: added approve_token column")
    if "resolved_at" not in existing_cols:
        c.execute("ALTER TABLE complaints ADD COLUMN resolved_at TEXT")
        print("  ✅ Migrated: added resolved_at column")
    # ─────────────────────────────────────────────────────────────────────

    conn.commit()
    conn.close()
    print("✅ DB ready →", DB_PATH)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def gen_ticket():
    return f"RC-{datetime.now().strftime('%Y%m%d')}-{''.join(random.choices(string.ascii_uppercase+string.digits,k=7))}"

def gen_token():
    return secrets.token_urlsafe(24)


# ═══════════════════════════════════════════════════════════
#  GEMINI CLASSIFICATION
# ═══════════════════════════════════════════════════════════
def classify_with_gemini(text="", audio_b64=None, audio_mime="audio/webm",
                          image_b64=None, image_mime=None):
    PROMPT = f"""You are a multilingual Indian Railways grievance classifier.
Fluent in all 22 Indian languages: Malayalam, Tamil, Telugu, Kannada, Hindi, Bengali,
Marathi, Gujarati, Punjabi, Odia, Assamese, Urdu, Maithili and more — plus English.

LANGUAGE RULES:
- Always detect language. Malayalam: "AC pani cheyyunnilla". Tamil: "toilet romba dirty".
- Always fill english_translation with complete English translation.
- Always fill transcription with original verbatim text.

CATEGORIES:
1. Coach-Cleanliness
   Toilets: dirty/blocked/smelly toilet, no water in washroom
   Cockroach/Rodents: cockroaches, rats, insects
   Coach-Interior: waste/garbage/litter/dirty seat/floor, foul smell, unclean berth

2. Electrical-Equipment
   Air Conditioner: AC not working, too hot, too cold — "garam hai", "AC pani cheyyunnilla"
   Fans: fan not working — "fan kharab hai"
   Lights: lights not working

3. Staff-Behaviour: rude/abusive TTE or staff, misbehaviour, drunk on duty

4. Security
   Harassment: being harassed, eve teasing, molestation
   Theft_of_Passengers_Belongings/Snatching: theft, stolen bag/mobile/wallet
   Smoking/Drinking_Alcohol/Narcotics: smoking, drinking alcohol, drugs

5. Corruption/Bribery: TTE/staff demanding bribe or money

6. Others: food quality, water supply, bedroll, overcrowding — LAST RESORT only

7. Not Valid Complaint: test messages, gibberish, ticket booking issues

EXAMPLES:
"Waste in coach S7" → Coach-Cleanliness / Coach-Interior
"Toilet romba dirty, water illai" → Coach-Cleanliness / Toilets [Tamil]
"AC pani cheyyunnilla, valla choodum" → Electrical-Equipment / Air Conditioner [Malayalam]
"AC chal nahi raha, garam ho raha" → Electrical-Equipment / Air Conditioner [Hindi]
"TTE ne 200 rupees maange" → Corruption/Bribery / Corruption/Bribery
"Mera bag chori ho gaya" → Security / Theft_of_Passengers_Belongings/Snatching
"Coach-il cockroach irukku" → Coach-Cleanliness / Cockroach/Rodents [Tamil]

TASK:
{"1. TRANSCRIBE audio verbatim." if audio_b64 else "1. Read the complaint carefully."}
2. Detect exact language name (e.g. Malayalam, Tamil, Hindi, English).
3. Translate fully to English.
4. Pick MOST SPECIFIC category + subcategory. NEVER use Others if something fits better.
{"5. Check image matches complaint — media_mismatch=true if unrelated." if image_b64 else "5. No image — media_mismatch=false."}
6. Write 2-sentence English admin summary (third-person, factual).

Complaint text: "{text}"

Return ONLY raw JSON — no markdown, no backticks, nothing else:
{{"detected_language":"...","transcription":"...","category":"...","subcategory":"...","valid":true,"media_mismatch":false,"admin_summary":"...","english_translation":"..."}}"""

    model = genai.GenerativeModel("gemini-2.5-flash")
    parts = [PROMPT]

    if audio_b64:
        try:
            parts.append({"mime_type": audio_mime, "data": base64.b64decode(audio_b64)})
        except Exception as e:
            print(f"  Audio decode error: {e}")

    if image_b64 and image_mime and image_mime.startswith("image"):
        try:
            parts.append(Image.open(io.BytesIO(base64.b64decode(image_b64))))
        except Exception as e:
            print(f"  Image decode error: {e}")

    resp = model.generate_content(parts)
    raw  = resp.text.strip()
    if "```" in raw:
        raw = raw.split("```")[1].lstrip("json").strip()
    return json.loads(raw)


def fallback_classify(text):
    t = (text or "").lower()
    cat, sub = "Others", "Others"
    if any(w in t for w in ["waste","garbage","kachra","dirty","litter","unclean","smell",
                              "toilet","washroom","cockroach","rodent","rat","pest","ganda"]):
        cat = "Coach-Cleanliness"
        if any(w in t for w in ["toilet","washroom","commode","latrine"]): sub = "Toilets"
        elif any(w in t for w in ["cockroach","rat","rodent","pest","insect"]): sub = "Cockroach/Rodents"
        else: sub = "Coach-Interior"
    elif any(w in t for w in ["ac","fan","light","garam","thanda","cool","conditioner","heater","bulb"]):
        cat = "Electrical-Equipment"
        if any(w in t for w in ["ac","garam","thanda","cool","conditioner"]): sub = "Air Conditioner"
        elif "fan" in t: sub = "Fans"
        else: sub = "Lights"
    elif any(w in t for w in ["bribe","corrupt","extort","paisa","paise","money","rupee"]):
        cat = "Corruption/Bribery"; sub = "Corruption/Bribery"
    elif any(w in t for w in ["harass","theft","steal","chori","smok","narc","drink","alcohol","cigarette","molest"]):
        cat = "Security"
        if "harass" in t or "molest" in t: sub = "Harassment"
        elif any(w in t for w in ["theft","steal","chori","bag","wallet","mobile"]): sub = "Theft_of_Passengers_Belongings/Snatching"
        else: sub = "Smoking/Drinking_Alcohol/Narcotics"
    elif any(w in t for w in ["staff","tte","rude","misbehav","abusive","conductor"]):
        cat = "Staff-Behaviour"; sub = "Staff-Behaviour"
    return {
        "detected_language":"Unknown","transcription":text,
        "category":cat,"subcategory":sub,"valid":True,"media_mismatch":False,
        "admin_summary":f"Passenger reported a {cat} issue onboard. Requires investigation.",
        "english_translation":text
    }


# ═══════════════════════════════════════════════════════════
#  EMAIL with magic approval buttons
# ═══════════════════════════════════════════════════════════
def send_email(ticket, row, authority_email, approve_token):
    if "YOUR_RESEND_KEY" in RESEND_API_KEY:
        print("  📧 [SKIP] Resend API key not configured")
        print(f"  📧 [WOULD SEND] {ticket} → {authority_email}")
        return False

    resolve_url    = f"{BASE_URL}/api/admin/approve/{approve_token}"
    inprogress_url = f"{BASE_URL}/api/admin/approve/{approve_token}?status=In+Progress"

    html = f"""
<div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;
            border:1px solid #ddd;border-radius:10px;overflow:hidden">
  <div style="background:#1565C0;padding:22px 28px">
    <div style="color:#fff;font-size:1.15rem;font-weight:800">🚂 RailSeva AI</div>
    <div style="color:rgba(255,255,255,.7);font-size:.78rem">Indian Railways Grievance Portal</div>
  </div>
  <div style="background:#FFF9C4;padding:10px 20px;font-size:.82rem;color:#555;border-bottom:1px solid #eee">
    📌 <strong>Demo Mode:</strong> In production this goes to <strong>{authority_email}</strong>.
    Routed to admin inbox for demonstration.
  </div>
  <div style="padding:24px 28px">
    <h2 style="color:#1565C0;margin:0 0 4px;font-size:1.05rem">New Complaint — Action Required</h2>
    <p style="color:#666;font-size:.83rem;margin:0 0 20px">Please respond within 48 hours.</p>
    <table style="width:100%;border-collapse:collapse;font-size:.86rem">
      <tr style="background:#E3F2FD">
        <td style="padding:9px 14px;font-weight:700;color:#0D47A1;width:34%">Ticket</td>
        <td style="padding:9px 14px;font-family:monospace;font-weight:700;color:#1565C0">{ticket}</td>
      </tr>
      <tr><td style="padding:9px 14px;font-weight:700;color:#0D47A1">PNR</td>
          <td style="padding:9px 14px">{row['pnr']}</td></tr>
      <tr style="background:#E3F2FD">
        <td style="padding:9px 14px;font-weight:700;color:#0D47A1">Train</td>
        <td style="padding:9px 14px">{row['train_name']} #{row.get('train_num','')}</td>
      </tr>
      <tr><td style="padding:9px 14px;font-weight:700;color:#0D47A1">Route</td>
          <td style="padding:9px 14px">{row['from_stn']} → {row['to_stn']}</td></tr>
      <tr style="background:#E3F2FD">
        <td style="padding:9px 14px;font-weight:700;color:#0D47A1">Category</td>
        <td style="padding:9px 14px"><strong style="color:#C62828">{row['category']}</strong>
            → {row['subcategory']}</td>
      </tr>
      <tr><td style="padding:9px 14px;font-weight:700;color:#0D47A1">Language</td>
          <td style="padding:9px 14px">{row['language']}</td></tr>
      <tr style="background:#E3F2FD">
        <td style="padding:9px 14px;font-weight:700;color:#0D47A1">AI Summary</td>
        <td style="padding:9px 14px">{row['admin_summary']}</td>
      </tr>
      <tr><td style="padding:9px 14px;font-weight:700;color:#0D47A1">Passenger Said</td>
          <td style="padding:9px 14px;font-style:italic;color:#444">"{row['complaint_text']}"</td></tr>
      {f'<tr style="background:#E3F2FD"><td style="padding:9px 14px;font-weight:700;color:#0D47A1">English</td><td style="padding:9px 14px">{row.get("english_translation","")}</td></tr>' if row.get("english_translation") and row.get("english_translation") != row.get("complaint_text") else ""}
    </table>

    <!-- Magic action buttons -->
    <div style="margin-top:28px;padding:22px;background:#F8FAFF;border-radius:10px;
                border:1px solid #DCE8F8;text-align:center">
      <p style="margin:0 0 16px;font-size:.9rem;font-weight:700;color:#0D47A1">
        Take Action — click to update complaint status
      </p>
      <a href="{resolve_url}"
         style="display:inline-block;padding:13px 32px;background:#2E7D32;color:#fff;
                text-decoration:none;border-radius:8px;font-weight:700;font-size:.95rem;
                margin:0 6px 8px;letter-spacing:.02em">
        ✅ Mark as Resolved
      </a>
      <a href="{inprogress_url}"
         style="display:inline-block;padding:13px 32px;background:#E65100;color:#fff;
                text-decoration:none;border-radius:8px;font-weight:700;font-size:.95rem;
                margin:0 6px 8px;letter-spacing:.02em">
        ⏳ Mark as In Progress
      </a>
      <p style="font-size:.75rem;color:#999;margin-top:12px">
        After clicking, the status updates immediately. Passengers can track at
        <strong>localhost:5000</strong> → Track Status → enter ticket <strong>{ticket}</strong>
      </p>
    </div>
  </div>
  <div style="background:#f5f5f5;padding:12px 28px;font-size:.73rem;color:#999;
              text-align:center;border-top:1px solid #eee">
    RailSeva AI · complaints@railseva.com · Helpline 139
  </div>
</div>"""

    try:
        resp = resend.Emails.send({
            "from":    RESEND_FROM,
            "to":      [ADMIN_EMAIL],
            "subject": f"[RailSeva → {authority_email}] {row['category']} | {ticket}",
            "html":    html,
        })
        print(f"  📧 ✅ Sent to {ADMIN_EMAIL} (prod: {authority_email}) id:{resp.get('id','?')}")
        return True
    except Exception as e:
        print(f"  📧 ❌ Failed: {e}")
        return False


# ═══════════════════════════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════════════════════════

@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/api/verify-pnr", methods=["POST"])
def verify_pnr():
    """Reads PNR from SQLite pnrs table."""
    pnr = str((request.json or {}).get("pnr","")).strip()
    if len(pnr) != 10:
        return jsonify({"success":False,"error":"Enter a valid 10-digit PNR"}), 400
    conn = get_db()
    row  = conn.execute("SELECT * FROM pnrs WHERE pnr=?", (pnr,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"success":False,"error":"PNR not found in system"}), 404
    return jsonify({"success":True,"journey":dict(row)})


@app.route("/api/classify", methods=["POST"])
def classify():
    d = request.json or {}
    text       = d.get("text","").strip()
    audio_b64  = d.get("audio_b64")
    audio_mime = d.get("audio_mime","audio/webm")
    image_b64  = d.get("image_b64")
    image_mime = d.get("image_mime")
    if not text and not audio_b64:
        return jsonify({"success":False,"error":"Provide text or audio"}), 400
    try:
        result = classify_with_gemini(text=text, audio_b64=audio_b64,
                                       audio_mime=audio_mime, image_b64=image_b64,
                                       image_mime=image_mime)
    except Exception as e:
        print(f"Gemini error: {e} — keyword fallback")
        result = fallback_classify(text)
    return jsonify({"success":True,"result":result})


@app.route("/api/submit", methods=["POST"])
def submit():
    d         = request.json or {}
    pnr       = d.get("pnr","")
    text      = d.get("complaint_text","").strip() or "[Audio complaint]"
    result    = d.get("ai_result",{})
    has_media = int(bool(d.get("has_media",False)))
    if not pnr: return jsonify({"success":False,"error":"PNR required"}), 400

    conn  = get_db()
    j_row = conn.execute("SELECT * FROM pnrs WHERE pnr=?", (pnr,)).fetchone()
    j     = dict(j_row) if j_row else {}

    ticket        = gen_ticket()
    approve_token = gen_token()
    auth_email    = CAT_EMAIL.get(result.get("category"),"general@railseva.in")
    now           = datetime.now().isoformat()

    conn.execute("""
        INSERT INTO complaints
        (ticket,approve_token,pnr,train_name,train_num,from_stn,to_stn,date,class,
         complaint_text,english_translation,language,category,subcategory,
         admin_summary,authority_email,status,has_media,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (ticket,approve_token,pnr,
          j.get("train_name",""),j.get("train_num",""),
          j.get("from_stn",""),j.get("to_stn",""),
          j.get("date",""),j.get("class",""),
          text,
          result.get("english_translation",text),
          result.get("detected_language","Unknown"),
          result.get("category","Others"),
          result.get("subcategory","Others"),
          result.get("admin_summary",""),
          auth_email,"Pending",has_media,now))
    conn.commit(); conn.close()

    email_row = {
        "pnr":pnr,"train_name":j.get("train_name",""),
        "train_num":j.get("train_num",""),
        "from_stn":j.get("from_stn",""),"to_stn":j.get("to_stn",""),
        "complaint_text":text,
        "english_translation":result.get("english_translation",text),
        "language":result.get("detected_language","Unknown"),
        "category":result.get("category","Others"),
        "subcategory":result.get("subcategory","Others"),
        "admin_summary":result.get("admin_summary",""),
    }
    email_sent = send_email(ticket, email_row, auth_email, approve_token)
    return jsonify({"success":True,"ticket":ticket,
                    "authority_email":auth_email,"email_sent":email_sent})


@app.route("/api/admin/approve/<token>")
def approve_complaint(token):
    """
    Magic link endpoint — embedded in the notification email as a button.
    Clicking 'Mark as Resolved' or 'Mark as In Progress' hits this URL.
    Updates the database instantly and shows a confirmation page.
    """
    status = request.args.get("status","Resolved")
    if status not in ("Resolved","In Progress","Pending"):
        status = "Resolved"

    conn = get_db()
    row  = conn.execute(
        "SELECT * FROM complaints WHERE approve_token=?", (token,)
    ).fetchone()

    if not row:
        conn.close()
        return (
            "<html><body style='font-family:Arial;text-align:center;padding:60px;background:#FFF5F5'>"
            "<h2 style='color:#C62828'>❌ Link not valid</h2>"
            "<p>This approval link may be expired or the ticket was already updated.</p>"
            "<a href='/' style='color:#1565C0'>← Back to RailSeva</a>"
            "</body></html>"
        ), 404

    resolved_at = datetime.now().isoformat() if status == "Resolved" else None
    conn.execute(
        "UPDATE complaints SET status=?, resolved_at=? WHERE approve_token=?",
        (status, resolved_at, token)
    )
    conn.commit()
    ticket = row["ticket"]
    conn.close()

    colors = {"Resolved":"#2E7D32","In Progress":"#E65100","Pending":"#1565C0"}
    icons  = {"Resolved":"✅","In Progress":"⏳","Pending":"🔵"}
    color  = colors.get(status,"#1565C0")
    icon   = icons.get(status,"✅")
    ts     = datetime.now().strftime("%d %b %Y at %H:%M")

    return f"""<!DOCTYPE html><html><head>
<meta charset="UTF-8"><title>RailSeva — Complaint {status}</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{font-family:Arial,sans-serif;background:#F0F4FF;display:flex;
        align-items:center;justify-content:center;min-height:100vh}}
  .card{{background:#fff;border-radius:16px;padding:52px 60px;text-align:center;
         box-shadow:0 8px 40px rgba(21,101,192,.15);max-width:480px;width:90%}}
  .icon{{font-size:3.5rem;margin-bottom:18px}}
  h2{{color:{color};font-size:1.7rem;margin-bottom:8px}}
  p{{color:#555;font-size:.95rem;line-height:1.6;margin-bottom:6px}}
  .ticket{{font-family:monospace;font-size:1.1rem;font-weight:700;
           color:#1565C0;background:#E3F2FD;padding:9px 22px;border-radius:8px;
           display:inline-block;margin:16px 0}}
  .meta{{color:#888;font-size:.8rem;margin-bottom:28px}}
  a{{display:inline-block;padding:12px 28px;background:#1565C0;color:#fff;
     text-decoration:none;border-radius:8px;font-weight:700;font-size:.9rem}}
  a:hover{{background:#1E88E5}}
</style>
</head><body>
  <div class="card">
    <div class="icon">{icon}</div>
    <h2>Complaint {status}!</h2>
    <p>Ticket number:</p>
    <div class="ticket">{ticket}</div>
    <p class="meta">Status set to <strong>{status}</strong><br>on {ts}</p>
    <p style="margin-bottom:24px;font-size:.85rem;color:#777">
      Passengers can now see this status in the<br>
      Track Status page using ticket <strong>{ticket}</strong>
    </p>
    <a href="/">← Back to RailSeva Portal</a>
  </div>
</body></html>"""


@app.route("/api/track/<ticket>")
def track(ticket):
    conn = get_db()
    row  = conn.execute("SELECT * FROM complaints WHERE ticket=?", (ticket,)).fetchone()
    conn.close()
    if not row: return jsonify({"success":False,"error":"Ticket not found"}), 404
    return jsonify({"success":True,"complaint":dict(row)})


@app.route("/api/admin/update-status", methods=["POST"])
@require_admin
def update_status():
    """Manual status update via curl or Postman."""
    d = request.json or {}
    ticket = d.get("ticket"); status = d.get("status")
    if not ticket or not status: return jsonify({"success":False}), 400
    resolved_at = datetime.now().isoformat() if status=="Resolved" else None
    conn = get_db()
    conn.execute("UPDATE complaints SET status=?, resolved_at=? WHERE ticket=?",
                 (status,resolved_at,ticket))
    conn.commit(); conn.close()
    return jsonify({"success":True,"message":f"Status set to {status}"})


@app.route("/api/admin/complaints")
@require_admin
def admin_complaints():
    cat=request.args.get("category"); status=request.args.get("status")
    conn=get_db()
    q="SELECT * FROM complaints WHERE 1=1"; p=[]
    if cat:    q+=" AND category=?"; p.append(cat)
    if status: q+=" AND status=?";   p.append(status)
    rows=[dict(r) for r in conn.execute(q+" ORDER BY created_at DESC",p).fetchall()]
    conn.close()
    return jsonify({"success":True,"complaints":rows,"count":len(rows)})


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = ""
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect(url_for("admin_panel"))
        error = "Invalid password"
    return f"""<!DOCTYPE html><html><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RailSeva Admin Login</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{font-family:Arial,sans-serif;background:#F0F4FF;display:flex;
        align-items:center;justify-content:center;min-height:100vh}}
  .card{{background:#fff;border-radius:16px;padding:48px 44px;text-align:center;
         box-shadow:0 8px 40px rgba(21,101,192,.15);max-width:400px;width:90%}}
  h2{{color:#1565C0;margin-bottom:6px;font-size:1.4rem}}
  p{{color:#888;font-size:.85rem;margin-bottom:24px}}
  input{{width:100%;padding:12px 16px;border:2px solid #DCE8F8;border-radius:8px;
         font-size:.95rem;margin-bottom:16px;outline:none;transition:border .2s}}
  input:focus{{border-color:#1565C0}}
  button{{width:100%;padding:13px;background:#1565C0;color:#fff;border:none;
          border-radius:8px;font-size:1rem;font-weight:700;cursor:pointer}}
  button:hover{{background:#1E88E5}}
  .err{{color:#C62828;font-size:.85rem;margin-bottom:14px}}
</style>
</head><body>
<div class="card">
  <div style="font-size:2.5rem;margin-bottom:12px">🔒</div>
  <h2>Admin Login</h2>
  <p>Enter password to access the admin panel</p>
  {'<div class="err">' + error + '</div>' if error else ''}
  <form method="POST">
    <input type="password" name="password" placeholder="Password" autofocus>
    <button type="submit">Login</button>
  </form>
</div>
</body></html>"""


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin_login"))


@app.route("/admin")
@require_admin
def admin_panel():
    """Browser-based admin panel — view all complaints and approve them."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM complaints ORDER BY created_at DESC"
    ).fetchall()
    conn.close()

    sc = {"Pending":"#C62828","In Progress":"#E65100","Resolved":"#2E7D32"}

    rows_html = ""
    for r in rows:
        col = sc.get(r["status"],"#1565C0")
        approve_url = f"/api/admin/approve/{r['approve_token']}"
        inp_url     = f"/api/admin/approve/{r['approve_token']}?status=In+Progress"
        complaint_snippet = (r["complaint_text"] or "")[:80]
        if len(r["complaint_text"] or "") > 80: complaint_snippet += "…"

        rows_html += f"""<tr>
          <td style="font-family:monospace;font-size:.8rem;color:#1565C0;font-weight:700">{r['ticket']}</td>
          <td>{r['pnr']}</td>
          <td style="font-size:.82rem">{r['from_stn']} → {r['to_stn']}</td>
          <td><strong style="color:#0D47A1">{r['category']}</strong><br>
              <span style="font-size:.75rem;color:#888">{r['subcategory']}</span></td>
          <td style="font-size:.82rem;max-width:180px">{complaint_snippet}</td>
          <td style="font-weight:700;color:{col}">{r['status']}</td>
          <td style="font-size:.75rem;color:#888">{(r['created_at'] or '')[:16]}</td>
          <td>
            <a href="{approve_url}"
               style="display:inline-block;padding:5px 10px;background:#2E7D32;
                      color:#fff;border-radius:5px;font-size:.75rem;text-decoration:none;
                      margin-bottom:4px;white-space:nowrap">✅ Resolve</a><br>
            <a href="{inp_url}"
               style="display:inline-block;padding:5px 10px;background:#E65100;
                      color:#fff;border-radius:5px;font-size:.75rem;text-decoration:none;
                      white-space:nowrap">⏳ In Progress</a>
          </td>
        </tr>"""

    if not rows_html:
        rows_html = '<tr><td colspan="8" style="text-align:center;padding:40px;color:#888">No complaints yet — file one at the portal!</td></tr>'

    return f"""<!DOCTYPE html><html><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RailSeva Admin</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{font-family:Arial,sans-serif;background:#F0F4FF}}
  .nav{{background:#1565C0;padding:16px 28px;color:#fff;font-size:1.05rem;
        font-weight:800;display:flex;align-items:center;gap:12px;
        box-shadow:0 2px 12px rgba(21,101,192,.3)}}
  .nav a{{margin-left:auto;color:#FDD835;font-size:.85rem;text-decoration:none;font-weight:600}}
  .nav a:hover{{color:#fff}}
  .wrap{{padding:24px 20px;overflow-x:auto}}
  .stats{{display:flex;gap:14px;margin-bottom:20px;flex-wrap:wrap}}
  .stat{{background:#fff;border-radius:10px;padding:14px 22px;
         box-shadow:0 2px 10px rgba(21,101,192,.08);min-width:120px}}
  .stat .n{{font-size:1.6rem;font-weight:800;color:#1565C0}}
  .stat .l{{font-size:.72rem;color:#888;text-transform:uppercase;letter-spacing:.06em}}
  table{{width:100%;border-collapse:collapse;background:#fff;border-radius:12px;
         overflow:hidden;box-shadow:0 2px 16px rgba(21,101,192,.1)}}
  th{{background:#1565C0;color:#fff;padding:11px 14px;text-align:left;
      font-size:.78rem;letter-spacing:.06em;text-transform:uppercase}}
  td{{padding:10px 14px;border-bottom:1px solid #EBF3FF;font-size:.84rem;vertical-align:top}}
  tr:last-child td{{border-bottom:none}}
  tr:hover td{{background:#F8FBFF}}
</style>
</head><body>
<div class="nav">
  🚂 RailSeva Admin Panel
  <span style="font-size:.82rem;opacity:.7;font-weight:400;margin-left:8px">
    {len(rows)} complaint{'s' if len(rows)!=1 else ''} total
  </span>
  <a href="/">← Back to Portal</a>
  <a href="/admin/logout" style="color:#FDD835;font-size:.85rem;text-decoration:none;font-weight:600;margin-left:16px">🔓 Logout</a>
</div>
<div class="wrap">
  <div class="stats">
    <div class="stat"><div class="n">{len(rows)}</div><div class="l">Total</div></div>
    <div class="stat"><div class="n" style="color:#C62828">{sum(1 for r in rows if r['status']=='Pending')}</div><div class="l">Pending</div></div>
    <div class="stat"><div class="n" style="color:#E65100">{sum(1 for r in rows if r['status']=='In Progress')}</div><div class="l">In Progress</div></div>
    <div class="stat"><div class="n" style="color:#2E7D32">{sum(1 for r in rows if r['status']=='Resolved')}</div><div class="l">Resolved</div></div>
  </div>
  <table>
    <thead><tr>
      <th>Ticket</th><th>PNR</th><th>Route</th><th>Category</th>
      <th>Complaint</th><th>Status</th><th>Filed At</th><th>Actions</th>
    </tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</div>
</body></html>"""


@app.route("/api/admin/add-pnr", methods=["POST"])
@require_admin
def add_pnr():
    """Add a real PNR to the database at runtime — no restart needed."""
    d = request.json or {}
    required = ["pnr","train_name","train_num","from_stn","to_stn","date","class"]
    missing = [k for k in required if not d.get(k)]
    if missing:
        return jsonify({"success":False,"error":"Missing: "+", ".join(missing)}), 400
    try:
        conn = get_db()
        conn.execute(
            "INSERT OR REPLACE INTO pnrs (pnr,train_name,train_num,from_stn,to_stn,date,class,quota,pax) VALUES (?,?,?,?,?,?,?,?,?)",
            (d["pnr"],d["train_name"],d["train_num"],d["from_stn"],d["to_stn"],
             d["date"],d["class"],d.get("quota","GN"),d.get("pax",1))
        )
        conn.commit(); conn.close()
        return jsonify({"success":True,"message":f"PNR {d['pnr']} saved"})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)}), 500


@app.route("/api/stats")
def stats():
    conn=get_db()
    total=conn.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
    by_cat={r[0]:r[1] for r in conn.execute("SELECT category,COUNT(*) FROM complaints GROUP BY category").fetchall()}
    by_st={r[0]:r[1] for r in conn.execute("SELECT status,COUNT(*) FROM complaints GROUP BY status").fetchall()}
    conn.close()
    return jsonify({"total":total,"by_category":by_cat,"by_status":by_st})


if __name__ == "__main__":
    init_db()
    print("\n" + "═"*56)
    print("  🚂  RailSeva AI Grievance Portal  v5")
    print("═"*56)
    print("  → Portal:       http://localhost:5000")
    print("  → Admin Panel:  http://localhost:5000/admin")
    print("  → Stats:        http://localhost:5000/api/stats")
    print("═"*56 + "\n")
    app.run(debug=True, port=5000)
