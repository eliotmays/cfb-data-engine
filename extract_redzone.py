import os
import re
from datetime import datetime
import pandas as pd

# 1. FBS Team Name to Preferred Abbreviation Mapping (138 Teams)
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
    "Sacramento State": "SacSt", "North Dakota State": "NDSU"
}

def clean_key_text(text: str) -> str:
    """Strips suffixes, punctuation, spaces, and lowers case."""
    if not text or pd.isna(text):
        return ""
    text = str(text).lower()
    # Remove generational and academic suffixes
    text = re.sub(r'\b(jr|sr|ii|iii|iv|v)\b', '', text)
    # Keep only alphanumeric characters
    text = re.sub(r'[^a-z0-9]', '', text)
    return text.strip()

def normalize_pos(pos: str) -> str:
    if not pos or pd.isna(pos):
        return ""
    p = str(pos).upper().strip()
    if p in ['HB', 'FB']:
        return 'RB'
    return p

def main():
    season = datetime.now().year
    pbp_url = f"https://github.com/sportsdataverse/cfbfastR-data/releases/download/pbp/play_by_play_{season}.parquet"
    roster_url = f"https://github.com/sportsdataverse/cfbfastR-data/releases/download/rosters/roster_{season}.parquet"

    print(f"Loading {season} PBP and Roster data from sportsdataverse...")
    try:
        pbp = pd.read_parquet(pbp_url)
        roster = pd.read_parquet(roster_url)
    except Exception as e:
        print(f"Error loading {season} parquet files: {e}")
        return

    # Prepare Roster lookup
    roster['team_abbr'] = roster['team'].map(TEAM_MAP)
    roster = roster.dropna(subset=['team_abbr'])
    roster['norm_pos'] = roster['position'].apply(normalize_pos)
    roster_lookup = roster.drop_duplicates(subset=['athlete_id']).set_index('athlete_id')[['norm_pos', 'name']].to_dict('index')

    # Filter for Red Zone plays (inside the 20, excluding defensive scores/safeties)
    rz = pbp[(pbp['yardline_100'] <= 20) & (pbp['yardline_100'] > 0)].copy()
    rz['team_abbr'] = rz['pos_team'].map(TEAM_MAP)
    rz = rz.dropna(subset=['team_abbr'])

    records = []

    # 1. RZ Rush Attempts (Exclude sacks, kneels, spikes)
    rush_plays = rz[
        (rz['rush'] == 1) & 
        (~rz['play_type'].str.contains('Sack|Kneel|Fumble|Spike', case=False, na=False))
    ]
    for _, row in rush_plays.iterrows():
        p_id = row.get('rush_player_id') or row.get('athlete_id_1')
        p_name = row.get('rusher_player_name')
        if pd.notna(p_name):
            pos = roster_lookup.get(p_id, {}).get('norm_pos', 'RB')
            records.append({
                'season': row['season'],
                'week': row['week'],
                'team': row['team_abbr'],
                'player_id': p_id,
                'player_name': p_name,
                'position': pos,
                'type': 'rush'
            })

    # 2. RZ Pass Targets
    pass_plays = rz[
        (rz['pass'] == 1) & 
        (~rz['play_type'].str.contains('Sack|Spike', case=False, na=False))
    ]
    for _, row in pass_plays.iterrows():
        p_id = row.get('receiver_player_id') or row.get('target_player_id')
        p_name = row.get('receiver_player_name')
        if pd.notna(p_name):
            pos = roster_lookup.get(p_id, {}).get('norm_pos', 'WR')
            records.append({
                'season': row['season'],
                'week': row['week'],
                'team': row['team_abbr'],
                'player_id': p_id,
                'player_name': p_name,
                'position': pos,
                'type': 'target'
            })

    df_records = pd.DataFrame(records)
    if df_records.empty:
        print("No red zone records found for the current filter.")
        return

    # Weekly aggregation
    agg = df_records.groupby(['week', 'team', 'player_id', 'player_name', 'position', 'type']).size().unstack(fill_value=0).reset_index()
    if 'rush' not in agg.columns: agg['rush'] = 0
    if 'target' not in agg.columns: agg['target'] = 0

    agg.rename(columns={'rush': 'rz_rush_att', 'target': 'rz_targets'}, inplace=True)

    # Build primary and secondary cascading match keys
    agg['match_key'] = agg.apply(
        lambda r: f"{clean_key_text(r['player_name'])}{clean_key_text(r['team'])}{clean_key_text(r['position'])}", axis=1
    )
    agg['alt_key'] = agg.apply(
        lambda r: f"{clean_key_text(r['player_name'])}{clean_key_text(r['team'])}", axis=1
    )

    output_cols = [
        'week', 'team', 'player_id', 'player_name', 'position', 
        'rz_rush_att', 'rz_targets', 'match_key', 'alt_key'
    ]
    agg = agg[output_cols].sort_values(by=['week', 'team', 'rz_rush_att'], ascending=[True, True, False])

    os.makedirs('data', exist_ok=True)
    out_path = 'data/redzone_weekly.csv'
    agg.to_csv(out_path, index=False)
    print(f"Successfully exported {len(agg)} player-week records to {out_path}")

if __name__ == '__main__':
    main()
