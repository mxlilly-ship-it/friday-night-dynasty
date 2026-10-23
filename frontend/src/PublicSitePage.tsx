import { useEffect } from 'react'
import { LegalDocumentBody } from './LegalDocumentModal'
import { PRIVACY_POLICY, SUPPORT_CONTACT_EMAIL } from './legalContent'
import './PublicSitePage.css'

type Page = 'about' | 'privacy'

const COPY = {
  about: {
    title: 'About — Friday Night Dynasty',
    description:
      'Friday Night Dynasty is a free browser game about coaching a high school football program through seasons, games, and the offseason.',
  },
  privacy: {
    title: 'Privacy Policy — Friday Night Dynasty',
    description:
      'How Friday Night Dynasty collects information, uses cookies, and works with Google AdSense.',
  },
} as const

export default function PublicSitePage({ page }: { page: Page }) {
  useEffect(() => {
    const meta = COPY[page]
    document.title = meta.title
    document.body.dataset.page = 'public'
    let tag = document.querySelector('meta[name="description"]')
    if (!tag) {
      tag = document.createElement('meta')
      tag.setAttribute('name', 'description')
      document.head.appendChild(tag)
    }
    tag.setAttribute('content', meta.description)
    return () => {
      delete document.body.dataset.page
    }
  }, [page])

  return (
    <div className="fnd-public">
      <header className="fnd-public-header">
        <a className="fnd-public-mark" href="/">
          Friday Night <span>Dynasty</span>
        </a>
        <nav className="fnd-public-nav" aria-label="Site">
          <a href="/" aria-current={undefined}>
            Play
          </a>
          <a href="/about" aria-current={page === 'about' ? 'page' : undefined}>
            About
          </a>
          <a href="/privacy" aria-current={page === 'privacy' ? 'page' : undefined}>
            Privacy
          </a>
        </nav>
      </header>

      <main className="fnd-public-main">
        {page === 'about' ? <AboutArticle /> : <PrivacyArticle />}
      </main>

      <footer className="fnd-public-footer">
        <p>
          Questions:{' '}
          <a href={`mailto:${SUPPORT_CONTACT_EMAIL}`}>{SUPPORT_CONTACT_EMAIL}</a>
        </p>
        <nav aria-label="Site">
          <a href="/">Play</a>
          <a href="/about">About</a>
          <a href="/privacy">Privacy</a>
        </nav>
      </footer>
    </div>
  )
}

function AboutArticle() {
  return (
    <article>
      <p className="fnd-public-kicker">The game</p>
      <h1>About Friday Night Dynasty</h1>
      <p className="fnd-public-lead">
        Friday Night Dynasty is a browser game about running a high school football program. You
        pick a school, coach the roster, play the season, and come back the next year with whoever
        is still on the team.
      </p>

      <section>
        <h2>A season</h2>
        <p>
          You start by choosing a state and a classification. Each school has a roster, a schedule,
          and a place in that state&apos;s field. The year moves one week at a time. You can play
          the games yourself or let the sim run them. Wins, losses, and point differential decide
          who reaches the playoffs.
        </p>
      </section>

      <section>
        <h2>On Friday night</h2>
        <p>
          A game is play by play. You call the offense, the defense reacts, and the scoreboard
          updates from the field. Stats follow the players: passing, rushing, tackles, and the rest
          of a normal box score. The season record is the result of those nights, not a number you
          type in.
        </p>
      </section>

      <section>
        <h2>After the season</h2>
        <p>
          Seniors leave. Younger players develop. New players arrive. Facilities, community, and
          how the last season went all sit under the program you are building. The next schedule is
          a new year with the roster you have left.
        </p>
      </section>

      <section>
        <h2>Leagues</h2>
        <p>
          You can play a dynasty on your own. You can also join a multiplayer league, where each
          coach runs one school and a commissioner advances the weeks for everyone.
        </p>
      </section>

      <section>
        <h2>A fictional sim</h2>
        <p>
          The schools in Friday Night Dynasty are a fictional setting for a game. Names, nicknames,
          towns, and rivalries are not a claim that any real school, district, or athletic
          association runs, endorses, or is connected to this game.
        </p>
      </section>

      <section>
        <h2>Free to play</h2>
        <p>
          The game is free, including single-player dynasties and multiplayer leagues. Please help
          keep it that way — an optional tip jar on the title screen helps pay for hosting. You need
          an account to save a dynasty. The privacy policy explains what the site collects and how
          advertising cookies work.
        </p>
      </section>
    </article>
  )
}

function PrivacyArticle() {
  return (
    <article className="fnd-public-legal">
      <p className="fnd-public-kicker">Your information</p>
      <h1>Privacy Policy</h1>
      <LegalDocumentBody document={PRIVACY_POLICY} />
    </article>
  )
}
