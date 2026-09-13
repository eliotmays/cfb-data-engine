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

    # Alternate naming variations
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

def normalize_pos(pos: str) -> str:
    if not pos: return ""
    p = str(pos).upper().strip()
    if p in ['HB', 'FB']: return 'RB'
    return p

def build_roster_index(base_url: str, headers: dict, season: int):
    """Fetches CFBD season roster to resolve official Player IDs and Positions."""
    years_to_try = [season, season - 1]
    roster_data = []

    for yr in years_to_try:
        print(f"Fetching CFBD rosters for {yr}...")
        try:
            resp = requests.get(f"{base_url}/roster?year={yr}", headers=headers, timeout=25)
            if resp.status_code == 200 and resp.json():
                roster_data = resp.json()
                print(f"Loaded {len(roster_data)} rostered players for {yr}.")
                break
        except Exception as e:
            print(f"Warning: Roster request failed for {yr}: {e}")

    full_map = {}
    initial_map = {}

    for p in roster_data:
        team_raw = p.get('team', '')
        team_abbr = resolve_team(team_raw)
        if not team_abbr:
            continue

        p_id = str(p.get('id', '')).strip()
        first = str(p.get('firstName', '')).strip()
        last = str(p.get('lastName', '')).strip()
        full_name = f"{first} {last}".strip()
        pos = normalize_pos(p.get('position', ''))

        c_first = clean_key(first)
        c_last = clean_key(last)
        c_full = clean_key(full_name)
        c_init = f"{c_first[:1]}{c_last}" if c_first else c_last

        player_obj = {
            'player_id': p_id,
            'player_name': full_name,
            'position': pos
        }

        full_map[(c_full, team_abbr)] = player_obj
        initial_map[(c_init, team_abbr)] = player_obj

    return full_map, initial_map

def resolve_player(raw_name: str, team_abbr: str, default_pos: str, full_map: dict, initial_map: dict):
    """Matches text player names against indexed roster records."""
    c_name = clean_key(raw_name)
    key = (c_name, team_abbr)

    if key in full_map:
        res = full_map[key]
        return res['player_id'], res['player_name'], (res['position'] or default_pos)

    if key in initial_map:
        res = initial_map[key]
        return res['player_id'], res['player_name'], (res['position'] or default_pos)

    return "", raw_name.strip(), default_pos

def main():
    api_key = os.environ.get("CFBD_API_KEY")
    if not api_key:
        print("ERROR: CFBD_API_KEY environment variable is missing.")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {api_key}"}
    season = int(os.environ.get("CFB_SEASON", datetime.now().year))
    base_url = "https://api.collegefootballdata.com"

    out_cols = [
        'week', 'team', 'player_id', 'player_name', 'position',
        'rz_rush_att', 'rz_targets', 'match_key', 'alt_key'
    ]
    os.makedirs('data', exist_ok=True)
    out_path = os.path.join('data', 'redzone_weekly.csv')

    # 1. Build Roster Index
    full_map, initial_map = build_roster_index(base_url, headers, season)

    # 2. Define Weeks 0 through 2
    target_weeks = [0, 1, 2]
    print(f"Executing Red Zone touch extraction for season {season} across weeks: {target_weeks}")

    # Regex patterns:
    # Captures: "[Player Name] run/rush ..."
    rush_regex = re.compile(r'([A-Z][a-zA-Z\.\'\-]+(?:\s+[A-Z][a-zA-Z\.\'\-]+)*)\s+(?:run|rush)', re.IGNORECASE)
    
    # Captures completions and incompletions: "to/intended for [Player Name]" stopping before "for/touchdown/comma/period"
    target_regex = re.compile(r'(?:to|intended for)\s+([A-Z][a-zA-Z\.\'\-]+(?:\s+[A-Z][a-zA-Z\.\'\-]+)*?)(?=\s+(?:for|touchdown|td|out of bounds|incomplete|intercepted)|\.|\,|$)', re.IGNORECASE)

    records = []

    for wk in target_weeks:
        print(f"Fetching Week {wk} play-by-play data...")
        url = f"{base_url}/plays?year={season}&week={wk}&seasonType=regular"
        try:
            resp = requests.get(url, headers=headers, timeout=40)
        except Exception as e:
            print(f"Request failed for week {wk}: {e}")
            continue

        if resp.status_code != 200:
            print(f"Week {wk} returned HTTP {resp.status_code}: {resp.text[:200]}")
            continue

        plays = resp.json()
        print(f"Week {wk}: Received {len(plays)} total plays.")

        for p in plays:
            yd = p.get('yardLine') or p.get('yardline')
            if yd is None or yd > 20 or yd <= 0:
                continue

            offense = resolve_team(p.get('offense'))
            if not offense:
                continue

            p_type = p.get('playType', '')
            p_text = p.get('playText', '')

            # A. Red Zone Rush Plays (Excluding sacks, kneels, fumbles)
            if 'Rush' in p_type or 'Run' in p_type:
                if any(x in p_type for x in ['Sack', 'Kneel', 'Fumble Recovery (Own)', 'Safety']):
                    continue

                rusher = p.get('rusher')
                if not rusher:
                    m = rush_regex.search(p_text)
                    if m: rusher = m.group(1).strip()

                if rusher:
                    pid, pname, pos = resolve_player(rusher, offense, 'RB', full_map, initial_map)
                    records.append({
                        'week': wk,
                        'team': offense,
                        'player_id': pid,
                        'player_name': pname,
                        'position': pos,
                        'type': 'rush'
                    })

            # B. Red Zone Targets (Completions & Incompletions)
            elif 'Pass' in p_type:
                if 'Sack' in p_type or 'Spike' in p_type:
                    continue

                receiver = p.get('receiver') or p.get('target')
                if not receiver:
                    m = target_regex.search(p_text)
                    if m: receiver = m.group(1).strip()

                if receiver:
                    pid, pname, pos = resolve_player(receiver, offense, 'WR', full_map, initial_map)
                    records.append({
                        'week': wk,
                        'team': offense,
                        'player_id': pid,
                        'player_name': pname,
                        'position': pos,
                        'type': 'target'
                    })

        time.sleep(0.2)

    df = pd.DataFrame(records)
    if df.empty:
        print("No red zone records found across specified weeks. Writing template CSV.")
        pd.DataFrame(columns=out_cols).to_csv(out_path, index=False)
        return

    # 3. Weekly Rollup
    agg = df.groupby(['week', 'team', 'player_id', 'player_name', 'position', 'type']).size().unstack(fill_value=0).reset_index()
    if 'rush' not in agg.columns: agg['rush'] = 0
    if 'target' not in agg.columns: agg['target'] = 0

    agg.rename(columns={'rush': 'rz_rush_att', 'target': 'rz_targets'}, inplace=True)

    # 4. Generate Match Keys
    agg['match_key'] = agg.apply(lambda r: f"{clean_key(r['player_name'])}{clean_key(r['team'])}{clean_key(r['position'])}", axis=1)
    agg['alt_key'] = agg.apply(lambda r: f"{clean_key(r['player_name'])}{clean_key(r['team'])}", axis=1)

    agg = agg[out_cols].sort_values(by=['week', 'team', 'rz_rush_att', 'rz_targets'], ascending=[True, True, False, False])
    agg.to_csv(out_path, index=False)
    print(f"SUCCESS: Exported {len(agg)} player-week red zone records across Weeks {target_weeks} to {out_path}")

if __name__ == '__main__':
    main()
