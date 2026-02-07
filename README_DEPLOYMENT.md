# Vietnam Gold Dashboard - Firebase Deployment Guide

## 🎯 Overview

This guide will help you deploy the Vietnam Gold & Market Dashboard to Firebase Hosting, making it accessible via a shareable web link.

## 📋 Prerequisites

1. **Node.js and npm** installed on your computer
2. **Firebase account** (free tier is sufficient)
3. **Python 3.x** with required packages installed

## 🚀 Quick Start Deployment

### Step 1: Install Firebase CLI

Open PowerShell and run:

```powershell
npm install -g firebase-tools
```

### Step 2: Login to Firebase

```powershell
firebase login
```

This will open your browser for authentication.

### Step 3: Create/Select Firebase Project

You have two options:

**Option A: Create a new project via Firebase Console**
1. Go to https://console.firebase.google.com/
2. Click "Add project"
3. Name it (e.g., "vietnam-gold-dashboard")
4. Follow the setup wizard (disable Google Analytics if not needed)
5. Note your project ID

**Option B: Use Firebase CLI**
```powershell
firebase projects:create vietnam-gold-dashboard
```

### Step 4: Link Your Local Project

Edit `.firebaserc` and replace `vietnam-gold-dashboard` with your actual project ID:

```json
{
  "projects": {
    "default": "your-actual-project-id"
  }
}
```

Or use the CLI:
```powershell
firebase use --add
```

### Step 5: Generate Fresh Data

```powershell
python generate_data.py
```

This creates `public/data.json` with the latest market data.

### Step 6: Deploy to Firebase

```powershell
firebase deploy --only hosting
```

### Step 7: Get Your Dashboard URL

After deployment, Firebase will provide a URL like:
- `https://your-project-id.web.app`
- `https://your-project-id.firebaseapp.com`

**Share this URL with your wife!** 📱

## 🔄 Updating Dashboard Data

### Manual Update (Recommended for Testing)

1. Run the data generator:
   ```powershell
   python generate_data.py
   ```

2. Deploy the updated data:
   ```powershell
   firebase deploy --only hosting
   ```

### Automated Updates with Task Scheduler (Windows)

Create a scheduled task to update data every 10 minutes:

1. **Create update script** (`update_and_deploy.bat`):
   ```batch
   @echo off
   cd /d C:\Users\tukum\.windsurf\worktrees\gold-dashboard-arena\gold-dashboard-arena-1468470e
   python generate_data.py
   firebase deploy --only hosting --token YOUR_CI_TOKEN
   ```

2. **Get Firebase CI token**:
   ```powershell
   firebase login:ci
   ```
   Copy the token and replace `YOUR_CI_TOKEN` in the script.

3. **Create scheduled task**:
   - Open Task Scheduler
   - Create Basic Task
   - Name: "Update Gold Dashboard"
   - Trigger: Daily, repeat every 10 minutes
   - Action: Start a program
   - Program: `C:\path\to\update_and_deploy.bat`

### Automated Updates with GitHub Actions (Recommended)

The workflow file already exists at `.github/workflows/update-dashboard.yml`. It runs every 30 minutes and deploys fresh data to Firebase Hosting automatically.

**One-time setup steps:**

1. **Push this repo to GitHub** (if not already):
   ```powershell
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/YOUR_USERNAME/gold-dashboard-arena.git
   git push -u origin main
   ```

2. **Generate a Firebase service account key**:
   - Go to [Firebase Console](https://console.firebase.google.com/) → your project → Project Settings → Service Accounts
   - Click **"Generate new private key"** → download the JSON file
   - **Do NOT commit this file** — it contains secrets

3. **Add GitHub Secrets** (Settings → Secrets and variables → Actions → New repository secret):
   - `FIREBASE_SERVICE_ACCOUNT` — paste the **entire contents** of the downloaded JSON key file
   - `FIREBASE_PROJECT_ID` — your Firebase project ID (e.g., `gold-dashboard-2026`)

4. **Verify the first run**:
   - Go to the **Actions** tab on GitHub
   - Click **"Update Dashboard Data"** → **"Run workflow"** to trigger manually
   - Confirm the run completes successfully and your live site shows fresh data

After setup, the workflow runs automatically every ~30 minutes with no further action needed.

## 🧪 Local Testing

Before deploying, test the dashboard locally:

1. **Generate data**:
   ```powershell
   python generate_data.py
   ```

2. **Start local server**:
   ```powershell
   firebase serve
   ```

3. **Open in browser**:
   ```
   http://localhost:5000
   ```

## 📱 Mobile Optimization

The dashboard is fully responsive and optimized for mobile devices. Your wife can:

1. **Add to Home Screen** (iOS/Android):
   - Open the dashboard URL in Safari/Chrome
   - Tap Share → Add to Home Screen
   - Creates an app-like icon

2. **Bookmark** for quick access

## 🎨 Customization

### Change Colors/Theme

Edit `public/styles.css` and modify the CSS variables:

```css
:root {
    --primary-color: #2563eb;  /* Change to your preferred color */
    --gold-color: #fbbf24;
    /* ... other colors ... */
}
```

### Change Refresh Interval

Edit `public/app.js`:

```javascript
const REFRESH_INTERVAL = 10 * 60 * 1000; // Change to desired milliseconds
```

### Add Vietnamese Language

Edit `public/index.html` to add Vietnamese labels alongside English.

## 🔧 Troubleshooting

### Data Not Updating

1. Check if `public/data.json` exists and is recent
2. Clear browser cache (Ctrl+Shift+R or Cmd+Shift+R)
3. Verify Firebase deployment succeeded

### Firebase Deploy Fails

1. Ensure you're logged in: `firebase login`
2. Check project ID in `.firebaserc` matches your Firebase project
3. Verify you have hosting enabled in Firebase Console

### Data Generation Errors

1. Check internet connection (scraping requires network access)
2. Some sources may be temporarily down (fallback data will be used)
3. Review error messages in console output

## 📊 Data Sources

The dashboard fetches data from:

- **Gold**: SJC official site (with Mi Hồng fallback)
- **USD/VND**: EGCurrency black market rates
- **Bitcoin**: CoinMarketCap (with CoinGecko API fallback)
- **VN30 Index**: Vietstock

All data is cached for 10 minutes to avoid rate limiting.

## 🔒 Security Notes

- No sensitive data is exposed in the frontend
- All scraping happens server-side (in `generate_data.py`)
- Firebase Hosting provides HTTPS by default
- Data is read-only (no user input/database)

## 💰 Cost

**Firebase Hosting Free Tier includes:**
- 10 GB storage
- 360 MB/day bandwidth
- Custom domain support

For a simple dashboard like this, you'll stay well within the free tier.

## 📞 Support

If you encounter issues:

1. Check Firebase Console for deployment status
2. Review browser console for JavaScript errors
3. Verify `data.json` is being generated correctly
4. Ensure all Python dependencies are installed

## 🎉 Next Steps

After deployment:

1. ✅ Share the URL with your wife
2. ✅ Test on her phone/device
3. ✅ Set up automated updates (optional)
4. ✅ Customize colors/theme to preference
5. ✅ Add to home screen for easy access

---

**Your dashboard is now live and shareable!** 🚀
