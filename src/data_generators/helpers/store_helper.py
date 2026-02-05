"""
Store helper for store and employee dimension generation.

Manages: dim_stores, dim_employees
"""

from typing import List, Optional

from .base_helper import BaseHelper, DataGenerationResult, GeneratedData
from ..entities.dim_stores import DimStoresGenerator
from ..entities.dim_employees import DimEmployeesGenerator


class StoreHelper(BaseHelper):
    """
    Helper for store-related dimensions.
    
    Manages:
    - dim_stores: Physical store locations
    - dim_employees: Store employees
    """
    
    name = "store"
    
    def __init__(self, config, keys_loader):
        """Initialize store helper with entity generators."""
        super().__init__(config, keys_loader)
        
        self.store_gen = DimStoresGenerator(config)
        self.employee_gen = DimEmployeesGenerator(config)
    
    def generate(self) -> DataGenerationResult:
        """
        Generate all store dimensions based on config.volumes.
        
        Returns:
            DataGenerationResult with store dimensions
        """
        result = DataGenerationResult()
        
        # Generate stores first (employees depend on them)
        if self._should_generate("stores"):
            stores = self._generate_stores()
            result.add_dimension(stores)
            self._update_keys("dim_stores", stores.surrogate_keys)
        
        # Generate employees
        if self._should_generate("employees"):
            store_keys = self._get_dimension_keys("dim_stores")
            employees = self._generate_employees(store_keys)
            result.add_dimension(employees)
            self._update_keys("dim_employees", employees.surrogate_keys)
        
        return result
    
    def _generate_stores(self, count: Optional[int] = None) -> GeneratedData:
        """
        Generate stores.
        
        Args:
            count: Override volume from config
            
        Returns:
            GeneratedData with store records
        """
        num_stores = count or self._get_volume("stores")
        start_key = self._get_next_key("dim_stores")
        
        self.logger.info(f"Generating {num_stores} stores")
        
        return self.store_gen.generate(
            count=num_stores,
            start_key=start_key
        )
    
    def _generate_employees(
        self,
        store_keys: List[int],
        count: Optional[int] = None
    ) -> GeneratedData:
        """
        Generate employees.
        
        Args:
            store_keys: Valid store keys for assignment
            count: Override volume from config
            
        Returns:
            GeneratedData with employee records
        """
        num_employees = count or self._get_volume("employees")
        start_key = self._get_next_key("dim_employees")
        
        self.logger.info(f"Generating {num_employees} employees")
        
        return self.employee_gen.generate(
            count=num_employees,
            start_key=start_key,
            store_keys=store_keys
        )
    
    def open_new_store(
        self,
        store_name: str,
        store_type: str = "Mall",
        region: str = "Northeast",
        initial_employees: int = 5,
        include_inventory: bool = True
    ) -> DataGenerationResult:
        """
        Add a new store with employees.
        
        Args:
            store_name: Name for the new store
            store_type: Type of store (Mall, Outlet, etc.)
            region: Geographic region
            initial_employees: Number of employees to hire
            include_inventory: Whether to generate initial inventory
            
        Returns:
            DataGenerationResult with store and employee data
        """
        result = DataGenerationResult()
        
        # Generate single store
        store_key = self._get_next_key("dim_stores")
        store = self.store_gen.generate(
            count=1,
            start_key=store_key
        )
        
        # Override generated values
        if store.row_count > 0:
            store.data.loc[0, "store_name"] = store_name
            store.data.loc[0, "store_type"] = store_type
            store.data.loc[0, "region"] = region
        
        result.add_dimension(store)
        self._update_keys("dim_stores", store.surrogate_keys)
        
        # Generate employees for this store
        employees = self._generate_employees(
            store_keys=[store_key],
            count=initial_employees
        )
        result.add_dimension(employees)
        self._update_keys("dim_employees", employees.surrogate_keys)
        
        # Inventory generation would be handled by InventoryHelper
        # Store the flag for caller to handle
        result.keys["include_inventory"] = [store_key] if include_inventory else []
        
        return result
