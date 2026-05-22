import { initializeApp } from 'firebase/app'
import { getAnalytics, isSupported } from 'firebase/analytics'

let app = null
let analytics = null

/** Config baked in at Vite build (local .env). */
export function configFromImportMeta() {
  const apiKey = String(import.meta.env.VITE_FIREBASE_API_KEY ?? '').trim()
  if (!apiKey) return null
  const measurementId = String(import.meta.env.VITE_FIREBASE_MEASUREMENT_ID ?? '').trim()
  return {
    apiKey,
    authDomain: String(import.meta.env.VITE_FIREBASE_AUTH_DOMAIN ?? '').trim(),
    projectId: String(import.meta.env.VITE_FIREBASE_PROJECT_ID ?? '').trim(),
    storageBucket: String(import.meta.env.VITE_FIREBASE_STORAGE_BUCKET ?? '').trim(),
    messagingSenderId: String(import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID ?? '').trim(),
    appId: String(import.meta.env.VITE_FIREBASE_APP_ID ?? '').trim(),
    ...(measurementId ? { measurementId } : {}),
  }
}

export function initFirebase(config) {
  if (app) return app
  if (!config?.apiKey) {
    throw new Error('Firebase config is missing apiKey.')
  }
  app = initializeApp(config)
  if (typeof window !== 'undefined') {
    isSupported().then((supported) => {
      if (supported) analytics = getAnalytics(app)
    })
  }
  return app
}

export function getFirebaseApp() {
  if (!app) {
    throw new Error('Firebase has not been initialized yet.')
  }
  return app
}

export { analytics }
