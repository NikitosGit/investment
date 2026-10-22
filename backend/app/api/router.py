"""Aggregated API router."""

from fastapi import APIRouter

from app.api.routes import (
    assets,
    dashboard,
    health,
    income,
    operations,
    portfolio,
    positions,
    quotes,
    snapshots,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(portfolio.router)
api_router.include_router(assets.router)
api_router.include_router(operations.router)
api_router.include_router(positions.router)
api_router.include_router(income.router)
api_router.include_router(quotes.router)
api_router.include_router(dashboard.router)
api_router.include_router(snapshots.router)
