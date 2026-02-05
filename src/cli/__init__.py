"""
CLI module for E-Commerce Data Warehouse.

Provides command-line interface for managing the data warehouse:
- Testing connections
- Generating SQL files
- Deploying tables
- Running pipelines
"""

from .main import cli

__all__ = ["cli"]
