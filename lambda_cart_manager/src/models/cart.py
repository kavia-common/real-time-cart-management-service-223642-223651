"""
Cart management Pydantic models.

This module defines the data models for shopping cart operations including
CartItem, Cart, and response schemas. All models include comprehensive validation
to ensure data integrity and consistency.

PUBLIC_INTERFACE
"""
from datetime import datetime
from typing import List
from pydantic import BaseModel, Field, field_validator, computed_field


class CartItem(BaseModel):
    """
    Represents a single item in a shopping cart.
    
    Attributes:
        product_id: Unique identifier for the product
        name: Display name of the product
        price: Unit price of the product (must be non-negative)
        quantity: Number of items (must be at least 1)
        added_at: Timestamp when item was added to cart
    
    @compliance
    - Validation: Price must be >= 0, quantity must be >= 1
    - Data Integrity: Auto-timestamps for audit trail
    """
    
    product_id: str = Field(
        ...,
        description="Unique identifier for the product",
        min_length=1
    )
    
    name: str = Field(
        ...,
        description="Display name of the product",
        min_length=1,
        max_length=255
    )
    
    price: float = Field(
        ...,
        description="Unit price of the product in currency units",
        ge=0.0
    )
    
    quantity: int = Field(
        ...,
        description="Number of items in cart",
        ge=1
    )
    
    added_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when item was added to cart (UTC)"
    )
    
    @field_validator("price")
    @classmethod
    def validate_price(cls, v: float) -> float:
        """
        Validate price is non-negative and reasonable.
        
        @compliance
        - Business Rules: Price must be >= 0
        - Data Quality: Round to 2 decimal places for currency
        """
        if v < 0:
            raise ValueError("Price cannot be negative")
        # Round to 2 decimal places for currency precision
        return round(v, 2)
    
    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v: int) -> int:
        """
        Validate quantity is at least 1 and reasonable.
        
        @compliance
        - Business Rules: Minimum quantity is 1
        - Data Quality: Prevent unreasonable quantities
        """
        if v < 1:
            raise ValueError("Quantity must be at least 1")
        if v > 10000:
            raise ValueError("Quantity exceeds maximum allowed (10000)")
        return v
    
    @field_validator("product_id", "name")
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """
        Validate string fields are not empty or whitespace only.
        
        @compliance
        - Data Quality: Prevent empty/whitespace-only values
        """
        if not v or not v.strip():
            raise ValueError("Field cannot be empty or whitespace only")
        return v.strip()
    
    @computed_field
    @property
    def subtotal(self) -> float:
        """
        Calculate subtotal for this cart item.
        
        Returns:
            float: price * quantity, rounded to 2 decimal places
            
        @compliance
        - Business Rules: Subtotal calculation for line items
        """
        return round(self.price * self.quantity, 2)
    
    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "product_id": "prod_abc123",
                "name": "Premium Wireless Headphones",
                "price": 99.99,
                "quantity": 2,
                "added_at": "2025-01-12T10:30:00.000Z"
            }
        }


class Cart(BaseModel):
    """
    Represents a user's shopping cart.
    
    Attributes:
        user_id: Unique identifier for the user who owns this cart
        items: List of items in the cart
        created_at: Timestamp when cart was created
        updated_at: Timestamp when cart was last modified
        total_amount: Computed total value of all items in cart
    
    @compliance
    - Data Integrity: Auto-timestamps for audit trail
    - Business Rules: Total amount automatically calculated from items
    - Performance: Efficient recalculation of totals
    """
    
    user_id: str = Field(
        ...,
        description="Unique identifier for the user who owns this cart",
        min_length=1
    )
    
    items: List[CartItem] = Field(
        default_factory=list,
        description="List of items currently in the cart"
    )
    
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when cart was created (UTC)"
    )
    
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when cart was last updated (UTC)"
    )
    
    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, v: str) -> str:
        """
        Validate user_id is not empty.
        
        @compliance
        - Data Quality: Ensure valid user identifier
        """
        if not v or not v.strip():
            raise ValueError("User ID cannot be empty")
        return v.strip()
    
    @field_validator("items")
    @classmethod
    def validate_items(cls, v: List[CartItem]) -> List[CartItem]:
        """
        Validate cart items list.
        
        @compliance
        - Business Rules: Check for duplicate products
        - Data Quality: Ensure cart size is reasonable
        """
        if len(v) > 1000:
            raise ValueError("Cart cannot contain more than 1000 items")
        
        # Check for duplicate product_ids
        product_ids = [item.product_id for item in v]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("Cart contains duplicate products. Use quantity for multiple items.")
        
        return v
    
    @computed_field
    @property
    def total_amount(self) -> float:
        """
        Calculate total amount of all items in cart.
        
        Returns:
            float: Sum of all item subtotals, rounded to 2 decimal places
            
        @compliance
        - Business Rules: Accurate cart total calculation
        - Performance: Computed on-demand from current items
        """
        if not self.items:
            return 0.0
        
        total = sum(item.subtotal for item in self.items)
        return round(total, 2)
    
    @computed_field
    @property
    def item_count(self) -> int:
        """
        Get total number of items in cart (sum of all quantities).
        
        Returns:
            int: Total quantity across all cart items
            
        @compliance
        - Business Rules: Total item count for display
        """
        return sum(item.quantity for item in self.items)
    
    # PUBLIC_INTERFACE
    def recalculate_totals(self) -> float:
        """
        Recalculate and return the total amount.
        
        This helper method explicitly recalculates totals and updates
        the updated_at timestamp. Useful after modifying items.
        
        Returns:
            float: Current total amount of cart
            
        Example:
            >>> cart = Cart(user_id="user123")
            >>> cart.items.append(CartItem(product_id="p1", name="Item", price=10.0, quantity=2))
            >>> total = cart.recalculate_totals()
            >>> print(total)
            20.0
            
        @compliance
        - Data Integrity: Updates timestamp on recalculation
        - Business Rules: Ensures total is current
        """
        self.updated_at = datetime.utcnow()
        return self.total_amount
    
    # PUBLIC_INTERFACE
    def add_item(self, item: CartItem) -> None:
        """
        Add an item to the cart or update quantity if product exists.
        
        Args:
            item: CartItem to add to cart
            
        Raises:
            ValueError: If adding item would exceed cart limits
            
        @compliance
        - Business Rules: Merge quantities for duplicate products
        - Data Integrity: Auto-update timestamps
        """
        # Check if product already exists
        existing_item = None
        for cart_item in self.items:
            if cart_item.product_id == item.product_id:
                existing_item = cart_item
                break
        
        if existing_item:
            # Update quantity of existing item
            new_quantity = existing_item.quantity + item.quantity
            if new_quantity > 10000:
                raise ValueError("Total quantity for product exceeds maximum (10000)")
            existing_item.quantity = new_quantity
        else:
            # Add as new item
            if len(self.items) >= 1000:
                raise ValueError("Cart cannot contain more than 1000 unique items")
            self.items.append(item)
        
        self.updated_at = datetime.utcnow()
    
    # PUBLIC_INTERFACE
    def remove_item(self, product_id: str) -> bool:
        """
        Remove an item from the cart by product_id.
        
        Args:
            product_id: ID of product to remove
            
        Returns:
            bool: True if item was found and removed, False otherwise
            
        @compliance
        - Data Integrity: Auto-update timestamps on modification
        """
        initial_length = len(self.items)
        self.items = [item for item in self.items if item.product_id != product_id]
        
        if len(self.items) < initial_length:
            self.updated_at = datetime.utcnow()
            return True
        return False
    
    # PUBLIC_INTERFACE
    def update_item_quantity(self, product_id: str, quantity: int) -> bool:
        """
        Update quantity of a specific item in cart.
        
        Args:
            product_id: ID of product to update
            quantity: New quantity (must be >= 1)
            
        Returns:
            bool: True if item was found and updated, False otherwise
            
        Raises:
            ValueError: If quantity is invalid
            
        @compliance
        - Business Rules: Quantity validation
        - Data Integrity: Auto-update timestamps
        """
        if quantity < 1:
            raise ValueError("Quantity must be at least 1")
        if quantity > 10000:
            raise ValueError("Quantity exceeds maximum allowed (10000)")
        
        for item in self.items:
            if item.product_id == product_id:
                item.quantity = quantity
                self.updated_at = datetime.utcnow()
                return True
        
        return False
    
    # PUBLIC_INTERFACE
    def clear(self) -> None:
        """
        Remove all items from the cart.
        
        @compliance
        - Data Integrity: Auto-update timestamps
        """
        self.items.clear()
        self.updated_at = datetime.utcnow()
    
    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "user_id": "user_abc123",
                "items": [
                    {
                        "product_id": "prod_1",
                        "name": "Laptop",
                        "price": 999.99,
                        "quantity": 1,
                        "added_at": "2025-01-12T10:30:00.000Z"
                    },
                    {
                        "product_id": "prod_2",
                        "name": "Mouse",
                        "price": 29.99,
                        "quantity": 2,
                        "added_at": "2025-01-12T10:31:00.000Z"
                    }
                ],
                "created_at": "2025-01-12T10:30:00.000Z",
                "updated_at": "2025-01-12T10:31:00.000Z"
            }
        }


class CartResponse(BaseModel):
    """
    Response schema for cart operations.
    
    This schema is used for API responses and includes all cart data
    plus computed fields for display.
    
    @compliance
    - API Design: Consistent response structure
    - Data Presentation: Includes computed fields for client convenience
    """
    
    user_id: str = Field(
        ...,
        description="Unique identifier for the user"
    )
    
    items: List[CartItem] = Field(
        ...,
        description="List of items in the cart"
    )
    
    total_amount: float = Field(
        ...,
        description="Total value of all items in cart"
    )
    
    item_count: int = Field(
        ...,
        description="Total number of items (sum of quantities)"
    )
    
    created_at: datetime = Field(
        ...,
        description="When cart was created"
    )
    
    updated_at: datetime = Field(
        ...,
        description="When cart was last updated"
    )
    
    # PUBLIC_INTERFACE
    @classmethod
    def from_cart(cls, cart: Cart) -> "CartResponse":
        """
        Create CartResponse from Cart model.
        
        Args:
            cart: Cart instance to convert
            
        Returns:
            CartResponse: Response schema with all cart data
            
        Example:
            >>> cart = Cart(user_id="user123")
            >>> response = CartResponse.from_cart(cart)
            
        @compliance
        - API Design: Conversion utility for consistent responses
        """
        return cls(
            user_id=cart.user_id,
            items=cart.items,
            total_amount=cart.total_amount,
            item_count=cart.item_count,
            created_at=cart.created_at,
            updated_at=cart.updated_at
        )
    
    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "user_id": "user_abc123",
                "items": [
                    {
                        "product_id": "prod_1",
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


class CartItemRequest(BaseModel):
    """
    Request schema for adding/updating cart items.
    
    This schema is used for API requests when adding or updating items.
    
    @compliance
    - API Design: Input validation at request level
    """
    
    product_id: str = Field(
        ...,
        description="Unique identifier for the product",
        min_length=1
    )
    
    name: str = Field(
        ...,
        description="Display name of the product",
        min_length=1,
        max_length=255
    )
    
    price: float = Field(
        ...,
        description="Unit price of the product",
        ge=0.0
    )
    
    quantity: int = Field(
        default=1,
        description="Number of items to add",
        ge=1,
        le=10000
    )
    
    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "product_id": "prod_abc123",
                "name": "Wireless Keyboard",
                "price": 59.99,
                "quantity": 1
            }
        }


class UpdateQuantityRequest(BaseModel):
    """
    Request schema for updating item quantity.
    
    @compliance
    - API Design: Specific schema for quantity updates
    """
    
    quantity: int = Field(
        ...,
        description="New quantity for the item",
        ge=1,
        le=10000
    )
    
    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "quantity": 3
            }
        }
