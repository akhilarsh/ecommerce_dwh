"""
Employee Dimension Table Model.

Defines store and sales associates.
"""

from typing import List
from ..base_table import BaseTable, Column, ForeignKey


class DimEmployees(BaseTable):
    """Employee dimension."""
    
    table_name = "dim_employees"
    primary_key = ["employee_key"]
    comment = "Store employees and sales associates"
    
    def define_columns(self) -> List[Column]:
        """Define employee dimension columns."""
        return [
            Column(
                "employee_key",
                "NUMBER",
                precision=38,
                nullable=False,
                comment="Surrogate key"
            ),
            Column(
                "employee_id",
                "VARCHAR",
                length=50,
                nullable=False,
                comment="Business employee identifier"
            ),
            Column(
                "first_name",
                "VARCHAR",
                length=100,
                nullable=False,
                comment="Employee first name"
            ),
            Column(
                "last_name",
                "VARCHAR",
                length=100,
                nullable=False,
                comment="Employee last name"
            ),
            Column(
                "full_name",
                "VARCHAR",
                length=200,
                comment="Full name (first + last)"
            ),
            Column(
                "email",
                "VARCHAR",
                length=200,
                comment="Employee email address"
            ),
            Column(
                "phone_number",
                "VARCHAR",
                length=20,
                comment="Employee phone number"
            ),
            Column(
                "position",
                "VARCHAR",
                length=100,
                comment="Sales Associate, Store Manager, etc."
            ),
            Column(
                "department",
                "VARCHAR",
                length=100,
                comment="Department name"
            ),
            Column(
                "store_key",
                "NUMBER",
                precision=38,
                comment="Associated store (FK to dim_stores)"
            ),
            Column(
                "hire_date",
                "DATE",
                comment="Employee hire date"
            ),
            Column(
                "termination_date",
                "DATE",
                comment="Employee termination date (if terminated)"
            ),
            Column(
                "salary",
                "NUMBER",
                precision=12,
                scale=2,
                comment="Annual salary"
            ),
            Column(
                "is_active",
                "BOOLEAN",
                nullable=False,
                default="TRUE",
                comment="Employee currently active"
            ),
            Column(
                "created_at",
                "TIMESTAMP_NTZ",
                nullable=False,
                comment="Record creation timestamp"
            ),
            Column(
                "updated_at",
                "TIMESTAMP_NTZ",
                comment="Last update timestamp"
            ),
        ]
    
    foreign_keys = [
        ForeignKey(
            column="store_key",
            reference_table="dim_stores",
            reference_column="store_key"
        )
    ]
