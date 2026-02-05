"""
Dimension generator for dim_channels.

Generates sales channel records (online, in-store, mobile, etc.).
"""

from datetime import datetime
from typing import Any, Dict, List

from .base_entity import BaseEntityGenerator, GeneratedData


class DimChannelsGenerator(BaseEntityGenerator):
    """Generator for dim_channels table."""
    
    table_name = "dim_channels"
    
    # Standard channels for multi-channel retail
    CHANNELS = [
        {
            "channel_name": "Online Web",
            "channel_code": "WEB",
            "channel_type": "Digital",
            "description": "Company e-commerce website",
            "is_active": True,
        },
        {
            "channel_name": "Mobile App",
            "channel_code": "APP",
            "channel_type": "Digital",
            "description": "iOS and Android mobile application",
            "is_active": True,
        },
        {
            "channel_name": "In-Store",
            "channel_code": "STORE",
            "channel_type": "Physical",
            "description": "Physical retail store locations",
            "is_active": True,
        },
        {
            "channel_name": "Phone Order",
            "channel_code": "PHONE",
            "channel_type": "Remote",
            "description": "Customer service phone orders",
            "is_active": True,
        },
        {
            "channel_name": "Marketplace",
            "channel_code": "MKTP",
            "channel_type": "Digital",
            "description": "Third-party marketplace (Amazon, eBay)",
            "is_active": True,
        },
        {
            "channel_name": "Social Commerce",
            "channel_code": "SOCIAL",
            "channel_type": "Digital",
            "description": "Social media shopping (Instagram, Facebook)",
            "is_active": True,
        },
    ]
    
    def generate(
        self,
        count: int = 0,
        start_key: int = 1,
        **kwargs
    ) -> GeneratedData:
        """
        Generate channel dimension records.
        
        Args:
            count: Ignored - all standard channels are generated
            start_key: Starting surrogate key value
            
        Returns:
            GeneratedData with channel dimension records
        """
        self.logger.info("Generating channel dimension")
        
        records = []
        keys = []
        now = datetime.now()
        
        for i, channel in enumerate(self.CHANNELS):
            key = start_key + i
            keys.append(key)
            
            record = {
                "channel_key": key,
                "channel_id": f"CH{key:03d}",
                **channel,
                "created_at": now,
                "updated_at": now,
            }
            records.append(record)
        
        df = self._create_dataframe(records)
        
        self.logger.info(f"Generated {len(records)} channel records")
        
        return GeneratedData(
            table_name=self.table_name,
            data=df,
            surrogate_keys=keys
        )
