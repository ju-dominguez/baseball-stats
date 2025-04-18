from ctbl_scraper import (
    scrape_league_stats,
    clean_and_convert,
    display_team_stat_leaders,
    generate_optimized_batting_order
)

# Constants
BASE_URL = "https://www.capitaloftexasbaseball.org/teams/default.asp"
TEAM_NAME = "Austin Baseball Club"
ADV_STATS = ["AVG", "OBP", "SLG", "OPS", "wOBA", "wRAA"]
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
    # 1. Scrape
    df = scrape_league_stats(BASE_URL)

    # 2. Clean & convert
    df = clean_and_convert(df)

    # 3. Display team stat leaders
    display_team_stat_leaders(df, TEAM_NAME, ADV_STATS, MIN_PA)

    # 4. Display optimized batting order
    generate_optimized_batting_order(df, TEAM_NAME, handedness, override_spots, MIN_PA)

if __name__ == "__main__":
    main()
