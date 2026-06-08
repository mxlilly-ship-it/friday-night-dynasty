import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { fetchPlaySelection } from './browserSave'
import './PlaybookGamePlanPage.css'
import TeamLogo from './TeamLogo'
import {
  cachePlaySelectionResponse,
  getPlaySelectionCache,
  hasPlaySelectionCache,
  setPlaySelectionCache,
  parseInstallMeta,
  parsePlaySelectionRows,
  type PlaySelectionPlayRow,
} from './playSelectionCache'
import {
  categoryInstallBand,
  computeProjectedInstallSummary,
  countActivePlays,
  DEFAULT_INSTALL_META,
  filterActivePlayEntries,
  installBandLabel,
  isActivePlayPct,
  type InstallMeta,
} from './playSelectionUtils'

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

type PlayEntry = PlaySelectionPlayRow

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
  onSaveState?: (state: any) => void
  readOnly?: boolean
  headerBackLabel?: string
  /** Prefetched on the preseason hub so the first open skips the loading flash. */
  prefetchedData?: {
    offensive?: Record<string, PlayEntry[]>
    defensive?: Record<string, PlayEntry[]>
    install_meta?: InstallMeta
  } | null
}

function roundPct(n: number) {
  return Math.round(n * 10) / 10
}

function hydrateFromSource(
  saveId: string,
  prefetchedData?: Props['prefetchedData'],
): { offensive: Record<string, PlayEntry[]>; defensive: Record<string, PlayEntry[]>; installMeta: InstallMeta } {
  const cached = getPlaySelectionCache(saveId)
  if (cached) {
    return {
      offensive: cached.offensive,
      defensive: cached.defensive,
      installMeta: cached.installMeta ?? DEFAULT_INSTALL_META,
    }
  }
  if (prefetchedData) {
    return {
      offensive: prefetchedData.offensive ?? {},
      defensive: prefetchedData.defensive ?? {},
      installMeta: prefetchedData.install_meta ?? DEFAULT_INSTALL_META,
    }
  }
  return { offensive: {}, defensive: {}, installMeta: DEFAULT_INSTALL_META }
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
  onSaveState,
  readOnly = false,
  headerBackLabel = 'Back to Preseason',
  prefetchedData = null,
}: Props) {
  const initial = hydrateFromSource(saveId, prefetchedData)
  const hasInitialData =
    Object.values(initial.offensive).some((arr) => arr.length > 0) ||
    Object.values(initial.defensive).some((arr) => arr.length > 0)

  const [loading, setLoading] = useState(!hasInitialData)
  const [fetchError, setFetchError] = useState<string | null>(null)
  const [offensiveCategory, setOffensiveCategory] = useState<string>(OFFENSIVE_CATEGORIES[0].key)
  const [defensiveCategory, setDefensiveCategory] = useState<string>(DEFENSIVE_CATEGORIES[0].key)
  const [localOffensive, setLocalOffensive] = useState<Record<string, PlayEntry[]>>(initial.offensive)
  const [localDefensive, setLocalDefensive] = useState<Record<string, PlayEntry[]>>(initial.defensive)
  const [installMeta, setInstallMeta] = useState<InstallMeta>(initial.installMeta)
  const [confirming, setConfirming] = useState(false)
  const userTeam = String(saveState?.user_team ?? '')

  const saveStateRef = useRef(saveState)
  saveStateRef.current = saveState
  const onSaveStateRef = useRef(onSaveState)
  onSaveStateRef.current = onSaveState
  const headersRef = useRef(headers)
  headersRef.current = headers
  const localOffensiveRef = useRef(localOffensive)
  localOffensiveRef.current = localOffensive
  const localDefensiveRef = useRef(localDefensive)
  localDefensiveRef.current = localDefensive
  const installMetaRef = useRef(installMeta)
  installMetaRef.current = installMeta

  const applyPayload = useCallback(
    (json: {
      offensive?: unknown
      defensive?: unknown
      install_meta?: unknown
      state?: unknown
    }) => {
      const offensive = parsePlaySelectionRows(json.offensive)
      const defensive = parsePlaySelectionRows(json.defensive)
      const meta = parseInstallMeta(json.install_meta) ?? DEFAULT_INSTALL_META
      setLocalOffensive(offensive)
      setLocalDefensive(defensive)
      setInstallMeta(meta)
      setPlaySelectionCache(saveId, { offensive, defensive, installMeta: meta })
      return { offensive, defensive, meta, state: json.state }
    },
    [saveId],
  )

  const fetchData = useCallback(
    async (opts?: { showLoading?: boolean }) => {
      if (!saveId) {
        setFetchError('Missing configuration')
        setLoading(false)
        return
      }
      const hasCached = hasPlaySelectionCache(saveId)
      const showLoading = opts?.showLoading ?? !hasCached
      if (showLoading) setLoading(true)
      setFetchError(null)
      try {
        const json = await fetchPlaySelection(
          apiBase ?? '',
          saveId,
          saveStateRef.current,
          headersRef.current,
        )
        const applied = applyPayload(json)
        if (json.state && !hasCached) {
          onSaveStateRef.current?.(json.state)
        }
        return applied
      } catch (e: any) {
        const msg = e?.message ?? 'Failed to load'
        if (!hasCached) setFetchError(msg)
      } finally {
        if (showLoading) setLoading(false)
      }
    },
    [apiBase, saveId, applyPayload],
  )

  useEffect(() => {
    if (!saveId) return
    if (hasPlaySelectionCache(saveId)) return
    void fetchData({ showLoading: !hasInitialData })
    // Intentionally only when saveId changes — saveState updates from onSaveState must not re-fetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [saveId])

  useEffect(() => {
    return () => {
      if (!saveId) return
      setPlaySelectionCache(saveId, {
        offensive: localOffensiveRef.current,
        defensive: localDefensiveRef.current,
        installMeta: installMetaRef.current,
      })
    }
  }, [saveId])

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

  const offCategoryKeys = useMemo(() => OFFENSIVE_CATEGORIES.map((c) => c.key), [])
  const defCategoryKeys = useMemo(() => DEFENSIVE_CATEGORIES.map((c) => c.key), [])

  const projectedInstall = useMemo(
    () =>
      computeProjectedInstallSummary(
        installMeta,
        localOffensive,
        localDefensive,
        offCategoryKeys,
        defCategoryKeys,
      ),
    [installMeta, localOffensive, localDefensive, offCategoryKeys, defCategoryKeys],
  )

  const offensiveCategoryActive = useMemo(
    () => countActivePlays(localOffensive[offensiveCategory] || []),
    [localOffensive, offensiveCategory],
  )

  const defensiveCategoryActive = useMemo(
    () => countActivePlays(localDefensive[defensiveCategory] || []),
    [localDefensive, defensiveCategory],
  )

  const offensiveCategoryBand = useMemo(
    () =>
      categoryInstallBand(
        offensiveCategoryActive,
        installMeta.recommended_plays_per_category,
        installMeta.teachable_plays_per_category,
      ),
    [offensiveCategoryActive, installMeta],
  )

  const defensiveCategoryBand = useMemo(
    () =>
      categoryInstallBand(
        defensiveCategoryActive,
        installMeta.recommended_plays_per_category,
        installMeta.teachable_plays_per_category,
      ),
    [defensiveCategoryActive, installMeta],
  )

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
            filterActivePlayEntries(v).map((p) => ({ play_id: p.play_id, pct: p.pct })),
          ]),
        ),
        defensive: Object.fromEntries(
          Object.entries(localDefensive).map(([k, v]) => [
            k,
            filterActivePlayEntries(v).map((p) => ({ play_id: p.play_id, pct: p.pct })),
          ]),
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
          <button type="button" className="playbook-gp-back" onClick={() => void fetchData({ showLoading: true })}>
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
      {!readOnly ? (
        <div className="playbook-gp-install-meter">
          <div className="playbook-gp-install-meter-main">
            <div className="playbook-gp-install-grade">
              <span className="playbook-gp-install-grade-label">Projected understanding</span>
              <span className="playbook-gp-install-grade-value">{projectedInstall.overall_grade}</span>
            </div>
            <div className="playbook-gp-install-stats">
              <div className="playbook-gp-install-stat">
                <span className="playbook-gp-install-stat-label">Offense install</span>
                <span className="playbook-gp-install-stat-value">
                  {projectedInstall.offensive_active_plays_per_category} plays / category
                  <span className="playbook-gp-install-stat-sub">
                    ({projectedInstall.offensive_pct_learned}% learned)
                  </span>
                </span>
              </div>
              <div className="playbook-gp-install-stat">
                <span className="playbook-gp-install-stat-label">Defense install</span>
                <span className="playbook-gp-install-stat-value">
                  {projectedInstall.defensive_active_plays_per_category} plays / category
                  <span className="playbook-gp-install-stat-sub">
                    ({projectedInstall.defensive_pct_learned}% learned)
                  </span>
                </span>
              </div>
            </div>
          </div>
          <p className="playbook-gp-install-hint">
            Coach recommends about <strong>{installMeta.recommended_plays_per_category}</strong> plays
            per category (scheme teach {installMeta.scheme_teach}/10). Only plays above 0% count
            toward your install — set unused plays to 0%.
          </p>
        </div>
      ) : null}
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
            {!readOnly ? (
              <span className={`playbook-gp-install-badge playbook-gp-install-badge--${offensiveCategoryBand}`}>
                Installing {offensiveCategoryActive} / {installMeta.recommended_plays_per_category} recommended
                · {installBandLabel(offensiveCategoryBand)}
              </span>
            ) : null}
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
                <div
                  key={p.play_id}
                  className={`playbook-gp-play-row${isActivePlayPct(p.pct) ? '' : ' playbook-gp-play-row--inactive'}`}
                >
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
            {!readOnly ? (
              <span className={`playbook-gp-install-badge playbook-gp-install-badge--${defensiveCategoryBand}`}>
                Installing {defensiveCategoryActive} / {installMeta.recommended_plays_per_category} recommended
                · {installBandLabel(defensiveCategoryBand)}
              </span>
            ) : null}
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
                <div
                  key={p.play_id}
                  className={`playbook-gp-play-row${isActivePlayPct(p.pct) ? '' : ' playbook-gp-play-row--inactive'}`}
                >
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
