# Railway Firebase Configuration Guide

## Frontend Service Environment Variables

After the recent Dockerfile changes, you need to set these environment variables in the Railway frontend service:

### Firebase Configuration

```bash
VITE_FIREBASE_API_KEY=AIzaSyDZxC_qLZUzcY_8Hq3CqJmwVv-ELKtqYd0
VITE_FIREBASE_AUTH_DOMAIN=clinica-oncologica-v02.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=clinica-oncologica-v02
VITE_FIREBASE_STORAGE_BUCKET=clinica-oncologica-v02.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID=461863078823
VITE_FIREBASE_APP_ID=1:461863078823:web:1dab4fdce1c4f8e39a7419
```

### How to Set in Railway

1. Open your Railway project dashboard
2. Select the **frontend-hormonia** service
3. Go to **Variables** tab
4. Click **New Variable** for each of the 6 Firebase variables above
5. Copy-paste the exact values (no quotes needed in Railway UI)
6. Click **Deploy** or wait for automatic redeploy

### Backend Service Environment Variables

Set these in the backend-hormonia service:

```bash
# Auto-provisioning control (RECOMMENDED: false for production)
AUTO_PROVISION_SUPABASE_USERS=false

# Domain whitelist (only matters if auto-provision is true)
FIREBASE_ALLOWED_DOMAINS=[]

# Block public email providers (gmail, yahoo, hotmail, etc)
FIREBASE_BLOCK_PUBLIC_DOMAINS=true
```

**Security Note**: O Firebase é usado para autenticação dos médicos/admins. O `FIREBASE_ALLOWED_DOMAINS` protege contra criação não autorizada de contas:

**Opção 1 - Manual (RECOMENDADO para máxima segurança)**:
```bash
AUTO_PROVISION_SUPABASE_USERS=false
```
- Admins criam usuários manualmente no backend primeiro
- Depois usuários autenticam via Firebase normalmente
- Previne qualquer pessoa de criar conta sem aprovação

**Opção 2 - Auto-provisionamento controlado**:
```bash
AUTO_PROVISION_SUPABASE_USERS=true
FIREBASE_ALLOWED_DOMAINS=["clinicaoncologica.com.br","hospitalsaomateus.com.br"]
FIREBASE_BLOCK_PUBLIC_DOMAINS=true
```
- Apenas emails institucionais podem se auto-provisionar
- Bloqueia gmail.com, yahoo.com, hotmail.com, etc
- Primeira autenticação cria usuário automaticamente como DOCTOR

### Firebase Console Setup

After Railway variables are set, configure in Firebase Console (https://console.firebase.google.com):

1. **Verify Storage Bucket Format**:
   - Go to Project Settings → General
   - Check if Storage Bucket shows `clinica-oncologica-v02.appspot.com` or `clinica-oncologica-v02.firebasestorage.app`
   - If it's `.appspot.com`, update the Railway variable to match

2. **Authorize Domain**:
   - Go to Authentication → Settings → Authorized domains
   - Click **Add domain**
   - Add: `frontend-production-18bb.up.railway.app`
   - Save

3. **Development Domain** (optional for local testing):
   - Add `localhost` if not already present

## Verification Steps

After Railway redeploys (usually 2-3 minutes):

1. **Check Build Logs**:
   ```bash
   # Should show Firebase variables in build output
   VITE_FIREBASE_API_KEY=AIza...
   VITE_FIREBASE_AUTH_DOMAIN=clinica...
   ```

2. **Test Frontend**:
   - Open https://frontend-production-18bb.up.railway.app
   - Open browser DevTools → Console
   - Should NOT see "Firebase is not configured"

3. **Test Login**:
   - Navigate to login page
   - Page should render without white screen
   - Firebase authentication should work

## Troubleshooting

### "Firebase is not configured" persists
- Verify all 6 variables are set in Railway (check for typos)
- Check Railway build logs show the variables
- Hard refresh browser (Ctrl+Shift+R) to clear cache

### Storage bucket error
- Update VITE_FIREBASE_STORAGE_BUCKET to use `.appspot.com` format if needed
- Redeploy after change

### Domain authorization error
- Ensure domain is added to Firebase Authorized domains
- Wait 1-2 minutes for Firebase to propagate changes

## Related Files

- [frontend-hormonia/Dockerfile](../../frontend-hormonia/Dockerfile) - Build configuration
- [frontend-hormonia/src/lib/firebase-client.ts](../../frontend-hormonia/src/lib/firebase-client.ts) - Firebase initialization
- [backend-hormonia/app/config.py](../../backend-hormonia/app/config.py) - Backend Firebase settings
