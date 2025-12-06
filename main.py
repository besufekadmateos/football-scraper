import requests
from bs4 import BeautifulSoup
import datetime
import re
import firebase_admin
from firebase_admin import credentials, firestore

# --- FIREBASE SETUP ---
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

print("🔎 Starting fixed scraper...")

url = "https://www.vitibet.com/index.php?clanek=quicktips&sekce=fotbal&lang=en"
headers = {"User-Agent": "Mozilla/5.0"}
response = requests.get(url, headers=headers)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")
tables = soup.find_all("table")

final_matches = []
current_year = datetime.datetime.now().year

current_league = "Unknown"
current_country_code = "Unknown"

for table in tables:
    rows = table.find_all("tr")

    for row in rows:

        # ----------- LEAGUE HEADER ----------- #
        if "odseknutiligy" in row.get("class", []):
            a = row.find("a")
            img = row.find("img")

            if a and img:
                src = img.get("src")  # ./images/vlajky/gr.gif
                code = src.split("/")[-1].replace(".gif", "").lower()

                current_country_code = code
                current_league = a.get_text(strip=True)

            continue

        cols = [c.get_text(strip=True) for c in row.find_all("td")]

        if len(cols) < 13:
            continue

        # ----------- DATE + HOME TEAM FIX ----------- #
        # Example: "06.12St. Johnstone"
        cell0 = cols[0]

        # Extract date
        nums = re.findall(r"\d+", cell0)
        if len(nums) < 2:
            continue

        day = nums[0]
        month = nums[1]
        date = f"{current_year}-{month.zfill(2)}-{day.zfill(2)}"

        # Remove date from front → get home team
        # Remove "06" and "12" from beginning
        home_team = cell0.replace(day, "", 1).replace(month, "", 1)
        home_team = home_team.replace(".", "", 1).strip()

        # Away team
        away_team = cols[3].strip()

        # ----------- SCORES ----------- #
        try:
            h = int(cols[5])
            a = int(cols[7])
        except:
            continue

        total_goals = h + a

        # ----------- CONFIDENCE FIX ----------- #
        # Example: "66 %xxxxxxxxxxxxx"
        conf_raw = cols[8]
        conf_nums = re.findall(r"\d+", conf_raw)
        if not conf_nums:
            continue
        confidence_int = int(conf_nums[0])

        if confidence_int < 60:
            continue

        vip = confidence_int >= 80

        # ----------- TIP LOGIC ----------- #
        if h - a >= 3:
            tip = "1"
        elif a - h >= 3:
            tip = "2"
        else:
            if total_goals >= 4:
                tip = "Over 2.5"
            elif total_goals <= 1:
                tip = "Under 2.5"
            else:
                tip = cols[11]

        # ----------- SAVE MATCH ----------- #
        match_data = {
            "date": date,
            "league": current_league,
            "league_country_code": current_country_code,
            "team_home": home_team,
            "team_away": away_team,
            "tip": tip,
            "vip": vip
        }

        final_matches.append(match_data)

# ---- UPLOAD TO FIRESTORE ---- #
uploaded = 0
for match in final_matches:
    db.collection("matches").add(match)
    uploaded += 1

print("\n✔ Uploaded:", uploaded, "matches to Firestore")
print("📌 Done!")
