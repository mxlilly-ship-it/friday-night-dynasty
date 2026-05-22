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
