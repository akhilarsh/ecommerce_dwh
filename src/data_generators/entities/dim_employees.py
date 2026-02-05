"""
Dimension generator for dim_employees.

Generates employee records linked to stores.
"""

import random
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List

from .base_entity import BaseEntityGenerator, GeneratedData


class DimEmployeesGenerator(BaseEntityGenerator):
    """Generator for dim_employees table."""
    
    table_name = "dim_employees"
    
    POSITIONS = [
        "Store Manager",
        "Assistant Manager",
        "Sales Associate",
        "Cashier",
        "Stock Associate",
        "Customer Service Rep",
    ]
    
    DEPARTMENTS = [
        "Sales",
        "Customer Service",
        "Inventory",
        "Management",
    ]
    
    # Country codes for multi-region stores
    COUNTRY_CODES = ["+1", "+44", "+49", "+33", "+61", "+81", "+91", "+55", "+52", "+65", "+54"]
    
    def generate(
        self,
        count: int = 50,
        start_key: int = 1,
        store_keys: List[int] = None,
        **kwargs
    ) -> GeneratedData:
        """
        Generate employee dimension records.
        
        Args:
            count: Number of employees to generate
            start_key: Starting surrogate key value
            store_keys: List of valid store keys for assignment
            
        Returns:
            GeneratedData with employee dimension records
        """
        if count <= 0:
            return GeneratedData(
                table_name=self.table_name,
                data=self._create_dataframe([]),
                surrogate_keys=[]
            )
        
        self.logger.info(f"Generating {count} employees")
        
        # Default store keys if not provided
        if not store_keys:
            store_keys = list(range(1, 11))  # Assume 10 stores
        
        records = []
        keys = []
        now = datetime.now()
        
        # Ensure each store has at least one manager
        store_managers = {store: False for store in store_keys}
        
        for i in range(count):
            key = start_key + i
            keys.append(key)
            
            # Assign to store
            store_key = random.choice(store_keys)
            
            # Determine position
            if not store_managers[store_key]:
                position = "Store Manager"
                store_managers[store_key] = True
            else:
                position = random.choice(self.POSITIONS[1:])  # Exclude Store Manager
            
            # Generate employee data
            first_name = self.faker.first_name()
            last_name = self.faker.last_name()
            
            # Hire date within last 5 years
            hire_date = self.faker.date_between(
                start_date="-5y",
                end_date="today"
            )
            
            # Salary based on position
            base_salary = {
                "Store Manager": (55000, 85000),
                "Assistant Manager": (40000, 55000),
                "Sales Associate": (28000, 38000),
                "Cashier": (25000, 32000),
                "Stock Associate": (26000, 34000),
                "Customer Service Rep": (28000, 36000),
            }
            salary_range = base_salary.get(position, (28000, 40000))
            
            record = {
                "employee_key": key,
                "employee_id": f"EMP{key:05d}",
                "first_name": first_name,
                "last_name": last_name,
                "full_name": f"{first_name} {last_name}",
                "email": f"{first_name.lower()}.{last_name.lower()}@company.com",
                "phone_number": self.faker.numerify(f"{random.choice(self.COUNTRY_CODES)}-###-###-####"),
                "position": position,
                "department": self._get_department(position),
                "store_key": store_key,
                "hire_date": hire_date,
                "termination_date": None,
                "salary": Decimal(str(random.randint(*salary_range))),
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }
            records.append(record)
        
        df = self._create_dataframe(records)
        
        self.logger.info(f"Generated {len(records)} employee records")
        
        return GeneratedData(
            table_name=self.table_name,
            data=df,
            surrogate_keys=keys
        )
    
    def _get_department(self, position: str) -> str:
        """Get department based on position."""
        if position in ["Store Manager", "Assistant Manager"]:
            return "Management"
        elif position in ["Sales Associate"]:
            return "Sales"
        elif position in ["Stock Associate"]:
            return "Inventory"
        else:
            return "Customer Service"
