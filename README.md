# 🚀 Quick Start (GitHub Codespaces)

This CLI application scrapes and analyzes player stats from the Capital of Texas Baseball League website.

## ⚾️ Get Started (No coding needed!)

1. Click the **Code** button above  
2. Under **Codespaces**, select **Create codespace on “main”**  
3. Wait ~1 minute for setup  
4. Open the **Terminal** (menu ▶️ **Terminal** ▶️ **New Terminal**)  


## ▶️ Running The ClI
   ```bash
   python cli.py
   ```

This will display the top-level menu: 
    ```sql
    Usage: cli.py [OPTIONS] COMMAND [ARGS]...

    CTBL League Stats Toolkit.

    Commands:
    team-leaders   Show top N stat leaders per team.
    batting-order  Generate optimized batting order for ABC.
    plot-leaders   Plot league-wide stat leaders.
    ```

# 📊 Examples:
- Show team leaders (pick a team, then see top 10 by each stat):
    ```bash 
    python cli.py team-leaders
    ```
- Generate batting order for “Austin Baseball Club”:
    ```bash 
    python cli.py batting-order
    ```
- Plot league leaders (choose a stat to chart):
    ```bash 
    python cli.py plot-leaders
    ```