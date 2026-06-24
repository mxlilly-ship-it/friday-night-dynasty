import { useCallback, useEffect, useState } from 'react'
import { GAME_SCREENSHOTS, screenshotPublicUrl } from './gameScreenshots'
import './ScreenshotsGallery.css'

type Props = {
  open: boolean
  onClose: () => void
}

export default function ScreenshotsGallery({ open, onClose }: Props) {
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null)

  const closeLightbox = useCallback(() => setLightboxIndex(null), [])

  const stepLightbox = useCallback(
    (delta: number) => {
      setLightboxIndex((prev) => {
        if (prev == null) return prev
        const next = (prev + delta + GAME_SCREENSHOTS.length) % GAME_SCREENSHOTS.length
        return next
      })
    },
    [],
  )

  useEffect(() => {
    if (!open) {
      setLightboxIndex(null)
      return
    }
    const onKeyDown = (ev: KeyboardEvent) => {
      if (ev.key === 'Escape') {
        if (lightboxIndex != null) closeLightbox()
        else onClose()
        return
      }
      if (lightboxIndex == null) return
      if (ev.key === 'ArrowRight') stepLightbox(1)
      if (ev.key === 'ArrowLeft') stepLightbox(-1)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [closeLightbox, lightboxIndex, onClose, open, stepLightbox])

  if (!open) return null

  const lightbox =
    lightboxIndex != null ? GAME_SCREENSHOTS[lightboxIndex] : null

  return (
    <div className="fnd-screens-root" role="dialog" aria-modal="true" aria-label="Game screenshots">
      <div className="fnd-screens-backdrop" onClick={onClose} aria-hidden="true" />
      <div className="fnd-screens-panel">
        <header className="fnd-screens-header">
          <div>
            <h2 className="fnd-screens-title">Game screenshots</h2>
            <p className="fnd-screens-sub">A look at Friday Night Dynasty in action.</p>
          </div>
          <button type="button" className="fnd-screens-close" onClick={onClose} aria-label="Close gallery">
            Close
          </button>
        </header>

        <div className="fnd-screens-grid">
          {GAME_SCREENSHOTS.map((shot, index) => (
            <button
              key={shot.file}
              type="button"
              className="fnd-screens-thumb"
              onClick={() => setLightboxIndex(index)}
            >
              <img src={screenshotPublicUrl(shot.file)} alt={shot.label} loading="lazy" />
            </button>
          ))}
        </div>
      </div>

      {lightbox ? (
        <div className="fnd-screens-lightbox" role="dialog" aria-label="Enlarged screenshot">
          <button type="button" className="fnd-screens-lightbox-close" onClick={closeLightbox} aria-label="Close image">
            ×
          </button>
          <button
            type="button"
            className="fnd-screens-lightbox-nav fnd-screens-lightbox-nav--prev"
            onClick={() => stepLightbox(-1)}
            aria-label="Previous screenshot"
          >
            ‹
          </button>
          <img
            className="fnd-screens-lightbox-img"
            src={screenshotPublicUrl(lightbox.file)}
            alt={lightbox.label}
          />
          <button
            type="button"
            className="fnd-screens-lightbox-nav fnd-screens-lightbox-nav--next"
            onClick={() => stepLightbox(1)}
            aria-label="Next screenshot"
          >
            ›
          </button>
          <div className="fnd-screens-lightbox-caption">
            {lightbox.label} · {(lightboxIndex ?? 0) + 1} / {GAME_SCREENSHOTS.length}
          </div>
        </div>
      ) : null}
    </div>
  )
}
