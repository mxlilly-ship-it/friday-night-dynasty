import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import './TeamHomePage.css'
import './NewSaveFlow.css'
import type { CSSProperties } from 'react'
import { DEFENSIVE_PLAYBOOKS, OFFENSIVE_PLAYBOOKS } from './newSaveTypes'
import PlaybookGamePlanPage from './PlaybookGamePlanPage'
import { fetchPlayLearningSummary, fetchPlaySelection, saveDepthChart } from './browserSave'
import { cachePlaySelectionResponse, hasPlaySelectionCache } from './playSelectionCache'
import DepthChartPage from './DepthChartPage'
import ScrimmagePanel from './ScrimmagePanel'
import PreseasonHubHeader from './PreseasonHubHeader'
import {
  ALL_POSITIONS_ORDERED,
  countPrimaryPositions,
  formatPositionRecommendation,
  primaryPositionTargets,
  recommendBalancedPositionsForRoster,
  recommendPlayerPositions,
} from './positionRecommendations'
import GamePlayPage from './GamePlayPage'
import TeamLogo from './TeamLogo'
import { LogoPrefsProvider } from './LogoPrefsContext'
import { saveUsesDefaultLeagueLogos } from './logoPrefs'
import SettingsPage from './SettingsPage'
import TeamInfoPage from './TeamInfoPage'
import { buildTeamInfoData } from './teamInfoData'
import { gameOfTheWeekLabel, isGameOfTheWeek, pickGameOfTheWeekForWeek } from './gameOfTheWeek'
import { buildPlayerStatRows } from './playerSeasonStats'
import { CoachProfileName, CoachProfileProvider } from './CoachProfileContext'
import CoachStatsPage from './CoachStatsPage'
import TeamRatingsPage from './TeamRatingsPage'
import CoachingCardPicker from './CoachingCardPicker'
import {
  COACH_DEV_SKILLS,
  COACH_DEV_THRESHOLDS,
  coachDevCpToNextLevel,
  coachDevLevelFromCp,
  coachDevNextThreshold,
  formatCoachCpDelta,
  type CoachDevBreakdown,
} from './coachDevelopment'
import {
  EMPTY_COACHING_LOADOUT,
  computeLoadoutChangeCp,
  isPlatinumBreakthroughEligible,
  normalizeLoadout,
  type CoachingCardLoadout,
} from './coachingCards'
import { PlayerProfileName, PlayerProfileProvider } from './PlayerProfileContext'
import { buildOffseasonPlayerReport } from './offseasonPlayerReport'
import OffseasonReportPlayerName from './OffseasonReportPlayerName'
import PlayerOffseasonReportModal from './PlayerOffseasonReportModal'
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
  buildTeamRatingsFromSaveState,
  fetchTeamRatings,
  ratingsForTeam,
  type TeamRatingRow,
} from './teamRatings'
import {
  findSeasonEntryByCalendarYear,
  getHistoricalPlayoffsByClass,
  standingsListToRecord,
} from './leagueHistoryView'
import SeasonSummaryPanel from './SeasonSummaryPanel'
import AllStateAwardsSection from './AllStateAwardsSection'
import HomeGameThemesPanel from './HomeGameThemesPanel'
import { themeLabelForGame } from './homeGameThemes'
import type { HomeThemeSelection } from './homeGameThemes'
import CoachInboxPanel from './CoachInboxPanel'
import InSeasonDashboard from './InSeasonDashboard'
import SchedulePlanningPanel, { SchedulePlanningScrollCallout } from './SchedulePlanningPanel'
import CommishCrossRegionPlanning from './CommishCrossRegionPlanning'
import {
  allSlotsFilled,
  buildCrossRegionPicksPayload,
  crossRegionSelectionsFromSaved,
  crossRegionSlotCountFromSave,
  emptySlotSelection,
  isInitialDynastySchedulePlanning,
  isMultiplayerLeagueSave,
  schedulePlanningInfoFromState,
  userClassExpectsCrossRegionPicks,
  type CrossRegionSelections,
} from './schedulePlanningData'
import { deriveUiPhaseFromSave } from './seasonPhase'
import { buildPregamePreviewData } from './pregamePreviewData'
import PregamePreviewModal from './PregamePreviewModal'
import ProgramDevelopmentPanel from './ProgramDevelopmentPanel'
import ProgramInvestmentBoosterCards from './ProgramInvestmentBoosterCards'
import {
  clampImprovementLevel,
  formatProgramPpDelta,
  pillarCumulativePpValue,
  PROGRAM_INVESTMENT_PILLAR_THEME,
} from './programInvestment'
import TeamFacilitiesPage from './TeamFacilitiesPage'
import catalogJson from './programEquipmentCatalog.json'
import {
  catalogById,
  fmtProgramDollars,
  hasTrainingEffects,
  parsePpFromAttributeLines,
  type ProgramDevAction,
  type ProgramEquipmentCatalog,
  type ProgramInventoryRow,
} from './programDevelopmentUtils'
import {
  buildPrestigeReportRows,
  formatTeamPoints,
  formatTeamPointsDelta,
  prestigeBandLabel,
} from './prestigeUtils'
import {
  buildOverallPlayoffColumns,
  buildRegionalPlayoffSlice,
  buildStatePlayoffFromResults,
  findPlayoffGame,
  firstRoundPairsFromSeeds,
  isRegionalPlayoffSeeds,
  type PlayoffSeedRow,
  PLAYOFF_FINAL_FOUR_VIEW,
  playoffDisplaySeedForTeam,
  playoffRegionsFromSeeds,
  roundNamesForBracketSize,
  userRegionFromSeeds,
  type PlayoffGameRow,
  type PlayoffRoundColumn,
} from './playoffBracketView'

/** Team menu value for the playoff bracket view (vs roster / depth / gameplans). */
const PLAYOFF_BRACKET_MENU = 'Playoff bracket'

/** Preseason hub: stage flow (playbook, depth, etc.). Other Team menu values show roster/stats/gameplans. */
const PRESEASON_TEAM_HUB = 'Preseason hub'
const OFFSEASON_TEAM_HUB = 'Offseason hub'
const SCHEDULE_PLANNING_HUB = 'Schedule hub'
const COACH_INBOX_MENU = 'Coach Inbox'

function defaultTeamMenuForPhase(phase: string): string {
  if (phase === 'preseason') return PRESEASON_TEAM_HUB
  if (phase === 'offseason') return OFFSEASON_TEAM_HUB
  if (phase === 'schedule_planning') return SCHEDULE_PLANNING_HUB
  if (phase === 'playoffs') return PLAYOFF_BRACKET_MENU
  return 'Roster'
}

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

const SEVEN_ON_SEVEN_TOURNAMENTS: {
  id: 'area' | 'regional' | 'state'
  label: string
  difficulty: string
  description: string
}[] = [
  {
    id: 'area',
    label: 'Area',
    difficulty: 'Easiest',
    description: 'Local programs. Softer competition and a friendly group stage.',
  },
  {
    id: 'regional',
    label: 'Regional',
    difficulty: 'Medium',
    description: 'Regional rivals and balanced fields. Standard 7-on-7 difficulty.',
  },
  {
    id: 'state',
    label: 'State',
    difficulty: 'Hardest',
    description: 'Statewide elite programs. Toughest bracket and crossover games.',
  },
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

function emptyCoachDevAllocations(): Record<string, number> {
  return Object.fromEntries(COACH_DEV_SKILLS.map(({ key }) => [key, 0])) as Record<string, number>
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
    homeGameThemes?: HomeThemeSelection[]
    homeGameThemesAck?: boolean
    playoffsSim?: boolean
    seasonFinish?: boolean
    crossRegionPicks?: { slot_index: number; opponent: string; user_home: boolean }[]
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
      program_development_actions?: ProgramDevAction[]
      seven_on_seven_tournament?: string
      seven_on_seven_ack_results?: boolean
    }
  }) => Promise<boolean>
  /** Latest save after sim (ref); use for back-to-back week sims before React re-renders. */
  getLiveSaveState?: () => any
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
  /** Browser saves: merge imported logos into the zip bundle and IndexedDB. */
  onImportLogosToBundle?: (logos: import('./saveBundle').SaveBundle['logos']) => Promise<void>
  /** Browser saves: merge stadium photos into the zip bundle and IndexedDB. */
  onImportStadiumsToBundle?: (stadiums: import('./saveBundle').SaveBundle['stadiums']) => Promise<void>
  /** Browser saves: merge helmet photos into the zip bundle and IndexedDB. */
  onImportHelmetsToBundle?: (helmets: import('./saveBundle').SaveBundle['helmets']) => Promise<void>
  /** Browser saves: merge jersey photos into the zip bundle and IndexedDB. */
  onImportJerseysToBundle?: (jerseys: import('./saveBundle').SaveBundle['jerseys']) => Promise<void>
  /** API saves: reload league_history.json when opening Team History. */
  onRefreshDynasty?: () => void | Promise<void>
  /** Multiplayer coach: league calendar advances on commish sim only. */
  leagueAdvanceLocked?: boolean
  /** Multiplayer coach: submit/unsubmit from My dynasty. */
  onSubmitWeek?: () => void | Promise<void>
  onUnsubmitWeek?: () => void | Promise<void>
  weekSubmitted?: boolean
  canUnsubmitWeek?: boolean
  submitWeekBusy?: boolean
  /** Multiplayer: commissioner sets human out-of-region schedules on the commish dashboard. */
  mpCommishLeagueId?: string
  mpCommishCrossRegionPlanning?: import('./multiplayer').CommishCrossRegionPlanningData
  onMpCommishCrossRegionPlanningChange?: (
    next: import('./multiplayer').CommishCrossRegionPlanningData,
  ) => void
  onReturnToLeagueHub?: () => void
}

type TeamHomePageBodyProps = Props & {
  logoVersion: number
  setLogoVersion: (n: number) => void
  stadiumVersion: number
  setStadiumVersion: (n: number) => void
  helmetVersion: number
  setHelmetVersion: (n: number) => void
  jerseyVersion: number
  setJerseyVersion: (n: number) => void
  onOpenSettings: () => void
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

function patchUserCoachCardsInState(state: any, userTeam: string, loadout: CoachingCardLoadout): any {
  if (!state || !userTeam || !Array.isArray(state.teams)) return state
  const cards = normalizeLoadout(loadout)
  const teams = state.teams.map((t: any) => {
    if (t?.name !== userTeam || !t?.coach) return t
    return { ...t, coach: { ...t.coach, coaching_cards: cards } }
  })
  return { ...state, teams }
}

function syncCanonicalOffseasonStagesInState(state: any): any {
  if (!state || String(state.season_phase ?? '').toLowerCase() !== 'offseason') return state
  const resolved = resolveOffseasonStagesFromSave(state)
  const canonical = [...CANONICAL_OFFSEASON_STAGES]
  const saved = state.offseason_stages
  const arraysMatch =
    Array.isArray(saved) &&
    saved.length === canonical.length &&
    saved.every((s: string, i: number) => s === canonical[i])
  if (arraysMatch && Number(state.offseason_stage_index ?? 0) === resolved.stageIndex) return state
  return {
    ...state,
    offseason_stages: canonical,
    offseason_stage_index: resolved.stageIndex,
  }
}

/** Matches backend `league_service._improvement_pp_delta` (offseason school Improvements). Negative = spend PP. */
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
  if (phase === 'schedule_planning') return 'Non-region selection'
  if (phase === 'offseason') return 'OffSeason'
  if (!phase) return '—'
  return safeStr(phase)
}

/** Align UI phase with save when league history is unavailable (e.g. next-opponent helper). */
function derivePhaseFromSave(saveState: any): string {
  return deriveUiPhaseFromSave(saveState)
}

/** Must match backend `OFFSEASON_UI_STAGES` in `league_service.py`. */
const CANONICAL_OFFSEASON_STAGES = [
  'Graduation',
  'Coach development',
  'Program Development',
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
  if (compact === 'programdevelopment' || compact === 'programdev' || compact === 'programbuilder') {
    return 'Program Development'
  }
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

/** Dashboard / schedule release: ``vs`` at home, ``@`` on the road. */
function formatScheduleOpponentLabel(opponent: string, userHome: boolean): string {
  const opp = String(opponent ?? '').trim()
  if (!opp || /^bye$/i.test(opp)) return opp || '—'
  return userHome ? `vs ${opp}` : `@ ${opp}`
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
    userHome: boolean
    gameIndex: number
    homeThemeLabel: string | null
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
        userHome: g.home === userTeam,
        gameIndex: gi,
        homeThemeLabel:
          g.home === userTeam ? themeLabelForGame(state, userTeam, wi + 1, gi) : null,
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
  homeThemeLabel: string | null
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
    const home = String(g?.home ?? '—')
    return {
      home,
      away: String(g?.away ?? '—'),
      played: Boolean(r?.played),
      homeScore: Number(r?.home_score ?? 0),
      awayScore: Number(r?.away_score ?? 0),
      ot: Boolean(r?.ot),
      recap: typeof r?.recap === 'string' ? r.recap : '',
      gameIndex: gi,
      homeThemeLabel: themeLabelForGame(state, home, week1Based, gi),
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
  homeThemeLabel: string | null
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
        homeThemeLabel: userHome ? themeLabelForGame(state, teamName, wi + 1, gi) : null,
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

/** Matches ``systems/league_structure.DEFAULT_REGION_KEY`` for teams without a region label. */
const DEFAULT_REGION_KEY = 'State'

function teamRegionLabel(regionMap: Map<string, string>, teamName: string): string {
  const r = regionMap.get(teamName) ?? ''
  return r.trim() || DEFAULT_REGION_KEY
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

function buildStandingsRows(
  state: any,
  classFilter: string | 'all' = 'all',
  regionFilter?: string | null,
) {
  const clsMap = teamClassificationMap(state)
  const regionMap = teamRegionMap(state)
  const standings = state?.standings ?? {}
  let teamNames = Object.keys(standings)
  if (classFilter !== 'all') {
    teamNames = teamNames.filter((n) => (clsMap.get(n) ?? '—') === classFilter)
  }
  if (regionFilter != null) {
    teamNames = teamNames.filter((n) => teamRegionLabel(regionMap, n) === regionFilter)
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

type RegionalStandingsGroup = {
  classification: string
  region: string
  title: string
  rows: ReturnType<typeof buildStandingsRows>
}

function listSchedulingPods(state: any, classFilter: string | 'all'): Omit<RegionalStandingsGroup, 'rows'>[] {
  const clsMap = teamClassificationMap(state)
  const regionMap = teamRegionMap(state)
  const seen = new Map<string, Omit<RegionalStandingsGroup, 'rows'>>()
  for (const t of state?.teams ?? []) {
    const name = String(t?.name ?? '').trim()
    if (!name) continue
    const classification = clsMap.get(name) ?? '—'
    if (classFilter !== 'all' && classification !== classFilter) continue
    const region = teamRegionLabel(regionMap, name)
    const key = `${classification}|${region}`
    if (!seen.has(key)) {
      const title = classFilter === 'all' ? `${classification} · ${region}` : region
      seen.set(key, { classification, region, title })
    }
  }
  return [...seen.values()].sort((a, b) => {
    if (a.classification !== b.classification) return a.classification.localeCompare(b.classification)
    return a.region.localeCompare(b.region, undefined, { numeric: true })
  })
}

function buildRegionalStandingsGroups(state: any, classFilter: string | 'all' = 'all'): RegionalStandingsGroup[] {
  return listSchedulingPods(state, classFilter).map((pod) => ({
    ...pod,
    rows: buildStandingsRows(
      state,
      classFilter === 'all' ? pod.classification : classFilter,
      pod.region,
    ),
  }))
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
  platinum_breakthrough_eligible?: boolean
  platinum_breakthrough?: boolean
  platinum_breakthrough_gain?: number
}

function BreakthroughStar({
  eligible,
  achieved,
  gain,
}: {
  eligible?: boolean
  achieved?: boolean
  gain?: number
}) {
  if (!eligible && !achieved) return null
  const title = achieved
    ? `Platinum breakthrough! +${gain ?? '?'} potential`
    : 'Near potential cap — platinum breakthrough chance this training cycle'
  return (
    <span
      className={`teamhome-breakthrough-star${achieved ? ' teamhome-breakthrough-star--hit' : ''}`}
      title={title}
      aria-label={title}
    >
      ★
    </span>
  )
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

function buildPlayoffView(state: any, classKey?: string | null, regionKey?: string | null) {
  let inner: {
    num_teams?: number
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

  const seeds: Array<{ seed: number; team: string; region?: string; region_seed?: number }> = Array.isArray(
    inner?.seeds,
  )
    ? inner.seeds
    : []
  const results: Array<any> = Array.isArray(inner?.bracket_results) ? inner.bracket_results : []
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

  if (!missingBracket && isRegionalPlayoffSeeds(seeds)) {
    const regions = playoffRegionsFromSeeds(seeds)
    if (regions.length) {
      const ut = String(state?.user_team || '').trim()
      const userReg = userRegionFromSeeds(seeds, ut)
      const rk = regionKey != null && String(regionKey).trim() !== '' ? String(regionKey).trim() : ''
      if (rk === PLAYOFF_FINAL_FOUR_VIEW) {
        const stateOnly = buildStatePlayoffFromResults(results)
        return {
          seeds,
          isRegional: true as const,
          viewFinalFour: true as const,
          regions,
          selectedRegion: PLAYOFF_FINAL_FOUR_VIEW,
          teamsPerRegion: 0,
          inRegionColumns: [] as PlayoffRoundColumn[],
          qfPairs: [] as { home: string; away: string }[],
          qf: [] as any[],
          sf: [] as any[],
          ch: [] as any[],
          sfRows: stateOnly.stateSfRows,
          chRow: stateOnly.stateChRow,
          completed,
          champion,
          viewClass,
          missingBracket,
        }
      }
      const selectedRegion =
        rk && regions.includes(rk) ? rk : userReg && regions.includes(userReg) ? userReg : regions[0]
      const slice = buildRegionalPlayoffSlice(seeds, results, selectedRegion)
      return {
        seeds,
        isRegional: true as const,
        viewFinalFour: false as const,
        regions,
        selectedRegion,
        teamsPerRegion: seeds.filter((s) => String(s.region) === selectedRegion).length,
        inRegionColumns: slice.inRegionColumns,
        qfPairs: [] as { home: string; away: string }[],
        qf: [] as any[],
        sf: [] as any[],
        ch: [] as any[],
        sfRows: slice.stateSfRows,
        chRow: slice.stateChRow,
        completed,
        champion,
        viewClass,
        missingBracket,
      }
    }
  }

  let bracketSize = Number((inner as { num_teams?: number })?.num_teams)
  const seedCount = seeds.length
  if (!Number.isFinite(bracketSize) || bracketSize < 2) {
    bracketSize = seedCount >= 2 ? seedCount : 8
  } else if (seedCount >= 2 && seedCount > bracketSize) {
    bracketSize = seedCount
  }
  const overallColumns = missingBracket
    ? ([] as PlayoffRoundColumn[])
    : buildOverallPlayoffColumns(seeds, results, bracketSize)

  return {
    seeds,
    isRegional: false as const,
    viewFinalFour: false as const,
    regions: [] as string[],
    selectedRegion: '',
    teamsPerRegion: 0,
    bracketSize,
    inRegionColumns: overallColumns,
    qfPairs: [] as { home: string; away: string }[],
    qf: [] as any[],
    sf: [] as any[],
    ch: [] as any[],
    sfRows: [] as any[],
    chRow: null as PlayoffGameRow | null,
    completed,
    champion,
    viewClass,
    missingBracket,
  }
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

function playoffBracketSizeFromInner(p: { num_teams?: number; seeds?: unknown[] } | null): number {
  if (!p) return 8
  const nt = Number(p.num_teams)
  if (Number.isFinite(nt) && nt >= 2) return nt
  const seeds = Array.isArray(p.seeds) ? p.seeds : []
  return seeds.length >= 2 ? seeds.length : 8
}

function playoffGridStyle(columnCount: number): CSSProperties {
  const cols = Math.max(1, Math.min(6, Math.floor(columnCount)))
  return { ['--playoff-cols' as string]: String(cols) }
}

function playoffRoundLabel(saveState: any): string {
  const p = userPlayoffInner(saveState)
  if (!p) return '—'
  if (p.completed && p.champion) return `Champion · ${p.champion}`
  const results = Array.isArray(p.bracket_results) ? p.bracket_results : []
  const size = playoffBracketSizeFromInner(p)
  const roundNames = roundNamesForBracketSize(size)
  let remaining = size
  for (const name of roundNames) {
    const required = remaining / 2
    const played = results.filter((g: any) => String(g.round || '') === name).length
    if (played < required) {
      return played > 0 ? `${name} (${played}/${required})` : name
    }
    remaining = required
  }
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

  const size = playoffBracketSizeFromInner(p)
  const roundNames = roundNamesForBracketSize(size)
  const firstRound = roundNames[0] ?? 'Quarterfinal'
  const firstGames = results.filter((g: any) => String(g.round || '') === firstRound)
  const firstPairs = firstRoundPairsFromSeeds(seeds, size)
  const firstRequired = size / 2

  if (firstGames.length < firstRequired) {
    const sn = Number(userSeed.seed)
    const pair = firstPairs.find((m) => m.home === userTeam || m.away === userTeam)
    if (pair) return pair.home === userTeam ? pair.away : pair.home
    if (Number.isFinite(sn) && sn > 0) {
      const oppSeed = size + 1 - sn
      return seeds.find((x: any) => Number(x.seed) === oppSeed)?.team ?? '—'
    }
    return '—'
  }

  let priorPairs = firstPairs
  let priorGames = firstGames
  for (let ri = 1; ri < roundNames.length; ri++) {
    const roundName = roundNames[ri]
    const roundGames = results.filter((g: any) => String(g.round || '') === roundName)
    const required = priorPairs.length / 2
    if (roundGames.length < required) {
      const myPrior = priorGames.find((g: any) => g.home === userTeam || g.away === userTeam)
      if (myPrior && myPrior.winner !== userTeam) return 'Eliminated'
      const projPairs = projPairsFromRound(priorGames, priorPairs)
      for (const pair of projPairs) {
        if (pair.home === userTeam) return pair.away
        if (pair.away === userTeam) return pair.home
      }
      return '—'
    }
    priorPairs = projPairsFromRound(priorGames, priorPairs)
    priorGames = roundGames
  }
  return '—'
}

function projPairsFromRound(
  priorGames: any[],
  priorPairs: { home: string; away: string }[],
): { home: string; away: string }[] {
  const w = (i: number) => {
    const pair = priorPairs[i]
    if (!pair) return null
    const g = findPlayoffGame(priorGames, pair)
    const winner = g?.winner
    return winner != null && String(winner).trim() !== '' ? String(winner) : null
  }
  return [
    { home: w(0) ?? 'TBD', away: w(3) ?? 'TBD' },
    { home: w(1) ?? 'TBD', away: w(2) ?? 'TBD' },
  ]
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
  getLiveSaveState,
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
  helmetVersion,
  setHelmetVersion,
  jerseyVersion,
  setJerseyVersion,
  onOpenSettings,
  leagueAdvanceLocked = false,
  onSubmitWeek,
  onUnsubmitWeek,
  weekSubmitted = false,
  canUnsubmitWeek = true,
  submitWeekBusy = false,
  onReturnToLeagueHub,
  mpCommishLeagueId,
  mpCommishCrossRegionPlanning,
  onMpCommishCrossRegionPlanningChange,
}: TeamHomePageBodyProps) {
  void backupReminderFrequency
  void onBackupReminderFrequencyChange
  void onBackupNow
  void setLogoVersion
  void setStadiumVersion
  void setHelmetVersion
  void setJerseyVersion
  const isLocalBundle = saveId === '__local__' || saveId.startsWith('b_')
  /** Browser/IDB saves use stateless /sim/game/* (no Bearer). Cloud saves need auth for /start-coach-game. */
  const canStartCoachPlay = Boolean(saveId) && (isLocalBundle || Boolean(headers?.Authorization))
  const saveStateFetchRef = useRef(saveState)
  saveStateFetchRef.current = saveState

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
  const phase = useMemo(
    () => deriveUiPhaseFromSave(saveState, leagueHistory),
    [saveState, leagueHistory],
  )
  const schedulePlanningInfo = useMemo(() => schedulePlanningInfoFromState(saveState), [saveState?.schedule_planning_info])
  const crossRegionSlotCount = useMemo(() => crossRegionSlotCountFromSave(saveState), [saveState?.user_cross_region_slot_count, saveState?.schedule_planning_info])
  const expectsCrossRegionPicks = useMemo(() => userClassExpectsCrossRegionPicks(saveState), [saveState?.user_team, saveState?.teams])
  const effectiveCrossRegionSlots = crossRegionSlotCount > 0 ? crossRegionSlotCount : expectsCrossRegionPicks ? Math.max(schedulePlanningInfo?.slot_count ?? 0, 1) : 0
  const [crossRegionSelections, setCrossRegionSelections] = useState<CrossRegionSelections>({})
  const crossRegionReady = useMemo(
    () => (schedulePlanningInfo ? allSlotsFilled(schedulePlanningInfo, crossRegionSelections) : false),
    [schedulePlanningInfo, crossRegionSelections],
  )
  const initialDynastySchedulePlanning = useMemo(
    () => isInitialDynastySchedulePlanning(saveState, phase),
    [saveState, phase],
  )
  const isMultiplayerLeague = useMemo(() => isMultiplayerLeagueSave(saveState), [saveState])
  const showCrossRegionPlanningUi = Boolean(
    schedulePlanningInfo &&
      !leagueAdvanceLocked &&
      !isMultiplayerLeague &&
      (phase === 'schedule_planning' ||
        (phase === 'season_summary' && effectiveCrossRegionSlots > 0)),
  )
  const needsCrossRegionPickUi = Boolean(showCrossRegionPlanningUi && !crossRegionReady)

  const commishCrossRegionBlocksAdvance = Boolean(
    mpCommishLeagueId && mpCommishCrossRegionPlanning?.active && !mpCommishCrossRegionPlanning.all_complete,
  )

  const scrollToSchedulePlanning = useCallback(() => {
    document.getElementById('schedplan-anchor')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])
  const [teamMenu, setTeamMenu] = useState(() => defaultTeamMenuForPhase(derivePhaseFromSave(saveState)))
  const [stateMenu, setStateMenu] = useState('Dashboard')
  const prevPhaseRef = useRef<string | null>(null)
  const crossRegionHydrateRef = useRef<string | null>(null)
  const [crossRegionSyncing, setCrossRegionSyncing] = useState(false)
  const playoffsComplete = phase === 'playoffs' && Boolean(saveState?.playoffs?.completed)
  const needsCrossRegionSync =
    phase === 'season_summary' ||
    phase === 'schedule_planning' ||
    playoffsComplete ||
    (phase === 'preseason' &&
      Array.isArray(saveState?.weeks) &&
      saveState.weeks.length > 0 &&
      !saveState?.cross_region_picks)

  useEffect(() => {
    if (!needsCrossRegionSync || !onSaveState) return
    const hydrateKey = `${saveId}:${saveState?.current_year}:${phase}:${Boolean(saveState?.cross_region_picks)}`
    if (crossRegionHydrateRef.current === hydrateKey) return
    crossRegionHydrateRef.current = hydrateKey
    let cancelled = false
    setCrossRegionSyncing(true)
    ;(async () => {
      try {
        const r = await fetch(`${apiBase}/sim/sync-state`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ state: saveStateFetchRef.current }),
        })
        if (!r.ok || cancelled) return
        const data = await r.json()
        if (data?.state) onSaveState(data.state)
      } catch {
        /* API offline — save still playable */
      } finally {
        if (!cancelled) setCrossRegionSyncing(false)
      }
    })()
    return () => {
      cancelled = true
      setCrossRegionSyncing(false)
    }
  }, [needsCrossRegionSync, phase, saveId, saveState?.current_year, saveState?.cross_region_picks, apiBase, onSaveState])

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
      setCrossRegionSelections({})
    }
    if (phase === 'schedule_planning' && prev !== 'schedule_planning') {
      setStateMenu('Dashboard')
      setTeamMenu(SCHEDULE_PLANNING_HUB)
    }
  }, [phase])
  useEffect(() => {
    if ((phase !== 'schedule_planning' && phase !== 'season_summary') || !schedulePlanningInfo) return
    const team = saveState?.user_team ?? ''
    const saved = crossRegionSelectionsFromSaved(saveState, team, schedulePlanningInfo)
    setCrossRegionSelections((prev) => {
      const next = { ...prev }
      let changed = false
      for (const slot of schedulePlanningInfo.slots) {
        const savedSel = saved[slot.slot_index]
        if (savedSel?.opponent) {
          if (
            next[slot.slot_index]?.opponent !== savedSel.opponent ||
            next[slot.slot_index]?.userHome !== savedSel.userHome
          ) {
            next[slot.slot_index] = savedSel
            changed = true
          }
          continue
        }
        if (next[slot.slot_index] === undefined) {
          next[slot.slot_index] = emptySlotSelection(slot.slot_index)
          changed = true
        }
      }
      return changed ? next : prev
    })
  }, [phase, schedulePlanningInfo, saveId, saveState?.cross_region_picks, saveState?.user_team])
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
    return list.filter((s) => {
      if (!s) return false
      if (!String(s.name || s.stage || '')) return false
      if (s.completed === false) return false
      return s.completed === true || s.played === true
    })
  }, [saveState?.preseason_scrimmages])
  const [teamScheduleTeam, setTeamScheduleTeam] = useState('')
  const [teamInfoTeam, setTeamInfoTeam] = useState('')
  const [facilitiesTeam, setFacilitiesTeam] = useState('')
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
  /** Regional playoffs: which scheduling region bracket to display (regional_8x4 / regional_4x4). */
  const [playoffBracketRegion, setPlayoffBracketRegion] = useState<string>('')
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
      setPlayoffBracketRegion('')
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
  const playoffRegionOptions = useMemo(() => {
    const bc = normalizePlayoffsByClass(saveState)
    if (!bc) return [] as string[]
    const rk = resolveBracketClassKey(bc, bracketClassForView || defaultPlayoffClass)
    const inner = rk && bc[rk] ? bc[rk] : null
    const seeds = Array.isArray(inner?.seeds) ? inner.seeds : []
    if (!isRegionalPlayoffSeeds(seeds)) return []
    return playoffRegionsFromSeeds(seeds)
  }, [saveState, bracketClassForView, defaultPlayoffClass])
  const defaultPlayoffRegion = useMemo(() => {
    if (!playoffRegionOptions.length) return ''
    const bc = normalizePlayoffsByClass(saveState)
    const rk = resolveBracketClassKey(bc, bracketClassForView || defaultPlayoffClass)
    const inner = rk && bc?.[rk] ? bc[rk] : null
    const seeds = Array.isArray(inner?.seeds) ? inner.seeds : []
    const ur = userRegionFromSeeds(seeds, String(saveState?.user_team || ''))
    return ur && playoffRegionOptions.includes(ur) ? ur : playoffRegionOptions[0]
  }, [saveState, bracketClassForView, defaultPlayoffClass, playoffRegionOptions, userTeam])
  const bracketRegionForView = useMemo(() => {
    const t = (playoffBracketRegion || '').trim()
    if (t) return t
    try {
      const s = sessionStorage.getItem(`fnd.playoff.viewRegion.${saveId}`)?.trim()
      if (s) return s
    } catch {
      /* ignore */
    }
    return defaultPlayoffRegion
  }, [playoffBracketRegion, defaultPlayoffRegion, saveId])
  const selectPlayoffRegionValue = useMemo(() => {
    const v = (playoffBracketRegion || '').trim()
    if (v) return v
    try {
      const s = sessionStorage.getItem(`fnd.playoff.viewRegion.${saveId}`)?.trim()
      if (s) return s
    } catch {
      /* ignore */
    }
    return defaultPlayoffRegion || playoffRegionOptions[0] || ''
  }, [playoffBracketRegion, defaultPlayoffRegion, playoffRegionOptions, saveId])
  const playoffView = useMemo(
    () => buildPlayoffView(saveState, bracketClassForView || null, bracketRegionForView || null),
    [saveState, bracketClassForView, bracketRegionForView],
  )
  const playoffSeedDisplayMode = playoffView.isRegional ? ('regional' as const) : ('overall' as const)
  const [teamHistoryLoading, setTeamHistoryLoading] = useState(false)
  const [teamRatingsRows, setTeamRatingsRows] = useState<TeamRatingRow[]>([])
  const [teamRatingsLoading, setTeamRatingsLoading] = useState(false)
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
  const inSeasonClassStandings = useMemo(
    () => buildStandingsRows(saveState, userClassification),
    [saveState, userClassification],
  )
  const seasonSummaryStandingsRows = useMemo(
    () => buildStandingsRows(saveState, bracketClassForView || userClassification).slice(0, 10),
    [saveState, bracketClassForView, userClassification],
  )

  const playoffBracketToolbar = useMemo(() => {
    if (playoffClassOptions.length <= 1 && playoffRegionOptions.length === 0) return null
    return (
      <div className="teamhome-playoffs-bracket-header season-summary-bracket-selectors">
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
              aria-label="Season summary playoff classification bracket"
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
        {playoffRegionOptions.length > 0 ? (
          <label className="teamhome-playoffs-class-label" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="teamhome-small" style={{ marginBottom: 0 }}>
              View
            </span>
            <select
              className="teamhome-select"
              value={selectPlayoffRegionValue}
              onChange={(e) => {
                const v = e.target.value
                setPlayoffBracketRegion(v)
                try {
                  sessionStorage.setItem(`fnd.playoff.viewRegion.${saveId}`, v)
                } catch {
                  /* ignore */
                }
              }}
              aria-label="Season summary playoff bracket view"
            >
              {playoffRegionOptions.map((r) => (
                <option key={r} value={r}>
                  Region {r}
                </option>
              ))}
              <option value={PLAYOFF_FINAL_FOUR_VIEW}>Final Four</option>
            </select>
          </label>
        ) : null}
      </div>
    )
  }, [
    playoffClassOptions,
    playoffRegionOptions,
    selectPlayoffClassValue,
    selectPlayoffRegionValue,
    saveId,
  ])
  const rankingsRows = useMemo(
    () => buildRankingsRows(saveState, leagueClassFilter),
    [saveState, leagueClassFilter],
  )
  const regionalStandingsGroups = useMemo(
    () => buildRegionalStandingsGroups(saveState, leagueClassFilter),
    [saveState, leagueClassFilter],
  )
  const statsRows = useMemo(() => buildStatsRows(saveState, leagueClassFilter), [saveState, leagueClassFilter])
  const teamStatRows = useMemo(
    () => buildTeamStatRows(saveState, leagueClassFilter),
    [saveState, leagueClassFilter],
  )
  const inSeasonUserStatsRow = useMemo(() => {
    const my = teamStatRows.find((r) => r.teamName === userTeam)
    if (!my) return null
    return {
      pointsFor: my.pointsFor,
      pointsAgainst: my.pointsAgainst,
      games: my.games,
      totalYards: my.totalYards,
      turnovers: my.turnovers,
    }
  }, [teamStatRows, userTeam])
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

  useEffect(() => {
    if (stateMenu !== 'Team Ratings' && stateMenu !== 'Team Info') return

    const applyClientRows = () => {
      setTeamRatingsRows(buildTeamRatingsFromSaveState(saveState))
    }

    if (isLocalBundle) {
      setTeamRatingsLoading(false)
      applyClientRows()
      return
    }

    applyClientRows()

    if (!apiBase || !saveId) {
      setTeamRatingsLoading(false)
      return
    }

    let cancelled = false
    setTeamRatingsLoading(true)
    void (async () => {
      try {
        const hdrs = headers?.Authorization ? headers : {}
        const rows = await fetchTeamRatings({ apiBase, saveId, headers: hdrs })
        if (!cancelled) {
          setTeamRatingsRows(rows)
          onError('')
        }
      } catch (e: unknown) {
        if (!cancelled) {
          applyClientRows()
          onError(e instanceof Error ? e.message : 'Failed to load team ratings from server (showing local estimate)')
        }
      } finally {
        if (!cancelled) setTeamRatingsLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- onError identity can churn from parent
  }, [stateMenu, apiBase, headers, saveId, isLocalBundle, saveState, saveState?.teams])

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
  const [pregamePreview, setPregamePreview] = useState<{ week: number; home: string; away: string } | null>(
    null,
  )

  const pregamePreviewData = useMemo(
    () => (pregamePreview ? buildPregamePreviewData(saveState, pregamePreview) : null),
    [saveState, pregamePreview],
  )

  const openPregamePreview = (week: number, home: string, away: string) => {
    if (!home || !away || home === '—' || away === '—') return
    setPregamePreview({ week, home, away })
  }

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

  useEffect(() => {
    if (!allTeamNames.length) return
    setFacilitiesTeam((prev) =>
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
  const gameOfTheWeek = useMemo(
    () => pickGameOfTheWeekForWeek(saveState, scheduleWeek),
    [saveState, scheduleWeek],
  )
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

  const renderPlayoffMatchupRow = (
    home: string,
    away: string,
    homeScore: number | null | undefined,
    awayScore: number | null | undefined,
    roundKey: string,
    exportEnabled: boolean,
    rowKey: string,
    projected = false,
  ) => (
    <div
      key={rowKey}
      className={`teamhome-playoffs-row teamhome-playoffs-row--stacked${projected ? ' teamhome-playoffs-row--projected' : ''}`}
    >
      <div className="teamhome-playoffs-matchup">
        {renderPlayoffBracketLine(home, homeScore, {
          playoffSeed: playoffDisplaySeedForTeam(playoffView.seeds, home, playoffSeedDisplayMode),
        })}
        {renderPlayoffBracketLine(away, awayScore, {
          playoffSeed: playoffDisplaySeedForTeam(playoffView.seeds, away, playoffSeedDisplayMode),
        })}
      </div>
      <div className="teamhome-playoffs-footer">
        {projected ? (
          <div className="teamhome-small teamhome-playoffs-projected-label">Projected — sim this round with Continue</div>
        ) : null}
        <div className="teamhome-playoffs-actions">
          <button
            type="button"
            className="teamhome-playoffs-link"
            disabled={!exportEnabled}
            onClick={async () => {
              try {
                await downloadPlayoffText(roundKey, home, away, 'box-score', playoffView.viewClass)
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
            disabled={!exportEnabled}
            onClick={async () => {
              try {
                await downloadPlayoffText(roundKey, home, away, 'game-log', playoffView.viewClass)
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

  const renderPlayoffRoundColumn = (col: PlayoffRoundColumn) => (
    <div className="teamhome-card" key={col.roundKey}>
      <div className="teamhome-card-title">{col.title}</div>
      <div className="teamhome-playoffs-list">
        {col.pairs.length > 0
          ? col.pairs.map((m) => {
              const played = findPlayoffGame(col.games, m)
              const playedHomeScore =
                played == null ? null : played.home === m.home ? played.home_score : played.away_score
              const playedAwayScore =
                played == null ? null : played.home === m.home ? played.away_score : played.home_score
              return renderPlayoffMatchupRow(
                m.home,
                m.away,
                playedHomeScore,
                playedAwayScore,
                col.roundKey,
                Boolean(played),
                `${col.roundKey}-${m.home}-${m.away}`,
              )
            })
          : col.rows.map((g, i) =>
              renderPlayoffMatchupRow(
                String(g.home),
                String(g.away),
                g.home_score,
                g.away_score,
                col.roundKey,
                g.home_score != null && !g.projected,
                `${col.roundKey}-row-${i}-${g.home}-${g.away}`,
                Boolean(g.projected),
              ),
            )}
      </div>
    </div>
  )

  const renderSeasonSummaryRoundColumn = (col: PlayoffRoundColumn) => (
    <div className="teamhome-card" key={col.roundKey}>
      <div className="teamhome-card-title">{col.title}</div>
      <div className="teamhome-playoffs-list">
        {col.pairs.length > 0
          ? col.pairs.map((m) => {
              const played = findPlayoffGame(col.games, m)
              const playedHomeScore =
                played == null ? null : played.home === m.home ? played.home_score : played.away_score
              const playedAwayScore =
                played == null ? null : played.home === m.home ? played.away_score : played.home_score
              return (
                <div key={`${col.roundKey}-${m.home}-${m.away}`} className="teamhome-playoffs-row teamhome-playoffs-row--stacked">
                  <div className="teamhome-playoffs-matchup">
                    {renderPlayoffBracketLine(m.home, playedHomeScore, {
                      playoffSeed: playoffDisplaySeedForTeam(playoffView.seeds, m.home, playoffSeedDisplayMode),
                    })}
                    {renderPlayoffBracketLine(m.away, playedAwayScore, {
                      playoffSeed: playoffDisplaySeedForTeam(playoffView.seeds, m.away, playoffSeedDisplayMode),
                    })}
                  </div>
                </div>
              )
            })
          : col.rows.map((g, i) => (
              <div
                key={`${col.roundKey}-row-${i}-${g.home}-${g.away}`}
                className="teamhome-playoffs-row teamhome-playoffs-row--stacked"
              >
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
  )

  const seasonSummaryBracketNode = useMemo(() => {
    if (playoffView.missingBracket) return null
    const bracketKey = `ss-bracket-${bracketClassForView}-${playoffView.selectedRegion ?? 'std'}`
    if (playoffView.isRegional && playoffView.viewFinalFour) {
      return (
        <div
          className="teamhome-playoffs-grid teamhome-playoffs-grid--final-four season-summary-bracket-readonly"
          key={bracketKey}
        >
          <div className="teamhome-card">
            <div className="teamhome-card-title">Semifinals</div>
            <div className="teamhome-playoffs-list">
              {playoffView.sfRows.map(
                (g: { home: string; away: string; home_score?: number | null; away_score?: number | null }, i: number) => (
                  <div key={`ss-sf-${i}-${g.home}-${g.away}`} className="teamhome-playoffs-row teamhome-playoffs-row--stacked">
                    <div className="teamhome-playoffs-matchup">
                      {renderPlayoffBracketLine(String(g.home), g.home_score, {
                        playoffSeed: playoffSeedForTeam(playoffView.seeds, String(g.home)),
                      })}
                      {renderPlayoffBracketLine(String(g.away), g.away_score, {
                        playoffSeed: playoffSeedForTeam(playoffView.seeds, String(g.away)),
                      })}
                    </div>
                  </div>
                ),
              )}
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
    }
    if (playoffView.isRegional) {
      return (
        <div
          className="teamhome-playoffs-grid teamhome-playoffs-grid--regional season-summary-bracket-readonly"
          key={bracketKey}
        >
          {playoffView.inRegionColumns.map((col) => renderSeasonSummaryRoundColumn(col))}
        </div>
      )
    }
    return (
      <div
        className="teamhome-playoffs-grid season-summary-bracket-readonly"
        key={bracketKey}
        style={playoffGridStyle(playoffView.inRegionColumns.length)}
      >
        {playoffView.inRegionColumns.map((col) => renderSeasonSummaryRoundColumn(col))}
      </div>
    )
  }, [playoffView, bracketClassForView, renderPlayoffBracketLine])

  const teamInfoViewTeam = teamInfoTeam || userTeam
  const teamInfoPageData = useMemo(() => {
    if (!teamInfoViewTeam) return null
    const rr = buildRecordAndRankForTeam(saveState, teamInfoViewTeam)
    const base = buildTeamInfoData({
      saveState,
      leagueHistory,
      teamName: teamInfoViewTeam,
      recordRank: {
        record: rr.record,
        stateRank: rr.rank,
        classRank: rr.classRank,
        classification: rr.classification,
      },
    })
    const rating = ratingsForTeam(teamRatingsRows, teamInfoViewTeam)
    return {
      ...base,
      ratings: rating
        ? {
            overall: rating.overall,
            offense: rating.offense,
            defense: rating.defense,
            run: rating.run,
            pass: rating.pass,
          }
        : null,
    }
  }, [saveState, leagueHistory, teamInfoViewTeam, teamRatingsRows])

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
    ) : stateMenu === 'Regional Standings' ? (
      <div className="teamhome-roster-shell teamhome-regional-standings-shell">
        {leagueClassFilterBar}
        <p className="teamhome-small teamhome-regional-standings-intro">
          Regular-season record within each scheduling region. Regional leaders (#1 in each pod) earn a regional title
          at the end of the season.
        </p>
        {regionalStandingsGroups.length === 0 ? (
          <div className="teamhome-roster-empty">No regional standings data yet.</div>
        ) : (
          regionalStandingsGroups.map((group) => (
            <section key={`${group.classification}-${group.region}`} className="teamhome-regional-standings-group">
              <h3 className="teamhome-regional-standings-title">{group.title}</h3>
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
                {group.rows.length === 0 ? (
                  <div className="teamhome-roster-empty">No teams in this region yet.</div>
                ) : (
                  group.rows.map((r, i) => (
                    <div key={`${group.region}-${r.teamName}-${i}`} className="teamhome-standings-row">
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
            </section>
          ))
        )}
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
          {gameOfTheWeek ? (
            <span className="teamhome-schedule-gotw-chip" title="Highest-profile matchup this week">
              <span className="teamhome-schedule-gotw-star" aria-hidden="true">
                ★
              </span>
              Game of the Week · {gameOfTheWeekLabel(gameOfTheWeek)}
            </span>
          ) : null}
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
              const gotw = isGameOfTheWeek(saveState, scheduleWeek, g.gameIndex)
              return (
                <div
                  key={`${g.home}-${g.away}-${g.gameIndex}`}
                  className={[
                    'teamhome-schedule-row',
                    'teamhome-schedule-row--weekly',
                    gotw ? 'teamhome-schedule-row--gotw' : '',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                >
                  <div className="teamhome-schedule-cell teamhome-schedule-team">
                    {gotw ? (
                      <span className="teamhome-schedule-gotw-star" title="Game of the Week" aria-label="Game of the Week">
                        ★
                      </span>
                    ) : null}
                    {teamWithLogo(g.home)}
                    {g.homeThemeLabel ? (
                      <div className="teamhome-schedule-theme teamhome-small">{g.homeThemeLabel}</div>
                    ) : null}
                  </div>
                  <div className="teamhome-schedule-cell teamhome-schedule-team">{teamWithLogo(g.away)}</div>
                  <div className="teamhome-schedule-cell teamhome-schedule-actions">
                    <span className="teamhome-schedule-score">{scoreShort}</span>
                    {!g.played ? (
                      <button
                        type="button"
                        className="teamhome-schedule-preview"
                        onClick={() => openPregamePreview(scheduleWeek, g.home, g.away)}
                      >
                        Preview
                      </button>
                    ) : null}
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
        {numScheduleWeeks > 0 && stateWeekGames.length > 0 ? (
          <div className="teamhome-schedule-gotw-legend teamhome-small">
            <span className="teamhome-schedule-gotw-star" aria-hidden="true">
              ★
            </span>
            Game of the Week — top marquee matchup by prestige, rivalry, and record
          </div>
        ) : null}
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
    ) : stateMenu === 'Team Ratings' ? (
      <TeamRatingsPage
        rows={teamRatingsRows}
        loading={teamRatingsLoading}
        classFilter={leagueClassFilter}
        classFilterBar={leagueClassFilterBar}
        apiBase={apiBase}
        headers={headers}
        logoVersion={logoVersion}
        userTeam={userTeam}
      />
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
          Week | Location | Opponent | Score | Result | Preview | Box score | Game log
        </div>
        <div className="teamhome-roster-table">
          {teamScheduleRows.length === 0 ? (
            <div className="teamhome-roster-empty">No schedule on file for this season.</div>
          ) : (
            teamScheduleRows.map((g) => {
              const userScore = g.userHome ? g.homeScore : g.awayScore
              const oppScore = g.userHome ? g.awayScore : g.homeScore
              const gotw = isGameOfTheWeek(saveState, g.week, g.gameIndex)
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
                    {gotw ? (
                      <span className="teamhome-schedule-gotw-star" title="Game of the Week">
                        ★
                      </span>
                    ) : null}
                    {g.isRegionGame ? (
                      <span className="teamhome-region-mark" title="Region game">*</span>
                    ) : null}
                    {g.userHome && g.homeThemeLabel ? (
                      <div className="teamhome-schedule-theme teamhome-small">{g.homeThemeLabel}</div>
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
                      className="teamhome-schedule-preview"
                      disabled={g.played}
                      onClick={() => openPregamePreview(g.week, g.home, g.away)}
                    >
                      Preview
                    </button>
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
    ) : stateMenu === 'Team Info' && teamInfoPageData ? (
      <TeamInfoPage
        data={teamInfoPageData}
        viewTeam={teamInfoViewTeam}
        allTeamNames={allTeamNames}
        userTeam={userTeam}
        onViewTeamChange={setTeamInfoTeam}
        apiBase={apiBase}
        headers={headers}
        logoVersion={logoVersion}
        stadiumVersion={stadiumVersion}
        helmetVersion={helmetVersion}
        jerseyVersion={jerseyVersion}
        hideChromeActions
      />
    ) : stateMenu === 'Facilities' ? (
      <TeamFacilitiesPage
        apiBase={apiBase}
        headers={headers}
        saveState={saveState}
        userTeam={userTeam}
        allTeamNames={allTeamNames}
        viewTeam={facilitiesTeam || userTeam}
        onViewTeamChange={setFacilitiesTeam}
      />
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
    ) : stateMenu === 'Coach Stats' ? (
      <CoachStatsPage
        saveState={saveState}
        leagueHistory={leagueHistory}
        apiBase={apiBase}
        headers={headers}
        logoVersion={logoVersion}
        userCoachName={String(findTeam(saveState, userTeam)?.coach?.name ?? '')}
      />
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

            {leagueHistEffectiveMode !== 'live' && lhArchivedSeasonEntry ? (
              <AllStateAwardsSection
                seasonEntry={lhArchivedSeasonEntry}
                userTeam={userTeam}
                apiBase={apiBase}
                headers={headers}
                logoVersion={logoVersion}
                defaultClass={String(
                  (saveState?.teams ?? []).find((t: { name?: string }) => t?.name === userTeam)?.classification ?? '',
                ).trim() || undefined}
              />
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
                    const results = Array.isArray(gamesRaw) ? (gamesRaw as PlayoffGameRow[]) : []
                    const seeds: PlayoffSeedRow[] = Array.isArray(inner?.seeds)
                      ? (inner.seeds as PlayoffSeedRow[])
                      : []
                    const seedForTeam = (name: string): number | null => {
                      const row = seeds.find((s) => String(s.team) === name)
                      const sn = Number(row?.seed)
                      return Number.isFinite(sn) && sn > 0 ? sn : null
                    }
                    const bracketSize = playoffBracketSizeFromInner({
                      num_teams: inner?.num_teams as number | undefined,
                      seeds,
                    })
                    const columns = buildOverallPlayoffColumns(seeds, results, bracketSize)
                    const roundShort = (title: string) => {
                      if (title === 'Championship') return 'Final'
                      if (title === 'Semifinal') return 'SF'
                      if (title === 'Quarterfinal') return 'QF'
                      if (title.startsWith('Round of ')) return title.replace('Round of ', 'R')
                      return title
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
                        <div
                          className="teamhome-playoffs-grid teamhome-league-history-playoffs-grid"
                          style={playoffGridStyle(columns.length)}
                        >
                          {columns.map((col) => (
                            <div key={`lh-po-${clsName}-${col.roundKey}`} className="teamhome-playoffs-microcol">
                              <div className="teamhome-microcol-title">{roundShort(col.title)}</div>
                              <div className="teamhome-playoffs-list">
                                {col.pairs.length > 0
                                  ? col.pairs.map((m) => {
                                      const played = findPlayoffGame(col.games, m)
                                      const ph =
                                        played == null
                                          ? undefined
                                          : played.home === m.home
                                            ? played.home_score
                                            : played.away_score
                                      const pa =
                                        played == null
                                          ? undefined
                                          : played.home === m.home
                                            ? played.away_score
                                            : played.home_score
                                      return (
                                        <div
                                          key={`lh-${clsName}-${col.roundKey}-${m.home}-${m.away}`}
                                          className="teamhome-playoffs-matchup"
                                        >
                                          {renderPlayoffBracketLine(String(m.home), typeof ph === 'number' ? ph : undefined, {
                                            playoffSeed: seedForTeam(m.home),
                                          })}
                                          {renderPlayoffBracketLine(String(m.away), typeof pa === 'number' ? pa : undefined, {
                                            playoffSeed: seedForTeam(m.away),
                                          })}
                                        </div>
                                      )
                                    })
                                  : col.rows.length > 0
                                    ? col.rows.map((g, i) => (
                                        <div
                                          key={`lh-${clsName}-${col.roundKey}-row-${i}`}
                                          className="teamhome-playoffs-matchup"
                                        >
                                          {renderPlayoffBracketLine(String(g.home), g.home_score ?? undefined, {
                                            playoffSeed: seedForTeam(String(g.home)),
                                          })}
                                          {renderPlayoffBracketLine(String(g.away), g.away_score ?? undefined, {
                                            playoffSeed: seedForTeam(String(g.away)),
                                          })}
                                        </div>
                                      ))
                                    : (
                                      <div className="teamhome-small" style={{ opacity: 0.8 }}>
                                        {col.title} pending.
                                      </div>
                                    )}
                              </div>
                            </div>
                          ))}
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
  const programFundingBalance = Number(userTeamObj?.program_funding_balance ?? 0)
  const programLastFundingIncome = Number(userTeamObj?.program_last_funding_income ?? 0)
  const userNickname = useMemo(() => {
    const raw = userTeamObj?.nickname ?? userTeamObj?.mascot
    const s = raw != null ? String(raw).trim() : ''
    return s || '—'
  }, [userTeamObj])
  const coach = userTeamObj?.coach ?? null

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
  const preseasonNextStageLabel = useMemo(() => {
    if (phase !== 'preseason' || !preseasonStages.length) return ''
    const i = preseasonStageIndex
    if (i < 0 || i >= preseasonStages.length) return '—'
    if (i < preseasonStages.length - 1) {
      return displayOffseasonStageLabel(preseasonStages[i + 1] ?? '')
    }
    return 'Regular season'
  }, [phase, preseasonStages, preseasonStageIndex])
  const lastOpponentText =
    phase === 'playoffs'
      ? playoffLast
      : last
        ? `${last.outcome}${last.ot ? ' (OT)' : ''} vs ${last.opponent} · ${last.userScore}-${last.oppScore}`
        : '—'

  const continueStyle: CSSProperties = rank === 1 ? { border: '2px solid rgba(125, 211, 252, 0.9)' } : {}

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
  const isHomeGameThemesStage = phase === 'preseason' && preseasonCurrentStage === 'Home Game Themes'
  const isSetGoalsStage = phase === 'preseason' && preseasonCurrentStage === 'Set Goals'
  const homeGameThemesConfirmed = useMemo(() => {
    if (isMultiplayerLeague) {
      const byTeam = saveState?.home_game_themes_confirmed_teams
      return Boolean(byTeam && typeof byTeam === 'object' && byTeam[userTeam])
    }
    return Boolean(saveState?.home_game_themes_user_confirmed)
  }, [isMultiplayerLeague, saveState?.home_game_themes_confirmed_teams, saveState?.home_game_themes_user_confirmed, userTeam])
  const [confirmingHomeThemes, setConfirmingHomeThemes] = useState(false)
  const isCoachingCarouselApplyStage =
    phase === 'offseason' &&
    (offseasonCurrentStage === 'Coaching carousel I' ||
      offseasonCurrentStage === 'Coaching carousel II' ||
      offseasonCurrentStage === 'Coaching carousel III')
  const isCoachingCarouselSummaryStage = phase === 'offseason' && offseasonCurrentStage === 'Coaching carousel IV'
  const isCoachingCarouselStage = isCoachingCarouselApplyStage || isCoachingCarouselSummaryStage
  const userSchemeNotice = saveState?.user_scheme_change_notice as
    | {
        headline?: string
        detail?: string
        playbooks_may_change?: boolean
        next_playbook_eligible_year?: number | null
        playbook_interval_seasons?: number
      }
    | undefined
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

  useEffect(() => {
    setShowPlaybookGamePlan(false)
  }, [preseasonCurrentStage])

  useEffect(() => {
    if (!isPlaySelectionStage || !saveId || hasPlaySelectionCache(saveId)) return
    let cancelled = false
    const stateSnapshot = saveState
    fetchPlaySelection(apiBase, saveId, stateSnapshot, headers)
      .then((json) => {
        if (cancelled) return
        cachePlaySelectionResponse(saveId, json)
        if (json.state) onSaveState?.(json.state)
      })
      .catch(() => {
        /* PlaybookGamePlanPage will fetch on open if prefetch fails */
      })
    return () => {
      cancelled = true
    }
    // Prefetch once per stage entry; avoid re-running on every saveState tick.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiBase, headers, isPlaySelectionStage, saveId])
  const [learningSummary, setLearningSummary] = useState<{
    offensive_pct_learned: number
    defensive_pct_learned: number
    overall_grade: string | null
  } | null>(null)
  const [learningLoading, setLearningLoading] = useState(false)
  const [confirmingResults, setConfirmingResults] = useState(false)
  const [positionDraft, setPositionDraft] = useState<Record<string, { position: string; secondary: string }>>({})
  const STAGE_GOAL_OPTIONS = [
    'Just to have fun',
    'Winning Season',
    'Playoffs',
    'Semifinal',
    'State Championship',
    'Title Winner',
  ]
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
  const [sevenOnSevenTier, setSevenOnSevenTier] = useState<'area' | 'regional' | 'state'>('regional')
  const [improveFacCumulative, setImproveFacCumulative] = useState(0)
  const [improveCulCumulative, setImproveCulCumulative] = useState(0)
  const [improveBooCumulative, setImproveBooCumulative] = useState(0)
  const [coachDevAllocations, setCoachDevAllocations] = useState<Record<string, number>>(() => emptyCoachDevAllocations())
  const [coachingCardsLoadout, setCoachingCardsLoadout] = useState<CoachingCardLoadout>(() => ({ ...EMPTY_COACHING_LOADOUT }))
  const [coachDevSavedLoadout, setCoachDevSavedLoadout] = useState<CoachingCardLoadout>(() => ({ ...EMPTY_COACHING_LOADOUT }))
  const coachDevCardsHydratedRef = useRef(false)
  const offseasonStagesSyncedRef = useRef(false)

  const handleCoachingCardsLoadoutChange = useCallback(
    (next: CoachingCardLoadout) => {
      setCoachingCardsLoadout(next)
      if (phase !== 'offseason' || offseasonCurrentStage !== 'Coach development' || !onSaveState) return
      const live = getLiveSaveState?.() ?? saveState
      onSaveState(patchUserCoachCardsInState(live, userTeam, next))
    },
    [phase, offseasonCurrentStage, onSaveState, getLiveSaveState, saveState, userTeam],
  )
  const [programDevPendingActions, setProgramDevPendingActions] = useState<ProgramDevAction[]>([])
  const [offseasonTrainingSort, setOffseasonTrainingSort] = useState<OffseasonTrainingSortMode>('position')
  const [offseasonReportPlayer, setOffseasonReportPlayer] = useState<string | null>(null)
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
  const positionCoachRecommendations = useMemo(() => {
    if (!isPositionChangesStage || !userTeam) {
      return {} as ReturnType<typeof recommendBalancedPositionsForRoster>
    }
    const roster = (findTeam(saveState, userTeam)?.roster ?? []) as Record<string, unknown>[]
    return recommendBalancedPositionsForRoster(roster)
  }, [isPositionChangesStage, saveState, userTeam])
  const positionDraftCounts = useMemo(() => countPrimaryPositions(positionDraft), [positionDraft])
  const positionTargetCounts = useMemo(() => {
    if (!isPositionChangesStage || !userTeam) return {} as Record<string, number>
    const rosterSize = findTeam(saveState, userTeam)?.roster?.length ?? 0
    return primaryPositionTargets(rosterSize)
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

  useEffect(() => {
    if (phase !== 'offseason' || offseasonCurrentStage !== 'Coach development') {
      coachDevCardsHydratedRef.current = false
      return
    }
    if (coachDevCardsHydratedRef.current) return
    coachDevCardsHydratedRef.current = true
    const coachObj = findTeam(saveState, userTeam)?.coach
    const normalized = normalizeLoadout(coachObj?.coaching_cards)
    setCoachingCardsLoadout(normalized)
    setCoachDevSavedLoadout(normalized)
  }, [phase, offseasonCurrentStage, saveState, userTeam])

  useEffect(() => {
    if (phase !== 'offseason' || !onSaveState) {
      offseasonStagesSyncedRef.current = false
      return
    }
    if (offseasonStagesSyncedRef.current) return
    const raw = getLiveSaveState?.() ?? saveState
    const synced = syncCanonicalOffseasonStagesInState(raw)
    offseasonStagesSyncedRef.current = true
    if (synced.offseason_stages !== raw?.offseason_stages || synced.offseason_stage_index !== raw?.offseason_stage_index) {
      onSaveState(synced)
    }
  }, [phase, onSaveState, getLiveSaveState, saveState])

  useEffect(() => {
    if (phase !== 'offseason' || offseasonCurrentStage !== 'Program Development') {
      setProgramDevPendingActions([])
    }
  }, [phase, offseasonCurrentStage])

  const flushMpPrepAndSubmitWeek = async () => {
    if (!onSubmitWeek) return
    if (
      isMultiplayerLeague &&
      phase === 'offseason' &&
      offseasonCurrentStage === 'Program Development' &&
      programDevPendingActions.length
    ) {
      const ok = await onSimWeek({ offseasonBody: { program_development_actions: programDevPendingActions } })
      if (ok === false) return
      setProgramDevPendingActions([])
    }
    await onSubmitWeek()
  }

  const coachDevBank = saveState?.offseason_coach_dev_bank
  const coachDevTotalCp = Number(coachDevBank?.cp_total ?? 0)
  const coachDevAllocatedCp = COACH_DEV_SKILLS.reduce((sum, { key }) => sum + Number(coachDevAllocations[key] ?? 0), 0)
  const coachDevCardLedger = (coachDevBank?.card_ledger ?? {}) as Record<string, number>
  const coachDevCardNetCost = useMemo(
    () => computeLoadoutChangeCp(coachDevSavedLoadout, coachingCardsLoadout, coachDevCardLedger).netCost,
    [coachDevSavedLoadout, coachingCardsLoadout, coachDevCardLedger],
  )
  const coachDevProjectedTotalCp = Math.round((coachDevTotalCp - coachDevCardNetCost) * 10) / 10
  const coachDevAvailableCp = Math.round((coachDevProjectedTotalCp - coachDevAllocatedCp) * 10) / 10
  const coachDevBreakdown = (coachDevBank?.breakdown ?? null) as CoachDevBreakdown | null
  const springBallResult = saveState?.offseason_spring_ball_results?.user_team_result ?? null
  const sevenOnSevenResult = saveState?.offseason_7on7_results ?? null
  const winterTrainingResult = saveState?.offseason_winter_training_results?.user_team_result ?? null
  const transferStage1 = saveState?.offseason_transfer_stage_1 ?? null
  const transferStage2 = saveState?.offseason_transfer_stage_2 ?? null
  const transferReview = saveState?.offseason_transfer_review ?? null
  const transferStage1PendingReview = Boolean(saveState?.offseason_transfer_stage_1_pending_review)
  const transferStage2PendingReview = Boolean(saveState?.offseason_transfer_stage_2_pending_review)
  const transfersDisabled = Boolean(saveState?.transfers_disabled)
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
    const equipmentPp = Number((raw as { equipment_pp_total?: number }).equipment_pp_total ?? 0)
    const net = Number((raw as { pp_total?: number }).pp_total ?? 0)
    return {
      rs,
      playoffWinPp,
      placementPp,
      placementLabel,
      goalPts,
      equipmentPp,
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
      badge: string
      accent: string
      accentDim: string
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
    const atProgramFloor = vFacFrom === 0 && vCulFrom === 0 && vBooFrom === 0
    const targetsAtFloor =
      improveFacCumulative === 0 && improveCulCumulative === 0 && improveBooCumulative === 0
    /** PP bank underwater but every pillar already at grade 1 — nothing left to refund. */
    const stuckAtFloorDebt = atProgramFloor && targetsAtFloor && projectedRemaining < 0
    const invalid = projectedRemaining < 0 && !stuckAtFloorDebt
    const shortfall = invalid ? Math.max(0, Math.ceil(-projectedRemaining)) : 0
    const pillars = [
      {
        id: 'facilities',
        label: 'Facilities',
        badge: PROGRAM_INVESTMENT_PILLAR_THEME.facilities.badge,
        accent: PROGRAM_INVESTMENT_PILLAR_THEME.facilities.accent,
        accentDim: PROGRAM_INVESTMENT_PILLAR_THEME.facilities.accentDim,
        fromCumulative: vFacFrom,
        targetCumulative: improveFacCumulative,
        pillarDeltaPp: facD,
      },
      {
        id: 'culture',
        label: 'Culture',
        badge: PROGRAM_INVESTMENT_PILLAR_THEME.culture.badge,
        accent: PROGRAM_INVESTMENT_PILLAR_THEME.culture.accent,
        accentDim: PROGRAM_INVESTMENT_PILLAR_THEME.culture.accentDim,
        fromCumulative: vCulFrom,
        targetCumulative: improveCulCumulative,
        pillarDeltaPp: culD,
      },
      {
        id: 'boosters',
        label: 'Booster support',
        badge: PROGRAM_INVESTMENT_PILLAR_THEME.boosters.badge,
        accent: PROGRAM_INVESTMENT_PILLAR_THEME.boosters.accent,
        accentDim: PROGRAM_INVESTMENT_PILLAR_THEME.boosters.accentDim,
        fromCumulative: vBooFrom,
        targetCumulative: improveBooCumulative,
        pillarDeltaPp: booD,
      },
    ]
    return {
      invalid,
      projectedRemaining,
      shortfall,
      deltaPp,
      ppRemaining,
      ppTotal,
      pillars,
      atProgramFloor,
      targetsAtFloor,
      stuckAtFloorDebt,
    }
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

  const improvementsResetKey = useMemo(() => {
    if (phase !== 'offseason' || offseasonCurrentStage !== 'Improvements') return ''
    const t = findTeam(saveState, userTeam)
    const fac = pillarCumulativePpValue(Number(t?.facilities_grade ?? 5), Number(t?.facilities_progress_pts ?? 0))
    const cul = pillarCumulativePpValue(Number(t?.culture_grade ?? 5), Number(t?.culture_progress_pts ?? 0))
    const boo = pillarCumulativePpValue(Number(t?.booster_support ?? 5), Number(t?.boosters_progress_pts ?? 0))
    return `${userTeam}-${saveState?.current_year ?? 0}-${fac}-${cul}-${boo}`
  }, [phase, offseasonCurrentStage, saveState, userTeam])

  const handleImprovementTargetChange = useCallback((pillarId: string, nextCumulative: number) => {
    if (pillarId === 'facilities') setImproveFacCumulative(nextCumulative)
    else if (pillarId === 'culture') setImproveCulCumulative(nextCumulative)
    else setImproveBooCumulative(nextCumulative)
  }, [])

  const offseasonTrainingRowsRaw = useMemo(
    () => (saveState?.offseason_training_results?.players ?? []) as OffseasonTrainingRow[],
    [saveState?.offseason_training_results],
  )
  const sortedOffseasonTrainingRows = useMemo(
    () => sortOffseasonTrainingRows(offseasonTrainingRowsRaw, offseasonTrainingSort),
    [offseasonTrainingRowsRaw, offseasonTrainingSort],
  )
  const trainingBreakthroughEligibleNames = useMemo(() => {
    if (phase !== 'offseason') return new Set<string>()
    const saved = (saveState?.offseason_training_results?.breakthrough_eligible ?? []) as string[]
    if (saved.length > 0) return new Set(saved.map(String))
    const team = findTeam(saveState, userTeam)
    if (!team) return new Set<string>()
    const loadout = normalizeLoadout((team as { coach?: { coaching_cards?: unknown } }).coach?.coaching_cards)
    const names = ((team as { roster?: Record<string, unknown>[] }).roster ?? [])
      .filter((p) => isPlatinumBreakthroughEligible(p, loadout))
      .map((p) => String(p.name ?? ''))
      .filter(Boolean)
    return new Set(names)
  }, [phase, saveState, userTeam])
  const offseasonPlayerReport = useMemo(() => {
    if (!offseasonReportPlayer || !userTeam) return null
    return buildOffseasonPlayerReport(saveState, userTeam, offseasonReportPlayer)
  }, [offseasonReportPlayer, saveState, userTeam])
  const trainingEquipmentPreview = useMemo(() => {
    if (phase !== 'offseason' || offseasonCurrentStage !== 'Training Results') return []
    const t = findTeam(saveState, userTeam)
    const inv = (t?.program_equipment || []) as ProgramInventoryRow[]
    const byId = catalogById(catalogJson as ProgramEquipmentCatalog)
    return inv
      .filter((r) => Number(r.seasons_remaining ?? 0) > 0)
      .map((r) => {
        const spec = byId[String(r.item_id)]
        if (!spec) return null
        const attrs = spec.attributes_affected || []
        return {
          name: spec.name,
          attrs,
          hasTraining: hasTrainingEffects(attrs),
          pp: parsePpFromAttributeLines(attrs),
        }
      })
      .filter(Boolean) as Array<{ name: string; attrs: string[]; hasTraining: boolean; pp: number }>
  }, [phase, offseasonCurrentStage, saveState, userTeam])
  const trainingEquipmentApplied = saveState?.offseason_training_results?.equipment as
    | { ui_rows?: Array<{ name: string; labels: string[] }>; equipment_points_applied?: number }
    | undefined
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
    fetchPlayLearningSummary(apiBase, saveId, saveStateFetchRef.current, headers)
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
        onSaveState={onSaveState}
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
        getLiveSaveState={getLiveSaveState}
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
                const live = getLiveSaveState?.() ?? saveState
                const r = await fetch(path, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ state: live, game }),
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
            try {
              const data = await saveDepthChart(apiBase, saveId, saveState, headers, depthChart)
              if (data?.state) onSaveState(data.state)
              onError('')
            } catch (e: unknown) {
              onError(e instanceof Error ? e.message : 'Failed to save depth chart')
            }
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
          onSaveState={onSaveState}
          readOnly
          headerBackLabel="Back to Team Home"
        />
      )
    }
    if (teamMenu === 'OFF Gameplan') {
      return (
        <CoachGameplanPage
          apiBase={apiBase}
          headers={headers}
          saveId={saveId}
          saveState={saveState}
          side="offense"
          onBack={gpBack}
          onError={onError}
          onSaveState={onSaveState}
        />
      )
    }
    if (teamMenu === 'DEF Gameplan') {
      return (
        <CoachGameplanPage
          apiBase={apiBase}
          headers={headers}
          saveId={saveId}
          saveState={saveState}
          side="defense"
          onBack={gpBack}
          onError={onError}
          onSaveState={onSaveState}
        />
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
            getLiveSaveState={getLiveSaveState}
            onSaveState={onSaveState}
            onError={onError}
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
            {phase !== 'preseason' ? <option>OFF Gameplan</option> : null}
            {phase !== 'preseason' ? <option>DEF Gameplan</option> : null}
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
            <option value="Regional Standings">Regional Standings</option>
            <option value="Weekly schedule">Weekly schedule</option>
            <option value="Team Schedule">Team Schedule</option>
            <option value="Rankings">Rankings</option>
            <option value="Team Ratings">Team Ratings</option>
            <option value="Stats">Stats</option>
            <option value="Team Info">Team Info</option>
            <option value="Facilities">Facilities</option>
            <option value="Coaching changes">Coaching changes</option>
            <option value="Coach Stats">Coach Stats</option>
            <option value="Team History">Team History</option>
            <option value="Prestige report">Prestige report</option>
            <option value="League History">League History</option>
          </select>
        </div>
        <div className="teamhome-top-actions">
          {phase === 'offseason' || phase === 'preseason' ? (
            <div className="teamhome-offseason-stage-inline" aria-live="polite">
              <div className="teamhome-offseason-stage-inline-row">
                <span className="teamhome-offseason-stage-k">Now</span>
                <span className="teamhome-offseason-stage-v">
                  {phase === 'preseason'
                    ? displayOffseasonStageLabel(preseasonCurrentStage || 'Preseason')
                    : displayOffseasonStageLabel(offseasonCurrentStage || 'Offseason')}
                </span>
                <span className="teamhome-offseason-stage-sep" aria-hidden>
                  ·
                </span>
                <span className="teamhome-offseason-stage-k">Next</span>
                <span className="teamhome-offseason-stage-v">
                  {phase === 'preseason' ? preseasonNextStageLabel || '—' : offseasonNextStageLabel || '—'}
                </span>
              </div>
            </div>
          ) : null}
          <div className="teamhome-top-actions-end">
          {phase === 'offseason' ? (
            <div className="teamhome-program-balance" title="Program funding balance (carries over year to year, max $250,000)">
              <span className="teamhome-program-balance-k">Program balance</span>
              <span className="teamhome-program-balance-v">{fmtProgramDollars(programFundingBalance)}</span>
              {programLastFundingIncome > 0 ? (
                <span className="teamhome-program-balance-inc">+{fmtProgramDollars(programLastFundingIncome)} this season</span>
              ) : null}
            </div>
          ) : null}
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
              (phase === 'offseason' && offseasonCurrentStage === 'Improvements' && improvementsBudget.invalid) ||
              (isHomeGameThemesStage && !homeGameThemesConfirmed) ||
              (effectiveCrossRegionSlots > 0 &&
                phase === 'season_summary' &&
                (!schedulePlanningInfo || !crossRegionReady)) ||
              (phase === 'schedule_planning' && (!schedulePlanningInfo || !crossRegionReady)) ||
              (crossRegionSyncing && !crossRegionReady && !isMultiplayerLeague) ||
              commishCrossRegionBlocksAdvance ||
              (isMultiplayerLeague && leagueAdvanceLocked && phase === 'season_summary')
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
                    coaching_cards?: CoachingCardLoadout
                    carousel_job_applications?: string[]
                    transfer_stage_1_ack_results?: boolean
                    transfer_stage_2_ack_results?: boolean
                    program_development_actions?: ProgramDevAction[]
                    seven_on_seven_tournament?: string
                    seven_on_seven_ack_results?: boolean
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
                    const cards = normalizeLoadout(coachingCardsLoadout)
                    offseasonBody = {
                      coach_dev_allocations: coachDevAllocations,
                      coaching_cards: cards,
                    }
                    if (onSaveState) {
                      const live = getLiveSaveState?.() ?? saveState
                      const synced = syncCanonicalOffseasonStagesInState(live)
                      onSaveState(patchUserCoachCardsInState(synced, userTeam, cards))
                    }
                  } else if (offseasonCurrentStage === 'Program Development') {
                    offseasonBody = { program_development_actions: programDevPendingActions }
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
                  } else if (offseasonCurrentStage === '7 on 7') {
                    offseasonBody = sevenOnSevenResult
                      ? { seven_on_seven_ack_results: true }
                      : { seven_on_seven_tournament: sevenOnSevenTier }
                  }
                  const ok = await onSimWeek({ offseasonBody })
                  if (ok !== false && offseasonCurrentStage === 'Program Development') {
                    setProgramDevPendingActions([])
                  }
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
                } else if (phase === 'preseason' && isHomeGameThemesStage) {
                  await onSimWeek({ homeGameThemesAck: true })
                } else if (phase === 'season_summary') {
                  await onSimWeek({
                    seasonFinish: true,
                    ...(effectiveCrossRegionSlots > 0 && schedulePlanningInfo && !isMultiplayerLeague
                      ? {
                          crossRegionPicks: buildCrossRegionPicksPayload(
                            schedulePlanningInfo,
                            crossRegionSelections,
                          ),
                        }
                      : {}),
                  })
                } else if (phase === 'schedule_planning' && schedulePlanningInfo) {
                  await onSimWeek({
                    seasonFinish: true,
                    crossRegionPicks: buildCrossRegionPicksPayload(schedulePlanningInfo, crossRegionSelections),
                  })
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
              phase === 'schedule_planning'
                ? crossRegionReady
                  ? 'Build the schedule and continue'
                  : 'Choose an opponent for each out-of-region game'
                : phase === 'season_summary'
                ? effectiveCrossRegionSlots > 0
                  ? crossRegionReady
                    ? 'Confirm out-of-region opponents and continue to graduation'
                    : 'Choose an opponent for each out-of-region game'
                  : commishCrossRegionBlocksAdvance
                    ? 'Save out-of-region schedules for every human school first'
                    : 'Continue to graduation and offseason'
                : phase === 'playoffs' && playoffsComplete
                ? 'Playoffs complete — Continue to open season summary'
                : phase === 'playoffs'
                  ? `Simulate the next playoff round (${playoffRoundDisplay === '—' ? 'see bracket' : playoffRoundDisplay})`
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
                                  : isHomeGameThemesStage
                                    ? 'Confirm home game themes below first'
                                    : isSetGoalsStage
                                      ? 'Confirm goals below'
                                      : 'Simulate the current week and advance'
            }
          >
            {phase === 'regular' && simmingWeek
              ? 'Simming week…'
                : phase === 'playoffs' && simmingWeek
                ? 'Simming playoffs…'
                : phase === 'schedule_planning'
                  ? 'Confirm schedule'
                : phase === 'season_summary'
                  ? mpCommishLeagueId && mpCommishCrossRegionPlanning?.active
                    ? 'Advance league'
                    : 'Continue'
                  : 'Continue'}
          </button>
          {leagueAdvanceLocked && onReturnToLeagueHub ? (
            <button
              type="button"
              className="teamhome-select"
              onClick={onReturnToLeagueHub}
              title="Back to League Hub"
            >
              League Hub
            </button>
          ) : null}
          {leagueAdvanceLocked && onSubmitWeek && !weekSubmitted ? (
            <button
              type="button"
              className="teamhome-select"
              disabled={submitWeekBusy}
              onClick={() => void flushMpPrepAndSubmitWeek()}
              title="Submit your prep for this week"
            >
              {submitWeekBusy ? 'Submitting…' : 'Submit week'}
            </button>
          ) : null}
          {leagueAdvanceLocked && onUnsubmitWeek && weekSubmitted ? (
            <button
              type="button"
              className="teamhome-select"
              disabled={submitWeekBusy || canUnsubmitWeek === false}
              onClick={() => void onUnsubmitWeek()}
              title={
                canUnsubmitWeek === false
                  ? 'Locked — too close to the advance deadline'
                  : 'Unsubmit so you can keep prepping'
              }
            >
              {submitWeekBusy ? '…' : 'Unsubmit'}
            </button>
          ) : null}
          <button type="button" className="teamhome-select" onClick={onOpenSettings} title="Settings">
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
              ? displayOffseasonStageLabel(preseasonCurrentStage || 'Preseason')
              : phase === 'offseason'
                ? displayOffseasonStageLabel(offseasonCurrentStage || 'Offseason')
                : phase === 'season_summary'
                  ? 'Season summary'
                  : phase === 'schedule_planning'
                    ? 'Non-region selection'
                  : formatStage(phase)}
          </div>
        </div>
        <div className="teamhome-top-group">
          <div className="teamhome-top-label">
            {phase === 'playoffs'
              ? 'PLAYOFF STATUS'
              : phase === 'offseason'
                ? 'OFFSEASON STEP'
                : phase === 'preseason'
                  ? 'PRESEASON STEP'
                : phase === 'season_summary'
                  ? 'SEASON YEAR'
                  : phase === 'schedule_planning'
                    ? 'NON-REGION STEP'
                    : 'CURRENT WEEK'}
          </div>
          <div className="teamhome-top-value">
            {phase === 'playoffs'
              ? playoffRoundDisplay
              : phase === 'offseason'
                ? offseasonStages.length
                  ? `${Math.min(offseasonStageIndex + 1, offseasonStages.length)} / ${offseasonStages.length}`
                  : '—'
                : phase === 'preseason'
                  ? preseasonStages.length
                    ? `${Math.min(preseasonStageIndex + 1, preseasonStages.length)} / ${preseasonStages.length}`
                    : '—'
                : phase === 'season_summary'
                  ? saveState?.current_year ?? '—'
                  : phase === 'schedule_planning'
                    ? 'Choose opponents'
                    : saveState?.current_week ?? '—'}
          </div>
        </div>
        <div className="teamhome-top-group">
          <div className="teamhome-top-label">
            {phase === 'season_summary' || phase === 'schedule_planning'
              ? 'NEXT STEP'
              : phase === 'preseason' || phase === 'offseason'
                ? 'NEXT STAGE'
                : 'NEXT OPPONENT'}
          </div>
          <div className="teamhome-top-value">
            {phase === 'season_summary'
              ? crossRegionSyncing
                ? 'Checking schedule…'
                : effectiveCrossRegionSlots > 0
                ? `Non-region selection · ${effectiveCrossRegionSlots} ${effectiveCrossRegionSlots === 1 ? 'game' : 'games'}`
                : 'Offseason · Graduation'
              : phase === 'schedule_planning'
                ? effectiveCrossRegionSlots > 0
                  ? `Pick ${effectiveCrossRegionSlots} out-of-region ${effectiveCrossRegionSlots === 1 ? 'opponent' : 'opponents'}`
                  : 'Confirm schedule'
              : phase === 'preseason'
                ? preseasonNextStageLabel || 'Regular season'
                : phase === 'offseason'
                  ? offseasonNextStageLabel || '—'
                  : nextOpponentText}
          </div>
        </div>
        <div className="teamhome-top-group">
          <div className="teamhome-top-label">{phase === 'playoffs' ? 'LAST PLAYOFF GAME' : 'LAST WEEKS RESULTS'}</div>
          <div className="teamhome-top-value">{lastOpponentText}</div>
        </div>
      </div>

      <div className="teamhome-content">
        {phase === 'season_summary' || phase === 'schedule_planning' ? (
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
            <div className="teamhome-season-end-stack">
              {mpCommishLeagueId && mpCommishCrossRegionPlanning?.active ? (
                <CommishCrossRegionPlanning
                  apiBase={apiBase}
                  headers={headers}
                  leagueId={mpCommishLeagueId}
                  planning={mpCommishCrossRegionPlanning}
                  logoVersion={logoVersion}
                  compact
                  onPlanningChange={onMpCommishCrossRegionPlanningChange}
                />
              ) : null}
              {needsCrossRegionPickUi ? (
                <SchedulePlanningScrollCallout
                  slotCount={effectiveCrossRegionSlots || schedulePlanningInfo?.slot_count || 1}
                  variant={initialDynastySchedulePlanning ? 'start' : 'scroll'}
                  onScrollToPicks={initialDynastySchedulePlanning ? undefined : scrollToSchedulePlanning}
                />
              ) : null}
              {initialDynastySchedulePlanning ? (
                <div className="schedplan-welcome">
                  <h2 className="schedplan-welcome-title">Welcome to your dynasty</h2>
                  <p className="schedplan-welcome-text">
                    Before your first season kicks off, choose who you play from other regions in your class.
                    In-region games are already on the calendar.
                  </p>
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
                  bracketToolbar={playoffBracketToolbar}
                  teamWithLogo={teamWithLogo}
                  onOpenLeagueHistory={() => setStateMenu('League History')}
                  onOpenTeamHistory={() => setStateMenu('Team History')}
                />
              )}
              {showCrossRegionPlanningUi && schedulePlanningInfo ? (
                <SchedulePlanningPanel
                  apiBase={apiBase}
                  headers={headers}
                  logoVersion={logoVersion}
                  userTeam={userTeam}
                  seasonYear={Number(saveState?.current_year ?? '—')}
                  info={schedulePlanningInfo}
                  selections={crossRegionSelections}
                  onSelectionsChange={setCrossRegionSelections}
                />
              ) : isMultiplayerLeague && leagueAdvanceLocked && phase === 'season_summary' && effectiveCrossRegionSlots > 0 ? (
                <div className="teamhome-preseason-panelA teamhome-preseason-panelA--compact teamhome-schedplan-fallback">
                  <div className="teamhome-preseason-title">Out-of-region schedules</div>
                  <div className="teamhome-preseason-sub">
                    Your commissioner sets non-region opponents for human schools during season summary. You will
                    see the full schedule after the league advances.
                  </div>
                </div>
              ) : phase === 'schedule_planning' && !isMultiplayerLeague && !showCrossRegionPlanningUi ? (
                <div className="teamhome-preseason-panelA teamhome-preseason-panelA--compact teamhome-schedplan-fallback">
                  <div className="teamhome-preseason-title">Non-region selection</div>
                  <div className="teamhome-preseason-sub">
                    {crossRegionSyncing
                      ? 'Loading out-of-region opponents…'
                      : expectsCrossRegionPicks
                        ? 'Schedule data did not load. Return to the load screen and reopen your dynasty, or confirm the backend server is running on port 8000.'
                        : 'Your classification uses a pod-only schedule — no out-of-region games required.'}
                  </div>
                </div>
              ) : null}
            </div>
          )
        ) : phase === 'preseason' ? (
          stateMenu !== 'Dashboard' && leagueStatePanel ? (
            <div className="teamhome-roster-shell teamhome-playoffs-league-view">{leagueStatePanel}</div>
          ) : teamMenu !== PRESEASON_TEAM_HUB ? (
            renderTeamMenuPanel()
          ) : (
          <div className="teamhome-preseason-shell">
            <PreseasonHubHeader
              seasonYear={Number(saveState?.current_year)}
              stages={preseasonStages}
              stageIndex={preseasonStageIndex}
              formatStageLabel={displayOffseasonStageLabel}
            />
            <div className="teamhome-preseason-top teamhome-preseason-top--offseason-single">
              <div className="teamhome-preseason-main">
              {completedScrimmages.length > 0 && !isScrimmageStage ? (
                isHomeGameThemesStage ? (
                  <div className="teamhome-scrimmage-results-card teamhome-preseason-main-banner">
                    <div className="teamhome-preseason-title">Scrimmage results</div>
                    <div className="teamhome-scrimmage-results-list">
                      {completedScrimmages
                        .slice()
                        .sort((a, b) => String(a.name || a.stage).localeCompare(String(b.name || b.stage)))
                        .map((s, i) => (
                          <div key={`${s.name || s.stage}-${i}`} className="teamhome-scrimmage-results-item">
                            <span className="teamhome-scrimmage-results-label">{s.name || s.stage}</span>
                            <span className="teamhome-scrimmage-results-score">
                              {s.home} {s.home_score}–{s.away} {s.away_score}
                              {s.ot ? ' (OT)' : ''}
                            </span>
                          </div>
                        ))}
                    </div>
                  </div>
                ) : (
                  <div className="teamhome-scrimmage-upcoming teamhome-preseason-main-banner">
                    <span className="teamhome-scrimmage-upcoming-label">Scrimmage results:</span>{' '}
                    {completedScrimmages
                      .slice()
                      .sort((a, b) => String(a.name || a.stage).localeCompare(String(b.name || b.stage)))
                      .map((s, i) => (
                        <span key={`${s.name || s.stage}-${i}`}>
                          {i > 0 && ' · '}
                          {s.name || s.stage}: {s.home} {s.home_score}–{s.away} {s.away_score}
                          {s.ot ? ' (OT)' : ''}
                        </span>
                      ))}
                  </div>
                )
              ) : null}
              {isPlaybookSelectStage ? (
                <div className="teamhome-playbook-select">
                  <div className="teamhome-playbook-title">Select playbooks for the upcoming season</div>
                  {!canChangePreferredPlaybooks ? (
                    <p className="teamhome-playbook-lock">
                      Preferred playbooks are locked until season {nextPreferredPlaybookEligibleYear ?? '—'} (once every{' '}
                      {PREFERRED_PLAYBOOK_LOCK_SEASONS} seasons). The league never changes your schemes — only you can, here when
                      eligible. You can still confirm to advance using your current playbooks.
                    </p>
                  ) : (
                    <p className="teamhome-playbook-lock">
                      You may change offensive and defensive playbooks now (once every {PREFERRED_PLAYBOOK_LOCK_SEASONS}{' '}
                      seasons). Philosophy ({safeStr(findTeam(saveState, userTeam)?.coach?.offensive_style)} /{' '}
                      {safeStr(findTeam(saveState, userTeam)?.coach?.defensive_style)}) stays as set until you change it at
                      creation or a future update.
                    </p>
                  )}
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
                <div className="teamhome-preseason-panelA teamhome-preseason-panelA--play-selection teamhome-preseason-panelA--compact">
                  <div className="teamhome-preseason-title">Play selection</div>
                  <p className="teamhome-preseason-stage-copy">
                    Assign play percentages within each category. Only plays above 0% count toward your install grade — set
                    unused plays to 0% for a focused game plan.
                  </p>
                  <div className="teamhome-preseason-playbook-chips">
                    <span className="teamhome-preseason-playbook-chip">
                      Offense · {safeStr(findTeam(saveState, userTeam)?.offensive_playbook ?? offensivePlaybook)}
                    </span>
                    <span className="teamhome-preseason-playbook-chip">
                      Defense · {safeStr(findTeam(saveState, userTeam)?.defensive_playbook ?? defensivePlaybook)}
                    </span>
                  </div>
                  <button
                    type="button"
                    className="teamhome-playbook-confirm teamhome-preseason-main-action"
                    onClick={() => setShowPlaybookGamePlan(true)}
                  >
                    Configure game plan
                  </button>
                </div>
              ) : isPositionChangesStage ? (
                <div className="teamhome-preseason-panelA teamhome-position-changes">
                  <div className="teamhome-preseason-title">Position changes</div>
                  <p className="teamhome-preseason-stage-copy">
                    Set each player&apos;s primary position (and optional secondary for two-way). CPU teams reassign
                    automatically when you continue. Coach recommendations use the same attribute-fit rules as AI staffs.
                  </p>
                  <div className="teamhome-position-changes-toolbar">
                    <button
                      type="button"
                      className="teamhome-position-changes-apply-all"
                      onClick={() => {
                        setPositionDraft((prev) => {
                          const next = { ...prev }
                          for (const [name, rec] of Object.entries(positionCoachRecommendations)) {
                            next[name] = {
                              position: rec.position,
                              secondary: rec.secondary ?? '',
                            }
                          }
                          return next
                        })
                      }}
                    >
                      Apply all coach recommendations
                    </button>
                  </div>
                  <div className="teamhome-position-changes-summary" aria-label="Primary position counts vs recommended">
                    {ALL_POSITIONS_ORDERED.map((pos) => {
                      const current = positionDraftCounts[pos] ?? 0
                      const target = positionTargetCounts[pos] ?? 0
                      const status =
                        current === target ? 'match' : current > target ? 'over' : 'under'
                      return (
                        <span
                          key={pos}
                          className={`teamhome-position-changes-summary-chip teamhome-position-changes-summary-chip--${status}`}
                          title={`${pos}: ${current} assigned, ${target} recommended`}
                        >
                          {pos}: {current}/{target}
                        </span>
                      )
                    })}
                  </div>
                  <div className="teamhome-position-changes-table-wrap">
                    <div className="teamhome-roster-row teamhome-roster-row-attrs teamhome-position-changes-head">
                      <div className="teamhome-roster-name">Player</div>
                      <div className="teamhome-roster-cell">Ovr</div>
                      <div className="teamhome-roster-cell">Primary</div>
                      <div className="teamhome-roster-cell">Secondary</div>
                      <div className="teamhome-roster-cell teamhome-position-changes-rec-col">Coach recommends</div>
                    </div>
                    {(findTeam(saveState, userTeam)?.roster ?? []).map((p: any) => {
                      const d = positionDraft[p.name] ?? {
                        position: String(p.position || 'WR'),
                        secondary: p.secondary_position ? String(p.secondary_position) : '',
                      }
                      const rec = positionCoachRecommendations[p.name] ?? recommendPlayerPositions(p)
                      const recLabel = formatPositionRecommendation(rec)
                      const matchesDraft =
                        d.position === rec.position && (d.secondary || '') === (rec.secondary || '')
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
                          <div className="teamhome-roster-cell teamhome-position-changes-rec-col">
                            <span
                              className={
                                matchesDraft
                                  ? 'teamhome-position-changes-rec teamhome-position-changes-rec--match'
                                  : 'teamhome-position-changes-rec'
                              }
                            >
                              {recLabel}
                            </span>
                            {!matchesDraft ? (
                              <button
                                type="button"
                                className="teamhome-position-changes-rec-apply"
                                onClick={() =>
                                  setPositionDraft((prev) => ({
                                    ...prev,
                                    [p.name]: {
                                      position: rec.position,
                                      secondary: rec.secondary ?? '',
                                    },
                                  }))
                                }
                              >
                                Use
                              </button>
                            ) : null}
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
                <div className="teamhome-preseason-panelA teamhome-preseason-panelA--play-results teamhome-preseason-panelA--compact">
                  <div className="teamhome-play-results">
                  <p className="teamhome-preseason-stage-copy">
                    Your staff finished installing the game plan. Review how much the team learned before locking it in for the
                    season.
                  </p>
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
              ) : isHomeGameThemesStage ? (
                <div className="teamhome-preseason-panelA teamhome-preseason-panelA--themes">
                  <HomeGameThemesPanel
                    apiBase={apiBase}
                    headers={headers}
                    logoVersion={logoVersion}
                    saveState={saveState}
                    userTeam={userTeam}
                    confirmed={homeGameThemesConfirmed}
                    confirming={confirmingHomeThemes}
                    commissionerAdvances={isMultiplayerLeague && leagueAdvanceLocked}
                    onConfirm={async (selections) => {
                      setConfirmingHomeThemes(true)
                      try {
                        await onSimWeek({ homeGameThemes: selections })
                      } catch (e: any) {
                        onError(e?.message ?? 'Failed to confirm themes')
                      } finally {
                        setConfirmingHomeThemes(false)
                      }
                    }}
                  />
                </div>
              ) : isSetGoalsStage ? (
                <div className="teamhome-preseason-panelA teamhome-goals-panel teamhome-preseason-panelA--compact">
                  <div className="teamhome-preseason-title">Goal selection</div>
                  <p className="teamhome-preseason-stage-copy">
                    Set win and postseason targets for the year. Goals drive program points and coach pressure at season end.
                  </p>
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
                  {goalStage === 'Just to have fun' ? (
                    <p className="teamhome-small teamhome-goals-hint">
                      No postseason target — only your win total is graded for goals, PP, and coach pressure.
                    </p>
                  ) : null}
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
                  commissionerSimulates={isMultiplayerLeague}
                  onSimulate={
                    isMultiplayerLeague
                      ? undefined
                      : async () => {
                          await onSimWeek({ forcePreseasonAdvance: true })
                        }
                  }
                  onPlay={
                    isMultiplayerLeague
                      ? undefined
                      : async () => {
                    if (!saveId) return
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
                  }
                  }
                />
              ) : (
                <div className="teamhome-preseason-panelA teamhome-preseason-panelA--placeholder">
                  <div className="teamhome-preseason-title">{displayOffseasonStageLabel(preseasonCurrentStage || 'Preseason')}</div>
                  <div className="teamhome-preseason-sub">Stage {preseasonStageNumber} of {preseasonStages.length || '—'}</div>
                  <div className="teamhome-preseason-stage">Use Continue when this stage is complete.</div>
                </div>
              )}

              </div>
            </div>

            <div className="teamhome-preseason-bottom">
              <div className="teamhome-preseason-panelD teamhome-preseason-panelD--news">
                <div className="teamhome-preseason-title">News wire</div>
                <NewsFeedPanel limit={24} compact />
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
                  <div className="teamhome-card-title">
                    Playoffs
                    {playoffView.isRegional
                      ? ` (regional · ${playoffView.seeds.length} teams)`
                      : ` (${playoffView.seeds.length || 8} teams)`}
                  </div>
                  <div className="teamhome-small" style={{ marginBottom: 10 }}>
                    {playoffView.completed
                      ? `Champion: ${playoffView.champion || '—'}`
                      : playoffView.isRegional
                        ? 'Use Continue to advance each round. Pick a region for local brackets, or Final Four for state semifinals and the championship.'
                        : 'Use Continue (top right) to run one round at a time — quarterfinals, then semifinals, then the championship.'}
                  </div>
                  <div className="teamhome-actions-grid">
                    <button
                      type="button"
                      className="teamhome-action-btn"
                      disabled={!canStartCoachPlay || playingWeek || !canCoachPlayoffGame}
                      onClick={async () => {
                        if (!canStartCoachPlay) return
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
                        leagueAdvanceLocked ||
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
                      disabled={leagueAdvanceLocked || !saveId || !saveState?.playoffs?.completed}
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
                  {playoffRegionOptions.length > 0 ? (
                    <label className="teamhome-playoffs-class-label" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span className="teamhome-small" style={{ marginBottom: 0 }}>
                        View
                      </span>
                      <select
                        className="teamhome-select"
                        value={selectPlayoffRegionValue}
                        onChange={(e) => {
                          const v = e.target.value
                          setPlayoffBracketRegion(v)
                          try {
                            sessionStorage.setItem(`fnd.playoff.viewRegion.${saveId}`, v)
                          } catch {
                            /* ignore */
                          }
                        }}
                        aria-label="Playoff bracket view"
                      >
                        {playoffRegionOptions.map((r) => (
                          <option key={r} value={r}>
                            Region {r}
                          </option>
                        ))}
                        <option value={PLAYOFF_FINAL_FOUR_VIEW}>Final Four</option>
                      </select>
                    </label>
                  ) : null}
                </div>
                {playoffView.missingBracket ? (
                  <div className="teamhome-card teamhome-card-dark" style={{ marginBottom: 0 }}>
                    <div className="teamhome-small">
                      No playoff bracket for this class. A bracket is created only when enough teams are in that classification for the active playoff format.
                    </div>
                  </div>
                ) : playoffView.isRegional && playoffView.viewFinalFour ? (
                  <div
                    className="teamhome-playoffs-grid teamhome-playoffs-grid--final-four"
                    key={`playoff-bracket-${bracketClassForView}-final-four`}
                  >
                    <div className="teamhome-card">
                      <div className="teamhome-card-title">Semifinals</div>
                      <div className="teamhome-playoffs-list">
                        {playoffView.sfRows.map((g: any, i: number) =>
                          renderPlayoffMatchupRow(
                            String(g.home),
                            String(g.away),
                            g.home_score,
                            g.away_score,
                            'Semifinal',
                            g.home_score != null,
                            `state-sf-${i}-${g.home}-${g.away}`,
                          ),
                        )}
                      </div>
                    </div>
                    <div className="teamhome-card">
                      <div className="teamhome-card-title">Championship</div>
                      <div className="teamhome-playoffs-list">
                        {playoffView.chRow
                          ? renderPlayoffMatchupRow(
                              String(playoffView.chRow.home),
                              String(playoffView.chRow.away),
                              playoffView.chRow.home_score,
                              playoffView.chRow.away_score,
                              'Championship',
                              playoffView.chRow.home_score != null,
                              `state-ch-${playoffView.chRow.home}-${playoffView.chRow.away}`,
                            )
                          : (
                            <div className="teamhome-small teamhome-playoffs-empty">TBD</div>
                          )}
                      </div>
                    </div>
                  </div>
                ) : playoffView.isRegional ? (
                  <div
                    className="teamhome-playoffs-grid teamhome-playoffs-grid--regional"
                    key={`playoff-bracket-${bracketClassForView}-${playoffView.selectedRegion}`}
                  >
                    {playoffView.inRegionColumns.map((col) => renderPlayoffRoundColumn(col))}
                  </div>
                ) : (
                  <div
                    className="teamhome-playoffs-grid"
                    key={`playoff-bracket-${bracketClassForView}`}
                    style={playoffGridStyle(playoffView.inRegionColumns.length)}
                  >
                    {playoffView.inRegionColumns.map((col) => renderPlayoffRoundColumn(col))}
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
                                    <th>OVR</th>
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
                                      <td>{computePlayerOverall(p)}</td>
                                      <td>{p?.position ?? '—'}</td>
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
                      Spend Coach Points (CP) on skill allocations and coaching cards. Levels update automatically when
                      allocated CP crosses each threshold.
                    </div>
                    {coachDevBreakdown ? (
                      <div className="teamhome-improvements-ledger" style={{ marginTop: 12, maxWidth: 640, textAlign: 'left' }}>
                        <div className="teamhome-improvements-ledger-head">
                          <span className="teamhome-improvements-ledger-title">Season CP earned</span>
                          {coachDevBreakdown.wins != null && coachDevBreakdown.losses != null ? (
                            <span className="teamhome-improvements-ledger-record">
                              {coachDevBreakdown.wins}-{coachDevBreakdown.losses}
                            </span>
                          ) : null}
                        </div>
                        <ul className="teamhome-improvements-ledger-rows">
                          <li>
                            <span>Base (coached a season)</span>
                            <span>{formatCoachCpDelta(Number(coachDevBreakdown.base_cp ?? 10))}</span>
                          </li>
                          <li>
                            <span>Record (wins − losses)</span>
                            <span>{formatCoachCpDelta(Number(coachDevBreakdown.record_cp ?? coachDevBreakdown.wins_cp ?? 0))}</span>
                          </li>
                          <li>
                            <span>Postseason</span>
                            <span>{formatCoachCpDelta(Number(coachDevBreakdown.playoffs_bonus ?? 0))}</span>
                          </li>
                          <li>
                            <span>Season goals</span>
                            <span>{formatCoachCpDelta(Number(coachDevBreakdown.goal_cp ?? 0))}</span>
                          </li>
                          <li>
                            <span>Loyalty (years at school)</span>
                            <span>{formatCoachCpDelta(Number(coachDevBreakdown.loyalty_bonus ?? 0))}</span>
                          </li>
                          {(Number(coachDevBreakdown.losing_season_penalty ?? 0) !== 0 ||
                            Number(coachDevBreakdown.age_modifier ?? 0) !== 0) && (
                            <>
                              {Number(coachDevBreakdown.losing_season_penalty ?? 0) !== 0 ? (
                                <li>
                                  <span>Losing season</span>
                                  <span>{formatCoachCpDelta(Number(coachDevBreakdown.losing_season_penalty ?? 0))}</span>
                                </li>
                              ) : null}
                              {Number(coachDevBreakdown.age_modifier ?? 0) !== 0 ? (
                                <li>
                                  <span>Age modifier</span>
                                  <span>{formatCoachCpDelta(Number(coachDevBreakdown.age_modifier ?? 0))}</span>
                                </li>
                              ) : null}
                            </>
                          )}
                          <li>
                            <span>
                              <b>Net this season</b>
                            </span>
                            <span>
                              <b>{formatCoachCpDelta(Number(coachDevBreakdown.cp_change ?? 0))}</b>
                            </span>
                          </li>
                        </ul>
                      </div>
                    ) : null}
                    <div style={{ marginTop: 12, textAlign: 'left', maxWidth: 860 }}>
                      <div className="teamhome-small">
                        Total CP: <b>{coachDevTotalCp.toFixed(1)}</b>
                        {coachDevCardNetCost > 0 ? (
                          <>
                            {' '}
                            → after cards: <b>{coachDevProjectedTotalCp.toFixed(1)}</b>
                          </>
                        ) : null}
                      </div>
                      <div className="teamhome-small">
                        Allocated CP: <b>{coachDevAllocatedCp.toFixed(1)}</b>
                      </div>
                      <div className="teamhome-small" style={{ color: coachDevAvailableCp < 0 ? '#7f1d1d' : undefined }}>
                        Available CP: <b>{coachDevAvailableCp.toFixed(1)}</b>
                      </div>
                      {coachDevCardNetCost > 0 ? (
                        <div className="teamhome-small" style={{ marginTop: 4 }}>
                          Card changes this stage: <b>−{coachDevCardNetCost.toFixed(1)} CP</b>
                        </div>
                      ) : null}
                    </div>
                    <div style={{ marginTop: 12, textAlign: 'left', width: '100%', maxWidth: 940 }}>
                      <table className="teamhome-roster-table" style={{ width: '100%' }}>
                        <thead>
                          <tr>
                            <th style={{ textAlign: 'left' }}>Attribute</th>
                            <th>Level</th>
                            <th>Allocated CP</th>
                            <th>Progress</th>
                            <th style={{ textAlign: 'center' }}>Adjust</th>
                          </tr>
                        </thead>
                        <tbody>
                          {COACH_DEV_SKILLS.map(({ key, label }) => {
                            const cp = Number(coachDevAllocations[key] ?? 0)
                            const lv = coachDevLevelFromCp(cp)
                            const nextTh = coachDevNextThreshold(lv)
                            const progress = coachDevCpToNextLevel(cp)
                            const progressPct =
                              progress && progress.next > progress.current
                                ? Math.min(
                                    100,
                                    Math.round(
                                      ((cp - progress.current) / (progress.next - progress.current)) * 100,
                                    ),
                                  )
                                : 100
                            return (
                              <tr key={key}>
                                <td>{label}</td>
                                <td>{lv}</td>
                                <td>{cp.toFixed(1)}</td>
                                <td style={{ minWidth: 120 }}>
                                  {nextTh == null ? (
                                    'Maxed'
                                  ) : (
                                    <div>
                                      <div style={{ fontSize: '0.8rem', opacity: 0.85 }}>
                                        {progress?.remaining ?? 0} CP to Lv {lv + 1}
                                      </div>
                                      <div
                                        style={{
                                          height: 6,
                                          borderRadius: 4,
                                          background: 'rgba(148,163,184,0.25)',
                                          marginTop: 4,
                                          overflow: 'hidden',
                                        }}
                                      >
                                        <div
                                          style={{
                                            width: `${progressPct}%`,
                                            height: '100%',
                                            background: '#38bdf8',
                                          }}
                                        />
                                      </div>
                                    </div>
                                  )}
                                </td>
                                <td style={{ textAlign: 'center', whiteSpace: 'nowrap' }}>
                                  <button
                                    type="button"
                                    className="teamhome-select"
                                    style={{ marginRight: 6 }}
                                    onClick={() =>
                                      setCoachDevAllocations((prev) => ({
                                        ...prev,
                                        [key]: Math.max(0, Math.round((Number(prev[key] ?? 0) - 10) * 10) / 10),
                                      }))
                                    }
                                  >
                                    −10
                                  </button>
                                  <button
                                    type="button"
                                    className="teamhome-select"
                                    style={{ marginRight: 6 }}
                                    onClick={() =>
                                      setCoachDevAllocations((prev) => ({
                                        ...prev,
                                        [key]: Math.round((Number(prev[key] ?? 0) + 10) * 10) / 10,
                                      }))
                                    }
                                  >
                                    +10
                                  </button>
                                  {nextTh != null ? (
                                    <button
                                      type="button"
                                      className="teamhome-select"
                                      onClick={() =>
                                        setCoachDevAllocations((prev) => ({
                                          ...prev,
                                          [key]: nextTh,
                                        }))
                                      }
                                    >
                                      Next Lv
                                    </button>
                                  ) : null}
                                </td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                    </div>
                    <div style={{ marginTop: 24, width: '100%', maxWidth: 980 }}>
                      <div className="teamhome-preseason-title" style={{ fontSize: '1.05rem' }}>
                        Coaching cards
                      </div>
                      <div className="teamhome-preseason-sub" style={{ marginTop: 6, maxWidth: 760 }}>
                        Specialize your program identity and position development. Card changes deduct CP now; unequipping
                        refunds 50%. Swapping program identity adds a fee.
                      </div>
                      <CoachingCardPicker
                        loadout={coachingCardsLoadout}
                        onChange={handleCoachingCardsLoadoutChange}
                        showCosts
                        availableCp={coachDevAvailableCp}
                        savedLoadout={coachDevSavedLoadout}
                        cardLedger={coachDevCardLedger}
                      />
                    </div>
                  </>
                ) : offseasonCurrentStage === 'Program Development' ? (
                  <>
                    <div className="teamhome-preseason-title">Program development</div>
                    <div className="teamhome-preseason-sub" style={{ marginTop: 8, maxWidth: 860 }}>
                      Invest annual funding in equipment and facilities. Purchases apply when you press Continue
                      {isMultiplayerLeague ? ' or Submit week' : ''}; CPU schools shop automatically afterward.
                    </div>
                    <div style={{ marginTop: 14, width: '100%', maxWidth: 980 }}>
                      <ProgramDevelopmentPanel
                        saveState={saveState}
                        userTeam={userTeam}
                        pendingActions={programDevPendingActions}
                        onPendingActionsChange={setProgramDevPendingActions}
                      />
                    </div>
                  </>
                ) : offseasonCurrentStage === 'Improvements' ? (
                  <>
                    <div className="teamhome-preseason-title">Program improvements</div>
                    <div className="teamhome-preseason-sub teamhome-improvements-lead">
                      Drop <b>invest chips</b> on facilities, culture, or booster support to spend program points (PP) from your
                      booster bank. Withdraw chips pull PP back out. Partial progress between grades is supported — level-ups fire when
                      you cross the same PP thresholds as in-season. Use <b>Continue</b> to lock in and advance.
                    </div>

                    <div className="teamhome-improvements-wrap">
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
                              How your PP bank was credited — season results, goals, and active program equipment that grants PP.
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
                              {improvementsSeasonLedger.equipmentPp > 0 ? (
                                <li>
                                  <span>Program equipment (owned facilities)</span>
                                  <span className="teamhome-improvements-num--good">
                                    {formatProgramPpDelta(improvementsSeasonLedger.equipmentPp)}
                                  </span>
                                </li>
                              ) : null}
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

                      <ProgramInvestmentBoosterCards
                        pillars={improvementsBudget.pillars}
                        bankAmount={improvementsBudget.projectedRemaining}
                        netCredited={improvementsSeasonLedger?.net ?? null}
                        onTargetChange={handleImprovementTargetChange}
                        resetToken={improvementsResetKey}
                      />

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
                            {(saveState.offseason_improvements_bank.breakdown as any).equipment_pp_total > 0 ? (
                              <div style={{ marginTop: 4 }}>
                                Program equipment PP:{' '}
                                <b>
                                  {Number(
                                    (saveState.offseason_improvements_bank.breakdown as any).equipment_pp_total ?? 0,
                                  )}
                                </b>
                              </div>
                            ) : null}
                          </div>
                        </details>
                      ) : null}

                      {improvementsBudget.stuckAtFloorDebt ? (
                        <div className="teamhome-improvements-alert teamhome-improvements-alert--warn" role="status">
                          <b>Program at minimum.</b> Facilities, culture, and boosters are already grade 1, so you cannot
                          refund more PP to balance a negative bank from this season. Use <b>Continue</b> to lock in and
                          advance — your bank will reset to 0 PP for this step.
                        </div>
                      ) : improvementsBudget.invalid ? (
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
                        ) : improvementsBudget.atProgramFloor && improvementsBudget.projectedRemaining > 0 ? (
                          <>At grade 1 on all pillars you cannot spend more PP here — use Continue with leftover bank.</>
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
                        <b>State → Coaching changes</b> for that season year.
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
                      {userSchemeNotice?.detail ? (
                        <div
                          className="teamhome-playbook-lock"
                          style={{
                            marginBottom: 14,
                            padding: '12px 14px',
                            borderRadius: 8,
                            border: '1px solid rgba(125, 211, 252, 0.35)',
                            background: 'rgba(30, 58, 95, 0.35)',
                            maxWidth: 640,
                          }}
                        >
                          <div className="teamhome-small" style={{ fontWeight: 700, marginBottom: 6 }}>
                            {userSchemeNotice.headline ?? 'Your preferred schemes'}
                          </div>
                          <div className="teamhome-small" style={{ opacity: 0.92, lineHeight: 1.45 }}>
                            {userSchemeNotice.detail}
                          </div>
                          {!userSchemeNotice.playbooks_may_change &&
                          userSchemeNotice.next_playbook_eligible_year != null ? (
                            <div className="teamhome-small" style={{ marginTop: 8, opacity: 0.85 }}>
                              Preseason <b>Playbook Select</b> unlocks playbook changes in season{' '}
                              {userSchemeNotice.next_playbook_eligible_year} (every{' '}
                              {userSchemeNotice.playbook_interval_seasons ?? PREFERRED_PLAYBOOK_LOCK_SEASONS} seasons).
                            </div>
                          ) : userSchemeNotice.playbooks_may_change ? (
                            <div className="teamhome-small" style={{ marginTop: 8, opacity: 0.85 }}>
                              You can update playbooks at preseason <b>Playbook Select</b> this year. The league does not
                              change your schemes for you.
                            </div>
                          ) : null}
                        </div>
                      ) : null}
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
                                Summary will appear once you finish stage III — if this is stuck empty, Continue once more from{' '}
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
                                      .join(' · ')
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
                                    · Your application list persists until the carousel completes
                                  </span>
                                </div>
                                <div className="teamhome-small" style={{ marginBottom: 10 }}>
                                  Top-ranked schools are prioritized when your coach evaluates offers; you can reorder between
                                  stages I–III as new vacancies appear.
                                </div>
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'flex-end', marginBottom: 10 }}>
                                  <select
                                    className="teamhome-select teamhome-select-inline"
                                    aria-label="Add school to application list"
                                    value={carouselVacancyPick}
                                    onChange={(e) => setCarouselVacancyPick(e.target.value)}
                                    style={{ minWidth: 220 }}
                                  >
                                    <option value="">Add vacancy…</option>
                                    {availAdd.map((n) => (
                                      <option key={n} value={n}>
                                        {prestigeOf(n)}★ {n}
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
                            return v !== undefined ? `${v} / 100` : '—'
                          })()}
                        </b>
                        <span style={{ opacity: 0.85 }}> · Higher = more pressure (losing seasons, missed goals, playoff drought).</span>
                      </div>
                      {(() => {
                        const hsMap = (saveState?.offseason_coach_carousel_hot_seat ?? {}) as Record<string, number>
                        const teams = (saveState?.teams ?? []) as any[]
                        const rows = teams
                          .filter((t) => t?.name && t?.coach)
                          .map((t) => {
                            const teamName = String(t.name)
                            const coachName = String(t.coach?.name ?? '—')
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
                              League hot seat — all head coaches
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
                              <option value="">— Show full list (no highlight) —</option>
                              {rows.map((r) => (
                                <option key={r.teamName} value={r.teamName}>
                                  {r.hotSeat}/100 · {r.teamName} — {r.coachName}
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
                          <li className="teamhome-small">No moves logged at this carousel step yet — press Continue.</li>
                        ) : (
                          (saveState?.offseason_coach_carousel_last_events ?? []).map((ev: any, i: number) => {
                            const yours =
                              ev?.affects_user_program === true ||
                              (ev?.is_user_coach === true && ev?.is_user_team === true) ||
                              ev?.type === 'user_scheme_reminder'
                            const typeLabel =
                              ev?.type === 'user_scheme_reminder' ? 'your schemes' : (ev.type ?? '—')
                            return (
                              <li key={`cc-ev-${i}`} className="teamhome-carousel-event-item" style={{ marginBottom: 6 }}>
                                <span style={{ opacity: 0.8 }}>[{typeLabel}]</span>{' '}
                                {yours ? <strong style={{ marginRight: 6 }}>Your program:</strong> : null}
                                {ev.detail ?? ''}
                              </li>
                            )
                          })
                        )}
                      </ul>
                      <div className="teamhome-small" style={{ marginTop: 12 }}>
                        Review past offseasons under <b>State → Coaching changes</b>.
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
                        <p className="teamhome-small" style={{ marginTop: 4, opacity: 0.85 }}>
                          Click a name to see that player&apos;s offseason growth so far.
                        </p>
                        <ul style={{ marginTop: 8 }}>
                          {((winterTrainingResult.notable_players ?? []) as any[]).slice(0, 5).map((n, i) => (
                            <li key={`${n.player_name}-${n.attribute}-${i}`}>
                              <OffseasonReportPlayerName
                                saveState={saveState}
                                userTeam={userTeam}
                                playerName={String(n.player_name ?? 'Player')}
                                onOpen={setOffseasonReportPlayer}
                              />{' '}
                              ({String(n.position ?? '')}) +{Number(n.delta ?? 0)} {String(n.attribute ?? '')}
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
                                <td>{String(r?.label ?? '—')}</td>
                                <td>{Number(r?.delta ?? 0) >= 0 ? `+${Number(r?.delta ?? 0).toFixed(1)}` : Number(r?.delta ?? 0).toFixed(1)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>

                        <div className="teamhome-preseason-title" style={{ fontSize: 15, marginTop: 12 }}>Notable player improvements</div>
                        <p className="teamhome-small" style={{ marginTop: 4, opacity: 0.85 }}>
                          Click a name to see that player&apos;s offseason growth so far.
                        </p>
                        <ul className="teamhome-list" style={{ marginTop: 6 }}>
                          {((springBallResult.notable_players ?? []) as any[]).slice(0, 5).map((n, i) => (
                            <li key={`notable-${i}`} className="teamhome-small">
                              {String(n?.position ?? '—')}{' '}
                              <OffseasonReportPlayerName
                                saveState={saveState}
                                userTeam={userTeam}
                                playerName={String(n?.player_name ?? 'Player')}
                                onOpen={setOffseasonReportPlayer}
                              />
                              : +{Number(n?.delta ?? 0)} {String(n?.attribute ?? '')}
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
                    <div className="teamhome-preseason-title">Transfers I — Portal entrants</div>
                    {transfersDisabled ? (
                      <>
                        <div className="teamhome-preseason-sub">
                          Transfers are disabled for this dynasty. No players will enter the portal and no moves will
                          occur.
                        </div>
                        <div className="teamhome-small" style={{ marginTop: 8 }}>
                          {transferStage1?.disabled || transferStage1?.entries != null
                            ? 'No portal entrants this offseason. Press Continue to advance.'
                            : 'Press Continue once to acknowledge and advance.'}
                        </div>
                      </>
                    ) : (
                      <>
                    <div className="teamhome-preseason-sub">
                      First <b>Continue</b> builds the portal class from the season that just ended (using final
                      standings). Review the list, then <b>Continue</b> again to lock entrants before destinations run
                      in Transfers II.
                    </div>
                    {transferStage1?.entries?.length ? (
                      <div style={{ marginTop: 12 }}>
                        <div className="teamhome-small" style={{ marginBottom: 8 }}>
                          League portal cap: <b>{Number(transferStage1.pool_pct ?? 0).toFixed(1)}%</b> · In portal:{' '}
                          <b>{Number(transferStage1.selected_count ?? 0)}</b>
                          {transferStage1.eligible_count != null ? (
                            <>
                              {' '}
                              · Candidates considered: <b>{Number(transferStage1.eligible_count)}</b>
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
                            const fromSchool = String(r.from_team ?? r.team ?? '—')
                            return (
                              <div
                                key={`tr1-${fromSchool}-${String(r.player)}-${i}`}
                                className="teamhome-roster-row teamhome-transfer-portal-row"
                              >
                                <div className="teamhome-roster-cell">{String(r.player ?? '—')}</div>
                                <div className="teamhome-roster-cell">{String(r.position ?? '—')}</div>
                                <div className="teamhome-roster-cell">{formatTransferPortalClassYear(r.year)}</div>
                                <div className="teamhome-roster-cell">{teamWithLogo(fromSchool, 22)}</div>
                                <div className="teamhome-roster-cell">{String(r.region ?? '—')}</div>
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
                    )}
                  </>
                ) : offseasonCurrentStage === 'Transfers II' ? (
                  <>
                    <div className="teamhome-preseason-title">Transfers II — Destinations</div>
                    {transfersDisabled ? (
                      <>
                        <div className="teamhome-preseason-sub">
                          Transfers are disabled for this dynasty. Destination resolution is skipped.
                        </div>
                        <div className="teamhome-small" style={{ marginTop: 8 }}>
                          {transferStage2?.disabled || transferStage2?.entries != null
                            ? 'No transfers occurred. Press Continue to advance.'
                            : 'Press Continue once to acknowledge and advance.'}
                        </div>
                      </>
                    ) : (
                      <>
                    <div className="teamhome-preseason-sub">
                      First <b>Continue</b> resolves destinations from the locked portal class. Review, then{' '}
                      <b>Continue</b> again to advance.
                    </div>
                    {transferStage2?.entries?.length ? (
                      <div style={{ marginTop: 10 }}>
                        <div className="teamhome-small">
                          Finalized moves: <b>{Number(transferStage2.moved_count ?? 0)}</b> · Blocked:{' '}
                          <b>{Number(transferStage2.blocked_count ?? 0)}</b>
                        </div>
                        <ul className="teamhome-list" style={{ marginTop: 8 }}>
                          {(transferStage2.entries as any[]).slice(0, 12).map((r: any, i: number) => (
                            <li key={`tr2-${i}`} className="teamhome-small">
                              {String(r.player)} ({String(r.position)}) · {String(r.from_team)} → {String(r.to_team)}
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
                    )}
                  </>
                ) : offseasonCurrentStage === 'Transfers III' ? (
                  <>
                    <div className="teamhome-preseason-title">Transfers III — Review</div>
                    {transfersDisabled ? (
                      <>
                        <div className="teamhome-preseason-sub">
                          Transfers are disabled for this dynasty. There is no transfer ledger for this offseason.
                        </div>
                        <div className="teamhome-small" style={{ marginTop: 8 }}>
                          No transfers occurred. Press Continue to advance.
                        </div>
                      </>
                    ) : (
                      <>
                    <div className="teamhome-preseason-sub">
                      Final offseason transfer ledger. Review every completed move before advancing.
                    </div>
                    {transferReview?.entries?.length ? (
                      <div style={{ marginTop: 10 }}>
                        <div className="teamhome-small">
                          Completed transfers: <b>{Number(transferReview.moved_count ?? transferReview.entries.length ?? 0)}</b> · Blocked:{' '}
                          <b>{Number(transferReview.blocked_count ?? 0)}</b>
                        </div>
                        <ul className="teamhome-list" style={{ marginTop: 8 }}>
                          {(transferReview.entries as any[]).map((r: any, i: number) => (
                            <li key={`tr3-${i}`} className="teamhome-small">
                              {String(r.player)} ({String(r.position)}) · {String(r.from_team)} → {String(r.to_team)}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : (
                      <div className="teamhome-small" style={{ marginTop: 8 }}>No transfers finalized this offseason.</div>
                    )}
                      </>
                    )}
                  </>
                ) : offseasonCurrentStage === '7 on 7' ? (
                  <>
                    <div className="teamhome-preseason-title">7-on-7 passing tournament</div>
                    {!sevenOnSevenResult ? (
                      <>
                        <div className="teamhome-preseason-sub" style={{ maxWidth: 720 }}>
                          Pick one tournament, then press Continue to sim the full event — four group games
                          (round-robin plus crossover), then a single-elimination bracket. Passing only; no coach
                          play.
                        </div>
                        <div className="teamhome-7on7-tournament-grid">
                          {SEVEN_ON_SEVEN_TOURNAMENTS.map((t) => (
                            <button
                              key={t.id}
                              type="button"
                              className={`teamhome-7on7-tournament-card${sevenOnSevenTier === t.id ? ' teamhome-7on7-tournament-card--active' : ''}`}
                              onClick={() => setSevenOnSevenTier(t.id)}
                            >
                              <div className="teamhome-7on7-tournament-label">{t.label}</div>
                              <div className="teamhome-7on7-tournament-diff">{t.difficulty}</div>
                              <div className="teamhome-7on7-tournament-desc">{t.description}</div>
                            </button>
                          ))}
                        </div>
                        <div className="teamhome-small" style={{ marginTop: 14, opacity: 0.9 }}>
                          Selected: <b>{SEVEN_ON_SEVEN_TOURNAMENTS.find((t) => t.id === sevenOnSevenTier)?.label ?? '—'}</b>
                          {' · '}8 teams · 4 group games · single elimination
                        </div>
                      </>
                    ) : (
                      <div className="teamhome-7on7-results" style={{ marginTop: 10, textAlign: 'left', width: '100%' }}>
                        <div className="teamhome-small" style={{ marginBottom: 10 }}>
                          <b>{String(sevenOnSevenResult.tier_label ?? 'Tournament')}</b>
                          {' · '}
                          Finish: <b>{String(sevenOnSevenResult.user_finish ?? '—')}</b>
                          {' · '}
                          Group record: <b>{String(sevenOnSevenResult.user_record ?? '—')}</b>
                          {' · '}
                          Champion: <b>{String(sevenOnSevenResult.champion ?? '—')}</b>
                        </div>

                        <div className="teamhome-preseason-title" style={{ fontSize: 15 }}>Group stage</div>
                        <div className="teamhome-7on7-group-labels teamhome-small" style={{ marginTop: 6, opacity: 0.85 }}>
                          Group A: {(sevenOnSevenResult.group_a as string[] | undefined)?.join(', ') ?? '—'}
                          <br />
                          Group B: {(sevenOnSevenResult.group_b as string[] | undefined)?.join(', ') ?? '—'}
                        </div>
                        <table className="teamhome-roster-table teamhome-7on7-table" style={{ width: '100%', marginTop: 10 }}>
                          <thead>
                            <tr>
                              <th style={{ textAlign: 'left' }}>Game</th>
                              <th>Score</th>
                              <th>Passing</th>
                            </tr>
                          </thead>
                          <tbody>
                            {((sevenOnSevenResult.group_games as any[]) ?? []).map((g, i) => {
                              const userGame = Boolean(g.user_involved)
                              const hs = g.home_stats ?? {}
                              const as = g.away_stats ?? {}
                              return (
                                <tr key={`7g-${i}`} className={userGame ? 'teamhome-7on7-row-user' : undefined}>
                                  <td>
                                    {String(g.home)} vs {String(g.away)}
                                    {userGame ? ' ★' : ''}
                                  </td>
                                  <td>
                                    {g.home_score}–{g.away_score}
                                  </td>
                                  <td className="teamhome-small">
                                    {String(g.home)} {hs.comp ?? 0}/{hs.att ?? 0}, {hs.pass_yds ?? 0} yds
                                    {' · '}
                                    {String(g.away)} {as.comp ?? 0}/{as.att ?? 0}, {as.pass_yds ?? 0} yds
                                  </td>
                                </tr>
                              )
                            })}
                          </tbody>
                        </table>

                        <div className="teamhome-preseason-title" style={{ fontSize: 15, marginTop: 14 }}>Standings</div>
                        <table className="teamhome-roster-table teamhome-7on7-table" style={{ width: '100%', marginTop: 8 }}>
                          <thead>
                            <tr>
                              <th>#</th>
                              <th style={{ textAlign: 'left' }}>Team</th>
                              <th>W-L</th>
                              <th>PF</th>
                              <th>PA</th>
                              <th>+/−</th>
                            </tr>
                          </thead>
                          <tbody>
                            {((sevenOnSevenResult.standings as any[]) ?? []).map((row) => (
                              <tr
                                key={`7s-${row.team}`}
                                className={row.team === userTeam ? 'teamhome-7on7-row-user' : undefined}
                              >
                                <td>{row.seed}</td>
                                <td>{String(row.team)}</td>
                                <td>
                                  {row.w}-{row.l}
                                </td>
                                <td>{row.pf}</td>
                                <td>{row.pa}</td>
                                <td>{row.diff >= 0 ? `+${row.diff}` : row.diff}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>

                        <div className="teamhome-preseason-title" style={{ fontSize: 15, marginTop: 14 }}>Playoffs</div>
                        <ul className="teamhome-list teamhome-small" style={{ marginTop: 8 }}>
                          {((sevenOnSevenResult.semifinals as any[]) ?? []).map((g, i) => (
                            <li key={`7sf-${i}`}>
                              Semifinal: {String(g.home)} {g.home_score}–{g.away_score} {String(g.away)}
                            </li>
                          ))}
                          {sevenOnSevenResult.final ? (
                            <li>
                              Final: {String(sevenOnSevenResult.final.home)} {sevenOnSevenResult.final.home_score}–
                              {sevenOnSevenResult.final.away_score} {String(sevenOnSevenResult.final.away)}
                            </li>
                          ) : null}
                        </ul>
                        <div className="teamhome-small" style={{ marginTop: 10, opacity: 0.9 }}>
                          Press <b>Continue</b> to lock results and advance.
                        </div>
                      </div>
                    )}
                  </>
                ) : offseasonCurrentStage === 'Training Results' ? (
                  <>
                    <div className="teamhome-preseason-title">Training &amp; development</div>
                    <div className="teamhome-preseason-sub">
                      Continue runs the main offseason development pass for every program. Active program equipment adds
                      flat training bonuses (position-filtered where noted). PP-granting gear credits your Improvements
                      bank later this offseason. Click a player name for the full offseason growth report (winter,
                      spring, and training).
                    </div>
                    {offseasonTrainingRowsRaw.length === 0 && isMultiplayerLeague ? (
                      <p className="teamhome-preseason-sub" style={{ marginTop: 12, opacity: 0.92 }}>
                        In multiplayer, the commissioner simulates this step. After advance, your growth table appears
                        here (and on Freshman Class) when you open your dashboard.
                      </p>
                    ) : null}
                    {trainingEquipmentPreview.length > 0 ? (
                      <div className="teamhome-improvements-ledger" style={{ marginTop: 14, textAlign: 'left' }}>
                        <div className="teamhome-improvements-ledger-head">
                          <span className="teamhome-improvements-ledger-title">Active program equipment</span>
                        </div>
                        <ul className="teamhome-improvements-ledger-rows" style={{ marginTop: 8 }}>
                          {trainingEquipmentPreview.map((row) => (
                            <li key={row.name}>
                              <span>{row.name}</span>
                              <span className="teamhome-small" style={{ opacity: 0.85 }}>
                                {row.hasTraining ? row.attrs.filter((a) => !/^\d+\s*PP/i.test(a)).join(' · ') || 'Training bonus' : null}
                                {row.pp > 0 ? `${row.hasTraining ? ' · ' : ''}+${row.pp} PP at Improvements` : ''}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                    {trainingEquipmentApplied?.ui_rows?.length ? (
                      <div className="teamhome-improvements-ledger" style={{ marginTop: 14, textAlign: 'left' }}>
                        <div className="teamhome-improvements-ledger-head">
                          <span className="teamhome-improvements-ledger-title">Equipment applied this training cycle</span>
                        </div>
                        <ul className="teamhome-improvements-ledger-rows" style={{ marginTop: 8 }}>
                          {trainingEquipmentApplied.ui_rows.map((row) => (
                            <li key={row.name}>
                              <span>{row.name}</span>
                              <span className="teamhome-small">{(row.labels || []).join(' · ')}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                    {offseasonTrainingRowsRaw.length === 0 && trainingBreakthroughEligibleNames.size > 0 ? (
                      <div style={{ marginTop: 14, textAlign: 'left' }}>
                        <div className="teamhome-small" style={{ marginBottom: 8, opacity: 0.9 }}>
                          <BreakthroughStar eligible />{' '}
                          Platinum breakthrough eligible — within 12 OVR of potential cap with a matching platinum
                          card equipped.
                        </div>
                        <ul className="teamhome-improvements-ledger-rows" style={{ marginTop: 0 }}>
                          {[...trainingBreakthroughEligibleNames]
                            .sort((a, b) => a.localeCompare(b))
                            .map((name) => (
                              <li key={name}>
                                <OffseasonReportPlayerName
                                  saveState={saveState}
                                  userTeam={userTeam}
                                  playerName={name}
                                  onOpen={setOffseasonReportPlayer}
                                />{' '}
                                <BreakthroughStar eligible />
                              </li>
                            ))}
                        </ul>
                      </div>
                    ) : null}
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
                              <option value="name">Name (A–Z)</option>
                            </select>
                          </div>
                          <span className="teamhome-small">{sortedOffseasonTrainingRows.length} players</span>
                        </div>
                        {trainingBreakthroughEligibleNames.size > 0 ? (
                          <div className="teamhome-small" style={{ marginTop: 8, opacity: 0.9 }}>
                            <BreakthroughStar eligible /> Potential platinum breakthrough
                          </div>
                        ) : null}
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
                                    <OffseasonReportPlayerName
                                      saveState={saveState}
                                      userTeam={userTeam}
                                      playerName={row.name}
                                      onOpen={setOffseasonReportPlayer}
                                    />{' '}
                                    <BreakthroughStar
                                      eligible={
                                        row.platinum_breakthrough_eligible ??
                                        trainingBreakthroughEligibleNames.has(row.name)
                                      }
                                      achieved={row.platinum_breakthrough}
                                      gain={row.platinum_breakthrough_gain}
                                    />
                                  </td>
                                  <td>{row.position ?? '—'}</td>
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
                    {offseasonTrainingRowsRaw.length === 0 && isMultiplayerLeague ? (
                      <p className="teamhome-preseason-sub" style={{ marginTop: 12, opacity: 0.92 }}>
                        Offseason development already ran when the commissioner advanced the league. Your roster
                        ratings include that growth; detailed before/after rows appear here once Training Results
                        data is saved for your school (leagues advancing after this update).
                      </p>
                    ) : null}
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
                              <option value="name">Name (A–Z)</option>
                            </select>
                          </div>
                          <span className="teamhome-small">{sortedOffseasonTrainingRows.length} players</span>
                        </div>
                        {trainingBreakthroughEligibleNames.size > 0 ? (
                          <div className="teamhome-small" style={{ marginTop: 8, opacity: 0.9 }}>
                            <BreakthroughStar eligible /> Potential platinum breakthrough
                          </div>
                        ) : null}
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
                                    <OffseasonReportPlayerName
                                      saveState={saveState}
                                      userTeam={userTeam}
                                      playerName={row.name}
                                      onOpen={setOffseasonReportPlayer}
                                    />{' '}
                                    <BreakthroughStar
                                      eligible={
                                        row.platinum_breakthrough_eligible ??
                                        trainingBreakthroughEligibleNames.has(row.name)
                                      }
                                      achieved={row.platinum_breakthrough}
                                      gain={row.platinum_breakthrough_gain}
                                    />
                                  </td>
                                  <td>{row.position ?? '—'}</td>
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
                          <option value="name">Name (A–Z)</option>
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
                                <td>{p?.position ?? '—'}</td>
                                <td>{formatPlayerYear(p?.year)}</td>
                                <td>{computePlayerOverall(p)}</td>
                                <td>{p?.potential ?? '—'}</td>
                                <td>{p?.height != null ? `${p.height}` : '—'}</td>
                                <td>{p?.weight != null ? `${p.weight}` : '—'}</td>
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
                              Week {r.week}: {formatScheduleOpponentLabel(r.opponent, r.userHome)}
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
                          <li>—</li>
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
                <NewsFeedPanel limit={24} compact />
              </div>
              <div className="teamhome-preseason-panelC">
                <div className="teamhome-preseason-title">Season</div>
                <div className="teamhome-preseason-sub">Year {saveState?.current_year ?? '—'}</div>
              </div>
            </div>
          </div>
          )
        ) : phase === 'regular' && stateMenu !== 'Dashboard' && leagueStatePanel ? (
          <div className="teamhome-roster-shell teamhome-playoffs-league-view">{leagueStatePanel}</div>
        ) : teamMenu === 'Overview' && phase === 'regular' ? (
          leagueStatePanel ?? (
          <InSeasonDashboard
            apiBase={apiBase}
            headers={headers}
            logoVersion={logoVersion}
            stadiumVersion={stadiumVersion}
            saveState={saveState}
            userTeam={userTeam}
            currentWeek={currentWeek}
            scheduleRows={scheduleRows}
            classStandings={inSeasonClassStandings}
            teamStatsRow={inSeasonUserStatsRow}
            hasUnplayedGameThisWeek={hasUnplayedGameThisWeek}
            canContinue={canContinue}
            canStartCoachPlay={canStartCoachPlay}
            playingWeek={playingWeek}
            simmingWeek={simmingWeek}
            simMultipleCount={simMultipleCount}
            leagueAdvanceLocked={leagueAdvanceLocked}
            onSubmitWeek={onSubmitWeek}
            onUnsubmitWeek={onUnsubmitWeek}
            weekSubmitted={weekSubmitted}
            canUnsubmitWeek={canUnsubmitWeek}
            submitWeekBusy={submitWeekBusy}
            onReturnToLeagueHub={onReturnToLeagueHub}
            onPlayGame={async () => {
              if (!canStartCoachPlay) return
              setPlayingWeek(true)
              try {
                const live = getLiveSaveState?.() ?? saveState
                const r = isLocalBundle
                  ? await fetch(`${apiBase}/sim/game/start`, {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ state: live, context: 'week' }),
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
            onSimGame={
              leagueAdvanceLocked
                ? undefined
                : async () => {
              setSimmingWeek(true)
              try {
                await onSimWeek()
              } catch (e: any) {
                onError(e?.message ?? 'Sim failed')
              } finally {
                setSimmingWeek(false)
              }
            }}
            onSimMultiple={
              leagueAdvanceLocked
                ? undefined
                : async (n) => {
              setSimMultipleCount(n)
              try {
                for (let i = 0; i < n; i++) {
                  const ok = await onSimWeek()
                  if (!ok) break
                  const st = getLiveSaveState?.() ?? saveState
                  const simPhase = String(st?.season_phase ?? '').toLowerCase()
                  const cw = Number(st?.current_week ?? 1)
                  const totalWeeks = Array.isArray(st?.weeks) ? st.weeks.length : 0
                  if (simPhase !== 'regular' || (totalWeeks > 0 && cw > totalWeeks)) break
                }
              } finally {
                setSimMultipleCount(0)
              }
            }}
            onOpenOffGameplan={() => setTeamMenu('OFF Gameplan')}
            onOpenDefGameplan={() => setTeamMenu('DEF Gameplan')}
            onOpenScouting={() => setTeamMenu(SCOUTING_MENU_OFFENSE)}
            onOpenInbox={() => setTeamMenu(COACH_INBOX_MENU)}
            onOpenGamePreview={() => {
              const row = scheduleRows.find((r) => r.week === currentWeek)
              if (!row?.opponent || /^bye$/i.test(row.opponent)) return
              const home = row.userHome ? userTeam : row.opponent
              const away = row.userHome ? row.opponent : userTeam
              openPregamePreview(currentWeek, home, away)
            }}
          />
          )
        ) : renderTeamMenuPanel()}
      </div>

      {pregamePreviewData ? (
        <PregamePreviewModal
          data={pregamePreviewData}
          apiBase={apiBase}
          headers={headers}
          logoVersion={logoVersion}
          stadiumVersion={stadiumVersion}
          helmetVersion={helmetVersion}
          jerseyVersion={jerseyVersion}
          onClose={() => setPregamePreview(null)}
        />
      ) : null}

      {offseasonPlayerReport ? (
        <PlayerOffseasonReportModal
          report={offseasonPlayerReport}
          onClose={() => setOffseasonReportPlayer(null)}
        />
      ) : null}
    </div>
  )
}

export default function TeamHomePage(props: Props) {
  const [logoVersion, setLogoVersion] = useState(0)
  const [stadiumVersion, setStadiumVersion] = useState(0)
  const [helmetVersion, setHelmetVersion] = useState(0)
  const [jerseyVersion, setJerseyVersion] = useState(0)
  const [showSettings, setShowSettings] = useState(false)
  const [defaultLogoVersion, setDefaultLogoVersion] = useState<number | undefined>(undefined)
  const preferDefaultLogos = useMemo(() => saveUsesDefaultLeagueLogos(props.saveState), [props.saveState])

  useEffect(() => {
    if (!preferDefaultLogos) return
    let cancelled = false
    fetch(`${props.apiBase}/default-logos/version`, { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : null))
      .then((j: { version?: number } | null) => {
        if (!cancelled && j && typeof j.version === 'number') setDefaultLogoVersion(j.version)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [props.apiBase, preferDefaultLogos])

  const effectiveLogoVersion = preferDefaultLogos ? (defaultLogoVersion ?? logoVersion) : logoVersion
  const logoPrefs = useMemo(
    () => ({
      preferDefaultLogos,
      logoVersion: effectiveLogoVersion,
      saveId: props.saveId,
    }),
    [preferDefaultLogos, effectiveLogoVersion, props.saveId],
  )
  const allTeamNames = useMemo(() => {
    const teams = props.saveState?.teams ?? []
    const names = teams.map((t: any) => t?.name).filter(Boolean) as string[]
    return [...new Set(names)].sort((a, b) => a.localeCompare(b))
  }, [props.saveState?.teams])

  if (showSettings) {
    return (
      <LogoPrefsProvider value={logoPrefs}>
        <SettingsPage
        apiBase={props.apiBase}
        headers={props.headers}
        saveId={props.saveId}
        teamNames={allTeamNames}
        backupReminderFrequency={props.backupReminderFrequency ?? 'none'}
        onBackupReminderFrequencyChange={props.onBackupReminderFrequencyChange}
        onBackupNow={props.onBackupNow}
        onApplySaveState={props.onSaveState}
        onClose={() => setShowSettings(false)}
        onError={props.onError}
        onLogoVersionBump={() => setLogoVersion(Date.now())}
        onStadiumVersionBump={() => setStadiumVersion(Date.now())}
        onHelmetVersionBump={() => setHelmetVersion(Date.now())}
        onJerseyVersionBump={() => setJerseyVersion(Date.now())}
        onImportLogosToBundle={props.onImportLogosToBundle}
        onImportStadiumsToBundle={props.onImportStadiumsToBundle}
        onImportHelmetsToBundle={props.onImportHelmetsToBundle}
        onImportJerseysToBundle={props.onImportJerseysToBundle}
      />
      </LogoPrefsProvider>
    )
  }

  return (
    <LogoPrefsProvider value={logoPrefs}>
    <NewsProvider saveId={props.saveId} saveState={props.saveState}>
      <NewsStateSync saveId={props.saveId} saveState={props.saveState} leagueHistory={props.leagueHistory} />
      <PlayerProfileProvider
        saveState={props.saveState}
        apiBase={props.apiBase}
        headers={props.headers}
        logoVersion={effectiveLogoVersion}
      >
        <CoachProfileProvider
          saveState={props.saveState}
          apiBase={props.apiBase}
          headers={props.headers}
          saveId={props.saveId}
          logoVersion={effectiveLogoVersion}
          leagueHistory={props.leagueHistory}
          seasonRecaps={props.seasonRecaps}
          onError={props.onError}
        >
          <TeamHomePageBody
            {...props}
            logoVersion={effectiveLogoVersion}
            setLogoVersion={setLogoVersion}
            stadiumVersion={stadiumVersion}
            setStadiumVersion={setStadiumVersion}
            helmetVersion={helmetVersion}
            setHelmetVersion={setHelmetVersion}
            jerseyVersion={jerseyVersion}
            setJerseyVersion={setJerseyVersion}
            onOpenSettings={() => setShowSettings(true)}
          />
        </CoachProfileProvider>
      </PlayerProfileProvider>
      <NewsTicker />
    </NewsProvider>
    </LogoPrefsProvider>
  )
}

