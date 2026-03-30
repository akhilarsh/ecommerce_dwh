"""
Individual entity generators for the E-Commerce Data Warehouse.

Each generator is responsible for creating synthetic data for a single table.
"""

from .base_entity import BaseEntityGenerator, GeneratedData

# Dimension generators
from .dim_dates import DimDatesGenerator
from .dim_time import DimTimeGenerator
from .dim_channels import DimChannelsGenerator
from .dim_payment_methods import DimPaymentMethodsGenerator
from .dim_shipping_methods import DimShippingMethodsGenerator
from .dim_customer_segments import DimCustomerSegmentsGenerator
from .dim_loyalty_tiers import DimLoyaltyTiersGenerator
from .dim_product_categories import DimProductCategoriesGenerator
from .dim_promotions import DimPromotionsGenerator
from .dim_stores import DimStoresGenerator
from .dim_employees import DimEmployeesGenerator
from .dim_products import DimProductsGenerator
from .dim_customers import DimCustomersGenerator
from .dim_customer_address import DimCustomerAddressGenerator
from .dim_customer_loyalty import DimCustomerLoyaltyGenerator
from .dim_accounts import DimAccountsGenerator

# Fact generators
from .fact_sales import FactSalesGenerator
from .fact_inventory import FactInventorySnapshotsGenerator
from .fact_interactions import FactCustomerInteractionsGenerator
from .fact_loyalty import FactLoyaltyPointsGenerator

# Bridge generators
from .bridge_order_items import BridgeOrderItemsGenerator
from .bridge_product_promotions import BridgeProductPromotionsGenerator
from .bridge_account_customers import BridgeAccountCustomersGenerator

__all__ = [
    # Base
    "BaseEntityGenerator",
    "GeneratedData",
    # Dimensions
    "DimDatesGenerator",
    "DimTimeGenerator",
    "DimChannelsGenerator",
    "DimPaymentMethodsGenerator",
    "DimShippingMethodsGenerator",
    "DimCustomerSegmentsGenerator",
    "DimLoyaltyTiersGenerator",
    "DimProductCategoriesGenerator",
    "DimPromotionsGenerator",
    "DimStoresGenerator",
    "DimEmployeesGenerator",
    "DimProductsGenerator",
    "DimCustomersGenerator",
    "DimCustomerAddressGenerator",
    "DimCustomerLoyaltyGenerator",
    "DimAccountsGenerator",
    # Facts
    "FactSalesGenerator",
    "FactInventorySnapshotsGenerator",
    "FactCustomerInteractionsGenerator",
    "FactLoyaltyPointsGenerator",
    # Bridges
    "BridgeOrderItemsGenerator",
    "BridgeProductPromotionsGenerator",
    "BridgeAccountCustomersGenerator",
]
