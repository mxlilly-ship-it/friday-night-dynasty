import { signOut } from 'firebase/auth'
import { login, signUp, auth } from './auth.js'
import { getOrCreateDeviceId } from './deviceId.js'

/**
 * Sign in with Firebase, then exchange ID token for app bearer token.
 * @param {string} apiBase
 * @param {{ email: string, password: string }} creds
 */
export async function firebaseLoginAndExchange(apiBase, { email, password }) {
  const cred = await login(email.trim(), password)
  return exchangeIdToken(apiBase, cred.user)
}

/**
 * Sign up with Firebase, then exchange ID token for app bearer token.
 */
export async function firebaseSignUpAndExchange(apiBase, { email, password }) {
  const cred = await signUp(email.trim(), password)
  return exchangeIdToken(apiBase, cred.user)
}

async function exchangeIdToken(apiBase, user) {
  const idToken = await user.getIdToken()
  const deviceId = getOrCreateDeviceId()
  const r = await fetch(`${apiBase}/auth/firebase`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id_token: idToken, device_id: deviceId }),
  })
  const text = await r.text()
  let data = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = null
  }
  if (!r.ok) {
    const detail = data?.detail
    const err = new Error(typeof detail === 'string' ? detail : formatDetail(detail) || `Login failed (${r.status})`)
    if (r.status === 403 && detail && typeof detail === 'object') {
      err.code = 'DEVICE_LIMIT'
      err.devices = detail.devices
      err.maxDevices = detail.max_devices
    }
    throw err
  }
  return data
}

function formatDetail(detail) {
  if (!detail) return ''
  if (typeof detail === 'string') return detail
  if (typeof detail.message === 'string') return detail.message
  return JSON.stringify(detail)
}

/** Remove a device while at the 3-device limit (uses fresh Firebase ID token). */
export async function firebaseRemoveDevice(apiBase, user, deviceId) {
  const idToken = await user.getIdToken()
  const r = await fetch(`${apiBase}/auth/firebase/remove-device`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id_token: idToken, device_id: deviceId }),
  })
  if (!r.ok) {
    const text = await r.text()
    let detail = text
    try {
      const j = JSON.parse(text)
      if (typeof j.detail === 'string') detail = j.detail
    } catch {
      /* ignore */
    }
    throw new Error(detail || `Remove device failed (${r.status})`)
  }
}

/**
 * If Firebase still has a signed-in user but the app bearer token was wiped (deploy),
 * exchange a fresh ID token for a new session without showing an error.
 * @param {string} apiBase
 * @returns {Promise<{ token: string, username?: string, email?: string } | null>}
 */
export async function tryRefreshAppSession(apiBase) {
  const user = auth.currentUser
  if (!user) return null
  try {
    return await exchangeIdToken(apiBase, user)
  } catch {
    return null
  }
}

export async function firebaseSignOut() {
  try {
    await signOut(auth)
  } catch {
    /* ignore */
  }
}
