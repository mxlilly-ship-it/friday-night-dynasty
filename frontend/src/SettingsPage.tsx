import { useCallback, useRef, useState, type ChangeEvent } from 'react'
import { suggestTeamForLogoFilename } from './logoMatch'
import { guessMime, type SaveBundle } from './saveBundle'
import './SettingsPage.css'

const MAX_LOGO_FILES = 200
const MAX_LOGO_BYTES = 5 * 1024 * 1024

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
  /** Server saves only: apply full state after bulk season simulation. */
  onApplySaveState?: (state: unknown) => void
  /** Browser / zip saves: merge logos into the local bundle and persist to IndexedDB. */
  onImportLogosToBundle?: (logos: SaveBundle['logos']) => Promise<void>
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
  onApplySaveState,
  onImportLogosToBundle,
}: Props) {
  const folderInputRef = useRef<HTMLInputElement | null>(null)
  const filesInputRef = useRef<HTMLInputElement | null>(null)
  const [busy, setBusy] = useState(false)
  const [progress, setProgress] = useState<string | null>(null)
  const [lastResult, setLastResult] = useState<string | null>(null)
  const [bulkSeasonCount, setBulkSeasonCount] = useState<1 | 5 | 10 | 20>(5)
  const [bulkBusy, setBulkBusy] = useState(false)

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
    const capped = logoFiles.length > MAX_LOGO_FILES ? logoFiles.slice(0, MAX_LOGO_FILES) : logoFiles
    const next = capped.map((file) => ({
      file,
      team: suggestTeamForLogoFilename(file.name, teamNames),
    }))
    setRows(next)
    setLastResult(
      logoFiles.length > MAX_LOGO_FILES
        ? `Showing first ${MAX_LOGO_FILES} of ${logoFiles.length} images. Import in batches if needed.`
        : null,
    )
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

    const isLocalSave = saveId === '__local__' || saveId.startsWith('b_')
    if (isLocalSave) {
      if (!onImportLogosToBundle) {
        onError('Logo import is not available for this save.')
        return
      }
    } else if (!headers.Authorization) {
      onError('Sign in to upload logos to a cloud save, or use a browser dynasty save.')
      return
    }

    setBusy(true)
    setProgress(null)
    onError('')

    let ok = 0
    let failed = 0
    let lastErr = ''

    if (isLocalSave) {
      const logos: SaveBundle['logos'] = {}
      for (let i = 0; i < toUpload.length; i++) {
        const { file, team } = toUpload[i]
        setProgress(`Importing ${i + 1} / ${toUpload.length}: ${team}…`)
        try {
          if (file.size > MAX_LOGO_BYTES) {
            throw new Error(`${file.name} is too large (max 5 MB).`)
          }
          const buf = new Uint8Array(await file.arrayBuffer())
          logos[team] = {
            filename: file.name,
            data: buf,
            mime: file.type?.startsWith('image/') ? file.type : guessMime(file.name),
          }
          ok += 1
        } catch (e: unknown) {
          failed += 1
          lastErr = e instanceof Error ? e.message : 'Import failed'
          break
        }
      }
      if (failed === 0 && ok > 0) {
        try {
          await onImportLogosToBundle!(logos)
        } catch (e: unknown) {
          failed += 1
          lastErr = e instanceof Error ? e.message : 'Failed to save logos'
        }
      }
    } else {
      const uploadHeaders: Record<string, string> = {}
      if (headers.Authorization) uploadHeaders.Authorization = headers.Authorization

      for (let i = 0; i < toUpload.length; i++) {
        const { file, team } = toUpload[i]
        setProgress(`Uploading ${i + 1} / ${toUpload.length}: ${team}…`)
        try {
          if (file.size > MAX_LOGO_BYTES) {
            throw new Error(`${file.name} is too large (max 5 MB).`)
          }
          const fd = new FormData()
          fd.append('logo', file)
          const r = await fetch(`${apiBase}/saves/logos/${encodeURIComponent(team)}`, {
            method: 'POST',
            headers: uploadHeaders,
            body: fd,
          })
          if (!r.ok) {
            const t = await r.text().catch(() => '')
            throw new Error(t || `Failed for ${team}`)
          }
          ok += 1
        } catch (e: unknown) {
          failed += 1
          lastErr = e instanceof Error ? e.message : 'Upload failed'
          break
        }
      }
    }

    onLogoVersionBump()
    setProgress(null)
    setBusy(false)

    if (failed > 0) {
      onError(lastErr || 'Import stopped due to an error.')
      setLastResult(`Imported ${ok} logo(s) before the error.`)
      return
    }

    setLastResult(`Imported ${ok} logo(s).`)
    onError('')
    clearRows()
  }

  const sortedTeams = [...teamNames].sort((a, b) => a.localeCompare(b))
  const isLocalSave = saveId === '__local__' || saveId.startsWith('b_')
  // Production build uses same-origin API: App passes apiBase="" so fetch URLs are `/saves/...` (empty string is falsy but valid).
  const canBulkSimulate = Boolean(
    !isLocalSave && Boolean(saveId) && typeof onApplySaveState === 'function' && typeof apiBase === 'string',
  )

  const runBulkSimulateSeasons = async () => {
    if (!canBulkSimulate || !onApplySaveState) return
    const n = bulkSeasonCount
    if (
      !window.confirm(
        `Simulate ${n} season(s)? Full CPU offseasons include carousel hires/firings, your coach's ranked HC applications, program-point spending on upgrades/rebalances, coach development picks like CPU schools, and transfers. Regular season and playoffs are fully simmed; large counts can take a while.`,
      )
    ) {
      return
    }
    setBulkBusy(true)
    onError('')
    try {
      const r = await fetch(`${apiBase}/saves/${saveId}/simulate-seasons`, {
        method: 'POST',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ seasons: n }),
      })
      if (!r.ok) throw new Error(await r.text())
      const j = (await r.json()) as { state?: unknown }
      if (!j?.state || typeof j.state !== 'object') throw new Error('Invalid response from server')
      onApplySaveState(j.state)
      const cy = (j.state as { current_year?: number }).current_year
      setLastResult(
        typeof cy === 'number'
          ? `Simulated ${n} season(s). Calendar year is now ${cy}.`
          : `Simulated ${n} season(s).`,
      )
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : 'Failed to simulate seasons')
    } finally {
      setBulkBusy(false)
    }
  }

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
            {isLocalSave ? (
              <>
                {' '}
                Browser saves store logos on this device (included in backup .zip).
              </>
            ) : null}
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
          <h2 className="settings-section-title">Simulate seasons</h2>
          <p className="settings-copy">
            Fast-forward the dynasty: CPU sims remaining games plus full playoffs each year, runs full offseasons (coaching carousel hires and
            firings, transfers, etc.), spends your <strong>program points</strong> on AI upgrades (and can downgrade an over-built area to fund
            weaker grades), applies <strong>coach development</strong> using the same rules as CPU schools, picks ranked <strong>HC job apps</strong>{' '}
            to open vacancies so your coach can move like the rest of the league, runs preseason scrimmages, then stops at{' '}
            <strong>regular season Week&nbsp;1</strong> after the last simulated year.
          </p>
          <p className="settings-copy settings-copy-muted">
            Not available for imported/local zip saves. Finish any interactive preseason step manually before using this if the game expects you to
            be on that screen.
          </p>
          <div className="settings-actions settings-actions-row settings-simulate-row">
            <label htmlFor="bulk-season-count" style={{ color: '#aeb7c3' }}>
              Seasons
            </label>
            <select
              id="bulk-season-count"
              className="settings-team-select"
              value={bulkSeasonCount}
              onChange={(e) => setBulkSeasonCount(Number(e.target.value) as 1 | 5 | 10 | 20)}
              disabled={bulkBusy || !canBulkSimulate}
            >
              <option value={1}>1</option>
              <option value={5}>5</option>
              <option value={10}>10</option>
              <option value={20}>20</option>
            </select>
            <button
              type="button"
              className="settings-primary"
              disabled={bulkBusy || busy || !canBulkSimulate}
              onClick={() => void runBulkSimulateSeasons()}
            >
              {bulkBusy ? 'Simulating…' : 'Run simulation'}
            </button>
          </div>
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
