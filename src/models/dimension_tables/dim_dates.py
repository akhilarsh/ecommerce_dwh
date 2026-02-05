"""
Date Dimension Table Model.

Pre-populated with 10+ years of date data for time-series analysis.
"""

from typing import List
from ..base_table import BaseTable, Column


class DimDates(BaseTable):
    """Date dimension for time-series analysis."""
    
    table_name = "dim_dates"
    primary_key = ["date_key"]
    comment = "Date dimension with calendar attributes"
    
    def define_columns(self) -> List[Column]:
        """Define date dimension columns."""
        return [
            Column(
                "date_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="Surrogate key (YYYYMMDD format)"
            ),
            Column(
                "full_date",
                "DATE",
                nullable=False,
                comment="Actual date"
            ),
            Column(
                "day_of_week",
                "NUMBER",
                precision=1,
                nullable=False,
                comment="1=Monday to 7=Sunday"
            ),
            Column(
                "day_name",
                "VARCHAR",
                length=10,
                nullable=False,
                comment="Monday, Tuesday, etc."
            ),
            Column(
                "day_of_month",
                "NUMBER",
                precision=2,
                nullable=False,
                comment="1-31"
            ),
            Column(
                "day_of_year",
                "NUMBER",
                precision=3,
                nullable=False,
                comment="1-366"
            ),
            Column(
                "week_of_year",
                "NUMBER",
                precision=2,
                nullable=False,
                comment="1-53"
            ),
            Column(
                "month_number",
                "NUMBER",
                precision=2,
                nullable=False,
                comment="1-12"
            ),
            Column(
                "month_name",
                "VARCHAR",
                length=10,
                nullable=False,
                comment="January, February, etc."
            ),
            Column(
                "month_abbr",
                "VARCHAR",
                length=3,
                nullable=False,
                comment="Jan, Feb, etc."
            ),
            Column(
                "quarter_number",
                "NUMBER",
                precision=1,
                nullable=False,
                comment="1-4"
            ),
            Column(
                "calendar_year",
                "NUMBER",
                precision=4,
                nullable=False,
                comment="Calendar year"
            ),
            Column(
                "is_weekend",
                "BOOLEAN",
                nullable=False,
                default="FALSE",
                comment="True if Saturday/Sunday"
            ),
            Column(
                "is_holiday",
                "BOOLEAN",
                nullable=False,
                default="FALSE",
                comment="True if public holiday"
            ),
            Column(
                "fiscal_year",
                "NUMBER",
                precision=4,
                comment="Fiscal year (can differ from calendar)"
            ),
            Column(
                "fiscal_quarter",
                "NUMBER",
                precision=1,
                comment="Fiscal quarter 1-4"
            ),
        ]
