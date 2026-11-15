# Health Prediction Application

A Python 3.11 foundation for a health prediction application. The backend is a
FastAPI REST API backed by SQLite and SQLAlchemy; the Streamlit frontend checks
the API and displays patient records. AI-generated remarks are intentionally
not implemented in this phase.

## Project layout

```text
backend/
  app/
    config.py                  Environment and application settings
    main.py                    FastAPI app, lifespan, and CORS
    database/
      connection.py            SQLAlchemy engine, session dependency, initialization
      models.py                Patient ORM model
    schemas/
      patient.py               Patient create, update, and response schemas
    routers/
      health.py                Database-aware health endpoint
      patients.py              Patient CRUD endpoints
    services/
      patient_service.py       Database operations and duplicate-email handling
    utils/
      validators.py            Shared patient-name validation
  tests/
    test_api.py                API health, CRUD, and validation tests
  requirements.txt             Backend dependencies
frontend/
  app.py                       Streamlit UI and backend HTTP client
  requirements.txt             Frontend dependencies
.env.example                   Environment variable names and local defaults
.gitignore                     Ignores credentials, databases, and Python artifacts
requirements.txt               Combined dependency install entry point
```

`components/` is reserved for future reusable Streamlit UI elements.

## Requirements and installation

Install Python 3.11, then from the project root create and activate a virtual
environment in PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

If PowerShell prevents environment activation, run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or invoke the
environment's Python directly as `.venv\Scripts\python.exe`.

The root requirements file combines the backend and frontend requirements.
For a smaller install, use `python -m pip install -r backend\requirements.txt`
or `python -m pip install -r frontend\requirements.txt`.

## Configuration and database

Set local settings in `.env`; do not commit that file. `.env.example` contains
only local defaults and placeholder configuration:

- `DATABASE_URL`: SQLAlchemy database URL. The default is local SQLite.
- `CORS_ORIGINS`: comma-separated allowed browser origins.
- `BACKEND_API_URL`: API base URL used by Streamlit.

The backend creates the configured database tables when the API starts.
With the default configuration, `health_prediction.db` is created at the
project root and persists patient records between runs. To initialize it
without starting the server, run from the project root:

```powershell
python -c "import sys; sys.path.insert(0, 'backend'); from app.database.connection import init_db; init_db()"
```

## Run the application

From the project root, start the backend:

```powershell
python -m uvicorn app.main:app --app-dir backend --reload
```

In another activated terminal, start Streamlit:

```powershell
streamlit run frontend/app.py
```

Open the Streamlit URL printed in the terminal (normally
`http://localhost:8501`). Its **Check backend connection** button calls
`GET /api/health`, and its Patients section calls `GET /api/patients`.
You can also view the interactive API docs at `http://127.0.0.1:8000/docs`
and check the health endpoint at `http://127.0.0.1:8000/api/health`.

Available patient routes are:

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Check API and database connectivity |
| POST | `/api/patients` | Create a patient |
| GET | `/api/patients` | List patients |
| GET | `/api/patients/{patient_id}` | Retrieve a patient |
| PUT | `/api/patients/{patient_id}` | Update provided patient fields |
| DELETE | `/api/patients/{patient_id}` | Delete a patient |

Patient email addresses are unique. Lab values are optional until entered and
must be non-negative with up to two decimal places. Patient create/update
responses use explicit Pydantic schemas; missing records return 404 and
duplicate emails return 409.

## Tests

From the project root:

```powershell
Push-Location backend
python -m pytest tests
Pop-Location
```

The tests use an isolated in-memory SQLite database and do not write patient
records into the application's local database.
