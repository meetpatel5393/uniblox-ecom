from fastapi import APIRouter

from app.api.v1.endpoints import admin, carts, customers, orders, products

# Single file to assemble v1. Adding v2 = copy this file, swap endpoint imports.
router = APIRouter()

router.include_router(customers.router)
router.include_router(products.router)
router.include_router(carts.router)
router.include_router(orders.router)
router.include_router(admin.router)
