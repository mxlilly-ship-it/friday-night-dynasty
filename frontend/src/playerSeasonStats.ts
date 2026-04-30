export type PlayerStatRow = {
  playerName: string
  teamName: string
  position: string
  passYds: number
  passTd: number
  comp: number
  att: number
  intThrown: number
  rushYds: number
  rushTd: number
  rec: number
  recYds: number
  recTd: number
  tackles: number
  sacks: number
  tfl: number
  interceptions: number
}

export function buildPlayerStatRows(state: any): PlayerStatRow[] {
  const rows = new Map<string, PlayerStatRow>()
  const rosterPos = new Map<string, string>()
  for (const t of state?.teams ?? []) {
    const teamName = String(t?.name ?? '')
    for (const p of t?.roster ?? []) {
      const name = String(p?.name ?? '')
      if (!teamName || !name) continue
      const key = `${teamName}::${name}`
      rosterPos.set(key, String(p?.position ?? '—'))
    }
  }

  const absorb = (ps: any[]) => {
    for (const s of ps ?? []) {
      const playerName = String(s?.player_name ?? '')
      const teamName = String(s?.team_name ?? '')
      if (!playerName || !teamName) continue
      const key = `${teamName}::${playerName}`
      if (!rows.has(key)) {
        rows.set(key, {
          playerName,
          teamName,
          position: rosterPos.get(key) ?? '—',
          passYds: 0,
          passTd: 0,
          comp: 0,
          att: 0,
          intThrown: 0,
          rushYds: 0,
          rushTd: 0,
          rec: 0,
          recYds: 0,
          recTd: 0,
          tackles: 0,
          sacks: 0,
          tfl: 0,
          interceptions: 0,
        })
      }
      const r = rows.get(key)!
      r.passYds += Number(s?.pass_yds ?? 0)
      r.passTd += Number(s?.pass_td ?? 0)
      r.comp += Number(s?.comp ?? 0)
      r.att += Number(s?.att ?? 0)
      r.intThrown += Number(s?.int_thrown ?? 0)
      r.rushYds += Number(s?.rush_yds ?? 0)
      r.rushTd += Number(s?.rush_td ?? 0)
      r.rec += Number(s?.rec ?? 0)
      r.recYds += Number(s?.rec_yds ?? 0)
      r.recTd += Number(s?.rec_td ?? 0)
      r.tackles += Number(s?.tackles ?? 0)
      r.sacks += Number(s?.sacks ?? 0)
      r.tfl += Number(s?.tfl ?? 0)
      r.interceptions += Number(s?.interceptions ?? 0)
    }
  }

  for (const wkRes of state?.week_results ?? []) {
    for (const g of wkRes ?? []) {
      if (!g?.played) continue
      absorb(g?.player_stats ?? [])
    }
  }
  for (const s of state?.preseason_scrimmages ?? []) absorb(s?.player_stats ?? [])

  return Array.from(rows.values())
}
