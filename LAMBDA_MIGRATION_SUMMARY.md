# Lambda Migration Summary

## What Was Done

Your Fresenius AI Assistant has been successfully configured for AWS Lambda deployment. Here's what was created:

### 1. Lambda Handlers
- **`lambda_handler.py`** - Main API handler using Mangum (FastAPI → Lambda adapter)
- **`websocket_handler.py`** - WebSocket handler for real-time chat via API Gateway WebSocket API

### 2. Deployment Configuration

#### AWS SAM (Recommended)
- **`template.yaml`** - CloudFormation template with all AWS resources
- **`samconfig.toml`** - Configuration for SAM CLI deployment
- **`deploy.sh`** - Automated deployment script

#### Serverless Framework (Alternative)
- **`serverless.yml`** - Serverless Framework configuration

### 3. Documentation
- **`LAMBDA_DEPLOYMENT.md`** - Comprehensive deployment guide
- **`QUICK_START_LAMBDA.md`** - Quick start guide
- **`.env.lambda`** - Environment variables template

### 4. Example Code
- **`examples/invoke_lambda.py`** - Python SDK examples for invoking Lambda
- **`examples/http_client.py`** - HTTP client for API Gateway

### 5. Updated Files
- **`requirements.txt`** - Added `mangum` for Lambda support
- **`app/main.py`** - Added Lambda environment detection and database initialization

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     API Gateway                          │
│                                                           │
│  ┌────────────────────┐      ┌────────────────────┐    │
│  │   HTTP API         │      │   WebSocket API    │    │
│  │   (REST/HTTP)      │      │   (Real-time chat) │    │
│  └────────┬───────────┘      └────────┬───────────┘    │
└───────────┼──────────────────────────┼─────────────────┘
            │                           │
            ▼                           ▼
┌───────────────────────┐   ┌───────────────────────────┐
│  Lambda Function      │   │  Lambda Function          │
│  (Main API)           │   │  (WebSocket Handler)      │
│                       │   │                           │
│  - FastAPI routes     │   │  - $connect/$disconnect   │
│  - OAuth flow         │   │  - Message handling       │
│  - API endpoints      │   │  - Agent invocation       │
└───────┬───────────────┘   └───────┬───────────────────┘
        │                           │
        │                           │
        ▼                           ▼
┌─────────────────────────────────────────────────────────┐
│                   AWS Bedrock                            │
│              (Claude Sonnet 4 Model)                     │
└─────────────────────────────────────────────────────────┘
```

## Key Features

### ✅ Fully Serverless
- No servers to manage
- Automatic scaling
- Pay only for what you use

### ✅ API Gateway Integration
- HTTP API for REST endpoints
- WebSocket API for real-time chat
- Built-in authentication support

### ✅ AWS Bedrock Integration
- Uses AWS Bedrock Claude Sonnet 4
- No need to manage API keys
- Native AWS IAM permissions

### ✅ Multiple Deployment Options
1. AWS SAM (native CloudFormation)
2. Serverless Framework (multi-cloud)
3. Manual deployment (ZIP upload)

## How to Deploy

### Quick Deploy (3 commands)
```bash
# 1. Edit samconfig.toml with your values
nano samconfig.toml

# 2. Deploy
./deploy.sh

# 3. Update Google OAuth redirect URI
# Use the API Gateway URL from deployment output
```

### Detailed Steps
See [LAMBDA_DEPLOYMENT.md](./LAMBDA_DEPLOYMENT.md) for comprehensive guide.

## How to Invoke from Other Services

### From Another Lambda
```python
import boto3
import json

lambda_client = boto3.client('lambda')
response = lambda_client.invoke(
    FunctionName='fresenius-ai-assistant',
    Payload=json.dumps({
        'httpMethod': 'GET',
        'path': '/api/config'
    })
)
```

### From Step Functions
```json
{
  "Type": "Task",
  "Resource": "arn:aws:states:::lambda:invoke",
  "Parameters": {
    "FunctionName": "fresenius-ai-assistant",
    "Payload": { "httpMethod": "GET", "path": "/api/config" }
  }
}
```

### Via HTTP (any language)
```bash
curl https://YOUR_API_GATEWAY_URL/api/config \
  -H "Cookie: access_token=YOUR_JWT_TOKEN"
```

### From EventBridge
Configure EventBridge rule to trigger Lambda on schedule or custom events.

### From S3 Events
Configure S3 bucket to trigger Lambda when files are uploaded.

See [examples/invoke_lambda.py](./examples/invoke_lambda.py) for more examples.

## Cost Estimation

### Lambda
- **Free tier**: 1M requests/month, 400,000 GB-seconds compute
- **After free tier**: $0.20 per 1M requests + $0.0000166667 per GB-second

### API Gateway
- **HTTP API**: $1.00 per million requests
- **WebSocket API**: $1.00 per million messages

### AWS Bedrock
- **Claude Sonnet 4**: Pay per token (input/output)
- Varies by region and model

### Example Monthly Cost (after free tier)
- 10,000 requests/month: ~$2-5
- 100,000 requests/month: ~$20-50
- Depends heavily on Bedrock token usage

## Production Considerations

### Must Do
1. ✅ Migrate from SQLite to RDS/DynamoDB
2. ✅ Use AWS Secrets Manager for secrets
3. ✅ Set up CloudWatch alarms
4. ✅ Configure VPC if needed
5. ✅ Enable X-Ray tracing
6. ✅ Set up WAF for API Gateway

### Should Do
1. Enable CloudFront CDN
2. Implement API rate limiting
3. Set up CI/CD pipeline
4. Add comprehensive logging
5. Implement health checks

### Database Migration
SQLite won't persist across Lambda invocations. For production:

**Option 1: Amazon RDS (PostgreSQL/MySQL)**
```python
# Update app/database.py
engine = create_engine(
    f"postgresql://{user}:{password}@{host}:{port}/{database}"
)
```

**Option 2: Amazon DynamoDB**
- Better for serverless (no cold start issues)
- More cost-effective at scale
- Requires code refactoring

## Monitoring & Debugging

### View Logs
```bash
# SAM
sam logs -n FreseiniusFunction --tail

# AWS CLI
aws logs tail /aws/lambda/fresenius-ai-assistant --follow
```

### Metrics
- Monitor in CloudWatch dashboard
- Set up alarms for errors, latency, throttles

### Local Testing
```bash
# Test locally with SAM
sam local start-api
sam local invoke FreseiniusFunction
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Cold starts slow | Increase memory, use Provisioned Concurrency |
| Database not found | Package Excel file, or use RDS/DynamoDB |
| Timeout errors | Break into smaller tasks, use Step Functions |
| Memory errors | Increase Lambda memory allocation |
| WebSocket disconnects | Use DynamoDB for connection state |

## Next Steps

1. **Test deployment**: Deploy to staging environment
2. **Update frontend**: Point to new API Gateway URLs
3. **Monitor performance**: Set up CloudWatch dashboards
4. **Optimize costs**: Review Lambda memory/timeout settings
5. **Migrate database**: Move from SQLite to RDS/DynamoDB
6. **CI/CD**: Set up GitHub Actions or CodePipeline

## Files Created

```
fresenius-app/
├── lambda_handler.py              # Main Lambda handler
├── websocket_handler.py           # WebSocket Lambda handler
├── template.yaml                  # AWS SAM template
├── samconfig.toml                 # SAM configuration
├── serverless.yml                 # Serverless Framework config
├── deploy.sh                      # Deployment script
├── .dockerignore                  # Docker ignore file
├── .env.lambda                    # Environment template
├── LAMBDA_DEPLOYMENT.md           # Full deployment guide
├── QUICK_START_LAMBDA.md          # Quick start guide
├── LAMBDA_MIGRATION_SUMMARY.md    # This file
└── examples/
    ├── invoke_lambda.py           # Lambda invocation examples
    └── http_client.py             # HTTP client example
```

## Support Resources

- **AWS SAM Documentation**: https://docs.aws.amazon.com/serverless-application-model/
- **Serverless Framework**: https://www.serverless.com/framework/docs
- **AWS Lambda Best Practices**: https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html
- **FastAPI + Lambda**: https://github.com/jordaneremieff/mangum

---

**Your application is now ready for Lambda deployment!** 🚀

Run `./deploy.sh` to get started.