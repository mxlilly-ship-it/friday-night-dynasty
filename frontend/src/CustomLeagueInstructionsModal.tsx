import { useEffect } from 'react'
import './LegalDocumentModal.css'

type Props = {
  onClose: () => void
}

const TEMPLATE_URL = `${import.meta.env.BASE_URL}templates/FND_Custom_League_Template.xlsx`

const STEPS = [
  {
    title: 'Step 1: Download the league template (recommended)',
    paragraphs: [
      'Use the Excel workbook to build your league — it matches the game’s teams.json format (schools, stadiums, rivals, community types, and playoff settings).',
    ],
    bullets: [
      <>
        Download{' '}
        <a href={TEMPLATE_URL} download="FND_Custom_League_Template.xlsx">
          FND_Custom_League_Template.xlsx
        </a>
        .
      </>,
      'Fill in League Info and Teams (see Community Types sheet for school-type descriptions).',
      'Convert the workbook to .json with: python scripts/excel_league_to_json.py YourLeague.xlsx',
      'Or build a .json file manually if you prefer.',
    ],
  },
  {
    title: 'Step 2: Locate the JSON file',
    bullets: [
      'After conversion, open the folder where your .json was saved.',
      'Confirm the file ends in .json and contains a teams array.',
    ],
  },
  {
    title: 'Step 3: Upload the JSON file',
    bullets: [
      'On this Dynasty save slot screen, find Team dataset source.',
      'Click Upload .json.',
      'Select your league file.',
    ],
  },
  {
    title: 'Step 4: Complete League Creation',
    bullets: [
      'Finish creating your league as prompted.',
      'Once the league is created, go to Settings.',
    ],
  },
  {
    title: 'Step 5: Add Logos',
    bullets: [
      'In Settings, find the Logos section.',
      'Click Choose Folder.',
      'Select the folder containing your team logos.',
    ],
  },
  {
    title: 'Step 6: Match Schools to Logos',
    bullets: [
      'Assign each school to its correct logo.',
      'Ensure all teams are properly matched.',
    ],
  },
  {
    title: 'Step 7: Add Stadiums and Helmets',
    paragraphs: ['Stadium photos and helmet images follow the same process:'],
    bullets: [
      'Click the relevant section (Stadiums or Helmets).',
      'Choose the appropriate folder.',
      'Match each team with its corresponding assets.',
    ],
  },
]

const TIPS = [
  'Make sure all files are clearly named to match team names.',
  'Keep logos, stadiums, and helmets organized in separate folders.',
  'Double-check matches to ensure everything displays correctly in-game.',
]

export default function CustomLeagueInstructionsModal({ onClose }: Props) {
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
      <div className="legal-modal" role="dialog" aria-modal="true" aria-labelledby="custom-league-guide-title">
        <div className="legal-modal-header">
          <h2 id="custom-league-guide-title" className="legal-modal-title">
            How to Upload a Custom League (JSON File)
          </h2>
          <button type="button" className="legal-modal-close" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="legal-modal-body">
          <p className="legal-modal-intro">
            Follow these steps to import a custom league into the game:
          </p>
          {STEPS.map((step) => (
            <section key={step.title} className="legal-modal-section">
              <h3>{step.title}</h3>
              {step.paragraphs?.map((p) => (
                <p key={p}>{p}</p>
              ))}
              {step.bullets?.length ? (
                <ul>
                  {step.bullets.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              ) : null}
            </section>
          ))}
          <section className="legal-modal-section">
            <h3>Tips</h3>
            <ul>
              {TIPS.map((tip) => (
                <li key={tip}>{tip}</li>
              ))}
            </ul>
            <p style={{ marginTop: '0.75rem' }}>You&apos;re now ready to play with your custom league!</p>
          </section>
        </div>
      </div>
    </div>
  )
}
