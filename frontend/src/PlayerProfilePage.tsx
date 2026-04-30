import { Fragment, useMemo } from 'react'
import TeamLogo from './TeamLogo'
import { formatPlayerAttributeCell, formatPlayerMeasureLine } from './playerAttributes'
import { buildPlayerStatRows, type PlayerStatRow } from './playerSeasonStats'
import './PlayerProfilePage.css'

const OFFENSE_POSITIONS = ['QB', 'RB', 'WR', 'OL', 'TE'] as const
const DEFENSE_POSITIONS = ['DE', 'DT', 'LB', 'CB', 'S'] as const

function computeOffenseRating(p: any, pos: string) {
  const get = (k: string) => Number(p?.[k] ?? 0)
  if (pos === 'QB') return (get('throw_power') + get('throw_accuracy') + get('decisions') + get('football_iq')) / 4
  if (pos === 'RB') return (get('speed') + get('break_tackle') + get('vision') + get('ball_security') + get('catching')) / 5
  if (pos === 'WR' || pos === 'TE') return (get('catching') + get('route_running') + get('speed') + get('agility')) / 4
  if (pos === 'OL') return (get('run_blocking') + get('pass_blocking') + get('strength')) / 3
  return 0
}

function computeDefenseRating(p: any, pos: string) {
  const get = (k: string) => Number(p?.[k] ?? 0)
  if (pos === 'DE' || pos === 'DT') return (get('pass_rush') + get('run_defense') + get('block_shedding') + get('strength')) / 4
  if (pos === 'LB') return (get('tackling') + get('pursuit') + get('coverage') + get('run_defense')) / 4
  if (pos === 'CB' || pos === 'S') return (get('coverage') + get('speed') + get('agility') + get('tackling')) / 4
  return 0
}

function computePlayerOverall(p: any) {
  const keys = [
    'speed',
    'agility',
    'acceleration',
    'strength',
    'football_iq',
    'coachability',
    'throw_accuracy',
    'catching',
    'run_blocking',
    'pass_blocking',
    'tackling',
    'coverage',
  ]
  const vals = keys.map((k) => Number(p?.[k] ?? 50))
  const avg = vals.reduce((a, b) => a + b, 0) / vals.length
  return Math.round(avg)
}

function getPlayerSidePosition(p: any, side: 'offense' | 'defense') {
  const allowed = (side === 'offense' ? OFFENSE_POSITIONS : DEFENSE_POSITIONS) as readonly string[]
  const primary = String(p?.position ?? '')
  const secondary = String(p?.secondary_position ?? '')
  if (allowed.includes(primary)) return primary
  if (allowed.includes(secondary)) return secondary
  return '—'
}

function getBestSideRating(p: any, side: 'offense' | 'defense') {
  const allowed = (side === 'offense' ? OFFENSE_POSITIONS : DEFENSE_POSITIONS) as readonly string[]
  const rate = side === 'offense' ? computeOffenseRating : computeDefenseRating
  const candidates = [String(p?.position ?? ''), String(p?.secondary_position ?? '')].filter((pos) =>
    allowed.includes(pos),
  )
  if (candidates.length === 0) return 0
  let best = 0
  for (const pos of candidates) best = Math.max(best, rate(p, pos))
  return Math.round(best)
}

function formatPlayerYear(year: any) {
  if (year == null) return '—'
  const n = Number(year)
  if (Number.isNaN(n)) return String(year)
  if (n === 9 || n === 1) return 'FR'
  if (n === 10 || n === 2) return 'SO'
  if (n === 11 || n === 3) return 'JR'
  if (n === 12 || n === 4) return 'SR'
  return String(year)
}

const PROFILE_ATTRIBUTE_GROUPS: ReadonlyArray<{ title: string; keys: readonly string[] }> = [
  {
    title: 'Physical',
    keys: [
      'frame',
      'speed',
      'agility',
      'acceleration',
      'strength',
      'balance',
      'jumping',
      'stamina',
      'injury',
    ],
  },
  {
    title: 'Mental',
    keys: ['toughness', 'effort', 'football_iq', 'coachability', 'confidence', 'discipline', 'leadership', 'composure'],
  },
  {
    title: 'Offense',
    keys: [
      'throw_power',
      'throw_accuracy',
      'decisions',
      'catching',
      'run_blocking',
      'pass_blocking',
      'vision',
      'ball_security',
      'break_tackle',
      'elusiveness',
      'route_running',
    ],
  },
  {
    title: 'Defense',
    keys: ['coverage', 'blitz', 'pass_rush', 'run_defense', 'pursuit', 'tackling', 'block_shedding'],
  },
  { title: 'Kicking', keys: ['kick_power', 'kick_accuracy'] },
  {
    title: 'Development',
    keys: ['potential', 'growth_rate', 'peak_age', 'consistency', 'late_bloomer', 'early_bloomer', 'age', 'year'],
  },
]

const ATTR_LABELS: Record<string, string> = {
  speed: 'Speed',
  agility: 'Agility',
  acceleration: 'Acceleration',
  strength: 'Strength',
  balance: 'Balance',
  jumping: 'Jumping',
  stamina: 'Stamina',
  injury: 'Injury',
  frame: 'Frame',
  height: 'Height',
  weight: 'Weight',
  toughness: 'Toughness',
  effort: 'Effort',
  football_iq: 'Football IQ',
  coachability: 'Coachability',
  confidence: 'Confidence',
  discipline: 'Discipline',
  leadership: 'Leadership',
  composure: 'Composure',
  throw_power: 'Throw power',
  throw_accuracy: 'Throw accuracy',
  decisions: 'Decisions',
  catching: 'Catching',
  run_blocking: 'Run block',
  pass_blocking: 'Pass block',
  vision: 'Vision',
  ball_security: 'Ball security',
  break_tackle: 'Break tackle',
  elusiveness: 'Elusiveness',
  route_running: 'Route running',
  coverage: 'Coverage',
  blitz: 'Blitz',
  pass_rush: 'Pass rush',
  run_defense: 'Run defense',
  pursuit: 'Pursuit',
  tackling: 'Tackling',
  block_shedding: 'Block shed',
  kick_power: 'Kick power',
  kick_accuracy: 'Kick accuracy',
  potential: 'Potential',
  growth_rate: 'Growth rate',
  peak_age: 'Peak age',
  consistency: 'Consistency',
  late_bloomer: 'Late bloomer',
  early_bloomer: 'Early bloomer',
  age: 'Age',
  year: 'Class year',
}

function statRowHasActivity(r: PlayerStatRow) {
  return (
    r.passYds +
      r.passTd +
      r.comp +
      r.att +
      r.intThrown +
      r.rushYds +
      r.rushTd +
      r.rec +
      r.recYds +
      r.recTd +
      r.tackles +
      r.sacks +
      r.tfl +
      r.interceptions >
    0
  )
}

type Props = {
  apiBase: string
  headers: Record<string, string>
  logoVersion: number
  teamName: string
  player: any
  saveState: any
  onClose: () => void
}

export default function PlayerProfilePage({
  apiBase,
  headers,
  logoVersion,
  teamName,
  player,
  saveState,
  onClose,
}: Props) {
  const name = String(player?.name ?? 'Unknown')
  const position = String(player?.position ?? '—')
  const secondary = String(player?.secondary_position ?? '')
  const posLine =
    secondary && secondary !== '—' ? `${position} / ${secondary}` : position

  const offPos = getPlayerSidePosition(player, 'offense')
  const defPos = getPlayerSidePosition(player, 'defense')
  const offRtg = offPos === '—' ? '—' : String(getBestSideRating(player, 'offense'))
  const defRtg = defPos === '—' ? '—' : String(getBestSideRating(player, 'defense'))
  const ovr = computePlayerOverall(player)
  const yearLabel = formatPlayerYear(player?.year)

  const statRow = useMemo(() => {
    const key = `${teamName}::${name}`
    return buildPlayerStatRows(saveState).find((r) => `${r.teamName}::${r.playerName}` === key) ?? null
  }, [saveState, teamName, name])

  return (
    <div className="player-profile">
      <div className="player-profile-top">
        <button type="button" className="player-profile-back" onClick={onClose}>
          ← Back
        </button>
        <div className="player-profile-identity">
          <TeamLogo apiBase={apiBase} teamName={teamName} logoVersion={logoVersion} headers={headers} size={56} />
          <div className="player-profile-title-block">
            <h1>{name}</h1>
            <p className="player-profile-meta">{teamName}</p>
            <p className="player-profile-meta">
              {posLine} · Year {yearLabel}
            </p>
            <p className="player-profile-meta player-profile-measure">{formatPlayerMeasureLine(player)}</p>
            <div className="player-profile-ratings">
              <span>Ovr {ovr}</span>
              <span>Off {offPos !== '—' ? `${offPos} ${offRtg}` : '—'}</span>
              <span>Def {defPos !== '—' ? `${defPos} ${defRtg}` : '—'}</span>
            </div>
          </div>
        </div>
      </div>

      <section className="player-profile-attrs" aria-label="Attributes">
        {PROFILE_ATTRIBUTE_GROUPS.map((g) => (
          <div key={g.title} className="player-profile-attr-col">
            <h2>{g.title}</h2>
            <dl className="player-profile-attr-grid">
              {g.keys.map((key) => (
                <Fragment key={key}>
                  <dt>{ATTR_LABELS[key] ?? key}</dt>
                  <dd>{formatPlayerAttributeCell(player, key)}</dd>
                </Fragment>
              ))}
            </dl>
          </div>
        ))}
      </section>

      <section className="player-profile-stats" aria-label="Season statistics">
        <h2>Season stats</h2>
        {!statRow || !statRowHasActivity(statRow) ? (
          <p className="player-profile-stats-empty">No stats logged yet for this player (games and scrimmages).</p>
        ) : (
          <div className="player-profile-stats-grid">
            <div className="player-profile-stat">
              <span className="player-profile-stat-label">Pass yards</span>
              <span className="player-profile-stat-val">{statRow.passYds}</span>
            </div>
            <div className="player-profile-stat">
              <span className="player-profile-stat-label">Pass TD</span>
              <span className="player-profile-stat-val">{statRow.passTd}</span>
            </div>
            <div className="player-profile-stat">
              <span className="player-profile-stat-label">Comp / Att</span>
              <span className="player-profile-stat-val">
                {statRow.comp} / {statRow.att}
              </span>
            </div>
            <div className="player-profile-stat">
              <span className="player-profile-stat-label">Cmp %</span>
              <span className="player-profile-stat-val">
                {statRow.att > 0 ? ((statRow.comp / statRow.att) * 100).toFixed(1) : '0.0'}%
              </span>
            </div>
            <div className="player-profile-stat">
              <span className="player-profile-stat-label">INT thrown</span>
              <span className="player-profile-stat-val">{statRow.intThrown}</span>
            </div>
            <div className="player-profile-stat">
              <span className="player-profile-stat-label">Rush yards</span>
              <span className="player-profile-stat-val">{statRow.rushYds}</span>
            </div>
            <div className="player-profile-stat">
              <span className="player-profile-stat-label">Rush TD</span>
              <span className="player-profile-stat-val">{statRow.rushTd}</span>
            </div>
            <div className="player-profile-stat">
              <span className="player-profile-stat-label">Receptions</span>
              <span className="player-profile-stat-val">{statRow.rec}</span>
            </div>
            <div className="player-profile-stat">
              <span className="player-profile-stat-label">Rec yards</span>
              <span className="player-profile-stat-val">{statRow.recYds}</span>
            </div>
            <div className="player-profile-stat">
              <span className="player-profile-stat-label">Rec TD</span>
              <span className="player-profile-stat-val">{statRow.recTd}</span>
            </div>
            <div className="player-profile-stat">
              <span className="player-profile-stat-label">Tackles</span>
              <span className="player-profile-stat-val">{statRow.tackles}</span>
            </div>
            <div className="player-profile-stat">
              <span className="player-profile-stat-label">Sacks</span>
              <span className="player-profile-stat-val">{statRow.sacks}</span>
            </div>
            <div className="player-profile-stat">
              <span className="player-profile-stat-label">TFL</span>
              <span className="player-profile-stat-val">{statRow.tfl}</span>
            </div>
            <div className="player-profile-stat">
              <span className="player-profile-stat-label">INT</span>
              <span className="player-profile-stat-val">{statRow.interceptions}</span>
            </div>
          </div>
        )}
      </section>
    </div>
  )
}
