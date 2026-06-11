import type { SaveBundle } from './saveBundle'

const DB_NAME = 'fnd-browser-saves'
const DB_VERSION = 2
const STORE_DYNASTIES = 'dynasties'
const STORE_AUTOSAVES = 'autosaves'

export type BrowserSaveRecord = {
  id: string
  saveName: string
  updatedAt: number
  bundle: SaveBundle
}

export function isBrowserSaveId(saveId: string): boolean {
  return saveId === '__local__' || saveId.startsWith('b_')
}

/** Browser saves and unauthenticated sessions use stateless /sim/* routes. */
export function shouldUseSimApi(saveId: string, headers: Record<string, string>): boolean {
  return isBrowserSaveId(saveId) || !headers?.Authorization
}

export function createBrowserSaveId(): string {
  const raw =
    typeof crypto !== 'undefined' && 'randomUUID' in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`
  return `b_${raw}`
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof window === 'undefined' || !('indexedDB' in window)) {
      reject(new Error('IndexedDB is not available in this browser.'))
      return
    }
    const req = window.indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE_DYNASTIES)) {
        db.createObjectStore(STORE_DYNASTIES, { keyPath: 'id' })
      }
      if (!db.objectStoreNames.contains(STORE_AUTOSAVES)) {
        db.createObjectStore(STORE_AUTOSAVES)
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error ?? new Error('Failed to open save database'))
  })
}

export async function listBrowserSaves(): Promise<BrowserSaveRecord[]> {
  const db = await openDb()
  const rows = await new Promise<BrowserSaveRecord[]>((resolve, reject) => {
    const tx = db.transaction(STORE_DYNASTIES, 'readonly')
    const req = tx.objectStore(STORE_DYNASTIES).getAll()
    req.onsuccess = () => resolve((req.result as BrowserSaveRecord[]) ?? [])
    req.onerror = () => reject(req.error ?? new Error('Failed to list saves'))
  })
  db.close()
  return rows.sort((a, b) => b.updatedAt - a.updatedAt)
}

export async function getBrowserSave(id: string): Promise<BrowserSaveRecord | null> {
  const db = await openDb()
  const row = await new Promise<BrowserSaveRecord | null>((resolve, reject) => {
    const tx = db.transaction(STORE_DYNASTIES, 'readonly')
    const req = tx.objectStore(STORE_DYNASTIES).get(id)
    req.onsuccess = () => resolve((req.result as BrowserSaveRecord | undefined) ?? null)
    req.onerror = () => reject(req.error ?? new Error('Failed to read save'))
  })
  db.close()
  return row
}

export async function putBrowserSave(record: BrowserSaveRecord): Promise<void> {
  const db = await openDb()
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE_DYNASTIES, 'readwrite')
    tx.objectStore(STORE_DYNASTIES).put({
      ...record,
      updatedAt: record.updatedAt || Date.now(),
    })
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error ?? new Error('Failed to write save'))
  })
  db.close()
}

export async function deleteBrowserSave(id: string): Promise<void> {
  const db = await openDb()
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE_DYNASTIES, 'readwrite')
    tx.objectStore(STORE_DYNASTIES).delete(id)
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error ?? new Error('Failed to delete save'))
  })
  db.close()
}

/** Legacy single-slot autosave (same DB as dynasty library). */
export const AUTOSAVE_KEY = 'latest'

export type BrowserAutosaveRecord = {
  savedAt: number
  saveId: string
  saveName: string
  payload: SaveBundle
}

export async function writeLatestAutosave(record: BrowserAutosaveRecord): Promise<void> {
  const db = await openDb()
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE_AUTOSAVES, 'readwrite')
    tx.objectStore(STORE_AUTOSAVES).put(record, AUTOSAVE_KEY)
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error ?? new Error('Failed to write autosave'))
  })
  db.close()
}

export async function readLatestAutosave(): Promise<BrowserAutosaveRecord | null> {
  const db = await openDb()
  const out = await new Promise<BrowserAutosaveRecord | null>((resolve, reject) => {
    const tx = db.transaction(STORE_AUTOSAVES, 'readonly')
    const req = tx.objectStore(STORE_AUTOSAVES).get(AUTOSAVE_KEY)
    req.onsuccess = () => resolve((req.result as BrowserAutosaveRecord | undefined) ?? null)
    req.onerror = () => reject(req.error ?? new Error('Failed to read autosave'))
  })
  db.close()
  return out
}

async function parseApiError(r: Response): Promise<string> {
  const errText = await r.text()
  let msg = `Failed to load (${r.status})`
  try {
    const j = JSON.parse(errText)
    if (j.detail) msg = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail)
  } catch {
    if (errText) msg = errText
  }
  return msg
}

/** Preseason play selection (stage 2) — uses /sim for browser saves. */
export async function fetchPlaySelection(
  apiBase: string,
  saveId: string,
  saveState: unknown,
  headers: Record<string, string>,
): Promise<{ offensive: Record<string, unknown[]>; defensive: Record<string, unknown[]>; state?: unknown }> {
  if (shouldUseSimApi(saveId, headers)) {
    const r = await fetch(`${apiBase}/sim/play-selection`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ state: saveState }),
    })
    if (!r.ok) throw new Error(await parseApiError(r))
    return r.json()
  }
  const r = await fetch(`${apiBase}/saves/${saveId}/play-selection`, { headers })
  if (!r.ok) throw new Error(await parseApiError(r))
  return r.json()
}

/** Play selection results learning summary — uses /sim for browser saves. */
export async function fetchPlayLearningSummary(
  apiBase: string,
  saveId: string,
  saveState: unknown,
  headers: Record<string, string>,
): Promise<{
  offensive_pct_learned: number
  defensive_pct_learned: number
  overall_grade: string | null
}> {
  if (shouldUseSimApi(saveId, headers)) {
    const r = await fetch(`${apiBase}/sim/play-learning-summary`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ state: saveState }),
    })
    if (!r.ok) throw new Error(await parseApiError(r))
    return r.json()
  }
  const r = await fetch(`${apiBase}/saves/${saveId}/play-learning-summary`, { headers })
  if (!r.ok) throw new Error(await parseApiError(r))
  return r.json()
}

export type GamePlanLibraryEntry = {
  id: string
  name: string
  description?: string
  builtin?: boolean
  plan: Record<string, unknown>
  created_at?: number
}

export type GamePlanLibrary = {
  presets: GamePlanLibraryEntry[]
  saved: GamePlanLibraryEntry[]
}

/** @deprecated use GamePlanLibrary */
export type OffenseGamePlanLibraryEntry = GamePlanLibraryEntry
/** @deprecated use GamePlanLibrary */
export type OffenseGamePlanLibrary = GamePlanLibrary

export type CoachGameplanResponse = {
  matchup_key: string | null
  offense: Record<string, unknown>
  defense: Record<string, unknown>
  fourth_down?: { go_for_it_max_ytg?: number }
  offense_library?: GamePlanLibrary
  defense_library?: GamePlanLibrary
  meta?: unknown
  state?: unknown
}

/** OFF/DEF coach gameplan (v2) — uses /sim for browser saves and when not signed in. */
export async function fetchCoachGameplan(
  apiBase: string,
  saveId: string,
  saveState: unknown,
  headers: Record<string, string>,
): Promise<CoachGameplanResponse> {
  if (shouldUseSimApi(saveId, headers)) {
    const r = await fetch(`${apiBase}/sim/coach-gameplan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ state: saveState }),
    })
    if (!r.ok) throw new Error(await parseApiError(r))
    return r.json()
  }
  const r = await fetch(`${apiBase}/saves/${saveId}/coach-gameplan`, { headers })
  if (!r.ok) throw new Error(await parseApiError(r))
  return r.json()
}

export async function saveCoachGameplan(
  apiBase: string,
  saveId: string,
  saveState: unknown,
  headers: Record<string, string>,
  body: {
    offense?: Record<string, unknown>
    defense?: Record<string, unknown>
    fourth_down?: { go_for_it_max_ytg?: number }
    add_offense_library?: { name: string; plan: Record<string, unknown> }
    delete_offense_library_id?: string
    add_defense_library?: { name: string; plan: Record<string, unknown> }
    delete_defense_library_id?: string
  },
): Promise<CoachGameplanResponse> {
  if (shouldUseSimApi(saveId, headers)) {
    const r = await fetch(`${apiBase}/sim/coach-gameplan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ state: saveState, ...body }),
    })
    if (!r.ok) throw new Error(await parseApiError(r))
    return r.json()
  }
  const r = await fetch(`${apiBase}/saves/${saveId}/coach-gameplan`, {
    method: 'PUT',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error(await parseApiError(r))
  return r.json()
}

/** Save depth chart (team menu) — uses /sim for browser saves and when not signed in. */
export async function saveDepthChart(
  apiBase: string,
  saveId: string,
  saveState: unknown,
  headers: Record<string, string>,
  depthChart: Record<string, string[]>,
): Promise<{ state?: unknown }> {
  if (shouldUseSimApi(saveId, headers)) {
    const r = await fetch(`${apiBase}/sim/depth-chart`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ state: saveState, depth_chart: depthChart }),
    })
    if (!r.ok) throw new Error(await parseApiError(r))
    return r.json()
  }
  const r = await fetch(`${apiBase}/saves/${saveId}/depth-chart`, {
    method: 'PUT',
    headers: { ...headers, 'Content-Type': 'application/json' },
    body: JSON.stringify({ depth_chart: depthChart }),
  })
  if (!r.ok) throw new Error(await parseApiError(r))
  return r.json()
}
