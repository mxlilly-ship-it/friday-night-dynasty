@echo off
cd /d "%~dp0"
echo Starting API on http://127.0.0.1:8000
echo Open http://127.0.0.1:8000/teams-data to test teams
echo Open http://127.0.0.1:8000/health to check API
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
