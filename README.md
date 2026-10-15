# Social Operations Hub V2

A clean, modern, and uncluttered SaaS platform for social media planning, composing, publishing simulation, and operational tracking.

---

## 1. Product Overview

Social Operations Hub V2 is built around a low cognitive load philosophy. It consolidates daily social operations into four core, un-nested operational views:

1. **Compose & Studio (`/compose`):** A distraction-free post editor with multi-network target toggles, platform character counters, and live preview cards for X (Twitter), LinkedIn, Instagram, and Facebook.
2. **Plan & Calendar (`/calendar`):** An interactive monthly and weekly visual schedule grid for drag-and-drop planning and schedule inspection.
3. **Queue & Pipeline (`/queue`):** A status pipeline (`Draft` -> `Scheduled` -> `Published` / `Failed`) with execution logs and immediate action triggers.
4. **Performance & Insights (`/insights`):** Essential operational KPI summaries (post volume, publishing velocity, platform distribution) without analytical clutter.

---

## 2. Core Architecture

The system employs a lean, progressive technology stack:

- **Frontend:** Next.js 15 (App Router), TypeScript, Tailwind CSS, Lucide icons.
- **Backend:** Python FastAPI (async), Pydantic v2 validation, SQLAlchemy 2.0 (async engine), Alembic database migrations.
- **Database:** PostgreSQL 16 for relational ACID integrity and JSONB platform metadata storage.
- **Simulation Engine:** Sandbox social publishing adapter (`SandboxSocialPublisher`) simulating network latency, character constraints, and mock platform IDs without requiring live social network credentials during initial phases.
- **Containers:** Docker Compose managing isolated application, API, and database services.

---

## 3. Repository Structure

```
social-operations-hub-v2/
├── backend/          # FastAPI backend service (endpoints, models, simulation engine)
├── frontend/         # Next.js 15 web application (4-pillar views and UI components)
├── docker/           # Docker Compose configuration and container definitions
├── .env.example      # Environment variables template with placeholder values
├── .gitignore        # Root gitignore excluding secrets, node_modules, and virtualenvs
└── README.md         # Project documentation and architecture guide
```

---

## 4. Getting Started

Detailed installation, local development instructions, and Docker startup commands will be introduced in subsequent milestones.
