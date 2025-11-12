"""
FastAPI application for cart management service.

This module defines the main FastAPI application with CORS middleware,
health check endpoints, and OpenAPI documentation configuration.

PUBLIC_INTERFACE
"""
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from src.auth.dependencies import get_current_user
from src.api.routes import cart_router

# Application metadata for OpenAPI documentation
app = FastAPI(
    title="Cart Management API",
    description="""
    Real-time cart management service with JWT authentication.
    
    ## Features
    * **JWT Authentication**: Secure endpoints with Bearer token authentication
    * **Cart Operations**: Get, add, update, remove, and clear cart items
    * **MongoDB Integration**: Fast and scalable cart storage with MongoDB Atlas
    * **Real-time Updates**: Efficient cart state management
    
    ## Authentication
    All protected endpoints require a JWT Bearer token in the Authorization header:
    ```
    Authorization: Bearer <your-jwt-token>
    ```
    
    The JWT token must contain a `user_id` claim that identifies the authenticated user.
    """,
    version="1.0.0",
    openapi_tags=[
        {
            "name": "health",
            "description": "Health check and system status endpoints"
        },
        {
            "name": "cart",
            "description": "Shopping cart management operations"
        }
    ]
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure via ALLOWED_ORIGINS environment variable
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include cart routes
app.include_router(cart_router)


@app.get(
    "/",
    tags=["health"],
    summary="Health check endpoint",
    description="Returns the health status of the service",
    response_description="Service health status"
)
async def health_check():
    """
    Health check endpoint.
    
    Returns a simple health status indicating the service is running.
    This endpoint does not require authentication.
    
    Returns:
        dict: Health status message
        
    Example:
        ```
        GET /
        Response: {"message": "Healthy"}
        ```
    
    @compliance
    - Monitoring: Standard health check for load balancers and monitoring systems
    """
    return {"message": "Healthy"}


@app.get(
    "/auth-test",
    tags=["health"],
    summary="Test authentication",
    description="Test endpoint to verify JWT authentication is working correctly",
    response_description="Authentication success message with user_id"
)
async def auth_test(user_id: str = Depends(get_current_user)):
    """
    Test authentication endpoint.
    
    This endpoint requires a valid JWT token and returns the authenticated user_id.
    Useful for testing JWT token generation and validation.
    
    Args:
        user_id: User ID extracted from JWT token (injected by dependency)
        
    Returns:
        dict: Message confirming authentication and the authenticated user_id
        
    Raises:
        HTTPException: 401 if authentication fails
        
    Example:
        ```
        GET /auth-test
        Headers:
          Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
        
        Response: {
          "message": "Authentication successful",
          "user_id": "user123"
        }
        ```
    
    @compliance
    - Security: Demonstrates proper JWT authentication usage
    - Testing: Allows verification of authentication configuration
    """
    return {
        "message": "Authentication successful",
        "user_id": user_id
    }
