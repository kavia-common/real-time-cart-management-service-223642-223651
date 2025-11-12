"""
Cart service business logic layer.

This module provides high-level business logic functions for cart operations,
building on top of the database layer. It includes validation, error handling,
and total recalculation logic.

PUBLIC_INTERFACE
"""
from typing import Dict, Any
import logging

from src.database import mongodb
from src.models.cart import CartItem, CartItemRequest, CartResponse
from src.database.mongodb import (
    DatabaseError,
    CartNotFoundError
)

# Module-level logger
logger = logging.getLogger(__name__)


class CartServiceError(Exception):
    """
    Base exception for cart service operations.
    
    @compliance
    - Error Handling: Centralized service error type
    """
    pass


class InvalidCartDataError(CartServiceError):
    """
    Exception raised when cart data validation fails.
    
    @compliance
    - Error Handling: Specific error for validation failures
    """
    pass


# PUBLIC_INTERFACE
async def get_user_cart(user_id: str) -> CartResponse:
    """
    Retrieve a user's cart with all items and calculated totals.
    
    This function retrieves the cart for a given user. If the cart doesn't exist,
    it creates a new empty cart automatically.
    
    Args:
        user_id: Unique identifier for the user
        
    Returns:
        CartResponse: User's cart with items and totals
        
    Raises:
        InvalidCartDataError: If user_id is invalid
        CartServiceError: If cart retrieval fails
        
    Example:
        >>> cart_response = await get_user_cart("user123")
        >>> print(f"Total: ${cart_response.total_amount}")
        >>> print(f"Items: {cart_response.item_count}")
        
    @compliance
    - Business Rules: Auto-creates cart if it doesn't exist
    - Data Integrity: Returns computed totals
    - Error Handling: Clean error propagation
    - Security: No sensitive data in logs
    """
    try:
        # Validate input
        if not user_id or not user_id.strip():
            logger.warning("Invalid user_id provided to get_user_cart")
            raise InvalidCartDataError("User ID cannot be empty")
        
        user_id = user_id.strip()
        
        logger.debug(
            "Retrieving cart for user",
            extra={"user_id": user_id}
        )
        
        # Get or create cart
        cart = await mongodb.create_or_get_cart(user_id)
        
        # Recalculate totals to ensure accuracy
        cart.recalculate_totals()
        
        # Convert to response model
        response = CartResponse.from_cart(cart)
        
        logger.info(
            "Cart retrieved successfully",
            extra={
                "user_id": user_id,
                "item_count": response.item_count,
                "total_amount": response.total_amount
            }
        )
        
        return response
        
    except ValueError as e:
        logger.warning(
            "Validation error in get_user_cart",
            extra={"user_id": user_id, "error": str(e)}
        )
        raise InvalidCartDataError(f"Invalid input: {str(e)}")
        
    except DatabaseError as e:
        logger.error(
            "Database error in get_user_cart",
            extra={"user_id": user_id, "error": str(e)},
            exc_info=True
        )
        raise CartServiceError(f"Failed to retrieve cart: {str(e)}")
        
    except Exception as e:
        logger.error(
            "Unexpected error in get_user_cart",
            extra={"user_id": user_id, "error": str(e)},
            exc_info=True
        )
        raise CartServiceError(f"Unexpected error: {str(e)}")


# PUBLIC_INTERFACE
async def add_item_to_cart(user_id: str, item_data: Dict[str, Any]) -> CartResponse:
    """
    Add a new item to the user's cart or update quantity if item exists.
    
    This function validates the item data, creates a CartItem, and adds it to
    the cart. If the product already exists in the cart, quantities are merged.
    Totals are automatically recalculated.
    
    Args:
        user_id: Unique identifier for the user
        item_data: Dictionary containing item information:
            - product_id (str): Product identifier
            - name (str): Product name
            - price (float): Unit price
            - quantity (int): Quantity to add (default: 1)
            
    Returns:
        CartResponse: Updated cart with the new/updated item
        
    Raises:
        InvalidCartDataError: If user_id or item_data is invalid
        CartServiceError: If add operation fails
        
    Example:
        >>> item = {
        ...     "product_id": "prod123",
        ...     "name": "Laptop",
        ...     "price": 999.99,
        ...     "quantity": 1
        ... }
        >>> cart = await add_item_to_cart("user123", item)
        >>> print(f"Total: ${cart.total_amount}")
        
    @compliance
    - Business Rules: Validates item data before adding
    - Business Rules: Merges quantities for existing products
    - Data Integrity: Recalculates totals after addition
    - Error Handling: Comprehensive validation and error messages
    """
    try:
        # Validate user_id
        if not user_id or not user_id.strip():
            logger.warning("Invalid user_id provided to add_item_to_cart")
            raise InvalidCartDataError("User ID cannot be empty")
        
        user_id = user_id.strip()
        
        # Validate item_data
        if not item_data or not isinstance(item_data, dict):
            logger.warning(
                "Invalid item_data provided to add_item_to_cart",
                extra={"user_id": user_id}
            )
            raise InvalidCartDataError("Item data must be a non-empty dictionary")
        
        logger.debug(
            "Adding item to cart",
            extra={
                "user_id": user_id,
                "product_id": item_data.get("product_id"),
                "quantity": item_data.get("quantity", 1)
            }
        )
        
        # Validate and create CartItem using Pydantic model
        try:
            cart_item_request = CartItemRequest(**item_data)
            cart_item = CartItem(
                product_id=cart_item_request.product_id,
                name=cart_item_request.name,
                price=cart_item_request.price,
                quantity=cart_item_request.quantity
            )
        except ValueError as e:
            logger.warning(
                "Item validation failed",
                extra={"user_id": user_id, "error": str(e)}
            )
            raise InvalidCartDataError(f"Invalid item data: {str(e)}")
        
        # Add item to cart in database
        cart = await mongodb.add_or_update_item(user_id, cart_item)
        
        # Recalculate totals
        cart.recalculate_totals()
        
        # Convert to response model
        response = CartResponse.from_cart(cart)
        
        logger.info(
            "Item added to cart successfully",
            extra={
                "user_id": user_id,
                "product_id": cart_item.product_id,
                "quantity": cart_item.quantity,
                "total_amount": response.total_amount
            }
        )
        
        return response
        
    except InvalidCartDataError:
        # Re-raise validation errors as-is
        raise
        
    except ValueError as e:
        logger.warning(
            "Validation error in add_item_to_cart",
            extra={"user_id": user_id, "error": str(e)}
        )
        raise InvalidCartDataError(f"Invalid input: {str(e)}")
        
    except DatabaseError as e:
        logger.error(
            "Database error in add_item_to_cart",
            extra={"user_id": user_id, "error": str(e)},
            exc_info=True
        )
        raise CartServiceError(f"Failed to add item to cart: {str(e)}")
        
    except Exception as e:
        logger.error(
            "Unexpected error in add_item_to_cart",
            extra={"user_id": user_id, "error": str(e)},
            exc_info=True
        )
        raise CartServiceError(f"Unexpected error: {str(e)}")


# PUBLIC_INTERFACE
async def update_cart_item(user_id: str, product_id: str, quantity: int) -> CartResponse:
    """
    Update the quantity of a specific item in the cart.
    
    This function updates the quantity of an existing cart item. The quantity
    must be at least 1. Totals are automatically recalculated after the update.
    
    Args:
        user_id: Unique identifier for the user
        product_id: ID of the product to update
        quantity: New quantity (must be >= 1)
        
    Returns:
        CartResponse: Updated cart with recalculated totals
        
    Raises:
        InvalidCartDataError: If user_id, product_id, or quantity is invalid
        CartServiceError: If update operation fails or product not found
        
    Example:
        >>> cart = await update_cart_item("user123", "prod123", 5)
        >>> print(f"Updated cart total: ${cart.total_amount}")
        
    @compliance
    - Business Rules: Quantity must be >= 1
    - Business Rules: Product must exist in cart
    - Data Integrity: Recalculates totals after update
    - Error Handling: Clear error messages for validation failures
    """
    try:
        # Validate user_id
        if not user_id or not user_id.strip():
            logger.warning("Invalid user_id provided to update_cart_item")
            raise InvalidCartDataError("User ID cannot be empty")
        
        user_id = user_id.strip()
        
        # Validate product_id
        if not product_id or not product_id.strip():
            logger.warning(
                "Invalid product_id provided to update_cart_item",
                extra={"user_id": user_id}
            )
            raise InvalidCartDataError("Product ID cannot be empty")
        
        product_id = product_id.strip()
        
        # Validate quantity
        if not isinstance(quantity, int) or quantity < 1:
            logger.warning(
                "Invalid quantity provided to update_cart_item",
                extra={"user_id": user_id, "product_id": product_id, "quantity": quantity}
            )
            raise InvalidCartDataError("Quantity must be an integer >= 1")
        
        if quantity > 10000:
            logger.warning(
                "Quantity exceeds maximum allowed",
                extra={"user_id": user_id, "product_id": product_id, "quantity": quantity}
            )
            raise InvalidCartDataError("Quantity exceeds maximum allowed (10000)")
        
        logger.debug(
            "Updating cart item quantity",
            extra={
                "user_id": user_id,
                "product_id": product_id,
                "new_quantity": quantity
            }
        )
        
        # Update item in database
        cart = await mongodb.update_item_qty(user_id, product_id, quantity)
        
        # Recalculate totals
        cart.recalculate_totals()
        
        # Convert to response model
        response = CartResponse.from_cart(cart)
        
        logger.info(
            "Cart item updated successfully",
            extra={
                "user_id": user_id,
                "product_id": product_id,
                "new_quantity": quantity,
                "total_amount": response.total_amount
            }
        )
        
        return response
        
    except InvalidCartDataError:
        # Re-raise validation errors as-is
        raise
        
    except CartNotFoundError as e:
        logger.warning(
            "Cart not found in update_cart_item",
            extra={"user_id": user_id, "error": str(e)}
        )
        raise CartServiceError(f"Cart not found for user {user_id}")
        
    except ValueError as e:
        logger.warning(
            "Validation error in update_cart_item",
            extra={"user_id": user_id, "product_id": product_id, "error": str(e)}
        )
        raise InvalidCartDataError(f"Invalid input: {str(e)}")
        
    except DatabaseError as e:
        logger.error(
            "Database error in update_cart_item",
            extra={"user_id": user_id, "product_id": product_id, "error": str(e)},
            exc_info=True
        )
        raise CartServiceError(f"Failed to update cart item: {str(e)}")
        
    except Exception as e:
        logger.error(
            "Unexpected error in update_cart_item",
            extra={"user_id": user_id, "product_id": product_id, "error": str(e)},
            exc_info=True
        )
        raise CartServiceError(f"Unexpected error: {str(e)}")


# PUBLIC_INTERFACE
async def remove_cart_item(user_id: str, product_id: str) -> CartResponse:
    """
    Remove a specific item from the user's cart.
    
    This function removes an item from the cart by product_id. Totals are
    automatically recalculated after removal.
    
    Args:
        user_id: Unique identifier for the user
        product_id: ID of the product to remove
        
    Returns:
        CartResponse: Updated cart with item removed and recalculated totals
        
    Raises:
        InvalidCartDataError: If user_id or product_id is invalid
        CartServiceError: If removal operation fails or product not found
        
    Example:
        >>> cart = await remove_cart_item("user123", "prod123")
        >>> print(f"Remaining items: {cart.item_count}")
        
    @compliance
    - Business Rules: Product must exist in cart
    - Data Integrity: Recalculates totals after removal
    - Error Handling: Clear error messages for validation failures
    """
    try:
        # Validate user_id
        if not user_id or not user_id.strip():
            logger.warning("Invalid user_id provided to remove_cart_item")
            raise InvalidCartDataError("User ID cannot be empty")
        
        user_id = user_id.strip()
        
        # Validate product_id
        if not product_id or not product_id.strip():
            logger.warning(
                "Invalid product_id provided to remove_cart_item",
                extra={"user_id": user_id}
            )
            raise InvalidCartDataError("Product ID cannot be empty")
        
        product_id = product_id.strip()
        
        logger.debug(
            "Removing item from cart",
            extra={"user_id": user_id, "product_id": product_id}
        )
        
        # Remove item from database
        cart = await mongodb.remove_item(user_id, product_id)
        
        # Recalculate totals
        cart.recalculate_totals()
        
        # Convert to response model
        response = CartResponse.from_cart(cart)
        
        logger.info(
            "Cart item removed successfully",
            extra={
                "user_id": user_id,
                "product_id": product_id,
                "remaining_items": response.item_count,
                "total_amount": response.total_amount
            }
        )
        
        return response
        
    except InvalidCartDataError:
        # Re-raise validation errors as-is
        raise
        
    except CartNotFoundError as e:
        logger.warning(
            "Cart not found in remove_cart_item",
            extra={"user_id": user_id, "error": str(e)}
        )
        raise CartServiceError(f"Cart not found for user {user_id}")
        
    except ValueError as e:
        logger.warning(
            "Validation error in remove_cart_item",
            extra={"user_id": user_id, "product_id": product_id, "error": str(e)}
        )
        raise InvalidCartDataError(f"Invalid input: {str(e)}")
        
    except DatabaseError as e:
        logger.error(
            "Database error in remove_cart_item",
            extra={"user_id": user_id, "product_id": product_id, "error": str(e)},
            exc_info=True
        )
        raise CartServiceError(f"Failed to remove cart item: {str(e)}")
        
    except Exception as e:
        logger.error(
            "Unexpected error in remove_cart_item",
            extra={"user_id": user_id, "product_id": product_id, "error": str(e)},
            exc_info=True
        )
        raise CartServiceError(f"Unexpected error: {str(e)}")


# PUBLIC_INTERFACE
async def clear_user_cart(user_id: str) -> CartResponse:
    """
    Remove all items from the user's cart.
    
    This function empties the cart but preserves the cart structure itself.
    The cart will have zero items and a total of 0.00 after this operation.
    
    Args:
        user_id: Unique identifier for the user
        
    Returns:
        CartResponse: Empty cart with zero items and zero total
        
    Raises:
        InvalidCartDataError: If user_id is invalid
        CartServiceError: If clear operation fails
        
    Example:
        >>> cart = await clear_user_cart("user123")
        >>> print(f"Items: {cart.item_count}, Total: ${cart.total_amount}")
        Items: 0, Total: $0.0
        
    @compliance
    - Business Rules: Preserves cart metadata (created_at)
    - Data Integrity: Sets totals to zero
    - Error Handling: Clear error messages for validation failures
    """
    try:
        # Validate user_id
        if not user_id or not user_id.strip():
            logger.warning("Invalid user_id provided to clear_user_cart")
            raise InvalidCartDataError("User ID cannot be empty")
        
        user_id = user_id.strip()
        
        logger.debug(
            "Clearing cart for user",
            extra={"user_id": user_id}
        )
        
        # Clear cart in database
        cart = await mongodb.clear_cart(user_id)
        
        # Recalculate totals (should be zero)
        cart.recalculate_totals()
        
        # Convert to response model
        response = CartResponse.from_cart(cart)
        
        logger.info(
            "Cart cleared successfully",
            extra={
                "user_id": user_id,
                "item_count": response.item_count,
                "total_amount": response.total_amount
            }
        )
        
        return response
        
    except InvalidCartDataError:
        # Re-raise validation errors as-is
        raise
        
    except CartNotFoundError as e:
        logger.warning(
            "Cart not found in clear_user_cart",
            extra={"user_id": user_id, "error": str(e)}
        )
        raise CartServiceError(f"Cart not found for user {user_id}")
        
    except ValueError as e:
        logger.warning(
            "Validation error in clear_user_cart",
            extra={"user_id": user_id, "error": str(e)}
        )
        raise InvalidCartDataError(f"Invalid input: {str(e)}")
        
    except DatabaseError as e:
        logger.error(
            "Database error in clear_user_cart",
            extra={"user_id": user_id, "error": str(e)},
            exc_info=True
        )
        raise CartServiceError(f"Failed to clear cart: {str(e)}")
        
    except Exception as e:
        logger.error(
            "Unexpected error in clear_user_cart",
            extra={"user_id": user_id, "error": str(e)},
            exc_info=True
        )
        raise CartServiceError(f"Unexpected error: {str(e)}")
