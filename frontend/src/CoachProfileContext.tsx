import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type MouseEvent,
  type ReactNode,
} from 'react'
import CoachProfilePage from './CoachProfilePage'

function findTeam(state: any, teamName: string) {
  const want = String(teamName ?? '').trim()
  if (!want) return null
  const teams = state?.teams ?? []
  const exact = teams.find((t: any) => String(t?.name ?? '').trim() === want)
  if (exact) return exact
  const lower = want.toLowerCase()
  return teams.find((t: any) => String(t?.name ?? '').trim().toLowerCase() === lower) ?? null
}

type CoachProfileContextValue = {
  openCoachForTeam: (teamName: string) => void
  openCoachByName: (coachName: string) => void
}

const CoachProfileContext = createContext<CoachProfileContextValue | null>(null)

function noop() {}

export function useOpenCoachProfile(): CoachProfileContextValue {
  const ctx = useContext(CoachProfileContext)
  return (
    ctx ?? {
      openCoachForTeam: noop,
      openCoachByName: noop,
    }
  )
}

type ProviderProps = {
  children: ReactNode
  saveState: any
  apiBase: string
  headers: Record<string, string>
  saveId: string
  logoVersion: number
  leagueHistory?: any
  seasonRecaps?: Record<string, string>
  onError: (msg: string) => void
}

export function CoachProfileProvider({
  children,
  saveState,
  apiBase,
  headers,
  saveId,
  logoVersion,
  leagueHistory,
  seasonRecaps,
  onError,
}: ProviderProps) {
  const [profile, setProfile] = useState<{ teamName: string; coach: any } | null>(null)

  const openCoachForTeam = useCallback(
    (teamName: string) => {
      const tn = String(teamName ?? '').trim()
      if (!tn) return
      const t = findTeam(saveState, tn)
      const coach = t?.coach
      if (!coach?.name) return
      setProfile({ teamName: tn, coach })
    },
    [saveState],
  )

  const openCoachByName = useCallback(
    (coachName: string) => {
      const cn = String(coachName ?? '').trim()
      if (!cn || cn === '—') return
      const lower = cn.toLowerCase()
      let foundTeam = ''
      let foundCoach: any = null
      for (const t of saveState?.teams ?? []) {
        const nm = String(t?.coach?.name ?? '').trim()
        if (nm.toLowerCase() === lower) {
          foundTeam = String(t?.name ?? '')
          foundCoach = t.coach
          break
        }
      }
      if (!foundCoach) {
        setProfile({ teamName: String(saveState?.user_team ?? ''), coach: { name: cn } })
        return
      }
      setProfile({ teamName: foundTeam, coach: foundCoach })
    },
    [saveState],
  )

  const value = useMemo(
    () => ({ openCoachForTeam, openCoachByName }),
    [openCoachForTeam, openCoachByName],
  )

  return (
    <CoachProfileContext.Provider value={value}>
      {children}
      {profile ? (
        <div className="coach-profile-layer">
          <CoachProfilePage
            apiBase={apiBase}
            headers={headers}
            saveId={saveId}
            logoVersion={logoVersion}
            teamName={profile.teamName}
            coach={profile.coach}
            saveState={saveState}
            leagueHistory={leagueHistory}
            seasonRecaps={seasonRecaps}
            onClose={() => setProfile(null)}
            onError={onError}
          />
        </div>
      ) : null}
    </CoachProfileContext.Provider>
  )
}

type CoachNameProps = {
  /** Required when mode is `team` (open current coach for that program). */
  teamName?: string
  coachName: string | null | undefined
  mode: 'team' | 'by-name'
  className?: string
  as?: 'span' | 'div' | 'td'
  children?: React.ReactNode
}

/** Click opens coach profile (under CoachProfileProvider). */
export function CoachProfileName({
  teamName,
  coachName,
  mode,
  className = '',
  as: Tag = 'span',
  children,
}: CoachNameProps) {
  const { openCoachForTeam, openCoachByName } = useOpenCoachProfile()
  const raw = String(coachName ?? '').trim()
  const display = children ?? (coachName ?? '—')
  const clickable = Boolean(raw && raw !== '—')
  const activate = () => {
    if (mode === 'team') {
      const tn = String(teamName ?? '').trim()
      if (tn) openCoachForTeam(tn)
      else openCoachByName(raw)
    } else openCoachByName(raw)
  }
  const onActivateClick = (e: MouseEvent) => {
    e.stopPropagation()
    activate()
  }
  if (!clickable) {
    return <Tag className={className || undefined}>{display}</Tag>
  }
  return (
    <Tag
      role="button"
      tabIndex={0}
      className={[className, 'teamhome-roster-name--profile'].filter(Boolean).join(' ')}
      title="Click for coach profile"
      onClick={onActivateClick}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          e.stopPropagation()
          activate()
        }
      }}
    >
      {display}
    </Tag>
  )
}
