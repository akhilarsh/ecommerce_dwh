"""
Date key utilities for data generation.

Converts between Python dates and integer date keys (YYYYMMDD format).
"""

from datetime import date, datetime, timedelta
from typing import List


def date_to_key(d: date) -> int:
    """
    Convert date to YYYYMMDD integer key.
    
    Args:
        d: Date object
        
    Returns:
        Integer in YYYYMMDD format (e.g., 20240115)
    """
    return int(d.strftime("%Y%m%d"))


def key_to_date(key: int) -> date:
    """
    Convert YYYYMMDD integer key to date.
    
    Args:
        key: Integer in YYYYMMDD format
        
    Returns:
        Date object
    """
    return datetime.strptime(str(key), "%Y%m%d").date()


def generate_date_keys(start_date: date, days: int) -> List[int]:
    """
    Generate date keys for a range starting from a date.
    
    Args:
        start_date: Starting date
        days: Number of days to generate
        
    Returns:
        List of integer date keys
    """
    return [
        date_to_key(start_date + timedelta(days=i))
        for i in range(days)
    ]


def generate_date_range_keys(start_date: date, end_date: date) -> List[int]:
    """
    Generate date keys between two dates (inclusive).
    
    Args:
        start_date: Start date
        end_date: End date (inclusive)
        
    Returns:
        List of integer date keys
    """
    days = (end_date - start_date).days + 1
    return generate_date_keys(start_date, days)


def time_to_key(hour: int, minute: int = 0, second: int = 0) -> int:
    """
    Convert time components to integer key.
    
    Args:
        hour: Hour (0-23)
        minute: Minute (0-59)
        second: Second (0-59)
        
    Returns:
        Integer in HHMMSS format (e.g., 143025 for 14:30:25)
    """
    return hour * 10000 + minute * 100 + second


def generate_time_keys(interval_minutes: int = 15) -> List[int]:
    """
    Generate time keys for all intervals in a day.
    
    Args:
        interval_minutes: Minutes between each time slot
        
    Returns:
        List of integer time keys
    """
    keys = []
    minutes_in_day = 24 * 60
    
    for total_minutes in range(0, minutes_in_day, interval_minutes):
        hour = total_minutes // 60
        minute = total_minutes % 60
        keys.append(time_to_key(hour, minute, 0))
    
    return keys
