import requests
from bs4 import BeautifulSoup
import pandas as pd
from itertools import combinations

ADV_STATS = ["AVG", "OBP", "SLG", "OPS", "wOBA", "wRAA"]
MIN_PA = 6

# Fetch & Clean Functions
def fetch_stats_table(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")
    table = soup.find("table")
    rows = table.find_all("tr")

    headers = [td.text.strip() for td in rows[0].find_all("td")]
    data = [[td.text.strip() for td in row.find_all("td")] for row in rows[1:] if row.find_all("td")]
    df = pd.DataFrame(data, columns=headers)
    return df

def clean_and_calculate(df):
    numeric_cols = ['PA', 'AB', 'H', '2B', '3B', 'HR', 'BB', 'HBP', 'SO']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    df['1B'] = df['H'] - df['2B'] - df['3B'] - df['HR']
    df['TB'] = df['1B'] + 2*df['2B'] + 3*df['3B'] + 4*df['HR']
    df['OBP'] = (df['H'] + df['BB'] + df['HBP']) / (df['AB'] + df['BB'] + df['HBP'])
    df['SLG'] = df['TB'] / df['AB']
    df['OPS'] = df['OBP'] + df['SLG']
    df['BABIP'] = (df['H'] - df['HR']) / (df['AB'] - df['SO'] + 0.0001)
    return df

def get_qualified(df, min_pa):
    df['PA'] = pd.to_numeric(df['PA'], errors='coerce').fillna(0)
    return df[df['PA'] >= min_pa]

# Team Analysis Functions
def display_team_stat_leaders(df, team_name, stat='OPS', min_pa=MIN_PA, top_n=5):
    team_df = get_qualified(df[df["Team"] == team_name], min_pa)
    top_df = team_df.sort_values(by=stat, ascending=False)
    return top_df[['Name', 'PA', 'OBP', 'SLG', 'OPS', 'BABIP']].head(top_n)

def calculate_handedness_score(lineup):
    score = 0
    count = 1
    for i in range(1, len(lineup)):
        prev = lineup.iloc[i - 1]["Bats"]
        curr = lineup.iloc[i]["Bats"]
        if curr == prev:
            count += 1
            score += 1
            if count >= 3:
                score += 1  # extra penalty for 3+ in a row
        else:
            count = 1
    return score

def optimize_for_handedness(lineup, override_spots=None, max_offset=2, max_perf_drop=0.05):
    if override_spots is None:
        override_spots = {}

    best_lineup = lineup.copy()
    best_score = calculate_handedness_score(best_lineup)

    improved = True
    while improved:
        improved = False
        for i, j in combinations(range(len(best_lineup)), 2):
            if i in override_spots.values() or j in override_spots.values():
                continue
            if abs(i - j) > max_offset:
                continue

            swapped = best_lineup.copy()
            swapped.iloc[i], swapped.iloc[j] = swapped.iloc[j].copy(), swapped.iloc[i].copy()

            new_score = calculate_handedness_score(swapped)
            perf_delta = abs(swapped.iloc[i]["batting_value"] - best_lineup.iloc[i]["batting_value"]) + \
                         abs(swapped.iloc[j]["batting_value"] - best_lineup.iloc[j]["batting_value"])

            if new_score < best_score and perf_delta <= max_perf_drop:
                best_lineup = swapped
                best_score = new_score
                improved = True
                break

    return best_lineup

def generate_optimized_batting_order(df, team_name, handedness_dict, override_spots=None, min_pa=MIN_PA):
    if override_spots is None:
        override_spots = {}

    team_df = get_qualified(df[df["Team"] == team_name], min_pa).copy()
    if team_df.empty:
        print(f"\u26a0\ufe0f No qualified players found for {team_name}.")
        return

    team_df["Bats"] = team_df["Name"].apply(lambda name: handedness_dict.get(name, "R"))

    for stat in ADV_STATS:
        max_val = team_df[stat].max()
        team_df[f"{stat}_score"] = team_df[stat] / max_val if max_val > 0 else 0

    team_df["K_rate"] = (team_df["SO"] / team_df["PA"]).fillna(0)
    team_df["contact_score"] = 1 - team_df["K_rate"]

    team_df["batting_value"] = (
        0.22 * team_df["OBP_score"] +
        0.18 * team_df["SLG_score"] +
        0.15 * team_df["OPS_score"] +
        0.15 * team_df["wRAA_score"] +
        0.15 * team_df["wOBA_score"] +
        0.10 * team_df["AVG_score"] +
        0.05 * team_df["contact_score"]
    )

    lineup = team_df.sort_values(by="batting_value", ascending=False).reset_index(drop=True)

    if override_spots:
        fixed = lineup[lineup["Name"].isin(override_spots.keys())].copy()
        floating = lineup[~lineup["Name"].isin(override_spots.keys())].copy()

        fixed["Forced Index"] = fixed["Name"].map(override_spots)
        fixed = fixed.sort_values("Forced Index")

        available_idxs = [i for i in range(len(lineup)) if i not in override_spots.values()]
        floating = floating.sort_values("batting_value", ascending=False).reset_index(drop=True)
        floating["Forced Index"] = available_idxs

        lineup = pd.concat([fixed, floating]).sort_values("Forced Index").reset_index(drop=True)

    lineup["Batting Order"] = [f"{i+1}" for i in range(len(lineup))]

    lineup = optimize_for_handedness(lineup, override_spots)

    round_cols = ["AVG", "OBP", "SLG", "OPS", "wOBA", "wRAA", "K_rate"]
    lineup[round_cols] = lineup[round_cols].round(3)

    return lineup
