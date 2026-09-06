"""The API router.

Aggregating every route module into one `api_router` that `main.py` mounts, rather than having
the application factory include each router itself. This is the layout the official FastAPI
full-stack template uses, and it means adding a route module touches this file only.
"""

from fastapi import APIRouter

from food_api.api.routes import dishes, health, orders, search

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(dishes.router)
api_router.include_router(orders.router)
api_router.include_router(search.router)
