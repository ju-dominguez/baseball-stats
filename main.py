from ctbl_scraper import (
    fetch_stats_table,
    clean_and_calculate,
    display_team_stat_leaders,
    generate_optimized_batting_order
)

# Constants
URL = "https://www.capitaloftexasbaseball.org/teams/default.asp?p=stats&bsort=plateappearances&u=CTBL&s=baseball"
TEAM_NAME = "Austin Baseball Club"
MIN_PA = 10

handedness = {
    'King, Demarcus': 'L',
    'Cho, Jason': 'L',
    'Manzo, Joel': 'L',
    'Hedrick, Paul': 'S'
}

override_spots = {
    'King, Demarcus': 0,  # Force to Leadoff
    'Hedrick, Paul': 3,   # Force to Cleanup
    'Cho, Jason': 6,      # Force to 7th
}

def main():
    print("\U0001F4CA Fetching league data...")
    df = fetch_stats_table(URL)
    df = clean_and_calculate(df)

    print(f"\n\U0001F3C6 Top {TEAM_NAME} Players by OPS:\n")
    top_df = display_team_stat_leaders(df, TEAM_NAME)
    print(top_df)

    print(f"\n\U0001F9E2 Optimized Batting Order for {TEAM_NAME} (with handedness + override spots):\n")
    lineup_df = generate_optimized_batting_order(df, TEAM_NAME, HANDEDNESS, OVERRIDE_SPOTS, MIN_PA)
    if lineup_df is not None:
        print(lineup_df[["Batting Order", "Bats", "Name", "AVG", "OBP", "SLG", "OPS"]].to_string(index=False))

if __name__ == "__main__":
    main()
