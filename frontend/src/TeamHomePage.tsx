import { useEffect, useMemo, useRef, useState } from 'react'
import './TeamHomePage.css'
import './NewSaveFlow.css'
import type { CSSProperties } from 'react'
import { DEFENSIVE_PLAYBOOKS, OFFENSIVE_PLAYBOOKS } from './newSaveTypes'
import PlaybookGamePlanPage from './PlaybookGamePlanPage'
import DepthChartPage from './DepthChartPage'
import ScrimmagePanel from './ScrimmagePanel'
import GamePlayPage from './GamePlayPage'
import TeamLogo from './TeamLogo'
import TeamStadium from './TeamStadium'
import SettingsPage from './SettingsPage'
import { buildPlayerStatRows } from './playerSeasonStats'
import { CoachProfileName, CoachProfileProvider } from './CoachProfileContext'
import { PlayerProfileName, PlayerProfileProvider } from './PlayerProfileContext'
import CoachGameplanPage from './CoachGameplanPage'
import ScoutingReportPage, { SCOUTING_MENU_DEFENSE, SCOUTING_MENU_OFFENSE } from './ScoutingReportPage'
import {
  PLAYER_ATTRIBUTE_COLUMNS_SCROLL,
  formatPlayerAttributeCell,
  rosterDepthTableGridTemplateColumns,
} from './playerAttributes'
import NewsFeedPanel from './news/NewsFeedPanel'
import { NewsProvider, NewsStateSync } from './news/NewsContext'
import NewsTicker from './news/NewsTicker'
import {
  buildStateChampionshipYearsForTeam,
  buildFullTeamHistoryRows,
  buildTeamProgramTotalsFromLeagueHistory,
  downloadTeamSeasonRecap,
  findLocalSeasonRecap,
  hasRecapForArchivedSeason,
  mergeLiveAndSnapshotTeamHistory,
  mergeTeamHistoryRowLists,
  mergeInProgressTeamProgramTotals,
  type TeamProgramTotalsDisplay,
} from './coachHistory'
import {
  findSeasonEntryByCalendarYear,
  getHistoricalPlayoffsByClass,
  standingsListToRecord,
} from './leagueHistoryView'
import SeasonSummaryPanel from './SeasonSummaryPanel'
import CoachInboxPanel from './CoachInboxPanel'
import {
  buildPrestigeReportRows,
  formatTeamPoints,
  formatTeamPointsDelta,
  prestigeBandLabel,
} from './prestigeUtils'

/** Team menu value for the playoff bracket view (vs roster / depth / gameplans). */
const PLAYOFF_BRACKET_MENU = 'Playoff bracket'

/** Preseason hub: stage flow (playbook, depth, etc.). Other Team menu values show roster/stats/gameplans. */
const PRESEASON_TEAM_HUB = 'Preseason hub'
const OFFSEASON_TEAM_HUB = 'Offseason hub'
const COACH_INBOX_MENU = 'Coach Inbox'

function defaultTeamMenuForPhase(phase: string): string {
  if (phase === 'preseason') return PRESEASON_TEAM_HUB
  if (phase === 'offseason') return OFFSEASON_TEAM_HUB
  if (phase === 'playoffs') return PLAYOFF_BRACKET_MENU
  return 'Roster'
}

const COACH_DEV_SKILLS = [
  { key: 'playcalling', label: 'Playcalling' },
  { key: 'player_development', label: 'Player development' },
  { key: 'community_outreach', label: 'Community outreach' },
  { key: 'culture', label: 'Culture' },
  { key: 'recruiting', label: 'Recruiting' },
  { key: 'scheme_teach', label: 'Scheme teaching' },
] as const

const SPRING_OFFENSE_OPTIONS: { value: string; label: string }[] = [
  { value: 'run_blocking', label: 'Run Blocking' },
  { value: 'pass_protection', label: 'Pass Protection' },
  { value: 'receiving', label: 'Receiving' },
  { value: 'pass_game', label: 'Pass Game' },
  { value: 'run_game', label: 'Run Game' },
]

const SPRING_DEFENSE_OPTIONS: { value: string; label: string }[] = [
  { value: 'run_defense', label: 'Run Defense' },
  { value: 'pass_rush', label: 'Pass Rush' },
  { value: 'tackling', label: 'Tackling' },
  { value: 'pass_defense', label: 'Pass Defense' },
  { value: 'block_defeat', label: 'Block Defeat' },
]

const WINTER_TRAINING_CATEGORIES: { key: string; label: string; primary: string; secondary: string }[] = [
  { key: 'squat', label: 'Squat', primary: 'Strength', secondary: 'Acceleration' },
  { key: 'bench', label: 'Bench', primary: 'Strength', secondary: 'Injury Resistance' },
  { key: 'cleans', label: 'Cleans', primary: 'Speed', secondary: 'Agility' },
  { key: 'cod', label: 'COD', primary: 'Agility', secondary: 'Acceleration' },
  { key: 'speed', label: 'Speed', primary: 'Speed', secondary: 'Jumping' },
  { key: 'plyometrics', label: 'Plyometrics', primary: 'Jumping', secondary: 'Agility' },
  { key: 'football_iq', label: 'Football IQ', primary: 'Awareness', secondary: 'Coachability' },
]

function winterEfficiency(points: number): number {
  const p = Math.max(0, Math.min(100, Number(points) || 0))
  if (p <= 10) return 0.1
  if (p <= 20) return 0.4
  if (p <= 39) return 0.75
  if (p <= 60) return 1.0
  if (p <= 75) return 0.8
  if (p <= 90) return 0.5
  return 0.25
}

function winterEfficiencyColor(points: number): string {
  const eff = winterEfficiency(points)
  if (eff >= 0.95) return '#34d399'
  if (eff >= 0.7) return '#fbbf24'
  return '#f87171'
}

function defaultWinterAllocations(): Record<string, number> {
  return {
    squat: 15,
    bench: 15,
    cleans: 15,
    cod: 15,
    speed: 15,
    plyometrics: 15,
    football_iq: 10,
  }
}

function springLabel(value: string, side: 'offense' | 'defense'): string {
  const list = side === 'offense' ? SPRING_OFFENSE_OPTIONS : SPRING_DEFENSE_OPTIONS
  return list.find((o) => o.value === value)?.label ?? value
}

const COACH_DEV_THRESHOLDS: Record<number, number> = {
  1: 0,
  2: 20,
  3: 50,
  4: 90,
  5: 140,
  6: 200,
  7: 275,
  8: 350,
  9: 425,
  10: 500,
}

function emptyCoachDevAllocations(): Record<string, number> {
  return Object.fromEntries(COACH_DEV_SKILLS.map(({ key }) => [key, 0])) as Record<string, number>
}

function coachDevLevelFromCp(cp: number): number {
  let level = 1
  for (let i = 1; i <= 10; i++) {
    if (cp >= (COACH_DEV_THRESHOLDS[i] ?? 0)) level = i
  }
  return level
}

function coachDevNextThreshold(level: number): number | null {
  if (level >= 10) return null
  return COACH_DEV_THRESHOLDS[level + 1] ?? null
}

type Props = {
  apiBase: string
  headers: Record<string, string>
  saveId: string
  saveState: any
  onMainMenu: () => void
  onSimWeek: (opts?: {
    playbook?: { offensive_playbook: string; defensive_playbook: string }
    gamePlan?: { offensive: Record<string, { play_id: string; pct: number }[]>; defensive: Record<string, { play_id: string; pct: number }[]> }
    depthChart?: Record<string, string[]>
    positionChanges?: { player_name: string; position: string; secondary_position?: string | null }[]
    goals?: { win_goal: number; stage_goal: string }
    playoffsSim?: boolean
    seasonFinish?: boolean
    forcePreseasonAdvance?: boolean
    offseasonBody?: {
      winter_strength_pct?: number
      winter_training_allocations?: Record<string, number>
      winter_training_ack_results?: boolean
      spring_offense_focus?: string
      spring_defense_focus?: string
      spring_ball_ack_results?: boolean
      improve_facilities_grade?: number
      improve_culture_grade?: number
      improve_booster_support?: number
      improve_facilities_cumulative_pp?: number
      improve_culture_cumulative_pp?: number
      improve_boosters_cumulative_pp?: number
      coach_dev_allocations?: Record<string, number>
      carousel_job_applications?: string[]
      transfer_stage_1_ack_results?: boolean
      transfer_stage_2_ack_results?: boolean
    }
  }) => Promise<boolean>
  onSaveState?: (state: any) => void
  onError: (msg: string) => void
  backupReminderFrequency?: 'none' | '3_weeks' | '6_weeks' | 'stage'
  onBackupReminderFrequencyChange?: (value: 'none' | '3_weeks' | '6_weeks' | 'stage') => void
  onBackupNow?: () => void
  /** Local zip bundle: used for coach/history without API */
  leagueHistory?: any
  seasonRecaps?: Record<string, string>
  records?: unknown
  onMergeLocalSimulationResult?: (data: {
    state?: unknown
    league_history?: unknown
    records?: unknown
    season_recaps?: Record<string, string>
  }) => void
  /** API saves: reload league_history.json when opening Team History. */
  onRefreshDynasty?: () => void | Promise<void>
}

type TeamHomePageBodyProps = Props & {
  logoVersion: number
  setLogoVersion: (n: number) => void
  stadiumVersion: number
  setStadiumVersion: (n: number) => void
}

const OFFENSE_POSITIONS = ['QB', 'RB', 'WR', 'OL', 'TE'] as const
const DEFENSE_POSITIONS = ['DE', 'DT', 'LB', 'CB', 'S'] as const
const SPECIALIST_POSITIONS = ['K', 'P'] as const
const ALL_PRESEASON_POSITIONS = [...OFFENSE_POSITIONS, ...DEFENSE_POSITIONS, ...SPECIALIST_POSITIONS] as const

function safeStr(v: any) {
  if (v == null) return ''
  return String(v)
}

/** Class year label for transfer portal tables (roster year 1–3). */
function formatTransferPortalClassYear(year: unknown): string {
  const y = Number(year)
  if (y === 1) return 'Fr.'
  if (y === 2) return 'So.'
  if (y === 3) return 'Jr.'
  if (Number.isFinite(y) && y > 0) return `Yr ${y}`
  return '—'
}

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

function findTeam(state: any, teamName: string) {
  return (state?.teams ?? []).find((t: any) => t?.name === teamName) ?? null
}

/** Matches backend `league_service._improvement_pp_delta` (offseason school Improvements). Negative = spend PP. */
function clampImprovementLevel(raw: number, fallback: number): number {
  const x = Number(raw)
  const base = Number.isFinite(x) ? x : fallback
  return Math.max(1, Math.min(10, Math.floor(base)))
}

const UPGRADE_COST_BY_LEVEL: Record<number, number> = {
  1: 100,
  2: 300,
  3: 500,
  4: 800,
  5: 1200,
  6: 1500,
  7: 1900,
  8: 2400,
  9: 3000,
}

const PILLAR_CUMULATIVE_PP_MAX = (() => {
  let s = 0
  for (let k = 1; k <= 9; k += 1) s += UPGRADE_COST_BY_LEVEL[k] ?? 3000
  return s
})()

/** Step for pillar +/- controls and range slider (less sensitive than 1 PP per tick). */
const PILLAR_SLIDER_STEP = 5

function pillarCumulativePpValue(level: number, progressPts: number): number {
  const L = clampImprovementLevel(level, 5)
  const pts = Math.max(0, Math.min(3500, Math.floor(Number(progressPts) || 0)))
  let total = 0
  for (let k = 1; k < L; k += 1) total += UPGRADE_COST_BY_LEVEL[k] ?? 3000
  if (L < 10) {
    const cap = UPGRADE_COST_BY_LEVEL[L] ?? 3000
    total += Math.min(pts, cap)
  }
  return total
}

function pillarStateFromCumulativePpValue(target: number): { level: number; progressPts: number } {
  let v = Math.max(0, Math.min(PILLAR_CUMULATIVE_PP_MAX, Math.floor(Number(target) || 0)))
  let L = 1
  while (L < 10) {
    const need = UPGRADE_COST_BY_LEVEL[L] ?? 3000
    if (v < need) return { level: L, progressPts: v }
    v -= need
    L += 1
  }
  return { level: 10, progressPts: 0 }
}

function formatPillarMeter(cumulativePp: number): string {
  const { level, progressPts } = pillarStateFromCumulativePpValue(cumulativePp)
  if (level >= 10) return 'Level 10 (max)'
  const need = UPGRADE_COST_BY_LEVEL[level] ?? 3000
  return `Level ${level} · ${progressPts} / ${need} PP toward level ${level + 1}`
}
function formatProgramPpDelta(n: number): string {
  const v = Number(n)
  if (!Number.isFinite(v)) return '—'
  if (v > 0) return `+${Math.round(v)}`
  if (v < 0) return String(Math.round(v))
  return '0'
}

function displayOffseasonStageLabel(stage: string): string {
  if (stage === 'Improvements') return 'Program development'
  return stage
}

type TopBarStandingRow = { name: string; wins: number; points_for: number; points_against: number }

function _topBarStandingsSort(a: TopBarStandingRow, b: TopBarStandingRow): number {
  if (b.wins !== a.wins) return b.wins - a.wins
  if (b.points_for !== a.points_for) return b.points_for - a.points_for
  return a.points_against - b.points_against
}

/**
 * Outside regular season / playoffs the live ``standings`` are reset to 0-0 for
 * the new year. Fall back to the persisted last-completed-season snapshot so the
 * UI shows last season's record (with a "(last season)" suffix) instead of 0-0
 * until the new year actually plays a game.
 *
 * Always prefer the snapshot during preseason / offseason when one is available —
 * regular-season W-L can't accrue in those phases, so any non-zero standings is
 * leftover data from a prior run and would be misleading to display.
 */
function _liveOrLastCompletedStandingsRow(state: any, teamName: string) {
  const live = state?.standings?.[teamName]
  const liveWins = Number(live?.wins ?? 0)
  const liveLosses = Number(live?.losses ?? 0)
  const phase = String(state?.season_phase ?? '').toLowerCase()
  const inLivePhase = phase === 'regular' || phase === 'playoffs'
  const snap = state?.last_completed_standings?.[teamName]
  const haveSnapshot = snap != null && typeof snap === 'object'
  if (!inLivePhase && haveSnapshot) {
    const yr = Number(state?.last_completed_year)
    return {
      wins: Number(snap.wins ?? 0),
      losses: Number(snap.losses ?? 0),
      pointsFor: Number(snap.points_for ?? 0),
      pointsAgainst: Number(snap.points_against ?? 0),
      isSnapshot: true,
      snapshotYear: Number.isFinite(yr) ? yr : null,
    }
  }
  return {
    wins: liveWins,
    losses: liveLosses,
    pointsFor: Number(live?.points_for ?? 0),
    pointsAgainst: Number(live?.points_against ?? 0),
    isSnapshot: false,
    snapshotYear: null as number | null,
  }
}

function buildRecordAndRankForTeam(state: any, teamName: string) {
  const standings = state?.standings ?? {}
  const ranked = _liveOrLastCompletedStandingsRow(state, teamName)
  const { wins, losses, pointsFor, pointsAgainst, isSnapshot, snapshotYear } = ranked
  const baseRecord = teamName ? `${wins}-${losses}` : '—'
  const record =
    teamName && isSnapshot
      ? snapshotYear != null
        ? `${baseRecord} (${snapshotYear} season)`
        : `${baseRecord} (last season)`
      : baseRecord

  const clsMap = teamClassificationMap(state)
  const classification = teamName ? (clsMap.get(teamName) ?? '—') : '—'

  // Ranking source: live standings during regular/playoffs, snapshot otherwise — matches the
  // record displayed above. Empty snapshot falls back to live (which will be all-zero, ranking arbitrary).
  const rankingSource =
    isSnapshot && state?.last_completed_standings && typeof state.last_completed_standings === 'object'
      ? state.last_completed_standings
      : standings
  const rows: TopBarStandingRow[] = Object.keys(rankingSource).map((name) => {
    const s = rankingSource[name] ?? {}
    return {
      name,
      wins: Number(s?.wins ?? 0),
      points_for: Number(s?.points_for ?? 0),
      points_against: Number(s?.points_against ?? 0),
    }
  })

  const sortedAll = [...rows].sort(_topBarStandingsSort)
  const rankIndex = sortedAll.findIndex((x) => x.name === teamName)
  const rank = teamName && rankIndex >= 0 ? rankIndex + 1 : null

  const classPeers = rows.filter((r) => (clsMap.get(r.name) ?? '—') === classification)
  const sortedClass = [...classPeers].sort(_topBarStandingsSort)
  const classRankIndex = sortedClass.findIndex((x) => x.name === teamName)
  const classRank = teamName && classRankIndex >= 0 ? classRankIndex + 1 : null

  return { record, rank, classRank, classification, wins, losses, pointsFor, pointsAgainst }
}

function buildRecordAndRank(state: any) {
  return buildRecordAndRankForTeam(state, state?.user_team ?? '')
}

function formatStage(phase: string) {
  if (phase === 'regular') return 'Regular Season'
  if (phase === 'playoffs') return 'Playoffs'
  if (phase === 'season_summary') return 'Season summary'
  if (phase === 'offseason') return 'OffSeason'
  if (!phase) return '—'
  return safeStr(phase)
}

/** Align UI phase with save: preseason if stage index is still within preseason_stages (handles missing/wrong season_phase). */
function derivePhaseFromSave(saveState: any): string {
  if (!saveState) return 'regular'
  const raw = String(saveState.season_phase ?? '').toLowerCase()
  // Must run before the "preseason finished → regular" shortcut, or playoffs/offseason are never shown.
  if (raw === 'playoffs' || raw === 'season_summary' || raw === 'offseason' || raw === 'done') return raw
  const stages = saveState.preseason_stages
  const idx = Number(saveState.preseason_stage_index ?? 0)
  // Past last preseason stage on file → show regular season (even if season_phase was not saved as regular yet).
  if (Array.isArray(stages) && stages.length > 0 && idx >= stages.length) return 'regular'
  if (raw === 'preseason') return 'preseason'
  if (Array.isArray(stages) && stages.length > 0 && idx < stages.length) return 'preseason'
  return 'regular'
}

/** Must match backend `OFFSEASON_UI_STAGES` in `league_service.py`. */
const CANONICAL_OFFSEASON_STAGES = [
  'Graduation',
  'Coach development',
  'Winter 1',
  'Winter 2',
  'Spring Ball',
  'Transfers I',
  'Transfers II',
  'Transfers III',
  '7 on 7',
  'Training Results',
  'Freshman Class',
  'Improvements',
  'Coaching carousel I',
  'Coaching carousel II',
  'Coaching carousel III',
  'Coaching carousel IV',
  'Schedule Release',
] as const

/** Map save/API typos or alternate labels to canonical `OFFSEASON_UI_STAGES` names. */
function normalizeOffseasonStageName(raw: unknown): string {
  const s = typeof raw === 'string' ? raw.trim() : ''
  if (!s) return ''
  const canon = CANONICAL_OFFSEASON_STAGES as readonly string[]
  if ((canon as readonly string[]).includes(s)) return s
  const lower = s
    .toLowerCase()
    .replace(/[\u2019\u2018]/g, "'")
    .replace(/\s+/g, ' ')
  const compact = lower.replace(/[^a-z0-9]/g, '')
  if (compact === 'coachdevelopment' || compact === 'coachingdevelopment') return 'Coach development'
  const aliases: Record<string, string> = {
    'coaching carousel i': 'Coaching carousel I',
    'coaching carousel ii': 'Coaching carousel II',
    'coaching carousel iii': 'Coaching carousel III',
    'coaching carousel iv': 'Coaching carousel IV',
    'coaching carousel 1': 'Coaching carousel I',
    'coaching carousel 2': 'Coaching carousel II',
    'coaching carousel 3': 'Coaching carousel III',
    'coaching carousel 4': 'Coaching carousel IV',
    transfers: 'Transfers I',
    transfer: 'Transfers I',
    'transfer stage 1': 'Transfers I',
    'transfer stage 2': 'Transfers II',
    'transfer stage 3': 'Transfers III',
    'transfer review': 'Transfers III',
  }
  if (aliases[lower]) return aliases[lower]
  for (const c of canon) {
    if (c.toLowerCase().replace(/[\u2019\u2018]/g, "'") === lower) return c
  }
  return s
}

/**
 * Old saves may have a shorter/different `offseason_stages` array after we add stages.
 * Map by stage name so the UI matches the server and highlights the correct panel.
 */
function resolveOffseasonStagesFromSave(saveState: any): {
  stages: string[]
  stageIndex: number
  currentStage: string
} {
  const canonical = [...CANONICAL_OFFSEASON_STAGES]
  const saved = saveState?.offseason_stages
  const rawIdx = Number(saveState?.offseason_stage_index ?? 0)

  if (!Array.isArray(saved) || saved.length === 0) {
    const idx = Math.max(0, Math.min(rawIdx, canonical.length - 1))
    return { stages: canonical, stageIndex: idx, currentStage: canonical[idx] ?? '' }
  }

  const arraysMatch =
    saved.length === canonical.length && saved.every((s: string, i: number) => s === canonical[i])
  if (arraysMatch) {
    const idx = Math.max(0, Math.min(rawIdx, canonical.length - 1))
    return { stages: canonical, stageIndex: idx, currentStage: canonical[idx] ?? '' }
  }

  const safeOldIdx = Math.max(0, Math.min(rawIdx, saved.length - 1))
  const nameAtIdx = normalizeOffseasonStageName(saved[safeOldIdx])
  if (typeof saved[safeOldIdx] === 'string' && (canonical as readonly string[]).includes(nameAtIdx)) {
    const newIdx = (canonical as string[]).indexOf(nameAtIdx)
    return { stages: canonical, stageIndex: newIdx, currentStage: nameAtIdx }
  }

  const idx = Math.max(0, Math.min(rawIdx, canonical.length - 1))
  return { stages: canonical, stageIndex: idx, currentStage: canonical[idx] ?? '' }
}

function getGameOpponent(weekGames: any[], userTeam: string) {
  for (const g of weekGames ?? []) {
    if (g?.home === userTeam) return g?.away
    if (g?.away === userTeam) return g?.home
  }
  return null
}

function getLastOpponentAndScore(state: any) {
  const userTeam = state?.user_team ?? ''
  const currentWeek = Number(state?.current_week ?? 1)
  const prevIdx = currentWeek - 2
  const weeks = state?.weeks ?? []
  const results = state?.week_results ?? []

  if (prevIdx < 0 || prevIdx >= weeks.length) return null
  const wk = weeks[prevIdx] ?? []
  const wkRes = results[prevIdx] ?? []

  for (let gi = 0; gi < wk.length; gi++) {
    const game = wk[gi]
    if (!game) continue
    const involves = game.home === userTeam || game.away === userTeam
    if (!involves) continue

    const r = wkRes[gi] ?? {}
    if (!r?.played) return null
    const homeScore = Number(r?.home_score ?? 0)
    const awayScore = Number(r?.away_score ?? 0)
    const ot = Boolean(r?.ot)

    const opponent = game.home === userTeam ? game.away : game.home
    const userHome = game.home === userTeam
    const userScore = userHome ? homeScore : awayScore
    const oppScore = userHome ? awayScore : homeScore
    const outcome = userScore >= oppScore ? 'W' : 'L'
    return { opponent, userScore, oppScore, outcome, ot }
  }
  return null
}

function getNextOpponent(state: any) {
  const userTeam = state?.user_team ?? ''
  const currentWeek = Number(state?.current_week ?? 1)
  const phase = derivePhaseFromSave(state)
  const weeks = state?.weeks ?? []

  if (phase !== 'regular') return 'Offseason'
  const idx = currentWeek - 1
  if (idx < 0 || idx >= weeks.length) return 'Offseason'
  const opponent = getGameOpponent(weeks[idx] ?? [], userTeam)
  return opponent ? String(opponent) : '—'
}

function buildScheduleRows(state: any) {
  const userTeam = state?.user_team ?? ''
  const weeks = state?.weeks ?? []
  const results = state?.week_results ?? []
  const regionMap = teamRegionMap(state)
  const clsMap = teamClassificationMap(state)

  const rows: Array<{
    week: number
    opponent: string
    played: boolean
    scoreLine: string
    isRegionGame: boolean
  }> = []

  for (let wi = 0; wi < weeks.length; wi++) {
    const weekGames = weeks[wi] ?? []
    const weekRes = results[wi] ?? []

    for (let gi = 0; gi < weekGames.length; gi++) {
      const g = weekGames[gi]
      if (!g) continue
      const involves = g.home === userTeam || g.away === userTeam
      if (!involves) continue

      const opponent = g.home === userTeam ? g.away : g.home
      const r = weekRes[gi] ?? {}
      const played = Boolean(r?.played)
      let scoreLine = 'Scheduled'
      if (played) {
        const homeScore = Number(r?.home_score ?? 0)
        const awayScore = Number(r?.away_score ?? 0)
        const ot = Boolean(r?.ot)
        const userHome = g.home === userTeam
        const userScore = userHome ? homeScore : awayScore
        const oppScore = userHome ? awayScore : homeScore
        const outcome = userScore >= oppScore ? 'W' : 'L'
        scoreLine = `${outcome}${ot ? ' (OT)' : ''} ${userScore}-${oppScore}`
      }

      rows.push({
        week: wi + 1,
        opponent: String(opponent),
        played,
        scoreLine,
        isRegionGame: isRegionGame(String(g.home), String(g.away), regionMap, clsMap),
      })
    }
  }

  // If multiple games in a week (shouldn't happen often in your format), keep the earliest.
  const byWeek = new Map<number, (typeof rows)[number]>()
  for (const r of rows) {
    if (!byWeek.has(r.week)) byWeek.set(r.week, r)
  }

  return Array.from(byWeek.entries())
    .sort((a: [number, any], b: [number, any]) => a[0] - b[0])
    .map(([, v]) => v)
}

type StateWeekGameRow = {
  home: string
  away: string
  played: boolean
  homeScore: number
  awayScore: number
  ot: boolean
  recap: string
  gameIndex: number
}

function buildStateWeekGames(state: any, week1Based: number): StateWeekGameRow[] {
  const weeks = state?.weeks ?? []
  const results = state?.week_results ?? []
  const wi = week1Based - 1
  if (wi < 0 || wi >= weeks.length) return []
  const weekGames = weeks[wi] ?? []
  const weekRes = results[wi] ?? []
  return weekGames.map((g: any, gi: number) => {
    const r = weekRes[gi] ?? {}
    return {
      home: String(g?.home ?? '—'),
      away: String(g?.away ?? '—'),
      played: Boolean(r?.played),
      homeScore: Number(r?.home_score ?? 0),
      awayScore: Number(r?.away_score ?? 0),
      ot: Boolean(r?.ot),
      recap: typeof r?.recap === 'string' ? r.recap : '',
      gameIndex: gi,
    }
  })
}

type TeamScheduleRow = {
  week: number
  gameIndex: number
  home: string
  away: string
  opponent: string
  userHome: boolean
  played: boolean
  homeScore: number
  awayScore: number
  ot: boolean
  /** Win / loss / tie for this team when the game was played */
  result: 'W' | 'L' | 'T' | null
  /** True for in-region matchups (same classification + same non-empty region). */
  isRegionGame: boolean
}

/** One row per game for `teamName` in the regular-season schedule. */
function buildTeamScheduleRows(state: any, teamName: string): TeamScheduleRow[] {
  if (!teamName) return []
  const weeks = state?.weeks ?? []
  const results = state?.week_results ?? []
  const regionMap = teamRegionMap(state)
  const clsMap = teamClassificationMap(state)
  const rows: TeamScheduleRow[] = []
  for (let wi = 0; wi < weeks.length; wi++) {
    const weekGames = weeks[wi] ?? []
    const weekRes = results[wi] ?? []
    for (let gi = 0; gi < weekGames.length; gi++) {
      const g = weekGames[gi]
      if (!g) continue
      if (g.home !== teamName && g.away !== teamName) continue
      const r = weekRes[gi] ?? {}
      const userHome = g.home === teamName
      const opponent = userHome ? g.away : g.home
      const played = Boolean(r?.played)
      const homeScore = Number(r?.home_score ?? 0)
      const awayScore = Number(r?.away_score ?? 0)
      let result: 'W' | 'L' | 'T' | null = null
      if (played) {
        const my = userHome ? homeScore : awayScore
        const opp = userHome ? awayScore : homeScore
        if (my > opp) result = 'W'
        else if (my < opp) result = 'L'
        else result = 'T'
      }
      rows.push({
        week: wi + 1,
        gameIndex: gi,
        home: String(g.home ?? '—'),
        away: String(g.away ?? '—'),
        opponent: String(opponent ?? '—'),
        userHome,
        played,
        homeScore,
        awayScore,
        ot: Boolean(r?.ot),
        result,
        isRegionGame: isRegionGame(String(g.home ?? ''), String(g.away ?? ''), regionMap, clsMap),
      })
    }
  }
  return rows
}

function teamClassificationMap(state: any): Map<string, string> {
  const m = new Map<string, string>()
  for (const t of state?.teams ?? []) {
    const name = String(t?.name ?? '').trim()
    if (!name) continue
    const c =
      t?.classification != null && String(t.classification).trim() !== ''
        ? String(t.classification).trim()
        : '—'
    m.set(name, c)
  }
  return m
}

/** Region (e.g. "North", "South", "Region I") for each team in the save. */
function teamRegionMap(state: any): Map<string, string> {
  const m = new Map<string, string>()
  for (const t of state?.teams ?? []) {
    const name = String(t?.name ?? '').trim()
    if (!name) continue
    const r =
      t?.region != null && String(t.region).trim() !== ''
        ? String(t.region).trim()
        : ''
    m.set(name, r)
  }
  return m
}

/**
 * True if `home` and `away` are in the same scheduling pod
 * (same classification AND same non-empty region) — i.e. an in-region game
 * that counts toward the regional title race. Cross-region matchups
 * (the "out-of-region" weeks of the schedule) return false.
 */
function isRegionGame(
  home: string,
  away: string,
  regionMap: Map<string, string>,
  classificationMap: Map<string, string>,
): boolean {
  const hr = regionMap.get(home) ?? ''
  const ar = regionMap.get(away) ?? ''
  if (!hr || !ar) return false
  if (hr !== ar) return false
  const hc = classificationMap.get(home) ?? ''
  const ac = classificationMap.get(away) ?? ''
  if (!hc || !ac || hc === '—' || ac === '—') return false
  return hc === ac
}

function uniqueClassifications(state: any): string[] {
  const s = new Set<string>()
  for (const t of state?.teams ?? []) {
    const c =
      t?.classification != null && String(t.classification).trim() !== ''
        ? String(t.classification).trim()
        : '—'
    s.add(c)
  }
  return [...s].sort((a, b) => a.localeCompare(b))
}

function buildStandingsRows(state: any, classFilter: string | 'all' = 'all') {
  const clsMap = teamClassificationMap(state)
  const standings = state?.standings ?? {}
  let teamNames = Object.keys(standings)
  if (classFilter !== 'all') {
    teamNames = teamNames.filter((n) => (clsMap.get(n) ?? '—') === classFilter)
  }
  const currentWeek = Number(state?.current_week ?? 1)
  const gamesPlayedFallback = Math.max(0, currentWeek - 1)

  const rows = teamNames.map((teamName) => {
    const s = standings[teamName] ?? {}
    const wins = Number(s?.wins ?? 0)
    const losses = Number(s?.losses ?? 0)
    const pointsFor = Number(s?.points_for ?? 0)
    const pointsAgainst = Number(s?.points_against ?? 0)
    const games = Math.max(1, wins + losses || gamesPlayedFallback || 1)
    const diff = pointsFor - pointsAgainst
    const ppg = pointsFor / games
    const ppgd = diff / games
    return {
      teamName,
      wins,
      losses,
      pointsFor,
      pointsAgainst,
      diff,
      ppg,
      ppgd,
    }
  })

  rows.sort((a, b) => {
    if (b.wins !== a.wins) return b.wins - a.wins
    if (b.diff !== a.diff) return b.diff - a.diff
    return b.pointsFor - a.pointsFor
  })

  return rows.map((r, idx) => ({ rank: idx + 1, ...r }))
}

function buildRankingsRows(state: any, classFilter: string | 'all' = 'all') {
  const standingsRows = buildStandingsRows(state, classFilter)
  return standingsRows
    .map((r) => {
      // Simple composite ranking score for now:
      // wins + point differential + ppg all contribute.
      const score = r.wins * 100 + r.diff * 2 + r.ppg * 3
      return { ...r, score }
    })
    .sort((a, b) => b.score - a.score)
    .map((r, idx) => ({ ...r, rank: idx + 1 }))
}

function buildStatsRows(state: any, classFilter: string | 'all' = 'all') {
  const standingsRows = buildStandingsRows(state, classFilter)
  return standingsRows
    .map((r) => ({
      teamName: r.teamName,
      games: Math.max(1, r.wins + r.losses),
      ppg: r.ppg,
      ppgd: r.ppgd,
      pointsFor: r.pointsFor,
      pointsAgainst: r.pointsAgainst,
      diff: r.diff,
    }))
    .sort((a, b) => b.ppg - a.ppg)
}

type TeamStatRow = {
  teamName: string
  games: number
  pointsFor: number
  pointsAgainst: number
  ppg: number
  ppgAllowed: number
  totalYards: number
  rushYards: number
  passYards: number
  ypg: number
  rypg: number
  pypg: number
  explosives: number
  turnovers: number
}

function buildTeamStatRows(state: any, classFilter: string | 'all' = 'all'): TeamStatRow[] {
  const clsMap = teamClassificationMap(state)
  const teams = (state?.teams ?? [])
    .map((t: any) => String(t?.name ?? ''))
    .filter(Boolean)
    .filter((name: string) => {
      if (classFilter === 'all') return true
      return (clsMap.get(name) ?? '—') === classFilter
    })
  const standings = state?.standings ?? {}
  const weeks = state?.weeks ?? []
  const results = state?.week_results ?? []
  const acc: Record<string, { games: number; totalYards: number; rushYards: number; passYards: number; explosives: number; turnovers: number }> = {}

  for (const teamName of teams) {
    acc[teamName] = { games: 0, totalYards: 0, rushYards: 0, passYards: 0, explosives: 0, turnovers: 0 }
  }

  for (let wi = 0; wi < weeks.length; wi++) {
    const wk = weeks[wi] ?? []
    const wkRes = results[wi] ?? []
    for (let gi = 0; gi < wk.length; gi++) {
      const g = wk[gi] ?? {}
      const r = wkRes[gi] ?? {}
      if (!r?.played) continue
      const home = String(g?.home ?? '')
      const away = String(g?.away ?? '')
      const ts = r?.team_stats ?? {}

      const addTeam = (name: string) => {
        if (!name) return
        if (!acc[name]) acc[name] = { games: 0, totalYards: 0, rushYards: 0, passYards: 0, explosives: 0, turnovers: 0 }
        const t = ts?.[name] ?? {}
        acc[name].games += 1
        acc[name].totalYards += Number(t?.total_yards ?? (Number(t?.rush_yards ?? 0) + Number(t?.pass_yards ?? 0)))
        acc[name].rushYards += Number(t?.rush_yards ?? 0)
        acc[name].passYards += Number(t?.pass_yards ?? 0)
        acc[name].explosives += Number(t?.explosives ?? (Number(t?.explosive_run ?? 0) + Number(t?.explosive_pass ?? 0)))
        acc[name].turnovers += Number(t?.turnovers ?? 0)
      }

      addTeam(home)
      addTeam(away)
    }
  }

  return Object.keys(acc).map((teamName) => {
    const s = standings?.[teamName] ?? {}
    const pointsFor = Number(s?.points_for ?? 0)
    const pointsAgainst = Number(s?.points_against ?? 0)
    const gamesByRecord = Number(s?.wins ?? 0) + Number(s?.losses ?? 0)
    const games = Math.max(1, acc[teamName].games || gamesByRecord || 1)
    const ppg = pointsFor / games
    const ppgAllowed = pointsAgainst / games
    const ypg = acc[teamName].totalYards / games
    const rypg = acc[teamName].rushYards / games
    const pypg = acc[teamName].passYards / games
    return {
      teamName,
      games,
      pointsFor,
      pointsAgainst,
      ppg,
      ppgAllowed,
      totalYards: acc[teamName].totalYards,
      rushYards: acc[teamName].rushYards,
      passYards: acc[teamName].passYards,
      ypg,
      rypg,
      pypg,
      explosives: acc[teamName].explosives,
      turnovers: acc[teamName].turnovers,
    }
  })
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

type TopLeaguePlayerRow = {
  rank: number
  name: string
  gradeLabel: string
  position: string
  overall: number
  school: string
}

/** All rostered players statewide, ranked by composite overall (see `computePlayerOverall`). */
function buildTopLeaguePlayerRows(state: any, limit = 250): TopLeaguePlayerRow[] {
  const teams = state?.teams ?? []
  const pooled: Omit<TopLeaguePlayerRow, 'rank'>[] = []
  for (const t of teams) {
    const school = String(t?.name ?? '').trim()
    const roster = t?.roster
    if (!school || !Array.isArray(roster)) continue
    for (const p of roster) {
      if (!p || typeof p !== 'object') continue
      const name = String((p as any)?.name ?? '').trim()
      if (!name) continue
      pooled.push({
        name,
        gradeLabel: formatPlayerYear((p as any)?.year),
        position: String((p as any)?.position ?? '—').trim() || '—',
        overall: computePlayerOverall(p),
        school,
      })
    }
  }
  pooled.sort(
    (a, b) =>
      b.overall - a.overall ||
      String(a.name).localeCompare(String(b.name)) ||
      String(a.school).localeCompare(String(b.school)),
  )
  return pooled.slice(0, limit).map((r, i) => ({ ...r, rank: i + 1 }))
}

/** High school year 9 (or legacy 1) = freshman — matches engine `development_system.FRESHMAN_YEAR`. */
function isFreshmanYear(year: unknown): boolean {
  const n = Number(year)
  if (Number.isNaN(n)) return false
  return n === 9 || n === 1
}

type OffseasonTrainingRow = {
  name: string
  position?: string
  before: number
  after: number
  delta: number
}

const POSITION_SORT_ORDER = ['QB', 'RB', 'WR', 'TE', 'OL', 'DE', 'DT', 'LB', 'CB', 'S', 'K', 'P']

function positionRankForSort(pos: string | undefined): number {
  const p = String(pos ?? '')
  const i = POSITION_SORT_ORDER.indexOf(p)
  return i >= 0 ? i : 40
}

type OffseasonTrainingSortMode = 'position' | 'delta' | 'name' | 'after'

function sortOffseasonTrainingRows(
  rows: OffseasonTrainingRow[],
  sort: OffseasonTrainingSortMode,
): OffseasonTrainingRow[] {
  const out = [...rows]
  if (sort === 'position') {
    out.sort(
      (a, b) =>
        positionRankForSort(a.position) - positionRankForSort(b.position) ||
        String(a.name).localeCompare(String(b.name)),
    )
  } else if (sort === 'delta') {
    out.sort(
      (a, b) =>
        Math.abs(b.delta) - Math.abs(a.delta) || String(a.name).localeCompare(String(b.name)),
    )
  } else if (sort === 'after') {
    out.sort((a, b) => b.after - a.after || String(a.name).localeCompare(String(b.name)))
  } else {
    out.sort((a, b) => String(a.name).localeCompare(String(b.name)))
  }
  return out
}

type FreshmanSortMode = 'position' | 'overall' | 'name'

function sortFreshmanRosterPlayers(players: any[], sort: FreshmanSortMode): any[] {
  const out = [...players]
  if (sort === 'position') {
    out.sort(
      (a, b) =>
        positionRankForSort(a?.position) - positionRankForSort(b?.position) ||
        String(a?.name ?? '').localeCompare(String(b?.name ?? '')),
    )
  } else if (sort === 'overall') {
    out.sort((a, b) => computePlayerOverall(b) - computePlayerOverall(a))
  } else {
    out.sort((a, b) => String(a?.name ?? '').localeCompare(String(b?.name ?? '')))
  }
  return out
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

function buildRosterPlayersSorted(state: any): any[] {
  const userTeam = state?.user_team ?? ''
  const team = findTeam(state, userTeam)
  const roster = team?.roster ?? []
  return [...roster].sort((a: any, b: any) => {
    const diff = computePlayerOverall(b) - computePlayerOverall(a)
    if (diff !== 0) return diff
    return String(a?.name ?? '').localeCompare(String(b?.name ?? ''))
  })
}

function classificationOfUserTeam(state: any): string {
  const u = state?.user_team
  const t = findTeam(state, u)
  const c = t?.classification
  return c != null && String(c).trim() !== '' ? String(c).trim() : '—'
}

/** User's bracket (for status line, next opponent, coach game) — not the class dropdown view. */
function userPlayoffInner(state: any): {
  seeds?: Array<{ seed: number; team: string }>
  bracket_results?: any[]
  completed?: boolean
  champion?: string | null
} | null {
  const p = state?.playoffs
  if (!p) return null
  const bc = normalizePlayoffsByClass(state)
  if (bc && Object.keys(bc).length) {
    const uc = p.user_class || classificationOfUserTeam(state)
    const rk = uc ? resolveBracketClassKey(bc, uc) : null
    if (rk && bc[rk]) return bc[rk]
    if (uc && bc[uc]) return bc[uc]
    const k = Object.keys(bc).sort((a, b) => a.localeCompare(b))[0]
    return k ? bc[k] : null
  }
  return null
}

function anyPlayoffGamesStarted(state: any): boolean {
  const p = state?.playoffs
  if (!p) return false
  const bc = normalizePlayoffsByClass(state)
  if (bc && typeof bc === 'object') {
    return Object.values(bc).some(
      (sub: any) => Array.isArray(sub?.bracket_results) && sub.bracket_results.length > 0,
    )
  }
  return (p.bracket_results?.length ?? 0) > 0
}

/** Match dropdown / team labels to `playoffs.by_class` keys (exact, then case-insensitive). */
function resolveBracketClassKey(bc: Record<string, any> | undefined | null, preferred: string | null | undefined): string | null {
  if (!bc || typeof bc !== 'object') return null
  const keys = Object.keys(bc)
  if (!keys.length) return null
  const w = String(preferred ?? '').trim()
  if (!w) return null
  if (Object.prototype.hasOwnProperty.call(bc, w)) return w
  const lower = w.toLowerCase()
  const found = keys.find((k) => k.toLowerCase() === lower)
  return found ?? null
}

/**
 * Single source for playoff brackets: real `playoffs.by_class`, or legacy top-level seeds/results
 * wrapped under the user’s classification key. Without this, the UI always showed legacy seeds and
 * ignored the class dropdown.
 */
function normalizePlayoffsByClass(state: any): Record<string, any> | null {
  const p = state?.playoffs
  if (!p || typeof p !== 'object') return null
  const raw = p.by_class
  if (raw && typeof raw === 'object' && Object.keys(raw).length > 0) {
    return raw as Record<string, any>
  }
  if (p.seeds != null || p.bracket_results != null) {
    const uc = String(p.user_class || classificationOfUserTeam(state) || 'UNK').trim() || 'UNK'
    return {
      [uc]: {
        num_teams: p.num_teams,
        seeds: p.seeds,
        bracket_results: p.bracket_results,
        completed: p.completed,
        champion: p.champion,
        runner_up: p.runner_up,
      },
    }
  }
  return null
}

function findQfGame(qf: any[], pair: { home: string; away: string }) {
  return qf.find(
    (g: any) =>
      (g?.home === pair.home && g?.away === pair.away) ||
      (g?.home === pair.away && g?.away === pair.home),
  )
}

function qfWinnerByIndex(qf: any[], qfPairs: { home: string; away: string }[], i: number): string | null {
  const p = qfPairs[i]
  if (!p) return null
  const g = findQfGame(qf, p)
  const w = g?.winner
  return w != null && String(w).trim() !== '' ? String(w) : null
}

/** Semifinal rows: real results plus projected matchups (QF winners → SF pairings) before the round is simmed. */
function buildPlayoffSfRows(qf: any[], sf: any[], qfPairs: { home: string; away: string }[]) {
  const w = (i: number) => qfWinnerByIndex(qf, qfPairs, i)
  const projRow = (which: 1 | 2) => {
    if (which === 1) {
      const home = w(0) ?? 'TBD'
      const away = w(3) ?? 'TBD'
      return { home, away, home_score: null, away_score: null, projected: true }
    }
    const home = w(1) ?? 'TBD'
    const away = w(2) ?? 'TBD'
    return { home, away, home_score: null, away_score: null, projected: true }
  }
  const matchesSf1 = (g: any) => {
    const a = w(0),
      b = w(3)
    if (!a || !b) return false
    return (g.home === a && g.away === b) || (g.home === b && g.away === a)
  }
  const matchesSf2 = (g: any) => {
    const a = w(1),
      b = w(2)
    if (!a || !b) return false
    return (g.home === a && g.away === b) || (g.home === b && g.away === a)
  }

  if (sf.length >= 2) {
    return sf.map((g) => ({ ...g, projected: false }))
  }
  if (sf.length === 1) {
    const g = sf[0]
    if (matchesSf1(g)) return [g, projRow(2)]
    if (matchesSf2(g)) return [projRow(1), g]
    return [g, projRow(2)]
  }
  return [projRow(1), projRow(2)]
}

/** Championship row: final game or projected matchup (both SF winners) before the title game. */
function buildPlayoffChRow(ch: any[], sf: any[]) {
  if (ch.length) return { ...ch[0], projected: false }
  if (sf.length === 2) {
    const w1 = sf[0]?.winner
    const w2 = sf[1]?.winner
    if (w1 && w2) {
      return {
        home: String(w1),
        away: String(w2),
        home_score: null,
        away_score: null,
        projected: true,
      }
    }
  }
  if (sf.length === 1 && sf[0]?.winner) {
    return {
      home: String(sf[0].winner),
      away: 'TBD',
      home_score: null,
      away_score: null,
      projected: true,
    }
  }
  return { home: 'TBD', away: 'TBD', home_score: null, away_score: null, projected: true }
}

function buildPlayoffView(state: any, classKey?: string | null) {
  let inner: {
    seeds?: Array<{ seed: number; team: string }>
    bracket_results?: any[]
    completed?: boolean
    champion?: string | null
  } | null = null

  const bc = normalizePlayoffsByClass(state)
  const preferred =
    classKey != null && String(classKey).trim() !== '' ? String(classKey).trim() : null

  if (bc && Object.keys(bc).length) {
    if (preferred) {
      const rk = resolveBracketClassKey(bc, preferred)
      if (rk && bc[rk] && typeof bc[rk] === 'object') inner = bc[rk]
      else inner = null
    } else {
      const uc = state?.playoffs?.user_class || classificationOfUserTeam(state)
      const rk = resolveBracketClassKey(bc, uc) ?? Object.keys(bc).sort((a, b) => a.localeCompare(b))[0] ?? null
      if (rk && bc[rk] && typeof bc[rk] === 'object') inner = bc[rk]
    }
  }

  const missingBracket = Boolean(
    bc && Object.keys(bc).length && preferred && !resolveBracketClassKey(bc, preferred),
  )

  const seeds: Array<{ seed: number; team: string }> = Array.isArray(inner?.seeds) ? inner.seeds : []
  const results: Array<any> = Array.isArray(inner?.bracket_results) ? inner.bracket_results : []
  const byRound = (round: string) => results.filter((g) => String(g?.round || '') === round)
  const qf = byRound('Quarterfinal')
  const sf = byRound('Semifinal')
  const ch = byRound('Championship')
  const completed = Boolean(inner?.completed)
  const champion = inner?.champion != null ? String(inner.champion) : ''
  let viewClass: string | null = null
  if (bc && Object.keys(bc).length) {
    if (preferred) {
      const rk = resolveBracketClassKey(bc, preferred)
      viewClass = rk ?? preferred
    } else {
      const uc = state?.playoffs?.user_class || classificationOfUserTeam(state)
      viewClass = resolveBracketClassKey(bc, uc) ?? Object.keys(bc).sort((a, b) => a.localeCompare(b))[0] ?? null
    }
  } else {
    viewClass = null
  }

  const seedName = (n: number) => seeds.find((s) => Number(s.seed) === n)?.team || `Seed ${n}`
  // Match engine order: 1v8, 2v7, 3v6, 4v5
  const qfPairs = missingBracket
    ? []
    : [
        [1, 8],
        [2, 7],
        [3, 6],
        [4, 5],
      ].map(([a, b]) => ({ home: seedName(a), away: seedName(b) }))

  const sfRows = missingBracket ? [] : buildPlayoffSfRows(qf, sf, qfPairs)
  const chRow = missingBracket ? null : buildPlayoffChRow(ch, sf)

  return { seeds, qfPairs, qf, sf, ch, sfRows, chRow, completed, champion, viewClass, missingBracket }
}

/** Playoff seed (1–8) for a team from initial bracket seeds; null if unknown / placeholder label. */
function playoffSeedForTeam(seeds: Array<{ seed: number; team: string }>, teamName: string): number | null {
  const n = String(teamName ?? '').trim()
  if (!n || n.startsWith('Game ') || /^Seed\s+\d+$/i.test(n)) return null
  const row = seeds.find((s) => String(s.team) === n)
  if (!row) return null
  const sn = Number(row.seed)
  return Number.isFinite(sn) && sn > 0 ? sn : null
}

function playoffRoundLabel(saveState: any): string {
  const p = userPlayoffInner(saveState)
  if (!p) return '—'
  if (p.completed && p.champion) return `Champion · ${p.champion}`
  const results = Array.isArray(p.bracket_results) ? p.bracket_results : []
  const n = results.length
  if (n === 0) return 'Quarterfinals'
  if (n < 4) return `Quarterfinals (${n}/4)`
  if (n === 4) return 'Semifinals'
  if (n < 6) return `Semifinals (${n - 4}/2)`
  if (n === 6) return 'Championship'
  return '—'
}

function playoffNextOpponent(state: any, userTeam: string): string {
  const p = userPlayoffInner(state)
  if (!p || !userTeam) return '—'
  if (p.completed) return p.champion === userTeam ? 'Champion' : '—'
  const results = Array.isArray(p.bracket_results) ? p.bracket_results : []
  const seeds = Array.isArray(p.seeds) ? p.seeds : []
  const userSeed = seeds.find((x: any) => x.team === userTeam)
  if (!userSeed) return '—'

  for (const g of results) {
    if (g.home !== userTeam && g.away !== userTeam) continue
    if (g.winner && g.winner !== userTeam) return 'Eliminated'
  }

  const qf = results.filter((g: any) => g.round === 'Quarterfinal')
  const sf = results.filter((g: any) => g.round === 'Semifinal')

  if (qf.length < 4) {
    const oppSeed = 9 - Number(userSeed.seed)
    return seeds.find((x: any) => Number(x.seed) === oppSeed)?.team ?? '—'
  }
  if (sf.length < 2) {
    const w = qf.map((g: any) => g.winner)
    const pairs: [string, string][] = [
      [w[0], w[3]],
      [w[1], w[2]],
    ]
    const myQf = qf.find((g: any) => g.home === userTeam || g.away === userTeam)
    if (!myQf || myQf.winner !== userTeam) return 'Eliminated'
    for (const [a, b] of pairs) {
      if (a === userTeam) return b
      if (b === userTeam) return a
    }
    return '—'
  }
  if (sf.length === 2) {
    const w1 = sf[0].winner
    const w2 = sf[1].winner
    if (userTeam === w1) return w2
    if (userTeam === w2) return w1
    return 'Eliminated'
  }
  return '—'
}

function playoffLastResult(state: any, userTeam: string): string {
  const results = userPlayoffInner(state)?.bracket_results
  if (!Array.isArray(results) || !userTeam) return '—'
  const mine = [...results].reverse().find((g: any) => g.home === userTeam || g.away === userTeam)
  if (!mine) return '—'
  const userHome = mine.home === userTeam
  const us = userHome ? mine.home_score : mine.away_score
  const them = userHome ? mine.away_score : mine.home_score
  const w = mine.winner === userTeam ? 'W' : 'L'
  const opp = userHome ? mine.away : mine.home
  return `${w} vs ${opp} · ${us}-${them}`
}

function TeamHomePageBody({
  apiBase,
  headers,
  saveId,
  saveState,
  leagueHistory,
  seasonRecaps,
  onMainMenu,
  onSimWeek,
  onSaveState,
  onError,
  backupReminderFrequency = 'none',
  onBackupReminderFrequencyChange,
  onBackupNow,
  onRefreshDynasty,
  logoVersion,
  setLogoVersion,
  stadiumVersion,
  setStadiumVersion,
}: TeamHomePageBodyProps) {
  const isLocalBundle = saveId === '__local__'
  const stadiumFileInputRef = useRef<HTMLInputElement>(null)

  const downloadTeamRecap = async (teamName: string, year: number | string) => {
    try {
      await downloadTeamSeasonRecap({
        apiBase,
        headers,
        saveId,
        teamName,
        year,
        seasonRecaps,
        isLocalBundle,
      })
      onError('')
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : 'Failed to download recap')
    }
  }

  const teamHistoryRecapAvailable = (row: { has_recap?: boolean; year?: unknown }, teamName: string) => {
    if (row.has_recap) return true
    const y = row.year != null && row.year !== '' ? row.year : ''
    if (isLocalBundle) {
      return Boolean(
        seasonRecaps && findLocalSeasonRecap(seasonRecaps, teamName, y as number | string),
      )
    }
    return Boolean(saveId)
  }
  const leagueHistSeasons = useMemo(
    () => (Array.isArray(leagueHistory?.seasons) ? leagueHistory.seasons : []) as Record<string, unknown>[],
    [leagueHistory],
  )
  const phase = useMemo(() => {
    const raw = derivePhaseFromSave(saveState)
    if (raw === 'playoffs') {
      const p = saveState?.playoffs
      if (p?.completed) {
        const cy = Number(saveState?.current_year)
        if (Number.isFinite(cy) && leagueHistSeasons.some((s) => Number(s?.year) === cy)) {
          return 'season_summary'
        }
      }
    }
    return raw
  }, [saveState, leagueHistSeasons])
  const [teamMenu, setTeamMenu] = useState(() => defaultTeamMenuForPhase(derivePhaseFromSave(saveState)))
  const [stateMenu, setStateMenu] = useState('Dashboard')
  const prevPhaseRef = useRef<string | null>(null)
  useEffect(() => {
    const prev = prevPhaseRef.current
    prevPhaseRef.current = phase
    if (phase === 'regular' && (prev === 'preseason' || prev === null)) {
      setTeamMenu('Overview')
      setStateMenu('Dashboard')
    }
    if (phase === 'playoffs' && prev !== 'playoffs') {
      setStateMenu('Dashboard')
      setTeamMenu(PLAYOFF_BRACKET_MENU)
    }
    if (phase === 'preseason' && prev !== 'preseason') {
      setStateMenu('Dashboard')
      setTeamMenu(PRESEASON_TEAM_HUB)
    }
    if (phase === 'offseason' && prev !== 'offseason') {
      setStateMenu('Dashboard')
      setTeamMenu(OFFSEASON_TEAM_HUB)
    }
    if (phase === 'season_summary' && prev !== 'season_summary') {
      setStateMenu('Dashboard')
    }
  }, [phase])
  useEffect(() => {
    setLeagueHistYearPick(null)
  }, [saveId])
  const [offensivePlaybook, setOffensivePlaybook] = useState<string>(() => {
    const t = findTeam(saveState, saveState?.user_team ?? '')
    const off = t?.coach?.offensive_formation
    return off && OFFENSIVE_PLAYBOOKS.includes(off as any) ? off : OFFENSIVE_PLAYBOOKS[0]
  })
  const [defensivePlaybook, setDefensivePlaybook] = useState<string>(() => {
    const t = findTeam(saveState, saveState?.user_team ?? '')
    const def = t?.coach?.defensive_formation
    return def && DEFENSIVE_PLAYBOOKS.includes(def as any) ? def : DEFENSIVE_PLAYBOOKS[0]
  })

  const userTeam = saveState?.user_team ?? ''

  useEffect(() => {
    const t = findTeam(saveState, userTeam)
    const off = t?.coach?.offensive_formation
    const def = t?.coach?.defensive_formation
    if (off && OFFENSIVE_PLAYBOOKS.includes(off as (typeof OFFENSIVE_PLAYBOOKS)[number])) setOffensivePlaybook(off)
    if (def && DEFENSIVE_PLAYBOOKS.includes(def as (typeof DEFENSIVE_PLAYBOOKS)[number])) setDefensivePlaybook(def)
  }, [saveState, userTeam])
  const [showSettings, setShowSettings] = useState(false)

  const { record, rank, classRank, classification: teamBarClassification } = useMemo(
    () => buildRecordAndRank(saveState),
    [saveState],
  )
  const nextOpponent = useMemo(() => getNextOpponent(saveState), [saveState])
  const last = useMemo(() => getLastOpponentAndScore(saveState), [saveState])
  const playoffRoundDisplay = useMemo(() => playoffRoundLabel(saveState), [saveState])
  const playoffNextOpp = useMemo(() => playoffNextOpponent(saveState, userTeam), [saveState, userTeam])
  const playoffLast = useMemo(() => playoffLastResult(saveState, userTeam), [saveState, userTeam])
  const canCoachPlayoffGame = useMemo(() => {
    if (phase !== 'playoffs') return false
    if (saveState?.playoffs?.completed) return false
    const o = playoffNextOpp
    return o !== 'Eliminated' && o !== '—' && o !== 'Title' && o !== 'Champion' && Boolean(o)
  }, [phase, saveState?.playoffs?.completed, playoffNextOpp])
  const scheduleRows = useMemo(() => buildScheduleRows(saveState), [saveState])
  const allTeamNames = useMemo(() => {
    const teams = saveState?.teams ?? []
    const names = teams.map((t: any) => t?.name).filter(Boolean) as string[]
    return [...new Set(names)].sort((a, b) => a.localeCompare(b))
  }, [saveState?.teams])
  const completedScrimmages = useMemo(() => {
    const list = (saveState?.preseason_scrimmages ?? []) as any[]
    return list.filter((s) => s && s.completed !== false && s.name)
  }, [saveState?.preseason_scrimmages])
  const [teamScheduleTeam, setTeamScheduleTeam] = useState('')
  const [teamInfoTeam, setTeamInfoTeam] = useState('')
  const [teamHistoryTeam, setTeamHistoryTeam] = useState('')
  const [graduationReportTeam, setGraduationReportTeam] = useState('')
  /** Must be declared before `leagueStatePanel` (Coaching changes view reads this). */
  const [coachingChangesYear, setCoachingChangesYear] = useState<number | 'all'>('all')
  /** STATE → League History: null = follow default (in-progress season if any, else latest archive). */
  const [leagueHistYearPick, setLeagueHistYearPick] = useState<'live' | number | null>(null)
  const [leagueHistRecapTeam, setLeagueHistRecapTeam] = useState('')
  /** Coaching carousel: optional team filter from hot-seat dropdown (highlights row in league table). */
  const [carouselHotSeatTeamFilter, setCarouselHotSeatTeamFilter] = useState('')
  /** Ranked HC job applications (persisted server-side across carousel rounds I–III). */
  const [carouselJobApplications, setCarouselJobApplications] = useState<string[]>([])
  /** Add-vacancy control for carousel application picker. */
  const [carouselVacancyPick, setCarouselVacancyPick] = useState('')
  /** Playoffs dashboard: which classification bracket to display (multi-class leagues). */
  const [playoffBracketClass, setPlayoffBracketClass] = useState<string>('')
  const prevSaveIdForPlayoffViewRef = useRef<string | null>(null)
  useEffect(() => {
    const prev = prevSaveIdForPlayoffViewRef.current
    prevSaveIdForPlayoffViewRef.current = saveId
    if (prev != null && prev !== saveId) {
      try {
        sessionStorage.removeItem(`fnd.playoff.viewClass.${prev}`)
      } catch {
        /* ignore */
      }
      setPlayoffBracketClass('')
    }
  }, [saveId])
  /** Team classifications plus any `by_class` keys so the dropdown always lists real brackets. */
  const playoffClassOptions = useMemo(() => {
    const fromTeams = uniqueClassifications(saveState)
    const sortedTeams = [...fromTeams].sort((a, b) => a.localeCompare(b))
    const bc = saveState?.playoffs?.by_class
    const fromBrackets =
      bc && typeof bc === 'object' ? Object.keys(bc).sort((a, b) => a.localeCompare(b)) : []
    const merged = new Set<string>([...sortedTeams, ...fromBrackets])
    const mergedArr = [...merged].sort((a, b) => a.localeCompare(b))
    if (mergedArr.length > 1) return mergedArr
    if (fromBrackets.length > 1) return fromBrackets
    return fromBrackets.length ? fromBrackets : sortedTeams
  }, [saveState])
  /** Default tab when the user has not chosen a class yet (empty string). */
  const defaultPlayoffClass = useMemo(() => {
    if (playoffClassOptions.length === 0) return ''
    const uc = saveState?.playoffs?.user_class || classificationOfUserTeam(saveState)
    if (playoffClassOptions.includes(uc)) return uc
    const uci = playoffClassOptions.find((o) => o.toLowerCase() === String(uc).toLowerCase())
    if (uci) return uci
    const bc = saveState?.playoffs?.by_class
    const ukr = uc && bc && typeof bc === 'object' ? resolveBracketClassKey(bc, uc) : null
    if (ukr && playoffClassOptions.includes(ukr)) return ukr
    return playoffClassOptions[0]
  }, [playoffClassOptions, saveState?.playoffs?.user_class, saveState?.teams, saveState?.user_team])
  /** Prefer explicit dropdown selection; otherwise default (user’s class or first option). */
  const bracketClassForView = useMemo(() => {
    const t = (playoffBracketClass || '').trim()
    if (t) return t
    try {
      const s = sessionStorage.getItem(`fnd.playoff.viewClass.${saveId}`)?.trim()
      if (s) return s
    } catch {
      /* ignore */
    }
    return defaultPlayoffClass
  }, [playoffBracketClass, defaultPlayoffClass, saveId])
  const selectPlayoffClassValue = useMemo(() => {
    const v = (playoffBracketClass || '').trim()
    if (v) return v
    try {
      const s = sessionStorage.getItem(`fnd.playoff.viewClass.${saveId}`)?.trim()
      if (s) return s
    } catch {
      /* ignore */
    }
    return defaultPlayoffClass || playoffClassOptions[0] || ''
  }, [playoffBracketClass, defaultPlayoffClass, playoffClassOptions, saveId])
  const playoffView = useMemo(
    () => buildPlayoffView(saveState, bracketClassForView || null),
    [saveState, bracketClassForView],
  )
  const [teamHistoryLoading, setTeamHistoryLoading] = useState(false)
  const [teamHistoryRows, setTeamHistoryRows] = useState<any[]>([])
  const [teamHistoryTotals, setTeamHistoryTotals] = useState<TeamProgramTotalsDisplay | null>(null)
  const teamScheduleRows = useMemo(
    () => buildTeamScheduleRows(saveState, teamScheduleTeam),
    [saveState, teamScheduleTeam],
  )
  const rosterPlayers = useMemo(() => buildRosterPlayersSorted(saveState), [saveState])
  const coachInboxUnread = useMemo(() => {
    const emails = saveState?.coach_inbox?.emails
    if (!Array.isArray(emails)) return 0
    return emails.filter((e: { read?: boolean }) => !e?.read).length
  }, [saveState?.coach_inbox?.emails])
  const rosterGridCols = useMemo(
    () => rosterDepthTableGridTemplateColumns(PLAYER_ATTRIBUTE_COLUMNS_SCROLL.length),
    [],
  )
  const leagueClassOptions = useMemo(() => uniqueClassifications(saveState), [saveState])
  const [leagueClassFilter, setLeagueClassFilter] = useState<string | 'all'>('all')

  useEffect(() => {
    if (leagueClassFilter !== 'all' && !leagueClassOptions.includes(leagueClassFilter)) {
      setLeagueClassFilter('all')
    }
  }, [leagueClassOptions, leagueClassFilter])

  const leagueClassFilterBar = (
    <div className="teamhome-schedule-weekbar teamhome-league-class-bar">
      <span className="teamhome-schedule-week-label">Class</span>
      <select
        className="teamhome-select teamhome-schedule-week-select"
        value={leagueClassFilter}
        onChange={(e) => {
          const v = e.target.value
          setLeagueClassFilter(v === 'all' ? 'all' : v)
        }}
        aria-label="Filter standings and stats by classification"
      >
        <option value="all">All classes</option>
        {leagueClassOptions.map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </select>
      <span className="teamhome-schedule-week-hint">Rankings within the selected class</span>
    </div>
  )

  const standingsRows = useMemo(
    () => buildStandingsRows(saveState, leagueClassFilter),
    [saveState, leagueClassFilter],
  )
  const userClassification = useMemo(() => classificationOfUserTeam(saveState), [saveState])
  const seasonSummaryStandingsRows = useMemo(
    () => buildStandingsRows(saveState, userClassification).slice(0, 10),
    [saveState, userClassification],
  )
  const rankingsRows = useMemo(
    () => buildRankingsRows(saveState, leagueClassFilter),
    [saveState, leagueClassFilter],
  )
  const statsRows = useMemo(() => buildStatsRows(saveState, leagueClassFilter), [saveState, leagueClassFilter])
  const teamStatRows = useMemo(
    () => buildTeamStatRows(saveState, leagueClassFilter),
    [saveState, leagueClassFilter],
  )
  const playerStatRows = useMemo(() => buildPlayerStatRows(saveState), [saveState])
  const leagueRosterPlayerCount = useMemo(() => {
    let n = 0
    for (const t of saveState?.teams ?? []) {
      const r = t?.roster
      if (Array.isArray(r)) n += r.length
    }
    return n
  }, [saveState?.teams])

  const prestigeReportRows = useMemo(
    () => buildPrestigeReportRows(saveState?.teams ?? [], userTeam),
    [saveState?.teams, userTeam],
  )

  const leagueHistDefaultYearMode = useMemo((): 'live' | number => {
    const cy = Number(saveState?.current_year)
    const hasArchived = Number.isFinite(cy) && leagueHistSeasons.some((s) => Number(s?.year) === cy)
    if (Number.isFinite(cy) && !hasArchived && (phase === 'regular' || phase === 'playoffs')) {
      return 'live'
    }
    const years = leagueHistSeasons.map((s) => Number(s.year)).filter((y) => Number.isFinite(y)) as number[]
    if (years.length) return Math.max(...years)
    return Number.isFinite(cy) ? cy : 0
  }, [leagueHistSeasons, saveState?.current_year, phase])

  const leagueHistEffectiveMode = leagueHistYearPick ?? leagueHistDefaultYearMode

  useEffect(() => {
    if (leagueHistEffectiveMode !== 'live') {
      setLeagueHistRecapTeam((prev) => prev || userTeam)
    }
  }, [leagueHistEffectiveMode, userTeam])

  const lhArchivedSeasonEntry = useMemo(() => {
    if (leagueHistEffectiveMode === 'live') return null
    const y = leagueHistEffectiveMode as number
    if (!Number.isFinite(y) || y <= 0) return null
    return findSeasonEntryByCalendarYear(leagueHistSeasons, y)
  }, [leagueHistEffectiveMode, leagueHistSeasons])

  const lhStandingsForRankings = useMemo(() => {
    if (leagueHistEffectiveMode === 'live') return saveState?.standings ?? {}
    return standingsListToRecord(lhArchivedSeasonEntry?.standings)
  }, [leagueHistEffectiveMode, saveState?.standings, lhArchivedSeasonEntry])

  const lhRankingsFakeState = useMemo(
    () => ({
      standings: lhStandingsForRankings,
      teams: saveState?.teams ?? [],
      current_week: 999,
    }),
    [lhStandingsForRankings, saveState?.teams],
  )

  const lhRecapTeamNames = useMemo(() => {
    const st = lhArchivedSeasonEntry?.standings
    if (Array.isArray(st) && st.length > 0) {
      const names = st
        .map((r) => (r && typeof r === 'object' ? String((r as { team?: unknown }).team ?? '').trim() : ''))
        .filter(Boolean)
      if (names.length) return [...new Set(names)].sort((a, b) => a.localeCompare(b))
    }
    return allTeamNames
  }, [lhArchivedSeasonEntry, allTeamNames])

  const lhRecapArchiveYear =
    leagueHistEffectiveMode !== 'live' && Number.isFinite(Number(leagueHistEffectiveMode))
      ? Number(leagueHistEffectiveMode)
      : null

  const lhRecapCanDownload = useMemo(() => {
    const team = (leagueHistRecapTeam || userTeam).trim()
    if (!team || lhRecapArchiveYear == null || !lhArchivedSeasonEntry) return false
    if (
      hasRecapForArchivedSeason(lhArchivedSeasonEntry, team, lhRecapArchiveYear, seasonRecaps) ||
      Boolean(findLocalSeasonRecap(seasonRecaps, team, lhRecapArchiveYear))
    ) {
      return true
    }
    return Boolean(saveId && !isLocalBundle)
  }, [
    leagueHistRecapTeam,
    userTeam,
    lhRecapArchiveYear,
    lhArchivedSeasonEntry,
    seasonRecaps,
    saveId,
    isLocalBundle,
  ])

  const lhPlayoffsByClass = useMemo(() => {
    if (leagueHistEffectiveMode === 'live') {
      const bc = normalizePlayoffsByClass(saveState)
      if (bc && Object.keys(bc).length) {
        const o: Record<string, Record<string, unknown>> = {}
        for (const [k, v] of Object.entries(bc)) {
          if (v && typeof v === 'object') o[k] = v as Record<string, unknown>
        }
        return o
      }
      return {}
    }
    const cmap = teamClassificationMap(saveState)
    return getHistoricalPlayoffsByClass(lhArchivedSeasonEntry, (nm) => cmap.get(nm) ?? '—')
  }, [leagueHistEffectiveMode, saveState, lhArchivedSeasonEntry])

  const lhYearDropdownOptions = useMemo(() => {
    const archivedYears = [
      ...new Set(leagueHistSeasons.map((s) => Number(s.year)).filter((y) => Number.isFinite(y))),
    ].sort((a, b) => b - a) as number[]
    const cy = Number(saveState?.current_year)
    const hasArchivedCurrent = Number.isFinite(cy) && archivedYears.includes(cy)
    const showLive =
      Number.isFinite(cy) && !hasArchivedCurrent && (phase === 'regular' || phase === 'playoffs')
    return { archivedYears, showLive, currentYear: cy }
  }, [leagueHistSeasons, saveState?.current_year, phase])

  const topLeaguePlayerRows = useMemo(() => buildTopLeaguePlayerRows(saveState, 250), [saveState])
  const [teamStatsSortKey, setTeamStatsSortKey] = useState<keyof TeamStatRow>('ppg')
  const [teamStatsSortDir, setTeamStatsSortDir] = useState<'asc' | 'desc'>('desc')
  const [playerStatsSide, setPlayerStatsSide] = useState<'offense' | 'defense'>('offense')
  const [playerStatsSortKey, setPlayerStatsSortKey] = useState<string>('passYds')
  const [playerStatsSortDir, setPlayerStatsSortDir] = useState<'asc' | 'desc'>('desc')

  const sortedTeamStatRows = useMemo(() => {
    const arr = [...teamStatRows]
    arr.sort((a, b) => {
      const av = a[teamStatsSortKey]
      const bv = b[teamStatsSortKey]
      if (typeof av === 'string' && typeof bv === 'string') {
        return teamStatsSortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av)
      }
      const an = Number(av ?? 0)
      const bn = Number(bv ?? 0)
      return teamStatsSortDir === 'asc' ? an - bn : bn - an
    })
    return arr
  }, [teamStatRows, teamStatsSortDir, teamStatsSortKey])
  useEffect(() => {
    if (playerStatsSide === 'offense') {
      setPlayerStatsSortKey('passYds')
      setPlayerStatsSortDir('desc')
    } else {
      setPlayerStatsSortKey('tackles')
      setPlayerStatsSortDir('desc')
    }
  }, [playerStatsSide])

  useEffect(() => {
    if (stateMenu !== 'Team History') return
    void onRefreshDynasty?.()
  }, [stateMenu, onRefreshDynasty])

  useEffect(() => {
    if (stateMenu !== 'Team History') return
    if (!teamHistoryTeam && userTeam) setTeamHistoryTeam(userTeam)
  }, [stateMenu, teamHistoryTeam, userTeam])

  useEffect(() => {
    if (stateMenu !== 'Team History') return
    const team = (teamHistoryTeam || userTeam || '').trim()
    if (!team) {
      setTeamHistoryRows([])
      setTeamHistoryLoading(false)
      return
    }

    const applyClientRows = () => {
      const clientArchived = buildFullTeamHistoryRows(leagueHistory, team, saveState, seasonRecaps)
      setTeamHistoryRows(
        mergeLiveAndSnapshotTeamHistory(
          clientArchived,
          team,
          saveState,
          saveState?.teams,
          seasonRecaps,
        ),
      )
      const tr = findTeam(saveState, team)
      const persistedReg = Number((tr as { regional_championships?: number })?.regional_championships ?? 0)
      setTeamHistoryTotals(
        mergeInProgressTeamProgramTotals(
          buildTeamProgramTotalsFromLeagueHistory(leagueHistory, team, persistedReg),
          team,
          saveState,
        ),
      )
    }

    if (isLocalBundle) {
      setTeamHistoryLoading(false)
      applyClientRows()
      onError('')
      return
    }

    applyClientRows()

    if (!apiBase || !saveId) {
      setTeamHistoryLoading(false)
      return
    }

    let cancelled = false
    setTeamHistoryLoading(true)
    void (async () => {
      try {
        const hdrs = headers?.Authorization ? headers : {}
        const r = await fetch(`${apiBase}/saves/${saveId}/team-history?team_name=${encodeURIComponent(team)}`, {
          headers: hdrs,
        })
        if (!r.ok) throw new Error(await r.text())
        const j = await r.json()
        if (!cancelled) {
          const fromApi = Array.isArray(j?.history) ? j.history : []
          const clientArchived = buildFullTeamHistoryRows(leagueHistory, team, saveState, seasonRecaps)
          const archived = mergeTeamHistoryRowLists(fromApi, clientArchived)
          setTeamHistoryRows(
            mergeLiveAndSnapshotTeamHistory(archived, team, saveState, saveState?.teams, seasonRecaps),
          )
          const tot = j?.totals && typeof j.totals === 'object' ? (j.totals as Record<string, unknown>) : null
          if (tot) {
            const base: TeamProgramTotalsDisplay = {
              program_wins: Number(tot.program_wins ?? 0),
              program_losses: Number(tot.program_losses ?? 0),
              state_championships: Number(tot.state_championships ?? 0),
              regional_championships: Number(tot.regional_championships ?? 0),
              playoff_appearances: Number(tot.playoff_appearances ?? 0),
            }
            setTeamHistoryTotals(mergeInProgressTeamProgramTotals(base, team, saveState))
          }
          const tn = String(j?.team_name ?? team)
          if (!teamHistoryTeam && tn) setTeamHistoryTeam(tn)
          onError('')
        }
      } catch (e: unknown) {
        if (!cancelled) {
          applyClientRows()
          onError(e instanceof Error ? e.message : 'Failed to load team history from server (showing local data)')
        }
      } finally {
        if (!cancelled) setTeamHistoryLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
    // Refetch when the calendar advances (e.g. playoffs → offseason) so data isn’t stale if this tab stays open.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- onError identity can churn from parent
  }, [
    stateMenu,
    apiBase,
    headers,
    saveId,
    teamHistoryTeam,
    userTeam,
    isLocalBundle,
    leagueHistory,
    seasonRecaps,
    saveState,
    saveState?.season_phase,
    saveState?.current_year,
    saveState?.last_completed_year,
    saveState?.last_completed_standings,
  ])
  const sortedPlayerStatRows = useMemo(() => {
    const arr = [...playerStatRows]
    arr.sort((a, b) => {
      if (playerStatsSortKey === 'cmpPct') {
        const ac = a.att > 0 ? (a.comp / a.att) * 100 : 0
        const bc = b.att > 0 ? (b.comp / b.att) * 100 : 0
        return playerStatsSortDir === 'asc' ? ac - bc : bc - ac
      }
      const av = (a as any)[playerStatsSortKey]
      const bv = (b as any)[playerStatsSortKey]
      if (typeof av === 'string' && typeof bv === 'string') {
        return playerStatsSortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av)
      }
      return playerStatsSortDir === 'asc' ? Number(av ?? 0) - Number(bv ?? 0) : Number(bv ?? 0) - Number(av ?? 0)
    })
    return arr
  }, [playerStatRows, playerStatsSortDir, playerStatsSortKey])

  const numScheduleWeeks = saveState?.weeks?.length ?? 0
  const [scheduleWeek, setScheduleWeek] = useState(1)

  useEffect(() => {
    const n = saveState?.weeks?.length ?? 0
    const cw = Number(saveState?.current_week ?? 1)
    setScheduleWeek(n > 0 ? Math.min(Math.max(1, cw), n) : 1)
  }, [saveId])

  useEffect(() => {
    if (numScheduleWeeks < 1) return
    setScheduleWeek((w) => Math.min(Math.max(1, w), numScheduleWeeks))
  }, [numScheduleWeeks])

  useEffect(() => {
    if (!allTeamNames.length) return
    setTeamScheduleTeam((prev) =>
      prev && allTeamNames.includes(prev)
        ? prev
        : userTeam && allTeamNames.includes(userTeam)
          ? userTeam
          : allTeamNames[0],
    )
  }, [allTeamNames, userTeam, saveId])

  useEffect(() => {
    if (!allTeamNames.length) return
    setTeamInfoTeam((prev) =>
      prev && allTeamNames.includes(prev)
        ? prev
        : userTeam && allTeamNames.includes(userTeam)
          ? userTeam
          : allTeamNames[0],
    )
  }, [allTeamNames, userTeam, saveId])

  const graduationReportTeamNames = useMemo(() => {
    const r = saveState?.offseason_graduation_report
    if (!r || typeof r !== 'object') return [] as string[]
    return Object.keys(r as Record<string, unknown>)
      .filter(Boolean)
      .sort((a, b) => a.localeCompare(b))
  }, [saveState?.offseason_graduation_report])

  useEffect(() => {
    if (!graduationReportTeamNames.length) return
    setGraduationReportTeam((prev) =>
      prev && graduationReportTeamNames.includes(prev)
        ? prev
        : userTeam && graduationReportTeamNames.includes(userTeam)
          ? userTeam
          : graduationReportTeamNames[0],
    )
  }, [graduationReportTeamNames, userTeam, saveId])

  const graduationViewTeam = useMemo(() => {
    if (!graduationReportTeamNames.length) return ''
    return graduationReportTeamNames.includes(graduationReportTeam)
      ? graduationReportTeam
      : graduationReportTeamNames[0]
  }, [graduationReportTeamNames, graduationReportTeam])

  const graduationPlayersForView = useMemo(() => {
    if (!graduationViewTeam) return [] as any[]
    const report = saveState?.offseason_graduation_report as Record<string, any[]> | undefined
    const players = report?.[graduationViewTeam]
    return Array.isArray(players) ? players : []
  }, [saveState?.offseason_graduation_report, graduationViewTeam])

  const stateWeekGames = useMemo(() => buildStateWeekGames(saveState, scheduleWeek), [saveState, scheduleWeek])
  const toggleTeamStatsSort = (key: keyof TeamStatRow) => {
    if (teamStatsSortKey === key) {
      setTeamStatsSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
      return
    }
    setTeamStatsSortKey(key)
    setTeamStatsSortDir(key === 'teamName' ? 'asc' : 'desc')
  }
  const togglePlayerStatsSort = (key: string) => {
    if (playerStatsSortKey === key) {
      setPlayerStatsSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
      return
    }
    setPlayerStatsSortKey(key)
    setPlayerStatsSortDir(key === 'playerName' || key === 'teamName' || key === 'position' ? 'asc' : 'desc')
  }

  const downloadWeekText = async (weekNum: number, gameIndex: number, kind: 'box-score' | 'game-log') => {
    if (isLocalBundle) {
      const wk = (saveState?.week_results ?? [])[Number(weekNum) - 1]
      const g = Array.isArray(wk) ? wk[gameIndex] : null
      const text =
        kind === 'box-score'
          ? String(g?.box_score_text ?? g?.recap ?? '').trim()
          : String(g?.game_log_text ?? '').trim()
      if (!text) throw new Error('That export is not available in this save bundle yet.')
      const blob = new Blob([text + '\n'], { type: 'text/plain' })
      const objUrl = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = objUrl
      a.download = `${kind}_week_${weekNum}_game_${gameIndex + 1}.txt`
      document.body.appendChild(a)
      a.click()
      a.remove()
      setTimeout(() => URL.revokeObjectURL(objUrl), 250)
      return
    }
    const path = kind === 'box-score' ? 'box-score.txt' : 'game-log.txt'
    const url = `${apiBase}/saves/${saveId}/weeks/${weekNum}/games/${gameIndex}/${path}`
    const r = await fetch(url, { headers })
    if (!r.ok) {
      const err = await r.text().catch(() => '')
      throw new Error(err || `Failed to export ${kind}`)
    }
    const blob = await r.blob()
    const objUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    const cd = r.headers.get('content-disposition') || ''
    const m = cd.match(/filename=\"?([^\";]+)\"?/i)
    a.href = objUrl
    a.download = m?.[1] || `${kind}.txt`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(objUrl)
  }

  const downloadPlayoffText = async (
    roundName: string,
    home: string,
    away: string,
    kind: 'box-score' | 'game-log',
    classification?: string | null,
  ) => {
    if (isLocalBundle) throw new Error('Playoff exports are not available in local bundle mode yet.')
    const clsQ =
      classification && String(classification).trim()
        ? `&classification=${encodeURIComponent(String(classification).trim())}`
        : ''
    const url = `${apiBase}/saves/${saveId}/playoffs/game-text.txt?round=${encodeURIComponent(roundName)}&home=${encodeURIComponent(home)}&away=${encodeURIComponent(away)}&kind=${encodeURIComponent(kind)}${clsQ}`
    const r = await fetch(url, { headers })
    if (!r.ok) {
      const err = await r.text().catch(() => '')
      throw new Error(err || `Failed to export ${kind}`)
    }
    const blob = await r.blob()
    const objUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    const cd = r.headers.get('content-disposition') || ''
    const m = cd.match(/filename=\"?([^\";]+)\"?/i)
    a.href = objUrl
    a.download = m?.[1] || `${kind}.txt`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(objUrl)
  }

  const teamWithLogo = (
    name: string,
    logoSize = 28,
    opts?: { playoffSeed?: number | null },
  ) => {
    const seed = opts?.playoffSeed
    const showSeed = seed != null && seed > 0
    return (
      <div className="teamhome-name-with-logo">
        <TeamLogo apiBase={apiBase} headers={headers} teamName={name} logoVersion={logoVersion} size={logoSize} />
        <span>
          {showSeed ? <span className="teamhome-playoffs-seed">#{seed}</span> : null}
          {name}
        </span>
      </div>
    )
  }

  const renderPlayoffBracketLine = (
    name: string,
    score: number | null | undefined,
    opts?: { playoffSeed?: number | null },
  ) => {
    const sn = typeof score === 'number' && Number.isFinite(score) ? score : null
    return (
      <div className="teamhome-playoffs-teamline teamhome-playoffs-teamline--withscore">
        <div className="teamhome-playoffs-teamline-main">
          {teamWithLogo(name, 22, opts)}
        </div>
        {sn != null ? <span className="teamhome-playoffs-line-score">{sn}</span> : null}
      </div>
    )
  }

  const seasonSummaryBracketNode = useMemo(() => {
    if (playoffView.missingBracket) return null
    return (
      <div className="teamhome-playoffs-grid season-summary-bracket-readonly" key={`ss-bracket-${bracketClassForView}`}>
        <div className="teamhome-card">
          <div className="teamhome-card-title">Quarterfinals</div>
          <div className="teamhome-playoffs-list">
            {playoffView.qfPairs.map((m) => {
              const played = findQfGame(playoffView.qf, m)
              const playedHomeScore =
                played == null ? null : played?.home === m.home ? played?.home_score : played?.away_score
              const playedAwayScore =
                played == null ? null : played?.home === m.home ? played?.away_score : played?.home_score
              return (
                <div key={`${m.home}-${m.away}`} className="teamhome-playoffs-row teamhome-playoffs-row--stacked">
                  <div className="teamhome-playoffs-matchup">
                    {renderPlayoffBracketLine(m.home, playedHomeScore, {
                      playoffSeed: playoffSeedForTeam(playoffView.seeds, m.home),
                    })}
                    {renderPlayoffBracketLine(m.away, playedAwayScore, {
                      playoffSeed: playoffSeedForTeam(playoffView.seeds, m.away),
                    })}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
        <div className="teamhome-card">
          <div className="teamhome-card-title">Semifinals</div>
          <div className="teamhome-playoffs-list">
            {playoffView.sfRows.map((g: { home: string; away: string; home_score?: number | null; away_score?: number | null }, i: number) => (
              <div key={`sf-${i}-${g.home}-${g.away}`} className="teamhome-playoffs-row teamhome-playoffs-row--stacked">
                <div className="teamhome-playoffs-matchup">
                  {renderPlayoffBracketLine(String(g.home), g.home_score, {
                    playoffSeed: playoffSeedForTeam(playoffView.seeds, String(g.home)),
                  })}
                  {renderPlayoffBracketLine(String(g.away), g.away_score, {
                    playoffSeed: playoffSeedForTeam(playoffView.seeds, String(g.away)),
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="teamhome-card">
          <div className="teamhome-card-title">Championship</div>
          <div className="teamhome-playoffs-list">
            {playoffView.chRow ? (
              <div className="teamhome-playoffs-row teamhome-playoffs-row--stacked">
                <div className="teamhome-playoffs-matchup">
                  {renderPlayoffBracketLine(String(playoffView.chRow.home), playoffView.chRow.home_score, {
                    playoffSeed: playoffSeedForTeam(playoffView.seeds, String(playoffView.chRow.home)),
                  })}
                  {renderPlayoffBracketLine(String(playoffView.chRow.away), playoffView.chRow.away_score, {
                    playoffSeed: playoffSeedForTeam(playoffView.seeds, String(playoffView.chRow.away)),
                  })}
                </div>
              </div>
            ) : (
              <div className="teamhome-small teamhome-playoffs-empty">TBD</div>
            )}
          </div>
        </div>
      </div>
    )
  }, [playoffView, bracketClassForView, renderPlayoffBracketLine])

  /** League / state views shown when TEAM menu is Overview (regular season). */
  const leagueStatePanel =
    stateMenu === 'Standings' ? (
      <div className="teamhome-roster-shell">
        {leagueClassFilterBar}
        <div className="teamhome-roster-head teamhome-standings-row">
          <div className="teamhome-roster-cell">Rank</div>
          <div className="teamhome-roster-name">Team Name</div>
          <div className="teamhome-roster-cell">Record</div>
          <div className="teamhome-roster-cell">Pts For</div>
          <div className="teamhome-roster-cell">Pts Agn</div>
          <div className="teamhome-roster-cell">Pt Diff</div>
          <div className="teamhome-roster-cell">PPG</div>
          <div className="teamhome-roster-cell">PPGD</div>
        </div>
        <div className="teamhome-roster-table">
          {standingsRows.length === 0 ? (
            <div className="teamhome-roster-empty">No standings data yet.</div>
          ) : (
            standingsRows.map((r, i) => (
              <div key={`${r.teamName}-${i}`} className="teamhome-standings-row">
                <div className="teamhome-roster-cell">{r.rank}</div>
                <div className="teamhome-roster-name">{teamWithLogo(r.teamName)}</div>
                <div className="teamhome-roster-cell">
                  {r.wins}-{r.losses}
                </div>
                <div className="teamhome-roster-cell">{r.pointsFor}</div>
                <div className="teamhome-roster-cell">{r.pointsAgainst}</div>
                <div className="teamhome-roster-cell">{r.diff >= 0 ? `+${r.diff}` : r.diff}</div>
                <div className="teamhome-roster-cell">{r.ppg.toFixed(1)}</div>
                <div className="teamhome-roster-cell">{r.ppgd >= 0 ? `+${r.ppgd.toFixed(1)}` : r.ppgd.toFixed(1)}</div>
              </div>
            ))
          )}
        </div>
      </div>
    ) : stateMenu === 'Weekly schedule' ? (
      <div className="teamhome-roster-shell teamhome-schedule-shell">
        <div className="teamhome-schedule-weekbar">
          <span className="teamhome-schedule-week-label">Week</span>
          <select
            className="teamhome-select teamhome-schedule-week-select"
            value={scheduleWeek}
            onChange={(e) => setScheduleWeek(Number(e.target.value))}
            disabled={numScheduleWeeks < 1}
          >
            {numScheduleWeeks < 1 ? (
              <option value={1}>—</option>
            ) : (
              Array.from({ length: numScheduleWeeks }, (_, i) => i + 1).map((w) => (
                <option key={w} value={w}>
                  {w}
                </option>
              ))
            )}
          </select>
          <span className="teamhome-schedule-week-hint">All state matchups for this week</span>
        </div>
        <div className="teamhome-roster-head teamhome-schedule-head">Home team | Away team | Box score | Game log</div>
        <div className="teamhome-roster-table">
          {numScheduleWeeks < 1 ? (
            <div className="teamhome-roster-empty">No regular-season schedule yet.</div>
          ) : stateWeekGames.length === 0 ? (
            <div className="teamhome-roster-empty">No games this week.</div>
          ) : (
            stateWeekGames.map((g) => {
              const scoreShort = g.played
                ? `${g.homeScore}–${g.awayScore}${g.ot ? ' OT' : ''}`
                : '—'
              return (
                <div
                  key={`${g.home}-${g.away}-${g.gameIndex}`}
                  className="teamhome-schedule-row teamhome-schedule-row--weekly"
                >
                  <div className="teamhome-schedule-cell teamhome-schedule-team">{teamWithLogo(g.home)}</div>
                  <div className="teamhome-schedule-cell teamhome-schedule-team">{teamWithLogo(g.away)}</div>
                  <div className="teamhome-schedule-cell teamhome-schedule-actions">
                    <span className="teamhome-schedule-score">{scoreShort}</span>
                    <button
                      type="button"
                      className="teamhome-schedule-link"
                      disabled={!g.played}
                          onClick={async () => {
                            try {
                              await downloadWeekText(scheduleWeek, g.gameIndex, 'box-score')
                            } catch (e: any) {
                              onError(e?.message ?? 'Failed to export box score')
                            }
                          }}
                    >
                      Box score
                    </button>
                  </div>
                  <div className="teamhome-schedule-cell teamhome-schedule-actions">
                    <button
                      type="button"
                      className="teamhome-schedule-link"
                      disabled={!g.played}
                          onClick={async () => {
                            try {
                              await downloadWeekText(scheduleWeek, g.gameIndex, 'game-log')
                            } catch (e: any) {
                              onError(e?.message ?? 'Failed to export game log')
                            }
                          }}
                    >
                      Game log
                    </button>
                  </div>
                </div>
              )
            })
          )}
        </div>
      </div>
    ) : stateMenu === 'Rankings' ? (
      <div className="teamhome-roster-shell">
        {leagueClassFilterBar}
        <div className="teamhome-roster-head teamhome-rankings-row">
          <div className="teamhome-roster-cell">Rank</div>
          <div className="teamhome-roster-name">Team Name</div>
          <div className="teamhome-roster-cell">Record</div>
          <div className="teamhome-roster-cell">Composite</div>
          <div className="teamhome-roster-cell">Pt Diff</div>
          <div className="teamhome-roster-cell">PPG</div>
        </div>
        <div className="teamhome-roster-table">
          {rankingsRows.length === 0 ? (
            <div className="teamhome-roster-empty">No rankings data yet.</div>
          ) : (
            rankingsRows.map((r, i) => (
              <div key={`${r.teamName}-rank-${i}`} className="teamhome-rankings-row">
                <div className="teamhome-roster-cell">{r.rank}</div>
                <div className="teamhome-roster-name">{teamWithLogo(r.teamName)}</div>
                <div className="teamhome-roster-cell">
                  {r.wins}-{r.losses}
                </div>
                <div className="teamhome-roster-cell">{r.score.toFixed(1)}</div>
                <div className="teamhome-roster-cell">{r.diff >= 0 ? `+${r.diff}` : r.diff}</div>
                <div className="teamhome-roster-cell">{r.ppg.toFixed(1)}</div>
              </div>
            ))
          )}
        </div>
      </div>
    ) : stateMenu === 'Stats' ? (
      <div className="teamhome-roster-shell">
        {leagueClassFilterBar}
        <div className="teamhome-roster-head teamhome-stats-row">
          <div className="teamhome-roster-name">Team Name</div>
          <div className="teamhome-roster-cell">Games</div>
          <div className="teamhome-roster-cell">PPG</div>
          <div className="teamhome-roster-cell">PPGD</div>
          <div className="teamhome-roster-cell">Pts For</div>
          <div className="teamhome-roster-cell">Pts Agn</div>
          <div className="teamhome-roster-cell">Pt Diff</div>
        </div>
        <div className="teamhome-roster-table">
          {statsRows.length === 0 ? (
            <div className="teamhome-roster-empty">No stats data yet.</div>
          ) : (
            statsRows.map((r, i) => (
              <div key={`${r.teamName}-stats-${i}`} className="teamhome-stats-row">
                <div className="teamhome-roster-name">{teamWithLogo(r.teamName)}</div>
                <div className="teamhome-roster-cell">{r.games}</div>
                <div className="teamhome-roster-cell">{r.ppg.toFixed(1)}</div>
                <div className="teamhome-roster-cell">{r.ppgd >= 0 ? `+${r.ppgd.toFixed(1)}` : r.ppgd.toFixed(1)}</div>
                <div className="teamhome-roster-cell">{r.pointsFor}</div>
                <div className="teamhome-roster-cell">{r.pointsAgainst}</div>
                <div className="teamhome-roster-cell">{r.diff >= 0 ? `+${r.diff}` : r.diff}</div>
              </div>
            ))
          )}
        </div>
      </div>
    ) : stateMenu === 'Top Players' ? (
      <div className="teamhome-roster-shell">
        <div className="teamhome-teaminfo-header" style={{ marginBottom: 12 }}>
          <div className="teamhome-card-title" style={{ marginBottom: 0 }}>
            Top 250 players
          </div>
          <div className="teamhome-small" style={{ marginTop: 8, opacity: 0.9, maxWidth: 560 }}>
            Statewide rostered athletes ranked by composite overall (same formula as the roster tab). Showing{' '}
            <b>{topLeaguePlayerRows.length}</b>
            {leagueRosterPlayerCount > topLeaguePlayerRows.length ? (
              <>
                {' '}
                of <b>{leagueRosterPlayerCount}</b> rostered.
              </>
            ) : (
              ' players.'
            )}
          </div>
        </div>
        <div className="teamhome-roster-head teamhome-topplayers-row">
          <div className="teamhome-roster-cell">Rank</div>
          <div className="teamhome-roster-name">Player</div>
          <div className="teamhome-roster-cell">Grade</div>
          <div className="teamhome-roster-cell">Pos</div>
          <div className="teamhome-roster-cell">OVR</div>
          <div className="teamhome-roster-name">School</div>
        </div>
        <div className="teamhome-roster-table">
          {topLeaguePlayerRows.length === 0 ? (
            <div className="teamhome-roster-empty">No player data loaded yet.</div>
          ) : (
            topLeaguePlayerRows.map((r) => (
              <div key={`tp-${r.rank}-${r.school}-${r.name}`} className="teamhome-topplayers-row">
                <div className="teamhome-roster-cell">{r.rank}</div>
                <div className="teamhome-roster-name">{r.name}</div>
                <div className="teamhome-roster-cell">{r.gradeLabel}</div>
                <div className="teamhome-roster-cell">{r.position}</div>
                <div className="teamhome-roster-cell">{r.overall}</div>
                <div className="teamhome-roster-name">{teamWithLogo(r.school)}</div>
              </div>
            ))
          )}
        </div>
      </div>
    ) : stateMenu === 'Team Schedule' ? (
      <div className="teamhome-roster-shell teamhome-schedule-shell">
        <div className="teamhome-schedule-weekbar">
          <span className="teamhome-schedule-week-label">Team</span>
          <select
            className="teamhome-select teamhome-schedule-week-select"
            value={teamScheduleTeam}
            onChange={(e) => setTeamScheduleTeam(e.target.value)}
            disabled={allTeamNames.length < 1}
          >
            {allTeamNames.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
          <span className="teamhome-schedule-week-hint">That team&apos;s regular-season games</span>
        </div>
        <div className="teamhome-roster-head teamhome-schedule-head">
          Week | Location | Opponent | Score | Result | Box score | Game log
        </div>
        <div className="teamhome-roster-table">
          {teamScheduleRows.length === 0 ? (
            <div className="teamhome-roster-empty">No schedule on file for this season.</div>
          ) : (
            teamScheduleRows.map((g) => {
              const userScore = g.userHome ? g.homeScore : g.awayScore
              const oppScore = g.userHome ? g.awayScore : g.homeScore
              const resultClass =
                g.result === 'W'
                  ? 'teamhome-schedule-result--w'
                  : g.result === 'L'
                    ? 'teamhome-schedule-result--l'
                    : g.result === 'T'
                      ? 'teamhome-schedule-result--t'
                      : ''
              return (
                <div key={`ts-${g.week}-${g.gameIndex}`} className="teamhome-schedule-row teamhome-schedule-row--team">
                  <div className="teamhome-schedule-cell">{g.week}</div>
                  <div className="teamhome-schedule-cell">{g.userHome ? 'Home' : 'Away'}</div>
                  <div className="teamhome-schedule-cell teamhome-schedule-team">
                    {teamWithLogo(g.opponent)}
                    {g.isRegionGame ? (
                      <span className="teamhome-region-mark" title="Region game">*</span>
                    ) : null}
                  </div>
                  <div className="teamhome-schedule-cell teamhome-schedule-team">
                    {g.played ? `${userScore}–${oppScore}${g.ot ? ' OT' : ''}` : '—'}
                  </div>
                  <div
                    className={['teamhome-schedule-cell', 'teamhome-schedule-result', resultClass].filter(Boolean).join(' ')}
                  >
                    {g.played && g.result ? g.result : '—'}
                  </div>
                  <div className="teamhome-schedule-cell teamhome-schedule-actions">
                    <button
                      type="button"
                      className="teamhome-schedule-link"
                      disabled={!g.played || !saveId}
                      onClick={async () => {
                        try {
                          await downloadWeekText(g.week, g.gameIndex, 'box-score')
                        } catch (e: any) {
                          onError(e?.message ?? 'Failed to export box score')
                        }
                      }}
                    >
                      Box score
                    </button>
                  </div>
                  <div className="teamhome-schedule-cell teamhome-schedule-actions">
                    <button
                      type="button"
                      className="teamhome-schedule-link"
                      disabled={!g.played || !saveId}
                      onClick={async () => {
                        try {
                          await downloadWeekText(g.week, g.gameIndex, 'game-log')
                        } catch (e: any) {
                          onError(e?.message ?? 'Failed to export game log')
                        }
                      }}
                    >
                      Game log
                    </button>
                  </div>
                </div>
              )
            })
          )}
        </div>
        {teamScheduleRows.some((g) => g.isRegionGame) ? (
          <div className="teamhome-schedule-region-legend teamhome-small">
            <span className="teamhome-region-mark">*</span> Region game
          </div>
        ) : null}
      </div>
    ) : stateMenu === 'Team Info' ? (
      (() => {
        const viewTeam = teamInfoTeam || userTeam
        const t = findTeam(saveState, viewTeam)
        const { record: tiRecord, rank: tiRank, classRank: tiClassRank, classification: tiClassRankGroup } =
          buildRecordAndRankForTeam(saveState, viewTeam)
        const coachName = t?.coach?.name != null ? safeStr(t.coach.name) : '—'
        const tm = t as Record<string, unknown>
        const persistedRegional = Number(tm.regional_championships ?? 0)
        const baseFromTeamsRow: TeamProgramTotalsDisplay | null =
          viewTeam
            ? {
                program_wins: Number(tm.program_wins ?? 0),
                program_losses: Number(tm.program_losses ?? 0),
                state_championships: Number(tm.championships ?? 0),
                regional_championships: persistedRegional,
                playoff_appearances: Number(tm.playoff_appearances ?? 0),
              }
            : null
        const hasLeagueHistSeasons =
          Boolean(leagueHistory) &&
          Array.isArray((leagueHistory as { seasons?: unknown }).seasons) &&
          ((leagueHistory as { seasons: unknown[] }).seasons?.length ?? 0) > 0
        const histTotals =
          viewTeam
            ? mergeInProgressTeamProgramTotals(
                hasLeagueHistSeasons
                  ? buildTeamProgramTotalsFromLeagueHistory(leagueHistory, viewTeam, persistedRegional)
                  : baseFromTeamsRow!,
                viewTeam,
                saveState,
              )
            : null
        const programWins =
          histTotals?.program_wins ??
          (typeof tm.program_wins === 'number' ? tm.program_wins : 0)
        const programLosses =
          histTotals?.program_losses ??
          (typeof tm.program_losses === 'number' ? tm.program_losses : 0)
        const programRecord = `${programWins}-${programLosses}`
        const playoffAppsRaw =
          histTotals?.playoff_appearances ??
          (typeof tm.playoff_appearances === 'number' ? tm.playoff_appearances : 0)
        const playoffAppearancesStr = String(playoffAppsRaw)
        const nickname =
          t?.nickname != null && String(t.nickname).trim() !== ''
            ? safeStr(t.nickname)
            : t?.mascot != null && String(t.mascot).trim() !== ''
              ? safeStr(t.mascot)
              : '—'
        const prestige = t?.prestige != null ? String(t.prestige) : '—'
        const teamPoints =
          tm.team_points != null && Number.isFinite(Number(tm.team_points))
            ? formatTeamPoints(Number(tm.team_points))
            : null
        const tpDelta = formatTeamPointsDelta(Number(tm.team_points_last_delta ?? 0))
        const community = t?.community_type != null ? safeStr(t.community_type) : '—'
        const enrollment = t?.enrollment != null ? String(t.enrollment) : '—'
        const classification = t?.classification != null ? safeStr(t.classification) : '—'
        const region =
          t?.region != null && String(t.region).trim() !== '' ? safeStr(t.region) : '—'
        const regionalTitles = String(histTotals?.regional_championships ?? tm.regional_championships ?? 0)
        const stateChampionshipYears = buildStateChampionshipYearsForTeam(leagueHistory, viewTeam, saveState)
        const persistedStateTitles = Math.max(
          0,
          Number(histTotals?.state_championships ?? (tm as { championships?: unknown }).championships ?? 0) || 0,
        )
        const stateTitlesDisplay =
          stateChampionshipYears.length > 0
            ? `${stateChampionshipYears.length} — ${stateChampionshipYears.join(', ')}`
            : persistedStateTitles > 0
              ? `${persistedStateTitles} (season years unavailable in archive)`
              : 'None'
        const fac = t?.facilities_grade != null ? String(t.facilities_grade).padStart(2, '0') : '00'
        const cul = t?.culture_grade != null ? String(t.culture_grade).padStart(2, '0') : '00'
        const boost = t?.booster_support != null ? String(t.booster_support).padStart(2, '0') : '00'
        const rankStr = tiRank != null ? String(tiRank) : '—'
        const classRankStr = tiClassRank != null ? `#${tiClassRank}` : '—'
        return (
          <div className="teamhome-roster-shell teamhome-teaminfo-shell">
            <div className="teamhome-teaminfo-header">
              <div className="teamhome-card-title" style={{ marginBottom: 0 }}>
                Team Info
              </div>
              <div className="teamhome-teaminfo-picker">
                <label className="teamhome-teaminfo-picker-label" htmlFor="teaminfo-team-select">
                  View team
                </label>
                <select
                  id="teaminfo-team-select"
                  className="teamhome-select teamhome-teaminfo-select"
                  value={viewTeam}
                  onChange={(e) => setTeamInfoTeam(e.target.value)}
                  disabled={allTeamNames.length < 1}
                >
                  {allTeamNames.length < 1 ? (
                    <option value="">—</option>
                  ) : (
                    allTeamNames.map((name) => (
                      <option key={name} value={name}>
                        {name}
                        {name === userTeam ? ' (you)' : ''}
                      </option>
                    ))
                  )}
                </select>
              </div>
            </div>
            <div className="teamhome-teaminfo-summary">
              <div className="teamhome-teaminfo-logo-wrap">
                <TeamLogo
                  apiBase={apiBase}
                  headers={headers}
                  teamName={viewTeam}
                  logoVersion={logoVersion}
                  size={112}
                  className="teamhome-teaminfo-biglogo"
                />
              </div>
              <div className="teamhome-teaminfo-summary-mid">
                <div>
                  <span className="teamhome-teaminfo-label">Team name</span>{' '}
                  <span className="teamhome-teaminfo-value">{viewTeam || '—'}</span>
                </div>
                <div>
                  <span className="teamhome-teaminfo-label">Nickname</span>{' '}
                  <span className="teamhome-teaminfo-value">{nickname}</span>
                </div>
                <div>
                  <span className="teamhome-teaminfo-label">Current record (standings)</span>{' '}
                  <span className="teamhome-teaminfo-value">{tiRecord}</span>
                </div>
                <div>
                  <span className="teamhome-teaminfo-label">Current rank (statewide)</span>{' '}
                  <span className="teamhome-teaminfo-value">{rankStr}</span>
                </div>
                <div>
                  <span className="teamhome-teaminfo-label">Class rank</span>{' '}
                  <span className="teamhome-teaminfo-value">
                    {classRankStr}
                    {tiClassRankGroup && tiClassRankGroup !== '—' ? (
                      <span className="teamhome-small" style={{ opacity: 0.85 }}>
                        {' '}
                        ({tiClassRankGroup})
                      </span>
                    ) : null}
                  </span>
                </div>
                <div>
                  <span className="teamhome-teaminfo-label">Head coach</span>{' '}
                  <span className="teamhome-teaminfo-value">
                    <CoachProfileName mode="team" teamName={viewTeam} coachName={coachName} as="span">
                      {coachName}
                    </CoachProfileName>
                  </span>
                </div>
              </div>
              <div className="teamhome-teaminfo-summary-right">
                <div>
                  <span className="teamhome-teaminfo-label">Program win–loss (all seasons + this year)</span>{' '}
                  <span className="teamhome-teaminfo-value">{programRecord}</span>
                </div>
                <div>
                  <span className="teamhome-teaminfo-label">Playoff appearances</span>{' '}
                  <span className="teamhome-teaminfo-value">{playoffAppearancesStr}</span>
                </div>
                <div>
                  <span className="teamhome-teaminfo-label">Regional titles</span>{' '}
                  <span className="teamhome-teaminfo-value">{regionalTitles}</span>
                </div>
                <div>
                  <span className="teamhome-teaminfo-label">State titles</span>{' '}
                  <span className="teamhome-teaminfo-value">{stateTitlesDisplay}</span>
                </div>
              </div>
            </div>
            <div className="teamhome-teaminfo-details">
              <div className="teamhome-teaminfo-details-col">
                <div>
                  <span className="teamhome-teaminfo-label">Prestige</span>{' '}
                  <span className="teamhome-teaminfo-value">
                    {prestige}
                    {teamPoints != null ? ` · ${teamPoints} TP` : ''}
                    {` · last Δ ${tpDelta}`}
                  </span>
                </div>
                <div>
                  <span className="teamhome-teaminfo-label">Community type</span>{' '}
                  <span className="teamhome-teaminfo-value">{community}</span>
                </div>
                <div>
                  <span className="teamhome-teaminfo-label">Enrollment</span>{' '}
                  <span className="teamhome-teaminfo-value">{enrollment}</span>
                </div>
              </div>
              <div className="teamhome-teaminfo-details-col">
                <div>
                  <span className="teamhome-teaminfo-label">Classification</span>{' '}
                  <span className="teamhome-teaminfo-value">{classification}</span>
                </div>
                <div>
                  <span className="teamhome-teaminfo-label">Region</span>{' '}
                  <span className="teamhome-teaminfo-value">{region}</span>
                </div>
              </div>
            </div>
            <div className="teamhome-teaminfo-grades">
              <div className="teamhome-teaminfo-grade-tile">
                <div className="teamhome-teaminfo-grade-icon" aria-hidden>
                  🏫
                </div>
                <div className="teamhome-teaminfo-grade-label">Facilities grade</div>
                <div className="teamhome-teaminfo-grade-num">{fac}</div>
              </div>
              <div className="teamhome-teaminfo-grade-tile">
                <div className="teamhome-teaminfo-grade-icon" aria-hidden>
                  🤝
                </div>
                <div className="teamhome-teaminfo-grade-label">Culture grade</div>
                <div className="teamhome-teaminfo-grade-num">{cul}</div>
              </div>
              <div className="teamhome-teaminfo-grade-tile">
                <div className="teamhome-teaminfo-grade-icon" aria-hidden>
                  💵
                </div>
                <div className="teamhome-teaminfo-grade-label">Booster support</div>
                <div className="teamhome-teaminfo-grade-num">{boost}</div>
              </div>
            </div>
            <div className="teamhome-teaminfo-stadium">
              <div className="teamhome-teaminfo-stadium-head">
                <span className="teamhome-teaminfo-stadium-title">Stadium</span>
                {!isLocalBundle && headers?.Authorization ? (
                  <div className="teamhome-teaminfo-stadium-actions">
                    <input
                      ref={stadiumFileInputRef}
                      type="file"
                      accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp"
                      className="teamhome-stadium-file-input"
                      aria-hidden
                      tabIndex={-1}
                      onChange={async (e) => {
                        const f = e.target.files?.[0]
                        e.target.value = ''
                        if (!f || !String(viewTeam || '').trim()) return
                        try {
                          const fd = new FormData()
                          fd.append('stadium', f)
                          const r = await fetch(`${apiBase}/saves/stadiums/${encodeURIComponent(viewTeam)}`, {
                            method: 'POST',
                            headers,
                            body: fd,
                          })
                          if (!r.ok) throw new Error((await r.text().catch(() => '')) || 'Upload failed')
                          setStadiumVersion(Date.now())
                          onError('')
                        } catch (err: unknown) {
                          onError(err instanceof Error ? err.message : 'Stadium upload failed')
                        }
                      }}
                    />
                    <button
                      type="button"
                      className="teamhome-action-btn-small"
                      disabled={!String(viewTeam || '').trim()}
                      onClick={() => stadiumFileInputRef.current?.click()}
                    >
                      Upload photo
                    </button>
                  </div>
                ) : null}
              </div>
              <TeamStadium
                apiBase={apiBase}
                headers={headers}
                teamName={viewTeam}
                stadiumVersion={stadiumVersion}
              />
              <p className="teamhome-teaminfo-stadium-hint">
                Optional home field or stadium shot (PNG, JPG, or WEBP). Shown for whichever school you select above;
                files are stored with your account like team logos.
              </p>
            </div>
            <div className="teamhome-teaminfo-banners">
              <div className="teamhome-teaminfo-banners-head">
                <span className="teamhome-teaminfo-banners-title">Banners</span>
              </div>
              {stateChampionshipYears.length > 0 ? (
                <ul className="teamhome-teaminfo-banners-list" aria-label="State championship banners">
                  {stateChampionshipYears.map((yr) => (
                    <li key={yr} className="teamhome-teaminfo-banner-chip">
                      State {yr}
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="teamhome-teaminfo-banners-placeholder">
                  State championship banners appear here when this program wins a title. Retired numbers and other
                  banners are coming later.
                </div>
              )}
            </div>
          </div>
        )
      })()
    ) : stateMenu === 'Coaching changes' ? (
      <div className="teamhome-roster-shell">
        <div className="teamhome-teaminfo-header">
          <div className="teamhome-card-title" style={{ marginBottom: 0 }}>
            Coaching changes
          </div>
          <div className="teamhome-teaminfo-picker">
            <label className="teamhome-teaminfo-picker-label" htmlFor="coaching-changes-year">
              Season year
            </label>
            <select
              id="coaching-changes-year"
              className="teamhome-select teamhome-teaminfo-select"
              value={coachingChangesYear === 'all' ? 'all' : String(coachingChangesYear)}
              onChange={(e) => {
                const v = e.target.value
                setCoachingChangesYear(v === 'all' ? 'all' : Number(v))
              }}
            >
              <option value="all">All years</option>
              {(() => {
                const histYears = ((saveState?.coaching_history ?? []) as { year?: number }[])
                  .map((h) => h.year)
                  .filter((y): y is number => typeof y === 'number')
                return Array.from(new Set(histYears))
                  .sort((a, b) => b - a)
                  .map((y) => (
                    <option key={y} value={String(y)}>
                      {y}
                    </option>
                  ))
              })()}
            </select>
          </div>
        </div>
        {(() => {
          const hist: {
            year?: number
            events?: any[]
            hot_seat_by_team?: Record<string, number>
            carousel_summary?: { headline?: string; bullets?: string[]; counts?: Record<string, number> }
          }[] = saveState?.coaching_history ?? []
          const liveCarousel = (saveState?.offseason_coach_carousel_last_events ?? []) as any[]
          const showLiveFeed =
            phase === 'offseason' && Array.isArray(liveCarousel) && liveCarousel.length > 0
          const filtered =
            coachingChangesYear === 'all'
              ? hist.slice().reverse()
              : hist.filter((h) => h?.year === coachingChangesYear).slice().reverse()
          if (filtered.length === 0 && !showLiveFeed) {
            return (
              <div className="teamhome-roster-empty">
                No archived coaching changes yet. During the offseason coaching carousel, moves stream on the Dashboard
                as you Continue; once you finish carousel stage III each year, full detail is archived here — see the summary
                headline on each Year card when present.
              </div>
            )
          }
          return (
            <div className="teamhome-roster-table" style={{ marginTop: 12 }}>
              {showLiveFeed ? (
                <div className="teamhome-coaching-live-block teamhome-coaching-carousel-marquee" style={{ marginBottom: 24 }}>
                  <div className="teamhome-card-title" style={{ fontSize: '1rem', marginBottom: 8 }}>
                    This offseason (latest moves)
                  </div>
                  <ul className="teamhome-coaching-events" style={{ textAlign: 'left', paddingLeft: 18, margin: 0 }}>
                    {liveCarousel.map((ev: any, i: number) => (
                      <li key={`live-cc-${i}`} style={{ marginBottom: 6 }}>
                        <span className="teamhome-small" style={{ opacity: 0.85 }}>
                          [{ev.type ?? '—'}]
                        </span>{' '}
                        {ev.detail ?? JSON.stringify(ev)}
                      </li>
                    ))}
                  </ul>
                  <div className="teamhome-small" style={{ marginTop: 10, opacity: 0.85 }}>
                    Press Continue on the dashboard to run the next carousel stage; archived seasons appear below when history exists.
                  </div>
                </div>
              ) : null}
              {filtered.map((entry) => (
                <div key={`cc-${entry.year}`} style={{ marginBottom: 20 }}>
                  <div className="teamhome-card-title" style={{ fontSize: '1rem', marginBottom: 8 }}>
                    Year {entry.year ?? '—'}
                  </div>
                  {entry.hot_seat_by_team && userTeam ? (
                    <div className="teamhome-small" style={{ marginBottom: 8 }}>
                      Your hot seat after that season:{' '}
                      <b>{entry.hot_seat_by_team[userTeam] ?? '—'}</b>
                    </div>
                  ) : null}
                  {entry.carousel_summary?.headline ? (
                    <div className="teamhome-small" style={{ marginBottom: 8, fontWeight: 700, opacity: 0.96 }}>
                      {entry.carousel_summary.headline}
                    </div>
                  ) : null}
                  {entry.carousel_summary?.bullets && entry.carousel_summary.bullets.length > 0 ? (
                    <>
                      <div className="teamhome-small" style={{ opacity: 0.88, marginBottom: 6 }}>
                        Season snapshot (movement highlights)
                      </div>
                      <ul className="teamhome-coaching-events" style={{ textAlign: 'left', paddingLeft: 18, margin: '0 0 12px' }}>
                        {(entry.carousel_summary.bullets ?? []).slice(-25).map((line: string, i: number) => (
                          <li key={`csum-${entry.year}-${i}`} style={{ marginBottom: 4 }}>
                            {line}
                          </li>
                        ))}
                      </ul>
                    </>
                  ) : null}
                  <div className="teamhome-small" style={{ opacity: 0.88, marginBottom: 6 }}>
                    Event log
                  </div>
                  <ul className="teamhome-coaching-events" style={{ textAlign: 'left', paddingLeft: 18, margin: 0 }}>
                    {(entry.events ?? []).slice(-30).map((ev: any, i: number) => (
                      <li key={`ev-${entry.year}-${i}`} style={{ marginBottom: 6 }}>
                        <span className="teamhome-small" style={{ opacity: 0.85 }}>
                          [{ev.type ?? '—'}]
                        </span>{' '}
                        {ev.detail ?? JSON.stringify(ev)}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          )
        })()}
      </div>
    ) : stateMenu === 'Team History' ? (
      <div className="teamhome-roster-shell">
        <div className="teamhome-teaminfo-header">
          <div className="teamhome-card-title" style={{ marginBottom: 0 }}>
            Team History
          </div>
          <div className="teamhome-small" style={{ marginTop: 8, marginBottom: 10, opacity: 0.88, maxWidth: 640, lineHeight: 1.45 }}>
            Rows list each completed year with record, postseason result, and head coach.{' '}
            <strong>Download</strong> opens a season archive (.txt): full schedule, team and top player stats, and end-of-season
            roster.
          </div>
          <div className="teamhome-teaminfo-picker">
            <label className="teamhome-teaminfo-picker-label" htmlFor="teamhistory-team-select">
              View team
            </label>
            <select
              id="teamhistory-team-select"
              className="teamhome-select teamhome-teaminfo-select"
              value={teamHistoryTeam || userTeam}
              onChange={(e) => setTeamHistoryTeam(e.target.value)}
              disabled={allTeamNames.length < 1}
            >
              {allTeamNames.length < 1 ? (
                <option value="">—</option>
              ) : (
                allTeamNames.map((name) => (
                  <option key={name} value={name}>
                    {name}
                    {name === userTeam ? ' (you)' : ''}
                  </option>
                ))
              )}
            </select>
          </div>
        </div>

        {teamHistoryTotals != null ? (
          <div className="teamhome-small" style={{ marginBottom: 12, opacity: 0.92, lineHeight: 1.5 }}>
            <strong>Career totals</strong> — Historical {teamHistoryTotals.program_wins}-
            {teamHistoryTotals.program_losses} · Regions {teamHistoryTotals.regional_championships}
            · States {teamHistoryTotals.state_championships} · Playoffs {teamHistoryTotals.playoff_appearances}
          </div>
        ) : null}

        {teamHistoryLoading ? (
          <div className="teamhome-roster-empty">Loading team history…</div>
        ) : teamHistoryRows.length === 0 ? (
          <div className="teamhome-roster-empty">
            No archived seasons for <strong>{teamHistoryTeam || userTeam || 'this team'}</strong> yet.
            {userTeam && (teamHistoryTeam || userTeam) !== userTeam ? (
              <>
                {' '}
                Try <strong>{userTeam}</strong> in View team — your program&apos;s recaps are stored per school.
              </>
            ) : (
              <>
                {' '}
                Finish playoffs and continue through <strong>season summary</strong> so the year is written to league
                history and recap files.
              </>
            )}
          </div>
        ) : (
          <div className="teamhome-team-history-scroll">
            <div className="teamhome-roster-head teamhome-roster-row teamhome-team-history-row">
              <div className="teamhome-roster-cell">Year</div>
              <div className="teamhome-roster-cell">Team</div>
              <div className="teamhome-roster-cell">W-L</div>
              <div className="teamhome-roster-cell">Postseason</div>
              <div className="teamhome-roster-cell">Coach</div>
              <div className="teamhome-roster-cell teamhome-team-history-cell-recap">Recap</div>
            </div>
            <div className="teamhome-roster-table">
              {teamHistoryRows.map((r: any) => {
                const teamPick = (teamHistoryTeam || userTeam).trim()
                const recapReady = teamHistoryRecapAvailable(r, teamPick)
                return (
                  <div key={`th-${r.year}`} className="teamhome-roster-row teamhome-team-history-row">
                    <div className="teamhome-roster-cell">{r.year ?? '—'}</div>
                    <div className="teamhome-roster-cell teamhome-team-history-cell-team">
                      {teamWithLogo(teamPick, 22)}
                    </div>
                    <div className="teamhome-roster-cell">
                      {typeof r.wins === 'number' && typeof r.losses === 'number' ? `${r.wins}-${r.losses}` : '—'}
                    </div>
                    <div className="teamhome-roster-cell">{r.postseason ?? '—'}</div>
                    <div className="teamhome-roster-cell">
                      <CoachProfileName mode="by-name" coachName={r.coach} as="span" />
                    </div>
                    <div className="teamhome-roster-cell teamhome-team-history-cell-recap">
                      {recapReady ? (
                        <button
                          type="button"
                          className="teamhome-schedule-link"
                          onClick={() => downloadTeamRecap(teamPick, r.year ?? '')}
                        >
                          Download
                        </button>
                      ) : (
                        <span className="teamhome-small" style={{ opacity: 0.45 }}>
                          —
                        </span>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>

    ) : stateMenu === 'Prestige report' ? (
      <div className="teamhome-roster-shell">
        <div className="teamhome-teaminfo-header">
          <div className="teamhome-card-title" style={{ marginBottom: 0 }}>
            Prestige report
          </div>
          <p className="teamhome-small" style={{ marginTop: 8, marginBottom: 12, opacity: 0.88, maxWidth: 720, lineHeight: 1.45 }}>
            Team Points update when a season is archived at the end of playoffs (season summary), not during Graduation
            or other offseason stages. The star rating only changes when TP crosses a band. Last Δ is the most recent TP
            change (season results, plus any coaching-carousel adjustment at the end of carousel stage III).
          </p>
        </div>
        <div className="teamhome-roster-head teamhome-roster-row">
          <div className="teamhome-roster-cell">Team</div>
          <div className="teamhome-roster-cell">★</div>
          <div className="teamhome-roster-cell">Team points</div>
          <div className="teamhome-roster-cell">Band</div>
          <div className="teamhome-roster-cell">Last Δ</div>
        </div>
        <div className="teamhome-roster-table">
          {prestigeReportRows.map((r) => (
            <div
              key={r.team}
              className={`teamhome-roster-row${r.team === userTeam ? ' teamhome-roster-row--highlight' : ''}`}
            >
              <div className="teamhome-roster-cell">{r.team}</div>
              <div className="teamhome-roster-cell">{r.prestige}</div>
              <div className="teamhome-roster-cell">{formatTeamPoints(r.teamPoints)}</div>
              <div className="teamhome-roster-cell">{prestigeBandLabel(r.prestige)}</div>
              <div className="teamhome-roster-cell">{formatTeamPointsDelta(r.lastDelta)}</div>
            </div>
          ))}
        </div>
      </div>
    ) : stateMenu === 'League History' ? (
      <div className="teamhome-roster-shell teamhome-league-history-root">
        <div className="teamhome-teaminfo-header">
          <div className="teamhome-card-title" style={{ marginBottom: 0 }}>
            League History
          </div>
          <div className="teamhome-teaminfo-picker">
            <label className="teamhome-teaminfo-picker-label" htmlFor="league-history-year-select">
              Season year
            </label>
            <select
              id="league-history-year-select"
              className="teamhome-select teamhome-teaminfo-select"
              value={leagueHistEffectiveMode === 'live' ? 'live' : String(leagueHistEffectiveMode)}
              onChange={(e) => {
                const v = e.target.value
                setLeagueHistYearPick(v === 'live' ? 'live' : Number(v))
              }}
              aria-label="League history season year"
              disabled={
                lhYearDropdownOptions.archivedYears.length < 1 && !lhYearDropdownOptions.showLive
              }
            >
              {lhYearDropdownOptions.showLive ? (
                <option value="live">{lhYearDropdownOptions.currentYear} (season in progress)</option>
              ) : null}
              {lhYearDropdownOptions.archivedYears.map((y) => (
                <option key={y} value={String(y)}>
                  {y}
                </option>
              ))}
            </select>
          </div>
        </div>

        {lhYearDropdownOptions.archivedYears.length < 1 && !lhYearDropdownOptions.showLive ? (
          <div className="teamhome-roster-empty">
            No league history yet — finish at least one full season (through playoffs and advance to offseason) to archive
            standings and brackets here.
          </div>
        ) : leagueHistEffectiveMode !== 'live' && !lhArchivedSeasonEntry ? (
          <div className="teamhome-roster-empty">No archived data for this year.</div>
        ) : (
          <>
            {leagueHistEffectiveMode === 'live' ? (
              <div className="teamhome-small" style={{ marginBottom: 12, opacity: 0.92, lineHeight: 1.45 }}>
                <strong>Season in progress</strong> — rankings use the live standings sheet. Playoff brackets mirror the STATE
                playoff brackets (including multiclass leagues). Everything here is finalized in history when you complete
                playoffs and tap <em>Finish season</em> (or Continue when the bracket is complete).
              </div>
            ) : (
              <div className="teamhome-small" style={{ marginBottom: 14, opacity: 0.92, lineHeight: 1.45 }}>
                <strong>State champion</strong>: {String(lhArchivedSeasonEntry?.state_champion ?? '—')} ·{' '}
                <strong>Runner-up</strong>: {String(lhArchivedSeasonEntry?.runner_up ?? '—')}
              </div>
            )}

            {leagueHistEffectiveMode !== 'live' && lhArchivedSeasonEntry && lhRecapArchiveYear != null ? (
              <div className="teamhome-league-history-recap-bar">
                <label className="teamhome-teaminfo-picker-label" htmlFor="league-history-recap-team">
                  Team season recap (.txt)
                </label>
                <select
                  id="league-history-recap-team"
                  className="teamhome-select teamhome-teaminfo-select"
                  value={leagueHistRecapTeam || userTeam}
                  onChange={(e) => setLeagueHistRecapTeam(e.target.value)}
                >
                  {lhRecapTeamNames.map((name) => (
                    <option key={name} value={name}>
                      {name}
                      {name === userTeam ? ' (you)' : ''}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  className="teamhome-schedule-link"
                  disabled={!lhRecapCanDownload}
                  onClick={() =>
                    downloadTeamRecap(leagueHistRecapTeam || userTeam, lhRecapArchiveYear)
                  }
                >
                  Download recap
                </button>
                <span className="teamhome-small teamhome-league-history-recap-hint">
                  Full schedule, team and player stats, postseason lines, and end-of-season roster for the selected year.
                </span>
              </div>
            ) : null}

            <div className="teamhome-card-title teamhome-league-history-section-head">Rankings · all classes</div>
            <p className="teamhome-small" style={{ opacity: 0.85, marginTop: -4 }}>
              Uses each team&apos;s classification on your current save rosters — same cutoff logic as Rankings elsewhere.
              Composite sort: wins / point differential / scoring.
            </p>
            <div className="teamhome-league-history-classes">
              {uniqueClassifications(saveState).map((cls) => {
                const rows = buildRankingsRows(lhRankingsFakeState, cls)
                if (rows.length === 0) return null
                const cap = rows.slice(0, 24)
                return (
                  <div key={`lh-rank-${cls}`} className="teamhome-card teamhome-league-history-class-card">
                    <div className="teamhome-card-title" style={{ fontSize: '0.92rem', marginBottom: 8 }}>
                      {cls}{rows.length > cap.length ? ` (top ${cap.length})` : ''}
                    </div>
                    <div className="teamhome-roster-head teamhome-rankings-row teamhome-league-history-rank-head">
                      <div className="teamhome-roster-cell">Rk</div>
                      <div className="teamhome-roster-name">Team</div>
                      <div className="teamhome-roster-cell">WL</div>
                      <div className="teamhome-roster-cell">PF</div>
                      <div className="teamhome-roster-cell">Diff</div>
                    </div>
                    <div className="teamhome-roster-table teamhome-league-history-rank-table">
                      {cap.map((r: { rank?: number; teamName?: string; wins?: number; losses?: number; pointsFor?: number; diff?: number }) => (
                        <div key={`lh-${cls}-${r.teamName}`} className="teamhome-rankings-row">
                          <div className="teamhome-roster-cell">{r.rank}</div>
                          <div className="teamhome-roster-name">{teamWithLogo(String(r.teamName ?? ''), 20)}</div>
                          <div className="teamhome-roster-cell">
                            {(r.wins ?? 0) as number}-{(r.losses ?? 0) as number}
                          </div>
                          <div className="teamhome-roster-cell">{r.pointsFor}</div>
                          <div className="teamhome-roster-cell">{Number(r.diff) >= 0 ? `+${r.diff}` : r.diff}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>

            <div className="teamhome-card-title teamhome-league-history-section-head" style={{ marginTop: 20 }}>
              Playoffs · condensed brackets
            </div>
            {Object.keys(lhPlayoffsByClass).length < 1 ? (
              <div className="teamhome-roster-empty">
                No playoff brackets for this year yet
                {leagueHistEffectiveMode === 'live' && phase === 'regular'
                  ? ' (playoffs begin after the regular season).'
                  : '.'}
              </div>
            ) : (
              <div className="teamhome-league-history-playoffs-wrap">
                {Object.entries(lhPlayoffsByClass)
                  .sort(([a], [b]) => a.localeCompare(b))
                  .map(([clsName, pdata]) => {
                    const inner = pdata as Record<string, unknown>
                    const gamesRaw = inner?.bracket_results
                    const games = Array.isArray(gamesRaw) ? (gamesRaw as Record<string, unknown>[]) : []
                    const seeds = Array.isArray(inner?.seeds) ? (inner.seeds as { seed?: number; team?: string }[]) : []
                    const qfGames = games.filter((g) => String(g.round) === 'Quarterfinal')
                    const sfGames = games.filter((g) => String(g.round) === 'Semifinal')
                    const chGames = games.filter((g) => String(g.round) === 'Championship')
                    const seedForTeam = (name: string): number | null => {
                      const row = seeds.find((s) => String(s.team) === name)
                      const sn = Number(row?.seed)
                      return Number.isFinite(sn) && sn > 0 ? sn : null
                    }

                    let qfDisplay
                    const useSeedsShell = seeds.length >= 8
                    if (useSeedsShell && qfGames.length < 4) {
                      const sn = (n: number) => seeds.find((s) => Number(s.seed) === n)?.team ?? `Seed ${n}`
                      const pairs = [
                        { home: sn(1), away: sn(8) },
                        { home: sn(2), away: sn(7) },
                        { home: sn(3), away: sn(6) },
                        { home: sn(4), away: sn(5) },
                      ]
                      qfDisplay = pairs.map((m) => {
                        const played =
                          qfGames.find((g) => (g.home === m.home && g.away === m.away) || (g.home === m.away && g.away === m.home)) ?? null
                        const ph = played
                          ? played.home === m.home
                            ? played.home_score
                            : played.away_score
                          : null
                        const pa = played
                          ? played.home === m.home
                            ? played.away_score
                            : played.home_score
                          : null
                        return (
                          <div key={`lh-qf-${clsName}-${m.home}-${m.away}`} className="teamhome-playoffs-matchup">
                            {renderPlayoffBracketLine(String(m.home), typeof ph === 'number' ? ph : undefined, {
                              playoffSeed: seedForTeam(m.home),
                            })}
                            {renderPlayoffBracketLine(String(m.away), typeof pa === 'number' ? pa : undefined, {
                              playoffSeed: seedForTeam(m.away),
                            })}
                          </div>
                        )
                      })
                    } else if (qfGames.length > 0) {
                      qfDisplay = qfGames.map((g) => (
                        <div key={`lh-qfc-${clsName}-${g.home}-${g.away}`} className="teamhome-playoffs-matchup">
                          {renderPlayoffBracketLine(String(g.home), Number(g.home_score), {
                            playoffSeed: seedForTeam(String(g.home)),
                          })}
                          {renderPlayoffBracketLine(String(g.away), Number(g.away_score), {
                            playoffSeed: seedForTeam(String(g.away)),
                          })}
                        </div>
                      ))
                    } else {
                      qfDisplay = (
                        <div className="teamhome-small">Quarterfinal games not archived for this bracket.</div>
                      )
                    }

                    return (
                      <div key={`lh-po-${clsName}`} className="teamhome-card teamhome-league-history-class-card">
                        <div className="teamhome-card-title" style={{ fontSize: '0.95rem', marginBottom: 8 }}>
                          {clsName}
                          {inner.completed !== true ? ' · bracket in progress' : ''}
                          {typeof inner.champion === 'string' && inner.champion ? (
                            <span className="teamhome-small teamhome-league-history-champ-pill">{` Champion: ${inner.champion}`}</span>
                          ) : null}
                        </div>
                        <div className="teamhome-playoffs-grid teamhome-league-history-playoffs-grid">
                          <div className="teamhome-playoffs-microcol">
                            <div className="teamhome-microcol-title">QF</div>
                            <div className="teamhome-playoffs-list">{qfDisplay}</div>
                          </div>
                          <div className="teamhome-playoffs-microcol">
                            <div className="teamhome-microcol-title">SF</div>
                            <div className="teamhome-playoffs-list">
                              {sfGames.length === 0 && useSeedsShell ? (
                                <div className="teamhome-small" style={{ opacity: 0.8 }}>
                                  (Semifinal matchups populate after quarterfinal results.)
                                </div>
                              ) : (
                                sfGames.map((g) => (
                                  <div key={`lh-sf-${clsName}-${g.home}-${g.away}`} className="teamhome-playoffs-matchup">
                                    {renderPlayoffBracketLine(String(g.home), Number(g.home_score), {
                                      playoffSeed: seedForTeam(String(g.home)),
                                    })}
                                    {renderPlayoffBracketLine(String(g.away), Number(g.away_score), {
                                      playoffSeed: seedForTeam(String(g.away)),
                                    })}
                                  </div>
                                ))
                              )}
                            </div>
                          </div>
                          <div className="teamhome-playoffs-microcol">
                            <div className="teamhome-microcol-title">Final</div>
                            <div className="teamhome-playoffs-list">
                              {chGames.length === 0 ? (
                                <div className="teamhome-small" style={{ opacity: 0.8 }}>
                                  {(inner.completed === false ? 'Championship pending.' : '')}
                                </div>
                              ) : (
                                chGames.map((g) => (
                                  <div key={`lh-ch-${clsName}-${g.home}-${g.away}`} className="teamhome-playoffs-matchup">
                                    {renderPlayoffBracketLine(String(g.home), Number(g.home_score), {
                                      playoffSeed: seedForTeam(String(g.home)),
                                    })}
                                    {renderPlayoffBracketLine(String(g.away), Number(g.away_score), {
                                      playoffSeed: seedForTeam(String(g.away)),
                                    })}
                                  </div>
                                ))
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    )
                  })}
              </div>
            )}
          </>
        )}
      </div>
    ) : null

  const userTeamObj = useMemo(() => findTeam(saveState, userTeam), [saveState, userTeam])
  const userNickname = useMemo(() => {
    const raw = userTeamObj?.nickname ?? userTeamObj?.mascot
    const s = raw != null ? String(raw).trim() : ''
    return s || '—'
  }, [userTeamObj])
  const coach = userTeamObj?.coach ?? null
  const offensePlan = coach
    ? `Offense: ${safeStr(coach.offensive_style)} · ${safeStr(coach.offensive_formation)}`
    : 'Offense: (not set yet)'
  const defensePlan = coach
    ? `Defense: ${safeStr(coach.defensive_style)} · ${safeStr(coach.defensive_formation)}`
    : 'Defense: (not set yet)'

  const nextOpponentText =
    phase === 'regular'
      ? nextOpponent || '—'
      : phase === 'playoffs'
        ? playoffNextOpp
        : phase === 'season_summary'
          ? 'Season complete'
          : phase === 'offseason'
            ? '—'
            : 'OffSeason'
  const currentWeek = Number(saveState?.current_week ?? 1)
  const hasUnplayedGameThisWeek = useMemo(() => {
    if (phase !== 'regular') return false
    const row = scheduleRows.find((r) => r.week === currentWeek)
    return row ? !row.played : false
  }, [phase, scheduleRows, currentWeek])
  const preseasonStages = (saveState?.preseason_stages ?? []) as string[]
  const preseasonStageIndex = Number(saveState?.preseason_stage_index ?? 0)
  const preseasonCurrentStage =
    phase === 'preseason' ? preseasonStages[preseasonStageIndex] ?? 'Preseason Complete' : ''
  const preseasonStageNumber = phase === 'preseason' ? Math.min(preseasonStageIndex + 1, preseasonStages.length) : 0
  const offseasonResolved = useMemo(
    () => resolveOffseasonStagesFromSave(saveState),
    [saveState?.offseason_stages, saveState?.offseason_stage_index],
  )
  const offseasonStages = offseasonResolved.stages
  const offseasonStageIndex = offseasonResolved.stageIndex
  const offseasonCurrentStage = phase === 'offseason' ? offseasonResolved.currentStage : ''
  const offseasonNextStageLabel = useMemo(() => {
    if (phase !== 'offseason' || !offseasonStages.length) return ''
    const i = offseasonStageIndex
    if (i < 0 || i >= offseasonStages.length) return '—'
    if (i < offseasonStages.length - 1) {
      return displayOffseasonStageLabel(offseasonStages[i + 1] ?? '')
    }
    return 'Preseason'
  }, [phase, offseasonStages, offseasonStageIndex])
  const lastOpponentText =
    phase === 'playoffs'
      ? playoffLast
      : last
        ? `${last.outcome}${last.ot ? ' (OT)' : ''} vs ${last.opponent} · ${last.userScore}-${last.oppScore}`
        : '—'

  const continueStyle: CSSProperties = rank === 1 ? { border: '2px solid rgba(125, 211, 252, 0.9)' } : {}

  const playoffsComplete = phase === 'playoffs' && Boolean(saveState?.playoffs?.completed)
  const canContinue = Boolean(saveId && saveState?.user_team)
  const isPlaybookSelectStage = phase === 'preseason' && preseasonCurrentStage === 'Playbook Select'
  /** Same calendar-year rule as backend: offensive/defensive playbook labels at most once every 5 seasons. */
  const PREFERRED_PLAYBOOK_LOCK_SEASONS = 5
  const currentSeasonYear = Math.max(1, Number(saveState?.current_year ?? 1))
  const userCoachPbYear = Number(findTeam(saveState, userTeam)?.coach?.last_preferred_playbook_change_year ?? 0)
  const canChangePreferredPlaybooks =
    userCoachPbYear <= 0 || currentSeasonYear >= userCoachPbYear + PREFERRED_PLAYBOOK_LOCK_SEASONS
  const nextPreferredPlaybookEligibleYear =
    userCoachPbYear <= 0 ? null : userCoachPbYear + PREFERRED_PLAYBOOK_LOCK_SEASONS
  const isPlaySelectionStage = phase === 'preseason' && preseasonCurrentStage === 'Play Selection'
  const isPlaySelectionResultsStage =
    phase === 'preseason' && preseasonCurrentStage === 'Play Selection Results'
  const isPositionChangesStage = phase === 'preseason' && preseasonCurrentStage === 'Position changes'
  const isSetDepthChartStage = phase === 'preseason' && preseasonCurrentStage === 'Set Depth Chart'
  const isScrimmageStage = phase === 'preseason' && (preseasonCurrentStage === 'Scrimmage 1' || preseasonCurrentStage === 'Scrimmage 2')
  const isSetGoalsStage = phase === 'preseason' && preseasonCurrentStage === 'Set Goals'
  const isCoachingCarouselApplyStage =
    phase === 'offseason' &&
    (offseasonCurrentStage === 'Coaching carousel I' ||
      offseasonCurrentStage === 'Coaching carousel II' ||
      offseasonCurrentStage === 'Coaching carousel III')
  const isCoachingCarouselSummaryStage = phase === 'offseason' && offseasonCurrentStage === 'Coaching carousel IV'
  const isCoachingCarouselStage = isCoachingCarouselApplyStage || isCoachingCarouselSummaryStage
  useEffect(() => {
    if (!isCoachingCarouselStage) setCarouselHotSeatTeamFilter('')
  }, [isCoachingCarouselStage])
  useEffect(() => {
    if (!isCoachingCarouselApplyStage) return
    const raw = saveState?.offseason_carousel_job_applications
    const next =
      Array.isArray(raw) ? raw.map((x: unknown) => String(x ?? '').trim()).filter(Boolean) : []
    setCarouselJobApplications(next)
  }, [
    isCoachingCarouselApplyStage,
    offseasonCurrentStage,
    saveState?.offseason_carousel_job_applications,
  ])
  const [confirmingPlaybook, setConfirmingPlaybook] = useState(false)
  const [showPlaybookGamePlan, setShowPlaybookGamePlan] = useState(false)
  const [learningSummary, setLearningSummary] = useState<{
    offensive_pct_learned: number
    defensive_pct_learned: number
    overall_grade: string | null
  } | null>(null)
  const [learningLoading, setLearningLoading] = useState(false)
  const [confirmingResults, setConfirmingResults] = useState(false)
  const [positionDraft, setPositionDraft] = useState<Record<string, { position: string; secondary: string }>>({})
  const STAGE_GOAL_OPTIONS = ['Winning Season', 'Playoffs', 'Semifinal', 'State Championship', 'Title Winner']
  const seasonGoals = saveState?.season_goals
  const existingWinGoal = typeof seasonGoals?.win_goal === 'number' ? seasonGoals.win_goal : 6
  const existingStageGoal = typeof seasonGoals?.stage_goal === 'string' ? seasonGoals.stage_goal : 'Winning Season'
  const [goalWinTotal, setGoalWinTotal] = useState<number>(existingWinGoal)
  const [goalStage, setGoalStage] = useState<string>(existingStageGoal)
  const [confirmingGoals, setConfirmingGoals] = useState(false)
  const [playingWeek, setPlayingWeek] = useState(false)
  const [simmingWeek, setSimmingWeek] = useState(false)
  const [simMultipleCount, setSimMultipleCount] = useState(0)
  const [winterStrengthPct, setWinterStrengthPct] = useState(50)
  const [winterTrainingAllocations, setWinterTrainingAllocations] = useState<Record<string, number>>(() => defaultWinterAllocations())
  const [springOffense, setSpringOffense] = useState('run_game')
  const [springDefense, setSpringDefense] = useState('pass_defense')
  const [improveFacCumulative, setImproveFacCumulative] = useState(0)
  const [improveCulCumulative, setImproveCulCumulative] = useState(0)
  const [improveBooCumulative, setImproveBooCumulative] = useState(0)
  const [coachDevAllocations, setCoachDevAllocations] = useState<Record<string, number>>(() => emptyCoachDevAllocations())
  const [offseasonTrainingSort, setOffseasonTrainingSort] = useState<OffseasonTrainingSortMode>('position')
  const [freshmanSort, setFreshmanSort] = useState<FreshmanSortMode>('position')
  const [activeGame, setActiveGame] = useState<{
    gameId: string
    homeTeam: string
    awayTeam: string
    userTeam: string
    initialState: any
    gameContext: 'scrimmage' | 'week' | 'playoff'
    scrimmageStage?: string
  } | null>(null)
  useEffect(() => {
    if (isSetGoalsStage) {
      setGoalWinTotal(existingWinGoal)
      setGoalStage(existingStageGoal)
    }
  }, [isSetGoalsStage, existingWinGoal, existingStageGoal])
  useEffect(() => {
    if (!isPositionChangesStage || !userTeam) return
    const t = findTeam(saveState, userTeam)
    const roster = t?.roster ?? []
    const next: Record<string, { position: string; secondary: string }> = {}
    for (const p of roster) {
      next[p.name] = {
        position: String(p.position || 'WR'),
        secondary: p.secondary_position ? String(p.secondary_position) : '',
      }
    }
    setPositionDraft(next)
  }, [isPositionChangesStage, saveState, userTeam])
  useEffect(() => {
    if (phase !== 'offseason' || !coach) return
    const st = offseasonCurrentStage
    if (st === 'Winter 1' || st === 'Winter 2') {
      const legacy = Number(coach.winter_strength_pct ?? 50)
      setWinterStrengthPct(legacy)
      const speed = 100 - legacy
      setWinterTrainingAllocations({
        squat: Math.round(legacy * 0.35),
        bench: Math.round(legacy * 0.25),
        cleans: Math.round(speed * 0.3),
        cod: Math.round(speed * 0.2),
        speed: Math.round(speed * 0.25),
        plyometrics: Math.round(speed * 0.15),
        football_iq: 0,
      })
    }
    if (st === 'Spring Ball') {
      setSpringOffense(String(coach.spring_offense_focus ?? 'run_game'))
      setSpringDefense(String(coach.spring_defense_focus ?? 'pass_defense'))
    }
  }, [phase, offseasonCurrentStage, coach])

  useEffect(() => {
    if (phase !== 'offseason' || offseasonCurrentStage !== 'Improvements') return
    const t = findTeam(saveState, userTeam)
    setImproveFacCumulative(pillarCumulativePpValue(Number(t?.facilities_grade ?? 5), Number(t?.facilities_progress_pts ?? 0)))
    setImproveCulCumulative(pillarCumulativePpValue(Number(t?.culture_grade ?? 5), Number(t?.culture_progress_pts ?? 0)))
    setImproveBooCumulative(pillarCumulativePpValue(Number(t?.booster_support ?? 5), Number(t?.boosters_progress_pts ?? 0)))
  }, [phase, offseasonCurrentStage, saveState, userTeam])

  useEffect(() => {
    if (phase !== 'offseason' || offseasonCurrentStage !== 'Coach development') return
    const bank = saveState?.offseason_coach_dev_bank
    const src = bank?.allocations
    if (src && typeof src === 'object') {
      setCoachDevAllocations(
        Object.fromEntries(COACH_DEV_SKILLS.map(({ key }) => [key, Math.max(0, Number(src?.[key] ?? 0))])) as Record<string, number>,
      )
      return
    }
    const coachObj = findTeam(saveState, userTeam)?.coach ?? {}
    setCoachDevAllocations(
      Object.fromEntries(
        COACH_DEV_SKILLS.map(({ key }) => {
          const lv = Math.max(1, Math.min(10, Number(coachObj?.[key] ?? 5)))
          return [key, COACH_DEV_THRESHOLDS[lv] ?? 0]
        }),
      ) as Record<string, number>,
    )
  }, [phase, offseasonCurrentStage, saveState, userTeam])

  const coachDevTotalCp = Number(saveState?.offseason_coach_dev_bank?.cp_total ?? 0)
  const coachDevAllocatedCp = COACH_DEV_SKILLS.reduce((sum, { key }) => sum + Number(coachDevAllocations[key] ?? 0), 0)
  const coachDevAvailableCp = coachDevTotalCp - coachDevAllocatedCp
  const springBallResult = saveState?.offseason_spring_ball_results?.user_team_result ?? null
  const winterTrainingResult = saveState?.offseason_winter_training_results?.user_team_result ?? null
  const transferStage1 = saveState?.offseason_transfer_stage_1 ?? null
  const transferStage2 = saveState?.offseason_transfer_stage_2 ?? null
  const transferReview = saveState?.offseason_transfer_review ?? null
  const transferStage1PendingReview = Boolean(saveState?.offseason_transfer_stage_1_pending_review)
  const transferStage2PendingReview = Boolean(saveState?.offseason_transfer_stage_2_pending_review)
  const transferStage1EntriesSorted = useMemo(() => {
    const raw = saveState?.offseason_transfer_stage_1?.entries
    const e = (Array.isArray(raw) ? raw : []) as Array<Record<string, unknown>>
    return [...e].sort((a, b) => {
      const sa = String(a.from_team ?? a.team ?? '')
      const sb = String(b.from_team ?? b.team ?? '')
      const bySchool = sa.localeCompare(sb)
      if (bySchool !== 0) return bySchool
      return String(a.player ?? '').localeCompare(String(b.player ?? ''))
    })
  }, [saveState?.offseason_transfer_stage_1])
  const winterPointsUsed = WINTER_TRAINING_CATEGORIES.reduce((sum, c) => sum + Math.max(0, Number(winterTrainingAllocations[c.key] ?? 0)), 0)
  const winterPointsRemaining = 100 - winterPointsUsed
  const winterAllocationInvalid =
    phase === 'offseason' &&
    (offseasonCurrentStage === 'Winter 1' || offseasonCurrentStage === 'Winter 2') &&
    !winterTrainingResult &&
    winterPointsRemaining !== 0

  const improvementsSeasonLedger = useMemo(() => {
    if (phase !== 'offseason' || offseasonCurrentStage !== 'Improvements') return null
    const raw = saveState?.offseason_improvements_bank?.breakdown
    if (!raw || typeof raw !== 'object') return null
    const snap = saveState?.last_completed_standings?.[userTeam]
    const wins =
      snap != null
        ? Number(snap.wins ?? 0)
        : Number((raw as { wins?: number }).wins ?? saveState?.standings?.[userTeam]?.wins ?? 0)
    const losses =
      snap != null
        ? Number(snap.losses ?? 0)
        : Number((raw as { losses?: number }).losses ?? saveState?.standings?.[userTeam]?.losses ?? 0)
    const rs = Number((raw as { regular_season_pp?: number }).regular_season_pp ?? (raw as { wl_points?: number }).wl_points ?? 0)
    const playoffWinPp = Number((raw as { playoff_win_pp_total?: number }).playoff_win_pp_total ?? 0)
    const placementPp = Number((raw as { placement_bonus_pp?: number }).placement_bonus_pp ?? 0)
    const placementLabel = String((raw as { placement_bonus_label?: string }).placement_bonus_label ?? '').trim() || 'Placement bonus'
    const goalPts = Number((raw as { goal_points?: number }).goal_points ?? 0)
    const goalFails = Number((raw as { goal_fail_count?: number }).goal_fail_count ?? 0)
    const goalMetCount = Number((raw as { goal_met_count?: number }).goal_met_count ?? 0)
    const net = Number((raw as { pp_total?: number }).pp_total ?? 0)
    return {
      rs,
      playoffWinPp,
      placementPp,
      placementLabel,
      goalPts,
      net,
      wins,
      losses,
      goalFails,
      goalMetCount,
    }
  }, [phase, offseasonCurrentStage, saveState?.offseason_improvements_bank, saveState, userTeam])

  const improvementsBudget = useMemo(() => {
    const emptyPillars: Array<{
      id: string
      label: string
      accent: string
      fromCumulative: number
      targetCumulative: number
      pillarDeltaPp: number
    }> = []
    if (phase !== 'offseason' || offseasonCurrentStage !== 'Improvements') {
      return {
        invalid: false,
        projectedRemaining: 0,
        shortfall: 0,
        deltaPp: 0,
        ppRemaining: 0,
        ppTotal: 0,
        pillars: emptyPillars,
      }
    }
    const bank = saveState?.offseason_improvements_bank
    const ppRemaining = Number(bank?.pp_remaining ?? bank?.pp_total ?? 0)
    const ppTotal = Number(bank?.pp_total ?? 0)
    const t = findTeam(saveState, userTeam)
    const facFrom = clampImprovementLevel(Number(t?.facilities_grade ?? 5), 5)
    const culFrom = clampImprovementLevel(Number(t?.culture_grade ?? 5), 5)
    const booFrom = clampImprovementLevel(Number(t?.booster_support ?? 5), 5)
    const facPtsFrom = Math.max(0, Math.min(3500, Math.floor(Number(t?.facilities_progress_pts ?? 0))))
    const culPtsFrom = Math.max(0, Math.min(3500, Math.floor(Number(t?.culture_progress_pts ?? 0))))
    const booPtsFrom = Math.max(0, Math.min(3500, Math.floor(Number(t?.boosters_progress_pts ?? 0))))
    const vFacFrom = pillarCumulativePpValue(facFrom, facPtsFrom)
    const vCulFrom = pillarCumulativePpValue(culFrom, culPtsFrom)
    const vBooFrom = pillarCumulativePpValue(booFrom, booPtsFrom)
    const facD = vFacFrom - improveFacCumulative
    const culD = vCulFrom - improveCulCumulative
    const booD = vBooFrom - improveBooCumulative
    const deltaPp = facD + culD + booD
    const projectedRemaining = ppRemaining + deltaPp
    const invalid = projectedRemaining < 0
    const shortfall = invalid ? Math.max(0, Math.ceil(-projectedRemaining)) : 0
    const pillars = [
      {
        id: 'facilities',
        label: 'Facilities',
        accent: '#38bdf8',
        fromCumulative: vFacFrom,
        targetCumulative: improveFacCumulative,
        pillarDeltaPp: facD,
      },
      {
        id: 'culture',
        label: 'Culture',
        accent: '#c084fc',
        fromCumulative: vCulFrom,
        targetCumulative: improveCulCumulative,
        pillarDeltaPp: culD,
      },
      {
        id: 'boosters',
        label: 'Booster support',
        accent: '#fbbf24',
        fromCumulative: vBooFrom,
        targetCumulative: improveBooCumulative,
        pillarDeltaPp: booD,
      },
    ]
    return { invalid, projectedRemaining, shortfall, deltaPp, ppRemaining, ppTotal, pillars }
  }, [
    phase,
    offseasonCurrentStage,
    saveState?.offseason_improvements_bank,
    saveState,
    userTeam,
    improveFacCumulative,
    improveCulCumulative,
    improveBooCumulative,
  ])

  const offseasonTrainingRowsRaw = useMemo(
    () => (saveState?.offseason_training_results?.players ?? []) as OffseasonTrainingRow[],
    [saveState?.offseason_training_results],
  )
  const sortedOffseasonTrainingRows = useMemo(
    () => sortOffseasonTrainingRows(offseasonTrainingRowsRaw, offseasonTrainingSort),
    [offseasonTrainingRowsRaw, offseasonTrainingSort],
  )
  const freshmanRosterPlayers = useMemo(() => {
    const team = findTeam(saveState, userTeam)
    return (team?.roster ?? []).filter((p: any) => isFreshmanYear(p?.year))
  }, [saveState, userTeam])
  const sortedFreshmanRosterPlayers = useMemo(
    () => sortFreshmanRosterPlayers(freshmanRosterPlayers, freshmanSort),
    [freshmanRosterPlayers, freshmanSort],
  )

  useEffect(() => {
    if (!isPlaySelectionResultsStage || !saveId) {
      setLearningSummary(null)
      return
    }
    let cancelled = false
    setLearningLoading(true)
    fetch(`${apiBase}/saves/${saveId}/play-learning-summary`, { headers })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error('Failed to load learning summary'))))
      .then((data) => {
        if (!cancelled) {
          setLearningSummary({
            offensive_pct_learned: Number(data?.offensive_pct_learned ?? 0),
            defensive_pct_learned: Number(data?.defensive_pct_learned ?? 0),
            overall_grade: data?.overall_grade != null ? String(data.overall_grade) : null,
          })
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLearningSummary({
            offensive_pct_learned: 0,
            defensive_pct_learned: 0,
            overall_grade: null,
          })
        }
      })
      .finally(() => {
        if (!cancelled) setLearningLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [apiBase, headers, isPlaySelectionResultsStage, saveId])

  if (showSettings) {
    return (
      <SettingsPage
        apiBase={apiBase}
        headers={headers}
        saveId={saveId}
        teamNames={allTeamNames}
        backupReminderFrequency={backupReminderFrequency ?? 'none'}
        onBackupReminderFrequencyChange={onBackupReminderFrequencyChange}
        onBackupNow={onBackupNow}
        onApplySaveState={onSaveState}
        onClose={() => setShowSettings(false)}
        onError={onError}
        onLogoVersionBump={() => setLogoVersion(Date.now())}
      />
    )
  }

  if (showPlaybookGamePlan && isPlaySelectionStage) {
    return (
      <PlaybookGamePlanPage
        apiBase={apiBase}
        headers={headers}
        saveId={saveId}
        saveState={saveState}
        logoVersion={logoVersion}
        onBack={() => setShowPlaybookGamePlan(false)}
        onConfirm={async (gamePlan) => {
          await onSimWeek({ gamePlan })
        }}
        onError={onError}
      />
    )
  }

  if (activeGame) {
    return (
      <GamePlayPage
        apiBase={apiBase}
        headers={headers}
        saveId={saveId}
        saveState={saveState}
        gameId={activeGame.gameId}
        homeTeam={activeGame.homeTeam}
        awayTeam={activeGame.awayTeam}
        userTeam={activeGame.userTeam}
        logoVersion={logoVersion}
        initialState={activeGame.initialState}
        onContinue={async (gameOver, finishPayload) => {
          if (gameOver) {
            try {
              if (isLocalBundle) {
                const game = finishPayload?.game
                if (!game || typeof game !== 'object') {
                  throw new Error('Cannot finish game: missing game data (try reloading the save).')
                }
                const path =
                  activeGame.gameContext === 'week'
                    ? `${apiBase}/sim/game/finish-week`
                    : activeGame.gameContext === 'playoff'
                      ? `${apiBase}/sim/game/finish-playoff`
                      : `${apiBase}/sim/game/finish-scrimmage?scrimmage_stage=${encodeURIComponent(activeGame.scrimmageStage ?? 'Scrimmage 1')}`
                const r = await fetch(path, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ state: saveState, game }),
                })
                if (!r.ok) {
                  const errText = await r.text()
                  let msg = 'Failed to finish game'
                  try {
                    const j = JSON.parse(errText)
                    msg = (typeof j?.detail === 'string' ? j.detail : Array.isArray(j?.detail) ? JSON.stringify(j.detail) : errText) || msg
                  } catch {
                    msg = errText || msg
                  }
                  throw new Error(msg)
                }
                const data = await r.json()
                onSaveState?.(data.state)
              } else {
                const url =
                  activeGame.gameContext === 'week'
                    ? `${apiBase}/saves/${saveId}/games/${activeGame.gameId}/finish-week`
                    : activeGame.gameContext === 'playoff'
                      ? `${apiBase}/saves/${saveId}/games/${activeGame.gameId}/finish-playoff`
                      : `${apiBase}/saves/${saveId}/games/${activeGame.gameId}/finish-scrimmage?scrimmage_stage=${encodeURIComponent(activeGame.scrimmageStage ?? 'Scrimmage 1')}`
                const r = await fetch(url, { method: 'POST', headers })
                if (!r.ok) {
                  const errText = await r.text()
                  let msg = 'Failed to finish game'
                  try {
                    const j = JSON.parse(errText)
                    msg = (typeof j?.detail === 'string' ? j.detail : errText) || msg
                  } catch {
                    msg = errText || msg
                  }
                  throw new Error(msg)
                }
                const data = await r.json()
                onSaveState?.(data.state)
              }
            } catch (e: any) {
              onError(e?.message ?? 'Failed to finish')
              return
            }
          }
          setActiveGame(null)
        }}
        onError={onError}
      />
    )
  }

  const renderTeamMenuPanel = () => {
    const gpBack = () => setTeamMenu(defaultTeamMenuForPhase(phase))
    if (teamMenu === 'Roster') {
      return (
        <div className="teamhome-roster-shell teamhome-roster-shell--attrs">
          <div className="teamhome-roster-attrs-scroll" role="region" aria-label="Roster table">
            <div
              className="teamhome-roster-head teamhome-roster-row teamhome-roster-row-attrs teamhome-roster-attrs-head"
              style={{ gridTemplateColumns: rosterGridCols }}
            >
              <div className="teamhome-roster-name">Name</div>
              <div className="teamhome-roster-cell">Position</div>
              <div className="teamhome-roster-cell">Off Pos</div>
              <div className="teamhome-roster-cell">Def Pos</div>
              <div className="teamhome-roster-cell">Off Rtg</div>
              <div className="teamhome-roster-cell">Def Rtg</div>
              <div className="teamhome-roster-cell">Ovr</div>
              <div className="teamhome-roster-cell">Year</div>
              <div className="teamhome-roster-cell">Ht</div>
              <div className="teamhome-roster-cell">Wt</div>
              {PLAYER_ATTRIBUTE_COLUMNS_SCROLL.map((col) => (
                <div key={col.key} className="teamhome-roster-cell teamhome-roster-attr-h" title={col.key}>
                  {col.label}
                </div>
              ))}
            </div>
            <div className="teamhome-roster-table teamhome-roster-table--attrs">
              {rosterPlayers.length === 0 ? (
                <div className="teamhome-roster-empty">No roster players found for this team.</div>
              ) : (
                rosterPlayers.map((p: any, i: number) => {
                const name = p?.name ?? 'Unknown'
                const position = p?.position ?? '—'
                const secondaryPosition = p?.secondary_position ?? '—'
                const offPosition = getPlayerSidePosition(p, 'offense')
                const defPosition = getPlayerSidePosition(p, 'defense')
                const offRating = getBestSideRating(p, 'offense')
                const defRating = getBestSideRating(p, 'defense')
                const overall = computePlayerOverall(p)
                const yearLabel = formatPlayerYear(p?.year)
                return (
                  <div
                    key={`${name}-${i}`}
                    className="teamhome-roster-row teamhome-roster-row-attrs"
                    style={{ gridTemplateColumns: rosterGridCols }}
                  >
                    <PlayerProfileName teamName={userTeam} playerName={String(name)} className="teamhome-roster-name" as="div" />
                    <div className="teamhome-roster-cell">
                      {position}
                      {secondaryPosition && secondaryPosition !== '—' ? ` / ${secondaryPosition}` : ''}
                    </div>
                    <div className="teamhome-roster-cell">{offPosition}</div>
                    <div className="teamhome-roster-cell">{defPosition}</div>
                    <div className="teamhome-roster-cell">{offPosition === '—' ? '—' : offRating}</div>
                    <div className="teamhome-roster-cell">{defPosition === '—' ? '—' : defRating}</div>
                    <div className="teamhome-roster-cell">{overall}</div>
                    <div className="teamhome-roster-cell">{yearLabel}</div>
                    <div className="teamhome-roster-cell">{formatPlayerAttributeCell(p, 'height')}</div>
                    <div className="teamhome-roster-cell">{formatPlayerAttributeCell(p, 'weight')}</div>
                    {PLAYER_ATTRIBUTE_COLUMNS_SCROLL.map((col) => (
                      <div key={col.key} className="teamhome-roster-cell teamhome-roster-attr-cell">
                        {formatPlayerAttributeCell(p, col.key)}
                      </div>
                    ))}
                  </div>
                )
              })
              )}
            </div>
          </div>
        </div>
      )
    }
    if (teamMenu === 'Depth Chart') {
      return (
        <DepthChartPage
          saveState={saveState}
          userTeam={userTeam}
          isPreseason={false}
          onSave={async (depthChart) => {
            if (!saveId || !onSaveState) return
            const r = await fetch(`${apiBase}/saves/${saveId}/depth-chart`, {
              method: 'PUT',
              headers: { ...headers, 'Content-Type': 'application/json' },
              body: JSON.stringify({ depth_chart: depthChart }),
            })
            if (!r.ok) {
              const err = await r.json().catch(() => ({}))
              onError(err?.detail ?? 'Failed to save depth chart')
              return
            }
            const data = await r.json()
            if (data?.state) onSaveState(data.state)
          }}
          onBack={() => setTeamMenu(defaultTeamMenuForPhase(phase))}
        />
      )
    }
    if (teamMenu === 'Team Stats') {
      return (
        <div className="teamhome-roster-shell">
          {leagueClassFilterBar}
          <div className="teamhome-roster-head">Click a column to sort rankings by that stat</div>
          <div className="teamhome-roster-table">
            <div className="teamhome-teamstats-row teamhome-teamstats-row-head">
              <button type="button" className="teamhome-table-sort-btn" onClick={() => toggleTeamStatsSort('teamName')}>
                Team
              </button>
              <button type="button" className="teamhome-table-sort-btn" onClick={() => toggleTeamStatsSort('games')}>
                G
              </button>
              <button type="button" className="teamhome-table-sort-btn" onClick={() => toggleTeamStatsSort('ppg')}>
                PPG
              </button>
              <button type="button" className="teamhome-table-sort-btn" onClick={() => toggleTeamStatsSort('ppgAllowed')}>
                PPGA
              </button>
              <button type="button" className="teamhome-table-sort-btn" onClick={() => toggleTeamStatsSort('ypg')}>
                YPG
              </button>
              <button type="button" className="teamhome-table-sort-btn" onClick={() => toggleTeamStatsSort('rypg')}>
                Rush YPG
              </button>
              <button type="button" className="teamhome-table-sort-btn" onClick={() => toggleTeamStatsSort('pypg')}>
                Pass YPG
              </button>
              <button type="button" className="teamhome-table-sort-btn" onClick={() => toggleTeamStatsSort('explosives')}>
                Explosives
              </button>
              <button type="button" className="teamhome-table-sort-btn" onClick={() => toggleTeamStatsSort('turnovers')}>
                Turnovers
              </button>
              <button type="button" className="teamhome-table-sort-btn" onClick={() => toggleTeamStatsSort('pointsFor')}>
                PF
              </button>
              <button type="button" className="teamhome-table-sort-btn" onClick={() => toggleTeamStatsSort('pointsAgainst')}>
                PA
              </button>
            </div>
            {sortedTeamStatRows.length === 0 ? (
              <div className="teamhome-roster-empty">No team stats available yet.</div>
            ) : (
              sortedTeamStatRows.map((r) => (
                <div key={r.teamName} className="teamhome-teamstats-row">
                  <div className="teamhome-roster-name">{teamWithLogo(r.teamName)}</div>
                  <div className="teamhome-roster-cell">{r.games}</div>
                  <div className="teamhome-roster-cell">{r.ppg.toFixed(1)}</div>
                  <div className="teamhome-roster-cell">{r.ppgAllowed.toFixed(1)}</div>
                  <div className="teamhome-roster-cell">{r.ypg.toFixed(1)}</div>
                  <div className="teamhome-roster-cell">{r.rypg.toFixed(1)}</div>
                  <div className="teamhome-roster-cell">{r.pypg.toFixed(1)}</div>
                  <div className="teamhome-roster-cell">{r.explosives}</div>
                  <div className="teamhome-roster-cell">{r.turnovers}</div>
                  <div className="teamhome-roster-cell">{r.pointsFor}</div>
                  <div className="teamhome-roster-cell">{r.pointsAgainst}</div>
                </div>
              ))
            )}
          </div>
        </div>
      )
    }
    if (teamMenu === 'Player Stats') {
      return (
        <div className="teamhome-roster-shell">
          <div className="teamhome-roster-head">Sortable player stats — offense and defense views</div>
          <div className="teamhome-playerstats-toggle">
            <button
              type="button"
              className={`teamhome-playerstats-toggle-btn ${playerStatsSide === 'offense' ? 'active' : ''}`}
              onClick={() => setPlayerStatsSide('offense')}
            >
              Offensive stats
            </button>
            <button
              type="button"
              className={`teamhome-playerstats-toggle-btn ${playerStatsSide === 'defense' ? 'active' : ''}`}
              onClick={() => setPlayerStatsSide('defense')}
            >
              Defensive stats
            </button>
          </div>
          <div className="teamhome-roster-table">
            {playerStatsSide === 'offense' ? (
              <div className="teamhome-playerstats-row teamhome-playerstats-row-head teamhome-playerstats-row-offense">
                <button type="button" className="teamhome-table-sort-btn" onClick={() => togglePlayerStatsSort('playerName')}>
                  Player
                </button>
                <button type="button" className="teamhome-table-sort-btn" onClick={() => togglePlayerStatsSort('teamName')}>
                  Team
                </button>
                <button type="button" className="teamhome-table-sort-btn" onClick={() => togglePlayerStatsSort('position')}>
                  Pos
                </button>
                <button type="button" className="teamhome-table-sort-btn" onClick={() => togglePlayerStatsSort('passYds')}>
                  Pass Yds
                </button>
                <button type="button" className="teamhome-table-sort-btn" onClick={() => togglePlayerStatsSort('comp')}>
                  Comp
                </button>
                <button type="button" className="teamhome-table-sort-btn" onClick={() => togglePlayerStatsSort('att')}>
                  Att
                </button>
                <button type="button" className="teamhome-table-sort-btn" onClick={() => togglePlayerStatsSort('cmpPct')}>
                  Cmp%
                </button>
                <button type="button" className="teamhome-table-sort-btn" onClick={() => togglePlayerStatsSort('passTd')}>
                  Pass TD
                </button>
                <button type="button" className="teamhome-table-sort-btn" onClick={() => togglePlayerStatsSort('intThrown')}>
                  INT
                </button>
                <button type="button" className="teamhome-table-sort-btn" onClick={() => togglePlayerStatsSort('rushYds')}>
                  Rush Yds
                </button>
                <button type="button" className="teamhome-table-sort-btn" onClick={() => togglePlayerStatsSort('rushTd')}>
                  Rush TD
                </button>
                <button type="button" className="teamhome-table-sort-btn" onClick={() => togglePlayerStatsSort('rec')}>
                  Rec
                </button>
                <button type="button" className="teamhome-table-sort-btn" onClick={() => togglePlayerStatsSort('recYds')}>
                  Rec Yds
                </button>
                <button type="button" className="teamhome-table-sort-btn" onClick={() => togglePlayerStatsSort('recTd')}>
                  Rec TD
                </button>
              </div>
            ) : (
              <div className="teamhome-playerstats-row teamhome-playerstats-row-head teamhome-playerstats-row-defense">
                <button type="button" className="teamhome-table-sort-btn" onClick={() => togglePlayerStatsSort('playerName')}>
                  Player
                </button>
                <button type="button" className="teamhome-table-sort-btn" onClick={() => togglePlayerStatsSort('teamName')}>
                  Team
                </button>
                <button type="button" className="teamhome-table-sort-btn" onClick={() => togglePlayerStatsSort('position')}>
                  Pos
                </button>
                <button type="button" className="teamhome-table-sort-btn" onClick={() => togglePlayerStatsSort('tackles')}>
                  Tackles
                </button>
                <button type="button" className="teamhome-table-sort-btn" onClick={() => togglePlayerStatsSort('sacks')}>
                  Sacks
                </button>
                <button type="button" className="teamhome-table-sort-btn" onClick={() => togglePlayerStatsSort('tfl')}>
                  TFL
                </button>
                <button type="button" className="teamhome-table-sort-btn" onClick={() => togglePlayerStatsSort('interceptions')}>
                  INT
                </button>
              </div>
            )}
            {sortedPlayerStatRows.length === 0 ? (
              <div className="teamhome-roster-empty">No player stats logged yet this season.</div>
            ) : playerStatsSide === 'offense' ? (
              sortedPlayerStatRows.map((r) => (
                <div key={`${r.teamName}-${r.playerName}`} className="teamhome-playerstats-row teamhome-playerstats-row-offense">
                  <PlayerProfileName
                    teamName={r.teamName}
                    playerName={r.playerName}
                    className="teamhome-roster-name"
                    as="div"
                  />
                  <div className="teamhome-roster-cell">{teamWithLogo(r.teamName, 22)}</div>
                  <div className="teamhome-roster-cell">{r.position}</div>
                  <div className="teamhome-roster-cell">{r.passYds}</div>
                  <div className="teamhome-roster-cell">{r.comp}</div>
                  <div className="teamhome-roster-cell">{r.att}</div>
                  <div className="teamhome-roster-cell">{r.att > 0 ? ((r.comp / r.att) * 100).toFixed(1) : '0.0'}</div>
                  <div className="teamhome-roster-cell">{r.passTd}</div>
                  <div className="teamhome-roster-cell">{r.intThrown}</div>
                  <div className="teamhome-roster-cell">{r.rushYds}</div>
                  <div className="teamhome-roster-cell">{r.rushTd}</div>
                  <div className="teamhome-roster-cell">{r.rec}</div>
                  <div className="teamhome-roster-cell">{r.recYds}</div>
                  <div className="teamhome-roster-cell">{r.recTd}</div>
                </div>
              ))
            ) : (
              sortedPlayerStatRows.map((r) => (
                <div key={`${r.teamName}-${r.playerName}`} className="teamhome-playerstats-row teamhome-playerstats-row-defense">
                  <PlayerProfileName
                    teamName={r.teamName}
                    playerName={r.playerName}
                    className="teamhome-roster-name"
                    as="div"
                  />
                  <div className="teamhome-roster-cell">{teamWithLogo(r.teamName, 22)}</div>
                  <div className="teamhome-roster-cell">{r.position}</div>
                  <div className="teamhome-roster-cell">{r.tackles}</div>
                  <div className="teamhome-roster-cell">{r.sacks}</div>
                  <div className="teamhome-roster-cell">{r.tfl}</div>
                  <div className="teamhome-roster-cell">{r.interceptions}</div>
                </div>
              ))
            )}
          </div>
        </div>
      )
    }
    if (teamMenu === 'Playbook') {
      return (
        <PlaybookGamePlanPage
          apiBase={apiBase}
          headers={headers}
          saveId={saveId}
          saveState={saveState}
          logoVersion={logoVersion}
          onBack={gpBack}
          onError={onError}
          readOnly
          headerBackLabel="Back to Team Home"
        />
      )
    }
    if (teamMenu === 'OFF Gameplan') {
      return (
        <CoachGameplanPage apiBase={apiBase} headers={headers} saveId={saveId} side="offense" onBack={gpBack} onError={onError} />
      )
    }
    if (teamMenu === 'DEF Gameplan') {
      return (
        <CoachGameplanPage apiBase={apiBase} headers={headers} saveId={saveId} side="defense" onBack={gpBack} onError={onError} />
      )
    }
    if (teamMenu === SCOUTING_MENU_OFFENSE) {
      return (
        <ScoutingReportPage
          key="scout-offense"
          apiBase={apiBase}
          headers={headers}
          saveState={saveState}
          userTeam={userTeam}
          initialTab="offense"
          logoVersion={logoVersion}
          onBack={() => setTeamMenu(defaultTeamMenuForPhase(phase))}
        />
      )
    }
    if (teamMenu === SCOUTING_MENU_DEFENSE) {
      return (
        <ScoutingReportPage
          key="scout-defense"
          apiBase={apiBase}
          headers={headers}
          saveState={saveState}
          userTeam={userTeam}
          initialTab="defense"
          logoVersion={logoVersion}
          onBack={() => setTeamMenu(defaultTeamMenuForPhase(phase))}
        />
      )
    }

    if (teamMenu === COACH_INBOX_MENU) {
      return (
        <div className="teamhome-roster-shell teamhome-coach-inbox-shell">
          <CoachInboxPanel
            saveState={saveState}
            saveId={saveId}
            apiBase={apiBase}
            headers={headers}
            onSaveState={onSaveState}
            onError={onError}
            readOnly={isLocalBundle}
          />
        </div>
      )
    }
    return (
      <div className="teamhome-roster-shell">
        <div className="teamhome-roster-empty">Select a view from the menu.</div>
      </div>
    )
  }

  return (
    <div className="teamhome-root teamhome-root--news">
      <div className="teamhome-topbar">
        <div className="teamhome-logo" title={userTeam ? `${userTeam} logo` : ''}>
          <TeamLogo apiBase={apiBase} headers={headers} teamName={userTeam} logoVersion={logoVersion} size={52} />
        </div>
        <div className="teamhome-top-group teamhome-top-group-name">
          <div className="teamhome-top-label">TEAM NAME</div>
          <div className="teamhome-top-value teamhome-top-value--name">{userTeam || '—'}</div>
          <div className="teamhome-top-subvalue">{userNickname}</div>
        </div>
        <div className="teamhome-top-group">
          <div className="teamhome-top-label">RECORD</div>
          <div className="teamhome-top-value">{record}</div>
        </div>
        <div className="teamhome-top-group">
          <div className="teamhome-top-label">RANK</div>
          <div className="teamhome-top-value">{rank ? `#${rank}` : '—'}</div>
        </div>
        <div className="teamhome-top-group">
          <div className="teamhome-top-label">CLASS RANK</div>
          <div className="teamhome-top-value">{classRank != null ? `#${classRank}` : '—'}</div>
          {teamBarClassification && teamBarClassification !== '—' ? (
            <div className="teamhome-top-subvalue">{teamBarClassification}</div>
          ) : (
            <div className="teamhome-top-subvalue" style={{ opacity: 0.45 }}>
              —
            </div>
          )}
        </div>
        <div className="teamhome-top-group teamhome-top-group-teamnav">
          <div className="teamhome-top-label">TEAM</div>
          <select
            className="teamhome-select teamhome-select-teamnav"
            value={teamMenu}
            onChange={(e) => {
              setTeamMenu(e.target.value)
              // If user is in a State view, switching TEAM should immediately show TEAM content.
              if (stateMenu !== 'Dashboard') setStateMenu('Dashboard')
            }}
          >
            {phase === 'playoffs' && <option value={PLAYOFF_BRACKET_MENU}>Playoff bracket</option>}
            {phase === 'regular' && <option>Overview</option>}
            {phase === 'preseason' && <option value={PRESEASON_TEAM_HUB}>Preseason</option>}
            {phase === 'offseason' && <option value={OFFSEASON_TEAM_HUB}>Offseason hub</option>}
            <option>Roster</option>
            <option>Depth Chart</option>
            <option>Team Stats</option>
            <option>Player Stats</option>
            <option>Playbook</option>
            <option>OFF Gameplan</option>
            <option>DEF Gameplan</option>
            <option value={SCOUTING_MENU_OFFENSE}>Offensive Scouting Report</option>
            <option value={SCOUTING_MENU_DEFENSE}>Defensive Scouting Report</option>
            <option value={COACH_INBOX_MENU}>
              Coach Inbox{coachInboxUnread > 0 ? ` (${coachInboxUnread} new)` : ''}
            </option>
          </select>
        </div>
        <div className="teamhome-top-group teamhome-top-group-league">
          <div className="teamhome-top-label">STATE</div>
          <select
            className="teamhome-select teamhome-select-league"
            value={stateMenu}
            title="League-wide views (standings, stats, statewide top players, etc.)"
            aria-label="State league menu"
            onChange={(e) => setStateMenu(e.target.value)}
          >
            <option value="Dashboard">Dashboard</option>
            <option value="Top Players">Top Players (statewide)</option>
            <option value="Standings">Standings</option>
            <option value="Weekly schedule">Weekly schedule</option>
            <option value="Team Schedule">Team Schedule</option>
            <option value="Rankings">Rankings</option>
            <option value="Stats">Stats</option>
            <option value="Team Info">Team Info</option>
            <option value="Coaching changes">Coaching changes</option>
            <option value="Team History">Team History</option>
            <option value="Prestige report">Prestige report</option>
            <option value="League History">League History</option>
          </select>
        </div>
        <div className="teamhome-top-actions">
          {phase === 'offseason' ? (
            <div className="teamhome-offseason-stage-inline" aria-live="polite">
              <div className="teamhome-offseason-stage-inline-row">
                <span className="teamhome-offseason-stage-k">Now</span>
                <span className="teamhome-offseason-stage-v">
                  {displayOffseasonStageLabel(offseasonCurrentStage || 'Offseason')}
                </span>
                <span className="teamhome-offseason-stage-sep" aria-hidden>
                  ·
                </span>
                <span className="teamhome-offseason-stage-k">Next</span>
                <span className="teamhome-offseason-stage-v">{offseasonNextStageLabel || '—'}</span>
              </div>
            </div>
          ) : null}
          <div className="teamhome-top-actions-end">
          <button
            type="button"
            className="teamhome-continue"
            style={continueStyle}
            disabled={
              !canContinue ||
              (phase === 'regular' && simmingWeek) ||
              isPlaybookSelectStage ||
              isPlaySelectionStage ||
              isPlaySelectionResultsStage ||
              isSetDepthChartStage ||
              isScrimmageStage ||
              isSetGoalsStage ||
              winterAllocationInvalid ||
              (phase === 'offseason' && offseasonCurrentStage === 'Improvements' && improvementsBudget.invalid)
            }
            onClick={async () => {
              try {
                if (phase === 'offseason') {
                  let offseasonBody: {
                    winter_strength_pct?: number
                    winter_training_allocations?: Record<string, number>
                    winter_training_ack_results?: boolean
                    spring_offense_focus?: string
                    spring_defense_focus?: string
                    spring_ball_ack_results?: boolean
                    improve_facilities_grade?: number
                    improve_culture_grade?: number
                    improve_booster_support?: number
                    improve_facilities_cumulative_pp?: number
                    improve_culture_cumulative_pp?: number
                    improve_boosters_cumulative_pp?: number
                    coach_dev_allocations?: Record<string, number>
                    carousel_job_applications?: string[]
                    transfer_stage_1_ack_results?: boolean
                    transfer_stage_2_ack_results?: boolean
                  } = {}
                  if (offseasonCurrentStage === 'Winter 1' || offseasonCurrentStage === 'Winter 2') {
                    offseasonBody = winterTrainingResult
                      ? { winter_training_ack_results: true }
                      : { winter_strength_pct: winterStrengthPct, winter_training_allocations: winterTrainingAllocations }
                  } else if (offseasonCurrentStage === 'Spring Ball') {
                    offseasonBody = springBallResult
                      ? { spring_ball_ack_results: true }
                      : { spring_offense_focus: springOffense, spring_defense_focus: springDefense }
                  } else if (offseasonCurrentStage === 'Improvements') {
                    offseasonBody = {
                      improve_facilities_cumulative_pp: improveFacCumulative,
                      improve_culture_cumulative_pp: improveCulCumulative,
                      improve_boosters_cumulative_pp: improveBooCumulative,
                    }
                  } else if (offseasonCurrentStage === 'Coach development') {
                    offseasonBody = { coach_dev_allocations: coachDevAllocations }
                  } else if (
                    offseasonCurrentStage === 'Coaching carousel I' ||
                    offseasonCurrentStage === 'Coaching carousel II' ||
                    offseasonCurrentStage === 'Coaching carousel III'
                  ) {
                    offseasonBody = { carousel_job_applications: carouselJobApplications }
                  } else if (offseasonCurrentStage === 'Transfers I') {
                    offseasonBody = transferStage1PendingReview
                      ? { transfer_stage_1_ack_results: true }
                      : {}
                  } else if (offseasonCurrentStage === 'Transfers II') {
                    offseasonBody = transferStage2PendingReview
                      ? { transfer_stage_2_ack_results: true }
                      : {}
                  }
                  await onSimWeek({ offseasonBody })
                } else if (phase === 'preseason' && isPositionChangesStage) {
                  const t = findTeam(saveState, userTeam)
                  const roster = t?.roster ?? []
                  const out: { player_name: string; position: string; secondary_position: string | null }[] = []
                  for (const p of roster) {
                    const d = positionDraft[p.name]
                    if (!d) continue
                    const sec = d.secondary.trim() ? d.secondary.trim() : null
                    const oldSec = p.secondary_position ?? null
                    if (d.position !== p.position || sec !== oldSec) {
                      out.push({ player_name: p.name, position: d.position, secondary_position: sec })
                    }
                  }
                  await onSimWeek({ positionChanges: out })
                } else if (phase === 'season_summary') {
                  await onSimWeek({ seasonFinish: true })
                } else {
                  if (phase === 'regular' || phase === 'playoffs') setSimmingWeek(true)
                  try {
                    await onSimWeek()
                  } finally {
                    if (phase === 'regular' || phase === 'playoffs') setSimmingWeek(false)
                  }
                }
              } catch (e: any) {
                onError(e?.message ?? 'Continue failed')
              }
            }}
            title={
              phase === 'season_summary'
                ? 'Archive complete — begin offseason (Graduation, coach development, etc.)'
                : phase === 'playoffs' && playoffsComplete
                ? 'Playoffs complete — Continue to open season summary'
                : phase === 'playoffs'
                  ? 'Simulate the next playoff round (quarterfinals → semifinals → championship)'
                  : phase === 'offseason' &&
                      offseasonCurrentStage === 'Improvements' &&
                      improvementsBudget.invalid
                    ? 'Reduce upgrades or use downgrades until PP is not overspent (see warning on the dashboard).'
                    : phase === 'offseason'
                      ? 'Complete the current offseason step and advance'
                      : isPlaybookSelectStage
                        ? 'Confirm playbook selection first'
                        : isPlaySelectionStage
                          ? 'Confirm game plan first'
                          : isPlaySelectionResultsStage
                            ? 'Confirm play selection results first'
                            : isPositionChangesStage
                              ? 'Continue to depth chart (CPU teams update positions automatically)'
                              : isSetDepthChartStage
                                ? 'Confirm depth chart first'
                                : isScrimmageStage
                                  ? 'Use Play or Simulate in the panel below'
                                  : isSetGoalsStage
                                    ? 'Confirm goals below'
                                    : 'Simulate the current week and advance'
            }
          >
            {phase === 'regular' && simmingWeek
              ? 'Simming week…'
              : phase === 'playoffs' && simmingWeek
                ? 'Simming playoffs…'
                : phase === 'season_summary'
                  ? 'Begin offseason'
                  : 'Continue'}
          </button>
          <button type="button" className="teamhome-select" onClick={() => setShowSettings(true)} title="Settings">
            Settings
          </button>
          <button type="button" className="teamhome-select" onClick={onMainMenu} title="Back to main menu">
            Main menu
          </button>
          </div>
        </div>
      </div>

      <div className="teamhome-secondbar">
        <div className="teamhome-top-group">
          <div className="teamhome-top-label">STAGE</div>
          <div className="teamhome-top-value">
            {phase === 'preseason'
              ? preseasonCurrentStage
              : phase === 'offseason'
                ? offseasonCurrentStage || 'Offseason'
                : phase === 'season_summary'
                  ? 'Season summary'
                  : formatStage(phase)}
          </div>
        </div>
        <div className="teamhome-top-group">
          <div className="teamhome-top-label">
            {phase === 'playoffs'
              ? 'PLAYOFF STATUS'
              : phase === 'offseason'
                ? 'OFFSEASON STEP'
                : phase === 'season_summary'
                  ? 'SEASON YEAR'
                  : 'CURRENT WEEK'}
          </div>
          <div className="teamhome-top-value">
            {phase === 'playoffs'
              ? playoffRoundDisplay
              : phase === 'offseason'
                ? offseasonStages.length
                  ? `${Math.min(offseasonStageIndex + 1, offseasonStages.length)} / ${offseasonStages.length}`
                  : '—'
                : phase === 'season_summary'
                  ? saveState?.current_year ?? '—'
                  : saveState?.current_week ?? '—'}
          </div>
        </div>
        <div className="teamhome-top-group">
          <div className="teamhome-top-label">
            {phase === 'season_summary' ? 'NEXT STEP' : 'NEXT OPPONENT'}
          </div>
          <div className="teamhome-top-value">
            {phase === 'season_summary' ? 'Offseason · Graduation' : nextOpponentText}
          </div>
        </div>
        <div className="teamhome-top-group">
          <div className="teamhome-top-label">{phase === 'playoffs' ? 'LAST PLAYOFF GAME' : 'LAST WEEKS RESULTS'}</div>
          <div className="teamhome-top-value">{lastOpponentText}</div>
        </div>
      </div>

      <div className="teamhome-content">
        {phase === 'season_summary' ? (
          stateMenu !== 'Dashboard' && leagueStatePanel ? (
            <div className="teamhome-roster-shell teamhome-playoffs-league-view">
              <div className="season-summary-state-banner">
                <button
                  type="button"
                  className="teamhome-select season-summary-back-btn"
                  onClick={() => setStateMenu('Dashboard')}
                >
                  ← Back to season summary
                </button>
              </div>
              {leagueStatePanel}
            </div>
          ) : (
            <SeasonSummaryPanel
              apiBase={apiBase}
              headers={headers}
              logoVersion={logoVersion}
              saveState={saveState}
              userTeam={userTeam}
              leagueHistory={leagueHistory}
              seasonYear={Number(saveState?.current_year)}
              playoffView={playoffView}
              standingsRows={seasonSummaryStandingsRows}
              bracketSlot={seasonSummaryBracketNode}
              teamWithLogo={teamWithLogo}
              onOpenLeagueHistory={() => setStateMenu('League History')}
              onOpenTeamHistory={() => setStateMenu('Team History')}
            />
          )
        ) : phase === 'preseason' ? (
          stateMenu !== 'Dashboard' && leagueStatePanel ? (
            <div className="teamhome-roster-shell teamhome-playoffs-league-view">{leagueStatePanel}</div>
          ) : teamMenu !== PRESEASON_TEAM_HUB ? (
            renderTeamMenuPanel()
          ) : (
          <div className="teamhome-preseason-shell">
            <div className="teamhome-preseason-top">
              {completedScrimmages.length > 0 ? (
                <div className="teamhome-scrimmage-upcoming" style={{ marginBottom: 10, opacity: 0.92 }}>
                  <span className="teamhome-scrimmage-upcoming-label">Scrimmage results:</span>{' '}
                  {completedScrimmages
                    .slice()
                    .sort((a, b) => String(a.name).localeCompare(String(b.name)))
                    .map((s, i) => (
                      <span key={`${s.name}-${i}`}>
                        {i > 0 && ' · '}
                        {s.name}: {s.home} {s.home_score}–{s.away} {s.away_score}
                        {s.ot ? ' (OT)' : ''}
                      </span>
                    ))}
                </div>
              ) : null}
              {isPlaybookSelectStage ? (
                <div className="teamhome-playbook-select">
                  <div className="teamhome-playbook-title">Select playbooks for the upcoming season</div>
                  {!canChangePreferredPlaybooks ? (
                    <p className="teamhome-playbook-lock" style={{ marginBottom: 12, opacity: 0.92, maxWidth: 520 }}>
                      Preferred playbooks are locked until season {nextPreferredPlaybookEligibleYear ?? '—'} (once every{' '}
                      {PREFERRED_PLAYBOOK_LOCK_SEASONS} seasons). You can still confirm to advance using your current playbooks.
                    </p>
                  ) : null}
                  <div className="teamhome-playbook-row">
                    <div className="teamhome-playbook-field">
                      <label className="teamhome-playbook-label">Offensive playbook</label>
                      <select
                        className="teamhome-playbook-select-input"
                        value={offensivePlaybook}
                        disabled={!canChangePreferredPlaybooks}
                        onChange={(e) => setOffensivePlaybook(e.target.value)}
                      >
                        {OFFENSIVE_PLAYBOOKS.map((pb) => (
                          <option key={pb} value={pb}>
                            {pb}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="teamhome-playbook-field">
                      <label className="teamhome-playbook-label">Defensive playbook</label>
                      <select
                        className="teamhome-playbook-select-input"
                        value={defensivePlaybook}
                        disabled={!canChangePreferredPlaybooks}
                        onChange={(e) => setDefensivePlaybook(e.target.value)}
                      >
                        {DEFENSIVE_PLAYBOOKS.map((pb) => (
                          <option key={pb} value={pb}>
                            {pb}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                  <button
                    type="button"
                    className="teamhome-playbook-confirm"
                    disabled={confirmingPlaybook}
                    onClick={async () => {
                      setConfirmingPlaybook(true)
                      try {
                        await onSimWeek({
                          playbook: {
                            offensive_playbook: offensivePlaybook,
                            defensive_playbook: defensivePlaybook,
                          },
                        })
                      } catch (e: any) {
                        onError(e?.message ?? 'Failed to confirm playbook')
                      } finally {
                        setConfirmingPlaybook(false)
                      }
                    }}
                  >
                    {confirmingPlaybook ? 'Confirming…' : 'Confirm'}
                  </button>
                </div>
              ) : isPlaySelectionStage ? (
                <div className="teamhome-preseason-panelA">
                  <div className="teamhome-preseason-title">Play Selection</div>
                  <div className="teamhome-preseason-sub">Assign percentages to plays in each category</div>
                  <div className="teamhome-preseason-stage">Each category must total 100%</div>
                  <button
                    type="button"
                    className="teamhome-playbook-confirm"
                    style={{ marginTop: 16 }}
                    onClick={() => setShowPlaybookGamePlan(true)}
                  >
                    Configure Game Plan
                  </button>
                </div>
              ) : isPositionChangesStage ? (
                <div className="teamhome-preseason-panelA teamhome-position-changes">
                  <div className="teamhome-preseason-title">Position changes</div>
                  <div className="teamhome-preseason-sub">
                    Set each player&apos;s primary position (and optional secondary for two-way). CPU teams are reassigned automatically when you continue.
                  </div>
                  <div className="teamhome-position-changes-table-wrap">
                    <div className="teamhome-roster-row teamhome-roster-row-attrs teamhome-position-changes-head">
                      <div className="teamhome-roster-name">Player</div>
                      <div className="teamhome-roster-cell">Ovr</div>
                      <div className="teamhome-roster-cell">Primary</div>
                      <div className="teamhome-roster-cell">Secondary</div>
                    </div>
                    {(findTeam(saveState, userTeam)?.roster ?? []).map((p: any) => {
                      const d = positionDraft[p.name] ?? {
                        position: String(p.position || 'WR'),
                        secondary: p.secondary_position ? String(p.secondary_position) : '',
                      }
                      return (
                        <div key={p.name} className="teamhome-roster-row teamhome-position-changes-row">
                          <PlayerProfileName
                            teamName={userTeam}
                            playerName={String(p.name)}
                            className="teamhome-roster-name"
                            as="div"
                          />
                          <div className="teamhome-roster-cell">{computePlayerOverall(p)}</div>
                          <div className="teamhome-roster-cell">
                            <select
                              className="teamhome-select-inline"
                              value={d.position}
                              onChange={(e) =>
                                setPositionDraft((prev) => ({
                                  ...prev,
                                  [p.name]: { ...d, position: e.target.value },
                                }))
                              }
                            >
                              {ALL_PRESEASON_POSITIONS.map((pos) => (
                                <option key={pos} value={pos}>
                                  {pos}
                                </option>
                              ))}
                            </select>
                          </div>
                          <div className="teamhome-roster-cell">
                            <select
                              className="teamhome-select-inline"
                              value={d.secondary || ''}
                              onChange={(e) =>
                                setPositionDraft((prev) => ({
                                  ...prev,
                                  [p.name]: { ...d, secondary: e.target.value },
                                }))
                              }
                            >
                              <option value="">—</option>
                              {ALL_PRESEASON_POSITIONS.filter((pos) => pos !== d.position).map((pos) => (
                                <option key={pos} value={pos}>
                                  {pos}
                                </option>
                              ))}
                            </select>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              ) : isSetDepthChartStage ? (
                <div className="teamhome-preseason-panelA teamhome-preseason-panelA--depth-chart">
                  {(saveState?.preseason_scrimmage_opponents ?? []).length >= 1 && (
                    <div className="teamhome-scrimmage-upcoming">
                      <span className="teamhome-scrimmage-upcoming-label">Upcoming scrimmages:</span>{' '}
                      {(saveState?.preseason_scrimmage_opponents ?? []).map((s: { opponent?: string; user_home?: boolean }, i: number) => (
                        <span key={i}>
                          {i > 0 && ' · '}
                          Scrimmage {i + 1}: {s.user_home ? `vs ${s.opponent} (H)` : `@ ${s.opponent} (A)`}
                        </span>
                      ))}
                    </div>
                  )}
                  <DepthChartPage
                    saveState={saveState}
                    userTeam={userTeam}
                    isPreseason
                    onSave={async (depthChart) => {
                      await onSimWeek({ depthChart })
                    }}
                  />
                </div>
              ) : isPlaySelectionResultsStage ? (
                <div className="teamhome-preseason-panelA teamhome-preseason-panelA--play-results">
                  <div className="teamhome-play-results">
                  <div className="teamhome-play-results-columns">
                    <div className="teamhome-play-results-col">
                      <div className="teamhome-play-results-heading">OFFENSIVE PLAYBOOK</div>
                      <div className="teamhome-play-results-pct">
                        PERCENT LEARNED :{' '}
                        {learningLoading ? '—' : `${learningSummary?.offensive_pct_learned ?? 0}%`}
                      </div>
                    </div>
                    <div className="teamhome-play-results-col">
                      <div className="teamhome-play-results-heading">DEFENSIVE PLAYBOOK</div>
                      <div className="teamhome-play-results-pct">
                        PERCENT LEARNED :{' '}
                        {learningLoading ? '—' : `${learningSummary?.defensive_pct_learned ?? 0}%`}
                      </div>
                    </div>
                  </div>
                  {!learningLoading && learningSummary?.overall_grade ? (
                    <div className="teamhome-play-results-grade">
                      Team understanding: {learningSummary.overall_grade}
                    </div>
                  ) : null}
                  <button
                    type="button"
                    className="teamhome-play-results-confirm"
                    disabled={confirmingResults || learningLoading}
                    onClick={async () => {
                      setConfirmingResults(true)
                      try {
                        await onSimWeek()
                      } catch (e: any) {
                        onError(e?.message ?? 'Failed to confirm')
                      } finally {
                        setConfirmingResults(false)
                      }
                    }}
                  >
                    {confirmingResults ? 'Confirming…' : 'CONFIRM'}
                  </button>
                  </div>
                </div>
              ) : isSetGoalsStage ? (
                <div className="teamhome-preseason-panelA teamhome-goals-panel">
                  <div className="teamhome-preseason-title">Goal Selection</div>
                  <div className="teamhome-goals-row">
                    <div className="teamhome-goals-col">
                      <div className="teamhome-goals-label">WIN TOTAL</div>
                      <select
                        className="teamhome-goals-select"
                        value={goalWinTotal}
                        onChange={(e) => setGoalWinTotal(Number(e.target.value))}
                      >
                        {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
                          <option key={n} value={n}>
                            {n}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="teamhome-goals-col">
                      <div className="teamhome-goals-label">STAGE REACHED</div>
                      <select
                        className="teamhome-goals-select"
                        value={goalStage}
                        onChange={(e) => setGoalStage(e.target.value)}
                      >
                        {STAGE_GOAL_OPTIONS.map((opt) => (
                          <option key={opt} value={opt}>
                            {opt}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                  <button
                    type="button"
                    className="teamhome-goals-confirm"
                    disabled={confirmingGoals}
                    onClick={async () => {
                      setConfirmingGoals(true)
                      try {
                        await onSimWeek({ goals: { win_goal: goalWinTotal, stage_goal: goalStage } })
                      } catch (e: any) {
                        onError(e?.message ?? 'Failed to confirm goals')
                      } finally {
                        setConfirmingGoals(false)
                      }
                    }}
                  >
                    {confirmingGoals ? 'Confirming…' : 'CONFIRM'}
                  </button>
                </div>
              ) : isScrimmageStage ? (
                <ScrimmagePanel
                  currentStage={preseasonCurrentStage}
                  scrimmages={saveState?.preseason_scrimmages ?? []}
                  opponents={saveState?.preseason_scrimmage_opponents ?? []}
                  onSimulate={async () => {
                    await onSimWeek({ forcePreseasonAdvance: true })
                  }}
                  onPlay={async () => {
                    if (!saveId || !headers) return
                    const scrimIdx = preseasonCurrentStage === 'Scrimmage 1' ? 0 : 1
                    const r = isLocalBundle
                      ? await fetch(`${apiBase}/sim/game/start`, {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ state: saveState, context: 'scrimmage', scrimmage_index: scrimIdx }),
                        })
                      : await fetch(`${apiBase}/saves/${saveId}/start-coach-game`, {
                          method: 'POST',
                          headers: { ...headers, 'Content-Type': 'application/json' },
                          body: JSON.stringify({ context: 'scrimmage', scrimmage_index: scrimIdx }),
                        })
                    if (!r.ok) {
                      const err = await r.text()
                      onError(err || 'Failed to start game')
                      return
                    }
                    const data = await r.json()
                    setActiveGame({
                      gameId: isLocalBundle ? '__local_game__' : data.game_id,
                      homeTeam: data.home_team_name,
                      awayTeam: data.away_team_name,
                      userTeam: data.user_team_name,
                      initialState: isLocalBundle ? { ...data.state, __game: data.game } : data.state,
                      gameContext: 'scrimmage',
                      scrimmageStage: preseasonCurrentStage,
                    })
                  }}
                />
              ) : (
                <div className="teamhome-preseason-panelA">
                  <div className="teamhome-preseason-title">Panel A</div>
                  <div className="teamhome-preseason-sub">Stage {preseasonStageNumber}</div>
                  <div className="teamhome-preseason-stage">{preseasonCurrentStage || 'Playbook Select'}</div>
                </div>
              )}

              <div className="teamhome-preseason-stages">
                <div className="teamhome-preseason-title">Off-season stages</div>
                <div className="teamhome-preseason-stage-list">
                  {preseasonStages.map((s: string, i: number) => (
                    <div
                      key={`${s}-${i}`}
                      className={`teamhome-preseason-stage-item ${i === preseasonStageIndex ? 'active' : i < preseasonStageIndex ? 'done' : ''}`}
                    >
                      Stage {i + 1}: {displayOffseasonStageLabel(s)}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="teamhome-preseason-bottom">
              <div className="teamhome-preseason-panelD">
                <div className="teamhome-preseason-title">News wire</div>
                <NewsFeedPanel limit={5} compact />
              </div>

              <div className="teamhome-preseason-panelC">
                <div className="teamhome-preseason-title">Panel C</div>
                <div className="teamhome-preseason-sub">Team stats</div>
                <div className="teamhome-preseason-stat-list">
                  <div>Offensive PPG</div>
                  <div>Defensive PPG</div>
                  <div>Explosives per game</div>
                  <div>Total yards per game</div>
                  <div>Rushing per game</div>
                  <div>Passing per game</div>
                  <div>Defensive total yards</div>
                  <div>Defensive rushing yards</div>
                  <div>Defensive passing yards</div>
                  <div>Turnovers</div>
                </div>
              </div>
            </div>
          </div>
          )
        ) : phase === 'playoffs' ? (
          stateMenu !== 'Dashboard' && leagueStatePanel ? (
            <div className="teamhome-roster-shell teamhome-playoffs-league-view">{leagueStatePanel}</div>
          ) : teamMenu !== PLAYOFF_BRACKET_MENU ? (
            renderTeamMenuPanel()
          ) : (
              <div className="teamhome-playoffs-shell">
                <div className="teamhome-card teamhome-card-dark" style={{ marginBottom: 14 }}>
                  <div className="teamhome-card-title">Playoffs (8 teams)</div>
                  <div className="teamhome-small" style={{ marginBottom: 10 }}>
                    {playoffView.completed
                      ? `Champion: ${playoffView.champion || '—'}`
                      : 'Use Continue (top right) to run one round at a time — quarterfinals, then semifinals, then the championship.'}
                  </div>
                  <div className="teamhome-actions-grid">
                    <button
                      type="button"
                      className="teamhome-action-btn"
                      disabled={!saveId || playingWeek || !canCoachPlayoffGame}
                      onClick={async () => {
                        if (!saveId || !headers) return
                        setPlayingWeek(true)
                        try {
                          const r = isLocalBundle
                            ? await fetch(`${apiBase}/sim/game/start`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ state: saveState, context: 'playoff' }),
                              })
                            : await fetch(`${apiBase}/saves/${saveId}/start-coach-game`, {
                                method: 'POST',
                                headers: { ...headers, 'Content-Type': 'application/json' },
                                body: JSON.stringify({ context: 'playoff' }),
                              })
                          if (!r.ok) {
                            const errText = await r.text()
                            let errMsg = 'Failed to start game'
                            try {
                              const j = JSON.parse(errText)
                              errMsg = (j?.detail ?? errText) || errMsg
                            } catch {
                              errMsg = errText || errMsg
                            }
                            onError(typeof errMsg === 'string' ? errMsg : JSON.stringify(errMsg))
                            return
                          }
                          const data = await r.json()
                          if ((!isLocalBundle && (!data?.game_id || !data?.state)) || (isLocalBundle && (!data?.game || !data?.state))) {
                            onError('Invalid response from server')
                            return
                          }
                          onError('')
                          setActiveGame({
                            gameId: isLocalBundle ? '__local_game__' : data.game_id,
                            homeTeam: data.home_team_name,
                            awayTeam: data.away_team_name,
                            userTeam: data.user_team_name,
                            initialState: isLocalBundle ? { ...data.state, __game: data.game } : data.state,
                            gameContext: 'playoff',
                          })
                        } catch (e: any) {
                          onError(e?.message ?? 'Failed to start game')
                        } finally {
                          setPlayingWeek(false)
                        }
                      }}
                    >
                      {playingWeek ? 'Loading…' : 'Play game'}
                      <span className="teamhome-action-sub">Coach your playoff game play-by-play</span>
                    </button>
                    <button
                      type="button"
                      className="teamhome-action-btn"
                      disabled={
                        !saveId ||
                        Boolean(saveState?.playoffs?.completed) ||
                        anyPlayoffGamesStarted(saveState)
                      }
                      onClick={async () => {
                        try {
                          await onSimWeek({ playoffsSim: true })
                        } catch (e: any) {
                          onError(e?.message ?? 'Playoff simulation failed')
                        }
                      }}
                    >
                      Sim entire bracket
                      <span className="teamhome-action-sub">
                        Only before any playoff games are played — runs QF, SF, and championship at once
                      </span>
                    </button>
                    <button
                      type="button"
                      className="teamhome-action-btn"
                      disabled={!saveId || !saveState?.playoffs?.completed}
                      onClick={async () => {
                        try {
                          await onSimWeek({ seasonFinish: true })
                        } catch (e: any) {
                          onError(e?.message ?? 'Failed to finish season')
                        }
                      }}
                    >
                      Finish season
                      <span className="teamhome-action-sub">
                        Archives standings to league history and opens the season summary (use Begin offseason there for
                        Graduation)
                      </span>
                    </button>
                  </div>
                </div>

                <div
                  className="teamhome-playoffs-bracket-header"
                  style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 12,
                    marginBottom: 8,
                  }}
                >
                  <div className="teamhome-playoffs-bracket-label" style={{ marginBottom: 0 }}>
                    Bracket
                  </div>
                  {playoffClassOptions.length > 1 ? (
                    <label className="teamhome-playoffs-class-label" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span className="teamhome-small" style={{ marginBottom: 0 }}>
                        Class
                      </span>
                      <select
                        className="teamhome-select"
                        value={selectPlayoffClassValue}
                        onChange={(e) => {
                          const v = e.target.value
                          setPlayoffBracketClass(v)
                          try {
                            sessionStorage.setItem(`fnd.playoff.viewClass.${saveId}`, v)
                          } catch {
                            /* ignore */
                          }
                        }}
                        aria-label="Playoff classification bracket"
                      >
                        {playoffClassOptions.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                    </label>
                  ) : playoffClassOptions.length === 1 ? (
                    <div className="teamhome-small" style={{ marginBottom: 0, opacity: 0.85 }}>
                      Class: <strong>{playoffClassOptions[0]}</strong>
                    </div>
                  ) : null}
                </div>
                {playoffView.missingBracket ? (
                  <div className="teamhome-card teamhome-card-dark" style={{ marginBottom: 0 }}>
                    <div className="teamhome-small">
                      No playoff bracket for this class. An 8-team bracket exists only when at least eight teams are in that classification.
                    </div>
                  </div>
                ) : (
                  <div className="teamhome-playoffs-grid" key={`playoff-bracket-${bracketClassForView}`}>
                  <div className="teamhome-card">
                    <div className="teamhome-card-title">Quarterfinals</div>
                    <div className="teamhome-playoffs-list">
                      {playoffView.qfPairs.map((m) => {
                        const played = findQfGame(playoffView.qf, m)
                        const playedHomeScore =
                          played == null ? null : played?.home === m.home ? played?.home_score : played?.away_score
                        const playedAwayScore =
                          played == null ? null : played?.home === m.home ? played?.away_score : played?.home_score
                        const exportHome = played?.home ?? m.home
                        const exportAway = played?.away ?? m.away
                        return (
                          <div key={`${m.home}-${m.away}`} className="teamhome-playoffs-row teamhome-playoffs-row--stacked">
                            <div className="teamhome-playoffs-matchup">
                              {renderPlayoffBracketLine(m.home, playedHomeScore, {
                                playoffSeed: playoffSeedForTeam(playoffView.seeds, m.home),
                              })}
                              {renderPlayoffBracketLine(m.away, playedAwayScore, {
                                playoffSeed: playoffSeedForTeam(playoffView.seeds, m.away),
                              })}
                            </div>
                            <div className="teamhome-playoffs-footer">
                              <div className="teamhome-playoffs-actions">
                                <button
                                  type="button"
                                  className="teamhome-playoffs-link"
                                  disabled={!played}
                                  onClick={async () => {
                                    try {
                                      await downloadPlayoffText(
                                        'Quarterfinal',
                                        exportHome,
                                        exportAway,
                                        'box-score',
                                        playoffView.viewClass,
                                      )
                                    } catch (e: any) {
                                      onError(e?.message ?? 'Failed to export box score')
                                    }
                                  }}
                                >
                                  Box score
                                </button>
                                <button
                                  type="button"
                                  className="teamhome-playoffs-link"
                                  disabled={!played}
                                  onClick={async () => {
                                    try {
                                      await downloadPlayoffText(
                                        'Quarterfinal',
                                        exportHome,
                                        exportAway,
                                        'game-log',
                                        playoffView.viewClass,
                                      )
                                    } catch (e: any) {
                                      onError(e?.message ?? 'Failed to export game log')
                                    }
                                  }}
                                >
                                  Game log
                                </button>
                              </div>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                  <div className="teamhome-card">
                    <div className="teamhome-card-title">Semifinals</div>
                    <div className="teamhome-playoffs-list">
                      {playoffView.sfRows.map((g: any, i: number) => (
                        <div key={`sf-${i}-${g.home}-${g.away}`} className="teamhome-playoffs-row teamhome-playoffs-row--stacked">
                          <div className="teamhome-playoffs-matchup">
                            {renderPlayoffBracketLine(String(g.home), g.home_score, {
                              playoffSeed: playoffSeedForTeam(playoffView.seeds, String(g.home)),
                            })}
                            {renderPlayoffBracketLine(String(g.away), g.away_score, {
                              playoffSeed: playoffSeedForTeam(playoffView.seeds, String(g.away)),
                            })}
                          </div>
                          <div className="teamhome-playoffs-footer">
                            <div className="teamhome-playoffs-actions">
                              <button
                                type="button"
                                className="teamhome-playoffs-link"
                                disabled={g.home_score == null}
                                onClick={async () => {
                                  try {
                                    await downloadPlayoffText(
                                      'Semifinal',
                                      g.home,
                                      g.away,
                                      'box-score',
                                      playoffView.viewClass,
                                    )
                                  } catch (e: any) {
                                    onError(e?.message ?? 'Failed to export box score')
                                  }
                                }}
                              >
                                Box score
                              </button>
                              <button
                                type="button"
                                className="teamhome-playoffs-link"
                                disabled={g.home_score == null}
                                onClick={async () => {
                                  try {
                                    await downloadPlayoffText(
                                      'Semifinal',
                                      g.home,
                                      g.away,
                                      'game-log',
                                      playoffView.viewClass,
                                    )
                                  } catch (e: any) {
                                    onError(e?.message ?? 'Failed to export game log')
                                  }
                                }}
                              >
                                Game log
                              </button>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="teamhome-card">
                    <div className="teamhome-card-title">Championship</div>
                    <div className="teamhome-playoffs-list">
                      {playoffView.chRow ? (
                        <div
                          key={`ch-${playoffView.chRow.home}-${playoffView.chRow.away}`}
                          className="teamhome-playoffs-row teamhome-playoffs-row--stacked"
                        >
                          <div className="teamhome-playoffs-matchup">
                            {renderPlayoffBracketLine(String(playoffView.chRow.home), playoffView.chRow.home_score, {
                              playoffSeed: playoffSeedForTeam(playoffView.seeds, String(playoffView.chRow.home)),
                            })}
                            {renderPlayoffBracketLine(String(playoffView.chRow.away), playoffView.chRow.away_score, {
                              playoffSeed: playoffSeedForTeam(playoffView.seeds, String(playoffView.chRow.away)),
                            })}
                          </div>
                          <div className="teamhome-playoffs-footer">
                            <div className="teamhome-playoffs-actions">
                              <button
                                type="button"
                                className="teamhome-playoffs-link"
                                disabled={playoffView.chRow.home_score == null}
                                onClick={async () => {
                                  try {
                                    await downloadPlayoffText(
                                      'Championship',
                                      playoffView.chRow!.home,
                                      playoffView.chRow!.away,
                                      'box-score',
                                      playoffView.viewClass,
                                    )
                                  } catch (e: any) {
                                    onError(e?.message ?? 'Failed to export box score')
                                  }
                                }}
                              >
                                Box score
                              </button>
                              <button
                                type="button"
                                className="teamhome-playoffs-link"
                                disabled={playoffView.chRow.home_score == null}
                                onClick={async () => {
                                  try {
                                    await downloadPlayoffText(
                                      'Championship',
                                      playoffView.chRow!.home,
                                      playoffView.chRow!.away,
                                      'game-log',
                                      playoffView.viewClass,
                                    )
                                  } catch (e: any) {
                                    onError(e?.message ?? 'Failed to export game log')
                                  }
                                }}
                              >
                                Game log
                              </button>
                            </div>
                          </div>
                        </div>
                      ) : null}
                    </div>
                  </div>
                </div>
                )}
              </div>
          )
        ) : phase === 'offseason' ? (
          stateMenu !== 'Dashboard' && leagueStatePanel ? (
            <div className="teamhome-roster-shell teamhome-playoffs-league-view">{leagueStatePanel}</div>
          ) : teamMenu !== OFFSEASON_TEAM_HUB ? (
            renderTeamMenuPanel()
          ) : (
          <div className="teamhome-preseason-shell">
            <div className="teamhome-preseason-top teamhome-preseason-top--offseason-single">
              <div className="teamhome-preseason-panelA">
                {offseasonCurrentStage === 'Graduation' ? (
                  <>
                    {/** Graduation */}
                    <div className="teamhome-preseason-title">Graduation</div>
                    <div className="teamhome-preseason-sub">
                      Players who left the program at the end of the school year (before the new season roster).
                    </div>
                    <div
                      style={{
                        marginTop: 14,
                        maxHeight: 'min(480px, 65vh)',
                        overflow: 'auto',
                        textAlign: 'left',
                      }}
                    >
                      {Object.keys(saveState?.offseason_graduation_report ?? {}).length === 0 ? (
                        <div className="teamhome-preseason-sub">No graduation data on file for this year rollover.</div>
                      ) : (
                        <>
                          <div className="teamhome-schedule-weekbar" style={{ marginBottom: 12 }}>
                            <span className="teamhome-schedule-week-label">Team</span>
                            <select
                              className="teamhome-select teamhome-schedule-week-select"
                              value={graduationViewTeam}
                              onChange={(e) => setGraduationReportTeam(e.target.value)}
                              disabled={graduationReportTeamNames.length < 1}
                              aria-label="Graduation report team"
                            >
                              {graduationReportTeamNames.map((name) => (
                                <option key={name} value={name}>
                                  {name}
                                </option>
                              ))}
                            </select>
                            <span className="teamhome-schedule-week-hint">Graduates for the selected program</span>
                          </div>
                          <div>
                            {!graduationViewTeam ? (
                              <div className="teamhome-preseason-sub">No teams in this report.</div>
                            ) : !graduationPlayersForView.length ? (
                              <div className="teamhome-small">No graduates</div>
                            ) : (
                              <table className="teamhome-roster-table" style={{ width: '100%', marginTop: 8 }}>
                                <thead>
                                  <tr>
                                    <th style={{ textAlign: 'left' }}>Name</th>
                                    <th>Pos</th>
                                    <th>Year</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {graduationPlayersForView.map((p: any, i: number) => (
                                    <tr key={`${graduationViewTeam}-${p?.name ?? i}-${i}`}>
                                      <td>
                                        <PlayerProfileName
                                          teamName={graduationViewTeam}
                                          playerName={p?.name}
                                          as="span"
                                        />
                                      </td>
                                      <td>{p?.position ?? 'ΓÇö'}</td>
                                      <td>{formatPlayerYear(p?.year)}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            )}
                          </div>
                        </>
                      )}
                    </div>
                  </>
                ) : offseasonCurrentStage === 'Coach development' ? (
                  <>
                    <div className="teamhome-preseason-title">Coach development</div>
                    <div className="teamhome-preseason-sub" style={{ marginTop: 8, maxWidth: 760 }}>
                      Allocate CP by attribute. Levels are automatic from thresholds; they increase or decrease as allocated CP crosses
                      each tier.
                    </div>
                    <div style={{ marginTop: 12, textAlign: 'left', maxWidth: 860 }}>
                      <div className="teamhome-small">
                        Total CP: <b>{coachDevTotalCp.toFixed(1)}</b>
                      </div>
                      <div className="teamhome-small">
                        Allocated CP: <b>{coachDevAllocatedCp.toFixed(1)}</b>
                      </div>
                      <div className="teamhome-small" style={{ color: coachDevAvailableCp < 0 ? '#7f1d1d' : undefined }}>
                        Available CP: <b>{coachDevAvailableCp.toFixed(1)}</b>
                      </div>
                    </div>
                    <div style={{ marginTop: 12, textAlign: 'left', width: '100%', maxWidth: 940 }}>
                      <table className="teamhome-roster-table" style={{ width: '100%' }}>
                        <thead>
                          <tr>
                            <th style={{ textAlign: 'left' }}>Attribute</th>
                            <th>Level</th>
                            <th>Allocated CP</th>
                            <th>Next Level</th>
                            <th style={{ textAlign: 'center' }}>Adjust</th>
                          </tr>
                        </thead>
                        <tbody>
                          {COACH_DEV_SKILLS.map(({ key, label }) => {
                            const cp = Number(coachDevAllocations[key] ?? 0)
                            const lv = coachDevLevelFromCp(cp)
                            const curTh = COACH_DEV_THRESHOLDS[lv] ?? 0
                            const nextTh = coachDevNextThreshold(lv)
                            return (
                              <tr key={key}>
                                <td>{label}</td>
                                <td>{lv}</td>
                                <td>{cp.toFixed(1)}</td>
                                <td>{nextTh == null ? 'Maxed' : `${curTh} -> ${nextTh}`}</td>
                                <td style={{ textAlign: 'center' }}>
                                  <button
                                    type="button"
                                    className="teamhome-select"
                                    style={{ marginRight: 8 }}
                                    onClick={() =>
                                      setCoachDevAllocations((prev) => ({
                                        ...prev,
                                        [key]: Math.max(0, Math.round((Number(prev[key] ?? 0) - 5) * 10) / 10),
                                      }))
                                    }
                                  >
                                    -
                                  </button>
                                  <button
                                    type="button"
                                    className="teamhome-select"
                                    onClick={() =>
                                      setCoachDevAllocations((prev) => ({
                                        ...prev,
                                        [key]: Math.round((Number(prev[key] ?? 0) + 5) * 10) / 10,
                                      }))
                                    }
                                  >
                                    +
                                  </button>
                                </td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                  </>
                ) : offseasonCurrentStage === 'Improvements' ? (
                  <>
                    <div className="teamhome-preseason-title">Program development</div>
                    <div className="teamhome-preseason-sub teamhome-improvements-lead">
                      Use <b>− / +</b> (5 PP per click) or drag each <b>pillar slider</b> to invest your flex <b>program points (PP)</b> into
                      that program track. You can sit
                      between full grades (partial progress) so the program moves smoothly — level-ups still happen when you cross the
                      PP thresholds from the in-season system. Use <b>Continue</b> to apply and advance.
                    </div>

                    <div className="teamhome-improvements-wrap">
                      <div className="teamhome-improvements-metrics">
                        <div className="teamhome-improvements-metric teamhome-improvements-metric--total">
                          <div className="teamhome-improvements-metric-label">Total program points</div>
                          <div className="teamhome-improvements-metric-value">{improvementsBudget.ppTotal}</div>
                          <div className="teamhome-improvements-metric-hint">In your offseason PP bank</div>
                        </div>
                        <div className="teamhome-improvements-metric teamhome-improvements-metric--bank">
                          <div className="teamhome-improvements-metric-label">Unspent PP</div>
                          <div
                            className={`teamhome-improvements-metric-value ${
                              improvementsBudget.ppRemaining <= 0 ? 'teamhome-improvements-num--warn' : 'teamhome-improvements-num--cyan'
                            }`}
                          >
                            {improvementsBudget.ppRemaining}
                          </div>
                          <div className="teamhome-improvements-metric-hint">Available before pillar changes</div>
                        </div>
                        <div className="teamhome-improvements-metric teamhome-improvements-metric--projected">
                          <div className="teamhome-improvements-metric-label">After Continue (projected)</div>
                          <div
                            className={`teamhome-improvements-metric-value ${
                              improvementsBudget.projectedRemaining < 0
                                ? 'teamhome-improvements-num--bad'
                                : improvementsBudget.projectedRemaining === improvementsBudget.ppRemaining
                                  ? 'teamhome-improvements-num--muted'
                                  : 'teamhome-improvements-num--good'
                            }`}
                          >
                            {improvementsBudget.projectedRemaining}
                          </div>
                          <div className="teamhome-improvements-metric-hint">
                            Net from pillar picks:{' '}
                            <strong className={improvementsBudget.deltaPp < 0 ? 'teamhome-improvements-num--bad' : improvementsBudget.deltaPp > 0 ? 'teamhome-improvements-num--good' : 'teamhome-improvements-num--muted'}>
                              {formatProgramPpDelta(improvementsBudget.deltaPp)}
                            </strong>
                          </div>
                        </div>
                      </div>

                      <div className="teamhome-improvements-ledger">
                        <div className="teamhome-improvements-ledger-head">
                          <span className="teamhome-improvements-ledger-title">Last season</span>
                          {improvementsSeasonLedger ? (
                            <span className="teamhome-improvements-ledger-record">
                              {improvementsSeasonLedger.wins}-{improvementsSeasonLedger.losses}
                            </span>
                          ) : null}
                        </div>
                        {improvementsSeasonLedger ? (
                          <>
                            <p className="teamhome-improvements-ledger-summary">
                              How your PP bank was credited from the season that just ended — wins and margins add PP; missed goals
                              subtract.
                            </p>
                            <ul className="teamhome-improvements-ledger-rows">
                              <li>
                                <span>Regular season (per game margins)</span>
                                <span
                                  className={
                                    improvementsSeasonLedger.rs > 0
                                      ? 'teamhome-improvements-num--good'
                                      : improvementsSeasonLedger.rs < 0
                                        ? 'teamhome-improvements-num--bad'
                                        : 'teamhome-improvements-num--muted'
                                  }
                                >
                                  {formatProgramPpDelta(improvementsSeasonLedger.rs)}
                                </span>
                              </li>
                              <li>
                                <span>Playoff wins</span>
                                <span
                                  className={
                                    improvementsSeasonLedger.playoffWinPp > 0
                                      ? 'teamhome-improvements-num--amber'
                                      : 'teamhome-improvements-num--muted'
                                  }
                                >
                                  {formatProgramPpDelta(improvementsSeasonLedger.playoffWinPp)}
                                </span>
                              </li>
                              <li>
                                <span className="teamhome-improvements-ledger-cap">{improvementsSeasonLedger.placementLabel}</span>
                                <span
                                  className={
                                    improvementsSeasonLedger.placementPp > 0
                                      ? 'teamhome-improvements-num--amber'
                                      : 'teamhome-improvements-num--muted'
                                  }
                                >
                                  {formatProgramPpDelta(improvementsSeasonLedger.placementPp)}
                                </span>
                              </li>
                              <li>
                                <span>
                                  Goal penalties
                                  {improvementsSeasonLedger.goalFails > 0 ? (
                                    <span className="teamhome-improvements-ledger-sub">
                                      {' '}
                                      ({improvementsSeasonLedger.goalFails} missed)
                                    </span>
                                  ) : null}
                                </span>
                                <span
                                  className={
                                    improvementsSeasonLedger.goalPts < 0
                                      ? 'teamhome-improvements-num--bad'
                                      : 'teamhome-improvements-num--muted'
                                  }
                                >
                                  {formatProgramPpDelta(improvementsSeasonLedger.goalPts)}
                                </span>
                              </li>
                              <li className="teamhome-improvements-ledger-net">
                                <span>Net PP credited</span>
                                <span className="teamhome-improvements-num--highlight">
                                  {formatProgramPpDelta(improvementsSeasonLedger.net)}
                                </span>
                              </li>
                            </ul>
                          </>
                        ) : (
                          <p className="teamhome-improvements-ledger-empty teamhome-small">
                            Season PP breakdown is not on file for this save (older export or pre-update). Your bank totals still
                            apply.
                          </p>
                        )}
                      </div>

                      <div className="teamhome-improvements-sliders">
                        {improvementsBudget.pillars.map((row) => {
                          const setC = (v: number) => {
                            const x = Math.max(0, Math.min(PILLAR_CUMULATIVE_PP_MAX, Math.round(v)))
                            if (row.id === 'facilities') setImproveFacCumulative(x)
                            else if (row.id === 'culture') setImproveCulCumulative(x)
                            else setImproveBooCumulative(x)
                          }
                          const pct = PILLAR_CUMULATIVE_PP_MAX > 0 ? (row.targetCumulative / PILLAR_CUMULATIVE_PP_MAX) * 100 : 0
                          return (
                            <div
                              key={row.id}
                              className="teamhome-improvements-slider-row"
                              style={{ borderLeftColor: row.accent }}
                            >
                              <div className="teamhome-improvements-slider-head">
                                <span className="teamhome-improvements-slider-title">{row.label}</span>
                                <span className="teamhome-improvements-slider-meter">{formatPillarMeter(row.targetCumulative)}</span>
                              </div>
                              <div className="teamhome-improvements-slider-track-wrap" aria-hidden>
                                <div
                                  className="teamhome-improvements-slider-track-fill"
                                  style={{
                                    width: `${pct}%`,
                                    background: `linear-gradient(90deg, ${row.accent}99, ${row.accent})`,
                                  }}
                                />
                              </div>
                              <div className="teamhome-improvements-slider-controls">
                                <button
                                  type="button"
                                  className="teamhome-improvements-step-btn"
                                  onClick={() => setC(row.targetCumulative - PILLAR_SLIDER_STEP)}
                                  disabled={row.targetCumulative <= 0}
                                  aria-label={`Decrease ${row.label} investment by ${PILLAR_SLIDER_STEP} PP`}
                                >
                                  −
                                </button>
                                <input
                                  type="range"
                                  className="teamhome-improvements-range"
                                  min={0}
                                  max={PILLAR_CUMULATIVE_PP_MAX}
                                  step={PILLAR_SLIDER_STEP}
                                  value={row.targetCumulative}
                                  onChange={(e) => setC(Number(e.target.value))}
                                  aria-label={`${row.label} program investment`}
                                  aria-valuemin={0}
                                  aria-valuemax={PILLAR_CUMULATIVE_PP_MAX}
                                  aria-valuenow={row.targetCumulative}
                                />
                                <button
                                  type="button"
                                  className="teamhome-improvements-step-btn"
                                  onClick={() => setC(row.targetCumulative + PILLAR_SLIDER_STEP)}
                                  disabled={row.targetCumulative >= PILLAR_CUMULATIVE_PP_MAX}
                                  aria-label={`Increase ${row.label} investment by ${PILLAR_SLIDER_STEP} PP`}
                                >
                                  +
                                </button>
                              </div>
                              <div className="teamhome-improvements-slider-meta">
                                <span className="teamhome-small">
                                  PP vs current:{' '}
                                  <strong
                                    className={
                                      row.pillarDeltaPp < 0
                                        ? 'teamhome-improvements-num--bad'
                                        : row.pillarDeltaPp > 0
                                          ? 'teamhome-improvements-num--good'
                                          : 'teamhome-improvements-num--muted'
                                    }
                                  >
                                    {formatProgramPpDelta(row.pillarDeltaPp)}
                                  </strong>{' '}
                                  (negative spends bank)
                                </span>
                                <span className="teamhome-improvements-slider-scale teamhome-small">
                                  0 — {PILLAR_CUMULATIVE_PP_MAX} PP · ±{PILLAR_SLIDER_STEP} per click or slider step
                                </span>
                              </div>
                            </div>
                          )
                        })}
                      </div>

                      {saveState?.offseason_improvements_bank?.breakdown ? (
                        <details className="teamhome-improvements-details">
                          <summary className="teamhome-improvements-details-summary">Full PP breakdown &amp; legacy fields</summary>
                          <div className="teamhome-improvements-details-body teamhome-small">
                            <div>
                              Total Improvements PP earned:{' '}
                              <b>{Number(saveState.offseason_improvements_bank.breakdown.pp_total ?? 0)}</b>
                            </div>
                            {(saveState.offseason_improvements_bank.breakdown as any).regular_season_pp != undefined ? (
                              <>
                                <div style={{ marginTop: 6 }}>
                                  Regular season (margin-based wins/losses):{' '}
                                  <b>{Number((saveState.offseason_improvements_bank.breakdown as any).regular_season_pp ?? 0)}</b>
                                </div>
                                <div style={{ marginTop: 4 }}>
                                  Playoff victories (
                                  {(saveState.offseason_improvements_bank.breakdown as any).playoff_wins ?? 0} ×{' '}
                                  {(saveState.offseason_improvements_bank.breakdown as any).playoff_win_pp_each ?? 20} PP):{' '}
                                  <b>
                                    {Number((saveState.offseason_improvements_bank.breakdown as any).playoff_win_pp_total ?? 0)}
                                  </b>
                                </div>
                                <div style={{ marginTop: 4 }}>
                                  Placement bonus (
                                  {(saveState.offseason_improvements_bank.breakdown as any).placement_bonus_label || 'none'}
                                  ):{' '}
                                  <b>
                                    {Number((saveState.offseason_improvements_bank.breakdown as any).placement_bonus_pp ?? 0)}
                                  </b>
                                </div>
                              </>
                            ) : null}
                            {(saveState.offseason_improvements_bank.breakdown as any).expectations_auto_each_pillar !==
                              undefined ||
                            (saveState.offseason_improvements_bank.breakdown as any).decay_each_pillar !== undefined ? (
                              <div style={{ marginTop: 6 }}>
                                Season-end pillar auto (legacy snapshot): expectations{' '}
                                <b>{String(saveState.offseason_improvements_bank.breakdown.expectations_label ?? '—')}</b>, Δ
                                pillar each{' '}
                                <b>
                                  {Number(saveState.offseason_improvements_bank.breakdown.expectations_auto_each_pillar ?? 0)}
                                </b>
                                , postseason bar pts{' '}
                                <b>{Number(saveState.offseason_improvements_bank.breakdown.postseason_points_total ?? 0)}</b>,
                                decay <b>{Number(saveState.offseason_improvements_bank.breakdown.decay_each_pillar ?? 0)}</b>
                                {(saveState.offseason_improvements_bank.breakdown as any).goal_fail_count ? (
                                  <>
                                    {' '}
                                    , goals missed{' '}
                                    <b>{Number((saveState.offseason_improvements_bank.breakdown as any).goal_fail_count)}</b>
                                  </>
                                ) : null}
                              </div>
                            ) : null}
                            {(saveState.offseason_improvements_bank.breakdown as any).goal_fail_count ? (
                              <div style={{ marginTop: 4 }}>
                                Goal miss PP:{' '}
                                <b>
                                  {typeof (saveState.offseason_improvements_bank.breakdown as any).goal_points === 'number'
                                    ? Number((saveState.offseason_improvements_bank.breakdown as any).goal_points).toFixed(0)
                                    : String((saveState.offseason_improvements_bank.breakdown as any).goal_points ?? 0)}
                                </b>{' '}
                                × missed facets{' '}
                                <b>{Number((saveState.offseason_improvements_bank.breakdown as any).goal_fail_count)}</b>
                              </div>
                            ) : null}
                          </div>
                        </details>
                      ) : null}

                      {improvementsBudget.invalid ? (
                        <div className="teamhome-improvements-alert teamhome-improvements-alert--error" role="alert">
                          <b>PP overspent.</b> These levels would drop your PP bank to{' '}
                          <b>{improvementsBudget.projectedRemaining}</b> ({improvementsBudget.ppRemaining} now
                          {improvementsBudget.deltaPp !== 0 ? (
                            <>
                              , net from pillar picks <b>{improvementsBudget.deltaPp > 0 ? '+' : ''}</b>
                              <b>{improvementsBudget.deltaPp}</b>
                            </>
                          ) : null}
                          ). You need <b>{improvementsBudget.shortfall}</b> more PP to afford this combo — lower a grade or pick
                          fewer upgrades. <b>Continue</b> stays off until this balances.
                        </div>
                      ) : (
                        <div className="teamhome-improvements-foot">
                          {improvementsBudget.ppRemaining !== improvementsBudget.projectedRemaining ? (
                            <span>
                              Pillar picks change your bank by{' '}
                              <strong className="teamhome-improvements-num--good">
                                {formatProgramPpDelta(improvementsBudget.deltaPp)}
                              </strong>{' '}
                              PP until you confirm with <b>Continue</b> (projected balance{' '}
                              <strong className="teamhome-improvements-num--cyan">{improvementsBudget.projectedRemaining}</strong>).
                            </span>
                          ) : (
                            <span>
                              Match target levels to current grades for no PP movement, or change targets to spend or refund PP.
                            </span>
                          )}
                        </div>
                      )}
                      <div className="teamhome-improvements-hint teamhome-small">
                        {improvementsBudget.invalid ? (
                          <>Fix PP above, then use Continue.</>
                        ) : (
                          <>Use Continue to lock in pillar grades and advance.</>
                        )}
                      </div>
                    </div>
                  </>
                ) : isCoachingCarouselStage ? (
                  <div className="teamhome-coaching-carousel-panel">
                    <div className="teamhome-preseason-title">{offseasonCurrentStage}</div>
                    {isCoachingCarouselSummaryStage ? (
                      <div className="teamhome-preseason-sub">
                        Coaching carousel recap for the offseason that just finished. This summary is archived under{' '}
                        <b>State ΓåÆ Coaching changes</b> for that season year.
                      </div>
                    ) : offseasonCurrentStage === 'Coaching carousel I' ? (
                      <div className="teamhome-preseason-sub">
                        Openings after retirements and firings are locked in below. Rank head-coach jobs you want your coach to
                        pursue, then Continue to run the first hiring wave.
                      </div>
                    ) : (
                      <div className="teamhome-preseason-sub">
                        Update applications if brand-new openings formed (promotions/poaching), then Continue for the next hiring
                        wave. Stage IV is a league-wide summary.
                      </div>
                    )}
                    <div style={{ marginTop: 14, textAlign: 'left' }}>
                      {isCoachingCarouselSummaryStage ? (
                        (() => {
                          const summ = saveState?.offseason_coaching_changes_summary as
                            | {
                                headline?: string
                                bullets?: string[]
                                counts?: Record<string, number>
                              }
                            | undefined
                          if (!summ?.headline && !(summ?.bullets && summ.bullets.length)) {
                            return (
                              <div className="teamhome-small" style={{ marginBottom: 10 }}>
                                Summary will appear once you finish stage III ΓÇö if this is stuck empty, Continue once more from{' '}
                                <b>stage III</b>.
                              </div>
                            )
                          }
                          const counts = summ?.counts ?? {}
                          return (
                            <div style={{ marginBottom: 16 }}>
                              {summ.headline ? (
                                <div className="teamhome-small" style={{ marginBottom: 12, fontWeight: 700 }}>
                                  {summ.headline}
                                </div>
                              ) : null}
                              <div className="teamhome-small" style={{ marginBottom: 8, opacity: 0.88 }}>
                                {Object.keys(counts).length > 0
                                  ? ['retirement', 'resignation', 'firing', 'hire', 'promotion', 'application_hire', 'scheme_change']
                                      .filter((k) => Number(counts[k] ?? 0) > 0)
                                      .map((k) => `${k.replace(/_/g, ' ')}: ${counts[k]}`)
                                      .join(' ┬╖ ')
                                  : null}
                              </div>
                              <div className="teamhome-small" style={{ opacity: 0.9, marginBottom: 8 }}>
                                Highlights:
                              </div>
                              <ul
                                className="teamhome-coaching-events teamhome-coaching-carousel-marquee"
                                style={{ textAlign: 'left', paddingLeft: 18, maxHeight: 360, overflow: 'auto' }}
                              >
                                {(summ?.bullets ?? []).map((line: string, i: number) => (
                                  <li key={`ccs-${i}`} className="teamhome-carousel-event-item" style={{ marginBottom: 6 }}>
                                    {line}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )
                        })()
                      ) : null}
                      {!isCoachingCarouselSummaryStage && userTeam && findTeam(saveState, userTeam)?.coach
                        ? (() => {
                            const blob = saveState?.offseason_coach_carousel as { vacancies?: string[] } | undefined
                            const vacancySet = new Set(
                              (Array.isArray(blob?.vacancies) ? blob.vacancies : [])
                                .map((x: unknown) => String(x ?? '').trim())
                                .filter(Boolean),
                            )
                            const teamsArr = (saveState?.teams ?? []) as Array<{ name?: string; prestige?: number }>
                            const prestigeOf = (n: string) => {
                              const row = teamsArr.find((t) => t?.name === n)
                              return Number(row?.prestige ?? 5)
                            }
                            const canAddChoices = [...vacancySet].sort((a, b) => prestigeOf(b) - prestigeOf(a) || a.localeCompare(b))
                            const availAdd = canAddChoices.filter((n) => !carouselJobApplications.includes(n))

                            function addVacancyPick() {
                              const choice = carouselVacancyPick.trim()
                              if (!choice || !vacancySet.has(choice)) return
                              if (carouselJobApplications.includes(choice)) return
                              setCarouselJobApplications((prev) => [...prev, choice])
                              setCarouselVacancyPick('')
                            }

                            function moveCarouselApp(i: number, dir: -1 | 1) {
                              setCarouselJobApplications((prev) => {
                                const j = i + dir
                                if (j < 0 || j >= prev.length) return prev
                                const next = [...prev]
                                ;[next[i], next[j]] = [next[j], next[i]]
                                return next
                              })
                            }

                            if (vacancySet.size === 0) return null

                            return (
                              <div
                                style={{
                                  marginBottom: 16,
                                  paddingBottom: 12,
                                  borderBottom: '1px solid rgba(80,88,106,0.45)',
                                }}
                              >
                                <div className="teamhome-small" style={{ marginBottom: 8, fontWeight: 700 }}>
                                  Apply for open HC jobs ({vacancySet.size} open){' '}
                                  <span style={{ fontWeight: 400, opacity: 0.85 }}>
                                    ┬╖ Your application list persists until the carousel completes
                                  </span>
                                </div>
                                <div className="teamhome-small" style={{ marginBottom: 10 }}>
                                  Top-ranked schools are prioritized when your coach evaluates offers; you can reorder between
                                  stages IΓÇôIII as new vacancies appear.
                                </div>
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'flex-end', marginBottom: 10 }}>
                                  <select
                                    className="teamhome-select teamhome-select-inline"
                                    aria-label="Add school to application list"
                                    value={carouselVacancyPick}
                                    onChange={(e) => setCarouselVacancyPick(e.target.value)}
                                    style={{ minWidth: 220 }}
                                  >
                                    <option value="">Add vacancyΓÇª</option>
                                    {availAdd.map((n) => (
                                      <option key={n} value={n}>
                                        {prestigeOf(n)}Γÿà {n}
                                      </option>
                                    ))}
                                  </select>
                                  <button
                                    type="button"
                                    className="teamhome-small"
                                    style={{
                                      padding: '6px 12px',
                                      borderRadius: 6,
                                      border: '1px solid #3b4252',
                                      background: '#1a2230',
                                      color: '#d9e0ea',
                                      cursor: availAdd.length && carouselVacancyPick ? 'pointer' : 'not-allowed',
                                      opacity: availAdd.length && carouselVacancyPick ? 1 : 0.45,
                                    }}
                                    disabled={!carouselVacancyPick || !availAdd.length}
                                    onClick={addVacancyPick}
                                  >
                                    Add to list
                                  </button>
                                </div>
                                {carouselJobApplications.length === 0 ? (
                                  <div className="teamhome-small" style={{ opacity: 0.8 }}>
                                    Optional: leave blank to stay put (CPU hiring still runs league-wide).
                                  </div>
                                ) : (
                                  <ul style={{ paddingLeft: 18, margin: 0 }}>
                                    {carouselJobApplications.map((name, idx) => (
                                      <li key={`${name}-${idx}`} className="teamhome-small" style={{ marginBottom: 8 }}>
                                        <b>{idx + 1}.</b> {name}{' '}
                                        <button
                                          type="button"
                                          style={{
                                            marginLeft: 6,
                                            padding: '2px 8px',
                                            fontSize: 12,
                                            borderRadius: 4,
                                            border: '1px solid #364152',
                                            background: '#10151d',
                                            color: '#c7d2e5',
                                          }}
                                          onClick={() => moveCarouselApp(idx, -1)}
                                          disabled={idx === 0}
                                        >
                                          Up
                                        </button>{' '}
                                        <button
                                          type="button"
                                          style={{
                                            marginLeft: 4,
                                            padding: '2px 8px',
                                            fontSize: 12,
                                            borderRadius: 4,
                                            border: '1px solid #364152',
                                            background: '#10151d',
                                            color: '#c7d2e5',
                                          }}
                                          onClick={() => moveCarouselApp(idx, 1)}
                                          disabled={idx >= carouselJobApplications.length - 1}
                                        >
                                          Down
                                        </button>{' '}
                                        <button
                                          type="button"
                                          style={{
                                            marginLeft: 4,
                                            padding: '2px 8px',
                                            fontSize: 12,
                                            borderRadius: 4,
                                            border: '1px solid #533',
                                            background: '#1f1212',
                                            color: '#fecaca',
                                          }}
                                          onClick={() =>
                                            setCarouselJobApplications((prev) => prev.filter((_, j) => j !== idx))
                                          }
                                        >
                                          Remove
                                        </button>
                                      </li>
                                    ))}
                                  </ul>
                                )}
                              </div>
                            )
                          })()
                        : null}
                      {!isCoachingCarouselSummaryStage ? (
                      <>
                      <div className="teamhome-small" style={{ marginBottom: 10 }}>
                        <b>Hot seat</b> (your program):{' '}
                        <b>
                          {(() => {
                            const hsMap = saveState?.offseason_coach_carousel_hot_seat as Record<string, number> | undefined
                            const fromMap = userTeam && hsMap ? hsMap[userTeam] : undefined
                            const fromCoach = Number(findTeam(saveState, userTeam)?.coach?.hot_seat)
                            const v = fromMap ?? (Number.isFinite(fromCoach) ? fromCoach : undefined)
                            return v !== undefined ? `${v} / 100` : 'ΓÇö'
                          })()}
                        </b>
                        <span style={{ opacity: 0.85 }}> ┬╖ Higher = more pressure (losing seasons, missed goals, playoff drought).</span>
                      </div>
                      {(() => {
                        const hsMap = (saveState?.offseason_coach_carousel_hot_seat ?? {}) as Record<string, number>
                        const teams = (saveState?.teams ?? []) as any[]
                        const rows = teams
                          .filter((t) => t?.name && t?.coach)
                          .map((t) => {
                            const teamName = String(t.name)
                            const coachName = String(t.coach?.name ?? 'ΓÇö')
                            const fromMap = hsMap[teamName]
                            const fromCoach = Number(t.coach?.hot_seat)
                            const hotSeat =
                              fromMap != null && Number.isFinite(Number(fromMap))
                                ? Number(fromMap)
                                : Number.isFinite(fromCoach)
                                  ? fromCoach
                                  : 0
                            return { teamName, coachName, hotSeat }
                          })
                          .sort((a, b) => b.hotSeat - a.hotSeat || a.teamName.localeCompare(b.teamName))
                        if (rows.length === 0) return null
                        return (
                          <div className="teamhome-carousel-hotseat-block" style={{ marginTop: 14, marginBottom: 14 }}>
                            <div className="teamhome-small" style={{ marginBottom: 8, fontWeight: 800 }}>
                              League hot seat ΓÇö all head coaches
                            </div>
                            <label className="teamhome-small" htmlFor="carousel-hotseat-select" style={{ display: 'block', marginBottom: 6 }}>
                              Jump to program
                            </label>
                            <select
                              id="carousel-hotseat-select"
                              className="teamhome-select teamhome-select-inline teamhome-carousel-hotseat-select"
                              value={carouselHotSeatTeamFilter}
                              onChange={(e) => setCarouselHotSeatTeamFilter(e.target.value)}
                            >
                              <option value="">ΓÇö Show full list (no highlight) ΓÇö</option>
                              {rows.map((r) => (
                                <option key={r.teamName} value={r.teamName}>
                                  {r.hotSeat}/100 ┬╖ {r.teamName} ΓÇö {r.coachName}
                                </option>
                              ))}
                            </select>
                            <div
                              className="teamhome-carousel-hotseat-table-wrap"
                              style={{
                                marginTop: 10,
                                maxHeight: Math.min(280, rows.length * 28 + 40),
                                overflow: 'auto',
                              }}
                            >
                              <table className="teamhome-roster-table teamhome-carousel-hotseat-table" style={{ width: '100%' }}>
                                <thead>
                                  <tr>
                                    <th style={{ textAlign: 'left' }}>Team</th>
                                    <th style={{ textAlign: 'left' }}>Coach</th>
                                    <th style={{ textAlign: 'right', width: 72 }}>Seat</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {rows.map((r) => {
                                    const active = carouselHotSeatTeamFilter && r.teamName === carouselHotSeatTeamFilter
                                    const userRow = r.teamName === userTeam
                                    return (
                                      <tr
                                        key={r.teamName}
                                        className={
                                          active
                                            ? 'teamhome-carousel-hotseat-row teamhome-carousel-hotseat-row--active'
                                            : userRow
                                              ? 'teamhome-carousel-hotseat-row teamhome-carousel-hotseat-row--user'
                                              : 'teamhome-carousel-hotseat-row'
                                        }
                                      >
                                        <td>{r.teamName}</td>
                                        <td>
                                          <CoachProfileName
                                            mode="team"
                                            teamName={r.teamName}
                                            coachName={r.coachName}
                                            as="span"
                                          />
                                        </td>
                                        <td style={{ textAlign: 'right', fontWeight: 800 }}>{r.hotSeat}</td>
                                      </tr>
                                    )
                                  })}
                                </tbody>
                              </table>
                            </div>
                            <div className="teamhome-small" style={{ marginTop: 8, opacity: 0.82 }}>
                              Sorted by hot seat (highest first). Values refresh after each carousel Continue.
                            </div>
                          </div>
                        )
                      })()}
                      {(() => {
                        const blob = saveState?.offseason_coach_carousel as { vacancies?: unknown[] } | undefined
                        const n = Array.isArray(blob?.vacancies) ? blob.vacancies.length : null
                        if (n == null) return null
                        return (
                          <div className="teamhome-small" style={{ marginBottom: 10 }}>
                            Open head-coach jobs: <b>{n}</b>
                          </div>
                        )
                      })()}
                      <div className="teamhome-small" style={{ opacity: 0.9, marginBottom: 8 }}>
                        Recent moves this offseason:
                      </div>
                      <ul
                        className="teamhome-coaching-events teamhome-coaching-carousel-marquee"
                        style={{ textAlign: 'left', paddingLeft: 18, maxHeight: 280, overflow: 'auto' }}
                      >
                        {(saveState?.offseason_coach_carousel_last_events ?? []).length === 0 ? (
                          <li className="teamhome-small">No moves logged at this carousel step yet ΓÇö press Continue.</li>
                        ) : (
                          (saveState?.offseason_coach_carousel_last_events ?? []).map((ev: any, i: number) => (
                            <li key={`cc-ev-${i}`} className="teamhome-carousel-event-item" style={{ marginBottom: 6 }}>
                              <span style={{ opacity: 0.8 }}>[{ev.type ?? 'ΓÇö'}]</span> {ev.detail ?? ''}
                            </li>
                          ))
                        )}
                      </ul>
                      <div className="teamhome-small" style={{ marginTop: 12 }}>
                        Review past offseasons under <b>State ΓåÆ Coaching changes</b>.
                      </div>
                      </>
                      ) : null}
                    </div>
                  </div>
                ) : offseasonCurrentStage === 'Winter 1' || offseasonCurrentStage === 'Winter 2' ? (
                  <>
                    <div className="teamhome-preseason-title">Winter training focus</div>
                    {!winterTrainingResult ? (
                      <>
                        <div className="teamhome-preseason-sub">
                          Allocate exactly 100 points. Green is optimal (40-60); red means inefficient.
                        </div>
                        <div className="teamhome-small" style={{ marginTop: 8, marginBottom: 8 }}>
                          Points used: <b>{winterPointsUsed}</b> / 100{' '}
                          <span style={{ color: winterPointsRemaining < 0 ? '#f87171' : '#a9b1bc' }}>
                            ({winterPointsRemaining >= 0 ? `${winterPointsRemaining} left` : `${Math.abs(winterPointsRemaining)} over`})
                          </span>
                        </div>
                        <table className="teamhome-roster-table" style={{ width: '100%', marginTop: 8 }}>
                          <thead>
                            <tr>
                              <th style={{ textAlign: 'left' }}>Category</th>
                              <th>Points</th>
                              <th>Efficiency</th>
                              <th style={{ textAlign: 'left' }}>Primary / Secondary</th>
                            </tr>
                          </thead>
                          <tbody>
                            {WINTER_TRAINING_CATEGORIES.map((cat) => {
                              const pts = Number(winterTrainingAllocations[cat.key] ?? 0)
                              const eff = winterEfficiency(pts)
                              return (
                                <tr key={cat.key}>
                                  <td style={{ textAlign: 'left' }}>{cat.label}</td>
                                  <td>
                                    <input
                                      type="number"
                                      min={0}
                                      max={100}
                                      value={pts}
                                      onChange={(e) => {
                                        const next = Math.max(0, Math.min(100, Number(e.target.value) || 0))
                                        setWinterTrainingAllocations((prev) => ({ ...prev, [cat.key]: next }))
                                      }}
                                      style={{
                                        width: 72,
                                        background: '#0f131b',
                                        color: '#d9e0ea',
                                        border: '1px solid #2f3440',
                                        borderRadius: 6,
                                        padding: '4px 6px',
                                      }}
                                    />
                                  </td>
                                  <td style={{ color: winterEfficiencyColor(pts) }}>{Math.round(eff * 100)}%</td>
                                  <td style={{ textAlign: 'left' }}>
                                    {cat.primary} / {cat.secondary}
                                  </td>
                                </tr>
                              )
                            })}
                          </tbody>
                        </table>
                        <div
                          className="teamhome-small"
                          style={{
                            marginTop: 8,
                            minHeight: 20,
                            color: '#f87171',
                            visibility: winterAllocationInvalid ? 'visible' : 'hidden',
                          }}
                        >
                          Allocate exactly 100 total points before continuing.
                        </div>
                      </>
                    ) : (
                      <div style={{ marginTop: 10, textAlign: 'left', width: '100%', maxWidth: 940 }}>
                        <div className="teamhome-small" style={{ marginBottom: 8 }}>
                          Session: <b>{String(winterTrainingResult.stage ?? offseasonCurrentStage)}</b>
                        </div>
                        <div className="teamhome-small" style={{ marginBottom: 12 }}>
                          Team summary: <b>{String(winterTrainingResult.summary ?? 'Minor Winter Progress')}</b>
                        </div>

                        <div className="teamhome-preseason-title" style={{ fontSize: 15 }}>Category efficiency and gains</div>
                        <table className="teamhome-roster-table" style={{ width: '100%', marginTop: 8 }}>
                          <thead>
                            <tr>
                              <th style={{ textAlign: 'left' }}>Category</th>
                              <th>Points</th>
                              <th>Efficiency</th>
                              <th>Team Gains</th>
                            </tr>
                          </thead>
                          <tbody>
                            {((winterTrainingResult.efficiency_rows ?? []) as any[]).map((r, i) => (
                              <tr key={`${r.category}-${i}`}>
                                <td style={{ textAlign: 'left' }}>{String(r.category ?? '').replaceAll('_', ' ')}</td>
                                <td>{Number(r.points ?? 0)}</td>
                                <td style={{ color: winterEfficiencyColor(Number(r.points ?? 0)) }}>
                                  {Math.round(Number(r.efficiency ?? 0) * 100)}%
                                </td>
                                <td>{Number(r.gains ?? 0).toFixed(1)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>

                        <div className="teamhome-preseason-title" style={{ marginTop: 14, fontSize: 15 }}>Notable players</div>
                        <ul style={{ marginTop: 8 }}>
                          {((winterTrainingResult.notable_players ?? []) as any[]).slice(0, 5).map((n, i) => (
                            <li key={`${n.player_name}-${n.attribute}-${i}`}>
                              {String(n.player_name ?? 'Player')} ({String(n.position ?? '')}) +{Number(n.delta ?? 0)} {String(n.attribute ?? '')}
                            </li>
                          ))}
                          {(!winterTrainingResult.notable_players || winterTrainingResult.notable_players.length === 0) ? (
                            <li>No major standouts this session.</li>
                          ) : null}
                        </ul>

                        <div className="teamhome-preseason-title" style={{ marginTop: 14, fontSize: 15 }}>Staff feedback</div>
                        <ul style={{ marginTop: 8 }}>
                          {((winterTrainingResult.feedback ?? []) as any[]).map((f, i) => (
                            <li key={`winter-fb-${i}`}>{String(f)}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </>
                ) : offseasonCurrentStage === 'Spring Ball' ? (
                  <>
                    <div className="teamhome-preseason-title">Spring Ball</div>
                    {!springBallResult ? (
                      <>
                        <div className="teamhome-preseason-sub">Select one offensive and one defensive focus, then press Continue to simulate spring camp.</div>
                        <div className="teamhome-playbook-row" style={{ marginTop: 16 }}>
                          <div className="teamhome-playbook-field">
                            <label className="teamhome-playbook-label">Offense</label>
                            <select
                              className="teamhome-playbook-select-input"
                              value={springOffense}
                              onChange={(e) => setSpringOffense(e.target.value)}
                            >
                              {SPRING_OFFENSE_OPTIONS.map((o) => (
                                <option key={o.value} value={o.value}>
                                  {o.label}
                                </option>
                              ))}
                            </select>
                          </div>
                          <div className="teamhome-playbook-field">
                            <label className="teamhome-playbook-label">Defense</label>
                            <select
                              className="teamhome-playbook-select-input"
                              value={springDefense}
                              onChange={(e) => setSpringDefense(e.target.value)}
                            >
                              {SPRING_DEFENSE_OPTIONS.map((o) => (
                                <option key={o.value} value={o.value}>
                                  {o.label}
                                </option>
                              ))}
                            </select>
                          </div>
                        </div>
                      </>
                    ) : (
                      <div style={{ marginTop: 10, textAlign: 'left', width: '100%', maxWidth: 940 }}>
                        <div className="teamhome-small" style={{ marginBottom: 8 }}>
                          Offensive focus: <b>{springLabel(String(springBallResult.offensive_focus ?? ''), 'offense')}</b>
                        </div>
                        <div className="teamhome-small" style={{ marginBottom: 8 }}>
                          Defensive focus: <b>{springLabel(String(springBallResult.defensive_focus ?? ''), 'defense')}</b>
                        </div>
                        <div className="teamhome-small" style={{ marginBottom: 12 }}>
                          Team summary: <b>{String(springBallResult.summary ?? 'Minor Improvement')}</b>
                        </div>

                        <div className="teamhome-preseason-title" style={{ fontSize: 15 }}>Position group changes</div>
                        <table className="teamhome-roster-table" style={{ width: '100%', marginTop: 8 }}>
                          <thead>
                            <tr>
                              <th style={{ textAlign: 'left' }}>Group</th>
                              <th>Avg Delta</th>
                            </tr>
                          </thead>
                          <tbody>
                            {((springBallResult.position_group_changes ?? []) as any[]).map((r, i) => (
                              <tr key={`${r?.label ?? 'grp'}-${i}`}>
                                <td>{String(r?.label ?? 'ΓÇö')}</td>
                                <td>{Number(r?.delta ?? 0) >= 0 ? `+${Number(r?.delta ?? 0).toFixed(1)}` : Number(r?.delta ?? 0).toFixed(1)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>

                        <div className="teamhome-preseason-title" style={{ fontSize: 15, marginTop: 12 }}>Notable player improvements</div>
                        <ul className="teamhome-list" style={{ marginTop: 6 }}>
                          {((springBallResult.notable_players ?? []) as any[]).slice(0, 5).map((n, i) => (
                            <li key={`notable-${i}`} className="teamhome-small">
                              {String(n?.position ?? 'ΓÇö')} {String(n?.player_name ?? 'Player')}: +{Number(n?.delta ?? 0)} {String(n?.attribute ?? '')}
                            </li>
                          ))}
                          {(!springBallResult.notable_players || springBallResult.notable_players.length === 0) ? (
                            <li className="teamhome-small">No major standouts this spring.</li>
                          ) : null}
                        </ul>

                        <div className="teamhome-preseason-title" style={{ fontSize: 15, marginTop: 10 }}>Feedback</div>
                        <ul className="teamhome-list" style={{ marginTop: 6 }}>
                          {((springBallResult.neutral_feedback ?? []) as any[]).map((f, i) => (
                            <li key={`fb-${i}`} className="teamhome-small">{String(f)}</li>
                          ))}
                        </ul>
                        <div className="teamhome-small" style={{ marginTop: 10, opacity: 0.9 }}>
                          Press <b>Continue</b> to lock results and advance.
                        </div>
                      </div>
                    )}
                  </>
                ) : offseasonCurrentStage === 'Transfers I' ? (
                  <>
                    <div className="teamhome-preseason-title">Transfers I ΓÇö Portal entrants</div>
                    <div className="teamhome-preseason-sub">
                      First <b>Continue</b> builds the portal class from the season that just ended (using final
                      standings). Review the list, then <b>Continue</b> again to lock entrants before destinations run
                      in Transfers II.
                    </div>
                    {transferStage1?.entries?.length ? (
                      <div style={{ marginTop: 12 }}>
                        <div className="teamhome-small" style={{ marginBottom: 8 }}>
                          League portal cap: <b>{Number(transferStage1.pool_pct ?? 0).toFixed(1)}%</b> ┬╖ In portal:{' '}
                          <b>{Number(transferStage1.selected_count ?? 0)}</b>
                          {transferStage1.eligible_count != null ? (
                            <>
                              {' '}
                              ┬╖ Candidates considered: <b>{Number(transferStage1.eligible_count)}</b>
                            </>
                          ) : null}
                        </div>
                        <div
                          className="teamhome-roster-table"
                          style={{ maxHeight: 320, overflowY: 'auto', marginTop: 8 }}
                        >
                          <div className="teamhome-roster-head teamhome-roster-row teamhome-transfer-portal-head">
                            <div className="teamhome-roster-cell">Player</div>
                            <div className="teamhome-roster-cell">Pos</div>
                            <div className="teamhome-roster-cell">Class</div>
                            <div className="teamhome-roster-cell">From (school)</div>
                            <div className="teamhome-roster-cell">Region</div>
                            <div className="teamhome-roster-cell">Pressure</div>
                          </div>
                          {transferStage1EntriesSorted.map((r: any, i: number) => {
                            const fromSchool = String(r.from_team ?? r.team ?? 'ΓÇö')
                            return (
                              <div
                                key={`tr1-${fromSchool}-${String(r.player)}-${i}`}
                                className="teamhome-roster-row teamhome-transfer-portal-row"
                              >
                                <div className="teamhome-roster-cell">{String(r.player ?? 'ΓÇö')}</div>
                                <div className="teamhome-roster-cell">{String(r.position ?? 'ΓÇö')}</div>
                                <div className="teamhome-roster-cell">{formatTransferPortalClassYear(r.year)}</div>
                                <div className="teamhome-roster-cell">{teamWithLogo(fromSchool, 22)}</div>
                                <div className="teamhome-roster-cell">{String(r.region ?? 'ΓÇö')}</div>
                                <div className="teamhome-roster-cell">{Number(r.score ?? 0).toFixed(1)}</div>
                              </div>
                            )
                          })}
                        </div>
                        <div className="teamhome-small" style={{ marginTop: 10, opacity: 0.85 }}>
                          Sorted by school, then name. List is everyone in this portal class (not a sample).
                          {transferStage1PendingReview ? (
                            <> Press <b>Continue</b> again to lock and advance.</>
                          ) : null}
                        </div>
                      </div>
                    ) : (
                      <div className="teamhome-small" style={{ marginTop: 8 }}>
                        Portal class not generated yet. Press <b>Continue</b> once to run the evaluation.
                      </div>
                    )}
                  </>
                ) : offseasonCurrentStage === 'Transfers II' ? (
                  <>
                    <div className="teamhome-preseason-title">Transfers II ΓÇö Destinations</div>
                    <div className="teamhome-preseason-sub">
                      First <b>Continue</b> resolves destinations from the locked portal class. Review, then{' '}
                      <b>Continue</b> again to advance.
                    </div>
                    {transferStage2?.entries?.length ? (
                      <div style={{ marginTop: 10 }}>
                        <div className="teamhome-small">
                          Finalized moves: <b>{Number(transferStage2.moved_count ?? 0)}</b> ┬╖ Blocked:{' '}
                          <b>{Number(transferStage2.blocked_count ?? 0)}</b>
                        </div>
                        <ul className="teamhome-list" style={{ marginTop: 8 }}>
                          {(transferStage2.entries as any[]).slice(0, 12).map((r: any, i: number) => (
                            <li key={`tr2-${i}`} className="teamhome-small">
                              {String(r.player)} ({String(r.position)}) ┬╖ {String(r.from_team)} ΓåÆ {String(r.to_team)}
                            </li>
                          ))}
                        </ul>
                        {transferStage2PendingReview ? (
                          <div className="teamhome-small" style={{ marginTop: 10, opacity: 0.85 }}>
                            Press <b>Continue</b> again to lock and advance.
                          </div>
                        ) : null}
                      </div>
                    ) : (
                      <div className="teamhome-small" style={{ marginTop: 8 }}>
                        Destinations not resolved yet. Press <b>Continue</b> once to run resolution.
                      </div>
                    )}
                  </>
                ) : offseasonCurrentStage === 'Transfers III' ? (
                  <>
                    <div className="teamhome-preseason-title">Transfers III ΓÇö Review</div>
                    <div className="teamhome-preseason-sub">
                      Final offseason transfer ledger. Review every completed move before advancing.
                    </div>
                    {transferReview?.entries?.length ? (
                      <div style={{ marginTop: 10 }}>
                        <div className="teamhome-small">
                          Completed transfers: <b>{Number(transferReview.moved_count ?? transferReview.entries.length ?? 0)}</b> ┬╖ Blocked:{' '}
                          <b>{Number(transferReview.blocked_count ?? 0)}</b>
                        </div>
                        <ul className="teamhome-list" style={{ marginTop: 8 }}>
                          {(transferReview.entries as any[]).map((r: any, i: number) => (
                            <li key={`tr3-${i}`} className="teamhome-small">
                              {String(r.player)} ({String(r.position)}) ┬╖ {String(r.from_team)} ΓåÆ {String(r.to_team)}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : (
                      <div className="teamhome-small" style={{ marginTop: 8 }}>No transfers finalized this offseason.</div>
                    )}
                  </>
                ) : offseasonCurrentStage === '7 on 7' ? (
                  <>
                    <div className="teamhome-preseason-title">{offseasonCurrentStage}</div>
                    <div className="teamhome-preseason-sub">Coming soon.</div>
                  </>
                ) : offseasonCurrentStage === 'Training Results' ? (
                  <>
                    <div className="teamhome-preseason-title">Training &amp; development</div>
                    <div className="teamhome-preseason-sub">
                      Continue runs the main offseason development for all programs. You get a full-roster before/after
                      report next (Freshman Class) with sorting by position, OVR change, and more.
                    </div>
                    {offseasonTrainingRowsRaw.length > 0 ? (
                      <div style={{ marginTop: 16 }}>
                        <div className="teamhome-playbook-row" style={{ alignItems: 'flex-end' }}>
                          <div className="teamhome-playbook-field">
                            <label className="teamhome-playbook-label">Sort roster by</label>
                            <select
                              className="teamhome-playbook-select-input"
                              value={offseasonTrainingSort}
                              onChange={(e) => setOffseasonTrainingSort(e.target.value as OffseasonTrainingSortMode)}
                            >
                              <option value="position">Position</option>
                              <option value="delta">OVR change (largest first)</option>
                              <option value="after">OVR after (high to low)</option>
                              <option value="name">Name (AΓÇôZ)</option>
                            </select>
                          </div>
                          <span className="teamhome-small">{sortedOffseasonTrainingRows.length} players</span>
                        </div>
                        <div style={{ maxHeight: 'min(420px, 60vh)', overflow: 'auto', marginTop: 10 }}>
                          <table className="teamhome-roster-table" style={{ width: '100%' }}>
                            <thead>
                              <tr>
                                <th style={{ textAlign: 'left' }}>Player</th>
                                <th>Pos</th>
                                <th>OVR before</th>
                                <th>OVR after</th>
                                <th>╬ö</th>
                              </tr>
                            </thead>
                            <tbody>
                              {sortedOffseasonTrainingRows.map((row, i) => (
                                <tr key={`${row.name}-${i}`}>
                                  <td>
                                    <PlayerProfileName teamName={userTeam} playerName={row.name} as="span" />
                                  </td>
                                  <td>{row.position ?? 'ΓÇö'}</td>
                                  <td>{row.before}</td>
                                  <td>{row.after}</td>
                                  <td>{row.delta >= 0 ? `+${row.delta}` : row.delta}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    ) : null}
                  </>
                ) : offseasonCurrentStage === 'Freshman Class' ? (
                  <>
                    <div className="teamhome-preseason-title">Freshman class</div>
                    <div className="teamhome-preseason-sub">
                      Full incoming class (year 9 / FR). These players were added when the new year started.
                    </div>
                    {offseasonTrainingRowsRaw.length > 0 ? (
                      <div style={{ marginTop: 16 }}>
                        <div className="teamhome-preseason-title" style={{ fontSize: 15 }}>
                          Training &amp; development results
                        </div>
                        <div className="teamhome-playbook-row" style={{ alignItems: 'flex-end', marginTop: 8 }}>
                          <div className="teamhome-playbook-field">
                            <label className="teamhome-playbook-label">Sort roster by</label>
                            <select
                              className="teamhome-playbook-select-input"
                              value={offseasonTrainingSort}
                              onChange={(e) => setOffseasonTrainingSort(e.target.value as OffseasonTrainingSortMode)}
                            >
                              <option value="position">Position</option>
                              <option value="delta">OVR change (largest first)</option>
                              <option value="after">OVR after (high to low)</option>
                              <option value="name">Name (AΓÇôZ)</option>
                            </select>
                          </div>
                          <span className="teamhome-small">{sortedOffseasonTrainingRows.length} players</span>
                        </div>
                        <div style={{ maxHeight: 'min(360px, 50vh)', overflow: 'auto', marginTop: 10 }}>
                          <table className="teamhome-roster-table" style={{ width: '100%' }}>
                            <thead>
                              <tr>
                                <th style={{ textAlign: 'left' }}>Player</th>
                                <th>Pos</th>
                                <th>OVR before</th>
                                <th>OVR after</th>
                                <th>╬ö</th>
                              </tr>
                            </thead>
                            <tbody>
                              {sortedOffseasonTrainingRows.map((row, i) => (
                                <tr key={`${row.name}-tr-${i}`}>
                                  <td>
                                    <PlayerProfileName teamName={userTeam} playerName={row.name} as="span" />
                                  </td>
                                  <td>{row.position ?? 'ΓÇö'}</td>
                                  <td>{row.before}</td>
                                  <td>{row.after}</td>
                                  <td>{row.delta >= 0 ? `+${row.delta}` : row.delta}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    ) : null}
                    <div className="teamhome-preseason-title" style={{ fontSize: 15, marginTop: 20 }}>
                      Freshmen ({freshmanRosterPlayers.length})
                    </div>
                    <div className="teamhome-playbook-row" style={{ marginTop: 8 }}>
                      <div className="teamhome-playbook-field">
                        <label className="teamhome-playbook-label">Sort freshmen by</label>
                        <select
                          className="teamhome-playbook-select-input"
                          value={freshmanSort}
                          onChange={(e) => setFreshmanSort(e.target.value as FreshmanSortMode)}
                        >
                          <option value="position">Position</option>
                          <option value="overall">Overall (high to low)</option>
                          <option value="name">Name (AΓÇôZ)</option>
                        </select>
                      </div>
                    </div>
                    <div style={{ maxHeight: 'min(380px, 55vh)', overflow: 'auto', marginTop: 10 }}>
                      {sortedFreshmanRosterPlayers.length === 0 ? (
                        <div className="teamhome-preseason-sub">No freshmen on the roster (check year labels in roster data).</div>
                      ) : (
                        <table className="teamhome-roster-table" style={{ width: '100%' }}>
                          <thead>
                            <tr>
                              <th style={{ textAlign: 'left' }}>Name</th>
                              <th>Pos</th>
                              <th>Year</th>
                              <th>OVR</th>
                              <th>Pot</th>
                              <th>Ht</th>
                              <th>Wt</th>
                            </tr>
                          </thead>
                          <tbody>
                            {sortedFreshmanRosterPlayers.map((p: any, i: number) => (
                              <tr key={`${p?.name ?? 'p'}-${i}`}>
                                <td>
                                  <PlayerProfileName teamName={userTeam} playerName={p?.name} as="span" />
                                </td>
                                <td>{p?.position ?? 'ΓÇö'}</td>
                                <td>{formatPlayerYear(p?.year)}</td>
                                <td>{computePlayerOverall(p)}</td>
                                <td>{p?.potential ?? 'ΓÇö'}</td>
                                <td>{p?.height != null ? `${p.height}` : 'ΓÇö'}</td>
                                <td>{p?.weight != null ? `${p.weight}` : 'ΓÇö'}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )}
                    </div>
                  </>
                ) : offseasonCurrentStage === 'Schedule Release' ? (
                  <>
                    <div className="teamhome-preseason-title">Schedule release</div>
                    <div className="teamhome-preseason-sub">Regular season matchups and the two preseason scrimmages (fixed for when you reach preseason).</div>
                    <div style={{ marginTop: 12 }}>
                      <div className="teamhome-preseason-title" style={{ fontSize: 14 }}>
                        Regular season (your team)
                      </div>
                      <ul style={{ margin: '8px 0', paddingLeft: 20 }}>
                        {scheduleRows.length === 0 ? (
                          <li>No schedule on file.</li>
                        ) : (
                          scheduleRows.map((r) => (
                            <li key={`wk-${r.week}`}>
                              Week {r.week}: vs {r.opponent}
                              {r.isRegionGame ? (
                                <span className="teamhome-region-mark" title="Region game">*</span>
                              ) : null}
                              {' '}({r.scoreLine})
                            </li>
                          ))
                        )}
                      </ul>
                      {scheduleRows.some((r) => r.isRegionGame) ? (
                        <div className="teamhome-schedule-region-legend teamhome-small">
                          <span className="teamhome-region-mark">*</span> Region game
                        </div>
                      ) : null}
                      <div className="teamhome-preseason-title" style={{ fontSize: 14, marginTop: 12 }}>
                        Preseason scrimmages
                      </div>
                      <ul style={{ margin: '8px 0', paddingLeft: 20 }}>
                        {(saveState?.preseason_scrimmage_opponents ?? []).length === 0 ? (
                          <li>ΓÇö</li>
                        ) : (
                          (saveState.preseason_scrimmage_opponents as { opponent?: string; user_home?: boolean }[]).map(
                            (s, i) => (
                              <li key={`sc-${i}`}>
                                Scrimmage {i + 1}:{' '}
                                {s.user_home ? `vs ${s.opponent} (home)` : `@ ${s.opponent} (away)`}
                              </li>
                            ),
                          )
                        )}
                      </ul>
                    </div>
                  </>
                ) : (
                  <div className="teamhome-preseason-title">Offseason</div>
                )}
              </div>

            </div>

            <div className="teamhome-preseason-bottom">
              <div className="teamhome-preseason-panelD">
                <div className="teamhome-preseason-title">News</div>
                <NewsFeedPanel limit={5} compact />
              </div>
              <div className="teamhome-preseason-panelC">
                <div className="teamhome-preseason-title">Season</div>
                <div className="teamhome-preseason-sub">Year {saveState?.current_year ?? 'ΓÇö'}</div>
              </div>
            </div>
          </div>
          )
        ) : phase === 'regular' && stateMenu !== 'Dashboard' && leagueStatePanel ? (
          <div className="teamhome-roster-shell teamhome-playoffs-league-view">{leagueStatePanel}</div>
        ) : teamMenu === 'Overview' && phase === 'regular' ? (
          leagueStatePanel ?? (
          <div className="teamhome-grid">
          {/* Left column */}
          <div className="teamhome-actions-grid">
            <div className="teamhome-card">
              <div className="teamhome-card-title">Game Actions</div>
              <div className="teamhome-small" style={{ marginBottom: 10 }}>
                Week {currentWeek} · {hasUnplayedGameThisWeek ? `vs ${nextOpponent || '—'}` : 'No game this week'}
              </div>
              <div className="teamhome-actions-grid">
                <button type="button" className="teamhome-action-btn" disabled>
                  Game plan
                  <span className="teamhome-action-sub">Coming soon (play selection UI)</span>
                </button>
                <button
                  type="button"
                  className="teamhome-action-btn"
                  disabled={playingWeek || !hasUnplayedGameThisWeek || isLocalBundle}
                  onClick={async () => {
                    if (!saveId || !headers) return
                    setPlayingWeek(true)
                    try {
                          const r = isLocalBundle
                            ? await fetch(`${apiBase}/sim/game/start`, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ state: saveState, context: 'week' }),
                              })
                            : await fetch(`${apiBase}/saves/${saveId}/start-coach-game`, {
                                method: 'POST',
                                headers: { ...headers, 'Content-Type': 'application/json' },
                                body: JSON.stringify({ context: 'week' }),
                              })
                      if (!r.ok) {
                        const errText = await r.text()
                        let errMsg = 'Failed to start game'
                        try {
                          const j = JSON.parse(errText)
                          errMsg = (j?.detail ?? errText) || errMsg
                        } catch {
                          errMsg = errText || errMsg
                        }
                        onError(typeof errMsg === 'string' ? errMsg : JSON.stringify(errMsg))
                        return
                      }
                      const data = await r.json()
                          if ((!isLocalBundle && (!data?.game_id || !data?.state)) || (isLocalBundle && (!data?.game || !data?.state))) {
                        onError('Invalid response from server')
                        return
                      }
                      onError('')
                      setActiveGame({
                            gameId: isLocalBundle ? '__local_game__' : data.game_id,
                            homeTeam: data.home_team_name,
                            awayTeam: data.away_team_name,
                            userTeam: data.user_team_name,
                            initialState: isLocalBundle ? { ...data.state, __game: data.game } : data.state,
                        gameContext: 'week',
                      })
                    } catch (e: any) {
                      onError(e?.message ?? 'Failed to start game')
                    } finally {
                      setPlayingWeek(false)
                    }
                  }}
                >
                  {playingWeek ? 'Loading…' : 'Play game'}
                  <span className="teamhome-action-sub">Coach the game play-by-play</span>
                </button>
                <button
                  type="button"
                  className="teamhome-action-btn"
                  disabled={!canContinue || simmingWeek}
                  onClick={async () => {
                    setSimmingWeek(true)
                    try {
                      await onSimWeek()
                    } catch (e: any) {
                      onError(e?.message ?? 'Sim failed')
                    } finally {
                      setSimmingWeek(false)
                    }
                  }}
                >
                  {simmingWeek ? 'Simming week…' : 'Sim game'}
                  <span className="teamhome-action-sub">
                    Sims every game this week (skips your game if you already played it), then advances
                  </span>
                </button>
                <div className="teamhome-sim-multi-row">
                  <span className="teamhome-action-sub">Sim multiple weeks:</span>
                  {[2, 3, 4].map((n) => (
                    <button
                      key={n}
                      type="button"
                      className="teamhome-action-btn teamhome-action-btn-small"
                      disabled={simMultipleCount > 0 || simmingWeek || !canContinue || phase !== 'regular'}
                      onClick={async () => {
                        setSimMultipleCount(n)
                        try {
                          for (let i = 0; i < n; i++) {
                            const ok = await onSimWeek()
                            if (!ok) break
                          }
                        } finally {
                          setSimMultipleCount(0)
                        }
                      }}
                    >
                      {simMultipleCount === n ? 'Simulating…' : `${n}`}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="teamhome-card">
              <div className="teamhome-card-title">Season goals</div>
              <div className="teamhome-list">
                <div className="teamhome-row">
                  <span className="teamhome-small">Win total</span>
                  <strong>{typeof seasonGoals?.win_goal === 'number' ? seasonGoals.win_goal : '—'}</strong>
                </div>
                <div className="teamhome-row">
                  <span className="teamhome-small">Stage goal</span>
                  <strong>{seasonGoals?.stage_goal ?? '—'}</strong>
                </div>
              </div>
            </div>

            <div className="teamhome-card teamhome-card-dark">
              <div className="teamhome-card-title">Standings</div>
              <div className="teamhome-list">
                {standingsRows.slice(0, 8).map((r) => (
                  <div key={r.teamName} className="teamhome-row teamhome-row-standings-mini">
                    <span className="teamhome-small">#{r.rank}</span>
                    <div className="teamhome-name-with-logo" style={{ flex: 1, minWidth: 0 }}>
                      <TeamLogo apiBase={apiBase} headers={headers} teamName={r.teamName} logoVersion={logoVersion} size={26} />
                      <strong>{r.teamName}</strong>
                    </div>
                    <span>{r.wins}-{r.losses}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Middle column */}
          <div className="teamhome-actions-grid">
            <div className="teamhome-card">
              <div className="teamhome-card-title">Game plan</div>
              <div className="teamhome-list">
                <div className="teamhome-row">
                  <div>
                    <strong>Offensive</strong>
                    <div className="teamhome-small">{offensePlan}</div>
                  </div>
                </div>
                <div className="teamhome-row">
                  <div>
                    <strong>Defensive</strong>
                    <div className="teamhome-small">{defensePlan}</div>
                  </div>
                </div>
              </div>
            </div>

            <div className="teamhome-card teamhome-card-dark">
              <div className="teamhome-card-title">News feed</div>
              <NewsFeedPanel limit={8} />
            </div>
          </div>

          {/* Right column */}
          <div className="teamhome-actions-grid">
            <div className="teamhome-card">
              <div className="teamhome-card-title">Schedule</div>
              <div className="teamhome-list">
                {scheduleRows.length === 0 ? (
                  <div className="teamhome-small">No schedule data yet.</div>
                ) : (
                  scheduleRows
                    .slice()
                    .sort((a, b) => a.week - b.week)
                    .map((r) => (
                      <div
                        key={r.week}
                        className="teamhome-row teamhome-schedule-mini-row"
                        style={{ background: r.played ? 'rgba(0,0,0,0.08)' : 'rgba(0,0,0,0.03)' }}
                      >
                        <div>
                          <strong>Week {r.week}</strong>
                          <div className="teamhome-name-with-logo teamhome-small teamhome-schedule-mini-opponent" style={{ gap: 6 }}>
                            {r.opponent && !/^bye$/i.test(String(r.opponent)) ? (
                              <TeamLogo apiBase={apiBase} headers={headers} teamName={r.opponent} logoVersion={logoVersion} size={16} />
                            ) : null}
                            <span>
                              {r.opponent}
                              {r.isRegionGame ? (
                                <span className="teamhome-region-mark" title="Region game">*</span>
                              ) : null}
                            </span>
                          </div>
                        </div>
                        <div className="teamhome-small teamhome-schedule-mini-score">{r.played ? r.scoreLine : 'Scheduled'}</div>
                      </div>
                    ))
                )}
              </div>
              {scheduleRows.some((r) => r.isRegionGame) ? (
                <div className="teamhome-schedule-region-legend teamhome-small">
                  <span className="teamhome-region-mark">*</span> Region game
                </div>
              ) : null}
            </div>

            <div className="teamhome-card teamhome-card-dark">
              <div className="teamhome-card-title">Team stats</div>
              <div className="teamhome-list">
                {(() => {
                  const my = statsRows.find((r) => r.teamName === userTeam)
                  if (!my) return <div className="teamhome-small">No stats yet.</div>
                  return (
                    <>
                      <div className="teamhome-row">
                        <span className="teamhome-small">Offensive PPG</span>
                        <strong>{(my.pointsFor / Math.max(1, my.games)).toFixed(1)}</strong>
                      </div>
                      <div className="teamhome-row">
                        <span className="teamhome-small">Defensive PPG</span>
                        <strong>{(my.pointsAgainst / Math.max(1, my.games)).toFixed(1)}</strong>
                      </div>
                      <div className="teamhome-row">
                        <span className="teamhome-small">Point diff</span>
                        <strong>{my.diff >= 0 ? '+' : ''}{my.diff}</strong>
                      </div>
                    </>
                  )
                })()}
              </div>
            </div>
          </div>
        </div>
          )
        ) : renderTeamMenuPanel()}
      </div>

    </div>
  )
}

export default function TeamHomePage(props: Props) {
  const [logoVersion, setLogoVersion] = useState(0)
  const [stadiumVersion, setStadiumVersion] = useState(0)
  return (
    <NewsProvider saveId={props.saveId} saveState={props.saveState}>
      <NewsStateSync saveId={props.saveId} saveState={props.saveState} leagueHistory={props.leagueHistory} />
      <PlayerProfileProvider
        saveState={props.saveState}
        apiBase={props.apiBase}
        headers={props.headers}
        logoVersion={logoVersion}
      >
        <CoachProfileProvider
          saveState={props.saveState}
          apiBase={props.apiBase}
          headers={props.headers}
          saveId={props.saveId}
          logoVersion={logoVersion}
          leagueHistory={props.leagueHistory}
          seasonRecaps={props.seasonRecaps}
          onError={props.onError}
        >
          <TeamHomePageBody
            {...props}
            logoVersion={logoVersion}
            setLogoVersion={setLogoVersion}
            stadiumVersion={stadiumVersion}
            setStadiumVersion={setStadiumVersion}
          />
        </CoachProfileProvider>
      </PlayerProfileProvider>
      <NewsTicker />
    </NewsProvider>
  )
}

