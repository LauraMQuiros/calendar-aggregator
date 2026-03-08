# Calendar Aggregator

Web-based system that monitors event websites, extracts events via LLM, deduplicates them, and exposes them through a REST API.

## Setup

```bash
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
```

Copy `.env.example` to `.env`. Configure a model (local preferred):

**Option A – Ollama (local, recommended)**  
1. Install [Ollama](https://ollama.com)  
2. `ollama pull llama3.2`  
3. In `.env`: `OLLAMA_MODEL=llama3.2`  

**Option B – Hugging Face transformers (local, no extra process)**  
- In `.env`: `USE_TRANSFORMERS=1`  
- `pip install transformers torch accelerate`  
- Model (~1–3GB) is downloaded on first run  

**Option C – Cloud APIs**  
- Set `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` in `.env`

## Run

```bash
python main.py
```

API: http://localhost:8000  
Docs: http://localhost:8000/docs

## Module Overview

| Module | Purpose |
|--------|---------|
| `scraper.py` | Fetches raw HTML from URLs (timeouts, retries, headers) |
| `cleaner.py` | Strips boilerplate with trafilatura/BeautifulSoup |
| `extractor.py` | Event extraction: local (Ollama, HF transformers) or cloud (Claude/OpenAI) |
| `deduplicator.py` | Fuzzy matching on title+date+location |
| `cache.py` | Content hash for change detection |
| `models.py` | DB models: Website, Folder, Event, ExtractionLog |
| `website_manager.py` | Add, validate, delete websites |
| `pipeline.py` | Orchestrates scraper → cleaner → cache → extractor → deduplicator |
| `scheduler.py` | APScheduler recurring extraction jobs |
| `api.py` | FastAPI REST endpoints |

## Event extraction (extractor.py)

The extractor turns cleaned page text into structured event records using an LLM. It is designed to work with local models (Ollama, Hugging Face transformers) or cloud APIs (Anthropic, OpenAI).

**Model order:** Ollama → Transformers → Anthropic → OpenAI. The first configured option is used (see Setup).

**Shortening the prompt (token limit):**

- **Stopword removal:** NLTK stopwords (English + Swedish) are removed from the text before sending to the LLM to reduce length. Month names (e.g. May, March) are kept so dates are preserved.
- **Event section only:** The text is trimmed to the “event” part of the page. The extractor looks for section headers like “Kommande evenemang”, “Upcoming events”, “Events”, “Calendar”, “Program”, etc., and keeps only that block. It stops at non-event sections (e.g. FAQ, Contact, About us) or phrases like “Load more” / “Läs in fler” so nav and footer are not sent.
- **Character cap for Ollama:** When using Ollama, the event-section text is further limited to `OLLAMA_MAX_TEXT_CHARS` (default **2500**). That keeps prompts small and fast for local models; cloud/transformers use a 50,000-character limit.

**Prompt and output:** The LLM is asked to return a JSON array of events with `title`, `date` (ISO preferred), optional `time`, `location`, `description`, and `source_url`. If the source is not in English, the prompt asks for translation and an `original_language` field. The extractor strips markdown code fences, repairs invalid `\uXXXX` escapes and broken JSON (via `json_repair`), and normalizes the list into a consistent event dict shape.

**Result:** A list of event dicts suitable for deduplication and storage.

## Tests

```bash
# Scraper + cleaner (no LLM required)
pytest tests/test_hands2ocean.py -v

# Full pipeline including event extraction (requires OLLAMA_MODEL, etc.)
OLLAMA_MODEL=llama3.2 pytest tests/test_hands2ocean.py -v
```

**Hands2Ocean test (`tests/test_hands2ocean.py`):** With the default Ollama setup, the full-pipeline test sends only the first part of the event section to the LLM (capped at `OLLAMA_MAX_TEXT_CHARS`, default 2500 characters). In practice this means **only the 4 most recent events** are extracted for that test. To get more events, increase `OLLAMA_MAX_TEXT_CHARS` (e.g. `OLLAMA_MAX_TEXT_CHARS=12000`) or use a cloud API (which uses a higher limit).

**Faster runs:** The full-pipeline test uses cached HTML (one fetch per test session) and sends only the event section to the LLM. For even faster Ollama inference, use a smaller model (e.g. `ollama pull llama3.2:1b`) or set `OLLAMA_NUM_CTX=4096` and `OLLAMA_MAX_TEXT_CHARS=12000` if you have enough RAM.

## API Endpoints

- `POST /websites` — Add website
- `GET /websites` — List websites
- `DELETE /websites/{id}` — Remove website
- `GET /events` — List events (optional `month`, `year`, `website_id`)
- `GET /calendar?month=&year=` — Events for a month
- `POST /websites/{id}/extract` — Trigger extraction
- `GET /websites/{id}/validate` — Test connectivity
- `GET /folders`, `POST /folders` — Folder management
