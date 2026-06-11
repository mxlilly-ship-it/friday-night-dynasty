import { useCallback, useRef, useState, type ChangeEvent } from 'react'
import { suggestTeamForLogoFilename, suggestTeamForStadiumFilename } from './logoMatch'
import { guessMime, type SaveBundle, type SaveBundleAssetMap } from './saveBundle'
import './SettingsPage.css'

const MAX_IMAGE_FILES = 200
const MAX_LOGO_BYTES = 5 * 1024 * 1024
const MAX_STADIUM_BYTES = 8 * 1024 * 1024

function filterImageFiles(files: readonly File[]): File[] {
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
  onStadiumVersionBump?: () => void
  backupReminderFrequency: 'none' | '3_weeks' | '6_weeks' | 'stage'
  onBackupReminderFrequencyChange?: (value: 'none' | '3_weeks' | '6_weeks' | 'stage') => void
  onBackupNow?: () => void
  /** Server saves only: apply full state after bulk season simulation. */
  onApplySaveState?: (state: unknown) => void
  /** Browser / zip saves: merge logos into the local bundle and persist to IndexedDB. */
  onImportLogosToBundle?: (logos: SaveBundle['logos']) => Promise<void>
  /** Browser / zip saves: merge stadium photos into the local bundle and persist to IndexedDB. */
  onImportStadiumsToBundle?: (stadiums: SaveBundle['stadiums']) => Promise<void>
}

export default function SettingsPage({
  apiBase,
  headers,
  saveId,
  teamNames,
  onClose,
  onError,
  onLogoVersionBump,
  onStadiumVersionBump,
  backupReminderFrequency,
  onBackupReminderFrequencyChange,
  onBackupNow,
  onApplySaveState,
  onImportLogosToBundle,
  onImportStadiumsToBundle,
}: Props) {
  const folderInputRef = useRef<HTMLInputElement | null>(null)
  const filesInputRef = useRef<HTMLInputElement | null>(null)
  const stadiumFolderInputRef = useRef<HTMLInputElement | null>(null)
  const stadiumFilesInputRef = useRef<HTMLInputElement | null>(null)
  const [busy, setBusy] = useState(false)
  const [stadiumBusy, setStadiumBusy] = useState(false)
  const [progress, setProgress] = useState<string | null>(null)
  const [stadiumProgress, setStadiumProgress] = useState<string | null>(null)
  const [lastResult, setLastResult] = useState<string | null>(null)
  const [stadiumLastResult, setStadiumLastResult] = useState<string | null>(null)
  const [bulkSeasonCount, setBulkSeasonCount] = useState<1 | 5 | 10 | 20>(5)
  const [bulkBusy, setBulkBusy] = useState(false)

  /** Rows: one file + which team it maps to (empty string = skip). */
  const [rows, setRows] = useState<{ file: File; team: string }[]>([])
  const [stadiumRows, setStadiumRows] = useState<{ file: File; team: string }[]>([])

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

  const setStadiumFolderInputEl = useCallback((el: HTMLInputElement | null) => {
    stadiumFolderInputRef.current = el
    if (!el) return
    try {
      el.setAttribute('webkitdirectory', '')
      el.setAttribute('directory', '')
      el.multiple = true
    } catch {
      /* ignore */
    }
  }, [])

  const buildRowsFromFiles = (
    raw: File[],
    suggest: (filename: string, teams: string[]) => string,
    setRowState: (rows: { file: File; team: string }[]) => void,
    setResult: (msg: string | null) => void,
  ) => {
    const imageFiles = filterImageFiles(raw)
    if (imageFiles.length === 0) {
      onError(
        raw.length > 0
          ? `Found ${raw.length} file(s), but none were PNG, JPG, or WEBP.`
          : 'No files were selected.',
      )
      return
    }
    const capped = imageFiles.length > MAX_IMAGE_FILES ? imageFiles.slice(0, MAX_IMAGE_FILES) : imageFiles
    const next = capped.map((file) => ({
      file,
      team: suggest(file.name, teamNames),
    }))
    setRowState(next)
    setResult(
      imageFiles.length > MAX_IMAGE_FILES
        ? `Showing first ${MAX_IMAGE_FILES} of ${imageFiles.length} images. Import in batches if needed.`
        : null,
    )
    onError('')
  }

  const onFolderChange = (e: ChangeEvent<HTMLInputElement>) => {
    const snap = snapshotFiles(e.target.files)
    e.target.value = ''
    buildRowsFromFiles(snap, suggestTeamForLogoFilename, setRows, setLastResult)
  }

  const onFilesChange = (e: ChangeEvent<HTMLInputElement>) => {
    const snap = snapshotFiles(e.target.files)
    e.target.value = ''
    buildRowsFromFiles(snap, suggestTeamForLogoFilename, setRows, setLastResult)
  }

  const onStadiumFolderChange = (e: ChangeEvent<HTMLInputElement>) => {
    const snap = snapshotFiles(e.target.files)
    e.target.value = ''
    buildRowsFromFiles(snap, suggestTeamForStadiumFilename, setStadiumRows, setStadiumLastResult)
  }

  const onStadiumFilesChange = (e: ChangeEvent<HTMLInputElement>) => {
    const snap = snapshotFiles(e.target.files)
    e.target.value = ''
    buildRowsFromFiles(snap, suggestTeamForStadiumFilename, setStadiumRows, setStadiumLastResult)
  }

  const setTeamAt = (index: number, team: string) => {
    setRows((prev) => {
      const copy = [...prev]
      if (copy[index]) copy[index] = { ...copy[index], team }
      return copy
    })
  }

  const setStadiumTeamAt = (index: number, team: string) => {
    setStadiumRows((prev) => {
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

  const clearStadiumRows = () => {
    setStadiumRows([])
    setStadiumProgress(null)
    setStadiumLastResult(null)
  }

  const importAssetsToBundle = async (
    toUpload: { file: File; team: string }[],
    maxBytes: number,
    merge: (assets: SaveBundleAssetMap) => Promise<void>,
  ) => {
    const assets: SaveBundleAssetMap = {}
    for (let i = 0; i < toUpload.length; i++) {
      const { file, team } = toUpload[i]
      if (file.size > maxBytes) {
        throw new Error(`${file.name} is too large (max ${Math.round(maxBytes / (1024 * 1024))} MB).`)
      }
      const buf = new Uint8Array(await file.arrayBuffer())
      assets[team] = {
        filename: file.name,
        data: buf,
        mime: file.type?.startsWith('image/') ? file.type : guessMime(file.name),
      }
    }
    if (Object.keys(assets).length > 0) {
      await merge(assets)
    }
    return toUpload.length
  }

  const uploadAssetsToApi = async (
    toUpload: { file: File; team: string }[],
    maxBytes: number,
    fieldName: 'logo' | 'stadium',
    pathSegment: 'logos' | 'stadiums',
    setProgressText: (msg: string | null) => void,
  ) => {
    const uploadHeaders: Record<string, string> = {}
    if (headers.Authorization) uploadHeaders.Authorization = headers.Authorization
    for (let i = 0; i < toUpload.length; i++) {
      const { file, team } = toUpload[i]
      setProgressText(`Uploading ${i + 1} / ${toUpload.length}: ${team}…`)
      if (file.size > maxBytes) {
        throw new Error(`${file.name} is too large (max ${Math.round(maxBytes / (1024 * 1024))} MB).`)
      }
      const fd = new FormData()
      fd.append(fieldName, file)
      const r = await fetch(`${apiBase}/saves/${pathSegment}/${encodeURIComponent(team)}`, {
        method: 'POST',
        headers: uploadHeaders,
        body: fd,
      })
      if (!r.ok) {
        const t = await r.text().catch(() => '')
        throw new Error(t || `Failed for ${team}`)
      }
    }
    return toUpload.length
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

    try {
      let ok = 0
      if (isLocalSave) {
        ok = await importAssetsToBundle(toUpload, MAX_LOGO_BYTES, onImportLogosToBundle ?? (async () => {}))
      } else {
        ok = await uploadAssetsToApi(toUpload, MAX_LOGO_BYTES, 'logo', 'logos', setProgress)
      }
      onLogoVersionBump()
      setLastResult(`Imported ${ok} logo(s).`)
      onError('')
      clearRows()
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : 'Import stopped due to an error.')
    } finally {
      setProgress(null)
      setBusy(false)
    }
  }

  const runStadiumImport = async () => {
    const toUpload = stadiumRows.filter((r) => r.team.trim())
    if (toUpload.length === 0) {
      onError('Pick a team for at least one stadium photo, or use Skip on all rows.')
      return
    }
    if (!saveId) return

    const isLocalSave = saveId === '__local__' || saveId.startsWith('b_')
    if (isLocalSave) {
      if (!onImportStadiumsToBundle) {
        onError('Stadium import is not available for this save.')
        return
      }
    } else if (!headers.Authorization) {
      onError('Sign in to upload stadium photos to a cloud save, or use a browser dynasty save.')
      return
    }

    setStadiumBusy(true)
    setStadiumProgress(null)
    onError('')

    try {
      let ok = 0
      if (isLocalSave) {
        ok = await importAssetsToBundle(toUpload, MAX_STADIUM_BYTES, onImportStadiumsToBundle!)
      } else {
        ok = await uploadAssetsToApi(toUpload, MAX_STADIUM_BYTES, 'stadium', 'stadiums', setStadiumProgress)
      }
      onStadiumVersionBump?.()
      setStadiumLastResult(`Imported ${ok} stadium photo(s).`)
      onError('')
      clearStadiumRows()
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : 'Import stopped due to an error.')
    } finally {
      setStadiumProgress(null)
      setStadiumBusy(false)
    }
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
          <h2 className="settings-section-title">Stadium photos</h2>
          <p className="settings-copy">
            Import home field or stadium shots the same way as logos — choose a <strong>folder</strong> or{' '}
            <strong>image files</strong>, assign each to a school, then import. Filenames like{' '}
            <code>Martinsburg_stadium.jpg</code> or <code>Beckley.png</code> are matched automatically.
            {isLocalSave ? (
              <>
                {' '}
                Browser saves store stadium photos on this device (included in backup .zip).
              </>
            ) : null}
          </p>

          <input
            ref={setStadiumFolderInputEl}
            type="file"
            className="settings-file-input"
            onChange={onStadiumFolderChange}
          />

          <input
            ref={stadiumFilesInputRef}
            type="file"
            multiple
            accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp"
            className="settings-file-input"
            onChange={onStadiumFilesChange}
          />

          <div className="settings-actions settings-actions-row">
            <button
              type="button"
              className="settings-primary"
              disabled={stadiumBusy || busy || !saveId}
              onClick={() => stadiumFolderInputRef.current?.click()}
            >
              Choose folder…
            </button>
            <button
              type="button"
              className="settings-secondary"
              disabled={stadiumBusy || busy || !saveId}
              onClick={() => stadiumFilesInputRef.current?.click()}
            >
              Choose image files…
            </button>
          </div>

          {stadiumRows.length > 0 ? (
            <div className="settings-review">
              <div className="settings-review-head">
                <span>{stadiumRows.length} image(s)</span>
                <button type="button" className="settings-linkbtn" onClick={clearStadiumRows} disabled={stadiumBusy}>
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
                    {stadiumRows.map((row, i) => (
                      <tr key={`stadium-${row.file.name}-${i}-${row.file.size}`}>
                        <td className="settings-filecell" title={row.file.name}>
                          {row.file.name}
                        </td>
                        <td>
                          <select
                            className="settings-team-select"
                            value={row.team}
                            onChange={(e) => setStadiumTeamAt(i, e.target.value)}
                            disabled={stadiumBusy}
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
                <button
                  type="button"
                  className="settings-import-btn"
                  disabled={stadiumBusy || busy || !saveId}
                  onClick={() => void runStadiumImport()}
                >
                  {stadiumBusy ? 'Working…' : 'Import stadium photos'}
                </button>
                {stadiumProgress ? <span className="settings-progress">{stadiumProgress}</span> : null}
              </div>
            </div>
          ) : null}
          {stadiumLastResult ? <p className="settings-result">{stadiumLastResult}</p> : null}
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
