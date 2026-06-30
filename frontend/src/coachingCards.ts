/** Coaching Card System — catalog, loadout helpers (mirrors systems/coaching_cards.py). */

export type CoachingCardLayer = 'program' | 'position' | 'platinum'

export type CoachingCardDef = {
  id: string
  name: string
  layer: CoachingCardLayer
  group: string
  accent: string
  ability: string
  tradeoff: string
  primary_groups?: string[]
  requires?: string | null
}

export type CoachingCardLoadout = {
  program_identity: string | null
  position: string[]
  platinum: string[]
}

export const EMPTY_COACHING_LOADOUT: CoachingCardLoadout = {
  program_identity: null,
  position: [],
  platinum: [],
}

export const MAX_PROGRAM_IDENTITY = 1
export const MAX_POSITION_CARDS = 3
export const MAX_PLATINUM_CARDS = 2

const PLATINUM_REQUIRES: Record<string, string> = {
  platinum_qb_whisperer: 'qb_whisperer',
  platinum_ol_guru: 'ol_guru',
  platinum_rb_stable: 'rb_stable',
  platinum_wr_technician: 'wr_technician',
  platinum_te_mismatch: 'te_mismatch',
  platinum_air_attack: 'air_attack',
  platinum_ground_and_pound: 'ground_and_pound',
  platinum_dl_factory: 'dl_factory',
  platinum_linebacker_core: 'linebacker_core',
  platinum_db_ballhawks: 'db_ballhawks',
  platinum_run_stop_unit: 'run_stop_unit',
  platinum_coverage_shell: 'coverage_shell',
}

const POSITION_CARDS_RAW: CoachingCardDef[] = [
  { id: 'qb_whisperer', name: 'QB Whisperer', layer: 'position', group: 'offense', accent: '#3B82F6', ability: 'QB dev +28%; +2% potential per offseason', tradeoff: 'OL dev −10%', primary_groups: ['QB'] },
  { id: 'ol_guru', name: 'OL Guru', layer: 'position', group: 'line', accent: '#78716C', ability: 'OL dev +28%; +2.5% potential per offseason', tradeoff: 'Skill positions −8%', primary_groups: ['OL'] },
  { id: 'rb_stable', name: 'RB Stable', layer: 'position', group: 'skill', accent: '#84CC16', ability: 'RB dev +24%; +2% potential per offseason', tradeoff: 'OL dev −8%', primary_groups: ['RB'] },
  { id: 'wr_technician', name: 'WR Technician', layer: 'position', group: 'skill', accent: '#06B6D4', ability: 'WR dev +26%; +2.5% potential per offseason', tradeoff: 'RB dev −8%', primary_groups: ['WR'] },
  { id: 'te_mismatch', name: 'TE Mismatch', layer: 'position', group: 'skill', accent: '#8B5CF6', ability: 'TE dev +28%; WR dev +12%; +4% TE potential per offseason', tradeoff: 'RB dev −8%', primary_groups: ['TE', 'WR'] },
  { id: 'air_attack', name: 'Air Attack', layer: 'position', group: 'offense', accent: '#0EA5E9', ability: 'QB + WR dev +18%; +2% potential per offseason', tradeoff: 'OL dev −8%', primary_groups: ['QB', 'WR'] },
  { id: 'ground_and_pound', name: 'Ground & Pound', layer: 'position', group: 'line', accent: '#B45309', ability: 'RB + OL dev +20%; +2% potential per offseason', tradeoff: 'QB/WR dev −12%', primary_groups: ['RB', 'OL'] },
  { id: 'dl_factory', name: 'DL Factory', layer: 'position', group: 'defense', accent: '#DC2626', ability: 'DL dev +28%; +2% potential per offseason', tradeoff: 'LB dev −8%', primary_groups: ['DL'] },
  { id: 'linebacker_core', name: 'Linebacker Core', layer: 'position', group: 'defense', accent: '#F97316', ability: 'LB dev +28%; +3% potential per offseason', tradeoff: 'DB dev −8%', primary_groups: ['LB'] },
  { id: 'db_ballhawks', name: 'DB Ballhawks', layer: 'position', group: 'defense', accent: '#10B981', ability: 'DB dev +28%; +2% potential per offseason', tradeoff: 'DL dev −8%', primary_groups: ['DB'] },
  { id: 'run_stop_unit', name: 'Run Stop Unit', layer: 'position', group: 'defense', accent: '#57534E', ability: 'Front 7 dev +22%; +3% potential per offseason', tradeoff: 'DB dev −8%', primary_groups: ['FRONT7'] },
  { id: 'coverage_shell', name: 'Coverage Shell', layer: 'position', group: 'defense', accent: '#2563EB', ability: 'DB dev +28%; +2% potential per offseason', tradeoff: 'DL dev −8%', primary_groups: ['DB'] },
]

export const PROGRAM_IDENTITY_CARDS: CoachingCardDef[] = [
  { id: 'ceiling_raiser', name: 'Ceiling Raiser', layer: 'program', group: 'identity', accent: '#8B5CF6', ability: '+12% potential cap; JR/SR dev +5% faster', tradeoff: 'FR/SO development speed −6%' },
  { id: 'developer', name: 'Developer', layer: 'program', group: 'identity', accent: '#22C55E', ability: 'All players develop +12% faster', tradeoff: 'Program potential cap −8% for all players' },
  { id: 'player_factory', name: 'Player Factory', layer: 'program', group: 'identity', accent: '#F59E0B', ability: '80+ OVR players develop +22% faster', tradeoff: 'Sub-70 OVR players develop −15% slower' },
  { id: 'late_bloomer_developer', name: 'Late Bloomer Developer', layer: 'program', group: 'identity', accent: '#A78BFA', ability: 'JR/SR development +35% faster', tradeoff: 'FR/SO development −20% slower' },
  { id: 'high_floor_program', name: 'High Floor Program', layer: 'program', group: 'identity', accent: '#38BDF8', ability: 'Sub-70 OVR: minimum +12% dev speed', tradeoff: '85+ OVR development −12%' },
  { id: 'boom_or_bust', name: 'Boom or Bust', layer: 'program', group: 'identity', accent: '#EF4444', ability: '8% chance of +10–15 dev spike; boom adds potential', tradeoff: '~5% chance of reduced or zero development' },
  { id: 'underdog_engine', name: 'Underdog Engine', layer: 'program', group: 'identity', accent: '#14B8A6', ability: 'Sub-72 OVR dev +22%; 5% potential bump chance', tradeoff: '80+ OVR dev slows; growth stalls above 85' },
  { id: 'elite_standard', name: 'Elite Standard', layer: 'program', group: 'identity', accent: '#EAB308', ability: '88+ OVR dev +18%; 5% potential bump chance', tradeoff: 'Sub-70 OVR development −10%' },
  { id: 'from_the_bottom_up', name: 'From the Bottom Up', layer: 'program', group: 'identity', accent: '#6366F1', ability: 'FR under-75 potential: +12% potential & +8% dev', tradeoff: 'High-potential FR/SO: −12% development rate' },
]

export const PLATINUM_CARDS: CoachingCardDef[] = Object.entries(PLATINUM_REQUIRES).map(([pid, base]) => {
  const baseCard = POSITION_CARDS_RAW.find((c) => c.id === base)!
  return {
    id: pid,
    name: `Platinum ${baseCard.name}`,
    layer: 'platinum' as const,
    group: baseCard.group,
    accent: '#E5E7EB',
    ability: '5–12% offseason breakthrough chance near potential cap',
    tradeoff: 'Requires base position card; ceiling-only (no speed boost)',
    primary_groups: baseCard.primary_groups,
    requires: base,
  }
})

export const POSITION_CARDS = POSITION_CARDS_RAW

export const ALL_COACHING_CARDS: CoachingCardDef[] = [
  ...PROGRAM_IDENTITY_CARDS,
  ...POSITION_CARDS,
  ...PLATINUM_CARDS,
]

export const COACHING_CARD_BY_ID: Record<string, CoachingCardDef> = Object.fromEntries(
  ALL_COACHING_CARDS.map((c) => [c.id, c]),
)

export const GROUP_LABELS: Record<string, string> = {
  identity: 'Program Identity',
  offense: 'Offense',
  line: 'Trenches',
  skill: 'Skill',
  defense: 'Defense',
}

export function normalizeLoadout(raw: unknown): CoachingCardLoadout {
  if (!raw || typeof raw !== 'object') return { ...EMPTY_COACHING_LOADOUT }
  const o = raw as Record<string, unknown>
  const pid = o.program_identity != null ? String(o.program_identity).trim() : ''
  const program_identity =
    pid && COACHING_CARD_BY_ID[pid]?.layer === 'program' ? pid : null
  const position: string[] = []
  for (const x of Array.isArray(o.position) ? o.position : []) {
    const s = String(x).trim()
    if (COACHING_CARD_BY_ID[s]?.layer === 'position' && !position.includes(s)) position.push(s)
  }
  const platinum: string[] = []
  for (const x of Array.isArray(o.platinum) ? o.platinum : []) {
    const s = String(x).trim()
    if (COACHING_CARD_BY_ID[s]?.layer === 'platinum' && !platinum.includes(s)) platinum.push(s)
  }
  const positionWithBases = [...position]
  for (const p of platinum) {
    const req = PLATINUM_REQUIRES[p]
    if (req && !positionWithBases.includes(req) && positionWithBases.length < MAX_POSITION_CARDS) {
      positionWithBases.push(req)
    }
  }
  return {
    program_identity,
    position: positionWithBases.slice(0, MAX_POSITION_CARDS),
    platinum: platinum.slice(0, MAX_PLATINUM_CARDS),
  }
}

export function validateLoadout(loadout: CoachingCardLoadout): string[] {
  const errors: string[] = []
  const lo = normalizeLoadout(loadout)
  if (lo.position.length > MAX_POSITION_CARDS) errors.push(`Max ${MAX_POSITION_CARDS} position cards.`)
  if (lo.platinum.length > MAX_PLATINUM_CARDS) errors.push(`Max ${MAX_PLATINUM_CARDS} platinum cards.`)
  const posSet = new Set(lo.position)
  for (const p of lo.platinum) {
    const req = PLATINUM_REQUIRES[p]
    if (!req) errors.push(`Unknown platinum: ${p}`)
    else if (!posSet.has(req)) errors.push(`Platinum requires ${COACHING_CARD_BY_ID[req]?.name ?? req}.`)
  }
  return errors
}

export function isCardEquipped(loadout: CoachingCardLoadout, cardId: string): boolean {
  const lo = normalizeLoadout(loadout)
  const c = COACHING_CARD_BY_ID[cardId]
  if (!c) return false
  if (c.layer === 'program') return lo.program_identity === cardId
  if (c.layer === 'position') return lo.position.includes(cardId)
  return lo.platinum.includes(cardId)
}

export function canEquipCard(
  loadout: CoachingCardLoadout,
  cardId: string,
  opts?: {
    availableCp?: number | null
    savedLoadout?: CoachingCardLoadout
    cardLedger?: Record<string, number>
  },
): boolean {
  const lo = normalizeLoadout(loadout)
  const c = COACHING_CARD_BY_ID[cardId]
  if (!c) return false
  if (isCardEquipped(lo, cardId)) return true

  const canAfford = (): boolean => {
    if (opts?.availableCp == null || !opts.savedLoadout) return true
    const next = toggleCard(lo, cardId)
    const { netCost: curNet } = computeLoadoutChangeCp(opts.savedLoadout, lo, opts.cardLedger ?? {})
    const { netCost: nextNet } = computeLoadoutChangeCp(opts.savedLoadout, next, opts.cardLedger ?? {})
    return nextNet - curNet <= opts.availableCp + 1e-6
  }

  if (c.layer === 'program') {
    return (lo.program_identity == null || lo.program_identity === cardId) && canAfford()
  }
  if (c.layer === 'position') {
    return lo.position.length < MAX_POSITION_CARDS && canAfford()
  }
  if (c.layer === 'platinum') {
    if (lo.platinum.length >= MAX_PLATINUM_CARDS) return false
    const req = c.requires
    if (!req) return false
    const hasBase = lo.position.includes(req)
    if (!hasBase && lo.position.length >= MAX_POSITION_CARDS) return false
    return canAfford()
  }
  return false
}

export function toggleCard(loadout: CoachingCardLoadout, cardId: string): CoachingCardLoadout {
  const lo = normalizeLoadout(loadout)
  const c = COACHING_CARD_BY_ID[cardId]
  if (!c) return lo

  if (c.layer === 'program') {
    return { ...lo, program_identity: lo.program_identity === cardId ? null : cardId }
  }
  if (c.layer === 'position') {
    const has = lo.position.includes(cardId)
    let position = has ? lo.position.filter((x) => x !== cardId) : [...lo.position, cardId]
    if (!has && position.length > MAX_POSITION_CARDS) return lo
    const removedBases = new Set(position)
    const platinum = lo.platinum.filter((p) => {
      const req = PLATINUM_REQUIRES[p]
      return req && removedBases.has(req)
    })
    return { ...lo, position: position.slice(0, MAX_POSITION_CARDS), platinum }
  }
  if (c.layer === 'platinum') {
    const has = lo.platinum.includes(cardId)
    if (has) return { ...lo, platinum: lo.platinum.filter((x) => x !== cardId) }
    const req = c.requires
    if (!req) return lo
    let position = [...lo.position]
    if (!position.includes(req)) {
      if (position.length >= MAX_POSITION_CARDS) return lo
      position = [...position, req].slice(0, MAX_POSITION_CARDS)
    }
    if (lo.platinum.length >= MAX_PLATINUM_CARDS) return lo
    return { ...lo, position, platinum: [...lo.platinum, cardId].slice(0, MAX_PLATINUM_CARDS) }
  }
  return lo
}

export function loadoutSummary(loadout: CoachingCardLoadout): string {
  const lo = normalizeLoadout(loadout)
  const parts: string[] = []
  if (lo.program_identity) parts.push(COACHING_CARD_BY_ID[lo.program_identity]?.name ?? lo.program_identity)
  for (const p of lo.position) parts.push(COACHING_CARD_BY_ID[p]?.name ?? p)
  for (const p of lo.platinum) parts.push(COACHING_CARD_BY_ID[p]?.name ?? p)
  return parts.length ? parts.join(' · ') : 'No cards equipped'
}

// ---------------------------------------------------------------------------
// CP costs (mirrors systems/coaching_cards.py)
// ---------------------------------------------------------------------------
export const CARD_REFUND_RATE = 0.5

const IDENTITY_EQUIP_COST: Record<string, number> = {
  boom_or_bust: 28,
  from_the_bottom_up: 28,
  ceiling_raiser: 38,
  elite_standard: 38,
  player_factory: 38,
  developer: 48,
  high_floor_program: 48,
  underdog_engine: 48,
  late_bloomer_developer: 48,
}

const IDENTITY_SWAP_FEE: Record<string, number> = {
  boom_or_bust: 12,
  from_the_bottom_up: 12,
  ceiling_raiser: 16,
  elite_standard: 16,
  player_factory: 16,
  developer: 20,
  high_floor_program: 20,
  underdog_engine: 20,
  late_bloomer_developer: 20,
}

const POSITION_EQUIP_COST: Record<string, number> = {
  qb_whisperer: 32,
  ol_guru: 32,
  dl_factory: 32,
  linebacker_core: 32,
  air_attack: 28,
  ground_and_pound: 28,
  rb_stable: 24,
  wr_technician: 24,
  te_mismatch: 24,
  db_ballhawks: 24,
  run_stop_unit: 20,
  coverage_shell: 20,
}

const PLATINUM_EQUIP_COST = 36

export function loadoutCardIds(loadout: CoachingCardLoadout): string[] {
  const lo = normalizeLoadout(loadout)
  const ids: string[] = []
  if (lo.program_identity) ids.push(lo.program_identity)
  ids.push(...lo.position, ...lo.platinum)
  return ids
}

export function cardEquipCost(cardId: string): number {
  if (IDENTITY_EQUIP_COST[cardId] != null) return IDENTITY_EQUIP_COST[cardId]
  if (POSITION_EQUIP_COST[cardId] != null) return POSITION_EQUIP_COST[cardId]
  if (cardId.startsWith('platinum_')) return PLATINUM_EQUIP_COST
  return 0
}

export function identitySwapFee(identityId: string | null | undefined): number {
  if (!identityId) return 0
  return IDENTITY_SWAP_FEE[identityId] ?? 16
}

export function computeLoadoutEquipCost(loadout: CoachingCardLoadout): number {
  return loadoutCardIds(loadout).reduce((sum, id) => sum + cardEquipCost(id), 0)
}

export function computeLoadoutChangeCp(
  oldLoadout: CoachingCardLoadout,
  newLoadout: CoachingCardLoadout,
  ledger: Record<string, number> = {},
): { netCost: number; newLedger: Record<string, number> } {
  const old = normalizeLoadout(oldLoadout)
  const next = normalizeLoadout(newLoadout)
  const paid: Record<string, number> = { ...ledger }

  const oldIds = new Set(loadoutCardIds(old))
  const newIds = new Set(loadoutCardIds(next))
  let refundTotal = 0
  const newLedger: Record<string, number> = {}

  for (const cid of oldIds) {
    if (!newIds.has(cid)) {
      const amount = paid[cid] ?? cardEquipCost(cid)
      refundTotal += amount * CARD_REFUND_RATE
    }
  }

  for (const cid of newIds) {
    if (oldIds.has(cid)) {
      newLedger[cid] = paid[cid] ?? cardEquipCost(cid)
    }
  }

  let chargeTotal = 0
  for (const cid of newIds) {
    if (!oldIds.has(cid)) {
      const cost = cardEquipCost(cid)
      chargeTotal += cost
      newLedger[cid] = cost
    }
  }

  const oldId = old.program_identity
  const newId = next.program_identity
  if (oldId && newId && oldId !== newId) {
    chargeTotal += identitySwapFee(newId)
  }

  const netCost = Math.round((chargeTotal - refundTotal) * 10) / 10
  return { netCost, newLedger }
}

export function projectedAvailableCpAfterLoadout(
  cpTotal: number,
  allocatedCp: number,
  oldLoadout: CoachingCardLoadout,
  newLoadout: CoachingCardLoadout,
  ledger: Record<string, number> = {},
): number {
  const { netCost } = computeLoadoutChangeCp(oldLoadout, newLoadout, ledger)
  return Math.round((cpTotal - netCost - allocatedCp) * 10) / 10
}

const POSITION_GROUPS: Record<string, Set<string>> = {
  QB: new Set(['QB']),
  RB: new Set(['RB']),
  WR: new Set(['WR']),
  TE: new Set(['TE']),
  OL: new Set(['OL']),
  DL: new Set(['DE', 'DT']),
  LB: new Set(['LB']),
  DB: new Set(['CB', 'S']),
  SKILL: new Set(['QB', 'RB', 'WR', 'TE']),
  FRONT7: new Set(['DE', 'DT', 'LB']),
}

function playerPositionCodes(player: Record<string, unknown>): Set<string> {
  const out = new Set<string>()
  for (const raw of [player.position, player.secondary_position]) {
    const p = String(raw ?? '').trim().toUpperCase()
    if (p) out.add(p)
  }
  return out
}

function playerInGroup(player: Record<string, unknown>, groupKey: string): boolean {
  const codes = playerPositionCodes(player)
  if (codes.has(groupKey)) return true
  const g = POSITION_GROUPS[groupKey]
  if (!g) return false
  for (const c of codes) {
    if (g.has(c)) return true
  }
  return false
}

function playerOverallForBreakthrough(player: Record<string, unknown>): number {
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
  const vals = keys.map((k) => Number(player?.[k] ?? 50))
  return vals.reduce((a, b) => a + b, 0) / vals.length
}

export function effectivePotentialCap(
  player: Record<string, unknown>,
  loadout: CoachingCardLoadout,
): number {
  const base = Number(player.potential ?? 50) || 50
  const lo = normalizeLoadout(loadout)
  const pid = lo.program_identity
  let mult = 1.0
  if (pid === 'ceiling_raiser') mult *= 1.12
  else if (pid === 'developer') mult *= 0.92
  return Math.max(10, Math.min(99, Math.round(base * mult)))
}

export function isPlatinumBreakthroughEligible(
  player: Record<string, unknown>,
  loadout: CoachingCardLoadout,
): boolean {
  if (player.potential == null) return false
  const lo = normalizeLoadout(loadout)
  if (!lo.platinum.length) return false
  const ovr = playerOverallForBreakthrough(player)
  const cap = effectivePotentialCap(player, lo)
  const gap = cap - ovr
  if (gap < 0 || gap > 12) return false
  for (const platId of lo.platinum) {
    const base = PLATINUM_REQUIRES[platId]
    if (!base) continue
    const card = POSITION_CARDS.find((c) => c.id === base)
    if (!card?.primary_groups?.length) continue
    if (card.primary_groups.some((g) => playerInGroup(player, g))) return true
  }
  return false
}
