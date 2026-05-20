# Expense Bot

A conversational AI-powered expense tracking bot for field workers, built on Telegram and Claude. Designed to streamline the process of logging receipts, tracking site codes, and generating formatted expense reports — all through natural language on a mobile device.

---

## What it does

Field workers often accumulate receipts throughout a trip without the context to organize them in real time. This bot solves that by letting the user:

- **Send receipt photos** — Claude vision extracts vendor, date, amount, category, and generates a description automatically
- **Log site codes** — forwarding any message or link containing an `L-XXXXX` code saves it automatically
- **Tag receipts to sites** — in plain language, during the trip or after via a reconciliation session
- **Generate expense reports** — a formatted summary sent via email with a PDF of all receipt images attached

Everything is driven by natural language. No commands to memorize.

---

## Features

- **Receipt processing** — photo → structured data via Claude vision
- **Site code extraction** — auto-detects `L-` codes from forwarded messages and links
- **Trip management** — start, name, rename, and end trips conversationally
- **Reconciliation** — walk through unassigned receipts after a trip and assign sites
- **Review mode** — revisit and update already-assigned receipts
- **Trip summary** — on-demand Telegram summary ordered by time with site tags
- **Email report** — full summary in email body, PDF of receipt images attached
- **Help system** — explains existing features or collects change requests and emails them to the developer with a conversation transcript

---

## Tech stack

- **Python 3.11**
- **python-telegram-bot** — Telegram bot framework
- **Anthropic Claude API** — receipt image processing and natural language intent detection
- **ReportLab** — PDF generation
- **python-dotenv** — environment variable management
- **Docker** — containerised deployment

---

## Project structure

```
expense-bot/
├── bot.py                  # Main bot — message handling and conversation flow
├── receipt_processor.py    # Claude vision receipt extraction
├── trip_log.py             # Trip and receipt data persistence (JSON)
├── reconciliation.py       # Reconciliation and review session logic
├── pdf_generator.py        # PDF report generation
├── help_handler.py         # Help flow and change request email
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container definition
├── docker-compose.yml      # Container orchestration
└── .env.example            # Environment variable template
```

---

## Setup

### Prerequisites

- Python 3.11+
- Docker (for containerised deployment)
- A Telegram bot token (via [@BotFather](https://t.me/BotFather))
- An Anthropic API key ([console.anthropic.com](https://console.anthropic.com))
- A Gmail account with an App Password enabled

### Environment variables

Copy `.env.example` to `.env` and fill in your values:

```
TELEGRAM_TOKEN=your_telegram_bot_token
ANTHROPIC_API_KEY=your_anthropic_api_key
GMAIL_ADDRESS=your_gmail_address@gmail.com
GMAIL_APP_PASSWORD=your_16_character_app_password
```


### Run locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 bot.py
```

### Run with Docker

```bash
docker compose up
```

---

## Usage

The bot is fully conversational. Example interactions:

| What you say | What happens |
|---|---|
| "Starting a trip" | Bot starts a new trip and asks for a name |
| Send a receipt photo | Bot extracts details and asks which site it's for |
| Forward a site link | Bot saves the `L-XXXXX` code automatically |
| "What do I have so far" | Bot shows a summary of the current trip |
| "Let's reconcile" | Bot walks through unassigned receipts one by one |
| "Review assigned" | Bot lets you update already-assigned receipts |
| "Email me" | Bot generates PDF and sends report to configured address |
| "Help" | Bot explains features or escalates a change request to the developer |

---

## Deployment

The bot is containerised and ready to deploy to any Docker-capable host. A `docker-compose.yml` is included with volume mounts for persistent photo and trip log storage.

For production deployment, environment variables should be managed at the OS or orchestration level rather than via a `.env` file.

---

## Notes

- Receipt photos are stored permanently and linked to their trip records
- Trip data persists in `trip_log.json` and is exportable via the JSON structure
- The bot uses long polling (suitable for local/single-server deployment)
- Switching to webhooks is recommended for higher-traffic or multi-instance deployments

---

## License

Private project. Not licensed for redistribution.
