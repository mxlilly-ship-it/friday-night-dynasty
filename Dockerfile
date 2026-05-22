FROM node:20-bookworm AS frontend-build
WORKDIR /app/frontend
# Firebase web config: loaded at runtime from /config/firebase.json (Railway VITE_* vars).
# Optional: set VITE_FIREBASE_* at build for faster startup; not required.
COPY frontend/package*.json ./
RUN npm ci
COPY frontend ./
RUN npx vite build

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8080 \
    FND_IGNORE_STALE_SPA=1
# Production: mount a Railway volume at /data and set FND_DATA_DIR=/data (see docs/RAILWAY_PERSISTENCE.md).
WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY . .
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

EXPOSE 8080
CMD ["sh", "-c", "python -m uvicorn backend.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
