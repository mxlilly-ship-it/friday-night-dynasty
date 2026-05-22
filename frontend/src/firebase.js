import { initializeApp } from 'firebase/app'
import { getAnalytics, isSupported } from 'firebase/analytics'

/** Firebase web config from env (never commit real keys — see frontend/.env.example). */
function env(name) {
  const v = String(import.meta.env[name] ?? '').trim()
  if (!v) {
    throw new Error(
      `Missing ${name}. Copy frontend/.env.example to frontend/.env for local dev, ` +
        'or set VITE_FIREBASE_* variables on Railway before deploy.',
    )
  }
  return v
}

const measurementId = String(import.meta.env.VITE_FIREBASE_MEASUREMENT_ID ?? '').trim()

const firebaseConfig = {
  apiKey: env('VITE_FIREBASE_API_KEY'),
  authDomain: env('VITE_FIREBASE_AUTH_DOMAIN'),
  projectId: env('VITE_FIREBASE_PROJECT_ID'),
  storageBucket: env('VITE_FIREBASE_STORAGE_BUCKET'),
  messagingSenderId: env('VITE_FIREBASE_MESSAGING_SENDER_ID'),
  appId: env('VITE_FIREBASE_APP_ID'),
  ...(measurementId ? { measurementId } : {}),
}

const app = initializeApp(firebaseConfig)

/** Analytics only in the browser (Vite dev/build); null during SSR/tests. */
let analytics = null
if (typeof window !== 'undefined') {
  isSupported().then((supported) => {
    if (supported) analytics = getAnalytics(app)
  })
}

export { analytics }
export default app
