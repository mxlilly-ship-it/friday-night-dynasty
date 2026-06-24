/** Public-folder screenshots shown on the title screen gallery. */
export const GAME_SCREENSHOTS: { file: string; label: string }[] = [
  { file: 'screenshot-01.png', label: 'Gameplay 1' },
  { file: 'screenshot-02.png', label: 'Gameplay 2' },
  { file: 'screenshot-03.png', label: 'Gameplay 3' },
  { file: 'screenshot-04.png', label: 'Gameplay 4' },
  { file: 'screenshot-05.png', label: 'Gameplay 5' },
  { file: 'screenshot-06.png', label: 'Gameplay 6' },
  { file: 'screenshot-07.png', label: 'Gameplay 7' },
  { file: 'screenshot-08.png', label: 'Gameplay 8' },
  { file: 'screenshot-09.png', label: 'Gameplay 9' },
  { file: 'screenshot-10.png', label: 'Gameplay 10' },
  { file: 'screenshot-11.png', label: 'Gameplay 11' },
  { file: 'screenshot-12.png', label: 'Gameplay 12' },
  { file: 'screenshot-13.png', label: 'Gameplay 13' },
  { file: 'screenshot-14.png', label: 'Gameplay 14' },
  { file: 'screenshot-15.png', label: 'Gameplay 15' },
  { file: 'screenshot-16.png', label: 'Gameplay 16' },
  { file: 'screenshot-17.png', label: 'Gameplay 17' },
  { file: 'screenshot-18.png', label: 'Gameplay 18' },
  { file: 'screenshot-19.png', label: 'Gameplay 19' },
  { file: 'screenshot-20.png', label: 'Gameplay 20' },
]

export function screenshotPublicUrl(file: string): string {
  const base = String(import.meta.env.BASE_URL || '/')
  const root = base.endsWith('/') ? base : `${base}/`
  return `${root}screenshots/${file}`
}
