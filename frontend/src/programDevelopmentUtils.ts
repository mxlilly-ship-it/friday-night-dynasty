export type ProgramEquipmentItem = {
  id: string
  name: string
  category: string
  subcategory: string
  cost: number
  attributes_affected?: string[]
  expiration_years: number
}

export type ProgramEquipmentCatalog = {
  version: number
  renewal_cost_multiplier: number
  items: ProgramEquipmentItem[]
}

export type ProgramInventoryRow = {
  item_id: string
  seasons_remaining: number
  purchased_year?: number
  renewals?: number
}

export type ProgramDevAction = {
  item_id: string
  action: 'purchase' | 'renew'
}

const FUNDING_BASE = 8_750
const FUNDING_MULTIPLIER = 16_658
const FUNDING_EXPONENT = 1.3
const FUNDING_INCOME_MIN = 20_000
const FUNDING_INCOME_MAX = 100_000
export const FUNDING_BALANCE_CAP = 250_000

export function fmtProgramDollars(n: number | null | undefined): string {
  const v = Number(n)
  if (!Number.isFinite(v)) return '—'
  return `$${Math.round(v).toLocaleString()}`
}

export function computeAnnualFunding(boosterRating: number, wins: number, communityOutreach: number): number {
  const b = Math.max(1, Math.min(10, Math.round(boosterRating || 5)))
  const o = Math.max(1, Math.min(10, Math.round(communityOutreach || 5)))
  const w = Math.max(0, Math.min(10, Math.round(wins || 0)))
  const score = (b / 10) * 0.5 + w * 0.3 + (o / 10) * 0.2
  const raw = FUNDING_BASE + score ** FUNDING_EXPONENT * FUNDING_MULTIPLIER
  return Math.max(FUNDING_INCOME_MIN, Math.min(FUNDING_INCOME_MAX, Math.round(raw)))
}

export function renewalCost(item: ProgramEquipmentItem, multiplier = 0.6): number {
  return Math.max(1, Math.round(Number(item.cost || 0) * multiplier))
}

export function catalogById(catalog: ProgramEquipmentCatalog): Record<string, ProgramEquipmentItem> {
  const out: Record<string, ProgramEquipmentItem> = {}
  for (const it of catalog.items || []) {
    if (it?.id) out[it.id] = it
  }
  return out
}

export function ownedItemIds(inventory: ProgramInventoryRow[] | undefined): Set<string> {
  return new Set((inventory || []).map((r) => String(r.item_id || '')).filter(Boolean))
}

export function parsePpFromAttributeLines(lines: string[] | undefined): number {
  if (!lines?.length) return 0
  let total = 0
  const re = /(\d+)\s*PP\s*Points?/gi
  for (const line of lines) {
    re.lastIndex = 0
    let m: RegExpExecArray | null
    while ((m = re.exec(line)) !== null) {
      total += Number(m[1] || 0)
    }
  }
  return total
}

export function hasTrainingEffects(lines: string[] | undefined): boolean {
  if (!lines?.length) return false
  const stripped = lines
    .map((l) => l.replace(/(\d+)\s*PP\s*Points?/gi, '').trim())
    .filter(Boolean)
  return stripped.some((s) => /plus\s+\d+/i.test(s))
}

export function projectedBalanceAfterActions(
  startBalance: number,
  catalogMap: Record<string, ProgramEquipmentItem>,
  owned: Set<string>,
  pending: ProgramDevAction[],
  renewalMultiplier = 0.6,
): number {
  let bal = startBalance
  const ownedSim = new Set(owned)
  for (const act of pending) {
    const spec = catalogMap[act.item_id]
    if (!spec) continue
    const cost =
      act.action === 'renew' ? renewalCost(spec, renewalMultiplier) : Number(spec.cost || 0)
    if (bal < cost) continue
    if (act.action === 'renew') {
      if (!ownedSim.has(act.item_id)) continue
    } else if (ownedSim.has(act.item_id)) {
      continue
    }
    bal -= cost
    ownedSim.add(act.item_id)
  }
  return Math.max(0, bal)
}

export type TeamEquipmentRow = ProgramEquipmentItem & {
  item_id: string
  seasons_remaining: number
  durability_pct: number
  renewal_cost: number
  purchased_year?: number
  renewals?: number
}

export function buildTeamEquipmentRows(
  inventory: ProgramInventoryRow[] | undefined,
  catalog: ProgramEquipmentCatalog,
): TeamEquipmentRow[] {
  const byId = catalogById(catalog)
  const mult = Number(catalog.renewal_cost_multiplier || 0.6)
  const rows: TeamEquipmentRow[] = []
  for (const row of inventory || []) {
    const iid = String(row?.item_id || '').trim()
    if (!iid) continue
    const spec = byId[iid]
    if (!spec) continue
    const expYears = Math.max(1, Number(spec.expiration_years || 1))
    const rem = Number(row.seasons_remaining ?? 0)
    rows.push({
      ...spec,
      item_id: iid,
      seasons_remaining: rem,
      durability_pct: Math.max(0, Math.min(100, Math.round((rem / expYears) * 100))),
      renewal_cost: renewalCost(spec, mult),
      purchased_year: row.purchased_year,
      renewals: row.renewals,
    })
  }
  const catOrder = [
    'Football Equipment',
    'Strength & Conditioning',
    'Training & Recovery',
    'Film / IQ / Coaching',
    'Locker Room & Culture',
  ]
  const rank = (c: string) => {
    const i = catOrder.indexOf(c)
    return i >= 0 ? i : 99
  }
  rows.sort((a, b) => {
    const byCat = rank(a.category) - rank(b.category)
    if (byCat !== 0) return byCat
    return a.name.localeCompare(b.name)
  })
  return rows
}
