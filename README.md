# ArbitrageBot

Website content reader and arbitrage analyzer.

Reads the fixed public page:

`https://betting.co.zw/sportsbook/upcoming`

The app extracts visible text and structures sportsbook page content into:

`Sport -> Competition -> Event -> Market -> Selection -> Odds`

It is read-only. It does not log in, place bets, create accounts, make payments, or interact with the site beyond loading, reading, scrolling, and taking screenshots when fallback extraction is needed.

## Run

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
cd frontend
npm.cmd install
npm.cmd run build
cd ..
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open:

`http://127.0.0.1:8000/reader`

## AI Vision Reader

The AI vision fallback is optional and only runs when browser extraction is incomplete.
Set these environment variables to enable it:

```powershell
$env:OPENAI_API_KEY="your_api_key"
$env:AI_VISION_MODEL="gpt-4o-mini"
```

If no API key is configured, the app records a warning and still returns HTML/browser extraction results.

## API

- `POST /api/scan` starts a read of the fixed URL.
- `GET /api/sessions/latest` returns the latest reading session.
- `GET /api/sessions/{id}` returns one session.
- `GET /api/sessions` lists recent sessions.
- `GET /api/logs` returns extraction logs.
