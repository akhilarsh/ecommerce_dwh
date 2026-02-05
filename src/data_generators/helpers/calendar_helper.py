"""
Calendar helper for date and time dimension generation.

Manages: dim_dates, dim_time
"""

from datetime import date
from typing import Optional

from .base_helper import BaseHelper, DataGenerationResult, GeneratedData
from ..entities.dim_dates import DimDatesGenerator
from ..entities.dim_time import DimTimeGenerator


class CalendarHelper(BaseHelper):
    """
    Helper for calendar-related dimensions.
    
    Manages:
    - dim_dates: Date dimension with calendar attributes
    - dim_time: Time dimension with time-of-day attributes
    """
    
    name = "calendar"
    
    def __init__(self, config, keys_loader):
        """Initialize calendar helper with entity generators."""
        super().__init__(config, keys_loader)
        
        self.date_gen = DimDatesGenerator(config)
        self.time_gen = DimTimeGenerator(config)
    
    def generate(self) -> DataGenerationResult:
        """
        Generate all calendar dimensions based on config.
        
        Returns:
            DataGenerationResult with date and time dimensions
        """
        result = DataGenerationResult()
        
        # Generate dates
        dates = self._generate_dates()
        if dates.row_count > 0:
            result.add_dimension(dates)
            self._update_keys("dim_dates", dates.surrogate_keys)
        
        # Generate time
        time = self._generate_time()
        if time.row_count > 0:
            result.add_dimension(time)
            self._update_keys("dim_time", time.surrogate_keys)
        
        return result
    
    def _generate_dates(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> GeneratedData:
        """
        Generate date dimension.
        
        Args:
            start_date: Override config start date
            end_date: Override config end date
            
        Returns:
            GeneratedData with date dimension records
        """
        start = start_date or self.config.dates.start
        end = end_date or self.config.dates.end
        
        self.logger.info(f"Generating dates from {start} to {end}")
        
        return self.date_gen.generate(
            start_date=start,
            end_date=end
        )
    
    def _generate_time(self, interval_minutes: int = 15) -> GeneratedData:
        """
        Generate time dimension.
        
        Args:
            interval_minutes: Time slot interval in minutes
            
        Returns:
            GeneratedData with time dimension records
        """
        self.logger.info(f"Generating time with {interval_minutes}-minute intervals")
        
        return self.time_gen.generate(
            interval_minutes=interval_minutes
        )
    
    def generate_date_for_range(
        self,
        start_date: date,
        end_date: date
    ) -> GeneratedData:
        """
        Generate dates for a specific range.
        
        Useful for extending existing date dimension.
        
        Args:
            start_date: Start of range
            end_date: End of range
            
        Returns:
            GeneratedData with date dimension records for range
        """
        return self._generate_dates(start_date, end_date)
