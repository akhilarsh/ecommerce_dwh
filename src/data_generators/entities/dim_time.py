"""
Dimension generator for dim_time.

Generates time dimension records with time-of-day attributes.
"""

from typing import Any, Dict, List

from .base_entity import BaseEntityGenerator, GeneratedData
from ..utils.date_keys import time_to_key


class DimTimeGenerator(BaseEntityGenerator):
    """Generator for dim_time table."""
    
    table_name = "dim_time"
    
    def generate(
        self,
        count: int = 0,
        start_key: int = 1,
        interval_minutes: int = 15,
        **kwargs
    ) -> GeneratedData:
        """
        Generate time dimension records.
        
        Args:
            count: Ignored - all time slots are generated
            start_key: Ignored - keys are time integers (HHMMSS)
            interval_minutes: Minutes between time slots (default 15)
            
        Returns:
            GeneratedData with time dimension records
        """
        self.logger.info(f"Generating time dimension with {interval_minutes}-minute intervals")
        
        records = []
        keys = []
        
        minutes_in_day = 24 * 60
        
        for total_minutes in range(0, minutes_in_day, interval_minutes):
            hour = total_minutes // 60
            minute = total_minutes % 60
            
            time_key = time_to_key(hour, minute, 0)
            keys.append(time_key)
            
            record = self._create_time_record(hour, minute, time_key)
            records.append(record)
        
        df = self._create_dataframe(records)
        
        self.logger.info(f"Generated {len(records)} time records")
        
        return GeneratedData(
            table_name=self.table_name,
            data=df,
            surrogate_keys=keys
        )
    
    def _create_time_record(self, hour: int, minute: int, time_key: int) -> Dict[str, Any]:
        """Create a single time dimension record."""
        return {
            "time_key": time_key,
            "time_value": f"{hour:02d}:{minute:02d}:00",
            "hour_24": hour,
            "minute_of_hour": minute,
            "second_of_minute": 0,
            "am_pm": "AM" if hour < 12 else "PM",
            "hour_12": hour % 12 or 12,
            "day_part": self._get_day_part(hour),
            "is_business_hours": 9 <= hour < 17,
            "is_peak_shopping": self._is_peak_shopping(hour),
        }
    
    def _get_day_part(self, hour: int) -> str:
        """Get part of day based on hour."""
        if 5 <= hour < 12:
            return "Morning"
        elif 12 <= hour < 17:
            return "Afternoon"
        elif 17 <= hour < 21:
            return "Evening"
        else:
            return "Night"
    
    def _is_peak_shopping(self, hour: int) -> bool:
        """Check if hour is peak shopping time."""
        # Peak hours: 10am-2pm and 6pm-9pm
        return (10 <= hour < 14) or (18 <= hour < 21)
