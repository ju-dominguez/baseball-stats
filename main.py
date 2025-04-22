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

TEAM_LIST = [
    "Austin Baseball Club",
    "Austin Mudcats",
    "Austin Reds",
    "ATX Thunder",
    "Charros",
    "Chupacabras",
    "Devil Rays",
    "Pilots",
    "Rebels",
    "Villain",
    "Zephyrs"
]

def choose_team_and_show(df):
    # Build a mapping 1→team, 2→team… N→team
    options = {str(i+1): team for i, team in enumerate(TEAM_LIST)}
    options[str(len(TEAM_LIST)+1)] = None  # Exit option

    while True:
        print("\nChoose a team:")
        for key, team in options.items():
            label = team or "Exit"
            print(f"{key}: {label}")

        choice = input(f"Enter your choice (1-{len(options)}): ").strip()
        team = options.get(choice)
        if team is None:
            print("Returning to main menu.")
            break
        elif team:
            display_team_stat_leaders(df, team, ADV_STATS, MIN_PA)
        else:
            print("Invalid choice, try again.")


def main():
    # 1. Scrape
    df = scrape_league_stats(BASE_URL)

    # 2. Clean & convert
    df = clean_and_convert(df)

    while True:
        print("\nChoose an option:")
        print("1. Display team stat leaders")
        print("2. Generate Optimized Batting Order (ABC Only)")
        print("3. Exit")

        choice = input("Enter your choice (1-3): ")

        if choice == '1':
            choose_team_and_show(df)

        elif choice == '2':
            while True: 
                generate_optimized_batting_order(df, "Austin Baseball Club", handedness, override_spots, MIN_PA)
                break 

        elif choice == '3':
            print("Goodbye!")
            break
        
        else:
            print("Invalid choice. Try again")

if __name__ == "__main__":
    main()
