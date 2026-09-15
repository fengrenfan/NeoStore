from fastapi import APIRouter

from app.api.v1.admin import auth as admin_auth
from app.api.v1.admin import categories as admin_categories
from app.api.v1.admin import inventory as admin_inventory
from app.api.v1.admin import orders as admin_orders
from app.api.v1.admin import products as admin_products
from app.api.v1.admin import settings as admin_settings
from app.api.v1.store import carts, checkout, locales, orders, products, regions

api_router = APIRouter()

store_router = APIRouter(prefix="/store", tags=["storefront"])
store_router.include_router(locales.router)
store_router.include_router(regions.router)
store_router.include_router(products.router)
store_router.include_router(carts.router)
store_router.include_router(checkout.router)
store_router.include_router(orders.router)

admin_router = APIRouter(prefix="/admin")
admin_router.include_router(admin_auth.router)
admin_router.include_router(admin_products.router)
admin_router.include_router(admin_categories.router)
admin_router.include_router(admin_orders.router)
admin_router.include_router(admin_inventory.router)
admin_router.include_router(admin_settings.router)

api_router.include_router(store_router)
api_router.include_router(admin_router)
