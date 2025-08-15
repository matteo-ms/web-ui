# 🚂 Railway Deployment Guide

Deploy your Browser Use WebUI on Railway in minutes!

## 🚀 Quick Deploy

### Method 1: One-Click Deploy
[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/your-template-id)

### Method 2: Manual Deploy

1. **Fork this repository** or clone it locally

2. **Login to Railway**
   ```bash
   npm install -g @railway/cli
   railway login
   ```

3. **Create a new Railway project**
   ```bash
   railway create browser-use-webui
   ```

4. **Set up environment variables**
   Copy variables from `.env.railway` to your Railway project:
   ```bash
   railway variables set OPENAI_API_KEY=your_key_here
   railway variables set BROWSER_SERVICE_API_KEY=your_key_here
   # Add other variables as needed
   ```

5. **Deploy**
   ```bash
   railway up
   ```

## 🔧 Configuration

### Required Environment Variables
- `OPENAI_API_KEY`: Your OpenAI API key
- `BROWSER_SERVICE_API_KEY`: Your browser service API key

### Optional Environment Variables
See `.env.railway` for the complete list of optional variables.

## 🌐 Access Your App

After deployment, Railway will provide you with:
- **Web URL**: `https://your-app-name.up.railway.app`
- **API Endpoint**: `https://your-app-name.up.railway.app/execute-task`
- **Health Check**: `https://your-app-name.up.railway.app/health`

## 🔍 Monitoring

- **Logs**: View real-time logs in Railway dashboard
- **Metrics**: Monitor CPU, memory, and network usage
- **Health**: Built-in health checks at `/health` endpoint

## 💰 Pricing

Railway offers:
- **Free Tier**: $5 worth of usage credits monthly
- **Pro Plan**: $20/month for higher limits
- **Usage-based**: Pay only for what you use

Estimated cost for this app: ~$10-30/month depending on usage.

## 🛠 Troubleshooting

### Common Issues

1. **Playwright Browser Not Found**
   - Railway automatically handles browser installation
   - Check logs for any installation errors

2. **Memory Issues**
   - Upgrade to Railway Pro for more memory
   - Monitor usage in Railway dashboard

3. **Timeout Issues**
   - Railway has 10-minute request timeout
   - Long-running tasks are automatically handled

### Debug Commands
```bash
# View logs
railway logs

# Connect to service
railway connect

# Check environment variables
railway variables
```

## 🔄 Updates

To update your deployment:
```bash
git push  # If connected to GitHub
# OR
railway up  # Manual deployment
```

## 🆚 Railway vs AWS ECS

| Feature | Railway | AWS ECS |
|---------|---------|---------|
| Setup Time | 5 minutes | 30+ minutes |
| Configuration | Minimal | Complex |
| Scaling | Automatic | Manual |
| Monitoring | Built-in | Requires setup |
| Cost | $10-30/month | $20-100+/month |
| Maintenance | Zero | High |

Railway is perfect for this application! 🎉
