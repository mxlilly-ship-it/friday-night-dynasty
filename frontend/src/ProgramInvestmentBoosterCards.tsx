import { useCallback, useEffect, useRef, useState } from 'react'
import {
  PILLAR_CHIP_VALUES,
  PILLAR_CUMULATIVE_PP_MAX,
  pillarRingDisplay,
  type ProgramInvestmentPillar,
} from './programInvestment'
import './ProgramInvestmentBoosterCards.css'

type Props = {
  pillars: ProgramInvestmentPillar[]
  bankAmount: number
  netCredited: number | null
  onTargetChange: (pillarId: string, nextCumulative: number) => void
  /** Changes when the stage re-initializes from save data — clears chip history. */
  resetToken: string
}

type ChipMap = Record<string, number[]>

function clampTarget(n: number): number {
  return Math.max(0, Math.min(PILLAR_CUMULATIVE_PP_MAX, Math.round(n)))
}

export default function ProgramInvestmentBoosterCards({
  pillars,
  bankAmount,
  netCredited,
  onTargetChange,
  resetToken,
}: Props) {
  const [chips, setChips] = useState<ChipMap>({})
  const [flashId, setFlashId] = useState<string | null>(null)
  const levelRef = useRef<Record<string, number>>({})

  useEffect(() => {
    setChips({})
    const next: Record<string, number> = {}
    for (const p of pillars) {
      next[p.id] = pillarRingDisplay(p.targetCumulative, p.fromCumulative).level
    }
    levelRef.current = next
  }, [resetToken, pillars])

  useEffect(() => {
    if (!flashId) return
    const t = window.setTimeout(() => setFlashId(null), 900)
    return () => window.clearTimeout(t)
  }, [flashId])

  const pillarChips = useCallback((id: string) => chips[id] ?? [], [chips])

  const applyChip = useCallback(
    (pillar: ProgramInvestmentPillar, value: number) => {
      const nextTarget = clampTarget(pillar.targetCumulative + value)
      if (nextTarget === pillar.targetCumulative) return

      const beforeLevel = pillarRingDisplay(pillar.targetCumulative, pillar.fromCumulative).level
      onTargetChange(pillar.id, nextTarget)
      setChips((prev) => ({
        ...prev,
        [pillar.id]: [...(prev[pillar.id] ?? []), value],
      }))

      const afterLevel = pillarRingDisplay(nextTarget, pillar.fromCumulative).level
      if (afterLevel > beforeLevel) setFlashId(pillar.id)
    },
    [onTargetChange],
  )

  const undoPillar = useCallback(
    (pillar: ProgramInvestmentPillar) => {
      const list = chips[pillar.id] ?? []
      if (list.length === 0) return
      const last = list[list.length - 1]
      onTargetChange(pillar.id, clampTarget(pillar.targetCumulative - last))
      setChips((prev) => ({
        ...prev,
        [pillar.id]: list.slice(0, -1),
      }))
    },
    [chips, onTargetChange],
  )

  const canInvest = useCallback(
    (pillar: ProgramInvestmentPillar, amount: number) => {
      const nextTarget = clampTarget(pillar.targetCumulative + amount)
      if (nextTarget === pillar.targetCumulative) return false
      return bankAmount >= amount
    },
    [bankAmount],
  )

  const canWithdraw = useCallback((pillar: ProgramInvestmentPillar, amount: number) => {
    return pillar.targetCumulative - amount >= 0
  }, [])

  const bankDisplay = Math.max(0, Math.round(bankAmount))

  return (
    <div className="pi-booster-root">
      <div className="pi-booster-bank">
        <div className="pi-booster-bank-label">Booster bank</div>
        <div className="pi-booster-bank-amount">{bankDisplay.toLocaleString()}</div>
        <div className="pi-booster-bank-sub">
          PP available to commit
          {netCredited != null ? (
            <>
              {' '}
              · <b>{netCredited > 0 ? `+${netCredited}` : netCredited}</b> net credited this cycle
            </>
          ) : null}
        </div>
      </div>

      <div className="pi-booster-cards">
        {pillars.map((pillar) => {
          const ring = pillarRingDisplay(pillar.targetCumulative, pillar.fromCumulative)
          const ringColor = ring.deficit ? 'var(--pi-coral)' : pillar.accent
          const list = pillarChips(pillar.id)
          const visible = list.slice(-12)

          return (
            <div
              key={pillar.id}
              className={`pi-booster-card${ring.deficit ? ' deficit' : ''}${flashId === pillar.id ? ' level-up' : ''}`}
              style={
                {
                  '--pi-accent': pillar.accent,
                  '--pi-accent-dim': pillar.accentDim,
                } as React.CSSProperties
              }
            >
              <div className="pi-booster-card-header">
                <div className="pi-booster-badge">{pillar.badge}</div>
                <div className="pi-booster-card-title">{pillar.label}</div>
              </div>

              <div className="pi-booster-ring-wrap">
                <div
                  className="pi-booster-ring"
                  style={{
                    background: `conic-gradient(${ringColor} ${ring.pct}%, var(--pi-bg-raised) ${ring.pct}%)`,
                  }}
                >
                  <div className="pi-booster-ring-inner">
                    <span className="pi-booster-ring-sub">Level</span>
                    <span className="pi-booster-ring-level">{ring.level}</span>
                  </div>
                </div>
              </div>

              <div className={`pi-booster-progress-text${ring.deficit ? ' deficit-text' : ''}`}>
                {ring.deficit ? (
                  <>
                    <span>−{pillar.fromCumulative - pillar.targetCumulative}</span> PP below current program
                  </>
                ) : ring.level >= 10 ? (
                  'Max level'
                ) : (
                  <>
                    <span>{ring.progress}</span> / {ring.required} PP to level <span>{ring.nextLevel}</span>
                  </>
                )}
              </div>

              <div className="pi-booster-chip-tray">
                {visible.map((v, i) => (
                  <div
                    key={`${pillar.id}-${list.length - visible.length + i}`}
                    className={`pi-booster-tray-chip${v < 0 ? ' negative' : ''}`}
                  >
                    {v}
                  </div>
                ))}
                {list.length > 12 ? (
                  <div className="pi-booster-tray-more">+{list.length - 12}</div>
                ) : null}
              </div>

              <div className="pi-booster-chip-divider">
                <div className="pi-booster-divider-line" />
                <div className="pi-booster-divider-label">Invest</div>
                <div className="pi-booster-divider-line" />
              </div>
              <div className="pi-booster-chip-buttons">
                {PILLAR_CHIP_VALUES.map((v) => (
                  <button
                    key={`inv-${v}`}
                    type="button"
                    className={`pi-booster-chip pi-booster-chip-${v}`}
                    disabled={!canInvest(pillar, v)}
                    onClick={() => applyChip(pillar, v)}
                  >
                    {v}
                  </button>
                ))}
                <button
                  type="button"
                  className="pi-booster-undo"
                  disabled={list.length === 0}
                  onClick={() => undoPillar(pillar)}
                >
                  Undo
                </button>
              </div>

              <div className="pi-booster-chip-divider">
                <div className="pi-booster-divider-line" />
                <div className="pi-booster-divider-label" style={{ color: 'var(--pi-coral)' }}>
                  Withdraw
                </div>
                <div className="pi-booster-divider-line" />
              </div>
              <div className="pi-booster-chip-buttons">
                {PILLAR_CHIP_VALUES.map((v) => (
                  <button
                    key={`wd-${v}`}
                    type="button"
                    className={`pi-booster-chip pi-booster-chip-${v} withdraw`}
                    disabled={!canWithdraw(pillar, v)}
                    onClick={() => applyChip(pillar, -v)}
                  >
                    {v}
                  </button>
                ))}
              </div>
            </div>
          )
        })}
      </div>

      <p className="pi-booster-footnote">
        Invest PP to level up a pillar, or withdraw to pull PP back into the bank — reducing that pillar&apos;s target.
        Undo reverses the last chip. Target levels lock in on Continue.
      </p>
    </div>
  )
}
