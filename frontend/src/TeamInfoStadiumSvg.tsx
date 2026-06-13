/** Day stadium illustration for Team Info page (from mockup). */
export default function TeamInfoStadiumSvg() {
  return (
    <svg viewBox="0 0 680 175" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMax meet" aria-hidden>
      <defs>
        <linearGradient id="ti-fg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#1a5c2a" />
          <stop offset="100%" stopColor="#0e3a18" />
        </linearGradient>
        <linearGradient id="ti-sg" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#1a2545" />
          <stop offset="100%" stopColor="#0d1525" />
        </linearGradient>
      </defs>
      <path
        d="M0,58 Q180,14 340,9 Q500,14 680,58 L680,118 Q500,78 340,73 Q180,78 0,118 Z"
        fill="url(#ti-sg)"
        opacity="0.8"
      />
      <ellipse cx="340" cy="132" rx="252" ry="46" fill="url(#ti-fg)" />
      <ellipse cx="340" cy="132" rx="198" ry="36" fill="none" stroke="#1f6b30" strokeWidth="1.2" />
      <ellipse cx="340" cy="132" rx="144" ry="26" fill="none" stroke="#1f6b30" strokeWidth="1.2" />
      <ellipse cx="340" cy="132" rx="88" ry="16" fill="none" stroke="#1f6b30" strokeWidth="1.2" />
      <path d="M88,132 Q170,93 252,132 Q170,171 88,132 Z" fill="#165022" opacity="0.6" />
      <path d="M592,132 Q510,93 428,132 Q510,171 592,132 Z" fill="#165022" opacity="0.6" />
      <rect x="93" y="24" width="5" height="28" rx="2" fill="#253558" />
      <rect x="582" y="24" width="5" height="28" rx="2" fill="#253558" />
      <circle cx="95" cy="22" r="5" fill="#fffacd" opacity="0.9" />
      <circle cx="584" cy="22" r="5" fill="#fffacd" opacity="0.9" />
      <circle cx="95" cy="22" r="9" fill="#fffacd" opacity="0.12" />
      <circle cx="584" cy="22" r="9" fill="#fffacd" opacity="0.12" />
    </svg>
  )
}
