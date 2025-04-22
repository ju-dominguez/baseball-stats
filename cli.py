# cli.py
import logging
import click
import pandas as pd
from ctbl_scraper import (
    ScraperConfig, StatsConfig,
    CTBLScraper, StatsProcessor
)

# ─── Configuration ─────────────────────────────────────────────────────────────
BASE_URL   = "https://www.capitaloftexasbaseball.org/teams/default.asp"
PARAMS     = {"p":"stats","bsort":"plateappearances","u":"CTBL","s":"baseball"}
TEAM_LIST  = [
    "Austin Baseball Club","Austin Mudcats","Austin Reds","ATX Thunder",
    "Charros","Chupacabras","Devil Rays","Pilots","Rebels","Villain","Zephyrs"
]
HAND_DICT  = {
    'King, Demarcus':'L','Cho, Jason':'L',
    'Manzo, Joel':'L','Hedrick, Paul':'S'
}
OVERRIDE_SPOTS = {'King, Demarcus':0,'Hedrick, Paul':3,'Cho, Jason':6}
ADV_STATS  = ["AVG","OBP","SLG","OPS","wOBA","wRAA"]

# ─── Setup ─────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@click.group()
@click.pass_context
def cli(ctx):
    """CTBL League Stats Toolkit."""
    # bootstrap scraper & processor
    scraper_cfg = ScraperConfig(BASE_URL, PARAMS)
    stats_cfg   = StatsConfig()
    df_raw      = CTBLScraper(scraper_cfg).fetch()
    if df_raw.empty:
        logger.error("No data fetched; exiting.")
        ctx.exit(1)

    processor = StatsProcessor(stats_cfg)
    df_clean  = processor.clean(df_raw)
    ctx.obj   = {"df": df_clean, "proc": processor}

def prompt_menu(options):
    """Generic numbered menu. options: list of (label, callback)."""
    for i, (label, _) in enumerate(options, 1):
        click.echo(f"{i}) {label}")
    click.echo(f"{len(options)+1}) Back")
    choice = click.prompt("Select", type=int)
    return choice - 1  # zero-based

@cli.command()
@click.pass_obj
def team_leaders(obj):
    """Show top N stat leaders per team."""
    df   = obj["df"]
    proc = obj["proc"]

    while True:
        # just build a list of (label, _) pairs — we don't actually use the callback
        opts = [(t, None) for t in TEAM_LIST]
        choice = prompt_menu(opts)
        # “Back” is the last entry
        if choice >= len(TEAM_LIST):
            break

        team = TEAM_LIST[choice]
        # only call compute once
        dfm, _ = proc.compute(df)
        team_df = dfm[
            (dfm["Team"] == team) &
            (dfm["PA"]   >= proc.cfg.min_pa)
        ]
        if team_df.empty:
            click.echo(f"No qualified players for {team}")
            continue

        for stat in ADV_STATS:
            click.echo(f"\n🏆 Top {team} by {stat}:")
            top = team_df.nlargest(10, stat)[["Name", "PA", stat]]
            click.echo(top.to_string(index=False, float_format="%.3f"))


@cli.command()
@click.pass_obj
def batting_order(obj):
    """Generate optimized batting order for ABC."""
    df = obj["df"]
    proc = obj["proc"]
    dfm, _ = proc.compute(df)
    team_df = proc.get_qualified(dfm[dfm["Team"]==TEAM_LIST[0]], proc.cfg.min_pa)
    if team_df.empty:
        click.echo("No qualified ABC players.")
        return

    # map handedness
    team_df["Bats"] = team_df["Name"].map(HAND_DICT).fillna("R")
    # score
    for stat in ADV_STATS:
        mx = team_df[stat].max()
        team_df[f"{stat}_score"] = team_df[stat] / (mx or 1)
    team_df["contact_score"] = 1 - (team_df["SO"] / team_df["PA"].replace(0,1))

    weights = {
        "OBP_score":0.22,"SLG_score":0.18,"OPS_score":0.15,
        "wRAA_score":0.15,"wOBA_score":0.15,"AVG_score":0.10,
        "contact_score":0.05
    }
    team_df["batting_value"] = sum(team_df[k]*w for k,w in weights.items())
    lineup = team_df.sort_values("batting_value", ascending=False).reset_index(drop=True)

    # apply overrides & optimize handedness
    # ... same as before, but using proc.optimize_lineup()
    if OVERRIDE_SPOTS:
        fixed = lineup[lineup["Name"].isin(OVERRIDE_SPOTS)].copy()
        floating = lineup[~lineup["Name"].isin(OVERRIDE_SPOTS)].copy()
        fixed["Order"]    = fixed["Name"].map(OVERRIDE_SPOTS)
        available = [i for i in range(len(lineup)) if i not in OVERRIDE_SPOTS.values()]
        floating["Order"] = available
        lineup = pd.concat([fixed, floating]).sort_values("Order").reset_index(drop=True)

    lineup["Batting Order"] = lineup.index + 1
    lineup[ADV_STATS] = lineup[ADV_STATS].round(3)

    click.echo("\n⚾️ Optimized Batting Lineup:")
    click.echo(lineup.iloc[:9][["Batting Order","Bats","Name"] + ADV_STATS].to_string(index=False))
    if len(lineup)>9:
        click.echo("\n🪑 Bench:")
        click.echo(lineup.iloc[9:][["Batting Order","Bats","Name"]+ADV_STATS].to_string(index=False))

@cli.command()
@click.pass_obj
def plot_leaders(obj):
    """Plot league-wide stat leaders."""
    df = obj["df"]
    proc = obj["proc"]
    while True:
        opts = [(stat, stat) for stat in ADV_STATS]
        choice = prompt_menu(opts)
        if choice >= len(opts):
            break
        stat = opts[choice][1]
        dfm, _ = proc.compute(df)
        leaders = dfm[dfm["PA"]>=proc.cfg.min_pa].nlargest(10, stat)
        # use matplotlib directly here
        import matplotlib.pyplot as plt
        plt.figure(figsize=(8,4))
        plt.barh(leaders["Name"], leaders[stat])
        plt.gca().invert_yaxis()
        plt.title(f"Top 10 by {stat}")
        plt.xlabel(stat)
        plt.tight_layout()
        plt.show()

if __name__ == "__main__":
    cli()
