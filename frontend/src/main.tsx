import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { configFromImportMeta, initFirebase } from './firebase.js'

function ConfigError({ message }: { message: string }) {
  return (
    <div
      style={{
        minHeight: '100vh',
        background: '#1e1b16',
        color: '#e8eaef',
        padding: '2rem',
        fontFamily: 'system-ui, Segoe UI, sans-serif',
        maxWidth: '40rem',
        margin: '0 auto',
      }}
    >
      <h1 style={{ color: '#facc15', marginTop: 0 }}>Friday Night Dynasty</h1>
      <p>Could not start the app:</p>
      <pre
        style={{
          background: '#2a2520',
          padding: '1rem',
          borderRadius: 8,
          whiteSpace: 'pre-wrap',
          fontSize: '0.9rem',
        }}
      >
        {message}
      </pre>
      <p style={{ color: '#9ca3af', fontSize: '0.9rem' }}>
        On Railway, set all <code>VITE_FIREBASE_*</code> variables on the service, redeploy, then open{' '}
        <code>/config/firebase.json</code> in the browser to confirm.
      </p>
    </div>
  )
}

async function loadFirebaseConfig(): Promise<Record<string, string>> {
  const baked = configFromImportMeta()
  if (baked) return baked
  const url = import.meta.env.DEV ? '/api/config/firebase.json' : '/config/firebase.json'
  const r = await fetch(url)
  if (!r.ok) {
    const text = await r.text()
    throw new Error(text || `Failed to load Firebase config (${r.status})`)
  }
  return r.json()
}

async function bootstrap() {
  const rootEl = document.getElementById('root')
  if (!rootEl) return

  let devNoFirebase = false
  try {
    const config = await loadFirebaseConfig()
    initFirebase(config)
  } catch (e: unknown) {
    const localHost =
      typeof window !== 'undefined' &&
      (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    if (import.meta.env.DEV || localHost) {
      // Local Vite dev or same-machine API (127.0.0.1): use /auth/dev-login when Firebase env is missing.
      devNoFirebase = true
    } else {
      const message = e instanceof Error ? e.message : String(e)
      createRoot(rootEl).render(<ConfigError message={message} />)
      return
    }
  }

  createRoot(rootEl).render(
    <StrictMode>
      <App devNoFirebase={devNoFirebase} />
    </StrictMode>,
  )
}

void bootstrap()
