import { useEffect } from 'react'
import TeamHelmet from './TeamHelmet'
import TeamJersey from './TeamJersey'
import TeamLogo from './TeamLogo'
import TeamStadium from './TeamStadium'
import type { PregamePreviewData } from './pregamePreviewData'
import './PregamePreviewModal.css'

type Props = {
  data: PregamePreviewData
  apiBase: string
  headers: Record<string, string>
  logoVersion: number
  stadiumVersion: number
  helmetVersion: number
  jerseyVersion: number
  onClose: () => void
}

function StatColumn({
  teamName,
  side,
  stats,
}: {
  teamName: string
  side: 'home' | 'away'
  stats: PregamePreviewData['homeStats']
}) {
  return (
    <div className="pgprev-sc">
      <div className="pgprev-sh">
        <div className={`pgprev-dot pgprev-dot--${side}`} />
        <span className="pgprev-shn">{teamName}</span>
      </div>
      {stats.map((row) => (
        <div key={row.label} className="pgprev-sr">
          <span className="pgprev-sk">{row.label}</span>
          <div className="pgprev-sb">
            <div className={`pgprev-sf pgprev-sf--${side}`} style={{ width: `${row.barPct}%` }} />
          </div>
          <span className={`pgprev-sv pgprev-sv--${side}`}>{row.value}</span>
        </div>
      ))}
    </div>
  )
}

function PlayerColumn({
  teamName,
  side,
  players,
}: {
  teamName: string
  side: 'home' | 'away'
  players: PregamePreviewData['homePlayers']
}) {
  return (
    <div className="pgprev-pc">
      <div className="pgprev-ph-head">
        <div className={`pgprev-dot pgprev-dot--${side}`} />
        <span className="pgprev-phn">{teamName}</span>
      </div>
      {players.map((p) => (
        <div key={p.name} className="pgprev-pr">
          <div className={`pgprev-pav pgprev-pav--${side}`}>{p.initials}</div>
          <div className="pgprev-pin">
            <div className="pgprev-pn">{p.name}</div>
            <div className="pgprev-pp">{p.positionLine}</div>
          </div>
          <div className="pgprev-ps">
            <strong className={`pgprev-ps-main pgprev-ps-main--${side}`}>{p.primaryStat}</strong>
            <span>{p.secondaryStat}</span>
          </div>
        </div>
      ))}
    </div>
  )
}

export default function PregamePreviewModal({
  data,
  apiBase,
  headers,
  logoVersion,
  stadiumVersion,
  helmetVersion,
  jerseyVersion,
  onClose,
}: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className="pgprev-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Pregame preview"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="pgprev-card">
        <button type="button" className="pgprev-close" onClick={onClose} aria-label="Close preview">
          ×
        </button>

        <div className="pgprev-banner">
          <div className="pgprev-eyebrow">
            <span className="pgprev-ey-dot" />
            Varsity Football · Pregame Preview
          </div>
          <div className="pgprev-matchup">
            <div className="pgprev-team">
              <div className="pgprev-crest pgprev-crest--home">
                <TeamLogo
                  apiBase={apiBase}
                  headers={headers}
                  teamName={data.homeTeam}
                  logoVersion={logoVersion}
                  size={52}
                />
              </div>
              <span className="pgprev-tname">{data.homeDisplay}</span>
              <span className="pgprev-trec">
                {data.homeRecord} · Home
              </span>
            </div>
            <div className="pgprev-vs">vs</div>
            <div className="pgprev-team">
              <div className="pgprev-crest pgprev-crest--away">
                <TeamLogo
                  apiBase={apiBase}
                  headers={headers}
                  teamName={data.awayTeam}
                  logoVersion={logoVersion}
                  size={52}
                />
              </div>
              <span className="pgprev-tname">{data.awayDisplay}</span>
              <span className="pgprev-trec">
                {data.awayRecord} · Away
              </span>
            </div>
          </div>
          <div className="pgprev-meta">
            <span className="pgprev-mi">📅 {data.meta.dateLabel}</span>
            <span className="pgprev-mi">🕖 {data.meta.timeLabel}</span>
            <span className="pgprev-mi">📍 {data.meta.venue}</span>
            <span className="pgprev-mi">🏆 {data.meta.gameType}</span>
          </div>
        </div>

        <div className="pgprev-sec">
          <div className="pgprev-slabel">🎙 From the Press Box</div>
          <div className="pgprev-rep">
            <div className="pgprev-rep-av" aria-hidden="true">
              🎙
            </div>
            <div>
              <div className="pgprev-rep-by">
                {data.reporter.name} · <strong>{data.reporter.title}</strong>
              </div>
              <div className="pgprev-rep-txt">
                <span className="pgprev-qm">&ldquo;</span>
                {data.reporter.quote}
              </div>
            </div>
          </div>
        </div>

        <div className="pgprev-div" />

        <div className="pgprev-sec">
          <div className="pgprev-slabel">🏟 Venue</div>
          <div className="pgprev-stad-card">
            <div className="pgprev-stad-img">
              <TeamStadium
                apiBase={apiBase}
                headers={headers}
                teamName={data.homeTeam}
                stadiumVersion={stadiumVersion}
                className="pgprev-stad-photo"
              />
            </div>
            <div className="pgprev-stad-foot">
              <div>
                <div className="pgprev-stad-name">{data.venue.stadiumName}</div>
                <div className="pgprev-stad-sub">{data.venue.surfaceLine}</div>
              </div>
              {data.venue.showHomeAdvantage ? <div className="pgprev-stad-badge">Home Advantage</div> : null}
            </div>
          </div>
        </div>

        <div className="pgprev-div" />

        <div className="pgprev-sec">
          <div className="pgprev-slabel">📊 Season Stats</div>
          <div className="pgprev-sg">
            <StatColumn teamName={data.homeDisplay} side="home" stats={data.homeStats} />
            <StatColumn teamName={data.awayDisplay} side="away" stats={data.awayStats} />
          </div>
        </div>

        <div className="pgprev-div" />

        <div className="pgprev-sec">
          <div className="pgprev-slabel">👕 Uniforms &amp; Helmets</div>
          <div className="pgprev-ug">
            {data.uniforms.map((u) => (
              <div key={`${u.teamName}-${u.kind}`} className="pgprev-uc">
                <div className="pgprev-ui">
                  {u.kind === 'helmet' ? (
                    <TeamHelmet
                      apiBase={apiBase}
                      headers={headers}
                      teamName={u.teamName}
                      helmetVersion={helmetVersion}
                      className="pgprev-uniform-img"
                    />
                  ) : (
                    <TeamJersey
                      apiBase={apiBase}
                      headers={headers}
                      teamName={u.teamName}
                      kind={u.kind === 'jersey-home' ? 'home' : 'away'}
                      jerseyVersion={jerseyVersion}
                      className="pgprev-uniform-img"
                    />
                  )}
                </div>
                <div className="pgprev-uf">
                  <div className="pgprev-ut">{u.title}</div>
                  <div className="pgprev-usw">
                    {u.swatches.map((c, i) => (
                      <div key={i} className="pgprev-sw" style={{ background: c }} />
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="pgprev-div" />

        <div className="pgprev-sec pgprev-sec--players">
          <div className="pgprev-slabel">⭐ Key Players to Watch</div>
          <div className="pgprev-pg2">
            <PlayerColumn teamName={data.homeDisplay} side="home" players={data.homePlayers} />
            <PlayerColumn teamName={data.awayDisplay} side="away" players={data.awayPlayers} />
          </div>
          <div className="pgprev-ms">
            <div className="pgprev-msp">
              <div className="pgprev-msn">{data.marquee.homeName}</div>
              <div className="pgprev-msd">{data.marquee.homeDetail}</div>
              <div className="pgprev-msd">{data.marquee.homeStat}</div>
            </div>
            <div className="pgprev-msb">Marquee Matchup</div>
            <div className="pgprev-msp pgprev-msp--right">
              <div className="pgprev-msn">{data.marquee.awayName}</div>
              <div className="pgprev-msd">{data.marquee.awayDetail}</div>
              <div className="pgprev-msd">{data.marquee.awayStat}</div>
            </div>
          </div>
        </div>

        <div className="pgprev-foot">
          <span className="pgprev-fb">
            <span className="pgprev-fd" />
            Friday Night Dynasty
          </span>
          <span className="pgprev-fp">{data.footerKickoff}</span>
        </div>
      </div>
    </div>
  )
}
