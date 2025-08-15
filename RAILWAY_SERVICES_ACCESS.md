# 🚂 Railway Multi-Service Access Guide

Dopo il deployment su Railway, la tua applicazione esporrà diversi servizi attraverso un reverse proxy nginx.

## 🌐 URL di Accesso

Sostituisci `your-app-name` con il nome effettivo della tua app Railway:

### 🎯 Servizi Principali

| Servizio | URL | Descrizione |
|----------|-----|-------------|
| **Web UI** | `https://your-app-name.up.railway.app/` | Interfaccia principale Gradio |
| **VNC Web** | `https://your-app-name.up.railway.app/vnc/` | Interfaccia noVNC per controllo remoto |
| **Chrome Debug** | `https://your-app-name.up.railway.app/debug/` | Chrome DevTools Protocol |
| **Health Check** | `https://your-app-name.up.railway.app/health` | Stato dell'applicazione |

### 🔧 Esempio con la Tua App

Per la tua app attuale: `https://web-ui-production-9528.up.railway.app`

- **Web UI**: `https://web-ui-production-9528.up.railway.app/`
- **VNC Web**: `https://web-ui-production-9528.up.railway.app/vnc/`
- **Chrome Debug**: `https://web-ui-production-9528.up.railway.app/debug/`

## 🖥️ Come Utilizzare i Servizi

### 1. **Interfaccia VNC Web (noVNC)**
- Accedi a `/vnc/` per vedere il desktop virtuale
- Password VNC predefinita: `vncpassword` (configurabile tramite `VNC_PASSWORD`)
- Puoi interagire direttamente con il browser Chrome

### 2. **Chrome Remote Debugging**
- Accedi a `/debug/` per vedere le tab aperte di Chrome
- Utile per debugging avanzato delle automazioni browser
- Compatibile con Chrome DevTools

### 3. **API Endpoints**
Se hai endpoint API personalizzati, saranno accessibili tramite l'URL principale.

## ⚙️ Configurazione

### Variabili d'Ambiente Importanti
```bash
VNC_PASSWORD=your-secure-password
RESOLUTION=1920x1080x24
RESOLUTION_WIDTH=1920
RESOLUTION_HEIGHT=1080
```

### Porte Interne (per riferimento)
- Gradio WebUI: `7788`
- noVNC: `6080`
- VNC Server: `5901`
- Chrome Debug: `9222`
- Nginx Proxy: `${PORT}` (assegnata da Railway)

## 🚀 Deployment

Per fare il deploy con le nuove configurazioni:

```bash
# Commit delle modifiche
git add .
git commit -m "Add multi-service support with nginx proxy"

# Push su Railway (se collegato a GitHub)
git push origin main

# Oppure deploy manuale
railway up
```

## 🔍 Troubleshooting

### Servizi Non Raggiungibili
1. Controlla i logs Railway: `railway logs`
2. Verifica che nginx si stia avviando correttamente
3. Controlla che tutti i servizi siano in esecuzione

### VNC Non Funziona
- Verifica la password VNC
- Controlla che X11 e il display virtuale siano attivi
- Prova ad accedere dopo qualche minuto (i servizi potrebbero impiegare tempo ad avviarsi)

### Chrome Debug Non Accessibile
- Verifica che Chrome si sia avviato con `--remote-debugging-port=9222`
- Controlla i logs per errori di Chrome

## 📊 Monitoraggio

Utilizza l'endpoint `/health` per monitorare lo stato dell'applicazione:

```bash
curl https://your-app-name.up.railway.app/health
```

## 🔐 Sicurezza

- Cambia la password VNC predefinita tramite la variabile `VNC_PASSWORD`
- I servizi di debug dovrebbero essere utilizzati solo in ambienti di sviluppo
- Considera l'aggiunta di autenticazione per gli endpoint sensibili
