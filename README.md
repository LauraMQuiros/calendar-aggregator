# Calendar Aggregator

[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![React](https://img.shields.io/badge/React-61DAFB?style=flat&logo=react&logoColor=black)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-646CFF?style=flat&logo=vite&logoColor=white)](https://vitejs.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Web-based system that monitors event websites, extracts events via LLM, and exposes them through a REST API with a calendar UI.

## Project structure

```
calendar-aggregator/
├── backend/           # Python FastAPI API & extraction pipeline
├── frontend/          # React + Vite UI
├── tests/             # Backend tests
├── requirements.txt
└── package.json       # Root scripts (dev:all, dev:backend, dev)
```

## Run

```bash
# Install root deps (concurrently)
npm install

# Install frontend deps
npm run install:frontend

# Run backend (Python, port 8000) + frontend (Vite, port 8080) together
npm run dev:all
```

Or separately:
```bash
# Backend only
python -m backend.main

# Frontend only (in another terminal)
npm run dev
```

Backend: http://localhost:8000 | Docs: http://localhost:8000/docs  
Frontend: http://localhost:8080

## Backend setup

```bash
python -m venv venv
source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set `OLLAMA_MODEL=llama3.2` (or another model). Run `ollama pull llama3.2`.

## How to use

![Calendar Aggregator UI](./public/UI_example.png)

1. **Add websites** – Click **+ Add Website** in the left sidebar and enter a URL (e.g. an events page). The app will test connectivity before adding it.

2. **Extract events** – After adding a website, click the refresh icon next to it to scrape and extract events using the LLM. Events are stored and shown on the calendar.

3. **View the calendar** – The main panel shows a monthly calendar. Events appear as blue bars with time slots. Use **Today** and the arrow buttons to move between months.

4. **Event details** – Click an event on the calendar to open a modal with full details (time, location, description, source link).
