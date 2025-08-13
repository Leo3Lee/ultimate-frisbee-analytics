"""
Statto → Model Bridge (integrated)
----------------------------------
Builds a per-player-per-point dataset from five Statto CSV exports of a single game:
 1) Player Stats vs. <opponent>.csv         (per-player aggregates; includes "Points played")
 2) Points vs. <opponent>.csv               (per-point outcomes & team context)
 3) Passes vs. <opponent>.csv               (event-level passing, geometry, completion)
 4) Defensive Blocks vs. <opponent>.csv     (event-level blocks)
 5) Possessions vs. <opponent>.csv          (per-possession flow; scoring per possession)

Outputs
-------
 A) per_player_per_point.csv   (model-ready rows)
 B) point_level_summary.csv    (O/D start, score context, possession-derived tags)

Notes
-----
- This script assumes consistent player names across files and that point numbers
  match between tables. If there are mismatches, consider adding a player-name map.
- Where the source lacks a stat (e.g., pulls, time_seconds), the field is filled with 0.
- Goals per receiver are inferred from completed passes flagged as Assist?=1.

CLI usage
---------
python statto_bridge.py \
  --player "Player Stats vs. ...csv" \
  --points "Points vs. ...csv" \
  --passes "Passes vs. ...csv" \
  --blocks "Defensive Blocks vs. ...csv" \
  --poss   "Possessions vs. ...csv" \
  --game_id 2025-07-03_FBA \
  --outdir ./out
"""
from __future__ import annotations
import argparse
import os
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd

# ----------------------------
# Core transformation helpers
# ----------------------------

def _expand_roster_from_player_stats(df_player: pd.DataFrame) -> pd.DataFrame:
    """Expand per-player rows into (Player, Point) rows based on "Points played" list."""
    rows: List[Dict] = []
    for _, row in df_player.iterrows():
        raw = str(row.get("Points played", ""))
        if not raw:
            continue
        for token in raw.split(","):
            token = token.strip()
            if token.isdigit():
                rows.append({"Player": row["Player"], "Point": int(token)})
    return pd.DataFrame(rows, columns=["Player","Point"]).dropna()


def _aggregate_passes(df_passes: pd.DataFrame) -> pd.DataFrame:
    """Return per-player-per-point throwing & catching stats derived from Passes table."""
    # Throwing
    g_throw = df_passes.groupby(["Point","Thrower"], dropna=False)
    throws = g_throw.agg(
        throws=("Thrower", "count"),
        completions=("Turnover?", lambda x: int((x == 0).sum())),
        turnovers=("Turnover?", lambda x: int((x == 1).sum())),
        assists=("Assist?", "sum"),
        secondary_assists=("Secondary assist?", "sum"),
        hucks=("Huck?", "sum"),
        swings=("Swing?", "sum"),
        dumps=("Dump?", "sum"),
        throw_yards=("Forward distance (m)", "sum"),
    ).reset_index().rename(columns={"Thrower": "Player"})

    # Catching (only completed passes count as catches)
    completed = df_passes[df_passes["Turnover?"] == 0]
    g_catch = completed.groupby(["Point","Receiver"], dropna=False)
    catches = g_catch.agg(
        catches=("Receiver", "count"),
        received_yards=("Forward distance (m)", "sum"),
        goals=("Assist?", lambda x: int((x == 1).sum())),  # receiver of an assisted completion scored
    ).reset_index().rename(columns={"Receiver": "Player"})

    # Outer merge to get players who only threw or only caught on a point
    df_actions = pd.merge(throws, catches, on=["Point","Player"], how="outer").fillna(0)
    # Normalize dtypes
    int_cols = ["throws","completions","turnovers","assists","secondary_assists","hucks","swings","dumps","catches","goals"]
    for c in int_cols:
        df_actions[c] = df_actions[c].astype(int)
    for c in ["throw_yards","received_yards"]:
        if c in df_actions:
            df_actions[c] = df_actions[c].astype(float)
    return df_actions


def _aggregate_blocks(df_blocks: pd.DataFrame) -> pd.DataFrame:
    """Per-player-per-point block counts from Defensive Blocks table."""
    if df_blocks.empty:
        return pd.DataFrame(columns=["Point","Player","blocks"])  # empty
    out = df_blocks.groupby(["Point","Player"], dropna=False).size().reset_index(name="blocks")
    out["blocks"] = out["blocks"].astype(int)
    return out


def _build_point_context_with_possessions(df_points: pd.DataFrame, df_poss: pd.DataFrame) -> pd.DataFrame:
    """Attach O/D start, result, score context, and possession-derived tags per point."""
    # Normalize points
    p = df_points[[
        "Point","Started on offense?","Scored?",
        "Our score at pull","Opponent's score at pull",
        "Possessions","Passes","Turnovers","Defensive blocks",
    ]].copy()
    p = p.rename(columns={
        "Our score at pull":"our_score_start",
        "Opponent's score at pull":"opp_score_start",
        "Possessions":"point_possessions_total",
        "Passes":"point_passes_total",
        "Turnovers":"point_turnovers_total",
        "Defensive blocks":"point_blocks_total",
    })
    p["team_line"] = p["Started on offense?"].map({1:"O", 0:"D"})
    p["point_result"] = p["Scored?"]

    # Possession summaries
    possum = df_poss.groupby("Point", dropna=False).agg(
        num_possessions=("Possession", "nunique"),
    ).reset_index()

    first_pos = df_poss.sort_values(["Point","Possession"]).groupby("Point", dropna=False).first().reset_index()
    first_pos = first_pos[["Point","Scored?"]].rename(columns={"Scored?":"first_possession_scored"})

    any_pos_scored = df_poss.groupby("Point", dropna=False)["Scored?"].max().reset_index().rename(columns={"Scored?":"any_possession_scored"})

    ctx = p.merge(possum, on="Point", how="left")\
           .merge(first_pos, on="Point", how="left")\
           .merge(any_pos_scored, on="Point", how="left")

    # Fill NaNs for points with missing possession rows
    for c in ["num_possessions","first_possession_scored","any_possession_scored"]:
        ctx[c] = ctx[c].fillna(0)

    # Tags
    soff = ctx["Started on offense?"] == 1
    scored = ctx["point_result"] == 1
    num_pos = ctx["num_possessions"].astype(int)

    ctx["clean_hold"] = ((soff) & (scored) & (num_pos == 1)).astype(int)
    ctx["hold"] = ((soff) & (scored)).astype(int)
    ctx["broken"] = ((soff) & (~scored)).astype(int)
    ctx["break_scored"] = ((~soff) & (scored)).astype(int)
    ctx["break_chance"] = ((~soff) & (num_pos > 0)).astype(int)

    return ctx


def build_per_player_per_point(
    df_player: pd.DataFrame,
    df_points: pd.DataFrame,
    df_passes: pd.DataFrame,
    df_blocks: pd.DataFrame,
    df_poss: pd.DataFrame,
    game_id: str,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Return (rows_df, point_summary_df)."""
    roster = _expand_roster_from_player_stats(df_player)
    actions = _aggregate_passes(df_passes)
    blocks = _aggregate_blocks(df_blocks)

    # Merge roster with actions/blocks (outer merge in actions done; now left-join onto roster)
    pp = roster.merge(actions, on=["Point","Player"], how="left")
    pp = pp.merge(blocks, on=["Point","Player"], how="left")

    # Fill missing numeric
    for col in [
        "throws","completions","turnovers","assists","secondary_assists",
        "hucks","swings","dumps","throw_yards","catches","received_yards","goals","blocks"
    ]:
        if col in pp.columns:
            pp[col] = pp[col].fillna(0)

    pp["touches"] = pp.get("throws", 0) + pp.get("catches", 0)

    # Point context + tags
    ctx = _build_point_context_with_possessions(df_points, df_poss)

    pp = pp.merge(ctx[[
        "Point","team_line","point_result","our_score_start","opp_score_start",
        "point_possessions_total","point_passes_total","point_turnovers_total","point_blocks_total",
        "num_possessions","first_possession_scored","any_possession_scored",
        "clean_hold","hold","broken","break_scored","break_chance"
    ]], on="Point", how="left")

    # Final model-ready table
    rows = pd.DataFrame({
        "game_id": game_id,
        "point_uid": pp["Point"].apply(lambda x: f"{game_id}_P{int(x):02d}"),
        "team_line": pp["team_line"],
        "player": pp["Player"],
        "touches": pp["touches"].astype(int),
        "throws": pp["throws"].astype(int),
        "completions": pp["completions"].astype(int),
        "assists": pp["assists"].astype(int),
        "secondary_assists": pp["secondary_assists"].astype(int),
        "goals": pp["goals"].astype(int),
        "turnovers": pp["turnovers"].astype(int),
        "blocks": pp["blocks"].fillna(0).astype(int),
        "pulls": 0,  # not tracked in current exports
        "yards_gain_m": (pp.get("throw_yards",0) + pp.get("received_yards",0)).astype(float).round(2),
        "score_diff_start": (pp["our_score_start"] - pp["opp_score_start"]).astype(int),
        "point_result": pp["point_result"].astype(int),
        # possession-derived tags
        "num_possessions": pp["num_possessions"].astype(int),
        "clean_hold": pp["clean_hold"].astype(int),
        "hold": pp["hold"].astype(int),
        "broken": pp["broken"].astype(int),
        "break_scored": pp["break_scored"].astype(int),
        "break_chance": pp["break_chance"].astype(int),
        # pass-type counts (role signal)
        "hucks": pp["hucks"].astype(int),
        "swings": pp["swings"].astype(int),
        "dumps": pp["dumps"].astype(int),
    })

    # Point-level summary for sanity checks & analysis
    ptsum = ctx.copy()
    ptsum["game_id"] = game_id
    ptsum["point_uid"] = ptsum["Point"].apply(lambda x: f"{game_id}_P{int(x):02d}")

    return rows, ptsum

# ----------------------------
# CLI
# ----------------------------

def main():
    ap = argparse.ArgumentParser(description="Statto → Model Bridge (integrated)")
    ap.add_argument("--player", required=True, help="Path to Player Stats vs. <opponent>.csv")
    ap.add_argument("--points", required=True, help="Path to Points vs. <opponent>.csv")
    ap.add_argument("--passes", required=True, help="Path to Passes vs. <opponent>.csv")
    ap.add_argument("--blocks", required=True, help="Path to Defensive Blocks vs. <opponent>.csv")
    ap.add_argument("--poss",   required=True, help="Path to Possessions vs. <opponent>.csv")
    ap.add_argument("--game_id", required=True, help="Identifier like 2025-07-03_FBA")
    ap.add_argument("--outdir", default="./out", help="Where to save outputs")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    df_player = pd.read_csv(args.player)
    df_points = pd.read_csv(args.points)
    df_passes = pd.read_csv(args.passes)
    df_blocks = pd.read_csv(args.blocks)
    df_poss = pd.read_csv(args.poss)

    rows, ptsum = build_per_player_per_point(
        df_player=df_player,
        df_points=df_points,
        df_passes=df_passes,
        df_blocks=df_blocks,
        df_poss=df_poss,
        game_id=args.game_id,
    )

    out_rows = os.path.join(args.outdir, "per_player_per_point.csv")
    out_ptsum = os.path.join(args.outdir, "point_level_summary.csv")
    rows.to_csv(out_rows, index=False)
    ptsum.to_csv(out_ptsum, index=False)

    print("Wrote:")
    print(" -", out_rows)
    print(" -", out_ptsum)

if __name__ == "__main__":
    main()
