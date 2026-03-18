# AWS Lambda Deployment Checklist

Use this checklist to ensure a smooth deployment to AWS Lambda.

## Pre-Deployment

### Prerequisites
- [ ] AWS account created
- [ ] AWS CLI installed and configured (`aws configure`)
- [ ] AWS SAM CLI installed (`pip install aws-sam-cli`)
- [ ] Docker installed and running
- [ ] Python 3.11+ installed
- [ ] Git repository set up

### Google OAuth Configuration
- [ ] Google Cloud project created
- [ ] OAuth 2.0 credentials created
- [ ] Client ID and Client Secret saved
- [ ] Authorized JavaScript origins configured
- [ ] Redirect URIs ready to update after deployment

### Environment Variables Ready
- [ ] `GOOGLE_CLIENT_ID` - From Google Cloud Console
- [ ] `GOOGLE_CLIENT_SECRET` - From Google Cloud Console
- [ ] `SECRET_KEY` - Generated (use: `python3 -c "import secrets; print(secrets.token_hex(32))"`)
- [ ] `WHITELISTED_EMAILS` - Comma-separated list of allowed emails
- [ ] `BEDROCK_MODEL_ID` - Model ID (default provided)
- [ ] `TAVILY_API_KEY` - Optional, for enhanced search

### AWS Permissions
- [ ] IAM user/role has Lambda creation permissions
- [ ] IAM user/role has API Gateway creation permissions
- [ ] IAM user/role has CloudFormation permissions
- [ ] IAM user/role has S3 permissions (for SAM artifacts)
- [ ] Bedrock access enabled in AWS account
- [ ] Bedrock model access granted (Claude Sonnet 4)

## Configuration

### Update samconfig.toml
- [ ] Open `samconfig.toml`
- [ ] Replace `YOUR_GOOGLE_CLIENT_ID` with actual value
- [ ] Replace `YOUR_GOOGLE_CLIENT_SECRET` with actual value
- [ ] Replace `YOUR_SECRET_KEY` with generated secret
- [ ] Replace `email1@example.com,email2@example.com` with actual emails
- [ ] Set desired AWS region (default: `us-east-1`)
- [ ] Review Bedrock model ID

### Review template.yaml
- [ ] Check Lambda timeout (default: 900 seconds / 15 minutes)
- [ ] Check Lambda memory (default: 2048 MB)
- [ ] Review IAM permissions for Bedrock access
- [ ] Verify CORS configuration if needed

## Deployment

### Build
- [ ] Run `sam build --use-container`
- [ ] Build completes without errors
- [ ] Dependencies packaged successfully

### Deploy
- [ ] Run `sam deploy --guided` (first time)
- [ ] Review all prompts and settings
- [ ] Confirm deployment changes
- [ ] Wait for CloudFormation stack creation
- [ ] Note the API Gateway URLs from outputs

### Quick Deploy Alternative
- [ ] Make deploy script executable: `chmod +x deploy.sh`
- [ ] Run `./deploy.sh`
- [ ] Follow prompts

## Post-Deployment

### Update Google OAuth
- [ ] Copy API Gateway URL from deployment output
- [ ] Go to Google Cloud Console
- [ ] Navigate to: APIs & Services → Credentials
- [ ] Edit OAuth 2.0 Client ID
- [ ] Add redirect URI: `https://YOUR_API_ID.execute-api.REGION.amazonaws.com/auth/callback`
- [ ] Save changes

### Test HTTP Endpoints
- [ ] Test root endpoint: `curl https://YOUR_API_URL/`
- [ ] Test config endpoint: `curl https://YOUR_API_URL/api/config`
- [ ] Verify 401 on protected endpoints (expected without auth)

### Test OAuth Flow
- [ ] Open API URL in browser
- [ ] Click "Sign in with Google"
- [ ] Verify redirect to Google
- [ ] Complete Google authentication
- [ ] Verify redirect back to app
- [ ] Verify successful login (if email whitelisted)
- [ ] Verify access denied (if email not whitelisted)

### Test Chat Functionality
- [ ] Login successfully
- [ ] Select role (Patient/Doctor/Nurse)
- [ ] Paste AWS temporary credentials
- [ ] Click "Start Chat"
- [ ] Send test message
- [ ] Verify AI response received
- [ ] Test multiple messages
- [ ] Test conversation memory

### Test WebSocket
- [ ] Open browser developer console (Network tab)
- [ ] Filter for WS connections
- [ ] Verify WebSocket connection established
- [ ] Send message and check WebSocket frames
- [ ] Verify messages received in real-time

## Monitoring Setup

### CloudWatch Logs
- [ ] Open AWS CloudWatch Console
- [ ] Find log group: `/aws/lambda/fresenius-ai-assistant`
- [ ] Find log group: `/aws/lambda/fresenius-websocket-handler`
- [ ] Test log streaming with: `sam logs -n FreseiniusFunction --tail`

### CloudWatch Metrics
- [ ] Create CloudWatch dashboard
- [ ] Add Lambda invocation metrics
- [ ] Add Lambda error metrics
- [ ] Add Lambda duration metrics
- [ ] Add API Gateway request metrics

### CloudWatch Alarms
- [ ] Create alarm for Lambda errors > 5 in 5 minutes
- [ ] Create alarm for Lambda throttles > 0
- [ ] Create alarm for API Gateway 5xx errors
- [ ] Configure SNS topic for alarm notifications
- [ ] Test alarms

## Security

### IAM Roles
- [ ] Review Lambda execution role permissions
- [ ] Verify principle of least privilege
- [ ] Ensure Bedrock access limited to required models
- [ ] Verify API Gateway permissions

### Secrets
- [ ] Verify no secrets in code
- [ ] Verify no secrets in logs
- [ ] Consider migrating to AWS Secrets Manager
- [ ] Rotate `SECRET_KEY` if exposed

### API Gateway
- [ ] Review CORS settings
- [ ] Consider adding AWS WAF
- [ ] Consider adding API key requirement
- [ ] Consider throttling limits

## Performance Optimization

### Lambda Configuration
- [ ] Test different memory allocations (1024 MB, 2048 MB, 3072 MB)
- [ ] Measure cold start times
- [ ] Consider Provisioned Concurrency for production
- [ ] Review timeout settings

### Database
- [ ] Verify SQLite database created successfully
- [ ] Consider migrating to RDS for production
- [ ] Consider migrating to DynamoDB for serverless
- [ ] Test database performance under load

### Caching
- [ ] Consider adding CloudFront CDN
- [ ] Enable API Gateway caching
- [ ] Implement response caching in Lambda

## Production Readiness

### High Priority
- [ ] Migrate from SQLite to RDS or DynamoDB
- [ ] Move secrets to AWS Secrets Manager
- [ ] Set up comprehensive monitoring
- [ ] Configure auto-scaling if needed
- [ ] Enable X-Ray tracing
- [ ] Set up CloudWatch dashboard

### Medium Priority
- [ ] Add API rate limiting
- [ ] Implement request validation
- [ ] Add comprehensive error handling
- [ ] Set up automated backups
- [ ] Configure VPC if needed
- [ ] Add health check endpoint

### Low Priority
- [ ] Implement CI/CD pipeline
- [ ] Add automated testing
- [ ] Set up staging environment
- [ ] Document API with OpenAPI/Swagger
- [ ] Add API versioning
- [ ] Implement blue-green deployment

## Cost Management

### Monitor Costs
- [ ] Enable AWS Cost Explorer
- [ ] Set up billing alerts
- [ ] Review Lambda costs daily
- [ ] Review Bedrock token usage
- [ ] Review API Gateway costs

### Optimize Costs
- [ ] Right-size Lambda memory
- [ ] Reduce Lambda timeout if possible
- [ ] Implement caching to reduce Bedrock calls
- [ ] Review and remove unused resources
- [ ] Consider Savings Plans or Reserved Capacity

## Documentation

### Internal Documentation
- [ ] Document deployment process
- [ ] Document rollback procedures
- [ ] Document monitoring setup
- [ ] Document troubleshooting steps
- [ ] Create runbook for common issues

### Update README
- [ ] Update README with Lambda deployment info
- [ ] Add architecture diagram
- [ ] Update API documentation
- [ ] Document environment variables

## Testing

### Functional Testing
- [ ] Test all API endpoints
- [ ] Test all three roles (Patient/Doctor/Nurse)
- [ ] Test WebSocket connections
- [ ] Test OAuth flow
- [ ] Test error scenarios
- [ ] Test with different browsers

### Load Testing
- [ ] Test concurrent users
- [ ] Test API rate limits
- [ ] Monitor Lambda scaling
- [ ] Check for cold start issues
- [ ] Verify database performance

### Security Testing
- [ ] Test authentication bypass attempts
- [ ] Test SQL injection (should be prevented by SQLAlchemy)
- [ ] Test XSS attempts
- [ ] Verify CORS restrictions
- [ ] Test with expired tokens

## Rollback Plan

### If Deployment Fails
- [ ] Review CloudFormation error messages
- [ ] Check CloudWatch logs
- [ ] Verify IAM permissions
- [ ] Run `sam delete` to clean up
- [ ] Fix issues and retry

### If Production Issues
- [ ] Have previous version ARN ready
- [ ] Know how to revert Lambda alias
- [ ] Document rollback steps
- [ ] Test rollback procedure

## Success Criteria

### Deployment Success
- ✅ CloudFormation stack created successfully
- ✅ Lambda functions deployed
- ✅ API Gateway endpoints accessible
- ✅ No deployment errors in logs

### Functionality Success
- ✅ Users can log in via Google OAuth
- ✅ Chat functionality works for all roles
- ✅ WebSocket connections stable
- ✅ AI responses accurate and timely
- ✅ No errors in CloudWatch logs

### Performance Success
- ✅ API latency < 2 seconds (excluding AI processing)
- ✅ Cold starts < 5 seconds
- ✅ WebSocket latency < 100ms
- ✅ 99% uptime

## Next Steps After Deployment

1. [ ] Monitor for 24 hours
2. [ ] Review CloudWatch metrics
3. [ ] Gather user feedback
4. [ ] Plan production optimizations
5. [ ] Schedule security review
6. [ ] Document lessons learned

---

## Quick Reference

### Useful Commands

```bash
# Build
sam build --use-container

# Deploy
sam deploy --guided

# View logs
sam logs -n FreseiniusFunction --tail

# Test locally
sam local start-api

# Delete stack
sam delete

# Check stack status
aws cloudformation describe-stacks --stack-name fresenius-ai-assistant
```

### Important URLs

- CloudFormation Console: https://console.aws.amazon.com/cloudformation
- Lambda Console: https://console.aws.amazon.com/lambda
- API Gateway Console: https://console.aws.amazon.com/apigateway
- CloudWatch Console: https://console.aws.amazon.com/cloudwatch
- Bedrock Console: https://console.aws.amazon.com/bedrock

---

**Print this checklist and check off items as you complete them!**
