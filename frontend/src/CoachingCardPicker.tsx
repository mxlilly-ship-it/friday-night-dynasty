import { useMemo, useState, type CSSProperties } from 'react'
import {
  ALL_COACHING_CARDS,
  GROUP_LABELS,
  MAX_PLATINUM_CARDS,
  MAX_POSITION_CARDS,
  PLATINUM_CARDS,
  POSITION_CARDS,
  PROGRAM_IDENTITY_CARDS,
  cardEquipCost,
  computeLoadoutEquipCost,
  type CoachingCardDef,
  type CoachingCardLoadout,
  canEquipCard,
  isCardEquipped,
  normalizeLoadout,
  toggleCard,
  validateLoadout,
} from './coachingCards'
import './CoachingCardPicker.css'

type Props = {
  loadout: CoachingCardLoadout
  onChange: (next: CoachingCardLoadout) => void
  disabled?: boolean
  showHardcore?: boolean
  hardcore?: boolean
  onHardcoreChange?: (v: boolean) => void
  compact?: boolean
  showCosts?: boolean
  availableCp?: number | null
  creationBonusCp?: number | null
  savedLoadout?: CoachingCardLoadout
  cardLedger?: Record<string, number>
}

function CardTile({
  card,
  equipped,
  canEquip,
  disabled,
  onToggle,
  showCost,
}: {
  card: CoachingCardDef
  equipped: boolean
  canEquip: boolean
  disabled?: boolean
  onToggle: () => void
  showCost?: boolean
}) {
  const dim = !equipped && !canEquip
  const cost = cardEquipCost(card.id)
  return (
    <button
      type="button"
      className={`cc-tile cc-tile--${card.group} ${equipped ? 'cc-tile--on' : ''} ${dim ? 'cc-tile--dim' : ''} ${card.layer === 'platinum' ? 'cc-tile--platinum' : ''}`}
      style={{ '--cc-accent': card.accent } as CSSProperties}
      disabled={disabled || (dim && !equipped)}
      onClick={onToggle}
      title={card.tradeoff}
    >
      <div className="cc-tile-badge">{card.layer === 'platinum' ? 'Pt' : card.group.slice(0, 2).toUpperCase()}</div>
      <div className="cc-tile-name">{card.name}</div>
      {showCost ? <div className="cc-tile-cost">{cost} CP</div> : null}
      <p className="cc-tile-ability">{card.ability}</p>
      <p className="cc-tile-tradeoff">{card.tradeoff}</p>
      {equipped ? <span className="cc-tile-equipped">Equipped</span> : null}
    </button>
  )
}

function CardSection({
  title,
  cards,
  loadout,
  disabled,
  onToggle,
  showCost,
  equipOpts,
}: {
  title: string
  cards: CoachingCardDef[]
  loadout: CoachingCardLoadout
  disabled?: boolean
  onToggle: (id: string) => void
  showCost?: boolean
  equipOpts?: {
    availableCp?: number | null
    savedLoadout?: CoachingCardLoadout
    cardLedger?: Record<string, number>
  }
}) {
  return (
    <section className="cc-section">
      <h3 className="cc-section-title">{title}</h3>
      <div className="cc-grid">
        {cards.map((card) => (
          <CardTile
            key={card.id}
            card={card}
            equipped={isCardEquipped(loadout, card.id)}
            canEquip={canEquipCard(loadout, card.id, equipOpts)}
            disabled={disabled}
            onToggle={() => onToggle(card.id)}
            showCost={showCost}
          />
        ))}
      </div>
    </section>
  )
}

export default function CoachingCardPicker({
  loadout,
  onChange,
  disabled,
  showHardcore,
  hardcore,
  onHardcoreChange,
  compact,
  showCosts = false,
  availableCp = null,
  creationBonusCp = null,
  savedLoadout,
  cardLedger,
}: Props) {
  const lo = useMemo(() => normalizeLoadout(loadout), [loadout])
  const savedLo = useMemo(() => normalizeLoadout(savedLoadout ?? loadout), [savedLoadout, loadout])
  const ledger = cardLedger ?? {}
  const equipOpts = useMemo(
    () => ({ availableCp, savedLoadout: savedLo, cardLedger: ledger }),
    [availableCp, savedLo, ledger],
  )
  const [tab, setTab] = useState<'program' | 'position' | 'platinum'>('program')
  const errors = useMemo(() => validateLoadout(lo), [lo])
  const equipCost = useMemo(() => (hardcore ? 0 : computeLoadoutEquipCost(lo)), [lo, hardcore])

  const handleToggle = (id: string) => {
    if (hardcore) return
    if (!isCardEquipped(lo, id) && !canEquipCard(lo, id, equipOpts)) return
    onChange(toggleCard(lo, id))
  }

  const handleHardcore = (v: boolean) => {
    onHardcoreChange?.(v)
    if (v) onChange({ program_identity: null, position: [], platinum: [] })
  }

  return (
    <div className={`cc-picker ${compact ? 'cc-picker--compact' : ''}`}>
      {showHardcore ? (
        <div className="cc-hardcore-banner">
          <p>
            <strong>Coaching Cards</strong> shape how your program develops players — identity, position focus, and
            platinum ceiling breakthroughs. Card costs come from your opening CP bonus ({creationBonusCp ?? 60}–80 CP
            depending on school prestige). Unequipping refunds 50% CP at season milestones later.
          </p>
          <label className="cc-hardcore-toggle">
            <input
              type="checkbox"
              checked={Boolean(hardcore)}
              onChange={(e) => handleHardcore(e.target.checked)}
              disabled={disabled}
            />
            Hardcore Mode — no coaching cards
          </label>
        </div>
      ) : (
        <p className="cc-intro">
          Equip up to <strong>1</strong> program identity, <strong>{MAX_POSITION_CARDS}</strong> position cards, and{' '}
          <strong>{MAX_PLATINUM_CARDS}</strong> platinum upgrades. Changing identity mid-dynasty adds a swap fee.
          Unequipping refunds <strong>50%</strong> of what you paid.
        </p>
      )}

      {showCosts && !hardcore ? (
        <div className="cc-cp-ledger">
          <span>
            Loadout cost: <strong>{equipCost} CP</strong>
          </span>
          {creationBonusCp != null ? (
            <span>
              Creation bonus: <strong>{creationBonusCp} CP</strong>
            </span>
          ) : null}
          {availableCp != null ? (
            <span className={availableCp < 0 ? 'cc-cp-negative' : undefined}>
              Available after cards: <strong>{availableCp.toFixed(1)} CP</strong>
            </span>
          ) : null}
        </div>
      ) : null}

      <div className="cc-slots">
        <span>Identity: {lo.program_identity ? 1 : 0}/1</span>
        <span>Position: {lo.position.length}/{MAX_POSITION_CARDS}</span>
        <span>Platinum: {lo.platinum.length}/{MAX_PLATINUM_CARDS}</span>
      </div>

      {errors.length > 0 ? (
        <div className="cc-errors" role="alert">
          {errors.map((e) => (
            <div key={e}>{e}</div>
          ))}
        </div>
      ) : null}

      {!compact ? (
        <>
          <div className="cc-tabs">
            {(['program', 'position', 'platinum'] as const).map((t) => (
              <button
                key={t}
                type="button"
                className={tab === t ? 'active' : ''}
                onClick={() => setTab(t)}
              >
                {t === 'program' ? 'Program Identity' : t === 'position' ? 'Position' : 'Platinum'}
              </button>
            ))}
          </div>
          {tab === 'program' ? (
            <CardSection
              title={GROUP_LABELS.identity}
              cards={PROGRAM_IDENTITY_CARDS}
              loadout={lo}
              disabled={disabled || hardcore}
              onToggle={handleToggle}
              showCost={showCosts && !hardcore}
              equipOpts={equipOpts}
            />
          ) : null}
          {tab === 'position' ? (
            <CardSection
              title="Position Cards"
              cards={POSITION_CARDS}
              loadout={lo}
              disabled={disabled || hardcore}
              onToggle={handleToggle}
              showCost={showCosts && !hardcore}
              equipOpts={equipOpts}
            />
          ) : null}
          {tab === 'platinum' ? (
            <>
              <p className="cc-intro" style={{ marginTop: 0 }}>
                Platinum upgrades need the matching position card. Selecting platinum auto-equips its base card when you
                have an open position slot. If all three slots are full, swap a position card first.
              </p>
              <CardSection
                title="Platinum Upgrades"
                cards={PLATINUM_CARDS}
                loadout={lo}
                disabled={disabled || hardcore}
                onToggle={handleToggle}
                showCost={showCosts && !hardcore}
                equipOpts={equipOpts}
              />
            </>
          ) : null}
        </>
      ) : (
        <div className="cc-equipped-list">
          {ALL_COACHING_CARDS.filter((c) => isCardEquipped(lo, c.id)).map((c) => (
            <span key={c.id} className="cc-equipped-chip" style={{ borderColor: c.accent }}>
              {c.name}
            </span>
          ))}
          {!lo.program_identity && lo.position.length === 0 && lo.platinum.length === 0 ? (
            <span className="cc-equipped-empty">No cards equipped</span>
          ) : null}
        </div>
      )}
    </div>
  )
}

