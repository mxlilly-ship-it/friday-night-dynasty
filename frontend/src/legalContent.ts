export const SUPPORT_CONTACT_EMAIL = 'mxlilly@gmail.com'

/** Shown on purchase screens and refund support form. */
export const REFUND_POLICY_SHORT =
  'The game is free to play. Tips are optional. Past purchases: request a refund within 5 days by emailing mxlilly@gmail.com (or Help & support → Refund request).'

export const GOOGLE_ADS_DATA_URL = 'https://policies.google.com/technologies/partner-sites'

/** A sentence that includes one external link. */
export type LegalLinkParagraph = {
  before: string
  href: string
  label: string
  after?: string
}

export type LegalParagraph = string | LegalLinkParagraph

export type LegalSection = {
  title: string
  paragraphs?: LegalParagraph[]
  bullets?: string[]
  subBullets?: string[]
}

export type LegalDocument = {
  title: string
  effectiveDate: string
  intro?: string
  sections: LegalSection[]
  contactEmail: string
}

export const TERMS_OF_SERVICE: LegalDocument = {
  title: 'Terms of Service',
  effectiveDate: 'August 3, 2026',
  intro:
    'Welcome to Friday Night Dynasty (“the Game”, “we”, “our”, or “us”). By accessing or using the Game, you agree to the following Terms of Service.',
  sections: [
    {
      title: '1. Acceptance of Terms',
      paragraphs: [
        'By creating an account or using the Game, you agree to be bound by these Terms. If you do not agree, do not use the Game.',
      ],
    },
    {
      title: '2. Description of Service',
      paragraphs: [
        'Friday Night Dynasty is a browser-based football simulation game that allows users to manage teams, simulate games, and interact with game data. The Game is currently in beta, and features may change at any time.',
        'Friday Night Dynasty is free to play, including single-player dynasties and multiplayer leagues. Optional tips help support continued development. We reserve the right to modify, suspend, or discontinue the Game at any time without notice.',
      ],
    },
    {
      title: '3. User Accounts',
      paragraphs: ['To access certain features, you must create an account.', 'You agree to:'],
      bullets: [
        'Provide accurate information',
        'Maintain the security of your account',
        'Accept responsibility for all activity under your account',
      ],
      subBullets: ['We reserve the right to suspend or terminate accounts at our discretion.'],
    },
    {
      title: '4. Acceptable Use',
      paragraphs: ['You agree NOT to:'],
      bullets: [
        'Exploit bugs or glitches',
        'Attempt to hack or disrupt the Game',
        'Reverse engineer or copy the Game',
        'Use automated scripts or bots',
        'Violate any applicable laws',
      ],
      subBullets: ['Violation may result in account suspension or termination.'],
    },
    {
      title: '5. Tips, Purchases & Refunds',
      paragraphs: [
        'Friday Night Dynasty is free to play. Tips and donations are optional and do not unlock extra features unless we clearly say otherwise.',
        'If you previously purchased access, that purchase remains recognized for your account. For refund questions on a past purchase, email mxlilly@gmail.com or use Help & support within 5 days of the charge date.',
        'Approved refunds for paid purchases are processed through Stripe. Tips through third-party tip jars follow that service’s own refund rules.',
      ],
    },
    {
      title: '6. Game Data & Beta Disclaimer',
      paragraphs: ['The Game is in beta.', 'You acknowledge:'],
      bullets: [
        'Game data may be reset at any time',
        'Progress may be lost',
        'Features may change or be removed',
      ],
      subBullets: ['We are not responsible for any loss of game data.'],
    },
    {
      title: '7. Intellectual Property',
      paragraphs: [
        'All content in the Game, including but not limited to code, design, logos, and text, is owned by Friday Night Dynasty.',
        'You may not:',
      ],
      bullets: ['Copy', 'Modify', 'Distribute', 'Sell'],
      subBullets: ['any part of the Game without permission.'],
    },
    {
      title: '8. Disclaimers',
      paragraphs: [
        'The Game is provided “AS IS” and “AS AVAILABLE” without warranties of any kind.',
        'We do not guarantee:',
      ],
      bullets: [
        'The Game will be error-free',
        'The Game will be uninterrupted',
        'The Game will meet your expectations',
      ],
    },
    {
      title: '9. Limitation of Liability',
      paragraphs: ['To the fullest extent permitted by law, we are not liable for:'],
      bullets: ['Loss of data', 'Loss of profits', 'Service interruptions', 'Bugs or errors'],
    },
    {
      title: '10. Changes to Terms',
      paragraphs: [
        'We may update these Terms at any time. Continued use of the Game means you accept the updated Terms.',
      ],
    },
    {
      title: '11. Governing Law',
      paragraphs: ['These Terms are governed by the laws of the State of West Virginia, United States.'],
    },
    {
      title: '12. Contact',
      paragraphs: ['If you have questions, contact us at:'],
    },
  ],
  contactEmail: 'mxlilly@gmail.com',
}

export const PRIVACY_POLICY: LegalDocument = {
  title: 'Privacy Policy',
  effectiveDate: 'October 12, 2026',
  intro:
    'This Privacy Policy explains how Friday Night Dynasty (“we”, “our”, or “us”) collects and uses your information.',
  sections: [
    {
      title: '1. Information We Collect',
      paragraphs: ['We may collect the following:'],
      bullets: [
        'Email address (via account registration)',
        'User ID',
        'Game data (teams, saves, stats)',
        'Device and browser information',
      ],
    },
    {
      title: '2. How We Use Information',
      paragraphs: ['We use your information to:'],
      bullets: [
        'Provide and operate the Game',
        'Save your progress',
        'Improve gameplay and features',
        'Communicate with users (if applicable)',
        'Show ads and understand whether those ads are working',
      ],
    },
    {
      title: '3. Third-Party Services',
      paragraphs: [
        'We use third-party services to operate the Game and to show ads.',
        'Google Firebase handles account sign-in and stores account data.',
        'Google AdSense serves ads on this site. Third parties, including Google, may place and read cookies on your browser, or use web beacons and IP addresses, to collect information as a result of ad serving.',
        {
          before: 'See ',
          href: GOOGLE_ADS_DATA_URL,
          label: 'how Google uses data when you use our partners’ sites or apps',
          after: '.',
        },
        'These services may collect and process data according to their own privacy policies.',
      ],
    },
    {
      title: '4. Data Sharing',
      paragraphs: [
        'We do not sell your personal information.',
        'We share data with service providers only as needed to run the Game, including Google when an ad is shown on this site.',
      ],
    },
    {
      title: '5. Cookies and Tracking',
      paragraphs: [
        'We and our advertising partners may use cookies or similar technologies to:',
      ],
      bullets: [
        'Maintain sessions',
        'Improve user experience',
        'Serve ads and measure how those ads perform',
      ],
    },
    {
      title: '6. Data Security',
      paragraphs: [
        'We take reasonable measures to protect your data, but no system is completely secure.',
      ],
    },
    {
      title: '7. Children’s Privacy',
      paragraphs: [
        'The Game is not intended for children under 13.',
        'We do not knowingly collect personal information from children under 13.',
      ],
    },
    {
      title: '8. Data Retention',
      paragraphs: [
        'We retain your data as long as your account is active or as needed to provide the Game.',
      ],
    },
    {
      title: '9. Your Rights',
      paragraphs: ['You may:', 'Request access to your data', 'Request deletion of your account'],
      subBullets: ['To do so, contact us at the email below.'],
    },
    {
      title: '10. Changes to This Policy',
      paragraphs: [
        'We may update this Privacy Policy at any time. Continued use of the Game means you accept the updated policy.',
      ],
    },
    {
      title: '11. Contact',
      paragraphs: ['If you have questions, contact us at:'],
    },
  ],
  contactEmail: 'mxlilly@gmail.com',
}
