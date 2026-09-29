"""
data_operations.py

Owns everything related to getting data into ClickHouse: secrets/config
loading, client construction, column reconciliation against the target
table schema, and the top-level load_data() orchestration that main.py
calls.

load_data() lives here (not api_operations.py) because loading is
fundamentally a data-storage concern — it pulls from the API module,
then owns validating and writing that data into ClickHouse. api_operations
stays focused purely on talking to the external source.
"""

import logging
from datetime import date
import clickhouse_connect
import yaml
import pandas as pd
from api_operations import fetch_statcast

logger = logging.getLogger(__name__)

# Columns in raw.statcast_pitches, in DDL order. ingested_at is excluded —
# it has a DEFAULT now() and is never supplied by pybaseball.
TABLE_COLUMNS = [
    "pitch_type", "game_date", "release_speed", "release_pos_x", "release_pos_z",
    "player_name", "batter", "pitcher", "events", "description", "spin_dir",
    "spin_rate_deprecated", "break_angle_deprecated", "break_length_deprecated",
    "zone", "des", "game_type", "stand", "p_throws", "home_team", "away_team",
    "type", "hit_location", "bb_type", "balls", "strikes", "game_year", "pfx_x",
    "pfx_z", "plate_x", "plate_z", "on_3b", "on_2b", "on_1b", "outs_when_up",
    "inning", "inning_topbot", "hc_x", "hc_y", "tfs_deprecated",
    "tfs_zulu_deprecated", "umpire", "sv_id", "vx0", "vy0", "vz0", "ax", "ay",
    "az", "sz_top", "sz_bot", "hit_distance_sc", "launch_speed", "launch_angle",
    "effective_speed", "release_spin_rate", "release_extension", "game_pk",
    "fielder_2", "fielder_3", "fielder_4", "fielder_5", "fielder_6", "fielder_7",
    "fielder_8", "fielder_9", "release_pos_y", "estimated_ba_using_speedangle",
    "estimated_woba_using_speedangle", "woba_value", "woba_denom", "babip_value",
    "iso_value", "launch_speed_angle", "at_bat_number", "pitch_number",
    "pitch_name", "home_score", "away_score", "bat_score", "fld_score",
    "post_away_score", "post_home_score", "post_bat_score", "post_fld_score",
    "if_fielding_alignment", "of_fielding_alignment", "spin_axis",
    "delta_home_win_exp", "delta_run_exp", "bat_speed", "swing_length",
    "miss_distance", "estimated_slg_using_speedangle", "delta_pitcher_run_exp",
    "hyper_speed", "home_score_diff", "bat_score_diff", "home_win_exp",
    "bat_win_exp", "age_pit_legacy", "age_bat_legacy", "age_pit", "age_bat",
    "n_thruorder_pitcher", "n_priorpa_thisgame_player_at_bat",
    "pitcher_days_since_prev_game", "batter_days_since_prev_game",
    "pitcher_days_until_next_game", "batter_days_until_next_game",
    "api_break_z_with_gravity", "api_break_x_arm", "api_break_x_batter_in",
    "arm_angle", "attack_angle", "attack_direction", "swing_path_tilt",
    "intercept_ball_minus_batter_pos_x_inches",
    "intercept_ball_minus_batter_pos_y_inches",
]


def load_secrets(path: str = "secrets.yaml") -> dict:
    logger.debug("Loading secrets from %s", path)
    with open(path, "r") as f:
        return yaml.safe_load(f)


def get_client(secrets: dict):
    ch = secrets["clickhouse"]
    logger.debug("Connecting to ClickHouse at %s:%s as %s", ch["host"], ch["port"], ch["user"])
    return clickhouse_connect.get_client(
        host=ch["host"],
        port=ch["port"],
        username=ch["user"],
        password=ch["password"],
        database="raw",
    )


def reconcile_columns(df):
    """
    Compare the DataFrame's columns against TABLE_COLUMNS and log any
    mismatch. Guards against pybaseball silently adding/removing columns
    between versions.

    Returns the DataFrame narrowed to just the columns present in both,
    in TABLE_COLUMNS order.
    """
    missing_in_df = [c for c in TABLE_COLUMNS if c not in df.columns]
    if missing_in_df:
        logger.warning("Columns expected by table but missing from API output: %s", missing_in_df)

    extra_in_df = [c for c in df.columns if c not in TABLE_COLUMNS]
    if extra_in_df:
        logger.warning("API returned columns not in table schema (will be dropped): %s", extra_in_df)

    insert_columns = [c for c in TABLE_COLUMNS if c in df.columns]
    return df[insert_columns]


def delete_date_range(client, start_dt: str, end_dt: str, table: str = "statcast_pitches"):
    """
    Remove any existing rows in [start_dt, end_dt] so a re-run of the same
    range replaces data instead of duplicating it.
    """
    start = date.fromisoformat(start_dt)
    end = date.fromisoformat(end_dt)
    logger.info("Deleting existing rows in raw.%s for %s to %s...", table, start, end)
    client.command(
        f"ALTER TABLE {table} DELETE "
        "WHERE game_date >= {start:Date} AND game_date <= {end:Date}",
        parameters={"start": start, "end": end},
        settings={"mutations_sync": 1},  # wait for the delete to finish before inserting
    )


def insert_dataframe(client, df, table: str = "statcast_pitches"):
    # ClickHouse doesn't accept NaN — convert to None so Nullable columns get real NULLs.
    df = df.where(df.notnull(), None)
    df["game_date"] = pd.to_datetime(df["game_date"]).dt.date
    logger.info("Inserting %d rows into raw.%s...", len(df), table)
    client.insert_df(table, df)
    logger.info("Insert complete.")


def load_data(start_dt: str, end_dt: str, secrets_path: str = "secrets.yaml"):
    """
    Top-level orchestration: pull Statcast data for the given date range
    and load it into raw.statcast_pitches.
    """
    secrets = load_secrets(secrets_path)
    client = get_client(secrets)

    df = fetch_statcast(start_dt, end_dt)
    if df.empty:
        logger.info("No rows returned for this date range. Nothing to insert.")
        return

    df = reconcile_columns(df)
    delete_date_range(client, start_dt, end_dt)
    insert_dataframe(client, df)