import { useEffect, useMemo, useRef, useState } from 'react'
import './index.css'
import './TitleScreen.css'
import { NewSaveFlow } from './NewSaveFlow'
import TeamHomePage from './TeamHomePage'
import { exportSaveZip, importSaveZip, type SaveBundle } from './saveBundle'
import { LocalAssetsProvider } from './LocalAssetsContext'

/** In dev, use Vite proxy (/api → backend). Production: set VITE_API_BASE or default below. */
/** Dev: Vite proxy. Production build served from the same host as FastAPI → empty string (same-origin). */
const API_BASE = import.meta.env.DEV
  ? '/api'
  : ((import.meta as any).env?.VITE_API_BASE ?? '')

const USE_LOCAL_BUNDLES = String((import.meta as any).env?.VITE_USE_LOCAL_BUNDLES ?? '').toLowerCase() === 'true'

/** Tokens live in the server DB; redeploys / new DB invalidate old browser tokens. */
const STALE_SESSION_MSG =
  'Your session expired. This often happens after a server restart or deploy. Enter your coach name and tap Continue to sign in again.'

async function formatApiErrorBody(r: Response): Promise<string> {
  const raw = await r.text()
  try {
    const j = JSON.parse(raw) as { detail?: unknown }
    const d = j.detail
    if (typeof d === 'string') return d
    if (Array.isArray(d))
      return d.map((x: any) => (typeof x?.msg === 'string' ? x.msg : JSON.stringify(x))).join('; ')
  } catch {
    /* use raw */
  }
  return raw || `Request failed (${r.status})`
}

function apiConnectionHint() {
  return ' Start the API: python -m uvicorn backend.app:app --host 127.0.0.1 --port 8001'
}

/** True when save JSON still has preseason stages to complete (even if season_phase is missing or wrong). */
function saveHasActivePreseasonFlow(state: any): boolean {
  const stages = state?.preseason_stages
  const idx = Number(state?.preseason_stage_index ?? 0)
  if (!Array.isArray(stages) || stages.length === 0) return false
  if (idx >= stages.length) return false
  const p = String(state?.season_phase ?? '').toLowerCase()
  if (p === 'playoffs' || p === 'offseason' || p === 'done') return false
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
type BrowserAutosaveRecord = {
  savedAt: number
  saveId: string
  saveName: string
  payload: SaveBundle
}

const AUTOSAVE_DB = 'fnd-browser-saves'
const AUTOSAVE_STORE = 'autosaves'
const AUTOSAVE_KEY = 'latest'

function openAutosaveDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof window === 'undefined' || !('indexedDB' in window)) {
      reject(new Error('IndexedDB is not available in this browser.'))
      return
    }
    const req = window.indexedDB.open(AUTOSAVE_DB, 1)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(AUTOSAVE_STORE)) {
        db.createObjectStore(AUTOSAVE_STORE)
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error ?? new Error('Failed to open autosave database'))
  })
}

async function writeAutosave(record: BrowserAutosaveRecord): Promise<void> {
  const db = await openAutosaveDb()
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(AUTOSAVE_STORE, 'readwrite')
    tx.objectStore(AUTOSAVE_STORE).put(record, AUTOSAVE_KEY)
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error ?? new Error('Failed to write autosave'))
  })
  db.close()
}

async function readAutosave(): Promise<BrowserAutosaveRecord | null> {
  const db = await openAutosaveDb()
  const out = await new Promise<BrowserAutosaveRecord | null>((resolve, reject) => {
    const tx = db.transaction(AUTOSAVE_STORE, 'readonly')
    const req = tx.objectStore(AUTOSAVE_STORE).get(AUTOSAVE_KEY)
    req.onsuccess = () => resolve((req.result as BrowserAutosaveRecord | undefined) ?? null)
    req.onerror = () => reject(req.error ?? new Error('Failed to read autosave'))
  })
  db.close()
  return out
}

export default function App() {
  const [token, setToken] = useState<string>(() => localStorage.getItem('fnd_token') ?? '')
  const [username, setUsername] = useState('alice')
  const [screen, setScreen] = useState<Screen>('title')
  const [saves, setSaves] = useState<SaveListItem[]>([])
  const [saveId, setSaveId] = useState<string>('')
  const [saveState, setSaveState] = useState<any>(null)
  const [localBundle, setLocalBundle] = useState<SaveBundle | null>(null)
  const [error, setError] = useState<string>('')
  const [crashReportText, setCrashReportText] = useState<string>('')
  const [lastCrashPromptKey, setLastCrashPromptKey] = useState<string>('')
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string>('')
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
  const inLocalRuntime = Boolean(localBundle)

  const saveStateRef = useRef<any>(null)
  saveStateRef.current = saveState

  const headers = useMemo((): Record<string, string> => {
    if (!token) return {}
    return { Authorization: `Bearer ${token}` }
  }, [token])

  function clearStaleSession() {
    localStorage.removeItem('fnd_token')
    setToken('')
  }

  /** If response is 401, clears stored token and sets a friendly message. Returns true = caller should stop. */
  async function consumeUnauthorized(r: Response): Promise<boolean> {
    if (r.status !== 401) return false
    clearStaleSession()
    setError(STALE_SESSION_MSG)
    return true
  }

  async function loadLocalBundleFromZip(file: File) {
    setError('')
    setSuccessMessage('')
    try {
      const bundle = await importSaveZip(file)
      setLocalBundle(bundle)
      setSaveId('__local__')
      setSaveState(bundle.state)
      setScreen('playing')
      setSuccessMessage('Loaded save from computer.')
      setTimeout(() => setSuccessMessage(''), 2500)
    } catch (e: any) {
      setError(e?.message ? String(e.message) : 'Failed to import save zip')
    }
  }

  function downloadJson(filename: string, payload: unknown) {
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 250)
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

  async function exportBackupFile() {
    const live = saveStateRef.current
    if (!live) {
      setError('No save state loaded to export.')
      return
    }
    const payload: SaveBundle = localBundle
      ? { ...localBundle, state: live }
      : { state: live, leagueHistory: { seasons: [] }, records: {}, logos: {}, seasonRecaps: {} }
    const name = String(live?.save_name ?? 'dynasty').trim() || 'dynasty'
    downloadJson(
      `${name.replaceAll(' ', '_')}_backup.json`,
      {
        format: 'fnd-backup-v1',
        exported_at: new Date().toISOString(),
        payload,
      },
    )
    setSuccessMessage('Backup downloaded.')
    setTimeout(() => setSuccessMessage(''), 2500)
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

  async function loadFromComputerFile(file: File) {
    const low = String(file.name || '').toLowerCase()
    if (low.endsWith('.zip')) {
      await loadLocalBundleFromZip(file)
      return
    }
    const text = await file.text()
    const parsed = JSON.parse(text)
    const bundle = normalizeImportedBundle(parsed)
    setLocalBundle(bundle)
    setSaveId('__local__')
    setSaveState(bundle.state)
    setScreen('playing')
    setError('')
    setSuccessMessage('Loaded save from computer.')
    setTimeout(() => setSuccessMessage(''), 2500)
  }

  async function restoreAutosave() {
    setError('')
    try {
      const rec = await readAutosave()
      if (!rec?.payload?.state) {
        setError('No browser autosave found yet.')
        return
      }
      setLocalBundle(rec.payload)
      setSaveId('__local__')
      setSaveState(rec.payload.state)
      setScreen('playing')
      setSuccessMessage(`Restored autosave from ${new Date(rec.savedAt).toLocaleString()}.`)
      setTimeout(() => setSuccessMessage(''), 3000)
    } catch (e: any) {
      setError(e?.message ? String(e.message) : 'Failed to restore autosave')
    }
  }

  async function exportLocalBundleZip() {
    if (!localBundle) {
      setError('No local bundle loaded.')
      return
    }
    try {
      const blob = await exportSaveZip({ ...localBundle, state: saveStateRef.current })
      const name = String(saveStateRef.current?.save_name ?? 'dynasty').trim() || 'dynasty'
      const a = document.createElement('a')
      const url = URL.createObjectURL(blob)
      a.href = url
      a.download = `${name.replaceAll(' ', '_')}.zip`
      document.body.appendChild(a)
      a.click()
      a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 250)
      setSuccessMessage('Exported save zip.')
      setTimeout(() => setSuccessMessage(''), 2500)
    } catch (e: any) {
      setError(e?.message ? String(e.message) : 'Failed to export save zip')
    }
  }

  async function devLogin() {
    setError('')
    try {
      const r = await fetch(`${API_BASE}/auth/dev-login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username }),
      })
      if (!r.ok) {
        setError(await formatApiErrorBody(r))
        return false
      }
      const data = await r.json()
      localStorage.setItem('fnd_token', data.token)
      setToken(data.token)
      return true
    } catch (e: any) {
      const msg = e?.message ? String(e.message) : 'network error'
      setError(
        msg.toLowerCase().includes('fetch') || msg.toLowerCase().includes('network') || msg.toLowerCase().includes('failed')
          ? `Login failed (${msg}).${apiConnectionHint()}`
          : `Login failed: ${msg}`,
      )
      return false
    }
  }

  async function loadSaves() {
    setError('')
    try {
      const r = await fetch(`${API_BASE}/saves`, { headers })
      if (!r.ok) {
        if (await consumeUnauthorized(r)) return
        setError(await formatApiErrorBody(r))
        return
      }
      const data = await r.json()
      setSaves(data)
    } catch (e: any) {
      setError(`Could not load saves (${e?.message ?? 'network error'}).${apiConnectionHint()}`)
    }
  }


  async function loadSave(id: string) {
    setError('')
    try {
      const r = await fetch(`${API_BASE}/saves/${id}`, { headers })
      if (!r.ok) {
        if (await consumeUnauthorized(r)) return
        setError(await formatApiErrorBody(r))
        return
      }
      const data = await r.json()
      setLocalBundle(null)
      setSaveId(id)
      setSaveState(data.state)
      setScreen('playing')
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
      const r = await fetch(`${API_BASE}/saves/${id}`, { method: 'DELETE', headers })
      if (!r.ok) {
        if (await consumeUnauthorized(r)) {
          setDeletingId(null)
          return
        }
        setError((await formatApiErrorBody(r)) || 'Delete failed')
        setDeletingId(null)
        return
      }
      await loadSaves()
      setSuccessMessage(`"${saveName}" deleted.`)
      setTimeout(() => setSuccessMessage(''), 3000)
      if (saveId === id) {
        setSaveId('')
        setSaveState(null)
        setScreen('load')
      }
    } catch (e: any) {
      setError(`Delete failed (${e?.message ?? 'network error'}).${apiConnectionHint()}`)
    } finally {
      setDeletingId(null)
    }
  }

  async function simWeek(opts?: {
    playbook?: { offensive_playbook: string; defensive_playbook: string }
    gamePlan?: { offensive: Record<string, { play_id: string; pct: number }[]>; defensive: Record<string, { play_id: string; pct: number }[]> }
    depthChart?: Record<string, string[]>
    positionChanges?: { player_name: string; position: string; secondary_position?: string | null }[]
    goals?: { win_goal: number; stage_goal: string }
    playoffsSim?: boolean
    seasonFinish?: boolean
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
      coach_dev_allocations?: Record<string, number>
    }
  }): Promise<boolean> {
    if (!saveId) {
      setError('No save is loaded. Return to the load screen and open your dynasty again.')
      return false
    }
    setError('')
    const live = saveStateRef.current
    const livePhase = String(live?.season_phase ?? '').toLowerCase()

    if (localBundle) {
      // Stateless mode: send current bundle state to the API and receive updated state (and updated history/records/recaps).
      try {
        const payload: any = { state: live, league_history: localBundle.leagueHistory, records: localBundle.records }
        if (opts?.seasonFinish) payload.kind = 'season-finish'
        // Full auto-playoff must win over generic "in playoffs → one round" (otherwise full sim never runs locally).
        else if (opts?.playoffsSim) payload.kind = 'playoffs-sim'
        else if (livePhase === 'playoffs') payload.kind = 'playoffs-sim-round'
        if (livePhase === 'offseason') payload.kind = 'offseason-advance'
        if (!payload.kind) payload.kind = 'week-sim'

        if (payload.kind === 'offseason-advance') payload.body = opts?.offseasonBody ?? {}
        if (payload.kind === 'week-sim' || payload.kind === 'season-finish') payload.body = null

        // Preseason advances + finish season are driven by existing UI flows that call simWeek()
        // through the same path; map them based on structural phase detection.
        const phaseLower = String(live?.season_phase ?? '').toLowerCase()
        const structDone = preseasonStructurallyComplete(live)
        const inPreseason =
          !structDone &&
          (Boolean(opts?.forcePreseasonAdvance) || phaseLower === 'preseason' || saveHasActivePreseasonFlow(live))
        if (inPreseason) {
          payload.kind = 'preseason-advance'
          if (opts?.playbook) payload.body = opts.playbook
          else if (opts?.gamePlan) payload.body = { game_plan: opts.gamePlan }
          else if (opts?.depthChart) payload.body = { depth_chart: opts.depthChart }
          else if (opts?.positionChanges !== undefined) payload.body = { position_changes: opts.positionChanges }
          else if (opts?.goals) payload.body = { goals: opts.goals }
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
          maybeTriggerBackupReminder(live, data.state)
          setSaveState(data.state)
        }
        if (data?.league_history || data?.records || data?.season_recaps) {
          setLocalBundle((prev) => {
            if (!prev) return prev
            return {
              ...prev,
              state: data.state ?? prev.state,
              leagueHistory: data.league_history ?? prev.leagueHistory,
              records: data.records ?? prev.records,
              seasonRecaps: data.season_recaps ? { ...(prev.seasonRecaps ?? {}), ...data.season_recaps } : prev.seasonRecaps,
            }
          })
        }
        return true
      } catch (e: any) {
        setError(`Request failed (${e?.message ?? 'network error'}).${apiConnectionHint()}`)
        return false
      }
    }

    if (opts?.seasonFinish) {
      try {
        const r = await fetch(`${API_BASE}/saves/${saveId}/season/finish`, { method: 'POST', headers })
        if (!r.ok) {
          if (await consumeUnauthorized(r)) return false
          setError((await formatApiErrorBody(r)) || 'Failed to advance season')
          return false
        }
        const data = await r.json()
        if (data?.state) {
          maybeTriggerBackupReminder(live, data.state)
          setSaveState(data.state)
        }
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
        if (data?.state) {
          maybeTriggerBackupReminder(live, data.state)
          setSaveState(data.state)
        }
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
        if (data?.state) {
          maybeTriggerBackupReminder(live, data.state)
          setSaveState(data.state)
        }
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
        if (data?.state) {
          maybeTriggerBackupReminder(live, data.state)
          setSaveState(data.state)
        }
        else await loadSave(saveId)
        return true
      } catch (e: any) {
        setError(`Request failed (${e?.message ?? 'network error'}).${apiConnectionHint()}`)
        return false
      }
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
      if (data?.state) {
        maybeTriggerBackupReminder(live, data.state)
        setSaveState(data.state)
      } else {
        await loadSave(saveId)
      }
      return true
    } catch (e: any) {
      setError(`Request failed (${e?.message ?? 'network error'}).${apiConnectionHint()}`)
      return false
    }
  }

  async function onLoadSaveClick() {
    setError('')
    setScreen('load')
    if (!USE_LOCAL_BUNDLES && token) await loadSaves()
  }

  async function onNewSaveClick() {
    setError('')
    setScreen('new')
  }

  const titleNavRef = useRef({ onNewSaveClick, onLoadSaveClick })
  titleNavRef.current = { onNewSaveClick, onLoadSaveClick }

  useEffect(() => {
    function onMessage(e: MessageEvent) {
      if (e.origin !== window.location.origin) return
      const d = e.data as { type?: string; action?: string } | null
      if (!d || d.type !== 'fnd-title') return
      if (d.action === 'new') void titleNavRef.current.onNewSaveClick()
      else if (d.action === 'load') void titleNavRef.current.onLoadSaveClick()
    }
    window.addEventListener('message', onMessage)
    return () => window.removeEventListener('message', onMessage)
  }, [])

  async function onContinueLoad() {
    const ok = await devLogin()
    if (ok) await loadSaves()
  }

  async function onContinueNew() {
    await devLogin()
  }

  useEffect(() => {
    if (!USE_LOCAL_BUNDLES && token && screen === 'load') loadSaves()
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
        : { state: live, leagueHistory: { seasons: [] }, records: {}, logos: {}, seasonRecaps: {} }
      const rec: BrowserAutosaveRecord = {
        savedAt: Date.now(),
        saveId: saveId || '__unknown__',
        saveName: String(live?.save_name ?? 'dynasty'),
        payload,
      }
      void writeAutosave(rec)
        .then(() => setLastAutosaveAt(rec.savedAt))
        .catch((e: any) => setError(e?.message ? String(e.message) : 'Autosave failed'))
    }, 1200)
    return () => window.clearTimeout(timer)
  }, [autosaveEnabled, localBundle, saveId, saveState, screen])

  function goTitle() {
    setScreen('title')
    setError('')
  }

  /* ——— Playing: league dashboard (same data as before) ——— */
  if (screen === 'playing' && (token || (USE_LOCAL_BUNDLES && localBundle))) {
    return (
      <>
        <div style={{ position: 'fixed', top: 12, right: 12, zIndex: 9999, display: 'flex', gap: 8 }}>
          <button type="button" className="teamhome-select" onClick={() => setAutosaveEnabled((v) => !v)} title="Toggle browser autosave">
            Autosave: {autosaveEnabled ? 'On' : 'Off'}
          </button>
          <button type="button" className="teamhome-select" onClick={exportBackupFile} title="Download JSON backup to your computer">
            Backup Save
          </button>
          {inLocalRuntime ? (
            <button type="button" className="teamhome-select" onClick={exportLocalBundleZip} title="Download updated save zip">
              Export ZIP
            </button>
          ) : null}
        </div>
        <LocalAssetsProvider bundle={localBundle}>
          <TeamHomePage
              apiBase={API_BASE}
              headers={inLocalRuntime ? {} : headers}
              saveId={saveId}
              saveState={saveState}
              onMainMenu={goTitle}
              onSimWeek={simWeek}
              onSaveState={setSaveState}
              onError={setError}
              backupReminderFrequency={backupReminderFrequency}
              onBackupReminderFrequencyChange={setBackupReminderFrequency}
              onBackupNow={() => void exportBackupFile()}
              leagueHistory={inLocalRuntime && localBundle ? localBundle.leagueHistory : undefined}
              seasonRecaps={inLocalRuntime && localBundle ? localBundle.seasonRecaps : undefined}
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
                    void exportBackupFile()
                    setShowBackupPrompt(false)
                  }}
                >
                  Backup now
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
          src={`${import.meta.env.BASE_URL}fnd_homepage.html`}
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
            <div style={{ marginBottom: '1rem', padding: '0.75rem', border: '1px solid #2f3440', borderRadius: 8 }}>
              <p style={{ margin: '0 0 0.5rem', color: '#9ca3af', fontSize: '0.9rem' }}>
                Restore from computer (.json backup or .zip save), or load your latest browser autosave.
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
                  Load Browser Autosave
                </button>
              </div>
              {lastAutosaveAt ? (
                <p style={{ margin: '0.5rem 0 0', color: '#7f8794', fontSize: '0.8rem' }}>
                  Last autosave this session: {new Date(lastAutosaveAt).toLocaleString()}
                </p>
              ) : null}
            </div>
            {USE_LOCAL_BUNDLES ? (
              <>
                <p style={{ margin: '0 0 1rem', color: '#9ca3af', fontSize: '0.9rem' }}>
                  Upload a dynasty save zip (contains JSON + logos). You’ll export a new zip when you’re done playing.
                </p>
                <input
                  type="file"
                  accept=".zip,application/zip"
                  onChange={(e) => {
                    const f = e.target.files?.[0]
                    if (f) void loadLocalBundleFromZip(f)
                  }}
                />
              </>
            ) : !token ? (
              <>
                <p style={{ margin: '0 0 1rem', color: '#9ca3af', fontSize: '0.9rem' }}>Enter coach name to see your saves.</p>
                <div className="fnd-login-row">
                  <input
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="Coach name"
                    onKeyDown={(e) => e.key === 'Enter' && onContinueLoad()}
                  />
                  <button type="button" onClick={onContinueLoad}>
                    Continue
                  </button>
                </div>
              </>
            ) : (
              <>
                <p style={{ margin: '0 0 1rem', color: '#9ca3af', fontSize: '0.85rem' }}>
                  Signed in as <strong style={{ color: '#d0d4dc' }}>{username}</strong>
                </p>
                <button type="button" className="fnd-title-btn" style={{ maxWidth: '100%', marginBottom: '1rem' }} onClick={loadSaves}>
                  Refresh list
                </button>
                {saves.length === 0 ? (
                  <p style={{ color: '#9ca3af', margin: 0 }}>No saves yet. Use New Save from the main menu.</p>
                ) : (
                  saves.map((s) => (
                    <div key={s.save_id} className="fnd-save-row-wrap">
                      <button type="button" className="fnd-save-row" onClick={() => loadSave(s.save_id)}>
                        <strong>{s.save_name}</strong>
                        <small>
                          {new Date(s.updated_at * 1000).toLocaleString()} · {s.save_id.slice(0, 8)}…
                        </small>
                      </button>
                      <button
                        type="button"
                        className="fnd-save-delete"
                        onClick={(e) => deleteSave(s.save_id, s.save_name, e)}
                        disabled={deletingId === s.save_id}
                        title="Delete this dynasty"
                      >
                        {deletingId === s.save_id ? 'Deleting…' : 'Delete'}
                      </button>
                    </div>
                  ))
                )}
              </>
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
              Sign in with a coach account to set up your save.
            </p>
            <div className="fnd-login-row">
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Coach / username"
                onKeyDown={(e) => e.key === 'Enter' && onContinueNew()}
              />
              <button type="button" onClick={onContinueNew}>
                Continue
              </button>
            </div>
          </div>
        )}

        {screen === 'new' && token ? (
          <NewSaveFlow
            apiBase={API_BASE}
            headers={headers}
            onBack={goTitle}
            onError={setError}
            defaultCoachName={username}
            onCreated={async (id) => {
              await loadSaves()
              await loadSave(id)
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
    </div>
  )
}
