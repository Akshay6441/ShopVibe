<h1 align="center">🛒 ShopVibe</h1>
<p align="center">A full-stack e-commerce platform with an AI-powered admin dashboard</p>

<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/React-20232A?style=flat&logo=react&logoColor=61DAFB" />
  <img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=flat&logo=postgresql&logoColor=white" />
  <img src="https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white" />
  <img src="https://img.shields.io/badge/GitHub_Actions-2088FF?style=flat&logo=githubactions&logoColor=white" />
</p>

---

## 📖 Overview

ShopVibe is a full-stack e-commerce application built to demonstrate production-style engineering practices — not just a CRUD storefront. It includes an AI agent embedded in the admin dashboard that can inspect orders, flag potential fraud, draft customer responses, and update order status autonomously.

## ✨ Key Features

- 🛍️ **Storefront** — product browsing, cart, and checkout flows
- 🔐 **Authentication** — Google OAuth 2.0 with JWT and CSRF-safe state handling
- 🤖 **AI Admin Agent** — tool-calling agent (Groq / Llama 3.3-70B) that can `get_order`, `flag_fraud`, `update_order_status`, `draft_response`, and `get_ticket`
- 🔄 **Salesforce Sync** — customer and order data synced to Salesforce via REST API on checkout
- 🧪 **CI/CD** — GitHub Actions pipeline with a coverage gate (~79% across 83 tests)
- 📊 **Observability** — Prometheus + Grafana dashboards for monitoring
- 🐳 **Containerized** — Docker Compose for local dev, deployable to Render

## 🏗️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, SQLAlchemy, Pydantic v2 |
| Database | PostgreSQL |
| Frontend | React 18, Zustand, Tailwind CSS |
| AI Agent | Groq (OpenAI-compatible API), Llama 3.3-70B-Versatile |
| Auth | Google OAuth 2.0, JWT |
| CRM | Salesforce REST API |
| Monitoring | Prometheus, Grafana |
| CI/CD | GitHub Actions |
| Deployment | Docker Compose, Render |

## 🚀 Getting Started

### Prerequisites
- Docker & Docker Compose
- Node.js 18+
- Python 3.11+

### Setup

```bash
# Clone the repo
git clone https://github.com/Akshay6441/ShopVibe.git
cd ShopVibe

# Copy environment variables
cp .env.example .env

# Start all services
docker compose up --build
```

The app will be available at `http://localhost:3000`, with the API at `http://localhost:8000`.

### Running Tests

```bash
pytest --cov=app tests/
```

## 📸 Screenshots

<!-- Add screenshots or a GIF of the storefront and admin dashboard here -->

## 🗺️ Architecture

<!-- Add an architecture diagram here if you have one, or a short description of how the FastAPI backend, React frontend, AI agent, and Salesforce sync interact -->

## 📄 License

This project is licensed under the MIT License.

## 📫 Contact

Built by [Akshay](https://github.com/Akshay6441) — [Portfolio](https://portfolio-henna-five-62.vercel.app) · [LinkedIn](https://linkedin.com/in/maddula-akshay) · [Email](mailto:maddulaakshay007@gmail.com)
