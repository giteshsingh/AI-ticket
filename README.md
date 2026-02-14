# Mahakaleshwar Booking Bot (Python)

This project provides a **run-on-demand** and **continuous retry** app to attempt booking for:

`https://www.shrimahakaleshwar.mp.gov.in/services/bhasmaarti-booking`

> ⚠️ The site can include captcha/OTP/manual checks. This tool does not bypass those protections.

### Login flow

The site requires login before booking. The bot will:

1. Open the login page: `https://www.shrimahakaleshwar.mp.gov.in/services/login`
2. Enter your mobile number (from `config.yaml` or `MOBILE_NUMBER` in `.env`) and click **Get OTP**
3. Pause so you can enter the OTP in the browser (use `--headful` so the window is visible)
4. After login (or timeout), navigate to the Bhasma Aarti booking page and continue

## Why Python

Python + Playwright is well-suited for browser automation with easy scheduling logic.

## Setup

1. Create virtual env and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

2. Optional: create custom config:

```bash
cp config.example.yaml config.yaml
```

## Run

### On demand (single attempt)

```bash
python booking_bot.py --mode once --headful
```

### Continuous mode (keeps trying)

```bash
python booking_bot.py --mode continuous --config config.yaml --headful
```

### Real execution mode

By default, script is `dry_run: true` and will stop before final booking click.
To execute the proceed click:

```bash
python booking_bot.py --mode once --execute --headful
```

## Notes

- If date picker/button selectors change, update them in `config.yaml`.
- Use `--headful` for interactive steps like login/captcha.
- In production, run continuous mode via systemd/supervisor/docker restart policy.
