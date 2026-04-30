import { useCallback, useEffect, useMemo, useState } from 'react'
import './NewSaveFlow.css'
import {
  COACH_PRESETS,
  DEFAULT_SKILLS,
  DEFENSIVE_STYLES,
  DEFENSIVE_PLAYBOOK_TO_FORMATIONS,
  DEFENSIVE_PLAYBOOKS,
  OFFENSIVE_PLAYBOOK_TO_FORMATIONS,
  OFFENSIVE_PLAYBOOKS,
  OFFENSIVE_STYLES,
  type TeamJsonRow,
  type TeamsDataResponse,
} from './newSaveTypes'

const STEPS = ['Save slot', 'Coach', 'Attributes', 'Your school'] as const

type Props = {
  apiBase: string
  headers: Record<string, string>
  onBack: () => void
  onCreated: (saveId: string) => void
  onError: (msg: string) => void
  defaultCoachName?: string
}

type SkillsState = typeof DEFAULT_SKILLS
type PlaybooksDataResponse = {
  offense_playbooks?: Record<string, { formations?: string[] }>
  defense_playbooks?: Record<string, { formations?: string[] }>
}

export function NewSaveFlow({
  apiBase,
  headers,
  onBack,
  onCreated,
  onError,
  defaultCoachName,
}: Props) {
  const [step, setStep] = useState(0)
  const [saveName, setSaveName] = useState('My Dynasty')
  const [startYear, setStartYear] = useState<number>(2026)
  const [presetId, setPresetId] = useState('balanced')
  const [coachName, setCoachName] = useState(defaultCoachName?.trim() || 'Coach')
  const [coachAge, setCoachAge] = useState(38)
  const [skills, setSkills] = useState<SkillsState>({ ...DEFAULT_SKILLS })
  const [userTeam, setUserTeam] = useState('')
  const [teamSearch, setTeamSearch] = useState('')
  const [teamsData, setTeamsData] = useState<TeamsDataResponse | null>(null)
  const [loadingTeams, setLoadingTeams] = useState(false)
  const [offensivePlaybooks, setOffensivePlaybooks] = useState<string[]>([...OFFENSIVE_PLAYBOOKS])
  const [defensivePlaybooks, setDefensivePlaybooks] = useState<string[]>([...DEFENSIVE_PLAYBOOKS])
  const [offensivePlaybookToFormations, setOffensivePlaybookToFormations] = useState<Record<string, string[]>>(
    OFFENSIVE_PLAYBOOK_TO_FORMATIONS as Record<string, string[]>,
  )
  const [defensivePlaybookToFormations, setDefensivePlaybookToFormations] = useState<Record<string, string[]>>(
    DEFENSIVE_PLAYBOOK_TO_FORMATIONS as Record<string, string[]>,
  )
  const [creating, setCreating] = useState(false)
  const [teamSource, setTeamSource] = useState<'default' | 'upload'>('default')
  const [uploadedFileName, setUploadedFileName] = useState('')

  const loadTeamsData = useCallback(async () => {
    setLoadingTeams(true)
    onError('')
    try {
      const url = `${apiBase}/teams-data`
      const r = await fetch(url, { credentials: 'include' })
      if (!r.ok) {
        const body = await r.text()
        onError(
          `Teams request failed (${r.status}). ${body || r.statusText}. ` +
            'Make sure the API is running: python -m uvicorn backend.app:app --host 127.0.0.1 --port 8001',
        )
        return
      }
      const data = (await r.json()) as TeamsDataResponse
      const teams = data.teams ?? []
      if (!teams.length && (data as any)._debug) {
        onError(
          `No teams found. Path: ${(data as any)._debug?.path || 'unknown'}. ` +
            'Ensure data/teams.json exists in the project folder.',
        )
        return
      }
      setTeamsData(data)
      const names = teams.map((t) => t.name).filter(Boolean)
      setUserTeam((prev) => (prev && names.includes(prev) ? prev : names[0] || ''))
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Network error'
      onError(
        `Could not load teams (${msg}). ` +
          'Is the API running? Start it from the project folder: python -m uvicorn backend.app:app --host 127.0.0.1 --port 8001',
      )
    } finally {
      setLoadingTeams(false)
    }
  }, [apiBase, onError])

  const loadPlaybooksData = useCallback(async () => {
    const offFallback = { ...(OFFENSIVE_PLAYBOOK_TO_FORMATIONS as Record<string, string[]>) }
    const defFallback = { ...(DEFENSIVE_PLAYBOOK_TO_FORMATIONS as Record<string, string[]>) }

    const mergePlaybooks = (
      fromApi: Record<string, { formations?: string[] }>,
      fallback: Record<string, string[]>,
      preferredOrder: readonly string[],
    ) => {
      const merged: Record<string, string[]> = { ...fallback }
      for (const k of Object.keys(fromApi)) {
        const f = fromApi[k]?.formations
        if (Array.isArray(f) && f.length) merged[k] = f
      }
      const keys = [...preferredOrder]
      for (const k of Object.keys(merged)) {
        if (!keys.includes(k)) keys.push(k)
      }
      return { keys, map: merged }
    }

    try {
      const r = await fetch(`${apiBase}/playbooks-data`, { credentials: 'include' })
      if (!r.ok) {
        setOffensivePlaybooks([...OFFENSIVE_PLAYBOOKS])
        setOffensivePlaybookToFormations(offFallback)
        setDefensivePlaybooks([...DEFENSIVE_PLAYBOOKS])
        setDefensivePlaybookToFormations(defFallback)
        return
      }
      const data = (await r.json()) as PlaybooksDataResponse
      const off = mergePlaybooks(data.offense_playbooks ?? {}, offFallback, OFFENSIVE_PLAYBOOKS)
      const def = mergePlaybooks(data.defense_playbooks ?? {}, defFallback, DEFENSIVE_PLAYBOOKS)
      setOffensivePlaybooks(off.keys)
      setOffensivePlaybookToFormations(off.map)
      setDefensivePlaybooks(def.keys)
      setDefensivePlaybookToFormations(def.map)
    } catch {
      setOffensivePlaybooks([...OFFENSIVE_PLAYBOOKS])
      setOffensivePlaybookToFormations(offFallback)
      setDefensivePlaybooks([...DEFENSIVE_PLAYBOOKS])
      setDefensivePlaybookToFormations(defFallback)
    }
  }, [apiBase])

  useEffect(() => {
    if (!teamsData && !loadingTeams && teamSource === 'default') loadTeamsData()
  }, [])

  useEffect(() => {
    loadPlaybooksData()
  }, [loadPlaybooksData])

  useEffect(() => {
    if (!offensivePlaybooks.includes(skills.offensive_formation) && offensivePlaybooks.length) {
      setSkills((s) => ({ ...s, offensive_formation: offensivePlaybooks[0] }))
    }
  }, [offensivePlaybooks, skills.offensive_formation])

  useEffect(() => {
    if (!defensivePlaybooks.includes(skills.defensive_formation) && defensivePlaybooks.length) {
      setSkills((s) => ({ ...s, defensive_formation: defensivePlaybooks[0] }))
    }
  }, [defensivePlaybooks, skills.defensive_formation])

  const applyPresetToSkills = useCallback(() => {
    const p = COACH_PRESETS.find((x) => x.id === presetId)
    setSkills((prev) => ({
      ...DEFAULT_SKILLS,
      ...(p?.config || {}),
      offensive_formation: prev.offensive_formation,
      defensive_formation: prev.defensive_formation,
    }))
  }, [presetId])

  const goNext = () => {
    if (step === 0) {
      if (!saveName.trim()) {
        onError('Enter a save name.')
        return
      }
      if (!Number.isFinite(startYear) || startYear < 1900) {
        onError('Start year must be 1900 or later.')
        return
      }
      onError('')
      setStep(1)
      return
    }
    if (step === 1) {
      if (!coachName.trim()) {
        onError('Enter your coach name.')
        return
      }
      if (coachAge < 21 || coachAge > 75) {
        onError('Coach age must be between 21 and 75.')
        return
      }
      applyPresetToSkills()
      onError('')
      setStep(2)
      return
    }
    if (step === 2) {
      onError('')
      setStep(3)
      return
    }
  }

  const canGoNext = (() => {
    if (step === 0) return Boolean(saveName.trim())
    if (step === 1) return Boolean(coachName.trim()) && coachAge >= 21 && coachAge <= 75
    if (step === 2) return true
    return false
  })()

  const goPrev = () => {
    onError('')
    if (step > 0) setStep(step - 1)
    else onBack()
  }

  const filteredTeams = useMemo(() => {
    const list = teamsData?.teams ?? []
    const q = teamSearch.trim().toLowerCase()
    if (!q) return list
    return list.filter((t) => t.name?.toLowerCase().includes(q))
  }, [teamsData, teamSearch])

  const coachConfig = useMemo(
    () => ({
      name: coachName.trim(),
      age: coachAge,
      playcalling: skills.playcalling,
      player_development: skills.player_development,
      community_outreach: skills.community_outreach,
      culture: skills.culture,
      recruiting: skills.recruiting,
      scheme_teach: skills.scheme_teach,
      offensive_style: skills.offensive_style,
      defensive_style: skills.defensive_style,
      winter_strength_pct: skills.winter_strength_pct,
      offensive_formation: skills.offensive_formation,
      defensive_formation: skills.defensive_formation,
    }),
    [coachName, coachAge, skills],
  )

  async function createSave() {
    if (!userTeam) {
      onError('Select a school.')
      return
    }
    setCreating(true)
    onError('')
    try {
      const r = await fetch(`${apiBase}/saves`, {
        method: 'POST',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          save_name: saveName.trim(),
          user_team: userTeam,
          coach_config: coachConfig,
          start_year: startYear,
          teams_data: teamSource === 'upload' ? teamsData : undefined,
        }),
      })
      if (!r.ok) {
        // FastAPI errors are often JSON: { detail: "..." }
        try {
          const maybe = await r.json()
          if (typeof maybe?.detail === 'string') {
            onError(maybe.detail)
          } else {
            onError(JSON.stringify(maybe))
          }
        } catch {
          onError(await r.text())
        }
        return
      }
      const created = await r.json()
      if (created?.save_id) onCreated(created.save_id)
      else onError('Save created but no id returned.')
    } finally {
      setCreating(false)
    }
  }

  const skill = (key: keyof typeof DEFAULT_SKILLS, label: string) => {
    if (key === 'offensive_style' || key === 'defensive_style') return null
    if (key === 'offensive_formation' || key === 'defensive_formation') return null
    if (key === 'winter_strength_pct') return null
    const v = skills[key] as number
    return (
      <div className="newsave-slider-block" key={key}>
        <label>
          <span>{label}</span>
          <span>{v}</span>
        </label>
        <input
          type="range"
          min={1}
          max={10}
          value={v}
          onChange={(e) => setSkills((s) => ({ ...s, [key]: Number(e.target.value) }))}
        />
      </div>
    )
  }

  return (
    <div className="newsave-root fnd-panel" style={{ maxWidth: 760 }}>
      <button type="button" className="fnd-back" onClick={step === 0 ? onBack : goPrev}>
        {step === 0 ? '← Back' : '← Previous'}
      </button>

      <div className="newsave-steps">
        {STEPS.map((label, i) => (
          <span key={label} className={i === step ? 'active' : i < step ? 'done' : ''}>
            {i + 1}. {label}
          </span>
        ))}
      </div>

      {step === 0 && (
        <>
          <h2 className="newsave-h3">Dynasty save slot</h2>
          <p className="newsave-sub">Name this save file. You can run multiple dynasties under the same coach login.</p>
          <input
            className="newsave-input"
            value={saveName}
            onChange={(e) => setSaveName(e.target.value)}
            placeholder="e.g. Year 1 — Martinsburg"
            autoFocus
          />
          <div className="newsave-row2" style={{ marginTop: 12 }}>
            <div />
            <div>
              <label className="newsave-sub" style={{ display: 'block', marginBottom: 6 }}>
                Start year (1900+)
              </label>
              <input
                className="newsave-input"
                type="number"
                min={1900}
                step={1}
                value={startYear}
                onChange={(e) => setStartYear(Number(e.target.value) || 1900)}
                style={{ marginBottom: 0 }}
              />
            </div>
          </div>
          <div style={{ marginTop: 14 }}>
            <div className="newsave-sub" style={{ marginBottom: 8 }}>
              Team dataset source
            </div>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              <button
                type="button"
                className={`newsave-preset-card ${teamSource === 'default' ? 'selected' : ''}`}
                onClick={() => {
                  setTeamSource('default')
                  setUploadedFileName('')
                  setTeamsData(null)
                  setUserTeam('')
                  loadTeamsData()
                }}
              >
                <strong>Default teams file</strong>
                <small>Use built-in data/teams.json</small>
              </button>
              <button
                type="button"
                className={`newsave-preset-card ${teamSource === 'upload' ? 'selected' : ''}`}
                onClick={() => {
                  setTeamSource('upload')
                  setTeamsData(null)
                  setUserTeam('')
                }}
              >
                <strong>Upload .json</strong>
                <small>Use a custom teams dataset</small>
              </button>
            </div>
            {teamSource === 'upload' ? (
              <div style={{ marginTop: 10 }}>
                <input
                  type="file"
                  accept=".json,application/json"
                  onChange={async (e) => {
                    const f = e.target.files?.[0]
                    if (!f) return
                    setUploadedFileName(f.name)
                    onError('')
                    try {
                      const txt = await f.text()
                      const parsed = JSON.parse(txt) as TeamsDataResponse
                      const teams = Array.isArray(parsed?.teams) ? parsed.teams : []
                      if (!teams.length) {
                        onError('Uploaded JSON has no teams array (or it is empty).')
                        setTeamsData(null)
                        setUserTeam('')
                        return
                      }
                      setTeamsData(parsed)
                      const names = teams.map((t) => t.name).filter(Boolean)
                      setUserTeam(names[0] || '')
                    } catch (err: any) {
                      onError(err?.message ? `Invalid JSON file: ${err.message}` : 'Invalid JSON file.')
                      setTeamsData(null)
                      setUserTeam('')
                    }
                  }}
                />
                <div className="newsave-sub" style={{ marginTop: 6 }}>
                  {uploadedFileName ? `Selected: ${uploadedFileName}` : 'No file selected'}
                </div>
              </div>
            ) : null}
          </div>
        </>
      )}

      {step === 1 && (
        <>
          <h2 className="newsave-h3">Coach profile</h2>
          <p className="newsave-sub">
            Pick an archetype (you can tune skills next), your name and age, and your offensive and defensive playbooks.
          </p>
          <div className="newsave-presets">
            {COACH_PRESETS.map((p) => (
              <button
                key={p.id}
                type="button"
                className={`newsave-preset-card ${presetId === p.id ? 'selected' : ''}`}
                onClick={() => setPresetId(p.id)}
              >
                <strong>{p.title}</strong>
                <small>{p.blurb}</small>
              </button>
            ))}
          </div>
          <input
            className="newsave-input"
            value={coachName}
            onChange={(e) => setCoachName(e.target.value)}
            placeholder="Coach name (display)"
          />
          <div className="newsave-row2">
            <div />
            <div>
              <label className="newsave-sub" style={{ display: 'block', marginBottom: 6 }}>
                Age
              </label>
              <input
                className="newsave-input"
                type="number"
                min={21}
                max={75}
                value={coachAge}
                onChange={(e) => setCoachAge(Number(e.target.value) || 35)}
                style={{ marginBottom: 0 }}
              />
            </div>
          </div>
          <p className="newsave-sub" style={{ marginTop: '1rem' }}>
            Choose your season playbooks (you can change later in preseason when eligible).
          </p>
          <div className="newsave-row2" style={{ gridTemplateColumns: '1fr 1fr', marginTop: 8 }}>
            <div>
              <label className="newsave-sub" style={{ display: 'block', marginBottom: 6 }}>
                Offensive playbook
              </label>
              <select
                className="newsave-select"
                value={skills.offensive_formation}
                onChange={(e) => setSkills((s) => ({ ...s, offensive_formation: e.target.value }))}
                style={{ marginBottom: 6 }}
              >
                {offensivePlaybooks.map((pb) => (
                  <option key={pb} value={pb}>
                    {pb}
                  </option>
                ))}
              </select>
              <div className="newsave-sub" style={{ opacity: 0.8, marginTop: 0 }}>
                {skills.offensive_formation ? (
                  <>Includes: {offensivePlaybookToFormations[skills.offensive_formation]?.join(' / ') ?? '—'}</>
                ) : (
                  '—'
                )}
              </div>
            </div>
            <div>
              <label className="newsave-sub" style={{ display: 'block', marginBottom: 6 }}>
                Defensive playbook
              </label>
              <select
                className="newsave-select"
                value={skills.defensive_formation}
                onChange={(e) => setSkills((s) => ({ ...s, defensive_formation: e.target.value }))}
                style={{ marginBottom: 6 }}
              >
                {defensivePlaybooks.map((pb) => (
                  <option key={pb} value={pb}>
                    {pb}
                  </option>
                ))}
              </select>
              <div className="newsave-sub" style={{ opacity: 0.8, marginTop: 0 }}>
                {skills.defensive_formation ? (
                  <>Includes: {defensivePlaybookToFormations[skills.defensive_formation]?.join(' / ') ?? '—'}</>
                ) : (
                  '—'
                )}
              </div>
            </div>
          </div>
        </>
      )}

      {step === 2 && (
        <>
          <h2 className="newsave-h3">Coach attributes</h2>
          <p className="newsave-sub">Skills are 1–10. Philosophy matches how your staff prefers to play.</p>
          {skill('playcalling', 'Playcalling')}
          {skill('scheme_teach', 'Scheme teach')}
          {skill('player_development', 'Player development')}
          {skill('recruiting', 'Recruiting')}
          {skill('community_outreach', 'Community / boosters')}
          {skill('culture', 'Program culture')}
          <label className="newsave-sub" style={{ display: 'block', marginTop: '1rem' }}>
            Offensive philosophy
          </label>
          <select
            className="newsave-select"
            value={skills.offensive_style}
            onChange={(e) => setSkills((s) => ({ ...s, offensive_style: e.target.value }))}
          >
            {OFFENSIVE_STYLES.map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </select>
          <label className="newsave-sub" style={{ display: 'block' }}>
            Defensive philosophy
          </label>
          <select
            className="newsave-select"
            value={skills.defensive_style}
            onChange={(e) => setSkills((s) => ({ ...s, defensive_style: e.target.value }))}
          >
            {DEFENSIVE_STYLES.map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </select>
          <label className="newsave-sub" style={{ display: 'block', marginTop: '0.75rem' }}>
            Winter strength focus (% strength vs speed)
          </label>
          <div className="newsave-slider-block">
            <label>
              <span>Strength</span>
              <span>{skills.winter_strength_pct}%</span>
            </label>
            <input
              type="range"
              min={0}
              max={100}
              value={skills.winter_strength_pct}
              onChange={(e) => setSkills((s) => ({ ...s, winter_strength_pct: Number(e.target.value) }))}
            />
          </div>
        </>
      )}

      {step === 3 && (
        <>
          <h2 className="newsave-h3">Choose your school</h2>
          <p className="newsave-sub">
            {teamSource === 'upload'
              ? 'Loaded from your uploaded .json file.'
              : 'Loaded from data/teams.json.'}{' '}
            Pick the program you run.
          </p>
          {teamsData?._schema ? <div className="newsave-schema">{teamsData._schema}</div> : null}
          <input
            className="newsave-input newsave-team-search"
            value={teamSearch}
            onChange={(e) => setTeamSearch(e.target.value)}
            placeholder="Search schools…"
          />
          {loadingTeams ? (
            <p className="newsave-sub">Loading teams…</p>
          ) : !teamsData?.teams?.length ? (
            <p className="newsave-sub">
              No teams loaded.{' '}
              <button type="button" className="newsave-retry" onClick={() => loadTeamsData()}>
                Retry
              </button>
            </p>
          ) : (
            <div className="newsave-team-grid">
              {filteredTeams.map((t: TeamJsonRow) => (
                <button
                  key={t.name}
                  type="button"
                  className={`newsave-team-card ${userTeam === t.name ? 'selected' : ''}`}
                  onClick={() => setUserTeam(t.name)}
                >
                  <div className="tn">{t.name}</div>
                  <div className="tm">
                    <span>
                      {t.classification ?? '—'} · Prestige {t.prestige ?? '—'}
                    </span>
                    <span>
                      Culture {t.culture_grade ?? '—'} · Boosters {t.booster_support ?? '—'} · Facilities{' '}
                      {t.facilities_grade ?? '—'}
                    </span>
                    <span>
                      {t.community ?? '—'}
                      {t.enrollment != null ? ` · ${t.enrollment} enrolled` : ''}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          )}
          <div className="newsave-summary" style={{ marginTop: '1.25rem' }}>
            <strong>Ready to start</strong>
            <br />
            Save: <strong>{saveName.trim() || '—'}</strong>
            <br />
            Coach: <strong>{coachName.trim() || '—'}</strong> (age {coachAge}) · {COACH_PRESETS.find((p) => p.id === presetId)?.title}
            <br />
            Playbooks: <strong>{skills.offensive_formation || '—'}</strong> (off) ·{' '}
            <strong>{skills.defensive_formation || '—'}</strong> (def)
            <br />
            School: <strong>{userTeam || '—'}</strong>
          </div>
        </>
      )}

      <div className="newsave-nav">
        <button type="button" className="fnd-back" onClick={goPrev} style={{ marginBottom: 0 }}>
          {step === 0 ? 'Main menu' : 'Back'}
        </button>
        {step < 3 ? (
          <button type="button" className="fnd-title-btn" onClick={goNext} disabled={!canGoNext}>
            Next
          </button>
        ) : (
          <button
            type="button"
            className="fnd-title-btn"
            onClick={createSave}
            disabled={creating || !userTeam || !coachName.trim() || coachAge < 21 || coachAge > 75}
          >
            {creating ? 'Creating…' : 'Create dynasty'}
          </button>
        )}
      </div>
    </div>
  )
}
