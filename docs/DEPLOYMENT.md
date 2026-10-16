# Deployment Guide — GitHub, Render (backend) and Vercel (frontend)

```
Browser ──► Vercel  (React dashboard, static)
               │  VITE_API_BASE
               ▼
            Render  (FastAPI backend + built-in simulator, Docker)
               ├──► Supabase   (PostgreSQL: machines, alerts, maintenance, feedback)
               └──► InfluxDB Cloud (telemetry)
```

The databases are the cloud ones from `DATABASE_MANUAL_SETUP_GUIDE.md` (Supabase + InfluxDB Cloud). The simulator runs **inside** the backend (`INGEST_MODE=direct`), so no MQTT broker is needed online.

---

## Part A — Put the code on GitHub

1. On github.com click **New repository**. Name it `oee-smart-factory`. Choose **Public** or **Private**. Do **not** tick "Add a README" or ".gitignore" (the project already has them). Click **Create repository**.
2. In PowerShell, from the project folder:
   ```powershell
   cd E:\SE_Project
   git branch -M main
   git remote add origin https://github.com/<your-github-username>/oee-smart-factory.git
   git push -u origin main
   ```
3. The first push opens a browser window to sign in to GitHub (Git Credential Manager). Approve it.
4. Refresh the repository page — your files appear.

**Before you push, check:** `git status` shows nothing you do not want to publish, and the file `.env` is **not** listed (it is git-ignored on purpose; it holds your database password and API token).

---

## Part B — Deploy the backend on Render

1. Sign up at **render.com** with GitHub and allow access to the repository.
2. **New → Blueprint** → select the repository. Render reads `render.yaml` and proposes a web service called `oee-backend`.
3. Render asks for the values marked secret. Use the same values as in your local `.env`:

   | Variable | Value |
   |---|---|
   | `INFLUX_URL` | your InfluxDB Cloud address (`https://…cloud2.influxdata.com`) |
   | `INFLUX_TOKEN` | the InfluxDB API token |
   | `INFLUX_ORG` | your InfluxDB organisation name |
   | `POSTGRES_HOST` | the Supabase **Session pooler** host |
   | `POSTGRES_USER` | `postgres.<project-ref>` |
   | `POSTGRES_PASSWORD` | the Supabase database password |
   | `USERS` | **new** logins for the public site, e.g. `boss:StrongPass-1:floor_manager,viewer:Another-2:production_analyst` |
   | `CORS_ORIGINS` | leave a placeholder for now; set it in Part D |

   Roles: `floor_manager`, `maintenance_engineer`, `production_analyst`, `system_administrator`.
   **Do not reuse the demo passwords** (`manager123`, …) on a public site.
4. Click **Apply**. The first build takes 5–10 minutes (it installs the packages and trains the ML model).
5. When it shows **Live**, open `https://oee-backend.onrender.com/health` (use your own service address). Expect:
   `"storage_mode":"db"`, `"influx":"ok"`, `"postgres":"ok"`.

---

## Part C — Deploy the frontend on Vercel

1. Sign up at **vercel.com** with GitHub. **Add New → Project** → import the repository.
2. Set **Root Directory** to `frontend`. Vercel detects **Vite** (build `npm run build`, output `dist`).
3. Open **Environment Variables** and add:
   - `VITE_API_BASE` = `https://oee-backend.onrender.com` (your Render address, **no trailing slash**)
4. Click **Deploy**. When it finishes you get an address such as `https://oee-dashboard.vercel.app`.

> `VITE_API_BASE` is read when the site is **built**. If you change it later, redeploy the frontend.

---

## Part D — Allow the frontend to call the backend (CORS)

1. In Render open the `oee-backend` service → **Environment**.
2. Set `CORS_ORIGINS` to your Vercel address exactly, with no trailing slash:
   `https://oee-dashboard.vercel.app`
   (Several addresses can be separated by commas.)
3. Save. Render restarts the service automatically.

---

## Part E — Test the live site

1. Open your Vercel address. The machines and OEE should be live.
2. Open **Control**, sign in with one of the logins you put in `USERS`, and inject a temperature ramp.
3. Acknowledge the alert on **Alerts**.
4. Check **Supabase → Table Editor → alerts** and **InfluxDB → Data Explorer → telemetry_raw**.

---

## Free-plan behaviour to know about

- **Render free services sleep after about 15 minutes without traffic.** The first visit after a pause takes up to a minute while the backend wakes up and the simulator restarts. Open the site a minute before a demo.
- While the backend sleeps the simulator does not run, so no new telemetry is produced.
- **InfluxDB Cloud free plan keeps data for 30 days** (the SRS asks for 30 days raw and 1 year aggregated; one year needs a paid plan or a self-hosted InfluxDB).
- **Supabase free projects pause after about a week of inactivity.** Open the project in the dashboard to wake it.
- Memory use is about 170 MB, comfortably inside Render's 512 MB.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Site loads but shows no data, browser console shows a CORS error | `CORS_ORIGINS` on Render does not match the Vercel address exactly (check `https`, no trailing slash). |
| Dashboard shows "offline" | Backend is asleep or `VITE_API_BASE` is wrong. Open the backend `/health` address in a tab first. |
| `postgres: unreachable` in `/health` | Wrong Supabase host, user or password, or the project is paused. Use the **Session pooler** host. |
| `influx: unreachable` | Wrong `INFLUX_URL`, token or organisation. |
| Render build fails | Check the build log; the Dockerfile must be built from the repository root (`dockerContext: .`). |
| Everyone can sign in with `manager123` | `USERS` was not set on Render. Set it and keep `DEMO_HINTS=false`. |

## Updating the live site
`git push` to `main` → Render and Vercel redeploy automatically.
