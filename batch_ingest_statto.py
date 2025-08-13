
"""
Batch ingest for Statto → Model Bridge
--------------------------------------
This template loops over multiple games, finds the five CSVs for each game,
and calls the bridge functions to produce model-ready rows. It also concatenates
all games into season-level CSVs.

USAGE (Python):
--------------
1) Save the bridge script as: statto_bridge.py (from the canvas)
2) Put this file in the same folder: batch_ingest_statto.py
3) Organize your data like:

   data/
     2025-07-03_FBA/
       Player Stats vs. Flat Ballers Association 2025-07-03_15-45-00.csv
       Points vs. Flat Ballers Association 2025-07-03_15-45-00.csv
       Passes vs. Flat Ballers Association 2025-07-03_15-45-00.csv
       Defensive Blocks vs. Flat Ballers Association 2025-07-03_15-45-00.csv
       Possessions vs. Flat Ballers Association 2025-07-03_15-45-00.csv
     2025-07-12_SomeTeam/
       ... (same 5 files)

4) Run:
   python batch_ingest_statto.py --root ./data --out ./season_out

This will write:
  - ./season_out/<GAME_ID>/per_player_per_point.csv
  - ./season_out/<GAME_ID>/point_level_summary.csv
  - ./season_out/all_per_player_per_point.csv
  - ./season_out/all_point_level_summary.csv
"""

from __future__ import annotations
import argparse
from pathlib import Path
import sys
import pandas as pd

# Import the bridge module (must be in the same folder or on PYTHONPATH)
try:
    import statto_bridge  # the script from the canvas, save it as statto_bridge.py
except ModuleNotFoundError as e:
    print("ERROR: Could not import 'statto_bridge'.")
    print("Make sure you saved the bridge script as 'statto_bridge.py' in the same directory.")
    sys.exit(1)

def find_game_files(game_dir: Path):
    # Use loose glob patterns so minor name differences still match
    player = next(game_dir.glob("Player Stats vs*.*csv"), None)
    points = next(game_dir.glob("Points vs*.*csv"), None)
    passes = next(game_dir.glob("Passes vs*.*csv"), None)
    blocks = next(game_dir.glob("Defensive Blocks vs*.*csv"), None)
    poss   = next(game_dir.glob("Possessions vs*.*csv"), None)

    missing = []
    if player is None: missing.append("Player Stats vs*.csv")
    if points is None: missing.append("Points vs*.csv")
    if passes is None: missing.append("Passes vs*.csv")
    if blocks is None: missing.append("Defensive Blocks vs*.csv")
    if poss   is None: missing.append("Possessions vs*.csv")

    if missing:
        raise FileNotFoundError(f"Missing files in {game_dir}:\n - " + "\n - ".join(missing))

    return {
        "player": player,
        "points": points,
        "passes": passes,
        "blocks": blocks,
        "poss": poss,
    }

def main():
    ap = argparse.ArgumentParser(description="Batch ingest multiple Statto games into model-ready CSVs")
    ap.add_argument("--root", required=True, help="Root folder containing per-game subfolders (one subfolder per game)")
    ap.add_argument("--out", required=True, help="Output folder for per-game and aggregated CSVs")
    args = ap.parse_args()

    root = Path(args.root)
    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    # Discover game folders (directories with files)
    game_dirs = [p for p in root.iterdir() if p.is_dir()]
    if not game_dirs:
        print(f"No subdirectories found under {root}. Create one folder per game.")
        sys.exit(1)

    all_rows = []
    all_ptsum = []

    for game_dir in sorted(game_dirs):
        game_id = game_dir.name  # folder name becomes the game_id (e.g., 2025-07-03_FBA)
        print(f"Processing {game_id} ...")
        try:
            files = find_game_files(game_dir)
        except FileNotFoundError as e:
            print(str(e))
            continue

        # Load CSVs
        df_player = pd.read_csv(files["player"])
        df_points = pd.read_csv(files["points"])
        df_passes = pd.read_csv(files["passes"])
        df_blocks = pd.read_csv(files["blocks"])
        df_poss   = pd.read_csv(files["poss"])

        # Build per-player-per-point and point-level summaries
        rows, ptsum = statto_bridge.build_per_player_per_point(
            df_player=df_player,
            df_points=df_points,
            df_passes=df_passes,
            df_blocks=df_blocks,
            df_poss=df_poss,
            game_id=game_id,
        )
        # Save per-game outputs
        game_out = out_root / game_id
        game_out.mkdir(parents=True, exist_ok=True)
        rows.to_csv(game_out / "per_player_per_point.csv", index=False)
        ptsum.to_csv(game_out / "point_level_summary.csv", index=False)

        all_rows.append(rows)
        all_ptsum.append(ptsum)

    # Aggregate season-level CSVs
    if all_rows:
        df_all_rows = pd.concat(all_rows, ignore_index=True)
        df_all_ptsum = pd.concat(all_ptsum, ignore_index=True)

        df_all_rows.to_csv(out_root / "all_per_player_per_point.csv", index=False)
        df_all_ptsum.to_csv(out_root / "all_point_level_summary.csv", index=False)

        print("Wrote aggregated CSVs:")
        print(" -", out_root / "all_per_player_per_point.csv")
        print(" -", out_root / "all_point_level_summary.csv")
    else:
        print("No games processed successfully. Check errors above.")

if __name__ == "__main__":
    main()
