"""
FastAPI authentication dependencies.

This module provides FastAPI dependency functions for authentication,
including extracting and validating JWT tokens from Authorization headers.

PUBLIC_INTERFACE
"""
from typing import Annotated
import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.auth.jwt_handler import (
    extract_user_id,
    TokenExpiredError,
    InvalidTokenError
)

# Module-level logger
logger = logging.getLogger(__name__)

# HTTPBearer security scheme for Swagger/OpenAPI documentation
security = HTTPBearer(
    scheme_name="Bearer",
    description="JWT Bearer token authentication"
)


class AuthenticationError(HTTPException):
    """
    HTTP 401 exception for authentication failures.
    
    @compliance
    - Security: Standard HTTP status for authentication errors
    - API Design: Consistent error response format
    """
    def __init__(self, detail: str = "Could not validate credentials"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )


# PUBLIC_INTERFACE
async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]
) -> str:
    """
    FastAPI dependency to extract and validate user from JWT token.
    
    This dependency extracts the JWT token from the Authorization header,
    validates it, and returns the user_id. Raises HTTP 401 on any failure.
    
    Args:
        credentials: HTTPAuthorizationCredentials from Authorization header
        
    Returns:
        str: Authenticated user_id from token
        
    Raises:
        HTTPException: 401 Unauthorized if token is missing, expired, or invalid
        
    Example:
        >>> from fastapi import APIRouter, Depends
        >>> from src.auth.dependencies import get_current_user
        >>>
        >>> router = APIRouter()
        >>>
        >>> @router.get("/cart")
        >>> async def get_cart(user_id: str = Depends(get_current_user)):
        ...     return {"user_id": user_id, "items": []}
        
    @compliance
    - Security: Validates JWT signature and expiration
    - Security: Returns 401 for any authentication failure
    - API Design: Standard Bearer token authentication
    - Logging: Logs authentication failures for security monitoring
    
    Note:
        This dependency automatically appears in FastAPI OpenAPI documentation
        with a "Authorize" button for testing authenticated endpoints.
        
    Usage in route:
        The user_id can be injected into any route handler:
        ```python
        @app.get("/api/cart")
        async def get_cart(user_id: str = Depends(get_current_user)):
            # user_id is automatically extracted and validated
            cart = await get_cart(user_id)
            return cart
        ```
    """
    if not credentials:
        logger.warning("Missing authentication credentials")
        raise AuthenticationError("Missing authentication token")
    
    token = credentials.credentials
    
    if not token or not token.strip():
        logger.warning("Empty authentication token")
        raise AuthenticationError("Invalid authentication token")
    
    try:
        # Extract and validate user_id from token
        user_id = extract_user_id(token)
        
        logger.debug(
            "User authenticated successfully",
            extra={"user_id": user_id}
        )
        
        return user_id
        
    except TokenExpiredError as e:
        logger.warning(
            "Authentication failed - token expired",
            extra={"error": str(e)}
        )
        raise AuthenticationError("Token has expired")
        
    except InvalidTokenError as e:
        logger.warning(
            "Authentication failed - invalid token",
            extra={"error": str(e)}
        )
        raise AuthenticationError("Invalid authentication token")
        
    except Exception as e:
        logger.error(
            "Unexpected authentication error",
            extra={"error": str(e)},
            exc_info=True
        )
        raise AuthenticationError("Authentication failed")


# PUBLIC_INTERFACE
async def get_optional_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(HTTPBearer(auto_error=False))
    ]
) -> str | None:
    """
    FastAPI dependency to extract user from JWT token (optional).
    
    This dependency is similar to get_current_user but does not raise
    an error if no token is provided. It returns None if authentication
    is not present or fails.
    
    Args:
        credentials: Optional HTTPAuthorizationCredentials from Authorization header
        
    Returns:
        Optional[str]: Authenticated user_id from token, or None if not authenticated
        
    Example:
        >>> @router.get("/public-cart")
        >>> async def get_public_cart(user_id: str | None = Depends(get_optional_user)):
        ...     if user_id:
        ...         return {"user_id": user_id, "items": [...]}
        ...     return {"message": "Anonymous cart"}
        
    @compliance
    - Security: Validates token if present, but allows anonymous access
    - API Design: Useful for endpoints that support both authenticated and anonymous access
    """
    if not credentials or not credentials.credentials:
        logger.debug("No authentication credentials provided")
        return None
    
    token = credentials.credentials
    
    try:
        user_id = extract_user_id(token)
        logger.debug(
            "Optional authentication successful",
            extra={"user_id": user_id}
        )
        return user_id
        
    except (TokenExpiredError, InvalidTokenError) as e:
        logger.debug(
            "Optional authentication failed",
            extra={"error": str(e)}
        )
        return None
        
    except Exception as e:
        logger.warning(
            "Unexpected error in optional authentication",
            extra={"error": str(e)}
        )
        return None


# Type alias for use in route handlers
CurrentUser = Annotated[str, Depends(get_current_user)]
OptionalUser = Annotated[str | None, Depends(get_optional_user)]
