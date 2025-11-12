"""
Application configuration using Pydantic BaseSettings.

This module provides centralized configuration management using environment variables.
All sensitive configuration (database credentials, JWT secrets) must be provided via
environment variables and never hardcoded.

PUBLIC_INTERFACE
"""
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    This class uses Pydantic BaseSettings to automatically load and validate
    configuration from environment variables or .env file.
    
    @compliance
    - Security: No hardcoded secrets, all sensitive data from environment
    - Validation: Pydantic ensures type safety and required fields
    """
    
    # MongoDB Configuration
    # User must provide MONGODB_URI in .env file
    mongodb_uri: str = Field(
        ...,
        description="MongoDB connection URI (e.g., mongodb+srv://user:pass@cluster.mongodb.net/)",
        min_length=1
    )
    
    mongodb_database: str = Field(
        ...,
        description="MongoDB database name",
        min_length=1
    )
    
    # JWT Configuration
    # User must provide JWT_SECRET_KEY in .env file - this should be a strong random string
    jwt_secret_key: str = Field(
        ...,
        description="Secret key for JWT token signing. Must be kept secure.",
        min_length=32
    )
    
    jwt_algorithm: str = Field(
        default="HS256",
        description="Algorithm used for JWT token signing"
    )
    
    jwt_expiration_minutes: int = Field(
        default=30,
        description="JWT token expiration time in minutes",
        gt=0
    )
    
    # Application Configuration
    environment: str = Field(
        default="development",
        description="Application environment (development, staging, production)"
    )
    
    # CORS and API Configuration (from existing .env)
    allowed_origins: str = Field(
        default="*",
        description="Comma-separated list of allowed CORS origins"
    )
    
    @validator("jwt_secret_key")
    def validate_jwt_secret(cls, v):
        """
        Validate JWT secret key strength.
        
        @compliance
        - Security: Ensures JWT secret is strong enough for production use
        """
        if len(v) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters long for security")
        return v
    
    @validator("jwt_algorithm")
    def validate_jwt_algorithm(cls, v):
        """
        Validate JWT algorithm is supported.
        
        @compliance
        - Security: Only allow secure JWT algorithms
        """
        allowed_algorithms = ["HS256", "HS384", "HS512", "RS256", "RS384", "RS512"]
        if v not in allowed_algorithms:
            raise ValueError(f"JWT_ALGORITHM must be one of {allowed_algorithms}")
        return v
    
    @validator("mongodb_uri")
    def validate_mongodb_uri(cls, v):
        """
        Validate MongoDB URI format.
        
        @compliance
        - Reliability: Ensure proper connection string format
        """
        if not (v.startswith("mongodb://") or v.startswith("mongodb+srv://")):
            raise ValueError("MONGODB_URI must start with mongodb:// or mongodb+srv://")
        return v
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        
        # Field name mapping for environment variables
        fields = {
            "mongodb_uri": {"env": "MONGODB_URI"},
            "mongodb_database": {"env": "MONGODB_DATABASE"},
            "jwt_secret_key": {"env": "JWT_SECRET_KEY"},
            "jwt_algorithm": {"env": "JWT_ALGORITHM"},
            "jwt_expiration_minutes": {"env": "JWT_EXPIRATION_MINUTES"},
            "environment": {"env": "ENVIRONMENT"},
            "allowed_origins": {"env": "ALLOWED_ORIGINS"}
        }


# PUBLIC_INTERFACE
@lru_cache()
def get_settings() -> Settings:
    """
    Get application settings singleton.
    
    This function uses LRU cache to ensure settings are loaded only once
    and reused throughout the application lifecycle.
    
    Returns:
        Settings: Application configuration settings
        
    Raises:
        ValidationError: If required environment variables are missing or invalid
        
    Example:
        >>> from src.config.settings import get_settings
        >>> settings = get_settings()
        >>> print(settings.mongodb_database)
        
    @compliance
    - Performance: Singleton pattern prevents repeated environment variable parsing
    - Reliability: Validates configuration at startup, fail-fast principle
    
    Note:
        Required environment variables must be set:
        - MONGODB_URI: MongoDB Atlas connection string
        - MONGODB_DATABASE: Database name
        - JWT_SECRET_KEY: Secret key for JWT signing (min 32 characters)
    """
    return Settings()
