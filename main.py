from ctbl_scraper import (
    scrape_league_stats,
    clean_and_convert,
    display_team_stat_leaders,
    generate_optimized_batting_order,
    plot_leaderboard
)

# — Configuration —
BASE_URL      = "https://www.capitaloftexasbaseball.org/teams/default.asp"
TEAM_LIST     = [
    "Austin Baseball Club", "Austin Mudcats", "Austin Reds", "ATX Thunder",
    "Charros", "Chupacabras", "Devil Rays", "Pilots", "Rebels", "Villain", "Zephyrs"
]
ADV_STATS     = ["AVG", "OBP", "SLG", "OPS", "wOBA", "wRAA"]
MIN_PA        = 10
HAND_DICT     = {
    'King, Demarcus': 'L',
    'Cho, Jason':    'L',
    'Manzo, Joel':   'L',
    'Hedrick, Paul': 'S'
}
OVERRIDE_SPOTS = {
    'King, Demarcus': 1,  # leadoff
    'Hedrick, Paul':  4,  # cleanup
    'Cho, Jason':     7   # 7th
}

def choose_team_and_show(df):
    opts = {str(i+1): team for i, team in enumerate(TEAM_LIST)}
    opts[str(len(TEAM_LIST)+1)] = None
    while True:
        print("\nSelect a team:")
        for k, v in opts.items():
            print(f"{k}: {v or 'Back'}")
        c = input("> ").strip()
        if c not in opts:
            print("❌ Invalid choice.")
        elif opts[c] is None:
            break
        else:
            display_team_stat_leaders(df, opts[c], ADV_STATS, MIN_PA)

def choose_and_plot(df):
    opts = {str(i+1): stat for i, stat in enumerate(ADV_STATS)}
    opts[str(len(ADV_STATS)+1)] = None
    while True:
        print("\nSelect stat to plot:")
        for k, v in opts.items():
            print(f"{k}: {v or 'Back'}")
        c = input("> ").strip()
        if c not in opts:
            print("❌ Invalid choice.")
        elif opts[c] is None:
            break
        else:
            plot_leaderboard(df, opts[c], MIN_PA)

MAIN_MENU = {
    "1": ("Team Stat Leaders", lambda df: choose_team_and_show(df)),
    "2": ("Optimized Batting Order (ABC)", 
          lambda df: generate_optimized_batting_order(df, TEAM_LIST[0], HAND_DICT, OVERRIDE_SPOTS, MIN_PA)),
    "3": ("Plot League Leaders", lambda df: choose_and_plot(df)),
    "4": ("Exit", None),
}

def main():
    # 1) Scrape & clean
    df_raw = scrape_league_stats(BASE_URL)
    if df_raw.empty:
        print("⚠️ No data fetched. Exiting.")
        return
    df = clean_and_convert(df_raw)

    # 2) Main loop
    while True:
        print("\nMain Menu:")
        for key, (label, _) in MAIN_MENU.items():
            print(f"{key}) {label}")
        choice = input("> ").strip()

        if choice == "4":
            print("👋 Goodbye!")
            break

        action = MAIN_MENU.get(choice, (None, None))[1]
        if action:
            action(df)
        else:
            print("❌ Invalid choice.")

if __name__ == "__main__":
    main()
