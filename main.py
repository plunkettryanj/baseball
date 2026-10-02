"""
main.py
Entrypoint for manual ingestion runs

Usage:
    python main.py --start <YYYY-MM-DD> --end <YYYY-MM-DD>
"""

import argparse
import logging

from data_operations import load_data

# import requests
# import pandas as pd

# live_game_feed = 'https://statsapi.mlb.com/api/v1.1/game/{game_list_input[i]}/feed/live'
# sample_reg_season = 'https://statsapi.mlb.com/api/v1/schedule/?sportId={sport_id_str}&gameTypes={game_type_str}&season={year_input_str}&hydrate=lineup,players'
# player_game_log = 'http://statsapi.mlb.com/api/v1/people/{player_id}?hydrate=stats(group={group},type=gameLog,season={season},startDate={start_date},endDate={end_date},sportId={sport_id},gameType=[{game_type_str}]),hydrations'
# base_url = 'https://statsapi.mlb.com/api/v1/'
# endpoints = ['teams', 'sports', 'gameTypes', 'leagues']
# for endpoint in endpoints:
#     response = requests.get(f'{base_url}{endpoint}')
#     response.raise_for_status()  # Raises HTTPError on 4xx 
#     data = response.json()
#     try:
#         normalize_df = pd.json_normalize(data, endpoint)
#     except KeyError:
#         normalize_df = pd.json_normalize(data)
#     print(normalize_df.head())


def configure_logging():
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s - %(levelname)s - %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S",)


def main():
    configure_logging()
    parser = argparse.ArgumentParser(description="Ingest baseball data into ClickHouse.")
    parser.add_argument("--start", required=True, help="Start date in YYYY-MM-DD format")
    parser.add_argument("--end", required=True, help="End date in YYYY-MM-DD format")
    parser.add_argument("--secrets", default="secrets.yaml", help="Path to descrypted secrets file")
    args = parser.parse_args()

    load_data(args.start, args.end, args.secrets)


if __name__ == "__main__":
    main()