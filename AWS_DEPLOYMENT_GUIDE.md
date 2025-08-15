# AWS ECS Deployment Guide

## Problem Diagnosis
Your ECS tasks were failing health checks because:
1. **Complex service startup chain**: The application uses multiple interdependent services (Xvfb → VNC → noVNC → Chrome → WebUI)
2. **Inadequate health checks**: Simple port checks don't verify application readiness
3. **Missing environment variables**: `BROWSER_SERVICE_API_KEY` is required but wasn't set
4. **Insufficient startup time**: ELB health checks started too early before services were ready

## Solutions Implemented

### 1. Improved Health Check Script
- **Multi-service validation** with retry logic
- **Prioritized checks**: Critical services first (API server → WebUI → supporting services)
- **Graceful degradation**: Won't fail if non-critical services aren't ready
- **Better timeout handling**: 5-second timeouts with 3 retries per service

### 2. Enhanced Container Startup
- **Environment variable defaults**: Automatic fallback for required variables
- **Robust directory creation**: Ensures all needed directories exist
- **Better error handling**: Graceful handling of permission issues
- **Increased service startup times**: More time for complex service dependencies

### 3. Supervisord Configuration Improvements
- **Longer startup grace periods**: 10 seconds for main services
- **More retry attempts**: 5 retries instead of 3
- **Better dependency management**: Proper service ordering

## AWS ECS Configuration Requirements

### 1. Environment Variables
**Required in your ECS Task Definition:**
```json
{
  "environment": [
    {
      "name": "BROWSER_SERVICE_API_KEY",
      "value": "your-secure-api-key-here"
    },
    {
      "name": "CHROME_DEBUGGING_PORT",
      "value": "9222"
    }
  ]
}
```

### 2. Health Check Configuration

#### Option A: Use API Server Health Check (Recommended)
Configure your Target Group to check the API server:
- **Port**: `7789`
- **Protocol**: `HTTP`
- **Path**: `/healthcheck`
- **Healthy threshold**: `2`
- **Unhealthy threshold**: `3`
- **Timeout**: `10 seconds`
- **Interval**: `30 seconds`
- **Grace period**: `120 seconds`

#### Option B: Use Enhanced Docker Health Check
If you prefer to keep checking port 7788:
- **Grace period**: `120 seconds` (increased from 30s)
- **Timeout**: `10 seconds` (increased from 5s)
- **Retries**: `5` (increased from 3)
- **Interval**: `30 seconds`

### 3. ECS Service Configuration
```json
{
  "healthCheckGracePeriodSeconds": 120,
  "desiredCount": 1,
  "launchType": "FARGATE",
  "networkConfiguration": {
    "awsvpcConfiguration": {
      "assignPublicIp": "ENABLED",
      "securityGroups": ["sg-your-security-group"],
      "subnets": ["subnet-your-subnet"]
    }
  }
}
```

### 4. Security Group Rules
Ensure your security group allows:
- **Port 7788**: Main WebUI (from ALB)
- **Port 7789**: API server (for health checks if using Option A)
- **Port 6080**: noVNC (optional, for VNC access)

## Deployment Steps

### 1. Update Your Container
```bash
# Build with new improvements
docker build -t your-ecr-repo:latest .

# Push to ECR
docker push your-ecr-repo:latest
```

### 2. Update ECS Task Definition
Add the required environment variables to your task definition.

### 3. Update Target Group Health Check
Choose either Option A (API server) or Option B (enhanced Docker health check) from above.

### 4. Update ECS Service
```bash
aws ecs update-service \
  --cluster your-cluster \
  --service your-service \
  --force-new-deployment
```

## Monitoring and Troubleshooting

### Check Health Check Logs
```bash
# Connect to your running container
aws ecs execute-command \
  --cluster your-cluster \
  --task your-task-id \
  --container browser-use \
  --interactive \
  --command "/bin/bash"

# Run health check manually
/app/health_check.sh
```

### Common Issues and Solutions

1. **"BROWSER_SERVICE_API_KEY environment variable must be set"**
   - **Solution**: Add the environment variable to your ECS task definition

2. **"Health checks failed"**
   - **Check**: Services are starting in correct order
   - **Verify**: Health check grace period is sufficient (120s recommended)
   - **Test**: Run health check script manually in container

3. **"Task failed to start"**
   - **Check**: CPU/Memory limits are sufficient
   - **Verify**: Security group allows required ports
   - **Review**: CloudWatch logs for startup errors

## Resource Requirements

### Recommended Task Resources
- **CPU**: 2048 (2 vCPU)
- **Memory**: 4096 MB (4 GB)
- **Storage**: 20 GB (for Chrome data and temporary files)

### Cost Optimization
- Use **Fargate Spot** for non-production environments
- Set up **auto-scaling** based on CPU/memory usage
- Consider **scheduled scaling** if usage is predictable

## Security Considerations

1. **API Key Management**: Use AWS Secrets Manager instead of plain text environment variables
2. **Network Security**: Use private subnets with NAT Gateway for production
3. **Container Security**: Run security scans on your container images
4. **Access Control**: Limit ALB access to specific IP ranges if possible

## Rollback Plan

If issues persist:
1. Revert to previous task definition
2. Use simple health check temporarily: `CMD nc -z localhost 7788 || exit 1`
3. Increase health check grace period to 300 seconds
4. Debug with a single running task before scaling up 