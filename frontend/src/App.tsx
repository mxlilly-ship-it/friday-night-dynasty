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
  isMultiplayerSaveId,
  listBrowserSaves,
  multiplayerSaveId,
  parseMultiplayerSaveId,
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
import SupportContactModal from './SupportContactModal'
import { getOrCreateDeviceId } from './deviceId.js'
import { confirmCheckoutSession, createCheckoutSession, fetchBillingStatus, parseApiError, syncBillingAccess as syncBillingAccessApi, type BillingStatus } from './billing'
import MultiplayerLeaguesPage from './MultiplayerLeaguesPage'
import LeagueDashboardPage from './LeagueDashboardPage'
import CommishDashboardPage from './CommishDashboardPage'
import {
  assignTeamByEmail,
  commishSimWeek,
  fetchCommishDashboard,
  fetchLeagueDashboard,
  fetchLeagueGame,
  inviteToLeague,
  postLeagueChat,
  removeLeagueMember,
  resetMemberPin,
  revokeLeagueInvite,
  saveLeagueGame,
  submitLeagueWeek,
  unsubmitLeagueWeek,
  updateCommishSettings,
  vacateTeamMember,
  verifyTeamPin,
  type CommishDashboardData,
  type LeagueDashboardData,
  type LeagueListItem,
} from './multiplayer'

/** Stable reference so child effects do not re-run when logged out (browser saves). */
const EMPTY_AUTH_HEADERS: Record<string, string> = Object.freeze({})

const PENDING_CHECKOUT_SESSION_KEY = 'fnd_pending_checkout_session'

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
type Screen =
  | 'title'
  | 'load'
  | 'new'
  | 'purchase'
  | 'playing'
  | 'multiplayer'
  | 'multiplayer_create'
  | 'multiplayer_coach_setup'
  | 'league_dashboard'
  | 'commish_dashboard'
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
  const [showSupportContact, setShowSupportContact] = useState(false)
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
  const [mpDashboard, setMpDashboard] = useState<LeagueDashboardData | null>(null)
  const [mpCommishDashboard, setMpCommishDashboard] = useState<CommishDashboardData | null>(null)
  const [mpPendingLeague, setMpPendingLeague] = useState<LeagueListItem | null>(null)
  const [mpPinTeam, setMpPinTeam] = useState<string | null>(null)
  const [mpPinInput, setMpPinInput] = useState('')
  const [mpPinBusy, setMpPinBusy] = useState(false)
  const [mpShowTeamPicker, setMpShowTeamPicker] = useState(false)
  const [mpCoachSetupTeam, setMpCoachSetupTeam] = useState<string | null>(null)
  const [mpGameContext, setMpGameContext] = useState<{
    leagueId: string
    teamName?: string
    commishMode?: boolean
  } | null>(null)
  const [mpCoachDashBusy, setMpCoachDashBusy] = useState(false)
  const [mpSubmitBusy, setMpSubmitBusy] = useState(false)
  const [mpCommishSimBusy, setMpCommishSimBusy] = useState(false)
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
  const [showTrialPurchaseModal, setShowTrialPurchaseModal] = useState(false)
  const inLocalRuntime = Boolean(localBundle) && (isBrowserSaveId(saveId) || isMultiplayerSaveId(saveId))
  const needsBillingPurchase = Boolean(
    billingStatus?.billing_required && !billingStatus?.entitled && !billingStatus?.trial_available,
  )
  const onFreeTrial = Boolean(
    billingStatus?.billing_required && !billingStatus?.entitled && billingStatus?.trial_available,
  )
  const supportDefaultEmail = useMemo(() => {
    const em = email.trim()
    if (em) return em
    const u = username.trim()
    return u.includes('@') ? u : ''
  }, [email, username])

  const saveStateRef = useRef<any>(null)
  saveStateRef.current = saveState
  const scheduleBrowserPersistRef = useRef<(() => void) | null>(null)
  const persistCurrentBrowserSaveRef = useRef<(() => Promise<void>) | null>(null)

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

  useEffect(() => {
    scheduleBrowserPersistRef.current = () => {
      if (!localBundle || !saveId) return
      void persistCurrentBrowserSaveRef.current?.()
    }
  }, [localBundle, saveId])

  const headers = useMemo((): Record<string, string> => {
    if (!token) return EMPTY_AUTH_HEADERS
    return { Authorization: `Bearer ${token}` }
  }, [token])

  const persistCurrentBrowserSave = useCallback(async () => {
    if (!localBundle) return
    const live = saveStateRef.current
    if (!live) return
    let id = saveId.startsWith('b_') || isMultiplayerSaveId(saveId) ? saveId : createBrowserSaveId()
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
    const mpCtx = isMultiplayerSaveId(id) ? parseMultiplayerSaveId(id) : null
    if (mpCtx && token && !mpCtx.commishMode && mpCtx.teamName) {
      try {
        await saveLeagueGame(API_BASE, headers, mpCtx.leagueId, mpCtx.teamName, live as Record<string, unknown>)
      } catch {
        /* server sync best-effort */
      }
    }
  }, [saveId, localBundle, token, headers])

  useEffect(() => {
    persistCurrentBrowserSaveRef.current = persistCurrentBrowserSave
  }, [persistCurrentBrowserSave])

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

  async function handleTrialOrApiError(r: Response): Promise<boolean> {
    if (await consumeUnauthorized(r)) return true
    const err = await parseApiError(r)
    if (r.status === 402 && err.code === 'TRIAL_COMPLETE') {
      setShowTrialPurchaseModal(true)
      void refreshBillingStatus()
      return true
    }
    setError(err.message)
    return true
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

  async function tryConfirmCheckoutSession(sessionId: string): Promise<boolean> {
    const sid = sessionId.trim()
    if (!sid) return false
    try {
      const auth = await getAuthHeaders()
      if (!auth.Authorization) return false
      const status = await confirmCheckoutSession(API_BASE, auth, sid)
      setBillingStatus(status)
      if (status.entitled) {
        sessionStorage.removeItem(PENDING_CHECKOUT_SESSION_KEY)
        return true
      }
    } catch {
      /* fall through to Stripe sync */
    }
    return false
  }

  async function syncBillingAccess(sessionId?: string) {
    setBillingChecking(true)
    try {
      const fromUrl = sessionId?.trim()
      const pending = fromUrl || sessionStorage.getItem(PENDING_CHECKOUT_SESSION_KEY)?.trim() || ''
      if (pending) {
        const confirmed = await tryConfirmCheckoutSession(pending)
        if (confirmed) return
      }
      const auth = await getAuthHeaders()
      if (!auth.Authorization) {
        await refreshBillingStatus()
        return
      }
      const status = await syncBillingAccessApi(API_BASE, auth)
      setBillingStatus(status)
      if (status.entitled) {
        sessionStorage.removeItem(PENDING_CHECKOUT_SESSION_KEY)
        setSuccessMessage('Purchase found — your account is unlocked!')
        setTimeout(() => setSuccessMessage(''), 5000)
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Could not refresh purchase status'
      setError(msg)
      await refreshBillingStatus()
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
      const { checkoutUrl, sessionId } = await createCheckoutSession(API_BASE, auth)
      sessionStorage.setItem(PENDING_CHECKOUT_SESSION_KEY, sessionId)
      window.location.href = checkoutUrl
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
    // Any multiplayer dynasty session is coach-prep only; league advance is dashboard-only.
    const mpCoachCtx =
      mpGameContext?.leagueId && mpGameContext.teamName ? mpGameContext : null
    const mpLeagueLocked = Boolean(mpGameContext?.leagueId)
    const MP_ADVANCE_MSG =
      'Advance the league from the Commissioner dashboard (Sim week). Finish your prep, then submit your week.'

    function mpOffseasonIsAdvanceAck(body: Record<string, unknown> | undefined): boolean {
      if (!body) return false
      return Boolean(
        body.winter_training_ack_results ||
          body.spring_ball_ack_results ||
          body.transfer_stage_1_ack_results ||
          body.transfer_stage_2_ack_results ||
          body.seven_on_seven_ack_results,
      )
    }

    function isMpCoachPrepOpts(): boolean {
      if (!opts) return false
      if (opts.playoffsSim || opts.seasonFinish) return false
      if (opts.offseasonBody && mpOffseasonIsAdvanceAck(opts.offseasonBody as Record<string, unknown>)) return false
      return Boolean(
        opts.playbook ||
          opts.gamePlan ||
          opts.depthChart ||
          opts.positionChanges !== undefined ||
          opts.goals ||
          opts.homeGameThemes ||
          opts.homeGameThemesAck ||
          opts.forcePreseasonAdvance ||
          opts.offseasonBody,
      )
    }

    function buildMpCoachPrep(): Record<string, unknown> {
      const prep: Record<string, unknown> = {}
      if (opts?.playbook) {
        prep.offensive_playbook = opts.playbook.offensive_playbook
        prep.defensive_playbook = opts.playbook.defensive_playbook
      }
      if (opts?.gamePlan) prep.game_plan = opts.gamePlan
      if (opts?.depthChart) prep.depth_chart = opts.depthChart
      if (opts?.positionChanges !== undefined) prep.position_changes = opts.positionChanges
      if (opts?.goals) prep.goals = opts.goals
      if (opts?.homeGameThemes) prep.home_game_themes = opts.homeGameThemes
      if (opts?.homeGameThemesAck) prep.home_game_themes_ack = true
      if (opts?.forcePreseasonAdvance) prep.scrimmage_simulate = true
      if (opts?.offseasonBody) Object.assign(prep, opts.offseasonBody)
      return prep
    }

    if (mpLeagueLocked && !mpCoachCtx) {
      setError(MP_ADVANCE_MSG)
      return false
    }

    if (mpCoachCtx) {
      if (opts?.seasonFinish || opts?.playoffsSim) {
        setError(MP_ADVANCE_MSG)
        return false
      }
      if (!isMpCoachPrepOpts()) {
        setError(MP_ADVANCE_MSG)
        return false
      }
      try {
        const q = `?team_name=${encodeURIComponent(mpCoachCtx.teamName!)}`
        const r = await fetch(`${API_BASE}/leagues/${mpCoachCtx.leagueId}/coach-prep${q}`, {
          method: 'POST',
          headers: { ...(await getAuthHeaders()), 'Content-Type': 'application/json' },
          body: JSON.stringify({ prep: buildMpCoachPrep() }),
        })
        if (!r.ok) {
          if (await handleTrialOrApiError(r)) return false
          setError(await formatApiErrorBody(r))
          return false
        }
        const data = await r.json()
        if (data?.state) {
          applySimulationState(data.state, data)
        }
        return true
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : 'Could not save prep')
        return false
      }
    }

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

        const auth = await getAuthHeaders()
        const r = await fetch(`${API_BASE}/sim`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...auth },
          body: JSON.stringify(payload),
        })
        if (!r.ok) {
          if (await handleTrialOrApiError(r)) return false
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
          if (await handleTrialOrApiError(r)) return false
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
          if (await handleTrialOrApiError(r)) return false
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
      setScreen('new')
      return
    }
    if (token) {
      await syncBillingAccess()
    }
    setScreen('new')
  }

  async function onPurchaseClick() {
    setError('')
    setSuccessMessage('')
    if (!token) {
      setScreen('purchase')
      return
    }
    if (!(await validateSession())) {
      expireSession()
      setScreen('purchase')
      return
    }
    const status = await refreshBillingStatus()
    if (status?.entitled) {
      setSuccessMessage('Your account already has full access.')
      setScreen('purchase')
      return
    }
    if (status && !status.billing_required) {
      setSuccessMessage('Purchase is not required on this server.')
      setScreen('purchase')
      return
    }
    await startCheckout()
  }

  const titleNavRef = useRef({
    onNewSaveClick,
    onLoadSaveClick,
    onPurchaseClick,
    onMultiplayerClick: () => setScreen('multiplayer'),
  })
  titleNavRef.current = { onNewSaveClick, onLoadSaveClick, onPurchaseClick, onMultiplayerClick }

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
      else if (d.action === 'purchase') void titleNavRef.current.onPurchaseClick()
      else if (d.action === 'multiplayer') void titleNavRef.current.onMultiplayerClick()
      else if (d.action === 'screenshots') setShowScreenshotsGallery(true)
      else if (d.action === 'support') setShowSupportContact(true)
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

  async function onContinuePurchase() {
    setError('')
    const ok = devNoFirebase ? await devAuthSubmit() : await firebaseAuthSubmit(authMode)
    if (!ok) return
    const status = await refreshBillingStatus()
    if (status?.entitled) {
      setSuccessMessage('Your account already has full access!')
      return
    }
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
        sessionStorage.setItem(PENDING_CHECKOUT_SESSION_KEY, sessionId)
        await syncBillingAccess(sessionId)
        const auth = await getAuthHeaders()
        if (auth.Authorization) {
          const status = await fetchBillingStatus(API_BASE, auth)
          setBillingStatus(status)
          if (status.entitled) {
            setSuccessMessage('Purchase complete — welcome to Friday Night Dynasty!')
            setTimeout(() => setSuccessMessage(''), 6000)
            setScreen('new')
          } else {
            setError('Payment received — still syncing access. Tap “Refresh purchase status” on the next screen.')
          }
        }
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
    if (billingStatus?.entitled) setShowTrialPurchaseModal(false)
  }, [billingStatus?.entitled])

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
    setMpDashboard(null)
    setMpCommishDashboard(null)
    setMpPendingLeague(null)
    setMpPinTeam(null)
    setMpPinInput('')
    setMpShowTeamPicker(false)
    setMpCoachSetupTeam(null)
    setMpGameContext(null)
  }

  function teamNeedsCoachSetup(league: LeagueListItem, teamName: string): boolean {
    const row = league.teams.find((t) => t.team_name === teamName)
    return Boolean(row && row.coach_setup_complete === false)
  }

  function beginTeamAccess(league: LeagueListItem, teamName: string) {
    setMpPendingLeague(league)
    if (teamNeedsCoachSetup(league, teamName)) {
      setMpCoachSetupTeam(teamName)
      setScreen('multiplayer_coach_setup')
      return
    }
    setMpPinTeam(teamName)
    setMpPinInput('')
  }

  async function loadLeagueDashboard(leagueId: string, teamName: string | null) {
    if (!token) return
    const data = await fetchLeagueDashboard(API_BASE, headers, leagueId, teamName ?? undefined)
    setMpDashboard(data)
    setMpCommishDashboard(null)
    setScreen('league_dashboard')
    setError('')
  }

  async function loadCommishDashboard(leagueId: string) {
    if (!token) return
    const data = await fetchCommishDashboard(API_BASE, headers, leagueId)
    setMpCommishDashboard(data)
    setMpDashboard(null)
    setScreen('commish_dashboard')
    setError('')
  }

  async function onMultiplayerSubmitWeek() {
    const leagueId =
      mpDashboard?.league_id ?? mpCommishDashboard?.league_id ?? mpGameContext?.leagueId
    const teamName =
      mpDashboard?.acting_team_name ??
      mpCommishDashboard?.acting_team_name ??
      mpGameContext?.teamName
    if (!leagueId || !teamName) return
    setMpSubmitBusy(true)
    setError('')
    try {
      if (mpGameContext?.teamName && saveStateRef.current && token) {
        await saveLeagueGame(API_BASE, headers, leagueId, teamName, saveStateRef.current)
      }
      await submitLeagueWeek(API_BASE, headers, leagueId, teamName)
      if (mpCommishDashboard?.league_id === leagueId) {
        const fresh = await fetchCommishDashboard(API_BASE, headers, leagueId)
        setMpCommishDashboard(fresh)
      }
      if (mpDashboard?.league_id === leagueId || !mpCommishDashboard) {
        const dash = await fetchLeagueDashboard(API_BASE, headers, leagueId, teamName)
        setMpDashboard(dash)
      }
      setSuccessMessage('Week submitted. Waiting for the commissioner to advance the league.')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Submit failed')
    } finally {
      setMpSubmitBusy(false)
    }
  }

  async function onMultiplayerUnsubmitWeek() {
    const leagueId =
      mpDashboard?.league_id ?? mpCommishDashboard?.league_id ?? mpGameContext?.leagueId
    const teamName =
      mpDashboard?.acting_team_name ??
      mpCommishDashboard?.acting_team_name ??
      mpGameContext?.teamName
    if (!leagueId || !teamName) return
    setMpSubmitBusy(true)
    setError('')
    try {
      await unsubmitLeagueWeek(API_BASE, headers, leagueId, teamName)
      if (mpCommishDashboard?.league_id === leagueId) {
        const fresh = await fetchCommishDashboard(API_BASE, headers, leagueId)
        setMpCommishDashboard(fresh)
      }
      if (mpDashboard?.league_id === leagueId || !mpCommishDashboard) {
        const dash = await fetchLeagueDashboard(API_BASE, headers, leagueId, teamName)
        setMpDashboard(dash)
      }
      setSuccessMessage('Week unsubmitted — you can keep prepping.')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unsubmit failed')
    } finally {
      setMpSubmitBusy(false)
    }
  }

  async function openMultiplayerDynasty(opts?: {
    leagueId?: string
    teamName?: string
    leagueName?: string
    requireCoachSetup?: boolean
  }) {
    const leagueId =
      opts?.leagueId ?? mpDashboard?.league_id ?? mpCommishDashboard?.league_id
    const teamName =
      opts?.teamName ?? mpDashboard?.acting_team_name ?? mpCommishDashboard?.acting_team_name
    const leagueName =
      opts?.leagueName ?? mpDashboard?.league_name ?? mpCommishDashboard?.league_name ?? 'League'
    if (!leagueId || !teamName) return

    const needsCoachSetup =
      opts?.requireCoachSetup === true ||
      (mpCommishDashboard?.league_id === leagueId && mpCommishDashboard.coach_setup_complete === false)
    if (needsCoachSetup) {
      const leagueForSetup: LeagueListItem =
        mpPendingLeague ??
        ({
          league_id: leagueId,
          name: leagueName,
          status: 'active',
          is_commissioner: Boolean(mpCommishDashboard),
          can_run_league: Boolean(mpCommishDashboard?.can_manage),
          teams: [
            {
              team_name: teamName,
              status: 'active',
              control_mode: 'human',
              role: 'coach',
              coach_setup_complete: false,
            },
          ],
          updated_at: Date.now(),
        } satisfies LeagueListItem)
      setMpPendingLeague(leagueForSetup)
      setMpCoachSetupTeam(teamName)
      setScreen('multiplayer_coach_setup')
      return
    }

    setMpCoachDashBusy(true)
    setError('')
    try {
      const data = await fetchLeagueGame(API_BASE, headers, leagueId, teamName)
      let state = data.state
      try {
        const r = await fetch(`${API_BASE}/sim/hydrate-inbox`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ state }),
        })
        if (r.ok) {
          const hydrated = await r.json()
          if (hydrated?.state) state = hydrated.state
        }
      } catch {
        /* offline */
      }
      try {
        const r2 = await fetch(`${API_BASE}/sim/sync-state`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ state }),
        })
        if (r2.ok) {
          const synced = await r2.json()
          if (synced?.state) state = synced.state
        }
      } catch {
        /* offline */
      }
      try {
        await enrichSaveStateFromLeagueJson(state, API_BASE)
      } catch {
        /* optional */
      }
      const bundle: SaveBundle = {
        state,
        leagueHistory: data.league_history ?? { seasons: [] },
        records: data.records ?? {},
        logos: {},
        stadiums: {},
        helmets: {},
        jerseys: {},
        seasonRecaps: {},
      }
      const id = multiplayerSaveId(leagueId, teamName)
      const saveName = String(state?.save_name ?? leagueName).trim() || 'League'
      await putBrowserSave({ id, saveName, updatedAt: Date.now(), bundle })
      setMpGameContext({ leagueId, teamName })
      setLocalBundle(bundle)
      setSaveId(id)
      setSaveState(state)
      setDynastyLeagueHistory(
        bundle.leagueHistory && typeof bundle.leagueHistory === 'object'
          ? bundle.leagueHistory
          : { seasons: [] },
      )
      setScreen('playing')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Could not open dynasty')
    } finally {
      setMpCoachDashBusy(false)
    }
  }

  async function returnToLeagueDashboard() {
    setError('')
    const ctx =
      mpGameContext ??
      (mpDashboard?.league_id
        ? {
            leagueId: mpDashboard.league_id,
            teamName: mpDashboard.acting_team_name ?? undefined,
            commishMode: false,
          }
        : null)
    if (ctx && saveStateRef.current && token && ctx.teamName) {
      try {
        await saveLeagueGame(API_BASE, headers, ctx.leagueId, ctx.teamName, saveStateRef.current)
      } catch {
        /* best-effort */
      }
    }
    if (ctx) {
      try {
        if (mpCommishDashboard?.league_id === ctx.leagueId && mpCommishDashboard.can_manage !== false) {
          await loadCommishDashboard(ctx.leagueId)
        } else {
          await loadLeagueDashboard(ctx.leagueId, ctx.teamName ?? null)
        }
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : 'Failed to return to league dashboard')
        setScreen('multiplayer')
      }
      setMpGameContext(null)
      return
    }
    setScreen('multiplayer')
  }

  function onMultiplayerClick() {
    setError('')
    if (!token) {
      setScreen('multiplayer')
      return
    }
    void validateSession(token).then((ok) => {
      if (!ok) {
        expireSession()
        setScreen('multiplayer')
        return
      }
      setScreen('multiplayer')
    })
  }

  function onOpenMultiplayerLeague(league: LeagueListItem) {
    setMpPendingLeague(league)
    setMpPinInput('')
    if (league.can_run_league || league.is_commissioner || league.is_platform_owner_view) {
      void loadCommishDashboard(league.league_id).catch((e: unknown) =>
        setError(e instanceof Error ? e.message : 'Failed to open commissioner dashboard'),
      )
      return
    }
    const assignedTeams = league.teams.map((t) => t.team_name).filter((n): n is string => Boolean(n))
    if (assignedTeams.length === 0) {
      setError('Waiting for the commissioner to assign your team.')
      return
    }
    if (assignedTeams.length === 1) {
      beginTeamAccess(league, assignedTeams[0])
      return
    }
    setMpShowTeamPicker(true)
  }

  async function onConfirmTeamPin() {
    if (!mpPendingLeague || !mpPinTeam) return
    setMpPinBusy(true)
    setError('')
    try {
      const ok = await verifyTeamPin(API_BASE, headers, mpPendingLeague.league_id, mpPinTeam, mpPinInput.trim())
      if (!ok) {
        setError('Invalid PIN. Check with your commissioner.')
        return
      }
      setMpPinTeam(null)
      setMpPinInput('')
      await loadLeagueDashboard(mpPendingLeague.league_id, mpPinTeam)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'PIN verification failed')
    } finally {
      setMpPinBusy(false)
    }
  }

  function onOpenLeagueOverview() {
    if (!mpPendingLeague) return
    setMpShowTeamPicker(false)
    void loadLeagueDashboard(mpPendingLeague.league_id, null).catch((e: unknown) =>
      setError(e instanceof Error ? e.message : 'Failed to open league'),
    )
  }

  function onPickTeamForPin(teamName: string) {
    setMpShowTeamPicker(false)
    if (!mpPendingLeague) return
    beginTeamAccess(mpPendingLeague, teamName)
  }

  /* ——— Multiplayer: coach profile setup (first invite / team assignment) ——— */
  if (screen === 'multiplayer_coach_setup' && mpPendingLeague && mpCoachSetupTeam && token) {
    return (
      <>
        <NewSaveFlow
          apiBase={API_BASE}
          headers={headers}
          getAuthHeaders={getAuthHeaders}
          mode="multiplayer_coach"
          leagueId={mpPendingLeague.league_id}
          fixedTeamName={mpCoachSetupTeam}
          defaultCoachName={username}
          onBack={() => {
            setScreen('multiplayer')
            setMpCoachSetupTeam(null)
          }}
          onError={setError}
          onSessionExpired={() => expireSession()}
          onCreated={() => {}}
          onCoachSetupComplete={() => {
            const teamName = mpCoachSetupTeam
            setMpPendingLeague({
              ...mpPendingLeague,
              teams: mpPendingLeague.teams.map((t) =>
                t.team_name === teamName ? { ...t, coach_setup_complete: true } : t,
              ),
            })
            setMpCoachSetupTeam(null)
            setScreen('multiplayer')
            setMpPinTeam(teamName)
            setMpPinInput('')
            setSuccessMessage('Coach profile saved. Enter your team PIN to continue.')
          }}
        />
        {error ? (
          <p className="fnd-error" style={{ maxWidth: 760, margin: '1rem auto' }}>
            {error}
          </p>
        ) : null}
      </>
    )
  }

  /* ——— Multiplayer: create league (same wizard as new dynasty) ——— */
  if (screen === 'multiplayer_create' && token) {
    return (
      <>
        <NewSaveFlow
          apiBase={API_BASE}
          headers={headers}
          getAuthHeaders={getAuthHeaders}
          mode="multiplayer_admin"
          defaultCoachName={username}
          onBack={() => setScreen('multiplayer')}
          onError={setError}
          onSessionExpired={() => expireSession()}
          onCreated={() => {}}
          onLeagueCreated={(_leagueId, _logos, extras) => {
            const pin = extras?.commissioner_pin
            const commishEmail = extras?.commissioner_email
            const selfCommish = !commishEmail || commishEmail === username.trim()
            setSuccessMessage(
              pin
                ? selfCommish
                  ? `League created. Your commissioner team PIN is ${pin} — save it; you will need it each visit.`
                  : `League created. Commissioner ${commishEmail} — share their team PIN: ${pin}`
                : 'League created.',
            )
            setScreen('multiplayer')
          }}
        />
        {error ? (
          <p className="fnd-error" style={{ maxWidth: 760, margin: '1rem auto' }}>
            {error}
          </p>
        ) : null}
        {successMessage ? (
          <p style={{ maxWidth: 760, margin: '1rem auto', color: '#86efac' }}>{successMessage}</p>
        ) : null}
      </>
    )
  }

  /* ——— Multiplayer: league list + league dashboard ——— */
  if (screen === 'multiplayer') {
    return (
      <>
        <MultiplayerLeaguesPage
          apiBase={API_BASE}
          headers={token ? headers : EMPTY_AUTH_HEADERS}
          onBack={goTitle}
          onOpenLeague={onOpenMultiplayerLeague}
          onCreateLeague={() => setScreen('multiplayer_create')}
        />
        {successMessage ? (
          <div className="fnd-success" style={{ maxWidth: 720, margin: '12px auto 0', padding: '0 32px' }}>
            {successMessage}
          </div>
        ) : null}
        {error ? (
          <p className="fnd-error" style={{ maxWidth: 720, margin: '12px auto 0', padding: '0 32px' }}>
            {error}
          </p>
        ) : null}
        {!token ? (
          <div
            style={{
              position: 'fixed',
              inset: 0,
              background: 'rgba(0,0,0,0.65)',
              zIndex: 10000,
              display: 'grid',
              placeItems: 'center',
              padding: '1rem',
            }}
          >
            <div className="fnd-panel" style={{ width: 'min(420px, 100%)', margin: 0 }}>
              <h2 style={{ marginTop: 0 }}>Sign in for multiplayer</h2>
              {devNoFirebase ? (
                <>
                  <p style={{ margin: '0 0 1rem', color: '#9ca3af', fontSize: '0.9rem' }}>
                    Local dev mode: enter your admin email as the coach name (e.g. <strong style={{ color: '#d0d4dc' }}>mxlilly@gmail.com</strong>).
                  </p>
                  <div className="fnd-login-row" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
                    <input
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      placeholder="Coach name / admin email"
                      onKeyDown={(e) => e.key === 'Enter' && void onContinueLoad()}
                    />
                    <button type="button" disabled={authBusy} onClick={() => void onContinueLoad()}>
                      {authBusy ? 'Please wait…' : 'Continue'}
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <p style={{ margin: '0 0 1rem', color: '#9ca3af', fontSize: '0.9rem' }}>
                    Log in with the email your commissioner invited. Purchase is required to join a league.
                  </p>
                  <div className="fnd-login-row" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
                    <input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" />
                    <input
                      type="password"
                      autoComplete={authMode === 'signup' ? 'new-password' : 'current-password'}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Password"
                    />
                    <button type="button" disabled={authBusy} onClick={() => void onContinueLoad()}>
                      {authBusy ? 'Please wait…' : 'Log in'}
                    </button>
                  </div>
                </>
              )}
              <button type="button" className="fnd-back" style={{ marginTop: 12 }} onClick={goTitle}>
                ← Back
              </button>
            </div>
          </div>
        ) : null}
        {mpShowTeamPicker && mpPendingLeague ? (
          <div
            style={{
              position: 'fixed',
              inset: 0,
              background: 'rgba(0,0,0,0.65)',
              zIndex: 10000,
              display: 'grid',
              placeItems: 'center',
              padding: '1rem',
            }}
          >
            <div className="fnd-panel" style={{ width: 'min(420px, 100%)', margin: 0 }}>
              <h2 style={{ marginTop: 0 }}>Select team</h2>
              <p style={{ margin: '0 0 1rem', color: '#9ca3af', fontSize: '0.9rem' }}>
                Choose which school you are coaching in {mpPendingLeague.name}.
              </p>
              {mpPendingLeague.is_commissioner ? (
                <button type="button" className="fnd-title-btn" style={{ maxWidth: '100%', marginBottom: 10 }} onClick={onOpenLeagueOverview}>
                  League dashboard (commissioner)
                </button>
              ) : null}
              {mpPendingLeague.teams
                .map((t) => t.team_name)
                .filter((n): n is string => Boolean(n))
                .map((team) => (
                  <button
                    key={team}
                    type="button"
                    className="fnd-save-row"
                    style={{ width: '100%', marginBottom: 8 }}
                    onClick={() => onPickTeamForPin(team)}
                  >
                    <strong>{team}</strong>
                  </button>
                ))}
              <button type="button" className="fnd-back" onClick={() => setMpShowTeamPicker(false)}>
                Cancel
              </button>
            </div>
          </div>
        ) : null}
        {mpPinTeam && mpPendingLeague ? (
          <div
            style={{
              position: 'fixed',
              inset: 0,
              background: 'rgba(0,0,0,0.65)',
              zIndex: 10001,
              display: 'grid',
              placeItems: 'center',
              padding: '1rem',
            }}
          >
            <div className="fnd-panel" style={{ width: 'min(420px, 100%)', margin: 0 }}>
              <h2 style={{ marginTop: 0 }}>Team PIN</h2>
              <p style={{ margin: '0 0 1rem', color: '#9ca3af', fontSize: '0.9rem' }}>
                Enter the 6-digit PIN for <strong style={{ color: '#d0d4dc' }}>{mpPinTeam}</strong>.
              </p>
              <input
                type="password"
                inputMode="numeric"
                maxLength={6}
                value={mpPinInput}
                onChange={(e) => setMpPinInput(e.target.value.replace(/\D/g, '').slice(0, 6))}
                placeholder="••••••"
                style={{ width: '100%', marginBottom: 12, letterSpacing: '0.35em', fontSize: '1.25rem', textAlign: 'center' }}
              />
              <button
                type="button"
                className="fnd-title-btn"
                style={{ maxWidth: '100%' }}
                disabled={mpPinBusy || mpPinInput.length !== 6}
                onClick={() => void onConfirmTeamPin()}
              >
                {mpPinBusy ? 'Verifying…' : 'Enter league'}
              </button>
              <button
                type="button"
                className="fnd-back"
                style={{ marginTop: 12 }}
                onClick={() => {
                  setMpPinTeam(null)
                  setMpPinInput('')
                }}
              >
                ← Back
              </button>
            </div>
          </div>
        ) : null}
        {error ? (
          <div className="fnd-error" style={{ position: 'fixed', bottom: 16, left: 16, right: 16, zIndex: 9999 }}>
            {error}
          </div>
        ) : null}
      </>
    )
  }

  if (screen === 'commish_dashboard' && mpCommishDashboard) {
    const coachTeam = mpCommishDashboard.acting_team_name ?? null
    const leagueForCoachAccess: LeagueListItem =
      mpPendingLeague ??
      ({
        league_id: mpCommishDashboard.league_id,
        name: mpCommishDashboard.league_name,
        status: 'active',
        is_commissioner: true,
        can_run_league: true,
        teams: mpCommishDashboard.members
          .filter((m) => m.team_name)
          .map((m) => ({
            team_name: m.team_name,
            status: m.status,
            control_mode: m.control_mode,
            role: m.role,
            coach_setup_complete: m.coach_setup_complete,
          })),
        updated_at: Date.now(),
      } satisfies LeagueListItem)
    return (
      <>
        <CommishDashboardPage
          data={mpCommishDashboard}
          onBack={() => {
            setMpCommishDashboard(null)
            setScreen('multiplayer')
          }}
          onRefresh={async () => {
            const fresh = await fetchCommishDashboard(API_BASE, headers, mpCommishDashboard.league_id)
            setMpCommishDashboard(fresh)
          }}
          onSimWeek={async () => {
            setMpCommishSimBusy(true)
            try {
              const res = await commishSimWeek(API_BASE, headers, mpCommishDashboard.league_id)
              return res.message
            } finally {
              setMpCommishSimBusy(false)
            }
          }}
          simWeekBusy={mpCommishSimBusy}
          onInvite={async (email) => {
            return inviteToLeague(API_BASE, headers, mpCommishDashboard.league_id, email)
          }}
          onAssign={async (email, teamName) => {
            const res = await assignTeamByEmail(API_BASE, headers, mpCommishDashboard.league_id, email, teamName)
            return res.pin
          }}
          onResetPin={async (userId) => {
            const res = await resetMemberPin(API_BASE, headers, mpCommishDashboard.league_id, userId)
            return res.pin
          }}
          onSaveSettings={async (patch) => {
            await updateCommishSettings(API_BASE, headers, mpCommishDashboard.league_id, patch)
          }}
          onVacate={async (userId) => {
            await vacateTeamMember(API_BASE, headers, mpCommishDashboard.league_id, userId)
          }}
          onRemove={async (userId) => {
            await removeLeagueMember(API_BASE, headers, mpCommishDashboard.league_id, userId)
          }}
          onRevokeInvite={async (inviteId) => {
            await revokeLeagueInvite(API_BASE, headers, mpCommishDashboard.league_id, inviteId)
          }}
          hasCoachTeam={Boolean(coachTeam)}
          onOpenLeagueHub={
            coachTeam
              ? () => {
                  setMpPendingLeague(leagueForCoachAccess)
                  void loadLeagueDashboard(mpCommishDashboard.league_id, coachTeam)
                }
              : undefined
          }
          onOpenMyDynasty={
            coachTeam
              ? () =>
                  void openMultiplayerDynasty({
                    leagueId: mpCommishDashboard.league_id,
                    teamName: coachTeam,
                    leagueName: mpCommishDashboard.league_name,
                  })
              : undefined
          }
          myDynastyBusy={mpCoachDashBusy}
          onSubmitWeek={coachTeam ? () => void onMultiplayerSubmitWeek() : undefined}
          onUnsubmitWeek={coachTeam ? () => void onMultiplayerUnsubmitWeek() : undefined}
          submitBusy={mpSubmitBusy}
        />
        {error ? (
          <div className="fnd-error" style={{ position: 'fixed', bottom: 16, left: 16, right: 16, zIndex: 9999 }}>
            {error}
          </div>
        ) : null}
      </>
    )
  }

  if (screen === 'league_dashboard' && mpDashboard) {
    const showSubmitControls = Boolean(mpDashboard.acting_team_name)
    return (
      <>
        <LeagueDashboardPage
          data={mpDashboard}
          onBack={() => {
            setMpDashboard(null)
            setScreen('multiplayer')
          }}
          onOpenCoachDashboard={() => void openMultiplayerDynasty()}
          coachDashBusy={mpCoachDashBusy}
          onSubmitWeek={showSubmitControls ? () => void onMultiplayerSubmitWeek() : undefined}
          onUnsubmitWeek={showSubmitControls ? () => void onMultiplayerUnsubmitWeek() : undefined}
          submitBusy={mpSubmitBusy}
          onSendChat={async (body) =>
            postLeagueChat(
              API_BASE,
              headers,
              mpDashboard.league_id,
              body,
              mpDashboard.acting_team_name,
            )
          }
        />
        {error ? (
          <div className="fnd-error" style={{ position: 'fixed', bottom: 16, left: 16, right: 16, zIndex: 9999 }}>
            {error}
          </div>
        ) : null}
      </>
    )
  }

  /* ——— Playing: coach dashboard (single-player / local) ——— */
  if (screen === 'playing' && localBundle && saveState) {
    return (
      <>
        <div style={{ position: 'fixed', top: 12, right: 12, zIndex: 9999, display: 'flex', gap: 8, flexWrap: 'wrap', maxWidth: 'min(100vw - 24px, 520px)', justifyContent: 'flex-end' }}>
          {mpGameContext ? (
            <button type="button" className="teamhome-select" onClick={() => void returnToLeagueDashboard()}>
              ←{' '}
              {mpCommishDashboard?.league_id === mpGameContext.leagueId &&
              mpCommishDashboard.can_manage !== false
                ? 'Commish dashboard'
                : 'League dashboard'}
            </button>
          ) : null}
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
              leagueAdvanceLocked={Boolean(mpGameContext?.leagueId)}
              onSubmitWeek={
                mpGameContext?.teamName ? () => void onMultiplayerSubmitWeek() : undefined
              }
              onUnsubmitWeek={
                mpGameContext?.teamName ? () => void onMultiplayerUnsubmitWeek() : undefined
              }
              weekSubmitted={Boolean(
                mpDashboard?.your_status?.submitted ?? mpCommishDashboard?.your_status?.submitted,
              )}
              canUnsubmitWeek={
                (mpDashboard?.your_status?.can_unsubmit ??
                  mpCommishDashboard?.your_status?.can_unsubmit) !== false
              }
              submitWeekBusy={mpSubmitBusy}
              onReturnToLeagueHub={
                mpGameContext?.leagueId ? () => void returnToLeagueDashboard() : undefined
              }
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
        {showTrialPurchaseModal ? (
          <div
            style={{
              position: 'fixed',
              inset: 0,
              background: 'rgba(0,0,0,0.65)',
              zIndex: 10001,
              display: 'grid',
              placeItems: 'center',
              padding: '1rem',
            }}
          >
            <div
              className="fnd-panel"
              style={{ width: 'min(520px, 100%)', margin: 0, border: '1px solid #3d4654' }}
            >
              <h2 style={{ marginTop: 0 }}>Season complete!</h2>
              <p style={{ margin: '0 0 1rem', color: '#9ca3af', fontSize: '0.9rem' }}>
                You&apos;ve finished your free season — from preseason through schedule release. Purchase once to
                continue your dynasty into year two and beyond.
              </p>
              {billingChecking ? (
                <p style={{ color: '#9ca3af', fontSize: '0.9rem' }}>Checking purchase status…</p>
              ) : (
                <>
                  <button
                    type="button"
                    className="fnd-title-btn"
                    style={{ maxWidth: '100%', marginBottom: 10 }}
                    disabled={billingBusy}
                    onClick={() => void startCheckout()}
                  >
                    {billingBusy ? 'Redirecting to checkout…' : 'Buy now — secure checkout'}
                  </button>
                  <button
                    type="button"
                    className="teamhome-select"
                    style={{ maxWidth: '100%' }}
                    disabled={billingBusy}
                    onClick={() => void syncBillingAccess()}
                  >
                    {billingBusy ? 'Please wait…' : 'Already paid? Refresh purchase status'}
                  </button>
                </>
              )}
              <button
                type="button"
                className="teamhome-select"
                style={{ marginTop: 12, maxWidth: '100%' }}
                onClick={() => setShowTrialPurchaseModal(false)}
              >
                Keep browsing schedule
              </button>
              <button
                type="button"
                className="fnd-support-link fnd-support-link--panel"
                style={{ marginTop: 12 }}
                onClick={() => setShowSupportContact(true)}
              >
                Need help or a refund?
              </button>
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
        <>
          <iframe
            className="fnd-title-iframe"
            title="Friday Night Dynasty"
            src={`${import.meta.env.BASE_URL}fnd_homepage.html?v=20260630b`}
          />
          <button
            type="button"
            className="fnd-support-link"
            onClick={() => setShowSupportContact(true)}
          >
            Help &amp; support
          </button>
        </>
      ) : (
        <div className="fnd-title-inner">
        <h1 className="fnd-title-heading">Friday Night Dynasty</h1>

        {screen === 'load' && (
          <div className="fnd-panel">
            <button type="button" className="fnd-back" onClick={goTitle}>
              ← Back
            </button>
            <h2>Load save</h2>
            <button
              type="button"
              className="fnd-support-link fnd-support-link--panel"
              onClick={() => setShowSupportContact(true)}
            >
              Help &amp; support — questions, bugs, refunds
            </button>
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

        {screen === 'purchase' && !token && (
          <div className="fnd-panel">
            <button type="button" className="fnd-back" onClick={goTitle}>
              ← Back
            </button>
            <h2>Purchase</h2>
            <p style={{ margin: '0 0 1rem', color: '#9ca3af', fontSize: '0.9rem' }}>
              Sign in, then complete secure checkout to unlock the full game after your free season.
            </p>
            {devNoFirebase ? (
              <div className="fnd-login-row" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
                <input
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Coach name"
                  onKeyDown={(e) => e.key === 'Enter' && void onContinuePurchase()}
                />
                <button type="button" disabled={authBusy} onClick={() => void onContinuePurchase()}>
                  {authBusy ? 'Please wait…' : 'Continue'}
                </button>
              </div>
            ) : (
              <>
                <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
                  <button
                    type="button"
                    className={authMode === 'login' ? 'fnd-title-btn' : 'fnd-back'}
                    style={{ flex: 1, maxWidth: 'none', margin: 0 }}
                    onClick={() => setAuthMode('login')}
                  >
                    Log in
                  </button>
                  <button
                    type="button"
                    className={authMode === 'signup' ? 'fnd-title-btn' : 'fnd-back'}
                    style={{ flex: 1, maxWidth: 'none', margin: 0 }}
                    onClick={() => setAuthMode('signup')}
                  >
                    Sign up
                  </button>
                </div>
                <div className="fnd-login-row" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
                  <input
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="Email"
                    type="email"
                    autoComplete="email"
                  />
                  <input
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Password"
                    type="password"
                    autoComplete={authMode === 'signup' ? 'new-password' : 'current-password'}
                    onKeyDown={(e) => e.key === 'Enter' && void onContinuePurchase()}
                  />
                  {authMode === 'signup' ? (
                    <SignupTermsConsent checked={termsAccepted} onChange={setTermsAccepted} />
                  ) : null}
                  <button
                    type="button"
                    disabled={authBusy || (authMode === 'signup' && !termsAccepted)}
                    onClick={() => void onContinuePurchase()}
                  >
                    {authBusy ? 'Please wait…' : authMode === 'signup' ? 'Create account' : 'Log in'}
                  </button>
                </div>
              </>
            )}
            <button
              type="button"
              className="fnd-support-link fnd-support-link--panel"
              style={{ marginTop: 12 }}
              onClick={() => setShowSupportContact(true)}
            >
              Need help or a refund?
            </button>
          </div>
        )}

        {screen === 'purchase' && token ? (
          <div className="fnd-panel">
            <button type="button" className="fnd-back" onClick={goTitle}>
              ← Back
            </button>
            <h2>Purchase</h2>
            <p style={{ margin: '0 0 1rem', color: '#9ca3af', fontSize: '0.9rem' }}>
              One-time purchase unlocks year two and beyond for{' '}
              <strong style={{ color: '#d0d4dc' }}>{username}</strong>.
            </p>
            {billingChecking ? (
              <p style={{ color: '#9ca3af', fontSize: '0.9rem' }}>Checking purchase status…</p>
            ) : billingStatus?.entitled ? (
              <p style={{ color: '#86efac', fontSize: '0.9rem', margin: 0 }}>
                This account already has full access.
              </p>
            ) : billingStatus && !billingStatus.billing_required ? (
              <p style={{ color: '#9ca3af', fontSize: '0.9rem', margin: 0 }}>
                Purchase is not required on this server.
              </p>
            ) : (
              <>
                <button
                  type="button"
                  className="fnd-title-btn"
                  style={{ maxWidth: '100%', marginBottom: 10 }}
                  disabled={billingBusy}
                  onClick={() => void startCheckout()}
                >
                  {billingBusy ? 'Redirecting to checkout…' : 'Buy now — secure checkout'}
                </button>
                <button
                  type="button"
                  className="teamhome-select"
                  style={{ maxWidth: '100%' }}
                  disabled={billingBusy}
                  onClick={() => void syncBillingAccess()}
                >
                  {billingBusy ? 'Please wait…' : 'Already paid? Refresh purchase status'}
                </button>
              </>
            )}
            <button
              type="button"
              className="fnd-support-link fnd-support-link--panel"
              style={{ marginTop: 12 }}
              onClick={() => setShowSupportContact(true)}
            >
              Need help or a refund?
            </button>
          </div>
        ) : null}

        {screen === 'new' && !token && (
          <div className="fnd-panel">
            <button type="button" className="fnd-back" onClick={goTitle}>
              ← Back
            </button>
            <h2>New dynasty</h2>
            <button
              type="button"
              className="fnd-support-link fnd-support-link--panel"
              onClick={() => setShowSupportContact(true)}
            >
              Help &amp; support — questions, bugs, refunds
            </button>
            <p style={{ margin: '0 0 1rem', color: '#9ca3af', fontSize: '0.9rem' }}>
              {devNoFirebase
                ? 'Local dev mode: enter a coach name (no Firebase). Dynasties save in this browser and on the API when you create a save.'
                : 'Log in to create a new dynasty. Your first full season is free — purchase to continue after schedule release.'}
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
              You&apos;ve used your free season on{' '}
              <strong style={{ color: '#d0d4dc' }}>{username}</strong>. Purchase once to continue your dynasty and
              start new saves.
            </p>
            {billingChecking ? (
              <p style={{ color: '#9ca3af', fontSize: '0.9rem' }}>Checking purchase status…</p>
            ) : (
              <>
                <button
                  type="button"
                  className="fnd-title-btn"
                  style={{ maxWidth: '100%', marginBottom: 10 }}
                  disabled={billingBusy}
                  onClick={() => void startCheckout()}
                >
                  {billingBusy ? 'Redirecting to checkout…' : 'Buy now — secure checkout'}
                </button>
                <button
                  type="button"
                  className="teamhome-select"
                  style={{ maxWidth: '100%' }}
                  disabled={billingBusy}
                  onClick={() => void syncBillingAccess()}
                >
                  {billingBusy ? 'Please wait…' : 'Already paid? Refresh purchase status'}
                </button>
              </>
            )}
            <button
              type="button"
              className="fnd-support-link fnd-support-link--panel"
              style={{ marginTop: 12 }}
              onClick={() => setShowSupportContact(true)}
            >
              Need help or a refund?
            </button>
          </div>
        ) : screen === 'new' && token ? (
          <>
            {onFreeTrial ? (
              <p
                style={{
                  margin: '0 0 1rem',
                  color: '#9ca3af',
                  fontSize: '0.9rem',
                  maxWidth: 560,
                }}
              >
                Your <strong style={{ color: '#d0d4dc' }}>first full season is free</strong> — preseason through
                schedule release. Purchase afterward to continue into year two.
              </p>
            ) : null}
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
          </>
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
      <SupportContactModal
        open={showSupportContact}
        onClose={() => setShowSupportContact(false)}
        apiBase={API_BASE}
        getAuthHeaders={getAuthHeaders}
        defaultEmail={supportDefaultEmail}
        onSuccess={(msg) => {
          setSuccessMessage(msg)
          setTimeout(() => setSuccessMessage(''), 8000)
        }}
        onError={(msg) => setError(msg)}
      />
    </div>
  )
}
