@echo off
echo Starting FastAPI Backend on http://127.0.0.1:8000 ...
IF EXIST ".\.venv\Scripts\python.exe" (
    .\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
) ELSE (
    python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
)

