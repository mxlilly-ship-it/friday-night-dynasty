import { exportSaveZip, type SaveBundle } from './saveBundle'

export function saveNameFromBundle(bundle: SaveBundle): string {
  return String(bundle?.state?.save_name ?? 'dynasty').trim() || 'dynasty'
}

export function downloadJsonFile(filename: string, payload: unknown) {
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

export function downloadBackupJson(bundle: SaveBundle) {
  const name = saveNameFromBundle(bundle)
  downloadJsonFile(`${name.replaceAll(' ', '_')}_backup.json`, {
    format: 'fnd-backup-v1',
    exported_at: new Date().toISOString(),
    payload: bundle,
  })
}

export async function downloadBackupZip(bundle: SaveBundle) {
  const name = saveNameFromBundle(bundle)
  const blob = await exportSaveZip(bundle)
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${name.replaceAll(' ', '_')}.zip`
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 250)
}
