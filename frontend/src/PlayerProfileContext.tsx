import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import PlayerProfilePage from './PlayerProfilePage'
import { buildPlayerStatRows } from './playerSeasonStats'

function findTeam(state: any, teamName: string) {
  return (state?.teams ?? []).find((t: any) => t?.name === teamName) ?? null
}

type PlayerProfileContextValue = {
  openPlayerProfile: (teamName: string, playerName: string) => void
}

const PlayerProfileContext = createContext<PlayerProfileContextValue | null>(null)

function noopOpenPlayerProfile(_teamName: string, _playerName: string) {}

export function useOpenPlayerProfile(): (teamName: string, playerName: string) => void {
  return useContext(PlayerProfileContext)?.openPlayerProfile ?? noopOpenPlayerProfile
}

type ProviderProps = {
  children: ReactNode
  saveState: any
  apiBase: string
  headers: Record<string, string>
  logoVersion: number
}

export function PlayerProfileProvider({ children, saveState, apiBase, headers, logoVersion }: ProviderProps) {
  const [profile, setProfile] = useState<{ teamName: string; player: any } | null>(null)

  const openPlayerProfile = useCallback(
    (teamName: string, playerName: string) => {
      const pn = String(playerName ?? '').trim()
      const tn = String(teamName ?? '').trim()
      if (!pn || !tn) return
      const t = findTeam(saveState, tn)
      const p = t?.roster?.find((x: any) => String(x?.name) === pn)
      if (p) {
        setProfile({ teamName: tn, player: p })
        return
      }
      const stat = buildPlayerStatRows(saveState).find((r) => r.teamName === tn && r.playerName === pn)
      setProfile({ teamName: tn, player: { name: pn, position: stat?.position ?? '—' } })
    },
    [saveState],
  )

  const value = useMemo(() => ({ openPlayerProfile }), [openPlayerProfile])

  return (
    <PlayerProfileContext.Provider value={value}>
      {children}
      {profile ? (
        <div className="player-profile-layer">
          <PlayerProfilePage
            apiBase={apiBase}
            headers={headers}
            logoVersion={logoVersion}
            teamName={profile.teamName}
            player={profile.player}
            saveState={saveState}
            onClose={() => setProfile(null)}
          />
        </div>
      ) : null}
    </PlayerProfileContext.Provider>
  )
}

type NameProps = {
  teamName: string
  playerName: string | null | undefined
  className?: string
  as?: 'span' | 'div' | 'td'
  children?: React.ReactNode
}

/** Double-click opens the player profile when name is valid (must be under PlayerProfileProvider). */
export function PlayerProfileName({ teamName, playerName, className = '', as: Tag = 'span', children }: NameProps) {
  const open = useOpenPlayerProfile()
  const raw = String(playerName ?? '').trim()
  const display = children ?? (playerName ?? '—')
  const clickable = Boolean(raw && raw !== '—')
  if (!clickable) {
    return <Tag className={className || undefined}>{display}</Tag>
  }
  return (
    <Tag
      className={[className, 'teamhome-roster-name--profile'].filter(Boolean).join(' ')}
      title="Double-click for profile"
      onDoubleClick={(e) => {
        e.stopPropagation()
        open(String(teamName).trim(), raw)
      }}
    >
      {display}
    </Tag>
  )
}
