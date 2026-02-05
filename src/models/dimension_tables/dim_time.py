"""
Time Dimension Table Model.

Provides intraday time granularity for analysis.
"""

from typing import List
from ..base_table import BaseTable, Column


class DimTime(BaseTable):
    """Time of day dimension for intraday analysis."""
    
    table_name = "dim_time"
    primary_key = ["time_key"]
    comment = "Time of day dimension with hourly/minute breakdown"
    
    def define_columns(self) -> List[Column]:
        """Define time dimension columns."""
        return [
            Column(
                "time_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="Surrogate key (HHMM format)"
            ),
            Column(
                "time_value",
                "TIME",
                nullable=False,
                comment="Actual time value"
            ),
            Column(
                "hour_24",
                "NUMBER",
                precision=2,
                nullable=False,
                comment="0-23"
            ),
            Column(
                "minute_of_hour",
                "NUMBER",
                precision=2,
                nullable=False,
                comment="0-59"
            ),
            Column(
                "second_of_minute",
                "NUMBER",
                precision=2,
                nullable=False,
                default="0",
                comment="0-59"
            ),
            Column(
                "am_pm",
                "VARCHAR",
                length=2,
                nullable=False,
                comment="AM or PM"
            ),
            Column(
                "hour_12",
                "NUMBER",
                precision=2,
                nullable=False,
                comment="1-12 (12-hour format)"
            ),
            Column(
                "day_part",
                "VARCHAR",
                length=20,
                comment="Morning, Afternoon, Evening, Night"
            ),
            Column(
                "is_business_hours",
                "BOOLEAN",
                nullable=False,
                default="FALSE",
                comment="True if 9AM-5PM"
            ),
            Column(
                "is_peak_shopping",
                "BOOLEAN",
                nullable=False,
                default="FALSE",
                comment="True if peak shopping hours"
            ),
        ]
