"""
api_operations.py

Handles all interaction with external data sources (currently: pybaseball /
Baseball Savant Statcast). No ClickHouse or storage logic belongs here —
this module's only job is fetching data and handing back a DataFrame.
"""

import logging
from pybaseball import statcast

logger = logging.getLogger(__name__)


def fetch_statcast(start_dt: str, end_dt: str):
    """
    Pull pitch-level Statcast data for a date range.

    Args:
        start_dt: YYYY-MM-DD
        end_dt: YYYY-MM-DD

    Returns:
        pandas.DataFrame of raw Statcast rows, one row per pitch.
    """
    logger.info("Pulling Statcast data from %s to %s...", start_dt, end_dt)
    df = statcast(start_dt=start_dt, end_dt=end_dt)
    logger.info("Pulled %d rows, %d columns.", len(df), len(df.columns))
    return df