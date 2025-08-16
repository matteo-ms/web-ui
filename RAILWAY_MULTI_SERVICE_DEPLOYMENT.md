# 🚂 Railway Multi-Service Deployment Guide

## 🚀 Quick Deploy Steps

### 1. **Configura le Variabili d'Ambiente**

Nel tuo progetto Railway esistente, vai su **Variables** e aggiungi:

```bash
# Required
BROWSER_SERVICE_API_KEY=your-secure-api-key-here
OPENAI_API_KEY=your-openai-key-here

# Optional
VNC_PASSWORD=your-secure-vnc-password
RESOLUTION=1920x1080x24
DEFAULT_LLM_PROVIDER=openai
DEFAULT_LLM_MODEL=gpt-4o
```

### 2. **Verifica la Configurazione Build**

Assicurati che il tuo progetto Railway usi:
- **Builder**: `DOCKERFILE`
- **Dockerfile Path**: `Dockerfile.railway`

### 3. **Deploy**

```bash
# Se hai Railway CLI installato
railway up

# Oppure fai push al repository connesso
git add .
git commit -m "Update Railway multi-service configuration"
git push
```

## 🌐 URLs di Accesso

Dopo il deployment, i tuoi servizi saranno disponibili su:

```
https://your-app-name.up.railway.app/          → Web UI (Gradio)
https://your-app-name.up.railway.app/vnc/      → noVNC Interface  
https://your-app-name.up.railway.app/debug/    → Chrome DevTools
```

## 🔧 API Endpoints

### **Triggerare un Task**
```bash
curl -X POST "https://your-app-name.up.railway.app/execute-task" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_browser_service_api_key" \
  -d '{
    "task": "Vai su google.com e cerca informazioni sui gatti",
    "session_id": "optional-session-id"
  }'
```

### **Controllare Status**
```bash
curl -X GET "https://your-app-name.up.railway.app/task-status/{session_id}" \
  -H "X-API-Key: your_browser_service_api_key"
```

### **Cancellare Task**
```bash
curl -X POST "https://your-app-name.up.railway.app/task-cancel/{session_id}" \
  -H "X-API-Key: your_browser_service_api_key"
```

### **Health Check**
```bash
curl https://your-app-name.up.railway.app/health
```

## 📁 Accesso ai Risultati

I file generati saranno disponibili tramite:
```
https://your-app-name.up.railway.app/tmp/agent_history/{task_id}/{task_id}.json
https://your-app-name.up.railway.app/tmp/agent_history/{task_id}/{task_id}.gif
https://your-app-name.up.railway.app/tmp/agent_history/{task_id}/step_{N}.jpg
```

## 🔍 Troubleshooting

### **1. Controlla i Log**
```bash
railway logs
```

### **2. Verifica le Variabili**
```bash
railway variables
```

### **3. Test Health Check**
```bash
curl https://your-app-name.up.railway.app/health
```

### **4. Test VNC Access**
Vai su `https://your-app-name.up.railway.app/vnc/` e usa la password VNC configurata.

## 🎯 Differenze con AWS

| Aspetto | AWS (3 servizi) | Railway (1 servizio) |
|---------|-----------------|---------------------|
| **API URL** | `api-browser.knowlee.ai/execute-task` | `your-app.up.railway.app/execute-task` |
| **VNC URL** | `vnc.knowlee.ai` | `your-app.up.railway.app/vnc/` |
| **Web UI** | `browser.knowlee.ai` | `your-app.up.railway.app/` |
| **Costo** | ~$60-150/mese | ~$10-30/mese |
| **Setup** | Complesso | Semplice |

## ✅ Vantaggi del Setup Railway

- ✅ **Costi ridotti**: Un singolo servizio invece di 3
- ✅ **Manutenzione minima**: Railway gestisce tutto automaticamente
- ✅ **Deploy semplice**: Un comando per deployare tutto
- ✅ **Stessa funzionalità**: Tutti i servizi accessibili tramite routing nginx
- ✅ **Scalabilità automatica**: Railway scala automaticamente in base al traffico

## 🚀 Pronto per il Deploy!

Il tuo progetto è ora configurato per replicare esattamente la funzionalità del tuo setup AWS su Railway con un'architettura semplificata ma altrettanto potente.
