# XFas Logistics - Vercel Deployment Guide

## 🚀 Quick Deployment Steps

### Step 1: Prepare Files
1. **Rename requirements file**:
   ```bash
   mv requirements_vercel.txt requirements.txt
   ```

2. **Ensure you have these files**:
   - `vercel.json` ✅
   - `requirements.txt` ✅
   - `server.py` ✅
   - `api/index.py` ✅
   - All other backend files ✅

### Step 2: Deploy to Vercel

#### Option A: Vercel CLI (Recommended)
1. **Install Vercel CLI**:
   ```bash
   npm install -g vercel
   ```

2. **Login to Vercel**:
   ```bash
   vercel login
   ```

3. **Deploy from backend folder**:
   ```bash
   cd backend
   vercel
   ```

4. **Follow the prompts**:
   - Link to existing project? **No**
   - Project name: **xfas-backend**
   - Directory: **./** (current directory)
   - Override settings? **No**

#### Option B: GitHub Integration
1. **Push to GitHub** (if not already done)
2. **Go to [vercel.com](https://vercel.com)**
3. **Import project** from GitHub
4. **Select backend folder** as root directory
5. **Deploy**

### Step 3: Configure Environment Variables
1. **Go to Vercel Dashboard**
2. **Select your project**
3. **Go to Settings → Environment Variables**
4. **Add these variables**:
   ```
   MONGO_URL=mongodb+srv://shwetakashyap942001_db_user:RcJ2L2ksOV0NMsPn@cluster0.cw5dmyv.mongodb.net/
   DB_NAME=xfas_logistics
   JWT_SECRET_KEY=ksHrzF47Sm7lHGue4FpmyFzE-7F1M1Eo9GdxgHb4rpw
   JWT_ALGORITHM=HS256
   JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
   CORS_ORIGINS=https://silver-smakager-4f7e69.netlify.app,http://localhost:3000
   ENVIRONMENT=production
   DEBUG=false
   ```

### Step 4: Update Frontend
1. **Get your Vercel URL** (e.g., `https://xfas-backend-abc123.vercel.app`)
2. **Update frontend API URL**:
   ```javascript
   const BACKEND_URL = 'https://your-actual-vercel-url.vercel.app/api/';
   ```
3. **Redeploy frontend** on Netlify

## ✅ Testing

### Test Backend:
1. **Health Check**: `https://your-vercel-url.vercel.app/api/health`
2. **Root API**: `https://your-vercel-url.vercel.app/api/`
3. **Registration**: Test user registration

### Test Frontend Integration:
1. **Update frontend** with Vercel backend URL
2. **Test registration/login**
3. **Test all features**

## 🎯 Why Vercel Should Work Better

- **Python 3.11** by default (better MongoDB compatibility)
- **Serverless functions** (no SSL handshake issues)
- **Automatic scaling**
- **Free tier** available
- **Easy deployment**
- **Better error handling**

## 🚨 Troubleshooting

### Common Issues:
1. **Import errors**: Check `api/index.py` path
2. **Environment variables**: Verify in Vercel dashboard
3. **CORS issues**: Update CORS_ORIGINS
4. **MongoDB connection**: Should work better with Python 3.11

### If deployment fails:
1. **Check Vercel logs**
2. **Verify requirements.txt**
3. **Check vercel.json syntax**
4. **Ensure all files are uploaded**

## 📞 Next Steps

After successful deployment:
1. **Test the API endpoints**
2. **Update frontend** with new backend URL
3. **Test full integration**
4. **Monitor Vercel logs** for any issues

---

**Note**: Vercel uses Python 3.11 by default, which should resolve the MongoDB SSL handshake issues we had with Render's Python 3.13.
