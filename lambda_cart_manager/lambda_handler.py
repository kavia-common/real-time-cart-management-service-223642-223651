"""
AWS Lambda handler for FastAPI cart management service.

This module provides the Lambda handler that wraps the FastAPI application
using Mangum, enabling deployment to AWS Lambda with API Gateway integration.

The handler manages the application lifecycle including database connections
and graceful shutdown procedures.

PUBLIC_INTERFACE
"""
import logging
from mangum import Mangum
from src.api.main import app
from src.database.mongodb import connect_db, close_db

# Configure logging for Lambda environment
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Global flag to track initialization
_is_initialized = False


async def initialize_app():
    """
    Initialize application resources on cold start.
    
    This function is called once per Lambda container lifecycle to establish
    database connections and perform other one-time initialization tasks.
    
    @compliance
    - Performance: Reuses connections across warm Lambda invocations
    - Reliability: Ensures database is connected before handling requests
    - Resource Management: Connection pooling for efficiency
    """
    global _is_initialized
    
    if not _is_initialized:
        try:
            logger.info("Initializing Lambda handler - connecting to MongoDB")
            await connect_db()
            logger.info("MongoDB connection established successfully")
            _is_initialized = True
        except Exception as e:
            logger.error(
                "Failed to initialize application",
                extra={"error": str(e)},
                exc_info=True
            )
            raise


async def cleanup_app():
    """
    Cleanup application resources on shutdown.
    
    This function is called during Lambda container shutdown to gracefully
    close database connections and clean up resources.
    
    @compliance
    - Resource Management: Prevents connection leaks
    - Reliability: Graceful shutdown
    """
    global _is_initialized
    
    if _is_initialized:
        try:
            logger.info("Cleaning up Lambda handler - closing MongoDB connection")
            await close_db()
            logger.info("MongoDB connection closed successfully")
            _is_initialized = False
        except Exception as e:
            logger.error(
                "Error during cleanup",
                extra={"error": str(e)},
                exc_info=True
            )


# Add lifecycle event handlers to FastAPI app
@app.on_event("startup")
async def startup_event():
    """
    FastAPI startup event handler.
    
    Initializes database connections when the application starts.
    This is called automatically by FastAPI during startup.
    
    @compliance
    - Reliability: Fail-fast on startup if critical resources unavailable
    """
    await initialize_app()


@app.on_event("shutdown")
async def shutdown_event():
    """
    FastAPI shutdown event handler.
    
    Closes database connections when the application shuts down.
    This is called automatically by FastAPI during shutdown.
    
    @compliance
    - Resource Management: Clean resource release
    """
    await cleanup_app()


# PUBLIC_INTERFACE
# Create Mangum handler for AWS Lambda
handler = Mangum(
    app,
    lifespan="auto",  # Automatically handle FastAPI lifespan events
    api_gateway_base_path=None,  # No base path stripping (use API Gateway stage if needed)
)

"""
Lambda Handler Configuration:

This handler is configured to work with AWS API Gateway (REST API or HTTP API).

Environment Variables Required:
- MONGODB_URI: MongoDB Atlas connection string
- MONGODB_DATABASE: Database name
- JWT_SECRET_KEY: Secret key for JWT token signing (min 32 characters)
- JWT_ALGORITHM: Algorithm for JWT (default: HS256)
- JWT_EXPIRATION_MINUTES: Token expiration time (default: 30)
- ENVIRONMENT: Application environment (development/staging/production)
- ALLOWED_ORIGINS: CORS allowed origins (comma-separated)

API Gateway Integration:
- This handler works with both REST API and HTTP API v2.0
- Supports proxy integration (ANY /{proxy+})
- Handles binary media types automatically
- Preserves headers, query parameters, and request body

Performance Considerations:
- Lambda container reuse: Database connections are maintained across warm invocations
- Cold start optimization: Minimal initialization overhead
- Connection pooling: Motor async client handles connection pooling efficiently

Deployment:
1. Package dependencies: pip install -r requirements.txt -t .
2. Create deployment package: zip -r deployment.zip .
3. Upload to Lambda or deploy via SAM/Serverless/CDK
4. Configure API Gateway to proxy all requests to Lambda
5. Set environment variables in Lambda configuration
6. Allocate sufficient memory (recommended: 512MB-1024MB)
7. Set timeout appropriately (recommended: 30 seconds)

Example SAM Template Configuration:
```yaml
Resources:
  CartFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: lambda_handler.handler
      Runtime: python3.11
      CodeUri: lambda_cart_manager/
      MemorySize: 512
      Timeout: 30
      Environment:
        Variables:
          MONGODB_URI: !Ref MongoDBUri
          MONGODB_DATABASE: !Ref MongoDBDatabase
          JWT_SECRET_KEY: !Ref JWTSecretKey
      Events:
        ApiGateway:
          Type: Api
          Properties:
            Path: /{proxy+}
            Method: ANY
```

Example API Gateway Proxy Configuration:
- Resource: /{proxy+}
- Method: ANY
- Integration Type: Lambda Proxy
- Lambda Function: <function-name>
- Use Lambda Proxy Integration: Yes

Testing Locally:
You can test the handler locally using AWS SAM CLI:
```bash
sam local start-api
curl http://localhost:3000/
curl -H "Authorization: Bearer <token>" http://localhost:3000/cart
```

Monitoring:
- CloudWatch Logs: Automatically captures application logs
- CloudWatch Metrics: Lambda execution metrics available
- X-Ray: Enable for distributed tracing (optional)
- Custom Metrics: Use CloudWatch Embedded Metric Format for business metrics

Security Best Practices:
- Store secrets in AWS Secrets Manager or Parameter Store
- Use IAM roles for MongoDB Atlas authentication if possible
- Enable VPC integration if MongoDB is in VPC
- Use API Gateway authorization (Cognito, Lambda authorizer, or IAM)
- Enable API Gateway throttling and rate limiting
- Use AWS WAF for additional protection

@compliance
- Deployment: AWS Lambda-ready handler with Mangum integration
- Performance: Connection reuse across warm invocations
- Reliability: Proper lifecycle management
- Security: Environment variable configuration for secrets
- Monitoring: CloudWatch integration via Lambda runtime
"""
