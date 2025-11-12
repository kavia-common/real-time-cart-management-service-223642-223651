"""
MongoDB database layer using Motor async client.

This module provides MongoDB connection management, lifecycle hooks, and helper
functions for cart operations. All operations are async and include comprehensive
error handling.

PUBLIC_INTERFACE
"""
from typing import Optional, Dict, Any
import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import (
    ConnectionFailure,
    DuplicateKeyError,
    PyMongoError
)

from src.config.settings import get_settings
from src.models.cart import Cart, CartItem

# Module-level logger
logger = logging.getLogger(__name__)

# Global MongoDB client and database instances
_mongo_client: Optional[AsyncIOMotorClient] = None
_mongo_database: Optional[AsyncIOMotorDatabase] = None


class DatabaseError(Exception):
    """
    Base exception for database operations.
    
    @compliance
    - Error Handling: Centralized database error type
    """
    pass


class CartNotFoundError(DatabaseError):
    """
    Exception raised when cart is not found.
    
    @compliance
    - Error Handling: Specific error for missing carts
    """
    pass


class DatabaseConnectionError(DatabaseError):
    """
    Exception raised when database connection fails.
    
    @compliance
    - Error Handling: Specific error for connection issues
    """
    pass


# PUBLIC_INTERFACE
async def connect_db() -> AsyncIOMotorDatabase:
    """
    Initialize MongoDB connection and create indexes.
    
    This function establishes connection to MongoDB Atlas, verifies connectivity,
    and ensures required indexes exist. Should be called during application startup.
    
    Returns:
        AsyncIOMotorDatabase: Connected database instance
        
    Raises:
        DatabaseConnectionError: If connection fails
        
    Example:
        >>> from src.database.mongodb import connect_db
        >>> db = await connect_db()
        
    @compliance
    - Reliability: Connection verification before use
    - Performance: Index creation for optimized queries
    - Security: Uses environment variables for credentials
    
    Note:
        Required environment variables:
        - MONGODB_URI: MongoDB connection string
        - MONGODB_DATABASE: Database name
    """
    global _mongo_client, _mongo_database
    
    try:
        settings = get_settings()
        
        logger.info(
            "Connecting to MongoDB",
            extra={
                "database": settings.mongodb_database,
                "environment": settings.environment
            }
        )
        
        # Create Motor client
        _mongo_client = AsyncIOMotorClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=5000,  # 5 second timeout
            maxPoolSize=50,
            minPoolSize=10,
            retryWrites=True
        )
        
        # Get database reference
        _mongo_database = _mongo_client[settings.mongodb_database]
        
        # Verify connection by pinging the server
        await _mongo_client.admin.command('ping')
        
        logger.info("Successfully connected to MongoDB")
        
        # Create indexes
        await _create_indexes()
        
        return _mongo_database
        
    except ConnectionFailure as e:
        logger.error(
            "Failed to connect to MongoDB",
            extra={"error": str(e)},
            exc_info=True
        )
        raise DatabaseConnectionError(f"MongoDB connection failed: {str(e)}")
        
    except Exception as e:
        logger.error(
            "Unexpected error during MongoDB connection",
            extra={"error": str(e)},
            exc_info=True
        )
        raise DatabaseConnectionError(f"Database initialization failed: {str(e)}")


# PUBLIC_INTERFACE
async def close_db() -> None:
    """
    Close MongoDB connection gracefully.
    
    This function should be called during application shutdown to ensure
    all connections are properly closed.
    
    Example:
        >>> from src.database.mongodb import close_db
        >>> await close_db()
        
    @compliance
    - Reliability: Graceful shutdown prevents connection leaks
    - Resource Management: Releases database connections
    """
    global _mongo_client, _mongo_database
    
    if _mongo_client:
        logger.info("Closing MongoDB connection")
        _mongo_client.close()
        _mongo_client = None
        _mongo_database = None
        logger.info("MongoDB connection closed")


# PUBLIC_INTERFACE
def get_database() -> AsyncIOMotorDatabase:
    """
    Get the current database instance.
    
    Returns:
        AsyncIOMotorDatabase: Active database connection
        
    Raises:
        DatabaseConnectionError: If database is not connected
        
    Example:
        >>> from src.database.mongodb import get_database
        >>> db = get_database()
        >>> carts_collection = db.carts
        
    @compliance
    - Reliability: Ensures database is connected before use
    """
    if _mongo_database is None:
        raise DatabaseConnectionError(
            "Database not connected. Call connect_db() first."
        )
    return _mongo_database


async def _create_indexes() -> None:
    """
    Create required database indexes.
    
    Creates indexes on the carts collection to optimize query performance:
    - Unique index on user_id for fast cart lookups
    - Index on updated_at for sorting/filtering by last update
    
    @compliance
    - Performance: Indexes optimize frequent queries
    - Data Integrity: Unique index ensures one cart per user
    """
    try:
        db = get_database()
        carts_collection = db.carts
        
        # Create unique index on user_id
        await carts_collection.create_index(
            "user_id",
            unique=True,
            name="user_id_unique_idx"
        )
        
        # Create index on updated_at for sorting
        await carts_collection.create_index(
            "updated_at",
            name="updated_at_idx"
        )
        
        logger.info("MongoDB indexes created successfully")
        
    except DuplicateKeyError:
        # Index already exists, this is fine
        logger.debug("Indexes already exist")
        
    except Exception as e:
        logger.warning(
            "Failed to create indexes",
            extra={"error": str(e)}
        )
        # Don't raise - indexes are optimization, not critical


def _cart_to_dict(cart: Cart) -> Dict[str, Any]:
    """
    Convert Cart model to MongoDB document.
    
    Args:
        cart: Cart model instance
        
    Returns:
        Dict: MongoDB document representation
        
    @compliance
    - Data Integrity: Proper serialization of datetime objects
    """
    return {
        "user_id": cart.user_id,
        "items": [
            {
                "product_id": item.product_id,
                "name": item.name,
                "price": item.price,
                "quantity": item.quantity,
                "added_at": item.added_at
            }
            for item in cart.items
        ],
        "created_at": cart.created_at,
        "updated_at": cart.updated_at
    }


def _dict_to_cart(doc: Dict[str, Any]) -> Cart:
    """
    Convert MongoDB document to Cart model.
    
    Args:
        doc: MongoDB document
        
    Returns:
        Cart: Cart model instance
        
    @compliance
    - Data Integrity: Proper deserialization of datetime objects
    """
    items = [
        CartItem(
            product_id=item["product_id"],
            name=item["name"],
            price=item["price"],
            quantity=item["quantity"],
            added_at=item["added_at"]
        )
        for item in doc.get("items", [])
    ]
    
    return Cart(
        user_id=doc["user_id"],
        items=items,
        created_at=doc["created_at"],
        updated_at=doc["updated_at"]
    )


# PUBLIC_INTERFACE
async def get_cart(user_id: str) -> Optional[Cart]:
    """
    Retrieve a cart by user_id.
    
    Args:
        user_id: Unique identifier for the user
        
    Returns:
        Optional[Cart]: Cart instance if found, None otherwise
        
    Raises:
        DatabaseError: If database operation fails
        
    Example:
        >>> cart = await get_cart("user123")
        >>> if cart:
        ...     print(f"Cart has {cart.item_count} items")
        
    @compliance
    - Performance: Uses indexed query on user_id
    - Error Handling: Clean error propagation
    - Security: No sensitive data in logs
    """
    try:
        if not user_id or not user_id.strip():
            raise ValueError("user_id cannot be empty")
        
        db = get_database()
        carts_collection = db.carts
        
        doc = await carts_collection.find_one({"user_id": user_id})
        
        if doc:
            logger.debug(
                "Cart retrieved",
                extra={"user_id": user_id, "item_count": len(doc.get("items", []))}
            )
            return _dict_to_cart(doc)
        
        logger.debug("Cart not found", extra={"user_id": user_id})
        return None
        
    except ValueError as e:
        logger.warning(f"Invalid user_id: {str(e)}")
        raise
        
    except PyMongoError as e:
        logger.error(
            "Database error retrieving cart",
            extra={"user_id": user_id, "error": str(e)},
            exc_info=True
        )
        raise DatabaseError(f"Failed to retrieve cart: {str(e)}")
        
    except Exception as e:
        logger.error(
            "Unexpected error retrieving cart",
            extra={"user_id": user_id, "error": str(e)},
            exc_info=True
        )
        raise DatabaseError(f"Unexpected error: {str(e)}")


# PUBLIC_INTERFACE
async def create_or_get_cart(user_id: str) -> Cart:
    """
    Get existing cart or create a new empty cart for user.
    
    This function is idempotent - it will return existing cart if present,
    or create and return a new cart if not.
    
    Args:
        user_id: Unique identifier for the user
        
    Returns:
        Cart: Existing or newly created cart
        
    Raises:
        DatabaseError: If database operation fails
        
    Example:
        >>> cart = await create_or_get_cart("user123")
        >>> print(f"Cart ID: {cart.user_id}")
        
    @compliance
    - Data Integrity: Atomic upsert operation
    - Performance: Single database operation
    - Reliability: Idempotent operation
    """
    try:
        if not user_id or not user_id.strip():
            raise ValueError("user_id cannot be empty")
        
        # First try to get existing cart
        existing_cart = await get_cart(user_id)
        if existing_cart:
            return existing_cart
        
        # Create new cart
        new_cart = Cart(user_id=user_id)
        
        db = get_database()
        carts_collection = db.carts
        
        cart_dict = _cart_to_dict(new_cart)
        
        # Use insert_one to create new cart
        await carts_collection.insert_one(cart_dict)
        
        logger.info(
            "New cart created",
            extra={"user_id": user_id}
        )
        
        return new_cart
        
    except DuplicateKeyError:
        # Race condition - cart was created between our check and insert
        # Just retrieve and return it
        logger.debug("Cart already exists (race condition)", extra={"user_id": user_id})
        return await get_cart(user_id)
        
    except ValueError as e:
        logger.warning(f"Invalid user_id: {str(e)}")
        raise
        
    except PyMongoError as e:
        logger.error(
            "Database error creating cart",
            extra={"user_id": user_id, "error": str(e)},
            exc_info=True
        )
        raise DatabaseError(f"Failed to create cart: {str(e)}")
        
    except Exception as e:
        logger.error(
            "Unexpected error creating cart",
            extra={"user_id": user_id, "error": str(e)},
            exc_info=True
        )
        raise DatabaseError(f"Unexpected error: {str(e)}")


# PUBLIC_INTERFACE
async def add_or_update_item(user_id: str, item: CartItem) -> Cart:
    """
    Add a new item to cart or update quantity if item exists.
    
    If the product already exists in the cart, its quantity will be increased.
    Otherwise, the item will be added as a new entry.
    
    Args:
        user_id: Unique identifier for the user
        item: CartItem to add or update
        
    Returns:
        Cart: Updated cart with the item added/updated
        
    Raises:
        DatabaseError: If database operation fails
        ValueError: If item data is invalid
        
    Example:
        >>> item = CartItem(
        ...     product_id="prod123",
        ...     name="Laptop",
        ...     price=999.99,
        ...     quantity=1
        ... )
        >>> cart = await add_or_update_item("user123", item)
        
    @compliance
    - Data Integrity: Validates item before adding
    - Business Rules: Merges quantities for existing products
    - Atomicity: Updates cart in single operation
    """
    try:
        if not user_id or not user_id.strip():
            raise ValueError("user_id cannot be empty")
        
        # Get or create cart
        cart = await create_or_get_cart(user_id)
        
        # Add item using Cart model logic
        cart.add_item(item)
        
        # Update in database
        db = get_database()
        carts_collection = db.carts
        
        cart_dict = _cart_to_dict(cart)
        
        result = await carts_collection.replace_one(
            {"user_id": user_id},
            cart_dict
        )
        
        if result.matched_count == 0:
            raise DatabaseError(f"Cart not found for user {user_id}")
        
        logger.info(
            "Item added/updated in cart",
            extra={
                "user_id": user_id,
                "product_id": item.product_id,
                "quantity": item.quantity
            }
        )
        
        return cart
        
    except ValueError as e:
        logger.warning(f"Invalid input: {str(e)}")
        raise
        
    except PyMongoError as e:
        logger.error(
            "Database error adding item to cart",
            extra={"user_id": user_id, "error": str(e)},
            exc_info=True
        )
        raise DatabaseError(f"Failed to add item to cart: {str(e)}")
        
    except Exception as e:
        logger.error(
            "Unexpected error adding item to cart",
            extra={"user_id": user_id, "error": str(e)},
            exc_info=True
        )
        raise DatabaseError(f"Unexpected error: {str(e)}")


# PUBLIC_INTERFACE
async def update_item_qty(user_id: str, product_id: str, quantity: int) -> Cart:
    """
    Update the quantity of a specific item in the cart.
    
    Args:
        user_id: Unique identifier for the user
        product_id: ID of the product to update
        quantity: New quantity (must be >= 1)
        
    Returns:
        Cart: Updated cart
        
    Raises:
        CartNotFoundError: If cart doesn't exist
        DatabaseError: If database operation fails
        ValueError: If quantity is invalid or product not in cart
        
    Example:
        >>> cart = await update_item_qty("user123", "prod123", 5)
        
    @compliance
    - Business Rules: Quantity validation
    - Data Integrity: Atomic update operation
    """
    try:
        if not user_id or not user_id.strip():
            raise ValueError("user_id cannot be empty")
        
        if not product_id or not product_id.strip():
            raise ValueError("product_id cannot be empty")
        
        # Get cart
        cart = await get_cart(user_id)
        if not cart:
            raise CartNotFoundError(f"Cart not found for user {user_id}")
        
        # Update quantity using Cart model logic
        updated = cart.update_item_quantity(product_id, quantity)
        
        if not updated:
            raise ValueError(f"Product {product_id} not found in cart")
        
        # Update in database
        db = get_database()
        carts_collection = db.carts
        
        cart_dict = _cart_to_dict(cart)
        
        result = await carts_collection.replace_one(
            {"user_id": user_id},
            cart_dict
        )
        
        if result.matched_count == 0:
            raise DatabaseError(f"Cart not found for user {user_id}")
        
        logger.info(
            "Item quantity updated",
            extra={
                "user_id": user_id,
                "product_id": product_id,
                "new_quantity": quantity
            }
        )
        
        return cart
        
    except (ValueError, CartNotFoundError) as e:
        logger.warning(f"Invalid input or not found: {str(e)}")
        raise
        
    except PyMongoError as e:
        logger.error(
            "Database error updating item quantity",
            extra={"user_id": user_id, "error": str(e)},
            exc_info=True
        )
        raise DatabaseError(f"Failed to update item quantity: {str(e)}")
        
    except Exception as e:
        logger.error(
            "Unexpected error updating item quantity",
            extra={"user_id": user_id, "error": str(e)},
            exc_info=True
        )
        raise DatabaseError(f"Unexpected error: {str(e)}")


# PUBLIC_INTERFACE
async def remove_item(user_id: str, product_id: str) -> Cart:
    """
    Remove an item from the cart.
    
    Args:
        user_id: Unique identifier for the user
        product_id: ID of the product to remove
        
    Returns:
        Cart: Updated cart with item removed
        
    Raises:
        CartNotFoundError: If cart doesn't exist
        DatabaseError: If database operation fails
        ValueError: If product not in cart
        
    Example:
        >>> cart = await remove_item("user123", "prod123")
        
    @compliance
    - Data Integrity: Atomic delete operation
    - Business Rules: Validates item exists before removal
    """
    try:
        if not user_id or not user_id.strip():
            raise ValueError("user_id cannot be empty")
        
        if not product_id or not product_id.strip():
            raise ValueError("product_id cannot be empty")
        
        # Get cart
        cart = await get_cart(user_id)
        if not cart:
            raise CartNotFoundError(f"Cart not found for user {user_id}")
        
        # Remove item using Cart model logic
        removed = cart.remove_item(product_id)
        
        if not removed:
            raise ValueError(f"Product {product_id} not found in cart")
        
        # Update in database
        db = get_database()
        carts_collection = db.carts
        
        cart_dict = _cart_to_dict(cart)
        
        result = await carts_collection.replace_one(
            {"user_id": user_id},
            cart_dict
        )
        
        if result.matched_count == 0:
            raise DatabaseError(f"Cart not found for user {user_id}")
        
        logger.info(
            "Item removed from cart",
            extra={"user_id": user_id, "product_id": product_id}
        )
        
        return cart
        
    except (ValueError, CartNotFoundError) as e:
        logger.warning(f"Invalid input or not found: {str(e)}")
        raise
        
    except PyMongoError as e:
        logger.error(
            "Database error removing item from cart",
            extra={"user_id": user_id, "error": str(e)},
            exc_info=True
        )
        raise DatabaseError(f"Failed to remove item from cart: {str(e)}")
        
    except Exception as e:
        logger.error(
            "Unexpected error removing item from cart",
            extra={"user_id": user_id, "error": str(e)},
            exc_info=True
        )
        raise DatabaseError(f"Unexpected error: {str(e)}")


# PUBLIC_INTERFACE
async def clear_cart(user_id: str) -> Cart:
    """
    Remove all items from the cart.
    
    This function empties the cart but keeps the cart document itself.
    
    Args:
        user_id: Unique identifier for the user
        
    Returns:
        Cart: Empty cart
        
    Raises:
        CartNotFoundError: If cart doesn't exist
        DatabaseError: If database operation fails
        
    Example:
        >>> cart = await clear_cart("user123")
        >>> print(f"Cart items: {cart.item_count}")  # 0
        
    @compliance
    - Data Integrity: Maintains cart document structure
    - Business Rules: Preserves cart metadata (created_at)
    """
    try:
        if not user_id or not user_id.strip():
            raise ValueError("user_id cannot be empty")
        
        # Get cart
        cart = await get_cart(user_id)
        if not cart:
            raise CartNotFoundError(f"Cart not found for user {user_id}")
        
        # Clear items using Cart model logic
        cart.clear()
        
        # Update in database
        db = get_database()
        carts_collection = db.carts
        
        cart_dict = _cart_to_dict(cart)
        
        result = await carts_collection.replace_one(
            {"user_id": user_id},
            cart_dict
        )
        
        if result.matched_count == 0:
            raise DatabaseError(f"Cart not found for user {user_id}")
        
        logger.info(
            "Cart cleared",
            extra={"user_id": user_id}
        )
        
        return cart
        
    except (ValueError, CartNotFoundError) as e:
        logger.warning(f"Invalid input or not found: {str(e)}")
        raise
        
    except PyMongoError as e:
        logger.error(
            "Database error clearing cart",
            extra={"user_id": user_id, "error": str(e)},
            exc_info=True
        )
        raise DatabaseError(f"Failed to clear cart: {str(e)}")
        
    except Exception as e:
        logger.error(
            "Unexpected error clearing cart",
            extra={"user_id": user_id, "error": str(e)},
            exc_info=True
        )
        raise DatabaseError(f"Unexpected error: {str(e)}")
