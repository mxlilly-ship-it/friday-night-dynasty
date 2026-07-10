import { useEffect, useState } from 'react'
import './SupportContactModal.css'
import {
  LEAGUE_START_TYPES,
  submitLeagueStartRequest,
  US_STATES,
  type LeagueStartType,
} from './leagueStartRequest'

type Props = {
  open: boolean
  onClose: () => void
  apiBase: string
  headers: Record<string, string>
  defaultEmail?: string
  onSuccess?: (message: string) => void
}

export default function RequestLeagueStartModal({
  open,
  onClose,
  apiBase,
  headers,
  defaultEmail = '',
  onSuccess,
}: Props) {
  const [leagueType, setLeagueType] = useState<LeagueStartType>('default')
  const [estimatedPlayers, setEstimatedPlayers] = useState('12')
  const [state, setState] = useState('')
  const [email, setEmail] = useState(defaultEmail)
  const [notes, setNotes] = useState('')
  const [leagueFile, setLeagueFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [localError, setLocalError] = useState('')

  useEffect(() => {
    if (!open) return
    setEmail(defaultEmail)
    setLocalError('')
    setLeagueFile(null)
  }, [open, defaultEmail])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  const selectedType = LEAGUE_START_TYPES.find((t) => t.id === leagueType)

  async function handleSubmit() {
    setLocalError('')
    const em = email.trim()
    if (!em || !em.includes('@')) {
      setLocalError('Enter a valid email so we can follow up.')
      return
    }
    const players = Number.parseInt(estimatedPlayers, 10)
    if (!Number.isFinite(players) || players < 2 || players > 120) {
      setLocalError('Estimated players must be between 2 and 120.')
      return
    }
    if (!state.trim()) {
      setLocalError('Select the state for this league.')
      return
    }
    if (leagueType === 'custom' && !leagueFile) {
      setLocalError('Upload your custom teams .json file.')
      return
    }

    setBusy(true)
    try {
      const result = await submitLeagueStartRequest(
        apiBase,
        {
          league_type: leagueType,
          estimated_players: players,
          state: state.trim(),
          contact_email: em,
          notes: notes.trim() || undefined,
          league_file: leagueFile,
        },
        headers,
      )
      setNotes('')
      setLeagueFile(null)
      onSuccess?.(result.message)
      onClose()
    } catch (e: unknown) {
      setLocalError(e instanceof Error ? e.message : 'Could not send request')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      className="fnd-support-backdrop"
      role="presentation"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="fnd-support-modal" role="dialog" aria-modal="true" aria-labelledby="fnd-league-start-title">
        <div className="fnd-support-header">
          <h2 id="fnd-league-start-title">Request to start a league</h2>
          <button type="button" className="fnd-support-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <div className="fnd-support-body">
          <p className="fnd-support-intro">
            Tell us what kind of multiplayer league you want to run. We&apos;ll review your request and email you to
            get it set up.
          </p>
          <label className="fnd-support-field">
            <span>League type</span>
            <select
              value={leagueType}
              onChange={(e) => setLeagueType(e.target.value as LeagueStartType)}
              disabled={busy}
            >
              {LEAGUE_START_TYPES.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
          {selectedType ? <p className="fnd-support-note">{selectedType.hint}</p> : null}
          <label className="fnd-support-field">
            <span>Estimated number of coaches</span>
            <input
              type="number"
              min={2}
              max={120}
              value={estimatedPlayers}
              onChange={(e) => setEstimatedPlayers(e.target.value)}
              disabled={busy}
            />
          </label>
          <label className="fnd-support-field">
            <span>State</span>
            <select value={state} onChange={(e) => setState(e.target.value)} disabled={busy}>
              <option value="">Select state…</option>
              {US_STATES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <label className="fnd-support-field">
            <span>Your email</span>
            <input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              disabled={busy}
            />
          </label>
          <label className="fnd-support-field">
            <span>{leagueType === 'custom' ? 'League file (.json)' : 'League file (.json, optional)'}</span>
            <input
              type="file"
              accept=".json,application/json"
              disabled={busy}
              onChange={(e) => setLeagueFile(e.target.files?.[0] ?? null)}
            />
          </label>
          <label className="fnd-support-field">
            <span>Additional notes (optional)</span>
            <textarea
              rows={4}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Preferred start date, class sizes, rivalries, anything else we should know…"
              disabled={busy}
            />
          </label>
          {localError ? <p className="fnd-support-error">{localError}</p> : null}
        </div>
        <div className="fnd-support-footer">
          <button type="button" className="teamhome-select" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button
            type="button"
            className="fnd-title-btn fnd-support-submit"
            onClick={() => void handleSubmit()}
            disabled={busy}
          >
            {busy ? 'Sending…' : 'Send request'}
          </button>
        </div>
      </div>
    </div>
  )
}
