"""
Dimension generator for dim_dates.

Generates date dimension records with calendar attributes.
"""

from datetime import date, timedelta
from typing import Any, Dict, List

from .base_entity import BaseEntityGenerator, GeneratedData
from ..utils.date_keys import date_to_key


class DimDatesGenerator(BaseEntityGenerator):
    """Generator for dim_dates table."""
    
    table_name = "dim_dates"
    
    def generate(
        self,
        count: int = 0,
        start_key: int = 1,
        start_date: date = None,
        end_date: date = None,
        **kwargs
    ) -> GeneratedData:
        """
        Generate date dimension records.
        
        Args:
            count: Ignored - dates are generated for full range
            start_key: Ignored - keys are date integers (YYYYMMDD)
            start_date: Start of date range (defaults to config)
            end_date: End of date range (defaults to config)
            
        Returns:
            GeneratedData with date dimension records
        """
        start = start_date or self.config.dates.start
        end = end_date or self.config.dates.end
        
        self.logger.info(f"Generating dates from {start} to {end}")
        
        records = []
        keys = []
        current = start
        
        while current <= end:
            date_key = date_to_key(current)
            keys.append(date_key)
            
            record = self._create_date_record(current, date_key)
            records.append(record)
            
            current += timedelta(days=1)
        
        df = self._create_dataframe(records)
        
        self.logger.info(f"Generated {len(records)} date records")
        
        return GeneratedData(
            table_name=self.table_name,
            data=df,
            surrogate_keys=keys
        )
    
    def _create_date_record(self, d: date, date_key: int) -> Dict[str, Any]:
        """Create a single date dimension record."""
        return {
            "date_key": date_key,
            "full_date": d,
            "day_of_week": d.weekday() + 1,  # 1=Monday, 7=Sunday
            "day_name": d.strftime("%A"),
            "day_of_month": d.day,
            "day_of_year": d.timetuple().tm_yday,
            "week_of_year": d.isocalendar()[1],
            "month_number": d.month,
            "month_name": d.strftime("%B"),
            "month_abbr": d.strftime("%b"),
            "quarter_number": (d.month - 1) // 3 + 1,
            "calendar_year": d.year,
            "is_weekend": d.weekday() >= 5,
            "is_holiday": self._is_holiday(d),
            "fiscal_year": self._get_fiscal_year(d),
            "fiscal_quarter": self._get_fiscal_quarter(d),
        }
    
    def _is_holiday(self, d: date) -> bool:
        """Check if date is a US holiday (simplified)."""
        holidays = [
            (1, 1),   # New Year's Day
            (7, 4),   # Independence Day
            (12, 25), # Christmas
        ]
        # Thanksgiving (4th Thursday of November)
        if d.month == 11 and d.weekday() == 3:
            # Check if it's the 4th Thursday
            first_day = date(d.year, 11, 1)
            first_thursday = first_day + timedelta(days=(3 - first_day.weekday()) % 7)
            fourth_thursday = first_thursday + timedelta(weeks=3)
            if d == fourth_thursday:
                return True
        
        return (d.month, d.day) in holidays
    
    def _get_fiscal_year(self, d: date) -> int:
        """Get fiscal year (assuming October start)."""
        return d.year + 1 if d.month >= 10 else d.year
    
    def _get_fiscal_quarter(self, d: date) -> int:
        """Get fiscal quarter (assuming October start)."""
        fiscal_month = (d.month - 10) % 12 + 1
        return (fiscal_month - 1) // 3 + 1
