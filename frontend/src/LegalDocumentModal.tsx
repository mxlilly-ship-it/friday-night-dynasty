import { useEffect } from 'react'
import type { LegalDocument } from './legalContent'
import './LegalDocumentModal.css'

type Props = {
  document: LegalDocument
  onClose: () => void
}

export default function LegalDocumentModal({ document, onClose }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className="legal-modal-backdrop"
      role="presentation"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="legal-modal" role="dialog" aria-modal="true" aria-labelledby="legal-modal-title">
        <div className="legal-modal-header">
          <h2 id="legal-modal-title" className="legal-modal-title">
            {document.title}
          </h2>
          <button type="button" className="legal-modal-close" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="legal-modal-body">
          <p className="legal-modal-effective">Effective Date: {document.effectiveDate}</p>
          {document.intro ? <p className="legal-modal-intro">{document.intro}</p> : null}
          {document.sections.map((section) => (
            <section key={section.title} className="legal-modal-section">
              <h3>{section.title}</h3>
              {section.paragraphs?.map((p) => (
                <p key={p}>{p}</p>
              ))}
              {section.bullets?.length ? (
                <ul>
                  {section.bullets.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              ) : null}
              {section.subBullets?.map((p) => (
                <p key={p}>{p}</p>
              ))}
            </section>
          ))}
          <p className="legal-modal-contact">
            Email:{' '}
            <a href={`mailto:${document.contactEmail}`}>{document.contactEmail}</a>
          </p>
        </div>
      </div>
    </div>
  )
}
