import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev: browser calls /api/* → Vite forwards to FastAPI (same origin = fewer CORS issues).
// Run API: python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
// Playoffs: POST /saves/{id}/playoffs/sim-round (one round) or /playoffs/sim (full bracket)
const apiProxy = {
  '/api': {
    // Override with: set VITE_API_PROXY_TARGET=http://127.0.0.1:PORT
    target: process.env.VITE_API_PROXY_TARGET ?? 'http://127.0.0.1:8000',
    changeOrigin: true,
    rewrite: (path: string) => path.replace(/^\/api/, ''),
  },
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: { ...apiProxy },
  },
  preview: {
    host: '127.0.0.1',
    port: 5173,
    proxy: { ...apiProxy },
  },
})
