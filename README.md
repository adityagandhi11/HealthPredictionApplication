# Health Prediction System

A patient-record dashboard built with Streamlit, FastAPI, SQLAlchemy, and SQLite.
It validates patient data, stores records locally, and can request cautious,
informational remarks from the Groq API. It is an assessment/demo application,
not a clinical decision system.

## Features

- Patient create, list, search, detail, update, and confirmed delete.
- SQLite persistence and SQLAlchemy ORM.
- Validation for names, email, numeric values, supported date formats, and future
  dates.
- Duplicate name/email pairs are rejected (case-insensitive, ignoring surrounding whitespace).
- Optional Groq AI remarks, stored with an explicit `pending`, `generated`, or
  `failed` status; a provider outage never prevents the record being saved.
- Assessment test-data runner with exact supplied examples and per-case results.
- Focused API tests use in-memory SQLite and mocked AI behavior.

## Technology

Python 3.11+, FastAPI, Streamlit, SQLite, SQLAlchemy 2, Pydantic 2, HTTPX,
python-dotenv, Groq's OpenAI-compatible chat-completions API, and Pytest.

## Architecture

```text
Streamlit dashboard
        |
        v
FastAPI routers ----> Pydantic validation
        |
        +-----------> Patient service ----> Groq AI service ----> Groq API
        |
        +-----------> SQLAlchemy ORM ------> SQLite
        |
        v
Structured response to dashboard
```

The Groq credential is read only by the backend. The frontend calls FastAPI and
never receives or sends the key to the browser. AI remarks are generated after a
record is committed, so provider errors do not discard a valid patient record.
Only non-identifying DOB and lab values are sent to Groq; the patient's name and
email are not included.

## Project layout

```text
backend/
  app/
    config.py                  Environment settings
    main.py                    FastAPI app, lifecycle, CORS, error handlers
    database/
      connection.py            Engine, sessions, SQLite schema compatibility
      models.py                Patient ORM model
    schemas/
      patient.py               Input and response validation
    routers/
      health.py                Database-aware health endpoint
      patients.py              Patient CRUD and AI retry endpoints
    services/
      ai_service.py            Groq request and provider error handling
      patient_service.py       Database operations and AI status updates
    utils/
      validators.py            Shared name validation
  tests/
    test_api.py                CRUD, validation, assessment, and AI tests
  requirements.txt             Backend dependencies
frontend/
  app.py                       Dashboard, forms, patient management
  components/
    assessment_data.py         Exact assessment examples
  requirements.txt             Streamlit dependencies
.env.example                   Configuration names and safe local defaults
.gitignore                     Excludes secrets, databases, and build artifacts
requirements.txt               Combined dependencies
```

## Install

Install Python 3.11, then use PowerShell from the project root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

If PowerShell prevents venv activation, run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or call
`.venv\Scripts\python.exe` and `.venv\Scripts\streamlit.exe` directly.

To install only one side, use
`python -m pip install -r backend\requirements.txt` or
`python -m pip install -r frontend\requirements.txt`.

## Configuration

Edit `.env` in the project root. It is ignored by Git; do not commit it.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy URL; defaults to a project-root SQLite database |
| `CORS_ORIGINS` | Comma-separated browser origins for local development |
| `BACKEND_API_URL` | FastAPI base URL used by Streamlit |
| `GROQ_API_KEY` | Groq API key; keep private and only set on the backend host |
| `GROQ_MODEL` | Groq model name; defaults to `llama-3.3-70b-versatile` |
| `GROQ_API_URL` | OpenAI-compatible Groq chat-completions URL |

The `.env.example` key is intentionally blank. Set it in `.env` to a
Groq-issued key to enable analysis. Without a key, patient CRUD still works and
remarks show as pending. Do not paste API keys into source code, issues, or
screenshots.

## Database

On backend startup, missing tables are created. The default database is
`health_prediction.db` in the project root. For manual initialization:

```powershell
python -c "import sys; sys.path.insert(0, 'backend'); from app.database.connection import init_db; init_db()"
```

The startup routine also upgrades an earlier SQLite scaffold by adding the AI
status column, removing its old unique-email index, and adding SQLite guards
that prevent new duplicate name/email pairs without deleting existing records.
Matching ignores case and surrounding whitespace.

## Run

Start FastAPI from the project root:

```powershell
python -m uvicorn app.main:app --app-dir backend --reload
```

Start Streamlit in another activated terminal:

```powershell
streamlit run frontend/app.py
```

Open the printed Streamlit URL (usually `http://localhost:8501`). API docs are
at `http://127.0.0.1:8000/docs`; database-aware health is at
`http://127.0.0.1:8000/api/health`.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Check API and database connectivity |
| POST | `/api/patients` | Validate, save, and attempt AI remarks generation |
| GET | `/api/patients` | List records, including AI status and remarks |
| GET | `/api/patients/{patient_id}` | Get one record; 404 if missing |
| PUT | `/api/patients/{patient_id}` | Update provided fields; refresh remarks when DOB/labs change |
| POST | `/api/patients/{patient_id}/remarks` | Retry AI remarks explicitly |
| DELETE | `/api/patients/{patient_id}` | Delete one record; 404 if missing |

Create and update accept `dd/mm/yyyy`, `dd.mm.yyyy`, and ISO date input. Dates
are stored as SQL `DATE` values and returned as ISO dates. The UI displays
`dd/mm/yyyy`. Names and emails are trimmed; malformed emails, impossible dates,
future DOBs, negative measurements, NaN, and infinity are rejected. Measurements
are not assigned units or clinical ranges by the application.

AI status is `generated` only when a valid provider response is stored.
Unavailable/unconfigured AI produces a `pending`/`failed` status and no
success-shaped remarks. Retry failures return a readable 503 response.

## Assessment workflow

Open **Assessment data**, review the ten supplied cases, confirm the database
write, and run them through the actual API. Results report each accepted or
rejected case. Cases 2 (malformed email), 4 (impossible date), and 8 (future
date and malformed email) should be rejected. Case 6 is rejected when case 1
has already been saved because both have the same name/email pair. The
remaining six are valid. The assessment page is a test
harness; dashboard records are always fetched from SQLite.

For the CRUD demonstration:

1. Open **Patient records**, edit a saved record's email to
   `gokul@infocare.com`, save, and verify it in the refreshed table.
2. Use **Delete patient**, then **Confirm delete**, and verify the row is gone.
3. Use **Retry AI remarks** for pending/failed analyses after configuring Groq.

The assessment runner writes to the configured database. It prevents saving
duplicate patient name/email pairs, including when a batch is run more than once.

## Tests

```powershell
Push-Location backend
python -m pytest tests
Pop-Location
```

Tests isolate storage in an in-memory SQLite database and mock Groq responses;
they require no API key or API credits.


## Limitations and medical disclaimer

The app does not know test units, lab reference ranges, symptoms, medical
history, or a patient's full clinical context. AI remarks may be incomplete or
incorrect. They are informational only, are not a diagnosis, and must not be
used to make treatment decisions. A qualified healthcare professional should
interpret results.

The initial SQLite schema helper handles the previous scaffold's email index
and AI-status column. For a deployed application with ongoing schema evolution,
use a migration tool such as Alembic and an appropriately secured database.
