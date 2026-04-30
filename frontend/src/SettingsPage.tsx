import { useCallback, useRef, useState, type ChangeEvent } from 'react'
import { suggestTeamForLogoFilename } from './logoMatch'
import './SettingsPage.css'

function filterLogoFiles(files: readonly File[]): File[] {
  return files.filter((f) => {
    const n = f.name
    if (!n || n.startsWith('.')) return false
    if (/^\.ds_store$/i.test(n) || /^thumbs\.db$/i.test(n)) return false
    return /\.(png|jpe?g|webp)$/i.test(n)
  })
}

function snapshotFiles(list: FileList | null): File[] {
  if (!list?.length) return []
  return Array.from(list)
}

type Props = {
  apiBase: string
  headers: Record<string, string>
  saveId: string
  /** Team names in the current save — required to assign each logo. */
  teamNames: string[]
  onClose: () => void
  onError: (msg: string) => void
  onLogoVersionBump: () => void
  backupReminderFrequency: 'none' | '3_weeks' | '6_weeks' | 'stage'
  onBackupReminderFrequencyChange?: (value: 'none' | '3_weeks' | '6_weeks' | 'stage') => void
  onBackupNow?: () => void
}

export default function SettingsPage({
  apiBase,
  headers,
  saveId,
  teamNames,
  onClose,
  onError,
  onLogoVersionBump,
  backupReminderFrequency,
  onBackupReminderFrequencyChange,
  onBackupNow,
}: Props) {
  const folderInputRef = useRef<HTMLInputElement | null>(null)
  const filesInputRef = useRef<HTMLInputElement | null>(null)
  const [busy, setBusy] = useState(false)
  const [progress, setProgress] = useState<string | null>(null)
  const [lastResult, setLastResult] = useState<string | null>(null)

  /** Rows: one file + which team it maps to (empty string = skip). */
  const [rows, setRows] = useState<{ file: File; team: string }[]>([])

  const setFolderInputEl = useCallback((el: HTMLInputElement | null) => {
    folderInputRef.current = el
    if (!el) return
    try {
      el.setAttribute('webkitdirectory', '')
      el.setAttribute('directory', '')
      el.multiple = true
    } catch {
      /* ignore */
    }
  }, [])

  const buildRowsFromFiles = (raw: File[]) => {
    const logoFiles = filterLogoFiles(raw)
    if (logoFiles.length === 0) {
      onError(
        raw.length > 0
          ? `Found ${raw.length} file(s), but none were PNG, JPG, or WEBP.`
          : 'No files were selected.',
      )
      return
    }
    const next = logoFiles.map((file) => ({
      file,
      team: suggestTeamForLogoFilename(file.name, teamNames),
    }))
    setRows(next)
    setLastResult(null)
    onError('')
  }

  const onFolderChange = (e: ChangeEvent<HTMLInputElement>) => {
    const snap = snapshotFiles(e.target.files)
    e.target.value = ''
    buildRowsFromFiles(snap)
  }

  const onFilesChange = (e: ChangeEvent<HTMLInputElement>) => {
    const snap = snapshotFiles(e.target.files)
    e.target.value = ''
    buildRowsFromFiles(snap)
  }

  const setTeamAt = (index: number, team: string) => {
    setRows((prev) => {
      const copy = [...prev]
      if (copy[index]) copy[index] = { ...copy[index], team }
      return copy
    })
  }

  const clearRows = () => {
    setRows([])
    setProgress(null)
    setLastResult(null)
  }

  const runImport = async () => {
    const toUpload = rows.filter((r) => r.team.trim())
    if (toUpload.length === 0) {
      onError('Pick a team for at least one logo, or use Skip on all rows.')
      return
    }
    if (!saveId) return

    setBusy(true)
    setProgress(null)
    setLastResult(null)
    onError('')

    let ok = 0
    let failed = 0
    let lastErr = ''

    for (let i = 0; i < toUpload.length; i++) {
      const { file, team } = toUpload[i]
      setProgress(`Uploading ${i + 1} / ${toUpload.length}: ${team}…`)
      try {
        const fd = new FormData()
        fd.append('logo', file)
        const r = await fetch(`${apiBase}/saves/logos/${encodeURIComponent(team)}`, {
          method: 'POST',
          headers,
          body: fd,
        })
        if (!r.ok) {
          const t = await r.text().catch(() => '')
          throw new Error(t || `Failed for ${team}`)
        }
        ok += 1
      } catch (e: any) {
        failed += 1
        lastErr = e?.message ?? 'Upload failed'
        break
      }
    }

    onLogoVersionBump()
    setProgress(null)
    setBusy(false)

    if (failed > 0) {
      onError(lastErr || 'Import stopped due to an error.')
      setLastResult(`Uploaded ${ok} logo(s) before the error.`)
      return
    }

    setLastResult(`Uploaded ${ok} logo(s).`)
    onError('')
    clearRows()
  }

  const sortedTeams = [...teamNames].sort((a, b) => a.localeCompare(b))

  return (
    <div className="settings-root">
      <div className="settings-card">
        <div className="settings-header">
          <h1 className="settings-title">Settings</h1>
          <button type="button" className="settings-close" onClick={onClose}>
            Back
          </button>
        </div>

        <section className="settings-section">
          <h2 className="settings-section-title">Team logos</h2>
          <p className="settings-copy">
            Choose a <strong>folder</strong> or <strong>image files</strong>. For each picture, pick which school it belongs to. Names are
            guessed from the filename when possible (same rules as before: e.g. <code>Martinsburg.png</code> → Martinsburg). You can change
            any row before importing.
          </p>

          <input ref={setFolderInputEl} type="file" className="settings-file-input" onChange={onFolderChange} />

          <input
            ref={filesInputRef}
            type="file"
            multiple
            accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp"
            className="settings-file-input"
            onChange={onFilesChange}
          />

          <div className="settings-actions settings-actions-row">
            <button
              type="button"
              className="settings-primary"
              disabled={busy || !saveId}
              onClick={() => folderInputRef.current?.click()}
            >
              Choose folder…
            </button>
            <button
              type="button"
              className="settings-secondary"
              disabled={busy || !saveId}
              onClick={() => filesInputRef.current?.click()}
            >
              Choose image files…
            </button>
          </div>

          {rows.length > 0 ? (
            <div className="settings-review">
              <div className="settings-review-head">
                <span>{rows.length} image(s)</span>
                <button type="button" className="settings-linkbtn" onClick={clearRows} disabled={busy}>
                  Clear list
                </button>
              </div>
              <div className="settings-review-table-wrap">
                <table className="settings-review-table">
                  <thead>
                    <tr>
                      <th>File</th>
                      <th>Team</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row, i) => (
                      <tr key={`${row.file.name}-${i}-${row.file.size}`}>
                        <td className="settings-filecell" title={row.file.name}>
                          {row.file.name}
                        </td>
                        <td>
                          <select
                            className="settings-team-select"
                            value={row.team}
                            onChange={(e) => setTeamAt(i, e.target.value)}
                            disabled={busy}
                          >
                            <option value="">— Skip —</option>
                            {sortedTeams.map((t) => (
                              <option key={t} value={t}>
                                {t}
                              </option>
                            ))}
                          </select>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="settings-import-row">
                <button type="button" className="settings-import-btn" disabled={busy || !saveId} onClick={() => void runImport()}>
                  {busy ? 'Working…' : 'Import logos'}
                </button>
                {progress ? <span className="settings-progress">{progress}</span> : null}
              </div>
            </div>
          ) : null}
        </section>

        <section className="settings-section">
          <h2 className="settings-section-title">Backup reminders</h2>
          <p className="settings-copy">
            Choose when the game reminds you to download a backup save to your computer.
          </p>
          <div className="settings-actions settings-actions-row">
            <label htmlFor="backup-reminder-frequency" style={{ color: '#aeb7c3' }}>
              Frequency
            </label>
            <select
              id="backup-reminder-frequency"
              className="settings-team-select"
              value={backupReminderFrequency}
              onChange={(e) =>
                onBackupReminderFrequencyChange?.(
                  e.target.value as 'none' | '3_weeks' | '6_weeks' | 'stage',
                )
              }
            >
              <option value="none">None</option>
              <option value="3_weeks">Every 3 weeks</option>
              <option value="6_weeks">Every 6 weeks</option>
              <option value="stage">Every stage</option>
            </select>
            <button type="button" className="settings-secondary" onClick={() => onBackupNow?.()}>
              Backup now
            </button>
          </div>
        </section>

        {lastResult ? <p className="settings-result">{lastResult}</p> : null}
      </div>
    </div>
  )
}
