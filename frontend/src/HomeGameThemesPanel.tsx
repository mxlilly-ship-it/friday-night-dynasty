import { useEffect, useMemo, useState } from 'react'
import TeamLogo from './TeamLogo'
import {
  draftToPayload,
  listUserHomeGames,
  readUserThemeDraft,
  themeById,
  themeOffersBoth,
  themeRewardSummary,
  themesByGroup,
  type HomeThemeSelection,
} from './homeGameThemes'

type Props = {
  apiBase: string
  headers: Record<string, string>
  logoVersion: number
  saveState: any
  userTeam: string
  confirmed: boolean
  confirming: boolean
  commissionerAdvances?: boolean
  onConfirm: (selections: HomeThemeSelection[]) => Promise<void>
}

export default function HomeGameThemesPanel({
  apiBase,
  headers,
  logoVersion,
  saveState,
  userTeam,
  confirmed,
  confirming,
  commissionerAdvances = false,
  onConfirm,
}: Props) {
  const homeGames = useMemo(() => listUserHomeGames(saveState, userTeam), [saveState, userTeam])
  const groupedThemes = useMemo(() => themesByGroup(), [])

  const [draft, setDraft] = useState<Record<string, HomeThemeSelection>>({})

  useEffect(() => {
    setDraft(readUserThemeDraft(saveState, userTeam))
  }, [saveState, userTeam])

  const setSlotTheme = (slotKey: string, week: number, gameIndex: number, themeId: string) => {
    if (!themeId) {
      setDraft((prev) => {
        const next = { ...prev }
        delete next[slotKey]
        return next
      })
      return
    }
    const def = themeById(themeId)
    let reward_choice: 'pp' | 'cash' | undefined
    if (def && def.pp > 0 && def.cash > 0) reward_choice = 'pp'
    else if (def && def.cash > 0) reward_choice = 'cash'
    else reward_choice = 'pp'
    setDraft((prev) => ({
      ...prev,
      [slotKey]: { week, game_index: gameIndex, theme_id: themeId, reward_choice },
    }))
  }

  const setSlotReward = (slotKey: string, choice: 'pp' | 'cash') => {
    setDraft((prev) => {
      const row = prev[slotKey]
      if (!row) return prev
      return { ...prev, [slotKey]: { ...row, reward_choice: choice } }
    })
  }

  return (
    <div className="teamhome-preseason-panelA teamhome-goals-panel teamhome-themes-panel teamhome-preseason-panelA--themes">
      <div className="teamhome-preseason-title">Home game themes</div>
      <p className="teamhome-small teamhome-goals-hint">
        Pick a theme for each home game. Win that game to earn the reward (PP or program funding). Leave blank for
        no bonus.
      </p>
      {homeGames.length === 0 ? (
        <div className="teamhome-small">No home games on this season&apos;s schedule.</div>
      ) : (
        <div className="teamhome-themes-list">
          {homeGames.map((g) => {
            const row = draft[g.slot_key]
            const themeId = row?.theme_id ?? ''
            const def = themeById(themeId)
            const dual = themeId ? themeOffersBoth(themeId) : false
            return (
              <div key={g.slot_key} className="teamhome-themes-row">
                <div className="teamhome-themes-row-head">
                  <strong>Week {g.week}</strong>
                  <span className="teamhome-name-with-logo teamhome-small" style={{ gap: 6 }}>
                    vs{' '}
                    {g.opponent && !/^bye$/i.test(g.opponent) ? (
                      <TeamLogo apiBase={apiBase} headers={headers} teamName={g.opponent} logoVersion={logoVersion} size={18} />
                    ) : null}
                    {g.opponent}
                  </span>
                </div>
                <select
                  className="teamhome-goals-select teamhome-themes-select"
                  value={themeId}
                  onChange={(e) => setSlotTheme(g.slot_key, g.week, g.game_index, e.target.value)}
                >
                  <option value="">— No theme —</option>
                  {groupedThemes.map((grp) => (
                    <optgroup key={grp.group} label={grp.label}>
                      {grp.themes.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.label} ({themeRewardSummary(t)})
                        </option>
                      ))}
                    </optgroup>
                  ))}
                </select>
                {dual && def ? (
                  <div className="teamhome-themes-reward-row">
                    <span className="teamhome-small">If you win, take:</span>
                    <select
                      className="teamhome-goals-select teamhome-themes-reward-select"
                      value={row?.reward_choice ?? 'pp'}
                      onChange={(e) => setSlotReward(g.slot_key, e.target.value as 'pp' | 'cash')}
                    >
                      <option value="pp">{def.pp} PP</option>
                      <option value="cash">${def.cash.toLocaleString()}</option>
                    </select>
                  </div>
                ) : def ? (
                  <div className="teamhome-small teamhome-themes-reward-hint">Win bonus: {themeRewardSummary(def)}</div>
                ) : null}
              </div>
            )
          })}
        </div>
      )}
      <button
        type="button"
        className="teamhome-goals-confirm"
        disabled={confirming || homeGames.length === 0}
        onClick={() => onConfirm(draftToPayload(draft))}
      >
        {confirming ? 'Confirming…' : confirmed ? 'Update themes' : 'Confirm themes'}
      </button>
      {confirmed ? (
        <p className="teamhome-small teamhome-goals-hint" style={{ marginTop: 8 }}>
          {commissionerAdvances
            ? 'Themes saved — submit your week on the League Hub. The commissioner will advance the league when everyone is ready.'
            : 'Themes saved — use Continue above to move to goal selection.'}
        </p>
      ) : null}
    </div>
  )
}
