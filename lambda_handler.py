"""
AWS Lambda handler for Fresenius AI Assistant
This file wraps the FastAPI application for deployment on AWS Lambda
"""
from mangum import Mangum
from app.main import app

# Mangum handler - converts API Gateway events to ASGI format
handler = Mangum(app, lifespan="off")

# For Lambda function URL or API Gateway HTTP API
def lambda_handler(event, context):
    """
    AWS Lambda entry point

    Args:
        event: API Gateway event or Lambda Function URL event
        context: Lambda context object

    Returns:
        API Gateway response
    """
    return handler(event, context)