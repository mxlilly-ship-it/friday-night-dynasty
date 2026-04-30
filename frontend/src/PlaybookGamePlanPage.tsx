import { useCallback, useEffect, useMemo, useState } from 'react'
import './PlaybookGamePlanPage.css'
import TeamLogo from './TeamLogo'

export const OFFENSIVE_CATEGORIES = [
  { key: 'INSIDE_RUN', label: 'Inside Run' },
  { key: 'OUTSIDE_RUN', label: 'Outside Run' },
  { key: 'SHORT_PASS', label: 'Short Pass' },
  { key: 'MEDIUM_PASS', label: 'Medium Pass' },
  { key: 'LONG_PASS', label: 'Long Pass' },
  { key: 'PLAY_ACTION', label: 'Play Action' },
] as const

export const DEFENSIVE_CATEGORIES = [
  { key: 'ZONES', label: 'Zone Coverage' },
  { key: 'MANS', label: 'Man Coverage' },
  { key: 'ZONE_PRESSURE', label: 'Zone Pressure' },
  { key: 'MAN_PRESSURE', label: 'Man Pressure' },
] as const

type PlayEntry = { play_id: string; name: string; formation?: string; pct: number }

type Props = {
  apiBase: string
  headers: Record<string, string>
  saveId: string
  saveState: any
  logoVersion?: number
  onBack?: () => void
  onConfirm?: (gamePlan: {
    offensive: Record<string, { play_id: string; pct: number }[]>
    defensive: Record<string, { play_id: string; pct: number }[]>
  }) => Promise<void>
  onError: (msg: string) => void
  readOnly?: boolean
  headerBackLabel?: string
}

function roundPct(n: number) {
  return Math.round(n * 10) / 10
}

export default function PlaybookGamePlanPage({
  apiBase,
  headers,
  saveId,
  saveState,
  logoVersion = 0,
  onBack,
  onConfirm,
  onError,
  readOnly = false,
  headerBackLabel = 'Back to Preseason',
}: Props) {
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState<string | null>(null)
  const [offensiveCategory, setOffensiveCategory] = useState<string>(OFFENSIVE_CATEGORIES[0].key)
  const [defensiveCategory, setDefensiveCategory] = useState<string>(DEFENSIVE_CATEGORIES[0].key)
  const [localOffensive, setLocalOffensive] = useState<Record<string, PlayEntry[]>>({})
  const [localDefensive, setLocalDefensive] = useState<Record<string, PlayEntry[]>>({})
  const [confirming, setConfirming] = useState(false)
  const userTeam = String(saveState?.user_team ?? '')

  const fetchData = useCallback(async () => {
    if (!saveId) {
      setFetchError('Missing configuration')
      setLoading(false)
      return
    }
    setLoading(true)
    setFetchError(null)
    try {
      const url = `${apiBase ?? ''}/saves/${saveId}/play-selection`
      const r = await fetch(url, { headers })
      if (!r.ok) {
        const errText = await r.text()
        let msg = `Failed to load (${r.status})`
        try {
          const j = JSON.parse(errText)
          if (j.detail) msg = j.detail
        } catch {
          if (errText) msg = errText
        }
        throw new Error(msg)
      }
      const json = await r.json()
      setLocalOffensive(json.offensive || {})
      setLocalDefensive(json.defensive || {})
    } catch (e: any) {
      const msg = e?.message ?? 'Failed to load'
      setFetchError(msg)
    } finally {
      setLoading(false)
    }
  }, [apiBase, headers, saveId])

  useEffect(() => {
    if (saveId) fetchData()
  }, [saveId, fetchData])

  const updateOffensivePct = (catKey: string, playId: string, pct: number) => {
    setLocalOffensive((prev) => {
      const list = [...(prev[catKey] || [])]
      const i = list.findIndex((p) => p.play_id === playId)
      if (i >= 0) list[i] = { ...list[i], pct }
      return { ...prev, [catKey]: list }
    })
  }

  const updateDefensivePct = (catKey: string, playId: string, pct: number) => {
    setLocalDefensive((prev) => {
      const list = [...(prev[catKey] || [])]
      const i = list.findIndex((p) => p.play_id === playId)
      if (i >= 0) list[i] = { ...list[i], pct }
      return { ...prev, [catKey]: list }
    })
  }

  const offensiveTotal = useMemo(() => {
    const list = localOffensive[offensiveCategory] || []
    return roundPct(list.reduce((s, p) => s + p.pct, 0))
  }, [localOffensive, offensiveCategory])

  const defensiveTotal = useMemo(() => {
    const list = localDefensive[defensiveCategory] || []
    return roundPct(list.reduce((s, p) => s + p.pct, 0))
  }, [localDefensive, defensiveCategory])

  const allCategoriesValid = useMemo(() => {
    const allOff = OFFENSIVE_CATEGORIES.every((c) => {
      const list = localOffensive[c.key] || []
      if (list.length === 0) return true
      const t = list.reduce((s, p) => s + p.pct, 0)
      return Math.abs(t - 100) < 0.1
    })
    const allDef = DEFENSIVE_CATEGORIES.every((c) => {
      const list = localDefensive[c.key] || []
      if (list.length === 0) return true
      const t = list.reduce((s, p) => s + p.pct, 0)
      return Math.abs(t - 100) < 0.1
    })
    return allOff && allDef
  }, [localOffensive, localDefensive])

  const handleConfirm = async () => {
    if (readOnly) return
    if (!onConfirm) return
    if (!allCategoriesValid) return
    setConfirming(true)
    try {
      const gamePlan = {
        offensive: Object.fromEntries(
          Object.entries(localOffensive).map(([k, v]) => [
            k,
            v.map((p) => ({ play_id: p.play_id, pct: p.pct })),
          ])
        ),
        defensive: Object.fromEntries(
          Object.entries(localDefensive).map(([k, v]) => [
            k,
            v.map((p) => ({ play_id: p.play_id, pct: p.pct })),
          ])
        ),
      }
      await onConfirm(gamePlan)
    } catch (e: any) {
      onError(e?.message ?? 'Confirm failed')
    } finally {
      setConfirming(false)
    }
  }

  const offPlays = localOffensive[offensiveCategory] || []
  const defPlays = localDefensive[defensiveCategory] || []

  return (
    <div className="playbook-gp-root">
      <div className="playbook-gp-header">
        <div className="playbook-gp-header-left">
          <div className="playbook-gp-logo">
            <TeamLogo
              apiBase={apiBase}
              headers={headers}
              teamName={userTeam}
              logoVersion={logoVersion}
              size={40}
              className="playbook-gp-logo-inner"
            />
          </div>
          {onBack ? (
            <button type="button" className="playbook-gp-back" onClick={onBack}>
              ← {headerBackLabel}
            </button>
          ) : null}
        </div>
      </div>

      {loading ? (
        <div className="playbook-gp-loading">Loading play selection…</div>
      ) : fetchError ? (
        <div className="playbook-gp-error">
          <p>{fetchError}</p>
          <button type="button" className="playbook-gp-back" onClick={() => fetchData()}>
            Retry
          </button>
        </div>
      ) : (() => {
        const hasOff = Object.values(localOffensive).some((arr) => arr.length > 0)
        const hasDef = Object.values(localDefensive).some((arr) => arr.length > 0)
        if (!hasOff && !hasDef) {
          return (
            <div className="playbook-gp-empty-state">
              <p>No play selection data yet.</p>
              <p className="playbook-gp-empty-hint">
                Make sure you&apos;ve completed <strong>Playbook Select</strong> (Stage 1) and clicked Continue to reach this stage.
                Then try again.
              </p>
              {onBack ? (
                <button type="button" className="playbook-gp-back" onClick={onBack}>
                  ← {headerBackLabel}
                </button>
              ) : null}
            </div>
          )
        }
        return (
      <>
      <div className="playbook-gp-panels">
        <div className="playbook-gp-panel">
          <h2 className="playbook-gp-panel-title">OFFENSIVE PLAYBOOK</h2>
          <div className="playbook-gp-panel-head">
            <select
              className="playbook-gp-cat-select"
              value={offensiveCategory}
              onChange={(e) => setOffensiveCategory(e.target.value)}
            >
              {OFFENSIVE_CATEGORIES.map((c) => (
                <option key={c.key} value={c.key}>
                  {c.label}
                </option>
              ))}
            </select>
            <span className={`playbook-gp-total ${Math.abs(offensiveTotal - 100) < 0.1 ? 'ok' : 'bad'}`}>
              TOTAL: {offensiveTotal}%
            </span>
          </div>
          <div className="playbook-gp-play-list">
            <div className="playbook-gp-play-header">
              <span>PLAY NAME</span>
              <span>%</span>
            </div>
            {offPlays.length === 0 ? (
              <div className="playbook-gp-empty">No plays in this category.</div>
            ) : (
              offPlays.map((p) => (
                <div key={p.play_id} className="playbook-gp-play-row">
                  <span className="playbook-gp-play-name">
                    {p.formation ? `${p.formation} — ${p.name}` : p.name}
                  </span>
                  {readOnly ? (
                    <span className="playbook-gp-pct-text">{p.pct}%</span>
                  ) : (
                    <input
                      type="number"
                      min={0}
                      max={100}
                      step={0.5}
                      value={p.pct}
                      onChange={(e) =>
                        updateOffensivePct(offensiveCategory, p.play_id, Number(e.target.value) || 0)
                      }
                      className="playbook-gp-pct-input"
                    />
                  )}
                </div>
              ))
            )}
          </div>
        </div>

        <div className="playbook-gp-panel">
          <h2 className="playbook-gp-panel-title">DEFENSIVE PLAYBOOK</h2>
          <div className="playbook-gp-panel-head">
            <select
              className="playbook-gp-cat-select"
              value={defensiveCategory}
              onChange={(e) => setDefensiveCategory(e.target.value)}
            >
              {DEFENSIVE_CATEGORIES.map((c) => (
                <option key={c.key} value={c.key}>
                  {c.label}
                </option>
              ))}
            </select>
            <span className={`playbook-gp-total ${Math.abs(defensiveTotal - 100) < 0.1 ? 'ok' : 'bad'}`}>
              TOTAL: {defensiveTotal}%
            </span>
          </div>
          <div className="playbook-gp-play-list">
            <div className="playbook-gp-play-header">
              <span>PLAY NAME</span>
              <span>%</span>
            </div>
            {defPlays.length === 0 ? (
              <div className="playbook-gp-empty">No plays in this category.</div>
            ) : (
              defPlays.map((p) => (
                <div key={p.play_id} className="playbook-gp-play-row">
                  <span className="playbook-gp-play-name">
                    {p.formation ? `${p.formation} — ${p.name}` : p.name}
                  </span>
                  {readOnly ? (
                    <span className="playbook-gp-pct-text">{p.pct}%</span>
                  ) : (
                    <input
                      type="number"
                      min={0}
                      max={100}
                      step={0.5}
                      value={p.pct}
                      onChange={(e) =>
                        updateDefensivePct(defensiveCategory, p.play_id, Number(e.target.value) || 0)
                      }
                      className="playbook-gp-pct-input"
                    />
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <div className="playbook-gp-footer">
        {readOnly ? (
          <div className="playbook-gp-hint playbook-gp-hint-lock">
            Locked from preseason selection.
          </div>
        ) : (
          <>
            <button
              type="button"
              className="playbook-gp-confirm"
              disabled={!allCategoriesValid || confirming}
              onClick={handleConfirm}
            >
              {confirming ? 'Confirming…' : 'CONFIRM'}
            </button>
            {!allCategoriesValid && (
              <div className="playbook-gp-hint">All categories must total 100% before confirming.</div>
            )}
          </>
        )}
      </div>
      </>
        )
      })()}
    </div>
  )
}
