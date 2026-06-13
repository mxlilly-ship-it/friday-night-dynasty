import type { TeamInfoRankingPoint } from './teamInfoData'

type Props = {
  points: TeamInfoRankingPoint[]
  className?: string
}

function buildChartGeometry(points: TeamInfoRankingPoint[]) {
  if (!points.length) return null
  const ranks = points.map((p) => p.rank)
  const minRank = Math.min(...ranks)
  const maxRank = Math.max(...ranks, minRank + 1)
  const pad = Math.max(4, Math.round((maxRank - minRank) * 0.15))
  const yMin = Math.max(1, minRank - pad)
  const yMax = maxRank + pad
  const width = 290
  const height = 68
  const left = 18
  const right = 285
  const top = 10
  const bottom = 60

  const xAt = (i: number) =>
    points.length === 1 ? (left + right) / 2 : left + (i / (points.length - 1)) * (right - left)
  const yAt = (rank: number) => {
    const t = (rank - yMin) / (yMax - yMin)
    return top + t * (bottom - top)
  }

  const coords = points.map((p, i) => ({ x: xAt(i), y: yAt(p.rank), ...p }))
  const line = coords.map((c) => `${c.x},${c.y}`).join(' ')
  const area = `${coords.map((c) => `${c.x},${c.y}`).join(' ')} ${coords[coords.length - 1].x},${bottom} ${coords[0].x},${bottom}`
  const midRank = Math.round((yMin + yMax) / 2)
  return { coords, line, area, yMin, midRank, yMax, width, height }
}

export default function TeamInfoRankingChart({ points, className = '' }: Props) {
  const geom = buildChartGeometry(points)
  if (!geom) {
    return (
      <div className={`ti-rank-empty ${className}`.trim()}>
        Ranking history will appear after completed seasons.
      </div>
    )
  }

  const labelYears = [
    geom.coords[0],
    geom.coords[Math.floor(geom.coords.length / 2)],
    geom.coords[geom.coords.length - 1],
  ].filter(Boolean)

  return (
    <div className={`ti-rank-chart ${className}`.trim()}>
      <svg viewBox={`0 0 ${geom.width} ${geom.height}`} xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none">
        <defs>
          <linearGradient id="ti-rg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#a8b4c0" stopOpacity="0.28" />
            <stop offset="100%" stopColor="#a8b4c0" stopOpacity="0" />
          </linearGradient>
        </defs>
        <text x="2" y="12" fontSize="7" fill="#555a6e" fontFamily="Rajdhani, sans-serif">
          #{geom.yMin}
        </text>
        <text x="2" y="36" fontSize="7" fill="#555a6e" fontFamily="Rajdhani, sans-serif">
          #{geom.midRank}
        </text>
        <text x="2" y="62" fontSize="7" fill="#555a6e" fontFamily="Rajdhani, sans-serif">
          #{geom.yMax}
        </text>
        <line x1="18" y1="10" x2="285" y2="10" stroke="#35394a" strokeWidth="0.5" />
        <line x1="18" y1="34" x2="285" y2="34" stroke="#35394a" strokeWidth="0.5" />
        <line x1="18" y1="60" x2="285" y2="60" stroke="#35394a" strokeWidth="0.5" />
        <polygon points={geom.area} fill="url(#ti-rg)" />
        <polyline
          points={geom.line}
          fill="none"
          stroke="#a8b4c0"
          strokeWidth="1.8"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        {geom.coords.map((c, idx) => (
          <circle
            key={c.year}
            cx={c.x}
            cy={c.y}
            r={idx === geom.coords.length - 1 ? 3 : 2}
            fill="#a8b4c0"
          />
        ))}
        {labelYears.map((c, i) => (
          <text
            key={`${c.year}-${i}`}
            x={c.x}
            y="68"
            fontSize="7"
            fill="#555a6e"
            fontFamily="Rajdhani, sans-serif"
            textAnchor={i === labelYears.length - 1 ? 'end' : i === 0 ? 'start' : 'middle'}
          >
            {c.year}
          </text>
        ))}
      </svg>
    </div>
  )
}
