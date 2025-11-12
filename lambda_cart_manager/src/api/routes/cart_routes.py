"""
Cart management API routes.

This module defines all cart-related endpoints with JWT authentication,
input validation, and comprehensive error handling.

PUBLIC_INTERFACE
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Body
from pydantic import ValidationError

from src.auth.dependencies import get_current_user
from src.models.cart import (
    CartResponse,
    CartItemRequest,
    UpdateQuantityRequest
)
from src.services.cart_service import (
    get_user_cart,
    add_item_to_cart,
    update_cart_item,
    remove_cart_item,
    clear_user_cart,
    CartServiceError,
    InvalidCartDataError
)

# Module-level logger
logger = logging.getLogger(__name__)

# Create router with cart tag
router = APIRouter(
    prefix="/cart",
    tags=["cart"]
)


# PUBLIC_INTERFACE
@router.get(
    "",
    response_model=CartResponse,
    summary="Get user's cart",
    description="Retrieve the current user's shopping cart with all items and totals",
    response_description="Cart with items and calculated totals",
    responses={
        200: {
            "description": "Cart retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "user_id": "user123",
                        "items": [
                            {
                                "product_id": "prod1",
                                "name": "Laptop",
                                "price": 999.99,
                                "quantity": 1,
                                "added_at": "2025-01-12T10:30:00.000Z"
                            }
                        ],
                        "total_amount": 999.99,
                        "item_count": 1,
                        "created_at": "2025-01-12T10:30:00.000Z",
                        "updated_at": "2025-01-12T10:30:00.000Z"
                    }
                }
            }
        },
        401: {"description": "Unauthorized - Invalid or missing JWT token"},
        500: {"description": "Internal server error"}
    }
)
async def get_cart(user_id: str = Depends(get_current_user)) -> CartResponse:
    """
    Get the current user's shopping cart.
    
    This endpoint retrieves the authenticated user's cart with all items,
    quantities, and calculated totals. If the cart doesn't exist, an empty
    cart is automatically created and returned.
    
    Args:
        user_id: User ID extracted from JWT token (injected by dependency)
        
    Returns:
        CartResponse: User's cart with items and totals
        
    Raises:
        HTTPException: 401 if authentication fails
        HTTPException: 500 if cart retrieval fails
        
    Example:
        ```
        GET /cart
        Headers:
          Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
        
        Response: {
          "user_id": "user123",
          "items": [...],
          "total_amount": 999.99,
          "item_count": 1,
          "created_at": "2025-01-12T10:30:00.000Z",
          "updated_at": "2025-01-12T10:30:00.000Z"
        }
        ```
    
    @compliance
    - Security: JWT authentication required
    - Business Rules: Auto-creates cart if doesn't exist
    - Performance: Returns computed totals
    """
    try:
        logger.info(
            "Get cart request",
            extra={"user_id": user_id}
        )
        
        cart = await get_user_cart(user_id)
        
        logger.info(
            "Cart retrieved successfully",
            extra={
                "user_id": user_id,
                "item_count": cart.item_count,
                "total_amount": cart.total_amount
            }
        )
        
        return cart
        
    except CartServiceError as e:
        logger.error(
            "Failed to retrieve cart",
            extra={"user_id": user_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve cart: {str(e)}"
        )
        
    except Exception as e:
        logger.error(
            "Unexpected error in get_cart",
            extra={"user_id": user_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )


# PUBLIC_INTERFACE
@router.post(
    "/items",
    response_model=CartResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add item to cart",
    description="Add a new item to the cart or update quantity if item already exists",
    response_description="Updated cart with the new/updated item",
    responses={
        201: {
            "description": "Item added successfully",
            "content": {
                "application/json": {
                    "example": {
                        "user_id": "user123",
                        "items": [
                            {
                                "product_id": "prod1",
                                "name": "Laptop",
                                "price": 999.99,
                                "quantity": 2,
                                "added_at": "2025-01-12T10:30:00.000Z"
                            }
                        ],
                        "total_amount": 1999.98,
                        "item_count": 2,
                        "created_at": "2025-01-12T10:30:00.000Z",
                        "updated_at": "2025-01-12T10:31:00.000Z"
                    }
                }
            }
        },
        400: {"description": "Bad request - Invalid item data"},
        401: {"description": "Unauthorized - Invalid or missing JWT token"},
        500: {"description": "Internal server error"}
    }
)
async def add_item(
    item: CartItemRequest = Body(
        ...,
        description="Item to add to cart",
        example={
            "product_id": "prod123",
            "name": "Wireless Keyboard",
            "price": 59.99,
            "quantity": 1
        }
    ),
    user_id: str = Depends(get_current_user)
) -> CartResponse:
    """
    Add a new item to the cart or update quantity if it exists.
    
    This endpoint adds a new product to the cart. If the product already
    exists in the cart, the quantities are merged. All prices and totals
    are automatically calculated.
    
    Args:
        item: CartItemRequest containing product details
        user_id: User ID extracted from JWT token (injected by dependency)
        
    Returns:
        CartResponse: Updated cart with the new/updated item
        
    Raises:
        HTTPException: 400 if item data is invalid
        HTTPException: 401 if authentication fails
        HTTPException: 500 if add operation fails
        
    Example:
        ```
        POST /cart/items
        Headers:
          Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
        Body:
          {
            "product_id": "prod123",
            "name": "Wireless Keyboard",
            "price": 59.99,
            "quantity": 1
          }
        
        Response: {
          "user_id": "user123",
          "items": [...],
          "total_amount": 1059.98,
          "item_count": 2,
          ...
        }
        ```
    
    @compliance
    - Security: JWT authentication required
    - Validation: Pydantic model validates all inputs
    - Business Rules: Merges quantities for existing products
    - Data Integrity: Recalculates totals automatically
    """
    try:
        logger.info(
            "Add item request",
            extra={
                "user_id": user_id,
                "product_id": item.product_id,
                "quantity": item.quantity
            }
        )
        
        # Convert Pydantic model to dict
        item_data = item.model_dump()
        
        cart = await add_item_to_cart(user_id, item_data)
        
        logger.info(
            "Item added successfully",
            extra={
                "user_id": user_id,
                "product_id": item.product_id,
                "total_amount": cart.total_amount
            }
        )
        
        return cart
        
    except ValidationError as e:
        logger.warning(
            "Invalid item data",
            extra={"user_id": user_id, "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid item data: {str(e)}"
        )
        
    except InvalidCartDataError as e:
        logger.warning(
            "Invalid cart data",
            extra={"user_id": user_id, "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
        
    except CartServiceError as e:
        logger.error(
            "Failed to add item to cart",
            extra={"user_id": user_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add item: {str(e)}"
        )
        
    except Exception as e:
        logger.error(
            "Unexpected error in add_item",
            extra={"user_id": user_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )


# PUBLIC_INTERFACE
@router.put(
    "/items/{product_id}",
    response_model=CartResponse,
    summary="Update item quantity",
    description="Update the quantity of a specific item in the cart",
    response_description="Updated cart with modified item quantity",
    responses={
        200: {
            "description": "Item quantity updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "user_id": "user123",
                        "items": [
                            {
                                "product_id": "prod1",
                                "name": "Laptop",
                                "price": 999.99,
                                "quantity": 5,
                                "added_at": "2025-01-12T10:30:00.000Z"
                            }
                        ],
                        "total_amount": 4999.95,
                        "item_count": 5,
                        "created_at": "2025-01-12T10:30:00.000Z",
                        "updated_at": "2025-01-12T10:35:00.000Z"
                    }
                }
            }
        },
        400: {"description": "Bad request - Invalid quantity or product not found"},
        401: {"description": "Unauthorized - Invalid or missing JWT token"},
        500: {"description": "Internal server error"}
    }
)
async def update_item_quantity(
    product_id: str,
    quantity_update: UpdateQuantityRequest = Body(
        ...,
        description="New quantity for the item",
        example={"quantity": 3}
    ),
    user_id: str = Depends(get_current_user)
) -> CartResponse:
    """
    Update the quantity of a specific item in the cart.
    
    This endpoint updates the quantity of an existing cart item. The quantity
    must be at least 1. Totals are automatically recalculated.
    
    Args:
        product_id: ID of the product to update
        quantity_update: UpdateQuantityRequest with new quantity
        user_id: User ID extracted from JWT token (injected by dependency)
        
    Returns:
        CartResponse: Updated cart with modified quantity and recalculated totals
        
    Raises:
        HTTPException: 400 if quantity is invalid or product not found
        HTTPException: 401 if authentication fails
        HTTPException: 500 if update operation fails
        
    Example:
        ```
        PUT /cart/items/prod123
        Headers:
          Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
        Body:
          {
            "quantity": 3
          }
        
        Response: {
          "user_id": "user123",
          "items": [...],
          "total_amount": 179.97,
          ...
        }
        ```
    
    @compliance
    - Security: JWT authentication required
    - Validation: Quantity must be >= 1
    - Business Rules: Product must exist in cart
    - Data Integrity: Recalculates totals automatically
    """
    try:
        logger.info(
            "Update item quantity request",
            extra={
                "user_id": user_id,
                "product_id": product_id,
                "new_quantity": quantity_update.quantity
            }
        )
        
        cart = await update_cart_item(user_id, product_id, quantity_update.quantity)
        
        logger.info(
            "Item quantity updated successfully",
            extra={
                "user_id": user_id,
                "product_id": product_id,
                "new_quantity": quantity_update.quantity,
                "total_amount": cart.total_amount
            }
        )
        
        return cart
        
    except ValidationError as e:
        logger.warning(
            "Invalid quantity data",
            extra={"user_id": user_id, "product_id": product_id, "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid quantity: {str(e)}"
        )
        
    except InvalidCartDataError as e:
        logger.warning(
            "Invalid update request",
            extra={"user_id": user_id, "product_id": product_id, "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
        
    except CartServiceError as e:
        logger.error(
            "Failed to update item quantity",
            extra={"user_id": user_id, "product_id": product_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update item: {str(e)}"
        )
        
    except Exception as e:
        logger.error(
            "Unexpected error in update_item_quantity",
            extra={"user_id": user_id, "product_id": product_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )


# PUBLIC_INTERFACE
@router.delete(
    "/items/{product_id}",
    response_model=CartResponse,
    summary="Remove item from cart",
    description="Remove a specific item from the cart",
    response_description="Updated cart with item removed",
    responses={
        200: {
            "description": "Item removed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "user_id": "user123",
                        "items": [],
                        "total_amount": 0.0,
                        "item_count": 0,
                        "created_at": "2025-01-12T10:30:00.000Z",
                        "updated_at": "2025-01-12T10:40:00.000Z"
                    }
                }
            }
        },
        400: {"description": "Bad request - Product not found in cart"},
        401: {"description": "Unauthorized - Invalid or missing JWT token"},
        500: {"description": "Internal server error"}
    }
)
async def remove_item(
    product_id: str,
    user_id: str = Depends(get_current_user)
) -> CartResponse:
    """
    Remove a specific item from the cart.
    
    This endpoint removes an item from the cart by product_id. Totals are
    automatically recalculated after removal.
    
    Args:
        product_id: ID of the product to remove
        user_id: User ID extracted from JWT token (injected by dependency)
        
    Returns:
        CartResponse: Updated cart with item removed and recalculated totals
        
    Raises:
        HTTPException: 400 if product not found in cart
        HTTPException: 401 if authentication fails
        HTTPException: 500 if removal operation fails
        
    Example:
        ```
        DELETE /cart/items/prod123
        Headers:
          Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
        
        Response: {
          "user_id": "user123",
          "items": [...remaining items...],
          "total_amount": 999.99,
          "item_count": 1,
          ...
        }
        ```
    
    @compliance
    - Security: JWT authentication required
    - Business Rules: Product must exist in cart
    - Data Integrity: Recalculates totals automatically
    """
    try:
        logger.info(
            "Remove item request",
            extra={"user_id": user_id, "product_id": product_id}
        )
        
        cart = await remove_cart_item(user_id, product_id)
        
        logger.info(
            "Item removed successfully",
            extra={
                "user_id": user_id,
                "product_id": product_id,
                "remaining_items": cart.item_count
            }
        )
        
        return cart
        
    except InvalidCartDataError as e:
        logger.warning(
            "Invalid remove request",
            extra={"user_id": user_id, "product_id": product_id, "error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
        
    except CartServiceError as e:
        logger.error(
            "Failed to remove item",
            extra={"user_id": user_id, "product_id": product_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove item: {str(e)}"
        )
        
    except Exception as e:
        logger.error(
            "Unexpected error in remove_item",
            extra={"user_id": user_id, "product_id": product_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )


# PUBLIC_INTERFACE
@router.delete(
    "",
    response_model=CartResponse,
    summary="Clear cart",
    description="Remove all items from the cart",
    response_description="Empty cart with zero items and zero total",
    responses={
        200: {
            "description": "Cart cleared successfully",
            "content": {
                "application/json": {
                    "example": {
                        "user_id": "user123",
                        "items": [],
                        "total_amount": 0.0,
                        "item_count": 0,
                        "created_at": "2025-01-12T10:30:00.000Z",
                        "updated_at": "2025-01-12T10:45:00.000Z"
                    }
                }
            }
        },
        401: {"description": "Unauthorized - Invalid or missing JWT token"},
        500: {"description": "Internal server error"}
    }
)
async def clear_cart(
    user_id: str = Depends(get_current_user)
) -> CartResponse:
    """
    Remove all items from the cart.
    
    This endpoint empties the cart but preserves the cart structure itself.
    The cart will have zero items and a total of 0.00 after this operation.
    
    Args:
        user_id: User ID extracted from JWT token (injected by dependency)
        
    Returns:
        CartResponse: Empty cart with zero items and zero total
        
    Raises:
        HTTPException: 401 if authentication fails
        HTTPException: 500 if clear operation fails
        
    Example:
        ```
        DELETE /cart
        Headers:
          Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
        
        Response: {
          "user_id": "user123",
          "items": [],
          "total_amount": 0.0,
          "item_count": 0,
          ...
        }
        ```
    
    @compliance
    - Security: JWT authentication required
    - Business Rules: Preserves cart metadata (created_at)
    - Data Integrity: Sets totals to zero
    """
    try:
        logger.info(
            "Clear cart request",
            extra={"user_id": user_id}
        )
        
        cart = await clear_user_cart(user_id)
        
        logger.info(
            "Cart cleared successfully",
            extra={"user_id": user_id}
        )
        
        return cart
        
    except CartServiceError as e:
        logger.error(
            "Failed to clear cart",
            extra={"user_id": user_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear cart: {str(e)}"
        )
        
    except Exception as e:
        logger.error(
            "Unexpected error in clear_cart",
            extra={"user_id": user_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )
