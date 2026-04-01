# Development Workflow

## Canonical Statement Input
- `expense_elt/data/RBC_Visa`
- `expense_elt/data/BMO_Mastercard`
- `expense_elt/data/Amex`

## Python Setup and Validation
```bash
cd expense_elt
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

On Ubuntu or other Debian-based Linux environments, install `libpoppler-cpp-dev` and `pkg-config` before `pip install -r requirements-dev.txt` so the `pdftotext` dependency used by `monopoly-core` can build successfully.

## Frontend Setup and Validation
```bash
cd frontend
npm ci
npm run typecheck
npm run build
```

`npm run build` already includes the TypeScript build check. There is no dedicated frontend UI test harness yet, so the current frontend gate is typecheck plus production build.

## CI Parity
The GitHub Actions workflow mirrors the same checks:
- Linux system packages `libpoppler-cpp-dev` and `pkg-config` for the PDF parser build
- Python install plus `python -m pytest -q`
- Frontend install plus `npm run typecheck`
- Frontend install plus `npm run build`

## Hosting with ngrok

Expose the local server to the internet via ngrok. Useful for accessing the app from another device or sharing with an accountant.

### Prerequisites
- Install ngrok: https://ngrok.com/download
- Sign up and authenticate: `ngrok config add-authtoken <your-token>`

### 1. Start the app
```bash
cd expense_elt
python main.py serve --port 9743
```

### 2. Start ngrok (PowerShell)
```powershell
Start-Process -NoNewWindow -FilePath ngrok -ArgumentList "http 9743 --log=stdout" -RedirectStandardOutput ngrok/ngrok.log -RedirectStandardError ngrok/ngrok-error.log
```

This runs ngrok in the background. You can close the terminal afterward. Logs are saved to the `ngrok/` folder (gitignored).

To stop ngrok later:
```powershell
Stop-Process -Name ngrok
```

### 3. Get the public URL
```powershell
curl -s http://localhost:4040/api/tunnels | python -m json.tool
```

Look for the `public_url` field (e.g., `https://abc123.ngrok-free.app`).

### 4. Update Google OAuth
In the [Google Cloud Console](https://console.cloud.google.com/apis/credentials):
- Add the ngrok URL to **Authorized JavaScript origins**
- Add the ngrok URL to **Authorized redirect URIs**

### 5. Update CORS
Add the ngrok URL to `CORS_ORIGINS` in `expense_elt/.env`:
```
CORS_ORIGINS=http://localhost:9743,http://localhost:5173,https://abc123.ngrok-free.app
```

### Notes
- Free ngrok generates a **new URL on every restart** — you'll need to update Google OAuth and CORS each time. A paid plan with a reserved domain avoids this.
- The ngrok inspector UI is available at `http://localhost:4040` while running.
- On Git Bash / Linux, use `nohup ngrok http 9743 --log=stdout > ngrok/ngrok.log 2>&1 & disown` instead.
