import os
import requests
from bs4 import BeautifulSoup
from google.cloud import firestore
import json
import re

# -------------------------------
# FIREBASE INIT FROM ENV
# -------------------------------
print("🔥 Initializing Firestore from environment variable...")

firebase_key_json = os.environ.get("FIREBASE_KEY")
if not firebase_key_json:
    print("❌ FIREBASE_KEY not found in environment variables!")
    exit()

# Convert string JSON to dict
try:
    cred_dict = json.loads(firebase_key_json)
    db = firestore.Client.from_service_account_info(cred_dict)
    print("✔ Firestore connected")
except Exception as e:
    print("❌ Firestore error:", e)
    exit()

# -------------------------------
# SCRAPER CONFIG
# -------------------------------
URL = "https://www.betmines.com/football/predictions"
print("🌍 Fetching page:", URL)
response = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"})
soup = BeautifulSoup(response.text, "html.parser")

rows = soup.find_all("tr")
print(f"🔍 Total <tr> rows found: {len(rows)}")

# -------------------------------
# HELPERS
# -------------------------------
def extract_country_code(flag_src):
    """Extract country code from /images/vlajky/gr.gif → 'gr'"""
    if "/vlajky/" in flag_src:
        return flag_src.split("/")[-1].replace(".gif", "")
    return "unknown"

def determine_tip(home_goals, away_goals, confidence):
    """Prediction logic for tip value"""
    total_goals = home_goals + away_goals
    goal_diff = abs(home_goals - away_goals)

    if goal_diff >= 3:
        return "1" if home_goals > away_goals else "2"
    if total_goals >= 4:
        return "Over 2.5"
    if total_goals <= 1:
        return "Under 2.5"
    return "1X2"

# -------------------------------
# MAIN SCRAPER LOOP
# -------------------------------
matches = []
current_flag_code = None

for row in rows:
    tds = [td.get_text(strip=True) for td in row.find_all("td")]
    imgs = row.find_all("img")

    if len(imgs) == 1 and "/vlajky/" in imgs[0].get("src", ""):
        current_flag_code = extract_country_code(imgs[0]["src"])
        continue

    if len(tds) < 13:
        continue

    numbers = re.findall(r"\d+", tds[0])
    if len(numbers) < 2:
        continue

    day, month = numbers[0], numbers[1]
    date_str = f"{day.zfill(2)}-{month.zfill(2)}-2025"

    home_team = tds[2]
    away_team = tds[3]

    try:
        home_goals = int(tds[5])
        away_goals = int(tds[7])
        confidence = int(re.findall(r"\d+", tds[8])[0])
    except:
        continue

    if confidence < 60:
        continue

    tip = determine_tip(home_goals, away_goals, confidence)
    vip = confidence >= 80

    match = {
        "date": date_str,
        "home": home_team,
        "away": away_team,
        "predicted_home_goals": home_goals,
        "predicted_away_goals": away_goals,
        "tip": tip,
        "country_code": current_flag_code,
        "vip": vip,
        "timestamp": firestore.SERVER_TIMESTAMP
    }

    matches.append(match)

# -------------------------------
# FIRESTORE UPLOAD
# -------------------------------
print(f"\n📤 Uploading {len(matches)} matches to Firestore...")
uploaded = 0
for m in matches:
    doc_id = f"{m['date']}-{m['home']}-{m['away']}".replace(" ", "_")
    db.collection("matches").document(doc_id).set(m)
    uploaded += 1

print(f"✔ Uploaded: {uploaded} matches to Firestore")
print("🎉 DONE!")
