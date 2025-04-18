import requests
from bs4 import BeautifulSoup
import pandas as pd
from itertools import combinations
from IPython.display import display

# ========== CONFIGURATION ==========
PARAMS = {
    "p": "stats",
    "bsort": "plateappearances",
    "u": "CTBL",
    "s": "baseball"
}
MAX_PAGES = 10
IDENTITY_COLS = ["Name", "Team"]
ADV_STATS = ["AVG", "OBP", "SLG", "OPS", "wOBA", "wRAA"]
MIN_PA = 10

# ========== HELPERS ==========
def get_qualified(df, min_pa=MIN_PA):
    return df[df["PA"] >= min_pa]

def trim_zero(val):
    if isinstance(val, float):
        return f"{val:.3f}".lstrip("0")
    return val

# ========== SCRAPING & CLEANING ==========
def scrape_league_stats(base_url, params=PARAMS, max_pages=10):
    all_data = []
    page = 1
    print("\U0001F4CA Fetching league data...")

    while page <= max_pages:
        print(f"🔍 Scraping page {page}...")
        if page > 1:
            params["bpageNum"] = page
        else:
            params.pop("bpageNum", None)

        response = requests.get(base_url, params=params)
        soup = BeautifulSoup(response.content, "html.parser")
        table = soup.find("table")

        if not table:
            print("❌ No table found. Stopping.")
            break

        rows = table.find_all("tr")
        if len(rows) < 2:
            print("❌ No data rows. Stopping.")
            break

        # Ensure rows[0] exists before accessing it
        header = None
        if rows:
            header = [td.text.strip() for td in rows[0].find_all("td")]

        data_rows = [
            [td.text.strip() for td in row.find_all("td")]
            for row in rows[1:]
            if header and len(row.find_all("td")) == len(header)
        ]

        if not data_rows:
            print("❌ No valid player rows. Stopping.")
            break

        all_data.extend(data_rows)
        page += 1

    if not all_data:
        print("⚠️ No data scraped. Returning an empty DataFrame.")
        return pd.DataFrame()

    return pd.DataFrame(all_data, columns=header)

def clean_and_convert(df, identity_cols=IDENTITY_COLS):
    cols_to_convert = [col for col in df.columns if col not in identity_cols]
    df.replace({'-': 0, '': 0}, inplace=True)
    df[cols_to_convert] = df[cols_to_convert].apply(pd.to_numeric, errors='coerce')
    return df

# ========== METRIC CALCULATIONS ==========
def calculate_woba_and_wraa(df, woba_scale=1.15, min_pa=MIN_PA):
    df["1B"] = df["H"] - df["2B"] - df["3B"] - df["HR"]
    df["wOBA_numerator"] = (
        0.69 * df["BB"] +
        0.72 * df["HBP"] +
        0.89 * df["1B"] +
        1.27 * df["2B"] +
        1.62 * df["3B"] +
        2.10 * df["HR"]
    )
    df["wOBA_denominator"] = df["AB"] + df["BB"] + df["HBP"]
    df["wOBA"] = df["wOBA_numerator"] / df["wOBA_denominator"]

    qualified = get_qualified(df, min_pa)
    league_woba = qualified["wOBA"].mean()

    df["wRAA"] = ((df["wOBA"] - league_woba) / woba_scale) * df["PA"]
    return df, league_woba

# ========== TEAM ANALYSIS FUNCTIONS ==========
def display_team_stat_leaders(df, team_name, stat_cols, min_pa=MIN_PA, top_n=10):
    calculate_woba_and_wraa(df)
    team_df = df[(df["Team"] == team_name) & (df["PA"] >= min_pa)]
    if team_df.empty:
        print(f"⚠️ No qualified players found for {team_name}.")
        return
    for stat in stat_cols:
        print(f"\n🏆 Top {top_n} on {team_name} by {stat}:")
        leaderboard = team_df.sort_values(by=stat, ascending=False)[["Name", "PA", stat]].head(top_n)
        display(leaderboard)

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

    lineup_df = lineup.iloc[:9].copy()
    bench_df = lineup.iloc[9:].copy()

    stat_cols_trimmed = ["AVG", "OBP", "SLG", "OPS"]

    # Display lineup (top 9)
    print("🧢 Optimized Batting Lineup:")
    print(
        lineup_df[["Batting Order", "Bats", "Name"] + stat_cols_trimmed]
        .to_string(index=False, formatters={col: trim_zero for col in stat_cols_trimmed})
    )

    # Display bench
    if not bench_df.empty:
        print("\n🪑 Bench Players:")
        print(
            bench_df[["Batting Order", "Bats", "Name"] + stat_cols_trimmed]
            .to_string(index=False, formatters={col: trim_zero for col in stat_cols_trimmed})
        )

