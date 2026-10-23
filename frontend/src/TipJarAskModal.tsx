import { useEffect } from 'react'
import './SupportContactModal.css'

type Props = {
  open: boolean
  onClose: () => void
  onOpenTipJar: () => void
}

export default function TipJarAskModal({ open, onClose, onOpenTipJar }: Props) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  return (
    <div
      className="fnd-support-backdrop"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="fnd-support-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="fnd-tip-ask-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="fnd-support-header">
          <h2 id="fnd-tip-ask-title">Please help keep the game free</h2>
          <button type="button" className="fnd-support-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <div className="fnd-support-body">
          <p className="fnd-support-intro">
            Friday Night Dynasty is free to play. Tips pay for hosting so it can stay that way.
            If you can chip in, the tip jar is the best way to help.
          </p>
        </div>
        <div className="fnd-support-footer">
          <button type="button" className="fnd-back" onClick={onClose}>
            Not now
          </button>
          <button type="button" className="fnd-title-btn fnd-support-submit" onClick={onOpenTipJar}>
            Open tip jar
          </button>
        </div>
      </div>
    </div>
  )
}
