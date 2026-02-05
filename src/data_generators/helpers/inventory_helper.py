"""
Inventory helper for inventory snapshot generation.

Manages: fact_inventory_snapshots
"""

from datetime import date
from typing import Dict, List, Optional

from .base_helper import BaseHelper, DataGenerationResult, GeneratedData
from ..entities.fact_inventory import FactInventorySnapshotsGenerator


class InventoryHelper(BaseHelper):
    """
    Helper for inventory-related facts.
    
    Manages:
    - fact_inventory_snapshots: Daily inventory levels per location
    """
    
    name = "inventory"
    
    def __init__(self, config, keys_loader):
        """Initialize inventory helper with entity generators."""
        super().__init__(config, keys_loader)
        
        self.inventory_gen = FactInventorySnapshotsGenerator(config)
    
    def generate(self) -> DataGenerationResult:
        """
        Generate inventory snapshots based on config.volumes.
        
        Returns:
            DataGenerationResult with inventory data
        """
        result = DataGenerationResult()
        
        if self._should_generate("inventory_snapshots"):
            dimension_keys = self.keys_loader.get_all_dimension_keys()
            inventory = self._generate_inventory(
                dimension_keys=dimension_keys,
                days=self._get_volume("inventory_snapshots")
            )
            result.add_fact(inventory)
            self._update_keys("fact_inventory_snapshots", inventory.surrogate_keys)
        
        return result
    
    def _generate_inventory(
        self,
        dimension_keys: Dict[str, List[int]],
        days: int = 30,
        snapshot_date: Optional[date] = None
    ) -> GeneratedData:
        """
        Generate inventory snapshots.
        
        Args:
            dimension_keys: Dictionary of dimension keys
            days: Number of days of history
            snapshot_date: Specific date for single snapshot
            
        Returns:
            GeneratedData with inventory snapshot records
        """
        start_key = self._get_next_key("fact_inventory_snapshots")
        
        self.logger.info(f"Generating inventory snapshots")
        
        return self.inventory_gen.generate(
            start_key=start_key,
            dimension_keys=dimension_keys,
            days=days,
            snapshot_date=snapshot_date
        )
    
    def generate_snapshot(self, snapshot_date: date) -> GeneratedData:
        """
        Generate inventory snapshot for a specific date.
        
        Args:
            snapshot_date: Date for the snapshot
            
        Returns:
            GeneratedData with inventory snapshot for the date
        """
        dimension_keys = self.keys_loader.get_all_dimension_keys()
        
        return self._generate_inventory(
            dimension_keys=dimension_keys,
            snapshot_date=snapshot_date
        )
    
    def generate_for_store(
        self,
        store_key: int,
        snapshot_date: Optional[date] = None
    ) -> GeneratedData:
        """
        Generate inventory for a specific store.
        
        Args:
            store_key: Store key to generate inventory for
            snapshot_date: Date for snapshot (defaults to today)
            
        Returns:
            GeneratedData with inventory for store
        """
        dimension_keys = self.keys_loader.get_all_dimension_keys()
        
        # Override store keys to just this store
        dimension_keys["dim_stores"] = [store_key]
        
        return self._generate_inventory(
            dimension_keys=dimension_keys,
            days=1,
            snapshot_date=snapshot_date or date.today()
        )
