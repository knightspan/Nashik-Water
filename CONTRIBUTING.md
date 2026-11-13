# Working on this project (team guide)

Everything you push to `main` on GitHub goes live by itself: Render rebuilds the API and
Vercel rebuilds the website within a few minutes. So test on your own PC first.

- Website: https://nashik-water.vercel.app
- API: https://nashik-water-api.onrender.com (docs at `/docs`)

## 1. One-time setup on your PC (about 15 minutes)

1. Install **Git** (git-scm.com), **VS Code**, **Node.js 22 LTS** (nodejs.org) and
   **Python 3.11, 3.12 or 3.13** (python.org, tick "Add python.exe to PATH").
2. Accept the GitHub invitation e-mail for **knightspan/Nashik-Water**.
3. In VS Code: `Ctrl+Shift+P` → **Git: Clone** → paste
   `https://github.com/knightspan/Nashik-Water.git` → choose a folder → **Open**.
   Sign in to GitHub when VS Code asks.
4. Tell Git who you are (once, in the VS Code terminal, `` Ctrl+` ``):
   ```
   git config --global user.name  "Your Name"
   git config --global user.email "the-email-on-your-github-account"
   ```
5. In the terminal, in the project folder:
   ```
   npm run setup
   npm run dev
   ```
   `setup` installs everything (a portable PostgreSQL, Python and website packages) and
   creates `backend/.env`. `dev` starts the database, API, simulator and website.
   Open http://localhost:5173. The admin login is printed by `npm run setup`.
   No Docker is needed.

## 2. Every time you work

```
git pull                         # get your teammates' latest changes first
git switch -c my-change          # a branch for your work (any short name)
# ... edit, then test with: npm run dev   and   npm test
git add -A
git commit -m "What you changed, in one line"
git push -u origin my-change
```

Then on GitHub open a **Pull request** from your branch into `main`. Vishal reviews it and
merges with **"Create a merge commit"**; the website and API then update by themselves.

In VS Code you can do the same with the **Source Control** panel (`Ctrl+Shift+G`):
pull, create a branch (bottom-left corner), stage, commit, publish branch.

## 3. Rules

- Never commit passwords or keys. These files stay on your PC and are git-ignored:
  `backend/.env`, `hosting.env`, `firmware/esp32c3_station/config.h`.
  Ask Vishal privately for the station's API key if you need to flash the ESP32.
- Run `npm test` before you push.
- Marathi text lives in `frontend/src/i18n/mr.ts`, English in `en.ts`; change both together.
- Hardware: see `docs/STATION.md`. Firmware is uploaded from the Arduino IDE, not deployed
  by GitHub.

## Where things are

| Folder | What |
|---|---|
| `frontend/` | Website (React) |
| `backend/` | Cloud API (FastAPI) and database |
| `firmware/esp32c3_station/` | ESP32-C3 sensor station |
| `firmware/esp32c3_sensor_test/` | 4-sensor test sketch |
| `ml/` | Model training and report |
| `simulator/` | Demo data for the simulated sites |
| `docs/` | Station, architecture, API, deployment guides |
