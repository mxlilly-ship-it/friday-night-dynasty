import TeamLogo from './TeamLogo'
import TeamStadium from './TeamStadium'
import TeamHelmet from './TeamHelmet'
import TeamJersey from './TeamJersey'
import type { JerseyKind } from './logoUtils'
import TeamInfoRankingChart from './TeamInfoRankingChart'
import { CoachProfileName } from './CoachProfileContext'
import {
  DEFAULT_UNIFORM_SLOTS,
  type TeamInfoData,
  type TeamInfoUniformSlot,
} from './teamInfoData'
import './TeamInfoPage.css'

function CameraPlaceholderIcon() {
  return (
    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
      <rect x="3" y="5" width="18" height="14" rx="2" stroke="#42475c" strokeWidth="1.5" />
      <circle cx="12" cy="12" r="3" stroke="#42475c" strokeWidth="1.5" />
      <path d="M3 17l4-4 3 3 4-5 4 6" stroke="#42475c" strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  )
}

function UniformSlot({
  slot,
  tall,
  viewTeam,
  apiBase,
  headers,
  helmetVersion,
  jerseyVersion,
}: {
  slot: TeamInfoUniformSlot
  tall?: boolean
  viewTeam: string
  apiBase: string
  headers?: Record<string, string>
  helmetVersion: number
  jerseyVersion: number
}) {
  const jerseyKind: JerseyKind | null =
    slot.id === 'home' || slot.id === 'away' || slot.id === 'alternate' ? slot.id : null

  return (
    <div className={tall ? 'ti-uni-slot ti-uni-slot--helmet' : 'ti-uni-slot ti-uni-slot--jersey'}>
      <div className={tall ? 'ti-uni-box ti-uni-box--helmet' : 'ti-uni-box ti-uni-box--jersey'}>
        {slot.id === 'helmet' ? (
          <TeamHelmet
            apiBase={apiBase}
            headers={headers}
            teamName={viewTeam}
            helmetVersion={helmetVersion}
            hidePlaceholder
          />
        ) : jerseyKind ? (
          <TeamJersey
            apiBase={apiBase}
            headers={headers}
            teamName={viewTeam}
            kind={jerseyKind}
            jerseyVersion={jerseyVersion}
            hidePlaceholder
          />
        ) : null}
        <div className="ti-uni-placeholder-inner">
          <CameraPlaceholderIcon />
          <span className="ti-uni-placeholder-text">{slot.placeholderLabel}</span>
        </div>
      </div>
      <div className="ti-uni-label">{slot.label}</div>
    </div>
  )
}

export type TeamInfoPageProps = {
  data: TeamInfoData
  viewTeam: string
  allTeamNames: string[]
  userTeam: string
  onViewTeamChange: (name: string) => void
  apiBase: string
  headers?: Record<string, string>
  logoVersion: number
  stadiumVersion: number
  helmetVersion: number
  jerseyVersion: number
  uniformSlots?: TeamInfoUniformSlot[]
  hideChromeActions?: boolean
  onContinue?: () => void
  onSettings?: () => void
  onMainMenu?: () => void
}

export default function TeamInfoPage({
  data,
  viewTeam,
  allTeamNames,
  userTeam,
  onViewTeamChange,
  apiBase,
  headers,
  logoVersion,
  stadiumVersion,
  helmetVersion,
  jerseyVersion,
  uniformSlots = DEFAULT_UNIFORM_SLOTS,
  hideChromeActions = true,
  onContinue,
  onSettings,
  onMainMenu,
}: TeamInfoPageProps) {
  const ng = data.nextGame

  return (
    <div className="ti-root">
      <header className="ti-chrome">
        <div className="ti-chrome-logo">
          <TeamLogo
            apiBase={apiBase}
            headers={headers}
            teamName={viewTeam}
            logoVersion={logoVersion}
            size={48}
            className="ti-chrome-logo-img"
          />
        </div>
        <div className="ti-chrome-team">
          <div className="ti-chrome-name">{data.teamName}</div>
          <div className="ti-chrome-nick">{data.subline}</div>
        </div>
        <div className="ti-chrome-stat">
          <span className="ti-chrome-stat-label">Record</span>
          <span className="ti-chrome-stat-val">{data.record}</span>
        </div>
        <div className="ti-chrome-stat">
          <span className="ti-chrome-stat-label">Rank</span>
          <span className="ti-chrome-stat-val ti-gold">{data.stateRankDisplay}</span>
        </div>
        <div className="ti-chrome-stat">
          <span className="ti-chrome-stat-label">Class Rank</span>
          <span className="ti-chrome-stat-val ti-gold">{data.classRankDisplay}</span>
        </div>
        {!hideChromeActions ? (
          <div className="ti-chrome-buttons">
            <button type="button" className="ti-btn ti-btn-primary" onClick={onContinue}>
              Continue
            </button>
            <button type="button" className="ti-btn ti-btn-ghost" onClick={onSettings}>
              Settings
            </button>
            <button type="button" className="ti-btn ti-btn-ghost" onClick={onMainMenu}>
              Main Menu
            </button>
          </div>
        ) : null}
      </header>

      <div className="ti-picker-bar">
        <label className="ti-picker-label" htmlFor="ti-team-select">
          View team
        </label>
        <select
          id="ti-team-select"
          className="ti-picker-select"
          value={viewTeam}
          onChange={(e) => onViewTeamChange(e.target.value)}
          disabled={allTeamNames.length < 1}
        >
          {allTeamNames.length < 1 ? (
            <option value="">—</option>
          ) : (
            allTeamNames.map((name) => (
              <option key={name} value={name}>
                {name}
                {name === userTeam ? ' (you)' : ''}
              </option>
            ))
          )}
        </select>
      </div>

      <div className="ti-body">
        <div className="ti-left-col">
          <section className="ti-panel">
            <div className="ti-sec-head">Team Info</div>
            <div className="ti-identity">
              <div className="ti-logo-area">
                <div className="ti-logo-img">
                  <TeamLogo
                    apiBase={apiBase}
                    headers={headers}
                    teamName={viewTeam}
                    logoVersion={logoVersion}
                    size={88}
                  />
                </div>
                <div className="ti-logo-hint">Team Logo</div>
              </div>
              <div className="ti-id-fields">
                <div className="ti-id-row">
                  <span className="ti-id-label">Team Name</span>
                  <span className="ti-id-val ti-em">{data.teamName}</span>
                </div>
                <div className="ti-id-row">
                  <span className="ti-id-label">Nickname</span>
                  <span className="ti-id-val ti-em">{data.nickname}</span>
                </div>
                <div className="ti-id-row">
                  <span className="ti-id-label">Current Record (Standings)</span>
                  <span className="ti-id-val ti-em">{data.record}</span>
                </div>
                <div className="ti-id-row">
                  <span className="ti-id-label">Current Rank (Statewide)</span>
                  <span className="ti-id-val ti-gold">{data.stateRankDisplay.replace('#', '')}</span>
                </div>
              </div>
              <div className="ti-id-fields">
                <div className="ti-id-row">
                  <span className="ti-id-label">Class Rank</span>
                  <span className="ti-id-val ti-gold">{data.classRankDisplay}</span>
                </div>
                <div className="ti-id-row">
                  <span className="ti-id-label">Head Coach</span>
                  <span className="ti-id-val ti-blue ti-sm">
                    <CoachProfileName mode="team" teamName={viewTeam} coachName={data.headCoach} as="span">
                      {data.headCoach}
                    </CoachProfileName>
                  </span>
                </div>
                <div className="ti-id-row">
                  <span className="ti-id-label">Classification</span>
                  <span className="ti-id-val">{data.classification}</span>
                </div>
                <div className="ti-id-row">
                  <span className="ti-id-label">Region</span>
                  <span className="ti-id-val">{data.region}</span>
                </div>
                <div className="ti-id-row">
                  <span className="ti-id-label">Rivals</span>
                  <span className="ti-id-val ti-rivals ti-sm">{data.rivals}</span>
                </div>
              </div>
            </div>
          </section>

          <section className="ti-panel">
            <div className="ti-sec-head">Program History</div>
            <div className="ti-program-stats">
              <div className="ti-ps-cell">
                <span className="ti-ps-label">Program Win–Loss (All Seasons + This Year)</span>
                <span className="ti-ps-val">{data.programRecord}</span>
              </div>
              <div className="ti-ps-cell">
                <span className="ti-ps-label">Playoff Appearances</span>
                <span className="ti-ps-val">{data.playoffAppearances}</span>
              </div>
              <div className="ti-ps-cell">
                <span className="ti-ps-label">Regional Titles</span>
                <span className="ti-ps-val">{data.regionalTitles}</span>
              </div>
              <div className="ti-ps-cell">
                <span className="ti-ps-label">State Titles</span>
                <span className={`ti-ps-val${data.stateTitlesDisplay === 'None' ? ' ti-none' : ''}`}>
                  {data.stateTitlesDisplay}
                </span>
              </div>
            </div>
          </section>

          <section className="ti-panel">
            <div className="ti-sec-head">Program Details</div>
            <div className="ti-prog-info">
              <div className="ti-pi-cell">
                <span className="ti-pi-label">Prestige</span>
                <span className="ti-pi-val">
                  <strong>{data.prestige}</strong> · {data.prestigeDetail}
                </span>
              </div>
              <div className="ti-pi-cell">
                <span className="ti-pi-label">Community Type</span>
                <span className="ti-pi-val">
                  <strong>{data.communityType}</strong>
                </span>
              </div>
              <div className="ti-pi-cell">
                <span className="ti-pi-label">Enrollment</span>
                <span className="ti-pi-val">
                  <strong>{data.enrollment}</strong>
                </span>
              </div>
            </div>
          </section>

          <section className="ti-panel">
            <div className="ti-sec-head">Program Grades</div>
            <div className="ti-grade-cards">
              {data.grades.map((g) => (
                <div key={g.label} className="ti-grade-card">
                  <div className="ti-gc-icon">{g.icon}</div>
                  <div className="ti-gc-label">{g.label}</div>
                  <div className={`ti-gc-grade ti-gc-grade--${g.letterClass}`}>{g.letter}</div>
                  <div className="ti-gc-bar">
                    <div
                      className={`ti-gc-bar-fill ti-gc-bar-fill--${g.letterClass}`}
                      style={{ width: `${Math.min(100, (g.score / g.maxScore) * 100)}%` }}
                    />
                  </div>
                  <div className="ti-gc-num">
                    {g.score} / {g.maxScore}
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="ti-panel">
            <div className="ti-sec-head">Stadium</div>
            <div className="ti-stadium-img">
              <TeamStadium
                apiBase={apiBase}
                headers={headers}
                teamName={viewTeam}
                stadiumVersion={stadiumVersion}
                className="ti-stadium-photo"
                hidePlaceholder
              />
            </div>
            <div className="ti-stadium-stats-bar">
              <div className="ti-ssb-cell">
                <span className="ti-ssb-label">Stadium Name</span>
                <span className="ti-ssb-val">{data.stadiumName}</span>
              </div>
              <div className="ti-ssb-cell">
                <span className="ti-ssb-label">Capacity</span>
                <span className="ti-ssb-val">{data.stadiumCapacity}</span>
              </div>
              <div className="ti-ssb-cell">
                <span className="ti-ssb-label">Surface</span>
                <span className="ti-ssb-val">{data.stadiumSurface}</span>
              </div>
              <div className="ti-ssb-cell">
                <span className="ti-ssb-label">Condition</span>
                <span className={`ti-ssb-val${data.stadiumConditionClass ? ' ti-good' : ''}`}>
                  {data.stadiumCondition}
                </span>
              </div>
            </div>
          </section>
        </div>

        <div className="ti-right-col">
          <section className="ti-panel">
            <div className="ti-sec-head">Next Game</div>
            <div className="ti-next-game">
              {ng ? (
                <>
                  <div className="ti-ng-row">
                    <div className="ti-ng-team">
                      <div className="ti-ng-badge">
                        <TeamLogo
                          apiBase={apiBase}
                          headers={headers}
                          teamName={ng.homeTeam}
                          logoVersion={logoVersion}
                          size={28}
                        />
                      </div>
                      <div className="ti-ng-name">{ng.homeTeam}</div>
                    </div>
                    <div className="ti-ng-vs">VS</div>
                    <div className="ti-ng-team">
                      <div className="ti-ng-badge">
                        <TeamLogo
                          apiBase={apiBase}
                          headers={headers}
                          teamName={ng.awayTeam}
                          logoVersion={logoVersion}
                          size={28}
                        />
                      </div>
                      <div className="ti-ng-name">{ng.awayTeam}</div>
                    </div>
                  </div>
                  <div className="ti-ng-meta">
                    <em>{ng.metaLine}</em>
                    {ng.location ? ` · ${ng.location}` : null}
                  </div>
                </>
              ) : (
                <div className="ti-ng-empty">No upcoming game on the schedule.</div>
              )}
            </div>
          </section>

          <section className="ti-panel">
            <div className="ti-sec-head">Key Personnel</div>
            <div className="ti-kp-grid">
              {data.keyPersonnel.map((kp) => (
                <div key={kp.role} className="ti-kp-cell">
                  <div className="ti-kp-role">{kp.role}</div>
                  <div className="ti-kp-avatar">🏈</div>
                  <div className="ti-kp-name">{kp.name}</div>
                  <div className="ti-kp-pos">{kp.positionYear}</div>
                </div>
              ))}
            </div>
          </section>

          <section className="ti-panel ti-panel--flex">
            <div className="ti-sec-head">Banner &amp; Trophy Case</div>
            <div className="ti-trophy-list">
              {data.trophies.length ? (
                data.trophies.map((tr) => (
                  <div key={tr.title} className={`ti-trophy-row ti-trophy-row--${tr.tier}`}>
                    <div className="ti-tr-icon">{tr.icon}</div>
                    <div className="ti-tr-info">
                      <div className="ti-tr-title">{tr.title}</div>
                      <div className="ti-tr-years">{tr.years}</div>
                    </div>
                    <div className="ti-tr-count">×{tr.count}</div>
                  </div>
                ))
              ) : (
                <div className="ti-trophy-empty">
                  Honours will appear here as the program wins titles and reaches the playoffs.
                </div>
              )}
            </div>
            <div className="ti-trophy-total">
              <span className="ti-tt-label">Total Honours</span>
              <span className="ti-tt-val">{data.totalHonours}</span>
            </div>
          </section>

          <section className="ti-panel">
            <div className="ti-sec-head">Statewide Ranking History</div>
            <div className="ti-rank-section">
              <TeamInfoRankingChart points={data.rankingHistory} />
            </div>
          </section>
        </div>

        <section className="ti-uniform-row ti-panel">
          <div className="ti-sec-head">Uniform &amp; Equipment</div>
          <div className="ti-uniform-display">
            {uniformSlots.map((slot, i) => (
              <UniformSlot
                key={slot.id}
                slot={slot}
                tall={i === 0}
                viewTeam={viewTeam}
                apiBase={apiBase}
                headers={headers}
                helmetVersion={helmetVersion}
                jerseyVersion={jerseyVersion}
              />
            ))}
          </div>
        </section>
      </div>
    </div>
  )
}
