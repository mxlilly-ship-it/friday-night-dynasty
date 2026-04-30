/**
 * Scouting report bundle — coach-readable, rule-generated from save state + games.
 * Serializable for export/print/debug.
 */
export type ScoutingConfidence = 'early' | 'building' | 'firm'

export type ScoutingPace = 'slow' | 'normal' | 'fast'

export type ScoutingMatchupLine = {
  arrow: 'attack' | 'avoid' | 'stop'
  position: string
  player: string
  reason: string
}

export type ScoutingKeyPlayer = {
  role: string
  name: string
  position: string
  tag: string
}

export type ScoutingSituationalRow = {
  situation: string
  label: string
}

export type ScoutingOpponentRow = {
  opponent: string
  result: 'W' | 'L'
  opponentWins: number
  opponentLosses: number
}

export type ScoutingLastWeekBoxScore = {
  opponent: string
  result: 'W' | 'L'
  score: string
  notes: string[]
}

export type OffensiveScoutingReport = {
  teamName: string
  schoolTypeLabel: string
  classification: string
  confidence: ScoutingConfidence
  confidenceNote: string
  /** 0–1 from coach playcalling + scheme_teach vs games played */
  reportSharpness: number
  identity: {
    playbook: string
    philosophy: string
    offensiveStyle: string
    springOffenseFocus: string
  }
  runPass: { runPct: number; passPct: number; note: string }
  pace: { label: ScoutingPace; playsPerGame: number }
  playCallerType: string[]
  recentForm: { bigWins: string; toughLosses: string; lastGame: string }
  lastWeekBoxScore: ScoutingLastWeekBoxScore | null
  gameplanRecommendations: string[]
  opponentSchedule: ScoutingOpponentRow[]
  strengths: string[]
  weaknesses: string[]
  whoToAttack: ScoutingMatchupLine[]
  whoToStop: ScoutingMatchupLine[]
  keyPlayers: ScoutingKeyPlayer[]
  tendencies: ScoutingSituationalRow[]
  assistantSummary: string
}

export type DefensiveScoutingReport = {
  teamName: string
  schoolTypeLabel: string
  classification: string
  confidence: ScoutingConfidence
  confidenceNote: string
  reportSharpness: number
  identity: {
    playbook: string
    philosophy: string
    defensiveStyle: string
    springDefenseFocus: string
  }
  blitzFrequency: 'low' | 'medium' | 'high'
  coverageTilt: string
  lastWeekBoxScore: ScoutingLastWeekBoxScore | null
  gameplanRecommendations: string[]
  opponentSchedule: ScoutingOpponentRow[]
  strengths: string[]
  weaknesses: string[]
  whoToAttack: ScoutingMatchupLine[]
  whoToAvoid: ScoutingMatchupLine[]
  pressureByDown: ScoutingSituationalRow[]
  assistantSummary: string
}

export type ScoutingReportBundle = {
  generatedAt: string
  gamesSampled: number
  offense: OffensiveScoutingReport
  defense: DefensiveScoutingReport
}
