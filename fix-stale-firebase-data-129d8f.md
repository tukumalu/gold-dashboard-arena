# Fix Stale Firebase Dashboard Data

The dashboard data is stuck because there is **no automated pipeline** — `generate_data.py` must be run manually, and `firebase deploy` must be run manually to push the new `data.json` to hosting.

## Root Cause

The current architecture is fully static:

1. **`generate_data.py`** scrapes live data → writes `public/data.json`
2. **`firebase deploy --only hosting`** uploads the `public/` folder (including `data.json`) to Firebase Hosting
3. **`app.js`** fetches `data.json` every 10 minutes from Firebase Hosting — but this file **never changes** unless steps 1+2 are re-run

The frontend's `setInterval(fetchData, REFRESH_INTERVAL)` re-fetches `data.json` from the CDN, but since `data.json` is a static file baked into the deploy, it always returns the same stale snapshot from the last deployment.

## Options (Pick One)

### Option A: GitHub Actions Cron (Recommended — Free, No Local Machine Required)
- Create `.github/workflows/update-dashboard.yml` with a cron schedule (e.g., every 10 min or every 30 min)
- The workflow: checkout → install Python deps → run `generate_data.py` → deploy to Firebase via service account
- **Pros:** Runs in the cloud, no local machine needed, free within GitHub Actions limits (~2,000 min/month)
- **Cons:** Requires pushing repo to GitHub, setting up `FIREBASE_SERVICE_ACCOUNT` secret
- **Note:** GitHub Actions cron has ~5-15 min jitter, so "every 10 min" may actually be every 10-25 min

### Option B: Windows Task Scheduler (Simple, Local)
- Create `update_and_deploy.bat` that runs `generate_data.py` + `firebase deploy`
- Schedule it via Windows Task Scheduler every 10 minutes
- **Pros:** Simple, no cloud setup
- **Cons:** Only works when your PC is on and connected

### Option C: Firebase Cloud Function + Firestore (Best Architecture, More Work)
- Replace static `data.json` with a Firebase Cloud Function (Python or Node.js) that runs on a schedule via Cloud Scheduler
- The function scrapes data and writes to Firestore (or Realtime Database)
- Frontend reads from Firestore instead of a static JSON file
- **Pros:** True real-time, no redeployment needed, serverless
- **Cons:** Requires Blaze (pay-as-you-go) plan for Cloud Functions + outbound network (scraping), more migration work

### Option D: External Cron Service (e.g., cron-job.org) + Firebase REST API
- Use a free cron service to hit a Firebase Cloud Function HTTP endpoint on a schedule
- The function scrapes and writes to Realtime Database / Firestore
- Frontend subscribes to live updates
- **Pros:** Free cron trigger, real-time frontend
- **Cons:** Still needs Blaze plan for Cloud Functions with outbound requests

## Recommended Next Step

**Option A (GitHub Actions)** is the best balance of effort vs. reliability. Implementation steps:

1. Create a Firebase service account key and add it as a GitHub secret
2. Create `.github/workflows/update-dashboard.yml` with cron schedule
3. Push repo to GitHub (if not already)
4. Verify the first automated run produces fresh `data.json` on the live site

If you want the dashboard to work even when your PC is off and you don't want to set up GitHub, **Option C** is the long-term best architecture but requires more migration.
