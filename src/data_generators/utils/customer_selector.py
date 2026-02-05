"""
Customer selector for ratio-based customer selection.

Used in incremental data generation to mix existing and new customers
according to configurable ratios.
"""

import random
from typing import List, Optional


class CustomerSelector:
    """
    Handles ratio-based customer selection for transactions.
    
    Provides weighted random selection between existing and newly
    registered customers based on configurable ratio.
    
    Usage:
        selector = CustomerSelector(
            existing_keys=[1, 2, 3],
            new_keys=[100, 101],
            existing_ratio=0.8
        )
        customer_key = selector.select()  # 80% chance of existing
    """
    
    def __init__(
        self,
        existing_keys: Optional[List[int]] = None,
        new_keys: Optional[List[int]] = None,
        existing_ratio: float = 0.8
    ):
        """
        Initialize the selector.
        
        Args:
            existing_keys: List of existing customer keys
            new_keys: List of newly created customer keys
            existing_ratio: Probability of selecting from existing (0.0-1.0)
        """
        self.existing_keys = existing_keys or []
        self.new_keys = new_keys or []
        self.existing_ratio = max(0.0, min(1.0, existing_ratio))
    
    def select(self) -> int:
        """
        Select a customer key based on configured ratio.
        
        Returns:
            Selected customer key
            
        Raises:
            ValueError: If no customer keys are available
        """
        if self.existing_keys and self.new_keys:
            # Both pools available - use ratio
            if random.random() < self.existing_ratio:
                return random.choice(self.existing_keys)
            return random.choice(self.new_keys)
        elif self.new_keys:
            # Only new keys available
            return random.choice(self.new_keys)
        elif self.existing_keys:
            # Only existing keys available
            return random.choice(self.existing_keys)
        
        raise ValueError("No customer keys available for selection")
    
    def select_many(self, count: int) -> List[int]:
        """
        Select multiple customer keys.
        
        Args:
            count: Number of keys to select
            
        Returns:
            List of selected customer keys
        """
        return [self.select() for _ in range(count)]
    
    def has_keys(self) -> bool:
        """Check if any keys are available."""
        return bool(self.existing_keys or self.new_keys)
    
    def total_available(self) -> int:
        """Get total number of available keys."""
        return len(self.existing_keys) + len(self.new_keys)
    
    def add_new_keys(self, keys: List[int]) -> None:
        """
        Add newly generated keys to the new keys pool.
        
        Args:
            keys: List of new customer keys to add
        """
        self.new_keys.extend(keys)
    
    def promote_new_to_existing(self) -> None:
        """
        Move all new keys to existing pool.
        
        Call this after a batch is complete to prepare for next batch.
        """
        self.existing_keys.extend(self.new_keys)
        self.new_keys = []
