"""
Dimension generator for dim_stores.

Generates store location records.
"""

import random
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List

from .base_entity import BaseEntityGenerator, GeneratedData


class DimStoresGenerator(BaseEntityGenerator):
    """Generator for dim_stores table."""
    
    table_name = "dim_stores"
    
    STORE_TYPES = ["Mall", "Outlet", "Flagship", "Express", "Warehouse"]
    
    # Region -> country code mapping
    REGIONS = {
        "North America": {"countries": ["USA", "Canada", "Mexico"], "codes": ["+1", "+1", "+52"]},
        "Europe": {"countries": ["UK", "Germany", "France"], "codes": ["+44", "+49", "+33"]},
        "Asia Pacific": {"countries": ["Japan", "Australia", "Singapore", "India"], "codes": ["+81", "+61", "+65", "+91"]},
        "Latin America": {"countries": ["Brazil", "Argentina"], "codes": ["+55", "+54"]},
    }
    
    def generate(
        self,
        count: int = 10,
        start_key: int = 1,
        **kwargs
    ) -> GeneratedData:
        """
        Generate store dimension records.
        
        Args:
            count: Number of stores to generate
            start_key: Starting surrogate key value
            
        Returns:
            GeneratedData with store dimension records
        """
        if count <= 0:
            return GeneratedData(
                table_name=self.table_name,
                data=self._create_dataframe([]),
                surrogate_keys=[]
            )
        
        self.logger.info(f"Generating {count} stores")
        
        records = []
        keys = []
        now = datetime.now()
        
        for i in range(count):
            key = start_key + i
            keys.append(key)
            
            store_type = random.choice(self.STORE_TYPES)
            
            # Pick region and country
            region = random.choice(list(self.REGIONS.keys()))
            region_data = self.REGIONS[region]
            country_idx = random.randint(0, len(region_data["countries"]) - 1)
            country = region_data["countries"][country_idx]
            country_code = region_data["codes"][country_idx]
            
            city = self.faker.city()
            state = self.faker.state_abbr() if country in ["USA", "Canada", "Australia"] else None
            
            # Generate store name based on type and location
            store_name = f"{city} {store_type}"
            
            # Opening date within last 5 years
            opening_date = self.faker.date_between(
                start_date="-5y",
                end_date="today"
            )
            
            # Generate coordinates based on region
            lat, lon = self._get_region_coordinates(region)
            
            record = {
                "store_key": key,
                "store_id": f"STR{key:04d}",
                "store_name": store_name,
                "store_type": store_type,
                "address_line1": self.faker.street_address(),
                "address_line2": self.faker.secondary_address() if random.random() < 0.3 else None,
                "city": city,
                "state": state,
                "postal_code": self.faker.zipcode(),
                "country": country,
                "region": region,
                "phone_number": self.faker.numerify(f"{country_code}-###-###-####"),
                "email": f"store{key}@company.com",
                "opening_date": opening_date,
                "closing_date": None,
                "square_footage": random.randint(2000, 50000),
                "is_active": True,
                "latitude": Decimal(str(lat)),
                "longitude": Decimal(str(lon)),
                "created_at": now,
                "updated_at": now,
            }
            records.append(record)
        
        df = self._create_dataframe(records)
        
        self.logger.info(f"Generated {len(records)} store records")
        
        return GeneratedData(
            table_name=self.table_name,
            data=df,
            surrogate_keys=keys
        )
    
    def _get_region_coordinates(self, region: str) -> tuple:
        """Get random coordinates for a region."""
        coords = {
            "North America": (25.0, 50.0, -125.0, -70.0),
            "Europe": (35.0, 60.0, -10.0, 30.0),
            "Asia Pacific": (-40.0, 45.0, 100.0, 180.0),
            "Latin America": (-35.0, 15.0, -80.0, -35.0),
        }
        lat_min, lat_max, lon_min, lon_max = coords.get(region, (25.0, 50.0, -125.0, -70.0))
        lat = round(random.uniform(lat_min, lat_max), 6)
        lon = round(random.uniform(lon_min, lon_max), 6)
        return lat, lon
