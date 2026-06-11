type Props = {
  homeLabel: string
  awayLabel: string
  stadiumLine: string
  className?: string
}

/** Night-game stadium illustration (from in-season dashboard mock). */
export default function StadiumNightSvg({ homeLabel, awayLabel, stadiumLine, className = '' }: Props) {
  const home = homeLabel.slice(0, 8).toUpperCase()
  const away = awayLabel.slice(0, 8).toUpperCase()
  const footer = stadiumLine.trim().toUpperCase()
  return (
    <svg className={className} viewBox="0 0 680 185" xmlns="http://www.w3.org/2000/svg" aria-hidden>
      <defs>
        <radialGradient id="isdash-sg" cx="50%" cy="40%" r="70%">
          <stop offset="0%" stopColor="#1a2d4a" />
          <stop offset="100%" stopColor="#060c16" />
        </radialGradient>
        <radialGradient id="isdash-lr" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#ffd200" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#ffd200" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width="680" height="185" fill="url(#isdash-sg)" />
      <circle cx="60" cy="20" r="1" fill="#fff" opacity="0.6" />
      <circle cx="150" cy="12" r="0.8" fill="#fff" opacity="0.5" />
      <circle cx="240" cy="25" r="1" fill="#fff" opacity="0.7" />
      <circle cx="360" cy="10" r="0.7" fill="#fff" opacity="0.4" />
      <circle cx="470" cy="18" r="1" fill="#fff" opacity="0.6" />
      <circle cx="560" cy="8" r="0.9" fill="#fff" opacity="0.5" />
      <circle cx="630" cy="22" r="0.8" fill="#fff" opacity="0.6" />
      <rect x="40" y="66" width="600" height="18" fill="#0f1a2a" rx="2" />
      <rect x="20" y="62" width="20" height="82" fill="#0f1a2a" />
      <rect x="640" y="62" width="20" height="82" fill="#0f1a2a" />
      <rect x="28" y="27" width="4" height="44" fill="#2a3a50" />
      <rect x="648" y="27" width="4" height="44" fill="#2a3a50" />
      <rect x="24" y="25" width="12" height="5" fill="#3a4a60" />
      <rect x="644" y="25" width="12" height="5" fill="#3a4a60" />
      <ellipse cx="30" cy="25" rx="16" ry="8" fill="url(#isdash-lr)" />
      <ellipse cx="650" cy="25" rx="16" ry="8" fill="url(#isdash-lr)" />
      <path d="M20 144 L20 86 L118 86 L118 144 Z" fill="#0c1522" />
      <path d="M562 86 L660 86 L660 144 L562 144 Z" fill="#0c1522" />
      <line x1="20" y1="100" x2="118" y2="100" stroke="#162030" strokeWidth="1.5" />
      <line x1="20" y1="113" x2="118" y2="113" stroke="#162030" strokeWidth="1.5" />
      <line x1="20" y1="126" x2="118" y2="126" stroke="#162030" strokeWidth="1.5" />
      <line x1="20" y1="139" x2="118" y2="139" stroke="#162030" strokeWidth="1.5" />
      <line x1="562" y1="100" x2="660" y2="100" stroke="#162030" strokeWidth="1.5" />
      <line x1="562" y1="113" x2="660" y2="113" stroke="#162030" strokeWidth="1.5" />
      <line x1="562" y1="126" x2="660" y2="126" stroke="#162030" strokeWidth="1.5" />
      <line x1="562" y1="139" x2="660" y2="139" stroke="#162030" strokeWidth="1.5" />
      <rect x="113" y="92" width="454" height="93" fill="#1c3d1c" />
      <line x1="113" y1="107" x2="567" y2="107" stroke="#2a562a" strokeWidth="1" />
      <line x1="113" y1="121" x2="567" y2="121" stroke="#2a562a" strokeWidth="1" />
      <line x1="113" y1="135" x2="567" y2="135" stroke="#2a562a" strokeWidth="1" />
      <line x1="113" y1="149" x2="567" y2="149" stroke="#2a562a" strokeWidth="1" />
      <line x1="113" y1="163" x2="567" y2="163" stroke="#2a562a" strokeWidth="1" />
      <line x1="158" y1="92" x2="158" y2="185" stroke="#245024" strokeWidth="1.5" />
      <line x1="203" y1="92" x2="203" y2="185" stroke="#245024" strokeWidth="1.5" />
      <line x1="248" y1="92" x2="248" y2="185" stroke="#245024" strokeWidth="1.5" />
      <line x1="293" y1="92" x2="293" y2="185" stroke="#3a703a" strokeWidth="2.5" />
      <line x1="340" y1="92" x2="340" y2="185" stroke="#245024" strokeWidth="1.5" />
      <line x1="385" y1="92" x2="385" y2="185" stroke="#245024" strokeWidth="1.5" />
      <line x1="430" y1="92" x2="430" y2="185" stroke="#245024" strokeWidth="1.5" />
      <line x1="475" y1="92" x2="475" y2="185" stroke="#245024" strokeWidth="1.5" />
      <line x1="520" y1="92" x2="520" y2="185" stroke="#245024" strokeWidth="1.5" />
      <rect x="113" y="92" width="45" height="93" fill="#102010" />
      <rect x="522" y="92" width="45" height="93" fill="#102010" />
      <line x1="340" y1="64" x2="340" y2="92" stroke="#888" strokeWidth="2" />
      <line x1="326" y1="64" x2="354" y2="64" stroke="#888" strokeWidth="2" />
      <line x1="326" y1="59" x2="326" y2="64" stroke="#888" strokeWidth="1.5" />
      <line x1="354" y1="59" x2="354" y2="64" stroke="#888" strokeWidth="1.5" />
      <rect x="272" y="66" width="136" height="21" fill="#0a0f1a" rx="3" />
      <text x="290" y="81" fontFamily="monospace" fontSize="10" fill="#ffd200" fontWeight="700">
        {home}
      </text>
      <text x="388" y="81" fontFamily="monospace" fontSize="10" fill="#7aaeff" fontWeight="700">
        {away}
      </text>
      <rect x="0" y="122" width="680" height="63" fill="url(#isdash-sg)" opacity="0.6" />
      {footer ? (
        <text x="340" y="182" textAnchor="middle" fontFamily="sans-serif" fontSize="8" fill="#3a4555" letterSpacing="2">
          {footer}
        </text>
      ) : null}
    </svg>
  )
}
