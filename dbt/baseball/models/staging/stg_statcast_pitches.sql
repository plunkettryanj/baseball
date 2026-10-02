{{ config(materialized='table', order_by='(game_date, game_pk, at_bat_number, pitch_number)') }}

select
    concat(toString(game_pk), '-', toString(at_bat_number), '-', toString(pitch_number)) as pitch_id,
    game_pk,
    game_date,
    at_bat_number,
    pitch_number,
    pitcher as pitcher_id,
    batter as batter_id,
    pitch_type,
    release_speed,
    description,
    events
from {{ source('raw', 'statcast_pitches') }}
