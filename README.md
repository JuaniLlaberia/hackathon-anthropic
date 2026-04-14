# WhatsApp Marketplace Bot

A WhatsApp-powered AI assistant that helps users create and publish product listings on Mercado Libre Argentina. Built with Anthropic's Managed Agents API, Kapso WhatsApp API, and Mercado Libre's REST API.

## How It Works

```
User sends photo via WhatsApp
    -> Kapso webhook -> FastAPI backend
        -> Dispatcher routes to onboarding or publication
        -> AI Agent (Claude) analyzes photo, researches prices,
           generates optimized listing
        -> User confirms -> listing published on Mercado Libre
    <- Response sent back via WhatsApp
```

### Full User Flow

1. **Onboarding**: New user sends a message. The bot asks them to connect their Mercado Libre account via OAuth.
2. **Product Photo**: User sends a photo of the product they want to sell.
3. **AI Analysis**: Claude analyzes the image, identifies the product (brand, model, condition), searches for the correct ML category, looks up reference prices via web search, and fetches required category attributes.
4. **Listing Draft**: The agent presents a complete listing draft with optimized title, suggested price, and generated description.
5. **User Edits**: User can request changes to price, title, or description.
6. **Publish**: User confirms and the listing is created on Mercado Libre via their API.

## Architecture

```
hackathon-anthropic/
├── backend/                  # FastAPI + Python 3.11
│   ├── app/
│   │   ├── auth/             # MercadoLibre OAuth callback
│   │   ├── onboarding/       # User registration + ML account linking
│   │   ├── publication/      # AI agent + ML listing creation
│   │   │   ├── agent_service.py   # Anthropic Managed Agents integration
│   │   │   └── ml_tools.py        # ML API tools (category, attributes, create listing)
│   │   ├── shared/           # Kapso client, Claude client, DB models
│   │   └── webhook/          # Kapso webhook receiver + message dispatcher
│   └── alembic/              # Database migrations
├── frontend/                 # React + TypeScript + Vite
│   └── src/
│       ├── onboarding/       # Admin dashboard, user list
│       └── publication/      # Feed, moderation panel, publication detail
├── database/                 # PostgreSQL init scripts
└── docker-compose.yml        # PostgreSQL + Backend + Frontend
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.11, FastAPI, SQLAlchemy, Alembic |
| AI Agent | Anthropic Managed Agents API (Claude Haiku 4.5) |
| WhatsApp | Kapso API (webhooks + messaging) |
| Marketplace | Mercado Libre REST API (OAuth, items, categories) |
| Database | PostgreSQL 16 |
| Frontend | React 18, TypeScript, Vite |
| Infrastructure | Docker Compose |

## Key Features

- **Vision-powered product recognition**: Send a photo and Claude identifies the product, brand, model, and condition
- **Real-time price research**: Agent uses web search to find competitive pricing on Mercado Libre
- **Category auto-detection**: Uses ML's domain discovery API to find the correct listing category
- **Attribute validation**: Fetches required attributes per category and fills them automatically
- **One-message listing**: Complete listing draft with title, price, description, and category in a single response
- **Live publishing**: Creates the listing on Mercado Libre via their API with the user's OAuth token
- **Webhook deduplication**: Prevents duplicate processing via idempotency keys
- **Background processing**: Async message handling to respect Kapso's 10-second webhook timeout
- **Stuck session recovery**: Automatically creates new agent sessions when previous ones get stuck

## Setup

### Prerequisites

- Docker and Docker Compose
- [Kapso](https://kapso.ai) account with a WhatsApp sandbox number
- [Anthropic](https://console.anthropic.com) API key
- [Mercado Libre](https://developers.mercadolibre.com.ar) developer app
- [ngrok](https://ngrok.com) for exposing the local server

### Environment Variables

```bash
cp .env.example .env
```

Fill in the following:

```env
# Database
POSTGRES_USER=hackathon
POSTGRES_PASSWORD=hackathon
POSTGRES_DB=hackathon

# Kapso (WhatsApp)
KAPSO_API_KEY=your_kapso_api_key
KAPSO_PHONE_NUMBER_ID=your_phone_number_id
KAPSO_WEBHOOK_SECRET=your_webhook_secret

# Anthropic (AI Agent)
ANTHROPIC_API_KEY=sk-ant-...

# MercadoLibre OAuth
ML_APP_ID=your_ml_app_id
ML_APP_SECRET=your_ml_app_secret
ML_REDIRECT_URI=https://your-ngrok.ngrok-free.dev/api/v1/auth/ml/callback
BACKEND_BASE_URL=https://your-ngrok.ngrok-free.dev
```

### Run

```bash
# Start all services
docker compose up -d

# Expose backend via ngrok
ngrok http 8000

# Register webhook in Kapso (replace URL with your ngrok URL)
curl -X POST https://api.kapso.ai/platform/v1/whatsapp/webhooks \
  -H "X-API-Key: $KAPSO_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "whatsapp_webhook": {
      "url": "https://your-ngrok.ngrok-free.dev/api/v1/webhook",
      "kind": "kapso",
      "events": ["whatsapp.message.received"],
      "secret_key": "your_secret",
      "active": true,
      "phone_number_id": "your_phone_number_id"
    }
  }'
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/webhook` | Kapso webhook receiver |
| GET | `/api/v1/auth/ml/callback` | MercadoLibre OAuth callback |
| POST | `/api/v1/onboarding/step` | Process onboarding step |
| GET | `/api/v1/onboarding/status/{phone}` | Get onboarding status |
| GET | `/api/v1/onboarding/users` | List all users (admin) |
| POST | `/api/v1/publications/` | Create publication |
| GET | `/api/v1/publications/` | List publications |
| PATCH | `/api/v1/publications/{id}/status` | Moderate publication |
| GET | `/health` | Health check |

## AI Agent Details

The publication agent uses Anthropic's **Managed Agents API** with:

- **Model**: Claude Haiku 4.5 (fast, cost-effective)
- **Built-in tools**: `web_search`, `web_fetch` (for price research)
- **Custom tools**:
  - `search_ml_category`: Predicts the correct Mercado Libre category
  - `get_category_attributes`: Fetches required/optional attributes for a category
  - `create_ml_listing`: Creates a live listing on Mercado Libre via their API

Sessions are persistent per user, allowing multi-turn conversations. The agent handles the complete flow from product identification to publishing.

## Built at Anthropic Hackathon 2026
