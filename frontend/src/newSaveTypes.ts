/** Row from data/teams.json */
export type TeamJsonRow = {
  name: string
  /** Optional short label from data file; not loaded onto sim Team model */
  abbreviation?: string
  prestige?: number
  classification?: string
  /** Regular-season scheduling pod with same classification; e.g. North, A, Region 1 — see regionOptions.ts presets */
  region?: string
  culture_grade?: number
  booster_support?: number
  community?: string
  enrollment?: number
  facilities_grade?: number
}

export type TeamsDataResponse = {
  _schema?: string
  teams: TeamJsonRow[]
}

export const OFFENSIVE_STYLES = [
  'Heavy Run',
  'Lean Run',
  'Balanced',
  'Lean Pass',
  'Heavy Pass',
] as const

export const OFFENSIVE_PLAYBOOKS = ['Spread', 'Pro', 'Flexbone', 'Smashmouth', 'Double Wing', 'Wing T'] as const
export type OffensivePlaybook = (typeof OFFENSIVE_PLAYBOOKS)[number]

export const OFFENSIVE_PLAYBOOK_TO_FORMATIONS: Record<OffensivePlaybook, string[]> = {
  Spread: ['Dual', 'Trio', 'Empty', 'Doubles'],
  Pro: ['Pro', 'Twins', 'Dual', 'Doubles', 'Trey Wing', 'Wing'],
  Flexbone: ['Flexbone', 'Power I', 'Dual'],
  Smashmouth: ['Power I', 'Trey Wing', 'Wing', 'Dual'],
  'Double Wing': ['Double Wing', 'Power I', 'Dual'],
  'Wing T': ['Wing T', 'Power I', 'Flexbone', 'Dual'],
}

export const DEFENSIVE_STYLES = [
  'Base',
  'Heavy Pressure',
  'Aggressive Man',
  'Conservative Man',
  'Primary Zone',
  'Aggressive Zone',
] as const

export const DEFENSIVE_PLAYBOOKS = ['4-3', '3-4', '5-2', '3-3 Stack'] as const
export type DefensivePlaybook = (typeof DEFENSIVE_PLAYBOOKS)[number]

export const DEFENSIVE_PLAYBOOK_TO_FORMATIONS: Record<DefensivePlaybook, string[]> = {
  '4-3': ['4-3', 'Nickel', 'Dime', '6-2'],
  '3-4': ['3-4', '5-2', 'Nickel', 'Dime', '6-2'],
  '5-2': ['5-2', 'Nickel', 'Dime', '6-2'],
  '3-3 Stack': ['3-3 Stack', '3-3 Stack 3-High', 'Dime', '6-2'],
}

export type CoachPreset = {
  id: string
  title: string
  blurb: string
  config: Partial<{
    playcalling: number
    player_development: number
    community_outreach: number
    culture: number
    recruiting: number
    scheme_teach: number
    offensive_style: string
    defensive_style: string
    winter_strength_pct: number
  }>
}

export const COACH_PRESETS: CoachPreset[] = [
  {
    id: 'balanced',
    title: 'Balanced leader',
    blurb: 'No glaring weakness — steady program builder.',
    config: {
      playcalling: 6,
      player_development: 6,
      community_outreach: 6,
      culture: 6,
      recruiting: 6,
      scheme_teach: 6,
      offensive_style: 'Balanced',
      defensive_style: 'Base',
    },
  },
  {
    id: 'ceo',
    title: 'Program CEO',
    blurb: 'Culture, community, boosters — you run the brand.',
    config: {
      playcalling: 4,
      player_development: 5,
      community_outreach: 9,
      culture: 9,
      recruiting: 6,
      scheme_teach: 5,
      offensive_style: 'Lean Run',
      defensive_style: 'Conservative Man',
    },
  },
  {
    id: 'tactician',
    title: "X's & O's",
    blurb: 'Playcalling and installing schemes are your edge.',
    config: {
      playcalling: 9,
      player_development: 6,
      community_outreach: 4,
      culture: 5,
      recruiting: 4,
      scheme_teach: 9,
      offensive_style: 'Lean Pass',
      defensive_style: 'Primary Zone',
    },
  },
  {
    id: 'developer',
    title: 'Developer',
    blurb: 'Grow kids and bring in talent every class.',
    config: {
      playcalling: 5,
      player_development: 9,
      community_outreach: 5,
      culture: 7,
      recruiting: 9,
      scheme_teach: 6,
      offensive_style: 'Balanced',
      defensive_style: 'Base',
    },
  },
  {
    id: 'pressure',
    title: 'Pressure coach',
    blurb: 'Aggressive defense, attack on offense.',
    config: {
      playcalling: 7,
      player_development: 6,
      community_outreach: 5,
      culture: 6,
      recruiting: 5,
      scheme_teach: 7,
      offensive_style: 'Lean Run',
      defensive_style: 'Heavy Pressure',
    },
  },
]

export const DEFAULT_SKILLS = {
  playcalling: 5,
  player_development: 5,
  community_outreach: 5,
  culture: 5,
  recruiting: 5,
  scheme_teach: 5,
  offensive_style: 'Balanced',
  defensive_style: 'Base',
  winter_strength_pct: 50,
  // For now, we store the offensive *playbook* in the same coach field that used to hold a single formation.
  // Backend maps:
  // - Spread -> Dual + Trio + Empty + Doubles
  // - Pro -> Pro + Twins + Dual + Doubles + Trey Wing + Wing
  // - Flexbone -> Flexbone + Power I + Dual
  // - Smashmouth -> Power I + Trey Wing + Wing + Dual
  // - Double Wing -> Double Wing + Power I + Dual
  // - Wing T -> Wing T + Power I + Flexbone + Dual
  offensive_formation: 'Spread',
  // Defensive *playbook* on the same coach field. Backend expands to multiple fronts per playbook.
  defensive_formation: '4-3',
}
