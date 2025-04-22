import requests
from bs4 import BeautifulSoup
import pandas as pd
import matplotlib.pyplot as plt
from itertools import combinations

# — Configuration —
PARAMS       = {"p":"stats","bsort":"plateappearances","u":"CTBL","s":"baseball"}
MAX_PAGES    = 10
IDENTITY_COLS= ["Name","Team"]
ADV_STATS    = ["AVG","OBP","SLG","OPS","wOBA","wRAA"]
MIN_PA       = 10

def get_qualified(df, min_pa=MIN_PA):
    return df[df["PA"] >= min_pa]

def scrape_league_stats(base_url, params=PARAMS, max_pages=MAX_PAGES):
    """Fetch up to `max_pages` of CTBL stats into a DataFrame."""
    records, headers = [], None
    for page in range(1, max_pages+1):
        p = params.copy()
        if page>1: p["bpageNum"] = page
        print(f"🔍 Fetching page {page}…")
        r = requests.get(base_url, params=p)
        soup = BeautifulSoup(r.content, "html.parser")
        tbl  = soup.find("table")
        if not tbl: break

        rows = tbl.find_all("tr")
        if not headers:
            ths = tbl.find_all("th")
            if ths:
                headers = [th.get_text(strip=True) for th in ths]
            else:
                headers = [td.get_text(strip=True) for td in rows[0].find_all("td")]

        for tr in rows[1:]:
            vals = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(vals)==len(headers):
                records.append(vals)

        # stop early if no valid rows this page
        if not any(len(tr.find_all("td"))==len(headers) for tr in rows[1:]):
            break

    return pd.DataFrame(records, columns=headers) if records else pd.DataFrame(columns=headers)

def clean_and_convert(df, identity_cols=IDENTITY_COLS):
    """Zero-fill '-' or '' and convert all non-ID cols to numeric."""
    df = df.copy().replace({"-":0,"":0})
    for c in df.columns:
        if c not in identity_cols:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df

def compute_stats(df, woba_scale=1.15, min_pa=MIN_PA):
    """Add wOBA, wRAA, and traditional AVG/OBP/SLG/OPS."""
    m = df.copy()
    # singles, TB
    m["1B"] = m["H"] - m["2B"] - m["3B"] - m["HR"]
    m["TB"] = m["1B"] + 2*m["2B"] + 3*m["3B"] + 4*m["HR"]

    # wOBA
    num = (0.69*m["BB"] + 0.72*m["HBP"] + 0.89*m["1B"]
         + 1.27*m["2B"] + 1.62*m["3B"] + 2.10*m["HR"])
    den = (m["AB"] + m["BB"] + m["HBP"]).replace(0, pd.NA)
    m["wOBA"] = num.div(den)

    league_woba = m.loc[m["PA"]>=min_pa, "wOBA"].mean()
    m["wRAA"] = ((m["wOBA"] - league_woba)/woba_scale) * m["PA"]

    # traditional metrics
    m["AVG"] = m["H"].div(m["AB"].replace(0,pd.NA))
    m["OBP"] = m[["H","BB","HBP"]].sum(axis=1).div(
               m[["AB","BB","HBP"]].sum(axis=1).replace(0,pd.NA))
    m["SLG"] = m["TB"].div(m["AB"].replace(0,pd.NA))
    m["OPS"] = m["OBP"] + m["SLG"]

    return m, league_woba

def display_team_stat_leaders(df, team_name, stat_cols, min_pa=MIN_PA, top_n=10):
    """
    1) Recompute all metrics on the cleaned DataFrame
    2) Force‑cast each stat column to float
    3) Filter to that team & min PA
    4) Use .nlargest on true floats
    """
    # 1) get back a DataFrame with numeric metrics
    dfm, _ = compute_stats(df)

    # 2) coerce each stat into a float column
    for stat in stat_cols:
        dfm[stat] = pd.to_numeric(dfm[stat], errors="coerce")

    # 3) only players on this team with PA >= threshold
    team_df = dfm[(dfm["Team"] == team_name) & (dfm["PA"] >= min_pa)]
    if team_df.empty:
        print(f"⚠️ No qualified players for '{team_name}'\n")
        return

    # 4) now that stat cols are floats, nlargest will work
    for stat in stat_cols:
        print(f"\n🏆 Top {top_n} {team_name} by {stat}:")
        leaders = team_df.nlargest(top_n, stat)[["Name", "PA", stat]]
        print(leaders.to_string(index=False, float_format="%.3f"))

def plot_leaderboard(df, stat, min_pa=MIN_PA, top_n=10):
    """Bar-plot: top_n league leaders for stat."""
    dfm, _ = compute_stats(df)
    dfm[stat] = pd.to_numeric(dfm[stat], errors="coerce")
    leaders = dfm[dfm["PA"] >= min_pa] \
                 .nlargest(top_n, stat)

    colors = ["orange"] + ["gray"] * (len(leaders) - 1)
    plt.figure(figsize=(10,5))
    plt.barh(leaders["Name"], leaders[stat], color=colors)
    plt.gca().invert_yaxis()
    plt.title(f"Top {top_n} by {stat}")
    plt.xlabel(stat)
    plt.tight_layout()
    plt.show()

def calculate_handedness_score(lineup):
    """Penalty for consecutive same‐side batters (+1 extra at 3+ in a row)."""
    bats = lineup["Bats"].tolist()
    score = count = 0
    prev = None
    for curr in bats:
        if curr==prev:
            count+=1
            score+=1 + (1 if count>=2 else 0)
        else:
            count=0
        prev=curr
    return score

def optimize_for_handedness(lineup, override_spots=None, max_offset=2, max_perf_drop=0.05):
    """Greedy adjacent swaps to reduce handedness score within perf threshold."""
    if override_spots is None: override_spots={}
    best, best_score = lineup.copy(), calculate_handedness_score(lineup)
    improved = True
    while improved:
        improved=False
        for i,j in combinations(range(len(best)),2):
            if abs(i-j)>max_offset or i in override_spots.values() or j in override_spots.values():
                continue
            tmp = best.copy()
            tmp.iloc[[i,j]] = tmp.iloc[[j,i]].values
            perf_drop = (abs(tmp.at[i,"batting_value"]-best.at[i,"batting_value"])
                       + abs(tmp.at[j,"batting_value"]-best.at[j,"batting_value"]))
            sc = calculate_handedness_score(tmp)
            if sc<best_score and perf_drop<=max_perf_drop:
                best, best_score, improved = tmp, sc, True
                break
    return best

def generate_optimized_batting_order(df, team_name, handedness, override_spots=None, min_pa=MIN_PA):
    """Composite-value sort → apply overrides → optimize for handedness → print."""
    dfm, _ = compute_stats(df)
    team = get_qualified(dfm[dfm["Team"]==team_name], min_pa).copy()
    if team.empty:
        print(f"⚠️ No qualified players for '{team_name}'\n")
        return

    # assign handedness
    team["Bats"] = team["Name"].map(handedness).fillna("R")
    # normalize scores
    for stat in ADV_STATS:
        mx = team[stat].max()
        team[f"{stat}_score"] = team[stat].div(mx if mx>0 else pd.NA).fillna(0)
    team["contact_score"] = 1 - team["SO"].div(team["PA"].replace(0,pd.NA))

    # composite batting_value
    weights = {
        "OBP_score":0.22, "SLG_score":0.18, "OPS_score":0.15,
        "wRAA_score":0.15, "wOBA_score":0.15, "AVG_score":0.10,
        "contact_score":0.05
    }
    team["batting_value"] = sum(team[k]*w for k,w in weights.items())

    lineup = team.sort_values("batting_value",ascending=False).reset_index(drop=True)
    
    # 1) fix override assignment via .loc on explicit copies:
    if override_spots:
        fixed    = lineup[lineup["Name"].isin(override_spots)].copy()
        floating = lineup[~lineup["Name"].isin(override_spots)].copy()

        fixed.loc[:, "Order"]    = fixed["Name"].map(override_spots)
        available_idxs = [i for i in range(len(lineup)) if i not in override_spots.values()]
        floating.loc[:, "Order"] = available_idxs

        lineup = pd.concat([fixed, floating]) \
                    .sort_values("Order") \
                    .reset_index(drop=True)

    # 2) assign batting order number
    lineup.loc[:, "Batting Order"] = lineup.index + 1

    # 3) round your numeric columns
    round_cols = ADV_STATS
    lineup.loc[:, round_cols] = lineup[round_cols].round(3)

    # 4) print without float_format
    display_cols = ["Batting Order","Bats","Name"] + ADV_STATS
    print("\n⚾️ Optimized Batting Lineup:")
    print(lineup[display_cols].to_string(index=False))

    # bench
    if len(lineup) > 9:
        print("\n🪑 Bench Players:")
        print(lineup.iloc[9:][display_cols].to_string(index=False))

    return lineup