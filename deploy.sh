#!/bin/bash

# Deployment script for Fresenius AI Assistant to AWS Lambda
# Prerequisites:
# - AWS CLI configured
# - AWS SAM CLI installed (pip install aws-sam-cli)
# - Docker installed (for building dependencies)

set -e

echo "🚀 Deploying Fresenius AI Assistant to AWS Lambda..."

# Check if AWS SAM CLI is installed
if ! command -v sam &> /dev/null; then
    echo "❌ AWS SAM CLI not found. Install it with: pip install aws-sam-cli"
    exit 1
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Build the application
echo "📦 Building Lambda package..."
sam build --use-container

# Deploy the application
echo "🌍 Deploying to AWS..."
sam deploy --guided

echo "✅ Deployment complete!"
echo ""
echo "📝 Next steps:"
echo "1. Update your Google OAuth redirect URI with the new API Gateway URL"
echo "2. Test the API endpoints"
echo "3. Update your frontend to point to the new Lambda endpoints"