import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import './index.css'
import './TitleScreen.css'
import { NewSaveFlow } from './NewSaveFlow'
import TeamHomePage from './TeamHomePage'
import type { HomeThemeSelection } from './homeGameThemes'
import { deriveUiPhaseFromSave, shouldBeginOffseason } from './seasonPhase'
import { importSaveZip, type SaveBundle } from './saveBundle'
import { downloadBackupJson, downloadBackupZip } from './backupDownload'
import {
  createBrowserSaveId,
  deleteBrowserSave,
  getBrowserSave,
  isBrowserSaveId,
  listBrowserSaves,
  putBrowserSave,
  readLatestAutosave,
  writeLatestAutosave,
  type BrowserAutosaveRecord,
} from './browserSave'
import { enrichSaveStateFromLeagueJson } from './leagueTeamStatic'
import { LocalAssetsProvider } from './LocalAssetsContext'
import {
  firebaseLoginAndExchange,
  firebaseRemoveDevice,
  firebaseSignOut,
  firebaseSignUpAndExchange,
  tryRefreshAppSession,
} from './authSession.js'
import { getAuthInstance, resetPassword } from './auth.js'
import SignupTermsConsent from './SignupTermsConsent'
import ScreenshotsGallery from './ScreenshotsGallery'
import { getOrCreateDeviceId } from './deviceId.js'
import { confirmCheckoutSession, createCheckoutSession, fetchBillingStatus, type BillingStatus } from './billing'

/** Stable reference so child effects do not re-run when logged out (browser saves). */
const EMPTY_AUTH_HEADERS: Record<string, string> = Object.freeze({})

/** In dev, use Vite proxy (/api → backend). Production: set VITE_API_BASE or default below. */
/** Dev: Vite proxy. Production build served from the same host as FastAPI → empty string (same-origin). */
const API_BASE = import.meta.env.DEV
  ? '/api'
  : ((import.meta as any).env?.VITE_API_BASE ?? '')

/** Tokens live in the server DB; redeploys / new DB invalidate old browser tokens. */
const STALE_SESSION_MSG =
  'Your session expired after a server update. Sign in again with your email and password.'

async function formatApiErrorBody(r: Response): Promise<string> {
  const raw = await r.text()
  const fallback = `Request failed (${r.status})`
  try {
    const j = JSON.parse(raw) as { detail?: unknown }
    const d = j.detail
    if (typeof d === 'string') {
      const trimmed = d.trim()
      if (trimmed && trimmed.toLowerCase() !== 'none') return trimmed
    }
    if (Array.isArray(d))
      return d.map((x: any) => (typeof x?.msg === 'string' ? x.msg : JSON.stringify(x))).join('; ')
  } catch {
    /* use raw */
  }
  const trimmedRaw = raw.trim()
  return trimmedRaw && trimmedRaw.toLowerCase() !== 'none' ? trimmedRaw : fallback
}

function apiConnectionHint() {
  return ' Start the API: python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000'
}

/** True when save JSON still has preseason stages to complete (even if season_phase is missing or wrong). */
function saveHasActivePreseasonFlow(state: any): boolean {
  const stages = state?.preseason_stages
  const idx = Number(state?.preseason_stage_index ?? 0)
  if (!Array.isArray(stages) || stages.length === 0) return false
  if (idx >= stages.length) return false
  const p = String(state?.season_phase ?? '').toLowerCase()
  if (p === 'playoffs' || p === 'season_summary' || p === 'schedule_planning' || p === 'offseason' || p === 'done') return false
  return true
}

/** Index has moved past the last preseason stage — regular season should use /week/sim, not /preseason/advance. */
function preseasonStructurallyComplete(state: any): boolean {
  const stages = state?.preseason_stages
  const idx = Number(state?.preseason_stage_index ?? 0)
  return Array.isArray(stages) && stages.length > 0 && idx >= stages.length
}

type SaveListItem = { save_id: string; save_name: string; updated_at: number }
type Screen = 'title' | 'load' | 'new' | 'playing'
type BackupReminderFrequency = 'none' | '3_weeks' | '6_weeks' | 'stage'
type CloudSaveListItem = { save_id: string; save_name: string; updated_at: number }

type AppProps = {
  /** Vite dev without Firebase env — use POST /auth/dev-login instead of email/password. */
  devNoFirebase?: boolean
}

export default function App({ devNoFirebase = false }: AppProps) {
  const [token, setToken] = useState<string>(() => localStorage.getItem('fnd_token') ?? '')
  const [username, setUsername] = useState(() => localStorage.getItem('fnd_username') ?? '')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [authBusy, setAuthBusy] = useState(false)
  const [resetPasswordBusy, setResetPasswordBusy] = useState(false)
  const [authMode, setAuthMode] = useState<'login' | 'signup'>('login')
  const [termsAccepted, setTermsAccepted] = useState(false)
  const [deviceLimitDevices, setDeviceLimitDevices] = useState<
    Array<{ device_id: string; label?: string | null; last_seen_at?: number }>
  >([])
  const [screen, setScreen] = useState<Screen>('title')
  const [showScreenshotsGallery, setShowScreenshotsGallery] = useState(false)
  const [saves, setSaves] = useState<SaveListItem[]>([])
  const [cloudSaves, setCloudSaves] = useState<CloudSaveListItem[]>([])
  const [saveId, setSaveId] = useState<string>('')
  const [saveState, setSaveState] = useState<any>(null)
  const [dynastyLeagueHistory, setDynastyLeagueHistory] = useState<{ seasons?: unknown[] }>({ seasons: [] })
  const [localBundle, setLocalBundle] = useState<SaveBundle | null>(null)
  const [error, setError] = useState<string>('')
  const [crashReportText, setCrashReportText] = useState<string>('')
  const [lastCrashPromptKey, setLastCrashPromptKey] = useState<string>('')
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string>('')
  const [billingStatus, setBillingStatus] = useState<BillingStatus | null>(null)
  const [billingChecking, setBillingChecking] = useState(false)
  const [billingBusy, setBillingBusy] = useState(false)
  const [autosaveEnabled, setAutosaveEnabled] = useState<boolean>(() => {
    const raw = localStorage.getItem('fnd_autosave_enabled')
    return raw == null ? true : raw === 'true'
  })
  const [lastAutosaveAt, setLastAutosaveAt] = useState<number | null>(null)
  const [backupReminderFrequency, setBackupReminderFrequency] = useState<BackupReminderFrequency>(() => {
    const raw = localStorage.getItem('fnd_backup_reminder_frequency')
    if (raw === '3_weeks' || raw === '6_weeks' || raw === 'stage' || raw === 'none') return raw
    return 'none'
  })
  const [showBackupPrompt, setShowBackupPrompt] = useState(false)
  const [backupPromptReason, setBackupPromptReason] = useState('')
  const inLocalRuntime = Boolean(localBundle) && isBrowserSaveId(saveId)
  const needsBillingPurchase = Boolean(
    billingStatus?.billing_required && !billingStatus?.entitled,
  )

  const saveStateRef = useRef<any>(null)
  saveStateRef.current = saveState
  const scheduleBrowserPersistRef = useRef<(() => void) | null>(null)

  /** Apply API simulation payload immediately (ref + React state) so back-to-back simWeek() calls stay in sync. */
  const applySimulationState = useCallback(
    (nextState: any, data?: { league_history?: unknown; records?: unknown; season_recaps?: Record<string, string> }) => {
      if (nextState === undefined || nextState === null) return
      maybeTriggerBackupReminder(saveStateRef.current, nextState)
      saveStateRef.current = nextState
      setSaveState(nextState)
      if (localBundle) {
        setLocalBundle((prev) => {
          if (!prev) return prev
          return {
            ...prev,
            state: nextState,
            leagueHistory:
              data?.league_history !== undefined && data?.league_history !== null
                ? (data.league_history as typeof prev.leagueHistory)
                : prev.leagueHistory,
            records:
              data?.records !== undefined && data?.records !== null
                ? (data.records as typeof prev.records)
                : prev.records,
            seasonRecaps: data?.season_recaps
              ? { ...(prev.seasonRecaps ?? {}), ...data.season_recaps }
              : prev.seasonRecaps,
          }
        })
      }
      scheduleBrowserPersistRef.current?.()
    },
    [localBundle],
  )

  const patchSaveState = useCallback(
    (nextState: unknown) => {
      if (nextState === undefined || nextState === null) return
      if (inLocalRuntime) {
        applySimulationState(nextState as any)
      } else {
        saveStateRef.current = nextState
        setSaveState(nextState)
      }
    },
    [inLocalRuntime, applySimulationState],
  )

  const getCurrentBundle = useCallback((): SaveBundle | null => {
    const live = saveStateRef.current
    if (!live) return null
    if (localBundle) return { ...localBundle, state: live }
    return {
      state: live,
      leagueHistory: dynastyLeagueHistory ?? { seasons: [] },
      records: {},
      logos: {},
      stadiums: {},
      helmets: {},
      jerseys: {},
      seasonRecaps: {},
    }
  }, [localBundle, dynastyLeagueHistory])

  const persistCurrentBrowserSave = useCallback(async () => {
    if (!localBundle) return
    const live = saveStateRef.current
    if (!live) return
    let id = saveId.startsWith('b_') ? saveId : createBrowserSaveId()
    if (saveId === '__local__' || !saveId) {
      setSaveId(id)
    }
    const saveName = String(live?.save_name ?? localBundle.state?.save_name ?? 'Dynasty').trim() || 'Dynasty'
    await putBrowserSave({
      id,
      saveName,
      updatedAt: Date.now(),
      bundle: { ...localBundle, state: live },
    })
  }, [saveId, localBundle])

  useEffect(() => {
    scheduleBrowserPersistRef.current = () => {
      if (!localBundle || !saveId) return
      void persistCurrentBrowserSave()
    }
  }, [localBundle, saveId, persistCurrentBrowserSave])

  const headers = useMemo((): Record<string, string> => {
    if (!token) return EMPTY_AUTH_HEADERS
    return { Authorization: `Bearer ${token}` }
  }, [token])

  const importLogosToBundle = useCallback(
    async (newLogos: SaveBundle['logos']) => {
      const live = saveStateRef.current
      setLocalBundle((prev) => {
        if (!prev) return prev
        const next: SaveBundle = {
          ...prev,
          logos: { ...(prev.logos ?? {}), ...newLogos },
          state: live ?? prev.state,
        }
        let id = saveId.startsWith('b_') ? saveId : createBrowserSaveId()
        if (!saveId.startsWith('b_')) {
          setSaveId(id)
        }
        const saveName = String((live ?? prev.state)?.save_name ?? 'Dynasty').trim() || 'Dynasty'
        void putBrowserSave({
          id,
          saveName,
          updatedAt: Date.now(),
          bundle: next,
        }).catch((e: unknown) =>
          setError(e instanceof Error ? e.message : 'Failed to save logos to browser'),
        )
        return next
      })
    },
    [saveId],
  )

  const importStadiumsToBundle = useCallback(
    async (newStadiums: SaveBundle['stadiums']) => {
      const live = saveStateRef.current
      setLocalBundle((prev) => {
        if (!prev) return prev
        const next: SaveBundle = {
          ...prev,
          stadiums: { ...(prev.stadiums ?? {}), ...newStadiums },
          state: live ?? prev.state,
        }
        let id = saveId.startsWith('b_') ? saveId : createBrowserSaveId()
        if (!saveId.startsWith('b_')) {
          setSaveId(id)
        }
        const saveName = String((live ?? prev.state)?.save_name ?? 'Dynasty').trim() || 'Dynasty'
        void putBrowserSave({
          id,
          saveName,
          updatedAt: Date.now(),
          bundle: next,
        }).catch((e: unknown) =>
          setError(e instanceof Error ? e.message : 'Failed to save stadium photos to browser'),
        )
        return next
      })
    },
    [saveId],
  )

  const importHelmetsToBundle = useCallback(
    async (newHelmets: SaveBundle['helmets']) => {
      const live = saveStateRef.current
      setLocalBundle((prev) => {
        if (!prev) return prev
        const next: SaveBundle = {
          ...prev,
          helmets: { ...(prev.helmets ?? {}), ...newHelmets },
          state: live ?? prev.state,
        }
        let id = saveId.startsWith('b_') ? saveId : createBrowserSaveId()
        if (!saveId.startsWith('b_')) {
          setSaveId(id)
        }
        const saveName = String((live ?? prev.state)?.save_name ?? 'Dynasty').trim() || 'Dynasty'
        void putBrowserSave({
          id,
          saveName,
          updatedAt: Date.now(),
          bundle: next,
        }).catch((e: unknown) =>
          setError(e instanceof Error ? e.message : 'Failed to save helmets to browser'),
        )
        return next
      })
    },
    [saveId],
  )

  const importJerseysToBundle = useCallback(
    async (newJerseys: SaveBundle['jerseys']) => {
      const live = saveStateRef.current
      setLocalBundle((prev) => {
        if (!prev) return prev
        const next: SaveBundle = {
          ...prev,
          jerseys: { ...(prev.jerseys ?? {}), ...newJerseys },
          state: live ?? prev.state,
        }
        let id = saveId.startsWith('b_') ? saveId : createBrowserSaveId()
        if (!saveId.startsWith('b_')) {
          setSaveId(id)
        }
        const saveName = String((live ?? prev.state)?.save_name ?? 'Dynasty').trim() || 'Dynasty'
        void putBrowserSave({
          id,
          saveName,
          updatedAt: Date.now(),
          bundle: next,
        }).catch((e: unknown) =>
          setError(e instanceof Error ? e.message : 'Failed to save jerseys to browser'),
        )
        return next
      })
    },
    [saveId],
  )

  const mergeLocalSimulationResult = useCallback(
    (data: {
      state?: unknown
      league_history?: unknown
      records?: unknown
      season_recaps?: Record<string, string>
    }) => {
      if (data?.state !== undefined && data?.state !== null) {
        applySimulationState(data.state as any, data)
      } else if (data?.league_history || data?.records || data?.season_recaps) {
        setLocalBundle((prev) => {
          if (!prev) return prev
          return {
            ...prev,
            leagueHistory:
              data.league_history !== undefined && data.league_history !== null
                ? data.league_history
                : prev.leagueHistory,
            records:
              data.records !== undefined && data.records !== null ? data.records : prev.records,
            seasonRecaps: data.season_recaps ? { ...(prev.seasonRecaps ?? {}), ...data.season_recaps } : prev.seasonRecaps,
          }
        })
      }
    },
    [applySimulationState],
  )

  function clearStaleSession() {
    localStorage.removeItem('fnd_token')
    localStorage.removeItem('fnd_username')
    setToken('')
    setBillingStatus(null)
    void firebaseSignOut()
  }

  function expireSession(message: string = STALE_SESSION_MSG) {
    clearStaleSession()
    setError(message)
  }

  async function validateSession(currentToken?: string): Promise<boolean> {
    const t = (currentToken ?? token).trim()
    if (!t) return false
    try {
      const r = await fetch(`${API_BASE}/auth/session`, {
        headers: { Authorization: `Bearer ${t}` },
      })
      if (r.ok) return true
    } catch {
      /* try Firebase refresh below */
    }
    const refreshed = await tryRefreshAppSession(API_BASE)
    if (refreshed?.token) {
      applySession(refreshed)
      return true
    }
    return false
  }

  /** Fresh bearer headers for protected API calls. */
  async function getAuthHeaders(): Promise<Record<string, string>> {
    const stored = (localStorage.getItem('fnd_token') ?? token).trim()
    if (stored && (await validateSession(stored))) {
      const live = (localStorage.getItem('fnd_token') ?? token).trim()
      return live ? { Authorization: `Bearer ${live}` } : {}
    }
    if (stored) expireSession()
    return {}
  }

  function applySession(data: { token: string; username?: string; email?: string }) {
    localStorage.setItem('fnd_token', data.token)
    setToken(data.token)
    const label = String(data.username || data.email || '').trim()
    if (label) {
      localStorage.setItem('fnd_username', label)
      setUsername(label)
    }
    void refreshBillingStatus({ Authorization: `Bearer ${data.token}` })
  }

  async function refreshBillingStatus(authHeaders?: Record<string, string>) {
    const auth =
      authHeaders ??
      (token.trim() ? { Authorization: `Bearer ${token.trim()}` } : null)
    if (!auth?.Authorization) {
      setBillingStatus(null)
      return null
    }
    setBillingChecking(true)
    try {
      const status = await fetchBillingStatus(API_BASE, auth)
      setBillingStatus(status)
      return status
    } catch {
      setBillingStatus(null)
      return null
    } finally {
      setBillingChecking(false)
    }
  }

  async function startCheckout() {
    setError('')
    setBillingBusy(true)
    try {
      const auth = await getAuthHeaders()
      if (!auth.Authorization) {
        setError('Sign in first, then complete checkout.')
        return
      }
      const url = await createCheckoutSession(API_BASE, auth)
      window.location.href = url
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Could not start checkout'
      setError(msg)
    } finally {
      setBillingBusy(false)
    }
  }

  async function removeRegisteredDevice(deviceId: string) {
    setError('')
    try {
      const user = getAuthInstance().currentUser
      if (!user) {
        setError('Sign in with Firebase first (enter email/password), then remove a device.')
        return
      }
      await firebaseRemoveDevice(API_BASE, user, deviceId)
      setDeviceLimitDevices((prev) => prev.filter((d) => d.device_id !== deviceId))
      setSuccessMessage('Device removed. Tap Log in again.')
      setTimeout(() => setSuccessMessage(''), 4000)
    } catch (e: any) {
      setError(e?.message ? String(e.message) : 'Could not remove device')
    }
  }

  async function devAuthSubmit(coachLabel?: string) {
    setError('')
    const name = (coachLabel ?? username).trim()
    if (!name) {
      setError('Enter a coach name.')
      return false
    }
    setAuthBusy(true)
    try {
      const r = await fetch(`${API_BASE}/auth/dev-login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: name }),
      })
      if (!r.ok) {
        setError(await formatApiErrorBody(r))
        return false
      }
      const data = (await r.json()) as { token: string; user_id: string }
      applySession({ token: data.token, username: name })
      return true
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Dev login failed'
      setError(`${msg}.${apiConnectionHint()}`)
      return false
    } finally {
      setAuthBusy(false)
    }
  }

  async function firebaseAuthSubmit(mode: 'login' | 'signup') {
    setError('')
    setDeviceLimitDevices([])
    const em = email.trim()
    if (!em || !password) {
      setError('Enter email and password.')
      return false
    }
    if (mode === 'signup' && !termsAccepted) {
      setError('You must agree to the Terms of Service and Privacy Policy.')
      return false
    }
    setAuthBusy(true)
    try {
      const data =
        mode === 'signup'
          ? await firebaseSignUpAndExchange(API_BASE, { email: em, password })
          : await firebaseLoginAndExchange(API_BASE, { email: em, password })
      applySession(data)
      return true
    } catch (e: any) {
      return handleFirebaseAuthError(e)
    } finally {
      setAuthBusy(false)
    }
  }

  function handleFirebaseAuthError(e: any): false {
    if (e?.code === 'DEVICE_LIMIT' && Array.isArray(e.devices)) {
      setDeviceLimitDevices(e.devices)
      setError(
        `This account is already on 3 devices. Remove one below, then sign in again. (This browser: ${getOrCreateDeviceId().slice(0, 8)}…)`,
      )
      return false
    }
    const msg = e?.message ? String(e.message) : 'Sign in failed'
    setError(
      msg.toLowerCase().includes('fetch') || msg.toLowerCase().includes('network')
        ? `Sign in failed (${msg}).${apiConnectionHint()}`
        : msg,
    )
    return false
  }

  async function handleForgotPassword() {
    setError('')
    setSuccessMessage('')
    const em = email.trim()
    if (!em) {
      setError('Enter your email address, then tap Forgot Password.')
      return
    }
    setResetPasswordBusy(true)
    try {
      await resetPassword(em)
      setSuccessMessage(`Password reset email sent to ${em}. Check your inbox (and spam folder).`)
      setTimeout(() => setSuccessMessage(''), 6000)
    } catch (e: any) {
      const code = String(e?.code ?? '')
      if (code === 'auth/invalid-email') {
        setError('Enter a valid email address.')
      } else if (code === 'auth/missing-email') {
        setError('Enter your email address first.')
      } else if (code === 'auth/user-not-found') {
        setError('No account found for that email.')
      } else if (code === 'auth/too-many-requests') {
        setError('Too many reset attempts. Wait a few minutes and try again.')
      } else {
        const msg = e?.message ? String(e.message) : 'Could not send reset email.'
        setError(msg)
      }
    } finally {
      setResetPasswordBusy(false)
    }
  }

  /** If response is 401, try Firebase re-login once; else expire session. Returns true = caller should stop. */
  async function consumeUnauthorized(r: Response): Promise<boolean> {
    if (r.status !== 401) return false
    const refreshed = await tryRefreshAppSession(API_BASE)
    if (refreshed?.token) {
      applySession(refreshed)
      return false
    }
    expireSession()
    return true
  }

  function downloadText(filename: string, text: string) {
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 250)
  }

  function buildCrashReport(message: string): string {
    const live = saveStateRef.current
    const now = new Date().toISOString()
    const context = {
      generated_at: now,
      screen,
      save_id: saveId || '(none)',
      season_phase: String(live?.season_phase ?? ''),
      current_week: Number(live?.current_week ?? 0),
      current_year: Number(live?.current_year ?? 0),
      preseason_stage_index: Number(live?.preseason_stage_index ?? -1),
      offseason_stage_index: Number(live?.offseason_stage_index ?? -1),
      user_team: String(live?.user_team ?? ''),
      url: typeof window !== 'undefined' ? window.location.href : '',
      user_agent: typeof navigator !== 'undefined' ? navigator.userAgent : '',
    }
    return [
      'Friday Night Dynasty Crash Report',
      '================================',
      '',
      'Error Message',
      '-------------',
      message,
      '',
      'Context',
      '-------',
      JSON.stringify(context, null, 2),
      '',
    ].join('\n')
  }

  function downloadCrashReportNow() {
    if (!crashReportText) return
    const stamp = new Date().toISOString().replace(/[:.]/g, '-')
    downloadText(`fnd_crash_report_${stamp}.txt`, crashReportText)
  }

  async function exportBackupJsonFile() {
    const payload = getCurrentBundle()
    if (!payload) {
      setError('No save state loaded to export.')
      return
    }
    downloadBackupJson(payload)
    setSuccessMessage('Backup (.json) downloaded.')
    setTimeout(() => setSuccessMessage(''), 2500)
  }

  async function exportBackupZipFile() {
    const payload = getCurrentBundle()
    if (!payload) {
      setError('No save state loaded to export.')
      return
    }
    try {
      await downloadBackupZip(payload)
      setSuccessMessage('Backup (.zip) downloaded.')
      setTimeout(() => setSuccessMessage(''), 2500)
    } catch (e: any) {
      setError(e?.message ? String(e.message) : 'Failed to export save zip')
    }
  }

  async function downloadBackupForListedSave(id: string, format: 'json' | 'zip') {
    setError('')
    try {
      const rec = await getBrowserSave(id)
      if (!rec?.bundle?.state) {
        setError('Save not found in this browser.')
        return
      }
      if (format === 'json') downloadBackupJson(rec.bundle)
      else await downloadBackupZip(rec.bundle)
      setSuccessMessage(`Backup (.${format}) downloaded.`)
      setTimeout(() => setSuccessMessage(''), 2500)
    } catch (e: any) {
      setError(e?.message ? String(e.message) : 'Download failed')
    }
  }

  function normalizeImportedBundle(raw: any): SaveBundle {
    if (!raw || typeof raw !== 'object') throw new Error('Invalid save file.')
    const maybePayload = raw?.format === 'fnd-backup-v1' ? raw.payload : raw
    if (!maybePayload || typeof maybePayload !== 'object') throw new Error('Invalid backup payload.')
    const state = (maybePayload as any).state
    if (!state || typeof state !== 'object' || !Array.isArray((state as any).teams)) {
      throw new Error('Backup is missing a valid save state.')
    }
    return {
      state,
      leagueHistory: (maybePayload as any).leagueHistory ?? { seasons: [] },
      records: (maybePayload as any).records ?? {},
      logos: (maybePayload as any).logos ?? {},
      stadiums: (maybePayload as any).stadiums ?? {},
      helmets: (maybePayload as any).helmets ?? {},
      jerseys: (maybePayload as any).jerseys ?? {},
      seasonRecaps: (maybePayload as any).seasonRecaps ?? {},
    }
  }

  function maybeTriggerBackupReminder(prevState: any, nextState: any) {
    if (backupReminderFrequency === 'none') return
    if (!prevState || !nextState) return
    const prevWeek = Number(prevState?.current_week ?? 0)
    const nextWeek = Number(nextState?.current_week ?? 0)
    const prevPhase = String(prevState?.season_phase ?? '').toLowerCase()
    const nextPhase = String(nextState?.season_phase ?? '').toLowerCase()
    const prevPreIdx = Number(prevState?.preseason_stage_index ?? -1)
    const nextPreIdx = Number(nextState?.preseason_stage_index ?? -1)
    const prevOffIdx = Number(prevState?.offseason_stage_index ?? -1)
    const nextOffIdx = Number(nextState?.offseason_stage_index ?? -1)

    let shouldPrompt = false
    let reason = 'Reminder: create a backup save?'
    if (backupReminderFrequency === '3_weeks' || backupReminderFrequency === '6_weeks') {
      const step = backupReminderFrequency === '3_weeks' ? 3 : 6
      const advancedWeek = nextWeek > prevWeek
      if (advancedWeek && nextWeek % step === 0) {
        shouldPrompt = true
        reason = `Week ${nextWeek} reached. Download a backup save?`
      }
    } else if (backupReminderFrequency === 'stage') {
      const preseasonAdvanced = nextPreIdx > prevPreIdx
      const offseasonAdvanced = nextOffIdx > prevOffIdx
      const phaseChanged = prevPhase !== nextPhase
      if (preseasonAdvanced || offseasonAdvanced || phaseChanged) {
        shouldPrompt = true
        reason = 'Stage advanced. Download a backup save?'
      }
    }
    if (shouldPrompt) {
      setBackupPromptReason(reason)
      setShowBackupPrompt(true)
    }
  }

  const refreshDynastyFromServer = useCallback(async () => {
    if (!saveId || inLocalRuntime) return
    try {
      const r = await fetch(`${API_BASE}/saves/${saveId}`, { headers })
      if (!r.ok) return
      const data = await r.json()
      if (data?.league_history && typeof data.league_history === 'object') {
        setDynastyLeagueHistory(data.league_history as { seasons?: unknown[] })
      }
      if (data?.state) {
        applySimulationState(data.state, data)
      }
    } catch {
      /* ignore refresh errors */
    }
  }, [saveId, inLocalRuntime, headers, applySimulationState])

  function applyDynastySimulationResult(data: {
    state?: unknown
    league_history?: unknown
    records?: unknown
    season_recaps?: Record<string, string>
  }) {
    if (data?.state !== undefined && data?.state !== null) {
      applySimulationState(data.state as any, data)
    }
    if (data?.league_history !== undefined && data.league_history !== null) {
      setDynastyLeagueHistory(data.league_history as { seasons?: unknown[] })
    } else if (saveId && !inLocalRuntime) {
      void refreshDynastyFromServer()
    }
    if (localBundle && data?.state !== undefined && data?.state !== null) {
      const id = saveId.startsWith('b_') ? saveId : createBrowserSaveId()
      if (!saveId.startsWith('b_')) setSaveId(id)
      const live = saveStateRef.current
      void putBrowserSave({
        id,
        saveName: String(live?.save_name ?? 'Dynasty').trim() || 'Dynasty',
        updatedAt: Date.now(),
        bundle: {
          ...localBundle,
          state: live,
          leagueHistory:
            data?.league_history !== undefined && data?.league_history !== null
              ? (data.league_history as any)
              : localBundle.leagueHistory,
          records:
            data?.records !== undefined && data?.records !== null ? (data.records as any) : localBundle.records,
          seasonRecaps: data?.season_recaps
            ? { ...(localBundle.seasonRecaps ?? {}), ...data.season_recaps }
            : localBundle.seasonRecaps,
        },
      }).catch((e: any) => setError(e?.message ? String(e.message) : 'Failed to save to browser'))
    }
  }

  useEffect(() => {
    if (screen === 'playing' && saveId && !inLocalRuntime) {
      void refreshDynastyFromServer()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- refresh when dynasty id changes only
  }, [saveId, screen, inLocalRuntime])

  async function importBundleToLibrary(bundle: SaveBundle) {
    const id = createBrowserSaveId()
    const saveName = String(bundle.state?.save_name ?? 'Imported Dynasty').trim() || 'Imported Dynasty'
    await putBrowserSave({ id, saveName, updatedAt: Date.now(), bundle })
    await loadBrowserSave(id)
    await loadBrowserSaveList()
  }

  async function loadFromComputerFile(file: File) {
    setError('')
    try {
      const low = String(file.name || '').toLowerCase()
      const bundle = low.endsWith('.zip')
        ? await importSaveZip(file)
        : normalizeImportedBundle(JSON.parse(await file.text()))
      await importBundleToLibrary(bundle)
      setSuccessMessage('Imported into this browser. Saved in My dynasties.')
      setTimeout(() => setSuccessMessage(''), 3000)
    } catch (e: any) {
      setError(e?.message ? String(e.message) : 'Failed to import save')
    }
  }

  async function restoreAutosave() {
    setError('')
    try {
      const rec = await readLatestAutosave()
      if (!rec?.payload?.state) {
        setError('No browser autosave found yet.')
        return
      }
      if (rec.saveId.startsWith('b_')) {
        await loadBrowserSave(rec.saveId)
      } else {
        await importBundleToLibrary(rec.payload)
      }
      setSuccessMessage(`Restored autosave from ${new Date(rec.savedAt).toLocaleString()}.`)
      setTimeout(() => setSuccessMessage(''), 3000)
    } catch (e: any) {
      setError(e?.message ? String(e.message) : 'Failed to restore autosave')
    }
  }

  async function loadBrowserSaveList() {
    setError('')
    try {
      const rows = await listBrowserSaves()
      setSaves(
        rows.map((r) => ({
          save_id: r.id,
          save_name: r.saveName,
          updated_at: Math.floor(r.updatedAt / 1000),
        })),
      )
    } catch (e: any) {
      setError(e?.message ? String(e.message) : 'Could not read saves from this browser')
    }
  }

  async function loadCloudSaves() {
    if (!token) return
    try {
      const auth = await getAuthHeaders()
      if (!auth.Authorization) return
      const r = await fetch(`${API_BASE}/saves`, { headers: auth })
      if (!r.ok) {
        if (await consumeUnauthorized(r)) return
        return
      }
      const data = await r.json()
      setCloudSaves(data)
    } catch {
      /* optional */
    }
  }

  async function loadBrowserSave(id: string) {
    setError('')
    const rec = await getBrowserSave(id)
    if (!rec?.bundle?.state) {
      setError('Save not found in this browser.')
      return
    }
    let state = rec.bundle.state
    try {
      const r = await fetch(`${API_BASE}/sim/hydrate-inbox`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ state }),
      })
      if (r.ok) {
        const data = await r.json()
        if (data?.state) state = data.state
      }
    } catch {
      /* API offline — load save as stored */
    }
    try {
      const r2 = await fetch(`${API_BASE}/sim/sync-state`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ state }),
      })
      if (r2.ok) {
        const data2 = await r2.json()
        if (data2?.state) state = data2.state
      }
    } catch {
      /* API offline — load save as stored */
    }
    try {
      await enrichSaveStateFromLeagueJson(state, API_BASE)
    } catch {
      /* teams-data unavailable — stadium names stay as stored */
    }
    setLocalBundle({ ...rec.bundle, state })
    setSaveId(id)
    setSaveState(state)
    setDynastyLeagueHistory(
      rec.bundle.leagueHistory && typeof rec.bundle.leagueHistory === 'object'
        ? rec.bundle.leagueHistory
        : { seasons: [] },
    )
    setScreen('playing')
  }

  async function loadSave(id: string) {
    if (isBrowserSaveId(id)) {
      try {
        await loadBrowserSave(id)
      } catch (e: any) {
        setError(e?.message ? String(e.message) : 'Could not load save')
      }
      return
    }
    setError('')
    try {
      const auth = await getAuthHeaders()
      const r = await fetch(`${API_BASE}/saves/${id}`, { headers: auth })
      if (!r.ok) {
        if (await consumeUnauthorized(r)) return
        setError(await formatApiErrorBody(r))
        return
      }
      const data = await r.json()
      const bundle: SaveBundle = {
        state: data.state,
        leagueHistory: data.league_history ?? { seasons: [] },
        records: data.records ?? {},
        logos: {},
        stadiums: {},
        helmets: {},
        jerseys: {},
        seasonRecaps: {},
      }
      const localId = createBrowserSaveId()
      await putBrowserSave({
        id: localId,
        saveName: String(data.state?.save_name ?? 'Dynasty'),
        updatedAt: Date.now(),
        bundle,
      })
      await loadBrowserSave(localId)
      await loadBrowserSaveList()
    } catch (e: any) {
      setError(`Could not load save (${e?.message ?? 'network error'}).${apiConnectionHint()}`)
    }
  }

  async function deleteSave(id: string, saveName: string, e: React.MouseEvent) {
    e.stopPropagation()
    if (!confirm(`Delete dynasty "${saveName}"? This cannot be undone.`)) return
    setError('')
    setSuccessMessage('')
    setDeletingId(id)
    try {
      if (isBrowserSaveId(id)) {
        await deleteBrowserSave(id)
        await loadBrowserSaveList()
      } else {
        const auth = await getAuthHeaders()
        const r = await fetch(`${API_BASE}/saves/${id}`, { method: 'DELETE', headers: auth })
        if (!r.ok) {
          if (await consumeUnauthorized(r)) {
            setDeletingId(null)
            return
          }
          setError((await formatApiErrorBody(r)) || 'Delete failed')
          setDeletingId(null)
          return
        }
        await loadCloudSaves()
      }
      setSuccessMessage(`"${saveName}" deleted.`)
      setTimeout(() => setSuccessMessage(''), 3000)
      if (saveId === id) {
        setSaveId('')
        setSaveState(null)
        setLocalBundle(null)
        setScreen('load')
      }
    } catch (e: any) {
      setError(`Delete failed (${e?.message ?? 'network error'}).${apiConnectionHint()}`)
    } finally {
      setDeletingId(null)
    }
  }

  async function copyCloudSaveToBrowser(cloudId: string) {
    setError('')
    try {
      const auth = await getAuthHeaders()
      const r = await fetch(`${API_BASE}/saves/${cloudId}`, { headers: auth })
      if (!r.ok) {
        if (await consumeUnauthorized(r)) return
        setError(await formatApiErrorBody(r))
        return
      }
      const data = await r.json()
      const id = createBrowserSaveId()
      await putBrowserSave({
        id,
        saveName: String(data.state?.save_name ?? 'Dynasty'),
        updatedAt: Date.now(),
        bundle: {
          state: data.state,
          leagueHistory: data.league_history ?? { seasons: [] },
          records: data.records ?? {},
          logos: {},
          stadiums: {},
          helmets: {},
          jerseys: {},
          seasonRecaps: {},
        },
      })
      await loadBrowserSaveList()
      setSuccessMessage('Copied to this browser.')
      setTimeout(() => setSuccessMessage(''), 2500)
    } catch (e: any) {
      setError(e?.message ? String(e.message) : 'Copy failed')
    }
  }

  async function simWeek(opts?: {
    playbook?: { offensive_playbook: string; defensive_playbook: string }
    gamePlan?: { offensive: Record<string, { play_id: string; pct: number }[]>; defensive: Record<string, { play_id: string; pct: number }[]> }
    depthChart?: Record<string, string[]>
    positionChanges?: { player_name: string; position: string; secondary_position?: string | null }[]
    goals?: { win_goal: number; stage_goal: string }
    homeGameThemes?: HomeThemeSelection[]
    homeGameThemesAck?: boolean
    playoffsSim?: boolean
    seasonFinish?: boolean
    crossRegionPicks?: { slot_index: number; opponent: string; user_home: boolean }[]
    /** Scrimmage Simulate — always hit preseason advance (avoids wrong URL if season_phase in React state is stale). */
    forcePreseasonAdvance?: boolean
    offseasonBody?: {
      winter_strength_pct?: number
      winter_training_allocations?: Record<string, number>
      winter_training_ack_results?: boolean
      spring_offense_focus?: string
      spring_defense_focus?: string
      spring_ball_ack_results?: boolean
      improve_facilities_grade?: number
      improve_culture_grade?: number
      improve_booster_support?: number
      improve_facilities_cumulative_pp?: number
      improve_culture_cumulative_pp?: number
      improve_boosters_cumulative_pp?: number
      coach_dev_allocations?: Record<string, number>
      coaching_cards?: { program_identity?: string | null; position?: string[]; platinum?: string[] }
      carousel_job_applications?: string[]
      transfer_stage_1_ack_results?: boolean
      transfer_stage_2_ack_results?: boolean
      program_development_actions?: { item_id: string; action: 'purchase' | 'renew' }[]
      seven_on_seven_tournament?: string
      seven_on_seven_ack_results?: boolean
    }
  }): Promise<boolean> {
    if (!saveId) {
      setError('No save is loaded. Return to the load screen and open your dynasty again.')
      return false
    }
    setError('')
    const live = saveStateRef.current
    const livePhase = String(live?.season_phase ?? '').toLowerCase()
    const uiPhase = deriveUiPhaseFromSave(live, localBundle?.leagueHistory ?? dynastyLeagueHistory)

    if (localBundle) {
      // Stateless mode: send current bundle state to the API and receive updated state (and updated history/records/recaps).
      try {
        const payload: any = { state: live, league_history: localBundle.leagueHistory, records: localBundle.records }
        const seasonFinishFlow = Boolean(opts?.seasonFinish)
        if (seasonFinishFlow) {
          payload.kind = 'season-finish'
          if (uiPhase === 'schedule_planning') {
            payload.body = { cross_region_picks: opts?.crossRegionPicks ?? [] }
          } else {
            const beginOffseason = shouldBeginOffseason(live, uiPhase)
            const body: Record<string, unknown> = { begin_offseason: beginOffseason }
            if (beginOffseason && opts?.crossRegionPicks?.length) {
              body.cross_region_picks = opts.crossRegionPicks
            }
            payload.body = body
          }
        }
        // Full auto-playoff must win over generic "in playoffs → one round" (otherwise full sim never runs locally).
        else if (opts?.playoffsSim) payload.kind = 'playoffs-sim'
        else if (livePhase === 'playoffs') payload.kind = 'playoffs-sim-round'
        if (!seasonFinishFlow && livePhase === 'offseason') payload.kind = 'offseason-advance'
        if (!payload.kind) payload.kind = 'week-sim'

        if (payload.kind === 'offseason-advance') payload.body = opts?.offseasonBody ?? {}
        if (payload.kind === 'week-sim') payload.body = null
        if (payload.kind === 'season-finish' && payload.body == null) payload.body = { begin_offseason: false }

        // Preseason advances + finish season are driven by existing UI flows that call simWeek()
        // through the same path; map them based on structural phase detection.
        const phaseLower = String(live?.season_phase ?? '').toLowerCase()
        const structDone = preseasonStructurallyComplete(live)
        const inPreseason =
          !structDone &&
          (Boolean(opts?.forcePreseasonAdvance) || phaseLower === 'preseason' || saveHasActivePreseasonFlow(live))
        if (inPreseason && !seasonFinishFlow) {
          payload.kind = 'preseason-advance'
          if (opts?.playbook) payload.body = opts.playbook
          else if (opts?.gamePlan) payload.body = { game_plan: opts.gamePlan }
          else if (opts?.depthChart) payload.body = { depth_chart: opts.depthChart }
          else if (opts?.positionChanges !== undefined) payload.body = { position_changes: opts.positionChanges }
          else if (opts?.goals) payload.body = { goals: opts.goals }
          else if (opts?.homeGameThemes) payload.body = { home_game_themes: opts.homeGameThemes }
          else if (opts?.homeGameThemesAck) payload.body = { home_game_themes_ack: true }
          else payload.body = {}
        }

        const r = await fetch(`${API_BASE}/sim`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        })
        if (!r.ok) {
          if (await consumeUnauthorized(r)) return false
          setError(await formatApiErrorBody(r))
          return false
        }
        const data = await r.json()
        if (data?.state) {
          applySimulationState(data.state, data)
        }
        return true
      } catch (e: any) {
        setError(`Request failed (${e?.message ?? 'network error'}).${apiConnectionHint()}`)
        return false
      }
    }

    if (opts?.seasonFinish) {
      try {
        const beginOffseason = shouldBeginOffseason(live, uiPhase)
        const body =
          uiPhase === 'schedule_planning'
            ? { cross_region_picks: opts.crossRegionPicks ?? [] }
            : beginOffseason && opts?.crossRegionPicks?.length
              ? { begin_offseason: true, cross_region_picks: opts.crossRegionPicks }
              : { begin_offseason: beginOffseason }
        const r = await fetch(`${API_BASE}/saves/${saveId}/season/finish`, {
          method: 'POST',
          headers: { ...headers, 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
        if (!r.ok) {
          if (await consumeUnauthorized(r)) return false
          setError((await formatApiErrorBody(r)) || 'Failed to advance season')
          return false
        }
        const data = await r.json()
        if (data?.state) applyDynastySimulationResult(data)
        else await loadSave(saveId)
        return true
      } catch (e: any) {
        setError(`Request failed (${e?.message ?? 'network error'}).${apiConnectionHint()}`)
        return false
      }
    }

    if (opts?.playoffsSim) {
      try {
        const r = await fetch(`${API_BASE}/saves/${saveId}/playoffs/sim`, { method: 'POST', headers })
        if (!r.ok) {
          if (await consumeUnauthorized(r)) return false
          setError(await formatApiErrorBody(r))
          return false
        }
        const data = await r.json()
        if (data?.state) applyDynastySimulationResult(data)
        else await loadSave(saveId)
        return true
      } catch (e: any) {
        setError(`Request failed (${e?.message ?? 'network error'}).${apiConnectionHint()}`)
        return false
      }
    }
    if (livePhase === 'playoffs') {
      try {
        const r = await fetch(`${API_BASE}/saves/${saveId}/playoffs/sim-round`, { method: 'POST', headers })
        if (!r.ok) {
          if (await consumeUnauthorized(r)) return false
          setError(await formatApiErrorBody(r))
          return false
        }
        const data = await r.json()
        if (data?.state) applyDynastySimulationResult(data)
        else await loadSave(saveId)
        return true
      } catch (e: any) {
        setError(`Request failed (${e?.message ?? 'network error'}).${apiConnectionHint()}`)
        return false
      }
    }
    if (livePhase === 'offseason') {
      try {
        const ob = opts?.offseasonBody ?? {}
        const r = await fetch(`${API_BASE}/saves/${saveId}/offseason/advance`, {
          method: 'POST',
          headers: { ...headers, 'Content-Type': 'application/json' },
          body: JSON.stringify(ob),
        })
        if (!r.ok) {
          if (await consumeUnauthorized(r)) return false
          setError(await formatApiErrorBody(r))
          return false
        }
        const data = await r.json()
        if (data?.state) applyDynastySimulationResult(data)
        else await loadSave(saveId)
        return true
      } catch (e: any) {
        setError(`Request failed (${e?.message ?? 'network error'}).${apiConnectionHint()}`)
        return false
      }
    }
    if (uiPhase === 'season_summary' || uiPhase === 'schedule_planning') {
      return simWeek({ ...opts, seasonFinish: true })
    }
    const phaseLower = String(live?.season_phase ?? '').toLowerCase()
    const structDone = preseasonStructurallyComplete(live)
    // If preseason stages are finished on file, always sim the regular season (even when season_phase was not updated yet).
    const inPreseason =
      !structDone &&
      (Boolean(opts?.forcePreseasonAdvance) ||
        phaseLower === 'preseason' ||
        saveHasActivePreseasonFlow(live))
    const url = inPreseason ? `${API_BASE}/saves/${saveId}/preseason/advance` : `${API_BASE}/saves/${saveId}/week/sim`
    let body: string | undefined
    if (inPreseason && opts?.playbook) {
      body = JSON.stringify(opts.playbook)
    } else if (inPreseason && opts?.gamePlan) {
      body = JSON.stringify({ game_plan: opts.gamePlan })
    } else if (inPreseason && opts?.depthChart) {
      body = JSON.stringify({ depth_chart: opts.depthChart })
    } else if (inPreseason && opts?.positionChanges !== undefined) {
      body = JSON.stringify({ position_changes: opts.positionChanges })
    } else if (inPreseason && opts?.goals) {
      body = JSON.stringify({ goals: opts.goals })
    } else if (inPreseason && opts?.homeGameThemes) {
      body = JSON.stringify({ home_game_themes: opts.homeGameThemes })
    } else if (inPreseason && opts?.homeGameThemesAck) {
      body = JSON.stringify({ home_game_themes_ack: true })
    } else if (inPreseason) {
      body = '{}'
    } else {
      body = undefined
    }
    try {
      const r = await fetch(url, {
        method: 'POST',
        headers: body ? { ...headers, 'Content-Type': 'application/json' } : headers,
        body,
      })
      if (!r.ok) {
        if (await consumeUnauthorized(r)) return false
        setError(await formatApiErrorBody(r))
        return false
      }
      let data: { state?: any }
      try {
        data = await r.json()
      } catch {
        setError('Server returned invalid JSON (often NaN/Infinity in save data). Check API logs.')
        return false
      }
      if (data?.state) applyDynastySimulationResult(data)
      else await loadSave(saveId)
      return true
    } catch (e: any) {
      setError(`Request failed (${e?.message ?? 'network error'}).${apiConnectionHint()}`)
      return false
    }
  }

  async function onLoadSaveClick() {
    setError('')
    setScreen('load')
    await loadBrowserSaveList()
    if (token) await loadCloudSaves()
  }

  async function onNewSaveClick() {
    setError('')
    if (token && !(await validateSession())) {
      expireSession()
    }
    setScreen('new')
  }

  const titleNavRef = useRef({ onNewSaveClick, onLoadSaveClick })
  titleNavRef.current = { onNewSaveClick, onLoadSaveClick }

  useEffect(() => {
    if (screen !== 'title') setShowScreenshotsGallery(false)
  }, [screen])

  useEffect(() => {
    function onMessage(e: MessageEvent) {
      if (e.origin !== window.location.origin) return
      const d = e.data as { type?: string; action?: string } | null
      if (!d || d.type !== 'fnd-title') return
      if (d.action === 'new') void titleNavRef.current.onNewSaveClick()
      else if (d.action === 'load') void titleNavRef.current.onLoadSaveClick()
      else if (d.action === 'screenshots') setShowScreenshotsGallery(true)
    }
    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [])

  async function onContinueLoad() {
    const ok = devNoFirebase ? await devAuthSubmit() : await firebaseAuthSubmit(authMode)
    if (ok) {
      await loadBrowserSaveList()
      await loadCloudSaves()
    }
  }

  async function onContinueNew() {
    setError('')
    const ok = devNoFirebase ? await devAuthSubmit() : await firebaseAuthSubmit(authMode)
    if (ok) setScreen('new')
  }

  useEffect(() => {
    if (authMode === 'login') setTermsAccepted(false)
  }, [authMode])

  useEffect(() => {
    if (!token) return
    void validateSession(token).then((ok) => {
      if (!ok) clearStaleSession()
      else {
        void refreshBillingStatus({ Authorization: `Bearer ${token}` })
        if (screen === 'load') {
          void loadBrowserSaveList()
          void loadCloudSaves()
        }
      }
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- validate stored token once on load
  }, [])

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const billing = params.get('billing')
    const sessionId = params.get('session_id')?.trim()
    if (!billing) return

    const cleanBillingParams = () => {
      const url = new URL(window.location.href)
      url.searchParams.delete('billing')
      url.searchParams.delete('session_id')
      const next = `${url.pathname}${url.search}${url.hash}`
      window.history.replaceState({}, '', next)
    }

    if (billing === 'cancelled') {
      cleanBillingParams()
      setError('Checkout was cancelled. You can try again when ready.')
      return
    }

    if (billing !== 'success' || !sessionId) return

    const storedToken = (localStorage.getItem('fnd_token') ?? token).trim()
    if (!storedToken) {
      setError('Sign in with the same account you used for checkout, then open the success link again.')
      cleanBillingParams()
      return
    }

    void (async () => {
      setBillingBusy(true)
      try {
        await confirmCheckoutSession(
          API_BASE,
          { Authorization: `Bearer ${storedToken}` },
          sessionId,
        )
        await refreshBillingStatus({ Authorization: `Bearer ${storedToken}` })
        setSuccessMessage('Purchase complete — welcome to Friday Night Dynasty!')
        setTimeout(() => setSuccessMessage(''), 6000)
        cleanBillingParams()
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : 'Could not confirm purchase'
        setError(msg)
      } finally {
        setBillingBusy(false)
      }
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once for Stripe return URL
  }, [])

  useEffect(() => {
    if (screen === 'load') {
      void loadBrowserSaveList()
      if (token) void loadCloudSaves()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, screen])

  useEffect(() => {
    localStorage.setItem('fnd_autosave_enabled', autosaveEnabled ? 'true' : 'false')
  }, [autosaveEnabled])

  useEffect(() => {
    localStorage.setItem('fnd_backup_reminder_frequency', backupReminderFrequency)
  }, [backupReminderFrequency])

  useEffect(() => {
    if (!error) {
      setCrashReportText('')
      return
    }
    const report = buildCrashReport(error)
    setCrashReportText(report)
    const crashLike =
      error.includes('trace_location') ||
      error.includes('crash_at') ||
      error.includes('Traceback') ||
      error.includes('Errno') ||
      error.includes('Invalid argument')
    if (!crashLike) return
    const key = `${saveId}|${screen}|${error}`
    if (key === lastCrashPromptKey) return
    setLastCrashPromptKey(key)
    const shouldCreate = window.confirm('Crash detected. Create a .txt crash report to send back?')
    if (shouldCreate) {
      const stamp = new Date().toISOString().replace(/[:.]/g, '-')
      downloadText(`fnd_crash_report_${stamp}.txt`, report)
    }
  }, [error, saveId, screen, lastCrashPromptKey])

  useEffect(() => {
    if (!autosaveEnabled) return
    if (screen !== 'playing') return
    const live = saveStateRef.current
    if (!live) return
    const timer = window.setTimeout(() => {
      const payload: SaveBundle = localBundle
        ? { ...localBundle, state: live }
        : { state: live, leagueHistory: { seasons: [] }, records: {}, logos: {}, stadiums: {}, helmets: {}, jerseys: {}, seasonRecaps: {} }
      const rec: BrowserAutosaveRecord = {
        savedAt: Date.now(),
        saveId: saveId || '__unknown__',
        saveName: String(live?.save_name ?? 'dynasty'),
        payload,
      }
      void writeLatestAutosave(rec)
        .then(() => setLastAutosaveAt(rec.savedAt))
        .catch((e: any) => setError(e?.message ? String(e.message) : 'Autosave failed'))
      if (localBundle && saveId) {
        void persistCurrentBrowserSave().catch(() => {})
      }
    }, 1200)
    return () => window.clearTimeout(timer)
  }, [autosaveEnabled, localBundle, saveId, saveState, screen, persistCurrentBrowserSave])

  function goTitle() {
    setScreen('title')
    setError('')
  }

  /* ——— Playing: league dashboard (same data as before) ——— */
  if (screen === 'playing' && localBundle && saveState) {
    return (
      <>
        <div style={{ position: 'fixed', top: 12, right: 12, zIndex: 9999, display: 'flex', gap: 8, flexWrap: 'wrap', maxWidth: 'min(100vw - 24px, 520px)', justifyContent: 'flex-end' }}>
          <button type="button" className="teamhome-select" onClick={() => setAutosaveEnabled((v) => !v)} title="Toggle browser autosave">
            Autosave: {autosaveEnabled ? 'On' : 'Off'}
          </button>
          <button type="button" className="teamhome-select" onClick={() => void exportBackupZipFile()} title="Full save zip (state, history, records, logos)">
            Download backup (.zip)
          </button>
          <button type="button" className="teamhome-select" onClick={() => void exportBackupJsonFile()} title="Lighter JSON backup">
            Download backup (.json)
          </button>
        </div>
        <LocalAssetsProvider bundle={localBundle}>
          <TeamHomePage
              apiBase={API_BASE}
              headers={inLocalRuntime ? {} : headers}
              saveId={saveId}
              saveState={saveState}
              onMainMenu={goTitle}
              onSimWeek={simWeek}
              getLiveSaveState={() => saveStateRef.current}
              onSaveState={patchSaveState}
              onError={setError}
              backupReminderFrequency={backupReminderFrequency}
              onBackupReminderFrequencyChange={setBackupReminderFrequency}
              onBackupNow={() => void exportBackupZipFile()}
              leagueHistory={
                inLocalRuntime && localBundle ? localBundle.leagueHistory : dynastyLeagueHistory
              }
              records={inLocalRuntime && localBundle ? localBundle.records : undefined}
              seasonRecaps={inLocalRuntime && localBundle ? localBundle.seasonRecaps : undefined}
              onMergeLocalSimulationResult={inLocalRuntime ? mergeLocalSimulationResult : undefined}
              onImportLogosToBundle={localBundle ? importLogosToBundle : undefined}
              onImportStadiumsToBundle={localBundle ? importStadiumsToBundle : undefined}
              onImportHelmetsToBundle={localBundle ? importHelmetsToBundle : undefined}
              onImportJerseysToBundle={localBundle ? importJerseysToBundle : undefined}
              onRefreshDynasty={inLocalRuntime ? undefined : refreshDynastyFromServer}
          />
        </LocalAssetsProvider>
        {showBackupPrompt ? (
          <div
            style={{
              position: 'fixed',
              inset: 0,
              background: 'rgba(0,0,0,0.55)',
              zIndex: 10000,
              display: 'grid',
              placeItems: 'center',
              padding: '1rem',
            }}
          >
            <div style={{ width: 'min(520px, 100%)', background: '#0f131b', border: '1px solid #2f3440', borderRadius: 12, padding: '1rem' }}>
              <h3 style={{ marginTop: 0, marginBottom: '0.5rem' }}>Backup Reminder</h3>
              <p style={{ marginTop: 0, color: '#a9b1bc' }}>{backupPromptReason}</p>
              <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                <button type="button" className="teamhome-select" onClick={() => setShowBackupPrompt(false)}>
                  Remind me later
                </button>
                <button
                  type="button"
                  className="teamhome-select"
                  onClick={() => {
                    void exportBackupZipFile()
                    setShowBackupPrompt(false)
                  }}
                >
                  Download .zip
                </button>
                <button
                  type="button"
                  className="teamhome-select"
                  onClick={() => {
                    void exportBackupJsonFile()
                    setShowBackupPrompt(false)
                  }}
                >
                  Download .json
                </button>
              </div>
            </div>
          </div>
        ) : null}
        {error ? (
          <div className="fnd-error" style={{ position: 'fixed', bottom: 16, left: 16, right: 16, zIndex: 9999 }}>
            <div>{error}</div>
            {crashReportText ? (
              <div style={{ marginTop: 8 }}>
                <button type="button" className="teamhome-select" onClick={downloadCrashReportNow}>
                  Download Crash Report (.txt)
                </button>
              </div>
            ) : null}
          </div>
        ) : null}
      </>
    )
  }

  /* ——— Title + Load list + New save ——— */
  return (
    <div className={screen === 'title' ? 'fnd-title-root fnd-title-root--landing' : 'fnd-title-root'}>
      {screen === 'title' ? (
        <iframe
          className="fnd-title-iframe"
          title="Friday Night Dynasty"
          src={`${import.meta.env.BASE_URL}fnd_homepage.html?v=20260620a`}
        />
      ) : (
        <div className="fnd-title-inner">
        <h1 className="fnd-title-heading">Friday Night Dynasty</h1>

        {screen === 'load' && (
          <div className="fnd-panel">
            <button type="button" className="fnd-back" onClick={goTitle}>
              ← Back
            </button>
            <h2>Load save</h2>
            <p style={{ margin: '0 0 1rem', color: '#9ca3af', fontSize: '0.9rem' }}>
              Dynasties are stored in <strong style={{ color: '#d0d4dc' }}>this browser</strong> (IndexedDB). Download backups
              to keep a copy on your computer.
            </p>
            <div style={{ marginBottom: '1rem', padding: '0.75rem', border: '1px solid #2f3440', borderRadius: 8 }}>
              <p style={{ margin: '0 0 0.5rem', color: '#9ca3af', fontSize: '0.9rem' }}>
                <strong style={{ color: '#d0d4dc' }}>Import</strong> — restore a .zip or .json backup into this browser.
              </p>
              <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                <input
                  type="file"
                  accept=".json,.zip,application/zip,application/json"
                  onChange={(e) => {
                    const f = e.target.files?.[0]
                    if (f) void loadFromComputerFile(f)
                    e.currentTarget.value = ''
                  }}
                />
                <button type="button" className="fnd-title-btn" style={{ maxWidth: 220 }} onClick={restoreAutosave}>
                  Load latest autosave
                </button>
              </div>
              {lastAutosaveAt ? (
                <p style={{ margin: '0.5rem 0 0', color: '#7f8794', fontSize: '0.8rem' }}>
                  Last autosave this session: {new Date(lastAutosaveAt).toLocaleString()}
                </p>
              ) : null}
            </div>
            <button type="button" className="fnd-title-btn" style={{ maxWidth: '100%', marginBottom: '1rem' }} onClick={() => void loadBrowserSaveList()}>
              Refresh my dynasties
            </button>
            <h3 style={{ margin: '0 0 0.75rem', fontSize: '1rem', color: '#d0d4dc' }}>My dynasties (this browser)</h3>
            {saves.length === 0 ? (
              <p style={{ color: '#9ca3af', margin: '0 0 1.5rem' }}>No saves in this browser yet. Import a file or start New Save.</p>
            ) : (
              <div style={{ marginBottom: '1.5rem' }}>
                {saves.map((s) => (
                  <div key={s.save_id} className="fnd-save-row-wrap" style={{ flexWrap: 'wrap', gap: 6 }}>
                    <button type="button" className="fnd-save-row" style={{ flex: '1 1 200px' }} onClick={() => loadSave(s.save_id)}>
                      <strong>{s.save_name}</strong>
                      <small>{new Date(s.updated_at * 1000).toLocaleString()}</small>
                    </button>
                    <button
                      type="button"
                      className="teamhome-select"
                      style={{ fontSize: '0.75rem' }}
                      onClick={(e) => {
                        e.stopPropagation()
                        void downloadBackupForListedSave(s.save_id, 'zip')
                      }}
                    >
                      .zip
                    </button>
                    <button
                      type="button"
                      className="teamhome-select"
                      style={{ fontSize: '0.75rem' }}
                      onClick={(e) => {
                        e.stopPropagation()
                        void downloadBackupForListedSave(s.save_id, 'json')
                      }}
                    >
                      .json
                    </button>
                    <button
                      type="button"
                      className="fnd-save-delete"
                      onClick={(e) => deleteSave(s.save_id, s.save_name, e)}
                      disabled={deletingId === s.save_id}
                      title="Delete from this browser"
                    >
                      {deletingId === s.save_id ? '…' : 'Delete'}
                    </button>
                  </div>
                ))}
              </div>
            )}
            {!token ? (
              <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid #2f3440' }}>
                <p style={{ margin: '0 0 0.75rem', color: '#9ca3af', fontSize: '0.85rem' }}>
                  Optional: sign in to copy cloud saves from the server into this browser.
                </p>
                <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
                  <button
                    type="button"
                    className={authMode === 'login' ? 'fnd-title-btn' : 'teamhome-select'}
                    style={{ flex: 1, maxWidth: 'none' }}
                    onClick={() => setAuthMode('login')}
                  >
                    Log in
                  </button>
                  <button
                    type="button"
                    className={authMode === 'signup' ? 'fnd-title-btn' : 'teamhome-select'}
                    style={{ flex: 1, maxWidth: 'none' }}
                    onClick={() => setAuthMode('signup')}
                  >
                    Sign up
                  </button>
                </div>
                <div className="fnd-login-row" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
                  <input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" />
                  <input
                    type="password"
                    autoComplete={authMode === 'signup' ? 'new-password' : 'current-password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Password"
                    onKeyDown={(e) => e.key === 'Enter' && void onContinueLoad()}
                  />
                  {authMode === 'signup' ? (
                    <SignupTermsConsent checked={termsAccepted} onChange={setTermsAccepted} />
                  ) : null}
                  <button
                    type="button"
                    disabled={authBusy || (authMode === 'signup' && !termsAccepted)}
                    onClick={() => void onContinueLoad()}
                  >
                    {authBusy ? 'Please wait…' : authMode === 'signup' ? 'Sign up' : 'Log in'}
                  </button>
                  {authMode === 'login' ? (
                    <button
                      type="button"
                      className="fnd-forgot-password"
                      disabled={authBusy || resetPasswordBusy}
                      onClick={() => void handleForgotPassword()}
                    >
                      {resetPasswordBusy ? 'Sending reset email…' : 'Forgot Password?'}
                    </button>
                  ) : null}
                </div>
              </div>
            ) : (
              <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid #2f3440' }}>
                <p style={{ margin: '0 0 0.75rem', color: '#9ca3af', fontSize: '0.85rem' }}>
                  Signed in as <strong style={{ color: '#d0d4dc' }}>{username}</strong>
                  <button
                    type="button"
                    className="teamhome-select"
                    style={{ marginLeft: 10, fontSize: '0.75rem' }}
                    onClick={() => {
                      clearStaleSession()
                      setCloudSaves([])
                    }}
                  >
                    Sign out
                  </button>
                </p>
                <h3 style={{ margin: '0 0 0.5rem', fontSize: '0.95rem', color: '#d0d4dc' }}>Server saves (copy to browser)</h3>
                {cloudSaves.length === 0 ? (
                  <p style={{ color: '#7f8794', fontSize: '0.85rem', margin: 0 }}>No cloud saves on this account.</p>
                ) : (
                  cloudSaves.map((s) => (
                    <div key={s.save_id} className="fnd-save-row-wrap" style={{ marginBottom: 6 }}>
                      <span style={{ flex: 1, padding: '0.5rem 0', color: '#c5cad3', fontSize: '0.9rem' }}>
                        <strong>{s.save_name}</strong>
                        <small style={{ display: 'block', color: '#7f8794' }}>
                          {new Date(s.updated_at * 1000).toLocaleString()}
                        </small>
                      </span>
                      <button type="button" className="teamhome-select" onClick={() => void copyCloudSaveToBrowser(s.save_id)}>
                        Copy here
                      </button>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        )}

        {screen === 'new' && !token && (
          <div className="fnd-panel">
            <button type="button" className="fnd-back" onClick={goTitle}>
              ← Back
            </button>
            <h2>New dynasty</h2>
            <p style={{ margin: '0 0 1rem', color: '#9ca3af', fontSize: '0.9rem' }}>
              {devNoFirebase
                ? 'Local dev mode: enter a coach name (no Firebase). Dynasties save in this browser and on the API when you create a save.'
                : 'Log in to create a new dynasty. It will be saved in this browser (IndexedDB); download backups anytime.'}
            </p>
            {devNoFirebase ? (
              <div className="fnd-login-row" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
                <input
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Coach name"
                  onKeyDown={(e) => e.key === 'Enter' && void onContinueNew()}
                />
                <button type="button" disabled={authBusy} onClick={() => void onContinueNew()}>
                  {authBusy ? 'Please wait…' : 'Continue'}
                </button>
              </div>
            ) : (
              <>
                <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
                  <button
                    type="button"
                    className={authMode === 'login' ? 'fnd-title-btn' : 'teamhome-select'}
                    style={{ flex: 1, maxWidth: 'none' }}
                    onClick={() => setAuthMode('login')}
                  >
                    Log in
                  </button>
                  <button
                    type="button"
                    className={authMode === 'signup' ? 'fnd-title-btn' : 'teamhome-select'}
                    style={{ flex: 1, maxWidth: 'none' }}
                    onClick={() => setAuthMode('signup')}
                  >
                    Sign up
                  </button>
                </div>
                <div className="fnd-login-row" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
                  <input
                    type="email"
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="Email"
                  />
                  <input
                    type="password"
                    autoComplete={authMode === 'signup' ? 'new-password' : 'current-password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Password"
                    onKeyDown={(e) => e.key === 'Enter' && void onContinueNew()}
                  />
                  {authMode === 'signup' ? (
                    <SignupTermsConsent checked={termsAccepted} onChange={setTermsAccepted} />
                  ) : null}
                  <button
                    type="button"
                    disabled={authBusy || (authMode === 'signup' && !termsAccepted)}
                    onClick={() => void onContinueNew()}
                  >
                    {authBusy ? 'Please wait…' : authMode === 'signup' ? 'Create account & continue' : 'Log in & continue'}
                  </button>
                  {authMode === 'login' ? (
                    <button
                      type="button"
                      className="fnd-forgot-password"
                      disabled={authBusy || resetPasswordBusy}
                      onClick={() => void handleForgotPassword()}
                    >
                      {resetPasswordBusy ? 'Sending reset email…' : 'Forgot Password?'}
                    </button>
                  ) : null}
                </div>
              </>
            )}
            {deviceLimitDevices.length > 0 ? (
              <div style={{ marginTop: 12, padding: 10, border: '1px solid #4a5568', borderRadius: 8 }}>
                <p style={{ margin: '0 0 8px', fontSize: '0.85rem', color: '#cbd5e1' }}>Registered devices</p>
                {deviceLimitDevices.map((d) => (
                  <div
                    key={d.device_id}
                    style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}
                  >
                    <span style={{ fontSize: '0.8rem', color: '#9ca3af' }}>{d.device_id.slice(0, 8)}…</span>
                    <button type="button" className="teamhome-select" onClick={() => void removeRegisteredDevice(d.device_id)}>
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        )}

        {screen === 'new' && token && needsBillingPurchase ? (
          <div className="fnd-panel">
            <button type="button" className="fnd-back" onClick={goTitle}>
              ← Back
            </button>
            <h2>Unlock Friday Night Dynasty</h2>
            <p style={{ margin: '0 0 1rem', color: '#9ca3af', fontSize: '0.9rem' }}>
              You&apos;re signed in as <strong style={{ color: '#d0d4dc' }}>{username}</strong>. Complete a one-time
              purchase to create a new dynasty and use cloud saves.
            </p>
            {billingChecking ? (
              <p style={{ color: '#9ca3af', fontSize: '0.9rem' }}>Checking purchase status…</p>
            ) : (
              <button
                type="button"
                className="fnd-title-btn"
                style={{ maxWidth: '100%' }}
                disabled={billingBusy}
                onClick={() => void startCheckout()}
              >
                {billingBusy ? 'Redirecting to checkout…' : 'Buy now — secure checkout'}
              </button>
            )}
          </div>
        ) : screen === 'new' && token ? (
          <NewSaveFlow
            apiBase={API_BASE}
            headers={headers}
            getAuthHeaders={getAuthHeaders}
            onBack={goTitle}
            onError={setError}
            onSessionExpired={() => expireSession()}
            defaultCoachName={username}
            onCreated={async (cloudId, logos) => {
              try {
                const auth = await getAuthHeaders()
                const r = await fetch(`${API_BASE}/saves/${cloudId}`, { headers: auth })
                if (!r.ok) {
                  if (await consumeUnauthorized(r)) return
                  setError(await formatApiErrorBody(r))
                  return
                }
                const data = await r.json()
                const localId = createBrowserSaveId()
                await putBrowserSave({
                  id: localId,
                  saveName: String(data.state?.save_name ?? 'My Dynasty'),
                  updatedAt: Date.now(),
                  bundle: {
                    state: data.state,
                    leagueHistory: data.league_history ?? { seasons: [] },
                    records: data.records ?? {},
                    logos: logos ?? {},
                    stadiums: {},
                    helmets: {},
                    jerseys: {},
                    seasonRecaps: {},
                  },
                })
                await loadBrowserSaveList()
                await loadBrowserSave(localId)
              } catch (e: any) {
                setError(e?.message ? String(e.message) : 'Could not save dynasty to this browser')
              }
            }}
          />
        ) : null}

        {error ? (
          <div className="fnd-error">
            <div>{error}</div>
            {crashReportText ? (
              <div style={{ marginTop: 8 }}>
                <button type="button" className="fnd-title-btn" style={{ maxWidth: 280 }} onClick={downloadCrashReportNow}>
                  Download Crash Report (.txt)
                </button>
              </div>
            ) : null}
          </div>
        ) : null}
        {successMessage ? <div className="fnd-success">{successMessage}</div> : null}
        </div>
      )}
      <ScreenshotsGallery open={showScreenshotsGallery} onClose={() => setShowScreenshotsGallery(false)} />
    </div>
  )
}
