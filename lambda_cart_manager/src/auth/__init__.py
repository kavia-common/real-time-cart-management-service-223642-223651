"""
Authentication package for JWT-based authentication.

This package provides JWT token handling and FastAPI authentication dependencies
for securing API endpoints with Bearer token authentication.
"""
from .jwt_handler import (
    create_access_token,
    decode_token,
    validate_token,
    extract_user_id,
    get_token_expiration,
    JWTValidationError,
    TokenExpiredError,
    InvalidTokenError
)

from .dependencies import (
    get_current_user,
    get_optional_user,
    AuthenticationError,
    CurrentUser,
    OptionalUser
)

__all__ = [
    # JWT handler functions
    "create_access_token",
    "decode_token",
    "validate_token",
    "extract_user_id",
    "get_token_expiration",
    
    # JWT exceptions
    "JWTValidationError",
    "TokenExpiredError",
    "InvalidTokenError",
    
    # FastAPI dependencies
    "get_current_user",
    "get_optional_user",
    "AuthenticationError",
    
    # Type aliases
    "CurrentUser",
    "OptionalUser"
]
