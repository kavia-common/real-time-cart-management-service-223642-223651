"""
API routes package.

This package contains all API route modules organized by resource type.
"""
from .cart_routes import router as cart_router

__all__ = ["cart_router"]
