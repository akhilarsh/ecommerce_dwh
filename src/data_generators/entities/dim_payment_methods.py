"""
Dimension generator for dim_payment_methods.

Generates payment method records.
"""

from datetime import datetime
from typing import Any, Dict, List

from .base_entity import BaseEntityGenerator, GeneratedData


class DimPaymentMethodsGenerator(BaseEntityGenerator):
    """Generator for dim_payment_methods table."""
    
    table_name = "dim_payment_methods"
    
    # Standard payment methods
    PAYMENT_METHODS = [
        {
            "payment_method_name": "Credit Card - Visa",
            "payment_method_code": "VISA",
            "payment_type": "Credit Card",
            "is_active": True,
        },
        {
            "payment_method_name": "Credit Card - Mastercard",
            "payment_method_code": "MC",
            "payment_type": "Credit Card",
            "is_active": True,
        },
        {
            "payment_method_name": "Credit Card - American Express",
            "payment_method_code": "AMEX",
            "payment_type": "Credit Card",
            "is_active": True,
        },
        {
            "payment_method_name": "Debit Card",
            "payment_method_code": "DEBIT",
            "payment_type": "Debit Card",
            "is_active": True,
        },
        {
            "payment_method_name": "PayPal",
            "payment_method_code": "PAYPAL",
            "payment_type": "Digital Wallet",
            "is_active": True,
        },
        {
            "payment_method_name": "Apple Pay",
            "payment_method_code": "APPAY",
            "payment_type": "Digital Wallet",
            "is_active": True,
        },
        {
            "payment_method_name": "Google Pay",
            "payment_method_code": "GPAY",
            "payment_type": "Digital Wallet",
            "is_active": True,
        },
        {
            "payment_method_name": "Gift Card",
            "payment_method_code": "GIFT",
            "payment_type": "Store Credit",
            "is_active": True,
        },
        {
            "payment_method_name": "Store Credit",
            "payment_method_code": "CREDIT",
            "payment_type": "Store Credit",
            "is_active": True,
        },
        {
            "payment_method_name": "Cash",
            "payment_method_code": "CASH",
            "payment_type": "Cash",
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
        Generate payment method dimension records.
        
        Args:
            count: Ignored - all standard payment methods are generated
            start_key: Starting surrogate key value
            
        Returns:
            GeneratedData with payment method dimension records
        """
        self.logger.info("Generating payment method dimension")
        
        records = []
        keys = []
        now = datetime.now()
        
        for i, method in enumerate(self.PAYMENT_METHODS):
            key = start_key + i
            keys.append(key)
            
            record = {
                "payment_method_key": key,
                "payment_method_id": f"PM{key:03d}",
                **method,
                "created_at": now,
                "updated_at": now,
            }
            records.append(record)
        
        df = self._create_dataframe(records)
        
        self.logger.info(f"Generated {len(records)} payment method records")
        
        return GeneratedData(
            table_name=self.table_name,
            data=df,
            surrogate_keys=keys
        )
