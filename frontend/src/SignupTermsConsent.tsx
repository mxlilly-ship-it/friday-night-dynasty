import { useState } from 'react'
import LegalDocumentModal from './LegalDocumentModal'
import { PRIVACY_POLICY, TERMS_OF_SERVICE } from './legalContent'

type Props = {
  checked: boolean
  onChange: (checked: boolean) => void
}

export default function SignupTermsConsent({ checked, onChange }: Props) {
  const [openDoc, setOpenDoc] = useState<'terms' | 'privacy' | null>(null)

  return (
    <>
      <label className="fnd-terms-consent">
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
        />
        <span>
          I agree to the{' '}
          <button
            type="button"
            className="fnd-legal-link"
            onClick={(e) => {
              e.preventDefault()
              e.stopPropagation()
              setOpenDoc('terms')
            }}
          >
            Terms of Service
          </button>{' '}
          and{' '}
          <button
            type="button"
            className="fnd-legal-link"
            onClick={(e) => {
              e.preventDefault()
              e.stopPropagation()
              setOpenDoc('privacy')
            }}
          >
            Privacy Policy
          </button>
        </span>
      </label>
      {openDoc === 'terms' ? (
        <LegalDocumentModal document={TERMS_OF_SERVICE} onClose={() => setOpenDoc(null)} />
      ) : null}
      {openDoc === 'privacy' ? (
        <LegalDocumentModal document={PRIVACY_POLICY} onClose={() => setOpenDoc(null)} />
      ) : null}
    </>
  )
}
