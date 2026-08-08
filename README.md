# ShopVibe — Full-Stack E-Commerce Platform

A production-ready e-commerce application built with **FastAPI** + **React** + **PostgreSQL**, containerized with Docker Compose.

Extended with real-world integrations:

- **Google OAuth 2.0** — "Continue with Google" social login
- **Salesforce REST** — sync customers & orders into a Salesforce org on checkout
- **Agentic AI** — an admin agent that reads orders/tickets and takes actions (flag fraud, update status, draft replies)
- **Observability** — Prometheus + Grafana dashboard, backend `/metrics` endpoint

---

## Quick Start

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running

### Run the full stack

```bash
docker compose up --build
```

| Service       | URL                                  |
|---------------|--------------------------------------|
| Shop          | http://localhost                     |
| API docs      | http://localhost:8001/api/docs       |
| Metrics       | http://localhost:8001/metrics        |
| Prometheus    | http://localhost:9090                |
| Grafana       | http://localhost:3001 (admin/admin)  |
| Database      | localhost:5432                       |

First boot seeds the database automatically with products, categories, and an admin account. Google OAuth, Salesforce, and the AI agent are **optional** — the app runs fine without them and they're activated as soon as their env vars are set.

---

## Demo Credentials

| Role  | Email             | Password   |
|-------|-------------------|------------|
| Admin | admin@shop.com    | admin123   |

Register any new account for a customer role.

---

## Features

### Frontend
- **Home** — Hero banner, category grid, featured products, promo banners, trust badges, newsletter
- **Shop** — URL-driven filters (category, price range, featured), search, sort, pagination
- **Product Detail** — Image gallery, star ratings, reviews, related products, qty stepper
- **Cart** — Guest + authenticated cart, qty management, order summary, free shipping threshold
- **Checkout** — 3-step flow: Shipping → Payment → Review & Place Order
- **Orders** — Collapsible order history with item details and status tracking
- **Profile** — Edit name/phone/address/avatar, account stats
- **Auth** — Email/password login & register, **"Continue with Google"** OAuth, JWT token management
- **Admin Dashboard** — Stats cards, full product CRUD, inline order status updates, **one-click Salesforce sync**, support tickets view/resolve, and an **AI Agent panel** (run + action log)

### Backend (FastAPI)
- JWT authentication (bcrypt passwords, 7-day tokens), Google OAuth 2.0
- Full CRUD: Products, Categories, Cart, Orders, Reviews, Support Tickets
- PostgreSQL via SQLAlchemy ORM, auto-seeded on first boot
- Paginated product listings with search, filter, sort
- Admin-only endpoints for products, orders, tickets, AI agent, Salesforce sync

---

## Integrations (optional — enable via env vars)

### 1. Google OAuth
1. Create a project in the [Google Cloud Console](https://console.cloud.google.com) → *APIs & Services* → *Credentials*.
2. Create an **OAuth 2.0 Client ID** (type: *Web application*).
3. Add an authorized redirect URI matching `GOOGLE_REDIRECT_URI` (e.g. `http://localhost:8001/api/auth/google/callback`).
4. Set in `backend/.env`:

```
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-...
GOOGLE_REDIRECT_URI=http://localhost:8001/api/auth/google/callback
FRONTEND_URL=http://localhost:3000
```

Flow: the login/register page's **Continue with Google** link → `/api/auth/google/login` → Google → callback exchanges the code, verifies the ID token, finds-or-creates the user, and redirects back to `/oauth/callback?token=<jwt>`. CSRF is protected with a signed `state` parameter.

### 2. Salesforce
Syncs every new order (and its customer) into a Salesforce **Contact + Order**, using the OAuth 2.0 JWT bearer flow.

1. In Salesforce, create a **Connected App** with *Use digital signatures* and upload a certificate (RSA key pair).
2. In the org, enable the connected app for your user and grant **API** access (also enable "Allow users to self-authorize" if using a simple setup).
3. Set in `backend/.env`:

```
SF_CLIENT_ID=3MVG9...          # Consumer Key
SF_CLIENT_SECRET=...           # Consumer Secret
SF_USERNAME=you@example.com    # a user that can use the app
SF_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----
SF_LOGIN_URL=https://login.salesforce.com
SF_INSTANCE_URL=               # optional override of the instance URL
```

Syncing is **best-effort** — failures are logged and never block checkout. You can also trigger a sync manually per order via `POST /api/admin/orders/{id}/sync-salesforce`.

### 3. Agentic AI
An admin-only agent (`POST /api/ai/agent`) that uses OpenAI function calling to read orders/tickets and take actions:

| Tool                    | Purpose                                   |
|-------------------------|-------------------------------------------|
| `get_order`             | Read order + items + payment              |
| `get_ticket`            | Read a support ticket + linked order      |
| `flag_fraud`            | Mark an order as suspicious (with reason) |
| `update_order_status`   | Advance/cancel an order                   |
| `draft_response`        | Draft a support reply for an order        |

```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

**Don't want to pay for OpenAI?** The code is OpenAI-compatible, so any free provider works via `OPENAI_BASE_URL`:

| Provider  | `OPENAI_BASE_URL`                            | `OPENAI_MODEL`                        |
|-----------|-----------------------------------------------|---------------------------------------|
| Groq      | `https://api.groq.com/openai/v1`              | `llama-3.3-70b-versatile`             |
| OpenRouter| `https://openrouter.ai/api/v1`                | `meta-llama/llama-3.3-70b-instruct:free` |
| Ollama (local, no key needed) | `http://host.docker.internal:11434/v1` | `llama3.1`                     |

All support function/tool calling, so the agent's tools work as-is. Leave `OPENAI_BASE_URL` empty to use the official OpenAI API.

Example: `POST /api/ai/agent` with `{"instruction": "Order #3 looks fraudulent — flag it and draft a reply to the customer"}`. The response returns the final reply plus the list of actions executed.

The admin dashboard (http://localhost/admin) has an **AI Agent** tab with a prompt box, example prompts, and a live log of the actions the agent took (plus a **Tickets** tab to view and resolve support tickets).

### 4. Monitoring
The backend exposes **Prometheus** metrics on `/metrics` (request counters + latency histograms via a Starlette middleware). The stack ships a pre-configured Prometheus scraping config and a Grafana instance:

```
GET /metrics          → Prometheus text format
http://localhost:9090 → Prometheus UI
http://localhost:3001 → Grafana (login admin/admin) — add a Prometheus datasource at http://prometheus:9090
```

---

## Tech Stack

| Layer     | Technology                                  |
|-----------|---------------------------------------------|
| Frontend  | React 18, React Router 6, Tailwind CSS      |
| State     | Zustand (cart/wishlist), React Context (auth) |
| HTTP      | Axios with JWT interceptor                  |
| Backend   | FastAPI, SQLAlchemy, Pydantic v2            |
| Auth      | python-jose (JWT), passlib (bcrypt), google-auth |
| Integrations | Salesforce REST (jwt-bearer), OpenAI       |
| Monitoring| prometheus-client, Prometheus, Grafana      |
| Database  | PostgreSQL 15                               |
| Server    | Nginx (gzip, caching, SPA fallback)         |
| Container | Docker Compose                              |

---

## Project Structure

```
├── backend/
│   ├── main.py            # FastAPI app + all routes
│   ├── models.py          # SQLAlchemy ORM models (User, Product, Order, SupportTicket, …)
│   ├── schemas.py         # Pydantic request/response schemas
│   ├── auth.py            # JWT + bcrypt helpers
│   ├── google_oauth.py    # Google OAuth 2.0 flow (state, token exchange, ID token verify)
│   ├── ai_agent.py        # OpenAI tool-calling agent for orders/tickets
│   ├── monitoring.py      # Prometheus metrics middleware + /metrics
│   ├── integrations/
│   │   └── salesforce.py  # Salesforce REST sync (JWT bearer)
│   ├── database.py        # DB engine + session
│   ├── seed.py            # Initial data seeder
│   ├── alembic/           # Schema migrations (002 = fraud flags + tickets)
│   ├── tests/             # pytest suite (83 tests, ~79% coverage)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/           # Axios API clients
│   │   ├── components/    # Layout + common UI components
│   │   ├── context/       # AuthContext (login/logout/OAuth)
│   │   ├── pages/         # Pages incl. OAuthCallbackPage
│   │   └── store/         # Zustand cart/wishlist stores
│   └── nginx.conf
├── monitoring/
│   └── prometheus.yml     # Scrape config for the backend
├── .github/workflows/ci.yml
└── compose.yaml
```

---

## Environment Variables

| Variable               | Default                                        | Description                  |
|------------------------|------------------------------------------------|------------------------------|
| DATABASE_URL           | postgresql://user:password@db:5432/mydatabase  | PostgreSQL URL               |
| SECRET_KEY             | change-me                                      | JWT signing secret           |
| APP_ENV                | development                                    | development / test / production |
| ALLOWED_ORIGINS        | http://localhost,http://localhost:3000         | CORS allow-list              |
| FRONTEND_URL           | http://localhost:3000                          | Redirect target after OAuth  |
| GOOGLE_CLIENT_ID       | *(empty)*                                      | Google OAuth client          |
| GOOGLE_CLIENT_SECRET   | *(empty)*                                      | Google OAuth secret          |
| GOOGLE_REDIRECT_URI    | http://localhost:8001/api/auth/google/callback | Registered redirect URI      |
| SF_CLIENT_ID           | *(empty)*                                      | Salesforce Consumer Key      |
| SF_CLIENT_SECRET       | *(empty)*                                      | Salesforce Consumer Secret   |
| SF_USERNAME            | *(empty)*                                      | Salesforce user              |
| SF_PRIVATE_KEY         | *(empty)*                                      | Salesforce RSA PEM key       |
| SF_LOGIN_URL           | https://login.salesforce.com                   | Salesforce login endpoint    |
| OPENAI_API_KEY         | *(empty)*                                      | OpenAI key for the AI agent  |
| OPENAI_MODEL           | gpt-4o-mini                                    | Model used by the agent      |
| OPENAI_BASE_URL        | *(empty)*                                      | OpenAI-compatible endpoint (e.g. Groq, OpenRouter, Ollama) |

**Change `SECRET_KEY` before deploying to production.** See `backend/.env.example` for the full list.

---

## Testing & Coverage

Backend tests run against SQLite locally or real PostgreSQL in CI.

```bash
cd backend
DATABASE_URL="sqlite:///./test.db" APP_ENV=test python -m pytest tests/ -q
```

Coverage is measured automatically (`pytest-cov` via `pytest.ini`/`.coveragerc`) and enforced at **70%** — the suite currently sits at ~79% across auth, OAuth, orders, tickets, salesforce, AI agent, and monitoring.

Frontend:

```bash
cd frontend
npm install
npm run build   # or: npm start
```

---

## CI / CD

`.github/workflows/ci.yml` runs on every push/PR:

1. **Backend** — ruff lint + pytest against a real PostgreSQL service container (with the coverage gate)
2. **Frontend** — production build
3. **Docker** — builds both images with BuildKit caching
4. **Deploy** — on pushes to `main`, triggers a **Render** webhook if `RENDER_DEPLOY_HOOK_URL` is set as a GitHub secret (create a Render Blueprint/webhook for your live demo and paste the hook URL into the repo secrets to enable auto-deploy)
