import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent } from 'react'
import './NewSaveFlow.css'
import { buildTeamAssetLookup, suggestTeamForLogoFilename } from './logoMatch'
import { guessMime, type SaveBundle } from './saveBundle'
import TeamLogo from './TeamLogo'
import CustomLeagueInstructionsModal from './CustomLeagueInstructionsModal'
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
import CoachingCardPicker from './CoachingCardPicker'
import {
  CREATION_BONUS_CP_DEFAULT,
  CREATION_BONUS_CP_LOW_PRESTIGE,
  COACH_DEV_THRESHOLDS,
  creationBonusCpForPrestige,
} from './coachDevelopment'
import { EMPTY_COACHING_LOADOUT, computeLoadoutEquipCost, normalizeLoadout, type CoachingCardLoadout } from './coachingCards'

const STEPS_FULL = ['Save slot', 'Coach', 'Attributes', 'Your school'] as const
const STEPS_COACH = ['Coach', 'Attributes'] as const

export type NewSaveFlowMode = 'singleplayer' | 'multiplayer_admin' | 'multiplayer_coach'

const MAX_IMAGE_FILES = 200
const MAX_LOGO_BYTES = 5 * 1024 * 1024

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

type LogoRow = { file: File; team: string }

type Props = {
  apiBase: string
  headers: Record<string, string>
  getAuthHeaders?: () => Promise<Record<string, string>>
  onBack: () => void
  onCreated: (saveId: string, logos?: SaveBundle['logos']) => void
  onError: (msg: string) => void
  onSessionExpired?: () => void
  defaultCoachName?: string
  mode?: NewSaveFlowMode
  leagueId?: string
  fixedTeamName?: string
  onLeagueCreated?: (
    leagueId: string,
    logos?: SaveBundle['logos'],
    extras?: { commissioner_pin?: string; commissioner_email?: string },
  ) => void
  onCoachSetupComplete?: () => void
}

type SkillsState = typeof DEFAULT_SKILLS
type PlaybooksDataResponse = {
  offense_playbooks?: Record<string, { formations?: string[] }>
  defense_playbooks?: Record<string, { formations?: string[] }>
}

export function NewSaveFlow({
  apiBase,
  headers,
  getAuthHeaders,
  onBack,
  onCreated,
  onError,
  onSessionExpired,
  defaultCoachName,
  mode = 'singleplayer',
  leagueId,
  fixedTeamName,
  onLeagueCreated,
  onCoachSetupComplete,
}: Props) {
  const isMpAdmin = mode === 'multiplayer_admin'
  const isMpCoach = mode === 'multiplayer_coach'
  const firstStep = isMpCoach ? 1 : 0
  const lastStep = isMpCoach ? 2 : 3
  const stepLabels = isMpCoach ? STEPS_COACH : STEPS_FULL

  const [step, setStep] = useState(firstStep)
  const [saveName, setSaveName] = useState(isMpAdmin ? 'My Multiplayer League' : 'My Dynasty')
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
  const [allowCoachFiring, setAllowCoachFiring] = useState(false)
  const [disableTransfers, setDisableTransfers] = useState(false)
  const [teamSource, setTeamSource] = useState<'default' | 'upload'>('default')
  const [uploadedFileName, setUploadedFileName] = useState('')
  const [logoRows, setLogoRows] = useState<LogoRow[]>([])
  const logoFolderInputRef = useRef<HTMLInputElement | null>(null)
  const logoFilesInputRef = useRef<HTMLInputElement | null>(null)
  const [defaultLogoVersion, setDefaultLogoVersion] = useState<number | undefined>(undefined)
  const [showCustomLeagueHelp, setShowCustomLeagueHelp] = useState(false)
  const [coachingCardsLoadout, setCoachingCardsLoadout] = useState<CoachingCardLoadout>(() => ({ ...EMPTY_COACHING_LOADOUT }))
  const [hardcoreNoCards, setHardcoreNoCards] = useState(false)
  const defaultAdminEmail = defaultCoachName?.includes('@') ? defaultCoachName.trim() : ''
  const [commishIsSelf, setCommishIsSelf] = useState(true)
  const [commissionerEmail, setCommissionerEmail] = useState(defaultAdminEmail)
  const [commissionerLookupStatus, setCommissionerLookupStatus] = useState<'idle' | 'ok' | 'missing' | 'checking'>('idle')

  const setLogoFolderInputEl = useCallback((el: HTMLInputElement | null) => {
    logoFolderInputRef.current = el
    if (!el) return
    try {
      el.setAttribute('webkitdirectory', '')
      el.setAttribute('directory', '')
      el.multiple = true
    } catch {
      /* ignore */
    }
  }, [])

  const uploadedTeamNames = useMemo(() => {
    if (!teamsData?.teams) return []
    return teamsData.teams.map((t) => t.name).filter(Boolean) as string[]
  }, [teamsData])

  const sortedUploadedTeams = useMemo(
    () => [...uploadedTeamNames].sort((a, b) => a.localeCompare(b)),
    [uploadedTeamNames],
  )

  const logoAssetLookup = useMemo(() => buildTeamAssetLookup(teamsData?.teams ?? []), [teamsData])

  const suggestLogoTeam = useCallback(
    (filename: string, teams: string[]) => suggestTeamForLogoFilename(filename, teams, logoAssetLookup),
    [logoAssetLookup],
  )

  const buildLogoRowsFromFiles = (raw: File[]) => {
    const imageFiles = filterImageFiles(raw)
    if (imageFiles.length === 0) {
      onError(
        raw.length > 0
          ? `Found ${raw.length} file(s), but none were PNG, JPG, or WEBP.`
          : 'No image files were selected.',
      )
      return
    }
    if (!uploadedTeamNames.length) {
      onError('Upload your teams .json first so logos can be matched to schools.')
      return
    }
    const capped = imageFiles.length > MAX_IMAGE_FILES ? imageFiles.slice(0, MAX_IMAGE_FILES) : imageFiles
    setLogoRows(
      capped.map((file) => ({
        file,
        team: suggestLogoTeam(file.name, uploadedTeamNames),
      })),
    )
    if (imageFiles.length > MAX_IMAGE_FILES) {
      onError(`Showing first ${MAX_IMAGE_FILES} of ${imageFiles.length} images. Add more in Settings if needed.`)
    } else {
      onError('')
    }
  }

  const onLogoFolderChange = (e: ChangeEvent<HTMLInputElement>) => {
    buildLogoRowsFromFiles(snapshotFiles(e.target.files))
    e.target.value = ''
  }

  const onLogoFilesChange = (e: ChangeEvent<HTMLInputElement>) => {
    buildLogoRowsFromFiles(snapshotFiles(e.target.files))
    e.target.value = ''
  }

  const setLogoTeamAt = (index: number, team: string) => {
    setLogoRows((prev) => {
      const copy = [...prev]
      if (copy[index]) copy[index] = { ...copy[index], team }
      return copy
    })
  }

  const [pendingLogoUrls, setPendingLogoUrls] = useState<Record<string, string>>({})

  useEffect(() => {
    const urls: Record<string, string> = {}
    const objectUrls: string[] = []
    for (const row of logoRows) {
      const team = row.team.trim()
      if (!team) continue
      const url = URL.createObjectURL(row.file)
      objectUrls.push(url)
      urls[team] = url
    }
    setPendingLogoUrls(urls)
    return () => {
      for (const u of objectUrls) URL.revokeObjectURL(u)
    }
  }, [logoRows])

  useEffect(() => {
    let cancelled = false
    fetch(`${apiBase}/default-logos/version`, { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : null))
      .then((j: { version?: number } | null) => {
        if (!cancelled && j && typeof j.version === 'number') setDefaultLogoVersion(j.version)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [apiBase])

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
            'Make sure the API is running: python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000',
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
          'Is the API running? Start it from the project folder: python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000',
      )
    } finally {
      setLoadingTeams(false)
    }
  }, [apiBase, onError])

  const loadLeagueSchools = useCallback(async () => {
    if (!leagueId) return
    setLoadingTeams(true)
    onError('')
    try {
      const auth = getAuthHeaders ? await getAuthHeaders() : headers
      const r = await fetch(`${apiBase}/leagues/${leagueId}/schools`, {
        headers: auth,
        credentials: 'include',
      })
      if (!r.ok) {
        onError(await r.text())
        return
      }
      const data = (await r.json()) as { teams?: TeamJsonRow[] }
      setTeamsData({ teams: data.teams ?? [] })
      if (fixedTeamName) setUserTeam(fixedTeamName)
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : 'Could not load league schools')
    } finally {
      setLoadingTeams(false)
    }
  }, [apiBase, fixedTeamName, getAuthHeaders, headers, leagueId, onError])

  const lookupCommissionerEmail = useCallback(async () => {
    const email = commissionerEmail.trim()
    if (!email || commishIsSelf) {
      setCommissionerLookupStatus('idle')
      return
    }
    setCommissionerLookupStatus('checking')
    try {
      const auth = getAuthHeaders ? await getAuthHeaders() : headers
      const r = await fetch(`${apiBase}/leagues/admin/users/lookup?email=${encodeURIComponent(email)}`, {
        headers: auth,
      })
      setCommissionerLookupStatus(r.ok ? 'ok' : 'missing')
    } catch {
      setCommissionerLookupStatus('missing')
    }
  }, [apiBase, commishIsSelf, commissionerEmail, getAuthHeaders, headers])

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
    if (isMpCoach) {
      if (fixedTeamName) setUserTeam(fixedTeamName)
      if (leagueId) void loadLeagueSchools()
      return
    }
    if (!teamsData && !loadingTeams && teamSource === 'default') void loadTeamsData()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mount load only
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

  const goNext = async () => {
    if (step === 0) {
      if (!saveName.trim()) {
        onError('Enter a save name.')
        return
      }
      if (isMpAdmin && !commishIsSelf) {
        const em = commissionerEmail.trim()
        if (!em || !em.includes('@')) {
          onError('Enter a valid commissioner email.')
          return
        }
        if (commissionerLookupStatus === 'missing') {
          onError('No FND account found for that email. They must sign in once before you appoint them.')
          return
        }
        if (commissionerLookupStatus !== 'ok') {
          setCommissionerLookupStatus('checking')
          try {
            const auth = getAuthHeaders ? await getAuthHeaders() : headers
            const r = await fetch(
              `${apiBase}/leagues/admin/users/lookup?email=${encodeURIComponent(em)}`,
              { headers: auth },
            )
            if (!r.ok) {
              setCommissionerLookupStatus('missing')
              onError('No FND account found for that email. They must sign in once before you appoint them.')
              return
            }
            setCommissionerLookupStatus('ok')
          } catch {
            setCommissionerLookupStatus('missing')
            onError('Could not verify commissioner account.')
            return
          }
        }
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
    if (step === 0) {
      if (!saveName.trim()) return false
      if (isMpAdmin && !commishIsSelf) {
        const em = commissionerEmail.trim()
        return Boolean(em && em.includes('@'))
      }
      return true
    }
    if (step === 1) return Boolean(coachName.trim()) && coachAge >= 21 && coachAge <= 75
    if (step === 2) return true
    return false
  })()

  const goPrev = () => {
    onError('')
    if (step > firstStep) setStep(step - 1)
    else onBack()
  }

  const filteredTeams = useMemo(() => {
    const list = teamsData?.teams ?? []
    const q = teamSearch.trim().toLowerCase()
    if (!q) return list
    return list.filter((t) => t.name?.toLowerCase().includes(q))
  }, [teamsData, teamSearch])

  const selectedTeamRow = useMemo(
    () => (teamsData?.teams ?? []).find((t) => t.name === userTeam) ?? null,
    [teamsData, userTeam],
  )

  const skillsAllocatedCp = useMemo(() => {
    const keys = [
      'playcalling',
      'player_development',
      'community_outreach',
      'culture',
      'recruiting',
      'scheme_teach',
    ] as const
    return keys.reduce((sum, key) => {
      const lv = Math.max(1, Math.min(10, Number(skills[key] ?? 5)))
      return sum + (COACH_DEV_THRESHOLDS[lv] ?? 0)
    }, 0)
  }, [skills])

  const creationBonusCp = creationBonusCpForPrestige(selectedTeamRow?.prestige)
  const coachingCardEquipCp = hardcoreNoCards ? 0 : computeLoadoutEquipCost(coachingCardsLoadout)
  const creationUnallocatedCp = Math.round((creationBonusCp - coachingCardEquipCp) * 10) / 10

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
      coaching_cards: hardcoreNoCards ? { ...EMPTY_COACHING_LOADOUT } : normalizeLoadout(coachingCardsLoadout),
    }),
    [coachName, coachAge, skills, coachingCardsLoadout, hardcoreNoCards],
  )

  async function createSave() {
    if (!isMpCoach && !userTeam) {
      onError('Select a school.')
      return
    }
    if (isMpCoach && !fixedTeamName) {
      onError('Team not assigned.')
      return
    }
    setCreating(true)
    onError('')
    try {
      const auth = getAuthHeaders ? await getAuthHeaders() : headers
      if (!auth.Authorization) {
        onSessionExpired?.()
        return
      }

      if (isMpCoach && leagueId && fixedTeamName) {
        const r = await fetch(
          `${apiBase}/leagues/${leagueId}/teams/${encodeURIComponent(fixedTeamName)}/coach-setup`,
          {
            method: 'POST',
            headers: { ...auth, 'Content-Type': 'application/json' },
            body: JSON.stringify({ coach_config: coachConfig }),
          },
        )
        if (!r.ok) {
          if (r.status === 401) {
            onSessionExpired?.()
            return
          }
          try {
            const maybe = await r.json()
            onError(typeof maybe?.detail === 'string' ? maybe.detail : JSON.stringify(maybe))
          } catch {
            onError(await r.text())
          }
          return
        }
        onCoachSetupComplete?.()
        return
      }

      if (isMpAdmin) {
        const r = await fetch(`${apiBase}/leagues/admin/leagues`, {
          method: 'POST',
          headers: { ...auth, 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: saveName.trim(),
            user_team: userTeam,
            coach_config: coachConfig,
            start_year: startYear,
            teams_data: teamSource === 'upload' ? teamsData : undefined,
            allow_user_coach_firing: allowCoachFiring,
            transfers_disabled: disableTransfers,
            ...(commishIsSelf ? {} : { commissioner_email: commissionerEmail.trim() }),
          }),
        })
        if (!r.ok) {
          if (r.status === 401) {
            onSessionExpired?.()
            return
          }
          try {
            const maybe = await r.json()
            onError(typeof maybe?.detail === 'string' ? maybe.detail : JSON.stringify(maybe))
          } catch {
            onError(await r.text())
          }
          return
        }
        const created = (await r.json()) as {
          league_id?: string
          commissioner_pin?: string
          commissioner_email?: string
        }
        if (!created?.league_id) {
          onError('League created but no id returned.')
          return
        }
        const toUpload = logoRows.filter((row) => row.team.trim())
        let logosBundle: SaveBundle['logos'] | undefined
        if (toUpload.length > 0) {
          logosBundle = {}
          for (const { file, team } of toUpload) {
            if (file.size > MAX_LOGO_BYTES) {
              onError(`${file.name} is too large (max 5 MB).`)
              return
            }
            const form = new FormData()
            form.append('logo', file, file.name)
            const up = await fetch(
              `${apiBase}/leagues/${created.league_id}/logos/${encodeURIComponent(team.trim())}`,
              { method: 'POST', headers: auth.Authorization ? { Authorization: auth.Authorization } : {}, body: form },
            )
            if (!up.ok) {
              onError(`Logo upload failed for ${team}`)
              return
            }
            const buf = new Uint8Array(await file.arrayBuffer())
            logosBundle[team] = {
              filename: file.name,
              data: buf,
              mime: file.type?.startsWith('image/') ? file.type : guessMime(file.name),
            }
          }
        }
        onLeagueCreated?.(created.league_id, logosBundle, {
          commissioner_pin: created.commissioner_pin,
          commissioner_email: created.commissioner_email,
        })
        return
      }

      const r = await fetch(`${apiBase}/saves`, {
        method: 'POST',
        headers: { ...auth, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          save_name: saveName.trim(),
          user_team: userTeam,
          coach_config: coachConfig,
          start_year: startYear,
          teams_data: teamSource === 'upload' ? teamsData : undefined,
          allow_user_coach_firing: allowCoachFiring,
          transfers_disabled: disableTransfers,
        }),
      })
      if (!r.ok) {
        if (r.status === 401) {
          onSessionExpired?.()
          return
        }
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
      if (created?.save_id) {
        const toUpload = logoRows.filter((r) => r.team.trim())
        if (toUpload.length > 0) {
          const uploadHeaders: Record<string, string> = {}
          if (auth.Authorization) uploadHeaders.Authorization = auth.Authorization
          for (const { file, team } of toUpload) {
            if (file.size > MAX_LOGO_BYTES) {
              onError(`${file.name} is too large (max 5 MB).`)
              return
            }
            const fd = new FormData()
            fd.append('logo', file)
            const ur = await fetch(`${apiBase}/saves/logos/${encodeURIComponent(team)}`, {
              method: 'POST',
              headers: uploadHeaders,
              body: fd,
            })
            if (!ur.ok) {
              if (ur.status === 401) {
                onSessionExpired?.()
                return
              }
              try {
                const maybe = await ur.json()
                onError(typeof maybe?.detail === 'string' ? maybe.detail : `Failed to upload logo for ${team}`)
              } catch {
                onError(`Failed to upload logo for ${team}`)
              }
              return
            }
          }
        }
        let logosBundle: SaveBundle['logos'] | undefined
        if (toUpload.length > 0) {
          logosBundle = {}
          for (const { file, team } of toUpload) {
            const buf = new Uint8Array(await file.arrayBuffer())
            logosBundle[team] = {
              filename: file.name,
              data: buf,
              mime: file.type?.startsWith('image/') ? file.type : guessMime(file.name),
            }
          }
        }
        onCreated(created.save_id, logosBundle)
      } else onError('Save created but no id returned.')
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
      <button type="button" className="fnd-back" onClick={step === firstStep ? onBack : goPrev}>
        {step === firstStep ? '← Back' : '← Previous'}
      </button>

      <div className="newsave-steps">
        {stepLabels.map((label, i) => (
          <span key={label} className={i + firstStep === step ? 'active' : i + firstStep < step ? 'done' : ''}>
            {i + 1}. {label}
          </span>
        ))}
      </div>

      {step === 0 && !isMpCoach && (
        <>
          <h2 className="newsave-h3">
            {isMpAdmin ? 'League setup' : 'Dynasty save slot'}
            <span className="newsave-footnote-mark">*</span>
          </h2>
          <p className="newsave-sub">
            {isMpAdmin
              ? 'Name this multiplayer league and choose your team dataset (default or custom JSON).'
              : 'Name this save file. You can run multiple dynasties under the same coach login.'}
          </p>
          <input
            className="newsave-input"
            value={saveName}
            onChange={(e) => setSaveName(e.target.value)}
            placeholder="e.g. Year 1 — Martinsburg"
            autoFocus
          />
          {isMpAdmin ? (
            <div style={{ marginTop: 16 }}>
              <div className="newsave-sub" style={{ marginBottom: 8 }}>
                Commissioner
              </div>
              <label style={{ display: 'flex', gap: 10, alignItems: 'flex-start', marginBottom: 10, cursor: 'pointer' }}>
                <input
                  type="radio"
                  name="commish-mode"
                  checked={commishIsSelf}
                  onChange={() => {
                    setCommishIsSelf(true)
                    setCommissionerLookupStatus('idle')
                    onError('')
                  }}
                  style={{ marginTop: 3 }}
                />
                <span>
                  <strong>I am the commissioner</strong>
                  <span className="newsave-sub" style={{ display: 'block', marginTop: 4 }}>
                    You will run the league and coach the school you pick below.
                  </span>
                </span>
              </label>
              <label style={{ display: 'flex', gap: 10, alignItems: 'flex-start', cursor: 'pointer' }}>
                <input
                  type="radio"
                  name="commish-mode"
                  checked={!commishIsSelf}
                  onChange={() => {
                    setCommishIsSelf(false)
                    setCommissionerLookupStatus('idle')
                    onError('')
                  }}
                  style={{ marginTop: 3 }}
                />
                <span style={{ flex: 1 }}>
                  <strong>Appoint someone else</strong>
                  <span className="newsave-sub" style={{ display: 'block', marginTop: 4 }}>
                    They must have signed in to FND at least once. You still set up their school and coach profile
                    below.
                  </span>
                  {!commishIsSelf ? (
                    <>
                      <input
                        className="newsave-input"
                        type="email"
                        value={commissionerEmail}
                        onChange={(e) => {
                          setCommissionerEmail(e.target.value)
                          setCommissionerLookupStatus('idle')
                        }}
                        onBlur={() => void lookupCommissionerEmail()}
                        placeholder="commissioner@email.com"
                        style={{ marginTop: 8, marginBottom: 0 }}
                      />
                      {commissionerLookupStatus === 'checking' ? (
                        <span className="newsave-sub" style={{ display: 'block', marginTop: 6 }}>
                          Checking account…
                        </span>
                      ) : null}
                      {commissionerLookupStatus === 'ok' ? (
                        <span className="newsave-sub" style={{ display: 'block', marginTop: 6, color: '#86efac' }}>
                          Account found — ready to appoint.
                        </span>
                      ) : null}
                      {commissionerLookupStatus === 'missing' ? (
                        <span className="newsave-sub" style={{ display: 'block', marginTop: 6, color: '#f87171' }}>
                          No account found. Ask them to sign in once, then try again.
                        </span>
                      ) : null}
                    </>
                  ) : null}
                </span>
              </label>
            </div>
          ) : null}
          <div className="newsave-help-row">
            <button
              type="button"
              className="newsave-help-btn"
              onClick={() => setShowCustomLeagueHelp(true)}
            >
              How to upload a custom league
            </button>
            <span className="newsave-help-suffix">— Your States League</span>
          </div>
          <p className="newsave-footnote">
            <span className="newsave-footnote-mark newsave-footnote-mark--lead">*</span>
            {teamSource === 'upload'
              ? 'Custom leagues can add logos below. Import stadiums, helmets, and jerseys in Settings after your dynasty starts.'
              : 'Import logos, stadiums, helmets, and jerseys in Settings after your dynasty starts.'}
          </p>
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
          <label
            style={{ display: 'flex', gap: 10, alignItems: 'flex-start', marginTop: 16, cursor: 'pointer' }}
          >
            <input
              type="checkbox"
              checked={allowCoachFiring}
              onChange={(e) => setAllowCoachFiring(e.target.checked)}
              style={{ marginTop: 3 }}
            />
            <span>
              <strong>My coach can be fired or forced out</strong>
              <span className="newsave-sub" style={{ display: 'block', marginTop: 4 }}>
                Leave unchecked for a stable job: the school will not fire, bench, or auto-resign your head coach. You can
                still leave for another school only if you rank that job during the coaching carousel.
              </span>
            </span>
          </label>
          <label
            style={{ display: 'flex', gap: 10, alignItems: 'flex-start', marginTop: 12, cursor: 'pointer' }}
          >
            <input
              type="checkbox"
              checked={disableTransfers}
              onChange={(e) => setDisableTransfers(e.target.checked)}
              style={{ marginTop: 3 }}
            />
            <span>
              <strong>Disable transfers</strong>
              <span className="newsave-sub" style={{ display: 'block', marginTop: 4 }}>
                When checked, the transfer portal stages still appear in the offseason but no players enter the portal
                and no transfers occur league-wide.
              </span>
            </span>
          </label>
          <div style={{ marginTop: 14 }}>
            <div className="newsave-sub" style={{ marginBottom: 8 }}>
              Team dataset source
            </div>
            <div style={{ display: 'flex', gap: 10, alignItems: 'stretch', flexWrap: 'wrap' }}>
              <button
                type="button"
                className={`newsave-preset-card ${teamSource === 'default' ? 'selected' : ''}`}
                onClick={() => {
                  setTeamSource('default')
                  setUploadedFileName('')
                  setTeamsData(null)
                  setUserTeam('')
                  setLogoRows([])
                  loadTeamsData()
                }}
              >
                <strong>Default teams file</strong>
                <small>Use built-in league file (112 schools)</small>
              </button>
              <button
                type="button"
                className={`newsave-preset-card ${teamSource === 'upload' ? 'selected' : ''}`}
                onClick={() => {
                  setTeamSource('upload')
                  setTeamsData(null)
                  setUserTeam('')
                  setLogoRows([])
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
                    setLogoRows([])
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
            {teamSource === 'upload' ? (
              <div className="newsave-logo-section">
                <div className="newsave-sub" style={{ marginBottom: 8 }}>
                  League logos <span className="newsave-footnote-mark">(optional)</span>
                </div>
                {!teamsData ? (
                  <p className="newsave-footnote">Upload your teams .json first so filenames can be matched to schools.</p>
                ) : (
                  <>
                    <p className="newsave-footnote newsave-logo-hint">
                      Choose a <strong>folder</strong> or <strong>image files</strong>. We guess the school from each
                      filename (e.g. <code>Martinsburg.png</code> or an abbreviation). Change any row before you finish
                      setup — logos upload when you create the save.
                    </p>
                    <input
                      ref={setLogoFolderInputEl}
                      type="file"
                      className="newsave-file-input"
                      onChange={onLogoFolderChange}
                    />
                    <input
                      ref={logoFilesInputRef}
                      type="file"
                      multiple
                      accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp"
                      className="newsave-file-input"
                      onChange={onLogoFilesChange}
                    />
                    <div className="newsave-logo-actions">
                      <button
                        type="button"
                        className="fnd-title-btn newsave-logo-btn"
                        disabled={creating}
                        onClick={() => logoFolderInputRef.current?.click()}
                      >
                        Choose folder…
                      </button>
                      <button
                        type="button"
                        className="fnd-title-btn newsave-logo-btn newsave-logo-btn--secondary"
                        disabled={creating}
                        onClick={() => logoFilesInputRef.current?.click()}
                      >
                        Choose image files…
                      </button>
                    </div>
                    {logoRows.length > 0 ? (
                      <div className="newsave-logo-review">
                        <div className="newsave-logo-review-head">
                          <span>
                            {logoRows.filter((r) => r.team).length} of {logoRows.length} assigned
                          </span>
                          <button
                            type="button"
                            className="newsave-linkbtn"
                            disabled={creating}
                            onClick={() => setLogoRows([])}
                          >
                            Clear list
                          </button>
                        </div>
                        <div className="newsave-logo-table-wrap">
                          <table className="newsave-logo-table">
                            <thead>
                              <tr>
                                <th>File</th>
                                <th>Team</th>
                              </tr>
                            </thead>
                            <tbody>
                              {logoRows.map((row, i) => (
                                <tr key={`${row.file.name}-${i}-${row.file.size}`}>
                                  <td className="newsave-logo-filecell" title={row.file.name}>
                                    {row.file.name}
                                  </td>
                                  <td>
                                    <select
                                      className="newsave-select newsave-logo-team-select"
                                      value={row.team}
                                      onChange={(e) => setLogoTeamAt(i, e.target.value)}
                                      disabled={creating}
                                    >
                                      <option value="">— Skip —</option>
                                      {sortedUploadedTeams.map((t) => (
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
                      </div>
                    ) : null}
                  </>
                )}
              </div>
            ) : null}
          </div>
        </>
      )}

      {step === 1 && (
        <>
          <h2 className="newsave-h3">Coach profile</h2>
          {isMpCoach && fixedTeamName ? (
            <p className="newsave-sub">
              Build your head coach for <strong>{fixedTeamName}</strong> — same steps as starting a new dynasty.
            </p>
          ) : (
            <p className="newsave-sub">
              Pick an archetype (you can tune skills next), your name and age, and your offensive and defensive
              playbooks.
            </p>
          )}
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
          <CoachingCardPicker
            loadout={coachingCardsLoadout}
            onChange={setCoachingCardsLoadout}
            showHardcore
            hardcore={hardcoreNoCards}
            onHardcoreChange={setHardcoreNoCards}
            showCosts
            creationBonusCp={CREATION_BONUS_CP_DEFAULT}
            availableCp={
              hardcoreNoCards
                ? CREATION_BONUS_CP_DEFAULT
                : Math.round((CREATION_BONUS_CP_DEFAULT - computeLoadoutEquipCost(coachingCardsLoadout)) * 10) / 10
            }
          />
          <p className="newsave-sub" style={{ marginTop: 10 }}>
            Low-prestige schools receive <strong>{CREATION_BONUS_CP_LOW_PRESTIGE} CP</strong> creation bonus instead of{' '}
            <strong>{CREATION_BONUS_CP_DEFAULT}</strong>. Card costs apply when your dynasty starts; skill allocations use
            separate threshold CP.
          </p>
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
          {isMpCoach ? (
            <div className="newsave-summary" style={{ marginTop: '1.25rem' }}>
              <strong>Your school</strong>
              <br />
              You are coaching <strong>{fixedTeamName || userTeam || '—'}</strong> in this league.
              <br />
              Coach: <strong>{coachName.trim() || '—'}</strong> (age {coachAge}) ·{' '}
              {COACH_PRESETS.find((p) => p.id === presetId)?.title}
              <br />
              Playbooks: <strong>{skills.offensive_formation || '—'}</strong> (off) ·{' '}
              <strong>{skills.defensive_formation || '—'}</strong> (def)
            </div>
          ) : null}
        </>
      )}

      {step === 3 && !isMpCoach && (
        <>
          <h2 className="newsave-h3">Choose your school</h2>
          <p className="newsave-sub">
            {teamSource === 'upload'
              ? 'Loaded from your uploaded .json file.'
              : 'Loaded from data/teams.json.'}{' '}
            Pick the program you run.
          </p>
          {teamsData?.state ? (
            <p className="newsave-sub newsave-league-state">
              League state: <strong>{teamsData.state}</strong>
              {teamsData.league_id ? (
                <>
                  {' '}
                  · id <code>{teamsData.league_id}</code>
                </>
              ) : null}
            </p>
          ) : null}
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
                  <div className="tn">
                    <TeamLogo
                      apiBase={apiBase}
                      teamName={t.name}
                      headers={headers}
                      overrideSrc={pendingLogoUrls[t.name]}
                      preferDefaultLogos={teamSource === 'default' && !pendingLogoUrls[t.name]}
                      logoVersion={defaultLogoVersion}
                      hideWhenMissing
                      size={28}
                    />
                    <span>{t.name}</span>
                  </div>
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
            {isMpAdmin ? (
              <>
                Commissioner:{' '}
                <strong>{commishIsSelf ? 'You' : commissionerEmail.trim() || '—'}</strong>
                <br />
              </>
            ) : null}
            Coach: <strong>{coachName.trim() || '—'}</strong> (age {coachAge}) · {COACH_PRESETS.find((p) => p.id === presetId)?.title}
            <br />
            Playbooks: <strong>{skills.offensive_formation || '—'}</strong> (off) ·{' '}
            <strong>{skills.defensive_formation || '—'}</strong> (def)
            <br />
            School: <strong>{userTeam || '—'}</strong>
            <br />
            Opening CP: <strong>{skillsAllocatedCp}</strong> allocated to skills · <strong>{creationBonusCp}</strong>{' '}
            creation bonus
            {!hardcoreNoCards ? (
              <>
                {' '}
                · <strong>{coachingCardEquipCp}</strong> coaching cards
              </>
            ) : null}
            <br />
            Unallocated CP after cards:{' '}
            <strong style={{ color: creationUnallocatedCp < 0 ? '#b91c1c' : undefined }}>
              {creationUnallocatedCp}
            </strong>
          </div>
        </>
      )}

      <div className="newsave-nav">
        <button type="button" className="fnd-back" onClick={goPrev} style={{ marginBottom: 0 }}>
          {step === firstStep ? 'Main menu' : 'Back'}
        </button>
        {step < lastStep ? (
          <button type="button" className="fnd-title-btn" onClick={() => void goNext()} disabled={!canGoNext}>
            Next
          </button>
        ) : (
          <button
            type="button"
            className="fnd-title-btn"
            onClick={createSave}
            disabled={
              creating ||
              (!isMpCoach && !userTeam) ||
              !coachName.trim() ||
              coachAge < 21 ||
              coachAge > 75
            }
          >
            {creating
              ? 'Creating…'
              : isMpAdmin
                ? 'Create league'
                : isMpCoach
                  ? 'Finish coach profile'
                  : 'Create dynasty'}
          </button>
        )}
      </div>

      {showCustomLeagueHelp ? (
        <CustomLeagueInstructionsModal onClose={() => setShowCustomLeagueHelp(false)} />
      ) : null}
    </div>
  )
}
