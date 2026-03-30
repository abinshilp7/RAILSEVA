"""
RailSeva — Flask Backend  (v4)
Run:  python app.py  →  http://localhost:5000
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3, json, random, string, base64, os
from datetime import datetime
from email.mime.text import MIMEText
import google.generativeai as genai
from PIL import Image
import io

# ═══════════════════════════════════════════════════════════════
#  CONFIG  — fill these before running
# ═══════════════════════════════════════════════════════════════
GEMINI_KEY  = "AI_API KEY"      # aistudio.google.com → Get API key (free)
genai.configure(api_key=GEMINI_KEY)

RESEND_API_KEY  = "RESENDAPI"        # resend.com → API Keys → Create
RESEND_FROM     = "RailSeva Complaints <complaints@railseva.com>"
# ↑ Replace railseva.com with your verified domain, OR use:
# RESEND_FROM   = "RailSeva Complaints <onboarding@resend.dev>"  ← works instantly, no domain needed

import resend
resend.api_key = RESEND_API_KEY

DB_PATH = "railseva.db"
app = Flask(__name__)
CORS(app)

# ═══════════════════════════════════════════════════════════════
#  ROUTING TABLE
# ═══════════════════════════════════════════════════════════════
CAT_EMAIL = {
    "Staff-Behaviour":      "staff@railseva.in",
    "Security":             "security@railseva.in",
    "Coach-Cleanliness":    "hygiene@railseva.in",
    "Electrical-Equipment": "electrical@railseva.in",
    "Corruption/Bribery":   "vigilance@railseva.in",
    "Others":               "general@railseva.in",
    "Not Valid Complaint":  None,
}

# ═══════════════════════════════════════════════════════════════
#  50 DUMMY PNRs
# ═══════════════════════════════════════════════════════════════
DUMMY_PNRS = {
    "4248765432":{"train_name":"Udyan Express","train_num":"11302","from_stn":"SBC","to_stn":"CSMT","date":"15 Oct 2026","class":"2A","quota":"GN","pax":2},
    "1234567890":{"train_name":"Rajdhani Express","train_num":"12951","from_stn":"NDLS","to_stn":"BCT","date":"20 Mar 2026","class":"1A","quota":"GN","pax":1},
    "9876543210":{"train_name":"Shatabdi Express","train_num":"12007","from_stn":"MAS","to_stn":"MYS","date":"10 Apr 2026","class":"CC","quota":"GN","pax":3},
    "1111111111":{"train_name":"Garib Rath","train_num":"12217","from_stn":"HWH","to_stn":"PNBE","date":"05 May 2026","class":"3A","quota":"GN","pax":4},
    "2222222222":{"train_name":"Duronto Express","train_num":"12213","from_stn":"PUNE","to_stn":"NDLS","date":"12 Mar 2026","class":"2A","quota":"GN","pax":2},
    "3333333333":{"train_name":"August Kranti Raj","train_num":"12953","from_stn":"BCT","to_stn":"NDLS","date":"18 Mar 2026","class":"3A","quota":"GN","pax":2},
    "4444444444":{"train_name":"Kerala Express","train_num":"12625","from_stn":"TVC","to_stn":"NDLS","date":"22 Mar 2026","class":"SL","quota":"GN","pax":5},
    "5555555555":{"train_name":"Humsafar Express","train_num":"12274","from_stn":"HWH","to_stn":"NDLS","date":"25 Mar 2026","class":"3A","quota":"GN","pax":2},
    "6666666666":{"train_name":"Tejas Express","train_num":"82501","from_stn":"LKO","to_stn":"NDLS","date":"28 Mar 2026","class":"CC","quota":"GN","pax":1},
    "7777777777":{"train_name":"Vande Bharat","train_num":"22436","from_stn":"NDLS","to_stn":"BSB","date":"01 Apr 2026","class":"EC","quota":"GN","pax":2},
    "8888888888":{"train_name":"Karnataka Express","train_num":"12627","from_stn":"SBC","to_stn":"NDLS","date":"03 Apr 2026","class":"2A","quota":"GN","pax":3},
    "9999999999":{"train_name":"Coromandel Express","train_num":"12841","from_stn":"HWH","to_stn":"MAS","date":"07 Apr 2026","class":"2A","quota":"GN","pax":2},
    "1122334455":{"train_name":"Mumbai Mail","train_num":"11094","from_stn":"PUNE","to_stn":"BCT","date":"09 Apr 2026","class":"SL","quota":"GN","pax":4},
    "2233445566":{"train_name":"Gitanjali Express","train_num":"12859","from_stn":"HWH","to_stn":"CSTM","date":"11 Apr 2026","class":"3A","quota":"GN","pax":2},
    "3344556677":{"train_name":"Deccan Queen","train_num":"12124","from_stn":"PUNE","to_stn":"BCT","date":"14 Apr 2026","class":"CC","quota":"GN","pax":1},
    "4455667788":{"train_name":"Mysore Express","train_num":"16210","from_stn":"MYS","to_stn":"MAS","date":"16 Apr 2026","class":"2A","quota":"GN","pax":2},
    "5566778899":{"train_name":"Nandi Express","train_num":"12007","from_stn":"SBC","to_stn":"UBL","date":"18 Apr 2026","class":"SL","quota":"GN","pax":3},
    "6677889900":{"train_name":"Hampi Express","train_num":"16592","from_stn":"SBC","to_stn":"UBL","date":"20 Apr 2026","class":"3A","quota":"GN","pax":2},
    "7788990011":{"train_name":"Brindavan Express","train_num":"12639","from_stn":"MAS","to_stn":"SBC","date":"22 Apr 2026","class":"CC","quota":"GN","pax":4},
    "8899001122":{"train_name":"Island Express","train_num":"16315","from_stn":"TVC","to_stn":"CBE","date":"24 Apr 2026","class":"SL","quota":"GN","pax":2},
    "9900112233":{"train_name":"Mangala Express","train_num":"12617","from_stn":"ERS","to_stn":"NDLS","date":"26 Apr 2026","class":"2A","quota":"GN","pax":3},
    "1023456789":{"train_name":"Golden Temple Mail","train_num":"12904","from_stn":"ASR","to_stn":"BCT","date":"28 Apr 2026","class":"1A","quota":"GN","pax":2},
    "2034567891":{"train_name":"Vivek Express","train_num":"15905","from_stn":"DBG","to_stn":"KYQ","date":"01 May 2026","class":"SL","quota":"GN","pax":6},
    "3045678912":{"train_name":"Konkan Kanya","train_num":"10111","from_stn":"CSTM","to_stn":"MAO","date":"03 May 2026","class":"2A","quota":"GN","pax":2},
    "4056789123":{"train_name":"Janshatabdi","train_num":"12071","from_stn":"BCT","to_stn":"PUNE","date":"05 May 2026","class":"CC","quota":"GN","pax":3},
    "5067891234":{"train_name":"Intercity Express","train_num":"12079","from_stn":"SBC","to_stn":"MYS","date":"07 May 2026","class":"CC","quota":"GN","pax":1},
    "6078912345":{"train_name":"Sampark Kranti","train_num":"12450","from_stn":"UDZ","to_stn":"NDLS","date":"09 May 2026","class":"3A","quota":"GN","pax":2},
    "7089123456":{"train_name":"Sabarmati Express","train_num":"19166","from_stn":"ADI","to_stn":"HWH","date":"11 May 2026","class":"SL","quota":"GN","pax":4},
    "8090234567":{"train_name":"Poorva Express","train_num":"12303","from_stn":"HWH","to_stn":"NDLS","date":"13 May 2026","class":"2A","quota":"GN","pax":2},
    "9001345678":{"train_name":"Mahanagari Express","train_num":"11093","from_stn":"BCT","to_stn":"PNBE","date":"15 May 2026","class":"SL","quota":"GN","pax":3},
    "1112131415":{"train_name":"Chandigarh Express","train_num":"12245","from_stn":"CDG","to_stn":"NDLS","date":"17 May 2026","class":"2A","quota":"GN","pax":2},
    "2223242526":{"train_name":"Howrah Express","train_num":"12321","from_stn":"CSTM","to_stn":"HWH","date":"19 May 2026","class":"3A","quota":"GN","pax":5},
    "3334353637":{"train_name":"Goa Express","train_num":"12779","from_stn":"HYB","to_stn":"VAG","date":"21 May 2026","class":"SL","quota":"GN","pax":2},
    "4445464748":{"train_name":"Gondwana Express","train_num":"12411","from_stn":"NDLS","to_stn":"JBP","date":"23 May 2026","class":"2A","quota":"GN","pax":3},
    "5556575859":{"train_name":"Pushpak Express","train_num":"12533","from_stn":"LKO","to_stn":"BCT","date":"25 May 2026","class":"3A","quota":"GN","pax":2},
    "6667686970":{"train_name":"Garib Nawaz SF","train_num":"12915","from_stn":"ADI","to_stn":"NDLS","date":"27 May 2026","class":"2A","quota":"GN","pax":4},
    "7778798081":{"train_name":"Lucknow Mail","train_num":"12230","from_stn":"NDLS","to_stn":"LKO","date":"29 May 2026","class":"1A","quota":"GN","pax":1},
    "8889909192":{"train_name":"Swarna Jayanti","train_num":"12987","from_stn":"JP","to_stn":"SDAH","date":"31 May 2026","class":"3A","quota":"GN","pax":3},
    "9900010203":{"train_name":"Amritsar Express","train_num":"14673","from_stn":"ASR","to_stn":"JAT","date":"02 Jun 2026","class":"SL","quota":"GN","pax":2},
    "1020304050":{"train_name":"Patna Express","train_num":"12308","from_stn":"PNBE","to_stn":"NDLS","date":"04 Jun 2026","class":"2A","quota":"GN","pax":3},
    "2030405060":{"train_name":"Bhopal Express","train_num":"12155","from_stn":"NDLS","to_stn":"BPL","date":"06 Jun 2026","class":"CC","quota":"GN","pax":2},
    "3040506070":{"train_name":"Avantika Express","train_num":"12961","from_stn":"NDLS","to_stn":"INDB","date":"08 Jun 2026","class":"2A","quota":"GN","pax":4},
    "4050607080":{"train_name":"Paschim Express","train_num":"12925","from_stn":"ASR","to_stn":"BCT","date":"10 Jun 2026","class":"3A","quota":"GN","pax":2},
    "5060708090":{"train_name":"Kashi Express","train_num":"13010","from_stn":"BSB","to_stn":"HWH","date":"12 Jun 2026","class":"SL","quota":"GN","pax":5},
    "6070809001":{"train_name":"Chambal Express","train_num":"11072","from_stn":"INDB","to_stn":"CSTM","date":"14 Jun 2026","class":"3A","quota":"GN","pax":3},
    "7080901012":{"train_name":"Janmabhoomi Express","train_num":"12759","from_stn":"SC","to_stn":"VSKP","date":"16 Jun 2026","class":"2A","quota":"GN","pax":2},
    "8091012023":{"train_name":"East Coast Express","train_num":"18645","from_stn":"HWH","to_stn":"VSKP","date":"18 Jun 2026","class":"SL","quota":"GN","pax":4},
    "9012023034":{"train_name":"Tirupati Express","train_num":"12245","from_stn":"SBC","to_stn":"TPTY","date":"20 Jun 2026","class":"CC","quota":"GN","pax":3},
    "1023034045":{"train_name":"Madurai Express","train_num":"12637","from_stn":"MAS","to_stn":"MDU","date":"22 Jun 2026","class":"SL","quota":"GN","pax":2},
    "2034045056":{"train_name":"Navyug Express","train_num":"14115","from_stn":"NDLS","to_stn":"DEE","date":"24 Jun 2026","class":"2A","quota":"GN","pax":1},
    "3045056067":{"train_name":"Intercity SF","train_num":"12031","from_stn":"HWH","to_stn":"PNBE","date":"26 Jun 2026","class":"CC","quota":"GN","pax":2},
}

# ═══════════════════════════════════════════════════════════════
#  DATABASE
# ═══════════════════════════════════════════════════════════════
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket TEXT UNIQUE NOT NULL,
            pnr TEXT NOT NULL,
            train_name TEXT, train_num TEXT, from_stn TEXT, to_stn TEXT,
            date TEXT, class TEXT,
            complaint_text TEXT NOT NULL,
            english_translation TEXT, language TEXT,
            category TEXT, subcategory TEXT,
            admin_summary TEXT, authority_email TEXT,
            status TEXT DEFAULT 'Pending',
            has_media INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit(); conn.close()
    print("✅ DB ready →", DB_PATH)

def gen_ticket():
    return f"RC-{datetime.now().strftime('%Y%m%d')}-{''.join(random.choices(string.ascii_uppercase+string.digits,k=7))}"

# ═══════════════════════════════════════════════════════════════
#  GEMINI  — highly detailed prompt with examples
# ═══════════════════════════════════════════════════════════════
def classify_with_gemini(text="", audio_b64=None, audio_mime="audio/webm",
                          image_b64=None, image_mime=None):

    # Rich examples help Gemini understand the full range of complaints
    PROMPT = f"""You are an expert Indian Railways grievance officer and AI classifier.
Your job is to read/listen to a passenger complaint and classify it ACCURATELY.

=== CATEGORIES AND WHAT BELONGS IN EACH ===

1. Coach-Cleanliness
   - Toilets: toilet blocked, smelly toilet, toilet not flushing, no water in toilet, toilet dirty, washroom problem
   - Cockroach/Rodents: cockroaches seen, rats in coach, insects, pests
   - Coach-Interior: garbage in coach, waste on floor/seat, dirty seats, litter, spilled food, foul smell in coach, unclean berth, dirty blanket/pillow, waste/garbage in coach S7 or any coach

2. Electrical-Equipment
   - Air Conditioner: AC not working, AC not cooling, AC too cold, no AC, broken AC, garam hai (too hot), thanda nahi (not cool)
   - Fans: fan not working, fan broken, ceiling fan stopped
   - Lights: lights not working, light fused, no electricity, dark coach

3. Staff-Behaviour
   - Staff-Behaviour: rude TTE, misbehaving conductor, staff abusive, staff not helpful, TTE harassing, staff demanding money without receipt, staff drunk, staff sleeping on duty

4. Security
   - Harassment: passenger being harassed, eve teasing, verbal abuse by co-passenger, molestation
   - Theft_of_Passengers_Belongings/Snatching: theft, stolen luggage, pickpocket, bag snatched, mobile stolen
   - Smoking/Drinking_Alcohol/Narcotics: smoking in coach, drinking alcohol, drug use, chain smoker in train

5. Corruption/Bribery
   - Corruption/Bribery: TTE asking for bribe, staff demanding money, extortion, unauthorized fee, paying for reserved seat

6. Others
   - Others: food quality, pantry car issue, overcharging for food, no bedroll, water not available, overcrowding, any complaint that does not fit above categories

7. Not Valid Complaint
   - Not Valid Complaint: test messages, gibberish, booking complaints, ticket price disputes, questions, general feedback not about an onboard experience

=== CONCRETE EXAMPLES ===
"Waste in coach S7" → Coach-Cleanliness / Coach-Interior
"Toilet band hai, bahut buri smell aa rahi hai" → Coach-Cleanliness / Toilets
"AC chal nahi raha, garam ho raha hai" → Electrical-Equipment / Air Conditioner
"TTE ne 200 rupees maange bina receipt ke" → Corruption/Bribery / Corruption/Bribery
"Mera bag chori ho gaya" → Security / Theft_of_Passengers_Belongings/Snatching
"Coach mein cockroach dekhe" → Coach-Cleanliness / Cockroach/Rodents
"Fan kharab hai berth 34 pe" → Electrical-Equipment / Fans
"TTE bahut rude tha, gaali de raha tha" → Staff-Behaviour / Staff-Behaviour
"Aadmi cigarette pee raha hai coach mein" → Security / Smoking/Drinking_Alcohol/Narcotics
"Lights nahi chal rahi" → Electrical-Equipment / Lights
"Koi ladki ko harass kar raha hai" → Security / Harassment
"Garbage/kachra pada hua hai seat ke neeche" → Coach-Cleanliness / Coach-Interior
"There is waste near my seat in S7" → Coach-Cleanliness / Coach-Interior
"The toilet is very dirty" → Coach-Cleanliness / Toilets
"Someone is smoking" → Security / Smoking/Drinking_Alcohol/Narcotics
"My wallet was stolen" → Security / Theft_of_Passengers_Belongings/Snatching
"No water in washroom" → Coach-Cleanliness / Toilets
"Seat is very dirty, has stains and food waste" → Coach-Cleanliness / Coach-Interior

=== YOUR TASK ===
{"STEP 1: Transcribe the audio recording verbatim first." if audio_b64 else "STEP 1: Read the complaint text carefully."}
STEP 2: Auto-detect the language (Hindi, English, Tamil, Telugu, Kannada, etc.)
STEP 3: Translate to English if needed.
STEP 4: Use the examples and category descriptions above to pick the MOST SPECIFIC category and subcategory. If in doubt between a specific category and "Others", always pick the specific one.
STEP 5: {"Check if any attached image is consistent with the complaint." if image_b64 else "No image attached — set media_mismatch to false."}
STEP 6: Write a 2-sentence professional admin summary in English (third person, factual, actionable).

IMPORTANT RULES:
- "Others" should only be used if NO other category fits at all
- Waste, garbage, dirty, unclean, litter → Coach-Cleanliness / Coach-Interior
- Toilet issues → Coach-Cleanliness / Toilets
- Temperature / AC / fan / light → Electrical-Equipment
- Money demands → Corruption/Bribery
- Theft / stealing → Security / Theft
- Smoking / drinking → Security / Smoking
- Staff misbehaviour → Staff-Behaviour
- Be generous in classification — always try to fit into a specific bucket

Complaint text: "{text}"

Respond with ONLY this raw JSON (no markdown, no triple backticks, nothing else):
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
    # Strip any markdown code fences Gemini might add despite instructions
    if "```" in raw:
        raw = raw.split("```")[1] if "```" in raw else raw
        raw = raw.lstrip("json").strip()
    return json.loads(raw)


def fallback_classify(text):
    """Keyword fallback — used only when Gemini API is unreachable."""
    t = (text or "").lower()
    cat, sub = "Others", "Others"

    # Cleanliness — check first (most common mismatch)
    if any(w in t for w in ["waste","garbage","kachra","dirty","litter","spill","unclean",
                              "stain","smell","foul","ganda","toilet","washroom","commode",
                              "cockroach","rodent","rat","pest","insect"]):
        cat = "Coach-Cleanliness"
        if any(w in t for w in ["toilet","washroom","commode","latrine"]): sub = "Toilets"
        elif any(w in t for w in ["cockroach","rat","rodent","pest","insect"]): sub = "Cockroach/Rodents"
        else: sub = "Coach-Interior"
    elif any(w in t for w in ["ac","fan","light","cool","garam","thanda","conditioner","heater","bulb"]):
        cat = "Electrical-Equipment"
        if any(w in t for w in ["ac","cool","garam","thanda","conditioner"]): sub = "Air Conditioner"
        elif "fan" in t: sub = "Fans"
        else: sub = "Lights"
    elif any(w in t for w in ["bribe","bribery","corrupt","extort","paisa","paise","money","rupee","rupe"]):
        cat = "Corruption/Bribery"; sub = "Corruption/Bribery"
    elif any(w in t for w in ["harass","theft","steal","chori","smok","narc","drink","alcohol","cigarette","molest"]):
        cat = "Security"
        if any(w in t for w in ["harass","molest","eve"]): sub = "Harassment"
        elif any(w in t for w in ["theft","steal","chori","bag","wallet","mobile"]): sub = "Theft_of_Passengers_Belongings/Snatching"
        else: sub = "Smoking/Drinking_Alcohol/Narcotics"
    elif any(w in t for w in ["staff","tte","tc","rude","misbehav","attitude","abusive","conductor"]):
        cat = "Staff-Behaviour"; sub = "Staff-Behaviour"

    return {
        "detected_language": "Unknown", "transcription": text,
        "category": cat, "subcategory": sub,
        "valid": True, "media_mismatch": False,
        "admin_summary": f"Passenger reported a {cat} issue onboard. Requires investigation.",
        "english_translation": text
    }


# ═══════════════════════════════════════════════════════════════
#  EMAIL  (masked as complaints@railseva.com)
# ═══════════════════════════════════════════════════════════════
def send_email(ticket, row, to):
    if not to:
        print("  📧 [SKIP] No authority email for this category"); return False

    if "YOUR_API_KEY" in RESEND_API_KEY:
        print(f"  📧 [SKIP] Resend API key not set — update RESEND_API_KEY in app.py")
        print(f"  📧 [WOULD SEND] {ticket} → {to}")
        return False

    html = f"""
<div style="font-family:Arial,sans-serif;max-width:620px;margin:0 auto;border:1px solid #ddd;border-radius:10px;overflow:hidden">
  <div style="background:#1565C0;padding:22px 28px;display:flex;align-items:center;gap:14px">
    <span style="font-size:1.8rem">🚂</span>
    <div>
      <div style="color:#fff;font-size:1.1rem;font-weight:800">RailSeva AI</div>
      <div style="color:rgba(255,255,255,.75);font-size:.78rem">Indian Railways Grievance Portal</div>
    </div>
  </div>
  <div style="padding:26px 28px">
    <h2 style="color:#1565C0;margin:0 0 6px;font-size:1.1rem">New Complaint — Action Required</h2>
    <p style="color:#666;font-size:.84rem;margin:0 0 20px">Please investigate and respond within 48 hours per Railway grievance policy.</p>
    <table style="width:100%;border-collapse:collapse;font-size:.87rem">
      <tr style="background:#E3F2FD"><td style="padding:10px 14px;font-weight:700;color:#0D47A1;width:36%">Ticket</td><td style="padding:10px 14px;font-family:monospace;font-weight:700;color:#1565C0">{ticket}</td></tr>
      <tr><td style="padding:10px 14px;font-weight:700;color:#0D47A1">PNR</td><td style="padding:10px 14px">{row['pnr']}</td></tr>
      <tr style="background:#E3F2FD"><td style="padding:10px 14px;font-weight:700;color:#0D47A1">Train</td><td style="padding:10px 14px">{row['train_name']} #{row.get('train_num','')}</td></tr>
      <tr><td style="padding:10px 14px;font-weight:700;color:#0D47A1">Route</td><td style="padding:10px 14px">{row['from_stn']} → {row['to_stn']}</td></tr>
      <tr style="background:#E3F2FD"><td style="padding:10px 14px;font-weight:700;color:#0D47A1">Category</td><td style="padding:10px 14px"><strong style="color:#C62828">{row['category']}</strong> → {row['subcategory']}</td></tr>
      <tr><td style="padding:10px 14px;font-weight:700;color:#0D47A1">Language</td><td style="padding:10px 14px">{row['language']}</td></tr>
      <tr style="background:#E3F2FD"><td style="padding:10px 14px;font-weight:700;color:#0D47A1">AI Summary</td><td style="padding:10px 14px">{row['admin_summary']}</td></tr>
      <tr><td style="padding:10px 14px;font-weight:700;color:#0D47A1">Passenger Said</td><td style="padding:10px 14px;font-style:italic;color:#444">"{row['complaint_text']}"</td></tr>
      {f'<tr style="background:#E3F2FD"><td style="padding:10px 14px;font-weight:700;color:#0D47A1">English</td><td style="padding:10px 14px">{row.get("english_translation","")}</td></tr>' if row.get('english_translation') and row.get('english_translation') != row.get('complaint_text') else ''}
    </table>
    <div style="margin-top:22px;padding:14px 18px;background:#FFF9C4;border-left:4px solid #F9A825;border-radius:6px;font-size:.82rem;color:#555">
      <strong>⚠ Action Required:</strong> Investigate and update complaint status within 48 hours.
    </div>
  </div>
  <div style="background:#f5f5f5;padding:14px 28px;font-size:.74rem;color:#999;text-align:center;border-top:1px solid #eee">
    Sent by RailSeva AI · complaints@railseva.com · Helpline 139
  </div>
</div>"""

    try:
        params = {
            "from":    RESEND_FROM,
            "to":      [to],
            "subject": f"[RailSeva] New Complaint — {row['category']} | {ticket}",
            "html":    html,
        }
        response = resend.Emails.send(params)
        print(f"  📧 ✅ Sent via Resend → {to} (id: {response.get('id','?')})")
        return True
    except Exception as e:
        print(f"  📧 ❌ Resend failed: {e}")
        return False


# ═══════════════════════════════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════════════════════════════
@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/api/verify-pnr", methods=["POST"])
def verify_pnr():
    pnr = str((request.json or {}).get("pnr","")).strip()
    if len(pnr) != 10:
        return jsonify({"success":False,"error":"Enter a valid 10-digit PNR"}), 400
    j = DUMMY_PNRS.get(pnr)
    if not j: return jsonify({"success":False,"error":"PNR not found in system"}), 404
    return jsonify({"success":True,"journey":{**j,"pnr":pnr}})

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

    j          = DUMMY_PNRS.get(pnr,{})
    ticket     = gen_ticket()
    auth_email = CAT_EMAIL.get(result.get("category"),"general@railseva.in")
    now        = datetime.now().isoformat()

    row = {
        "pnr":pnr, "train_name":j.get("train_name",""), "train_num":j.get("train_num",""),
        "from_stn":j.get("from_stn",""), "to_stn":j.get("to_stn",""),
        "date":j.get("date",""), "class":j.get("class",""),
        "complaint_text":text,
        "english_translation":result.get("english_translation",text),
        "language":result.get("detected_language","Unknown"),
        "category":result.get("category","Others"),
        "subcategory":result.get("subcategory","Others"),
        "admin_summary":result.get("admin_summary",""),
        "authority_email":auth_email,
    }

    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO complaints
        (ticket,pnr,train_name,train_num,from_stn,to_stn,date,class,
         complaint_text,english_translation,language,category,subcategory,
         admin_summary,authority_email,status,has_media,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (ticket,pnr,row["train_name"],row["train_num"],row["from_stn"],row["to_stn"],
          row["date"],row["class"],text,row["english_translation"],row["language"],
          row["category"],row["subcategory"],row["admin_summary"],auth_email,
          "Pending",has_media,now))
    conn.commit(); conn.close()

    email_sent = send_email(ticket, row, auth_email)
    return jsonify({"success":True,"ticket":ticket,"authority_email":auth_email,"email_sent":email_sent})

@app.route("/api/track/<ticket>")
def track(ticket):
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    row  = conn.execute("SELECT * FROM complaints WHERE ticket=?",(ticket,)).fetchone()
    conn.close()
    if not row: return jsonify({"success":False,"error":"Ticket not found"}), 404
    return jsonify({"success":True,"complaint":dict(row)})

@app.route("/api/admin/complaints")
def admin_complaints():
    cat=request.args.get("category"); status=request.args.get("status")
    conn=sqlite3.connect(DB_PATH); conn.row_factory=sqlite3.Row
    q="SELECT * FROM complaints WHERE 1=1"; p=[]
    if cat:    q+=" AND category=?"; p.append(cat)
    if status: q+=" AND status=?";   p.append(status)
    rows=[dict(r) for r in conn.execute(q+" ORDER BY created_at DESC",p).fetchall()]
    conn.close()
    return jsonify({"success":True,"complaints":rows,"count":len(rows)})

@app.route("/api/admin/update-status", methods=["POST"])
def update_status():
    d=request.json or {}; ticket=d.get("ticket"); status=d.get("status")
    if not ticket or not status: return jsonify({"success":False}), 400
    conn=sqlite3.connect(DB_PATH)
    conn.execute("UPDATE complaints SET status=? WHERE ticket=?",(status,ticket))
    conn.commit(); conn.close()
    return jsonify({"success":True})

@app.route("/api/stats")
def stats():
    conn=sqlite3.connect(DB_PATH)
    total=conn.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
    by_cat={r[0]:r[1] for r in conn.execute("SELECT category,COUNT(*) FROM complaints GROUP BY category").fetchall()}
    by_st ={r[0]:r[1] for r in conn.execute("SELECT status,COUNT(*) FROM complaints GROUP BY status").fetchall()}
    conn.close()
    return jsonify({"total":total,"by_category":by_cat,"by_status":by_st})

if __name__ == "__main__":
    init_db()
    print("\n" + "═"*55)
    print("  🚂  RailSeva AI Grievance Portal  v4")
    print("═"*55)
    print("  → Frontend:  http://localhost:5000")
    print("  → Stats:     http://localhost:5000/api/stats")
    print("  → Complaints:http://localhost:5000/api/admin/complaints")
    print("═"*55 + "\n")
    app.run(debug=True, port=5000)
