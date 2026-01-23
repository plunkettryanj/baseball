import requests
import pandas as pd


base_url = 'https://statsapi.mlb.com/api/v1/'

response = requests.get(f'{base_url}teams')
response.raise_for_status()  # Raises HTTPError on 4xx 
teams_data = response.json()
teams_df = pd.json_normalize(teams_data, 'teams')
filtered_df = teams_df[teams_df['name'].str.contains('Angel')]
print(filtered_df)