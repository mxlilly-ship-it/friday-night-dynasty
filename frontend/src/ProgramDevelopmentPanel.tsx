import { useMemo, useState } from 'react'
import catalogJson from './programEquipmentCatalog.json'
import {
  catalogById,
  computeAnnualFunding,
  fmtProgramDollars,
  ownedItemIds,
  projectedBalanceAfterActions,
  renewalCost,
  type ProgramDevAction,
  type ProgramEquipmentCatalog,
  type ProgramInventoryRow,
} from './programDevelopmentUtils'
import './ProgramDevelopmentPanel.css'

const CATALOG = catalogJson as ProgramEquipmentCatalog
const BY_ID = catalogById(CATALOG)

const SHOP_GROUPS: { id: string; label: string; subcategories: string[] }[] = [
  { id: 'blocking', label: 'Blocking equipment', subcategories: ['blocking'] },
  { id: 'qb', label: 'QB training', subcategories: ['qb'] },
  { id: 'receiving', label: 'Receiving', subcategories: ['receiving'] },
  { id: 'defense', label: 'Defense training', subcategories: ['defense'] },
  { id: 'sc', label: 'Strength & conditioning', subcategories: ['sc'] },
  { id: 'recovery', label: 'Training & recovery', subcategories: ['recovery'] },
  { id: 'film', label: 'Film & coaching', subcategories: ['film'] },
  { id: 'locker', label: 'Locker room & culture', subcategories: ['locker'] },
]

const CATALOG_CATEGORY_ORDER = [
  'Football Equipment',
  'Strength & Conditioning',
  'Training & Recovery',
  'Film / IQ / Coaching',
  'Locker Room & Culture',
] as const

type Props = {
  saveState: any
  userTeam: string
  pendingActions: ProgramDevAction[]
  onPendingActionsChange: (actions: ProgramDevAction[]) => void
}

function findTeam(saveState: any, name: string) {
  return (saveState?.teams as any[] | undefined)?.find((t) => t?.name === name)
}

export default function ProgramDevelopmentPanel({
  saveState,
  userTeam,
  pendingActions,
  onPendingActionsChange,
}: Props) {
  const [tab, setTab] = useState<'shop' | 'facilities' | 'expiring' | 'boosters' | 'guide'>('shop')
  const [shopGroup, setShopGroup] = useState('blocking')
  const [guideCategory, setGuideCategory] = useState<string>('all')
  const [notice, setNotice] = useState<{ text: string; bad?: boolean } | null>(null)

  const team = findTeam(saveState, userTeam)
  const inventory = (team?.program_equipment || []) as ProgramInventoryRow[]
  const owned = useMemo(() => ownedItemIds(inventory), [inventory])
  const balance = Number(team?.program_funding_balance ?? 0)
  const lastIncome = Number(team?.program_last_funding_income ?? 0)
  const wins = Number(team?.wins ?? 0)
  const losses = Number(team?.losses ?? 0)
  const booster = Number(team?.booster_support ?? 5)
  const outreach = Number(team?.coach?.community_outreach ?? 5)
  const prestige = Number(team?.prestige ?? 5)

  const projectedBal = useMemo(
    () =>
      projectedBalanceAfterActions(
        balance,
        BY_ID,
        owned,
        pendingActions,
        Number(CATALOG.renewal_cost_multiplier || 0.6),
      ),
    [balance, owned, pendingActions],
  )

  const pendingCost = balance - projectedBal

  const renewQueuedIds = useMemo(
    () => new Set(pendingActions.filter((a) => a.action === 'renew').map((a) => a.item_id)),
    [pendingActions],
  )

  const enrichedInventory = useMemo(() => {
    return inventory
      .map((row) => {
        const spec = BY_ID[String(row.item_id)]
        if (!spec) return null
        const expYears = Math.max(1, Number(spec.expiration_years || 1))
        const rem = Number(row.seasons_remaining ?? 0)
        const renewQueued = renewQueuedIds.has(String(row.item_id))
        const displayRem = renewQueued ? expYears : rem
        return {
          ...spec,
          item_id: String(row.item_id),
          seasons_remaining: rem,
          renew_queued: renewQueued,
          durability_pct: renewQueued
            ? 100
            : Math.max(0, Math.min(100, Math.round((rem / expYears) * 100))),
          display_seasons_remaining: displayRem,
          renewal_cost: renewalCost(spec, Number(CATALOG.renewal_cost_multiplier || 0.6)),
        }
      })
      .filter(Boolean) as Array<
      ProgramEquipmentCatalog['items'][number] & {
        item_id: string
        seasons_remaining: number
        durability_pct: number
        renewal_cost: number
        renew_queued?: boolean
        display_seasons_remaining?: number
      }
    >
  }, [inventory, renewQueuedIds])

  const expiring = enrichedInventory.filter((r) => r.seasons_remaining <= 1)

  const shopItems = useMemo(() => {
    const grp = SHOP_GROUPS.find((g) => g.id === shopGroup)
    if (!grp) return []
    return (CATALOG.items || []).filter((it) => grp.subcategories.includes(it.subcategory))
  }, [shopGroup])

  const guideItems = useMemo(() => {
    const catRank = (c: string) => {
      const i = CATALOG_CATEGORY_ORDER.indexOf(c as (typeof CATALOG_CATEGORY_ORDER)[number])
      return i >= 0 ? i : 99
    }
    return [...(CATALOG.items || [])].sort((a, b) => {
      const byCat = catRank(a.category) - catRank(b.category)
      if (byCat !== 0) return byCat
      return a.name.localeCompare(b.name)
    })
  }, [])

  const filteredGuideItems = useMemo(() => {
    if (guideCategory === 'all') return guideItems
    return guideItems.filter((it) => it.category === guideCategory)
  }, [guideItems, guideCategory])

  const queueAction = (action: ProgramDevAction, label: string) => {
    if (action.action === 'renew' && renewQueuedIds.has(action.item_id)) return
    onPendingActionsChange([...pendingActions, action])
    setNotice({ text: `${label} queued — press Continue to confirm.` })
    window.setTimeout(() => setNotice(null), 2500)
  }

  const fundingPreview = computeAnnualFunding(booster, wins, outreach)

  return (
    <div className="program-dev-root">
      <div className="program-dev-topbar">
        <div className="program-dev-title">
          {userTeam || 'Your program'}
          <span className="program-dev-badge">Year {Number(saveState?.current_year ?? '—')}</span>
        </div>
        <div className="program-dev-pills">
          <div className="program-dev-pill program-dev-pill-income">
            <span className="program-dev-pill-lbl">Season income</span>
            <span className="program-dev-pill-val">{fmtProgramDollars(lastIncome)}</span>
          </div>
          <div className="program-dev-pill">
            <span className="program-dev-pill-lbl">Budget</span>
            <span className="program-dev-pill-val">{fmtProgramDollars(balance)}</span>
          </div>
          {pendingCost > 0 ? (
            <div className="program-dev-pill program-dev-pill-pending">
              <span className="program-dev-pill-lbl">Queued spend</span>
              <span className="program-dev-pill-val">−{fmtProgramDollars(pendingCost)}</span>
            </div>
          ) : null}
        </div>
      </div>

      <div className="program-dev-stats">
        <div className="program-dev-stat">
          <div className="program-dev-stat-lbl">Record</div>
          <div className="program-dev-stat-val">
            {wins}–{losses}
          </div>
        </div>
        <div className="program-dev-stat">
          <div className="program-dev-stat-lbl">Booster support</div>
          <div className="program-dev-stat-val">
            {booster}
            <span className="program-dev-stat-sub">/10</span>
          </div>
        </div>
        <div className="program-dev-stat">
          <div className="program-dev-stat-lbl">Coach outreach</div>
          <div className="program-dev-stat-val">
            {outreach}
            <span className="program-dev-stat-sub">/10</span>
          </div>
        </div>
        <div className="program-dev-stat">
          <div className="program-dev-stat-lbl">Prestige</div>
          <div className="program-dev-stat-val">
            {prestige}
            <span className="program-dev-stat-sub">/15</span>
          </div>
        </div>
      </div>

      <div className="program-dev-tabs">
        {(
          [
            ['shop', 'Shop upgrades'],
            ['facilities', 'My facilities'],
            ['expiring', `Expiring${expiring.length ? ` (${expiring.length})` : ''}`],
            ['boosters', 'Funding'],
            ['guide', 'Equipment guide'],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={`program-dev-tab${tab === id ? ' active' : ''}`}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'shop' ? (
        <div className="program-dev-two-col">
          <div className="program-dev-panel">
            <div className="program-dev-panel-head">Browse equipment</div>
            <div className="program-dev-panel-body">
              <select
                className="teamhome-select program-dev-cat-sel"
                value={shopGroup}
                onChange={(e) => setShopGroup(e.target.value)}
              >
                {SHOP_GROUPS.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.label}
                  </option>
                ))}
              </select>
              <div className="program-dev-shop-list">
                {shopItems.map((it) => {
                  const isOwned = owned.has(it.id)
                  const cost = Number(it.cost || 0)
                  const canBuy = !isOwned && projectedBal >= cost
                  return (
                    <div key={it.id} className="program-dev-shop-item">
                      <div>
                        <div className="program-dev-shop-name">{it.name}</div>
                        <div className="program-dev-shop-attr">{it.attributes_affected?.[0] || '—'}</div>
                        <div className="program-dev-shop-exp">
                          Lasts {it.expiration_years} season{it.expiration_years === 1 ? '' : 's'}
                        </div>
                      </div>
                      <div className="program-dev-shop-right">
                        <span className="program-dev-shop-cost">{fmtProgramDollars(cost)}</span>
                        <button
                          type="button"
                          className={`program-dev-buy${canBuy ? ' program-dev-buy--ok' : ''}`}
                          disabled={isOwned || !canBuy}
                          onClick={() => queueAction({ item_id: it.id, action: 'purchase' }, it.name)}
                        >
                          {isOwned ? 'Owned' : 'Buy'}
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
              {notice ? (
                <div className={`program-dev-notice${notice.bad ? ' program-dev-notice--bad' : ''}`}>{notice.text}</div>
              ) : null}
              <p className="program-dev-hint">
                Purchases apply when you press <b>Continue</b>. CPU schools shop automatically after you advance.
              </p>
            </div>
          </div>
          <div className="program-dev-panel">
            <div className="program-dev-panel-head">Current facilities (quick view)</div>
            <div className="program-dev-panel-body program-dev-scroll">
              {enrichedInventory.length === 0 ? (
                <p className="program-dev-empty">No equipment owned yet.</p>
              ) : (
                enrichedInventory.slice(0, 12).map((it) => (
                  <div
                    key={it.item_id}
                    className={`program-dev-fac-row${it.renew_queued ? ' program-dev-fac-row--renew-queued' : ''}`}
                  >
                    <div>
                      <div className="program-dev-shop-name">{it.name}</div>
                      <div className="program-dev-shop-attr">{it.attributes_affected?.[0] || '—'}</div>
                    </div>
                    <div className="program-dev-dur">
                      <div className="program-dev-dur-bar">
                        <div
                          className={`program-dev-dur-fill${it.renew_queued || it.durability_pct > 60 ? ' good' : it.durability_pct > 30 ? ' mid' : ' low'}`}
                          style={{ width: `${it.durability_pct}%` }}
                        />
                      </div>
                      <span>{it.renew_queued ? 'Renewal queued' : `${it.durability_pct}%`}</span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      ) : null}

      {tab === 'facilities' ? (
        <div className="program-dev-panel">
          <div className="program-dev-panel-head">All owned facilities</div>
          <div className="program-dev-panel-body program-dev-fac-grid">
            {enrichedInventory.length === 0 ? (
              <p className="program-dev-empty">No equipment owned yet.</p>
            ) : (
              enrichedInventory.map((it) => (
                <div
                  key={it.item_id}
                  className={`program-dev-fac-row${it.renew_queued ? ' program-dev-fac-row--renew-queued' : ''}`}
                >
                  <div>
                    <div className="program-dev-shop-name">{it.name}</div>
                    <div className="program-dev-shop-attr">{it.category}</div>
                  </div>
                  <div className="program-dev-dur">
                    <div className="program-dev-dur-bar">
                      <div
                        className={`program-dev-dur-fill${it.renew_queued || it.durability_pct > 60 ? ' good' : it.durability_pct > 30 ? ' mid' : ' low'}`}
                        style={{ width: `${it.durability_pct}%` }}
                      />
                    </div>
                    <span>
                      {it.renew_queued
                        ? 'Renewal queued'
                        : `${Number(it.display_seasons_remaining ?? it.seasons_remaining).toFixed(1)} yrs left`}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      ) : null}

      {tab === 'expiring' ? (
        <div className="program-dev-panel">
          <div className="program-dev-panel-head">Expiring equipment</div>
          <div className="program-dev-panel-body">
            <p className="program-dev-hint">Items with one season or less remaining. Renew to reset durability.</p>
            <div className="program-dev-exp-list">
              {expiring.length === 0 ? (
                <p className="program-dev-empty">Nothing expiring soon.</p>
              ) : (
                expiring.map((it) => {
                  const queued = Boolean(it.renew_queued)
                  return (
                  <div
                    key={it.item_id}
                    className={`program-dev-exp-item${
                      queued ? ' renew-queued' : it.seasons_remaining <= 0.5 ? ' urgent' : ' soon'
                    }`}
                  >
                    <div>
                      <div className="program-dev-exp-badge">
                        {queued
                          ? 'Renewal queued — press Continue to confirm'
                          : it.seasons_remaining <= 0.5
                            ? 'Expires this season'
                            : '1 season remaining'}
                      </div>
                      <div className="program-dev-shop-name">{it.name}</div>
                      <div className="program-dev-shop-attr">
                        {queued ? 'Will reset to full durability' : `Renewal: ${fmtProgramDollars(it.renewal_cost)}`}
                      </div>
                    </div>
                    <button
                      type="button"
                      className={`program-dev-renew${queued ? ' program-dev-renew--queued' : ''}`}
                      disabled={queued || projectedBal < it.renewal_cost}
                      onClick={() => queueAction({ item_id: it.item_id, action: 'renew' }, `${it.name} renewal`)}
                    >
                      {queued ? 'Queued' : 'Renew'}
                    </button>
                  </div>
                  )
                })
              )}
            </div>
          </div>
        </div>
      ) : null}

      {tab === 'boosters' ? (
        <div className="program-dev-two-col">
          <div className="program-dev-panel">
            <div className="program-dev-panel-head">Funding formula</div>
            <div className="program-dev-panel-body">
              <p className="program-dev-hint">
                Annual deposit at season review: $8,750 base plus a weighted score (boosters 50%, wins 30%, coach
                outreach 20%), raised to the 1.3 power × $16,658. Elite programs (~10/10/10) reach ~$100,000;
                average seasons (~5/5/5) land near $45–50,000; struggling programs (~2/2/2) near $20,000. Income is
                capped at $100,000; balance caps at $250,000.
              </p>
              <div className="program-dev-funding-rows">
                <div>
                  <span>Booster support ({booster}/10)</span>
                  <strong>{fmtProgramDollars(lastIncome ? lastIncome : fundingPreview)}</strong>
                </div>
                <div>
                  <span>Wins this season ({wins})</span>
                  <strong>weight 30%</strong>
                </div>
                <div>
                  <span>Coach outreach ({outreach}/10)</span>
                  <strong>weight 20%</strong>
                </div>
                <div className="program-dev-funding-total">
                  <span>Projected next deposit (similar season)</span>
                  <strong>{fmtProgramDollars(fundingPreview)}</strong>
                </div>
              </div>
            </div>
          </div>
          <div className="program-dev-panel">
            <div className="program-dev-panel-head">Queued this stage</div>
            <div className="program-dev-panel-body">
              {pendingActions.length === 0 ? (
                <p className="program-dev-empty">No queued purchases.</p>
              ) : (
                <ul className="program-dev-queue">
                  {pendingActions.map((a, i) => {
                    const spec = BY_ID[a.item_id]
                    return (
                      <li key={`${a.item_id}-${i}`}>
                        {a.action === 'renew' ? 'Renew' : 'Buy'} — {spec?.name || a.item_id}
                      </li>
                    )
                  })}
                </ul>
              )}
              {pendingActions.length > 0 ? (
                <button type="button" className="program-dev-clear" onClick={() => onPendingActionsChange([])}>
                  Clear queue
                </button>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}

      {tab === 'guide' ? (
        <div className="program-dev-panel">
          <div className="program-dev-panel-head">Equipment &amp; attributes reference</div>
          <div className="program-dev-panel-body">
            <p className="program-dev-hint">
              Full catalog ({guideItems.length} items). Training bonuses apply at{' '}
              <b>Training Results</b>; PP grants deposit into your <b>Improvements</b> bank.
            </p>
            <select
              className="teamhome-select program-dev-cat-sel"
              value={guideCategory}
              onChange={(e) => setGuideCategory(e.target.value)}
            >
              <option value="all">All categories</option>
              {CATALOG_CATEGORY_ORDER.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
            <div className="program-dev-guide-scroll">
              <table className="program-dev-guide-table">
                <thead>
                  <tr>
                    <th>Item</th>
                    <th>Category</th>
                    <th>Cost</th>
                    <th>Attributes affected</th>
                    <th>Lasts</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredGuideItems.map((it) => (
                    <tr key={it.id} className={owned.has(it.id) ? 'program-dev-guide-owned' : undefined}>
                      <td>
                        <div className="program-dev-guide-name">{it.name}</div>
                        {owned.has(it.id) ? <span className="program-dev-guide-tag">Owned</span> : null}
                      </td>
                      <td>{it.category}</td>
                      <td>{fmtProgramDollars(it.cost)}</td>
                      <td>{it.attributes_affected?.join(' · ') || '—'}</td>
                      <td>
                        {it.expiration_years} yr{it.expiration_years === 1 ? '' : 's'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
