import os
import re
import sys
import time
import requests
import pandas as pd
from datetime import datetime

# 1. Preferred FBS Abbreviations (138 Teams + Aliases)
TEAM_MAP = {
    "Air Force": "AF", "Akron": "Akr", "Appalachian State": "App", "Arizona": "Ariz",
    "Arkansas": "Ark", "Arkansas State": "ArkSt", "Army": "Army", "Auburn": "Aub",
    "Arizona State": "AzSt", "Boston College": "BC", "Bowling Green": "BGSU", "BYU": "BYU",
    "Ball State": "Ball", "Alabama": "Bama", "Baylor": "Bayl", "Boise State": "Boise",
    "Buffalo": "Buff", "Central Michigan": "C Mi", "California": "Cal", "Cincinnati": "Cin",
    "Clemson": "Clem", "Coastal Carolina": "CoCar", "Colorado State": "ColSt", "Colorado": "Colo",
    "Duke": "Duke", "Eastern Michigan": "E Mi", "East Carolina": "ECU", "FIU": "FLInt",
    "Florida Atlantic": "FlAtl", "Florida": "Fla", "Florida State": "FlaSt", "Fresno State": "Fres",
    "Georgia State": "GASt", "Georgia Tech": "GATec", "Georgia Southern": "GaSo", "Hawai'i": "Hawaii",
    "Houston": "Hou", "Iowa State": "IASt", "Illinois": "Ill", "Indiana": "Ind",
    "Iowa": "Iowa", "James Madison": "JMU", "Jacksonville State": "JacSt", "Kansas State": "K St",
    "Kentucky": "KY", "Kansas": "Kan", "Kennesaw State": "KennSt", "Kent State": "Kent",
    "LSU": "LSU", "Louisiana Tech": "LT", "Liberty": "Lib", "Louisville": "Lou",
    "Maryland": "MD", "Minnesota": "MIN", "Michigan State": "MSU", "Marshall": "Marsh",
    "Memphis": "Mem", "Miami": "MiaFL", "Miami (OH)": "MiaOH", "Michigan": "Mich",
    "Middle Tennessee": "MidTN", "Ole Miss": "Miss", "Mississippi State": "MissSt", "Missouri": "Mizzou",
    "Missouri State": "MoSt", "NC State": "NCSt", "Notre Dame": "ND", "Nevada": "NEV",
    "Northern Illinois": "NIU", "New Mexico": "NM", "New Mexico State": "NMS", "Northwestern": "NW",
    "Navy": "Navy", "Nebraska": "Neb", "North Texas": "NorTx", "Old Dominion": "OD",
    "Ohio State": "OSU", "Ohio": "Ohio", "Oklahoma State": "OkSt", "Oklahoma": "Okla",
    "Oregon State": "OreSt", "Oregon": "Oreg", "Penn State": "PSU", "Pittsburgh": "Pitt",
    "Purdue": "Pur", "Rice": "Rice", "Rutgers": "Rut", "South Carolina": "SCar",
    "San Diego State": "SDSU", "San José State": "SJSU", "SMU": "SMU", "Southern Miss": "SMiss",
    "Sam Houston": "SamHu", "South Alabama": "SoAl", "South Florida": "SoFL", "Stanford": "Stan",
    "Syracuse": "Syr", "TCU": "TCU", "Temple": "Tem", "Tennessee": "Tenn",
    "Texas": "Tex", "Toledo": "Toled", "Troy": "Troy", "Tulane": "Tul",
    "Tulsa": "Tuls", "Texas A&M": "TxAM", "Texas State": "TxSt", "Texas Tech": "TxTch",
    "UAB": "UAB", "UCF": "UCF", "UCLA": "UCLA", "UConn": "UConn",
    "Delaware": "UD", "Georgia": "UGA", "Louisiana": "ULLaf", "UL Monroe": "ULMon",
    "UMass": "UMass", "North Carolina": "UNC", "Charlotte": "UNCC", "UNLV": "UNLV",
    "USC": "USC", "UTEP": "UTEP", "UTSA": "UTSA", "Virginia": "UVA",
    "Utah State": "UtSt", "Utah": "Utah", "Virginia Tech": "VaTec", "Vanderbilt": "Vand",
    "Western Kentucky": "W Ky", "West Virginia": "WVU", "Washington State": "WaSt", "Wake Forest": "Wake",
    "Washington": "Wash", "Western Michigan": "WestMI", "Wisconsin": "Wisc", "Wyoming": "Wyo",
    "Sacramento State": "SacSt", "North Dakota State": "NDSU",

    # Name variants
    "App State": "App", "Miami (FL)": "MiaFL", "Miami FL": "MiaFL", "Miami (OH)": "MiaOH",
    "San Jose State": "SJSU", "Hawaii": "Hawaii", "UL Monroe": "ULMon", "Louisiana Monroe": "ULMon",
    "Louisiana-Lafayette": "ULLaf", "North Carolina State": "NCSt", "Massachusetts": "UMass",
    "Connecticut": "UConn", "Florida International": "FLInt", "Middle Tennessee State": "MidTN"
}

NORM_TEAM_MAP = {re.sub(r'[^a-z0-9]', '', k.lower()): v for k, v in TEAM_MAP.items()}

def resolve_team(name: str) -> str:
    if not name: return ""
    clean = re.sub(r'[^a-z0-9]', '', str(name).lower())
    return NORM_TEAM_MAP.get(clean, "")

def clean_key(text: str) -> str:
    if not text: return ""
    text = str(text).lower()
    text = re.sub(r'\b(jr|sr|ii|iii|iv|v)\b', '', text)
    return re.sub(r'[^a-z0-9]', '', text).strip()

def parse_skill_position(play_type: str, is_rush: bool) -> str:
    return "RB" if is_rush else "WR"

def main():
    api_key = os.environ.get("CFBD_API_KEY")
    if not api_key:
        print("ERROR: CFBD_API_KEY environment variable is missing.")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {api_key}"}
    season = int(os.environ.get("CFB_SEASON", datetime.now().year))
    base_url = "https://api.collegefootballdata.com"

    # Schema output
    out_cols = [
        'week', 'team', 'player_id', 'player_name', 'position',
        'rz_rush_att', 'rz_targets', 'match_key', 'alt_key'
    ]
    os.makedirs('data', exist_ok=True)
    out_path = os.path.join('data', 'redzone_weekly.csv')

    # Get current calendar / completed weeks from CFBD
    print(f"Fetching season calendar for {season}...")
    cal_resp = requests.get(f"{base_url}/calendar?year={season}", headers=headers)
    
    # If the calendar isn't returned, fallback to checking weeks 1 through 15
    if cal_resp.status_code == 200 and cal_resp.json():
        weeks_to_check = [w['week'] for w in cal_resp.json() if datetime.fromisoformat(w['firstGameStart'].replace('Z', '+00:00')) <= datetime.now().astimezone()]
    else:
        weeks_to_check = list(range(1, 16))

    if not weeks_to_check:
        weeks_to_check = [1]

    print(f"Processing Red Zone plays for weeks: {weeks_to_check}")
    records = []

    for wk in weeks_to_check:
        print(f"Querying Week {wk} plays...")
        url = f"{base_url}/plays?year={season}&week={wk}&seasonType=both"
        resp = requests.get(url, headers=headers)
        
        if resp.status_code != 200:
            print(f"Warning: Week {wk} returned status {resp.status_code}")
            continue

        plays = resp.json()
        if not plays:
            continue

        for p in plays:
            # Filter for Red Zone (yardline <= 20)
            # In CFBD: yardLine is distance to goal line
            yd = p.get('yardLine') or p.get('yardline')
            if yd is None or yd > 20 or yd <= 0:
                continue

            offense = resolve_team(p.get('offense'))
            if not offense:
                continue

            p_type = p.get('playType', '')
            p_text = p.get('playText', '')

            # 1. Red Zone Rush Plays
            if 'Rush' in p_type or 'Run' in p_type:
                if any(x in p_type for x in ['Sack', 'Kneel', 'Fumble Recovery (Own)']):
                    continue
                
                # CFBD provides rusher name or parsed player tags
                rusher = p.get('rusher')
                if not rusher:
                    m = re.search(r'([A-Z][a-zA-Z\.\'\-]+(?:\s+[A-Z][a-zA-Z\.\'\-]+)+)\s+run', p_text)
                    if m: rusher = m.group(1)

                if rusher:
                    records.append({
                        'week': wk,
                        'team': offense,
                        'player_id': '',
                        'player_name': rusher.strip(),
                        'position': 'RB',
                        'type': 'rush'
                    })

            # 2. Red Zone Pass Targets
            elif 'Pass' in p_type:
                if 'Sack' in p_type or 'Spike' in p_type:
                    continue

                receiver = p.get('receiver') or p.get('target')
                if not receiver:
                    m = re.search(r'to\s+([A-Z][a-zA-Z\.\'\-]+(?:\s+[A-Z][a-zA-Z\.\'\-]+)+)', p_text)
                    if m: receiver = m.group(1)

                if receiver:
                    records.append({
                        'week': wk,
                        'team': offense,
                        'player_id': '',
                        'player_name': receiver.strip(),
                        'position': 'WR',
                        'type': 'target'
                    })

        time.sleep(0.2)  # Respect CFBD rate pacing

    df = pd.DataFrame(records)
    if df.empty:
        print("No red zone records found. Writing empty schema CSV.")
        pd.DataFrame(columns=out_cols).to_csv(out_path, index=False)
        return

    # Aggregate by player-week
    agg = df.groupby(['week', 'team', 'player_id', 'player_name', 'position', 'type']).size().unstack(fill_value=0).reset_index()
    if 'rush' not in agg.columns: agg['rush'] = 0
    if 'target' not in agg.columns: agg['target'] = 0

    agg.rename(columns={'rush': 'rz_rush_att', 'target': 'rz_targets'}, inplace=True)

    # Primary & Secondary Keys
    agg['match_key'] = agg.apply(lambda r: f"{clean_key(r['player_name'])}{clean_key(r['team'])}{clean_key(r['position'])}", axis=1)
    agg['alt_key'] = agg.apply(lambda r: f"{clean_key(r['player_name'])}{clean_key(r['team'])}", axis=1)

    agg = agg[out_cols].sort_values(by=['week', 'team', 'rz_rush_att'], ascending=[True, True, False])
    agg.to_csv(out_path, index=False)
    print(f"SUCCESS: Exported {len(agg)} red zone records to {out_path}")

if __name__ == '__main__':
    main()
