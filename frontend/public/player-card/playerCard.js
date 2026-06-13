/**
 * @typedef {Object} PlayerData
 * @property {string} name
 * @property {string} school
 * @property {string[]} positions
 * @property {string} classYear
 * @property {string} height
 * @property {number} weightLbs
 * @property {number} age
 * @property {number} overallRating
 * @property {{ label: string, value: number }[]} positionRatings
 * @property {Object} attributes
 * @property {Record<string, number>} attributes.physical
 * @property {Record<string, number>} attributes.mental
 * @property {Record<string, number>} attributes.offense
 * @property {Record<string, number>} attributes.defense
 * @property {Record<string, number>} attributes.kicking
 * @property {Record<string, number>} attributes.development
 * @property {Object[]} careerStats
 * @property {Object} positionFitRatings
 * @property {Record<string, number>} positionFitRatings.offense
 * @property {Record<string, number>} positionFitRatings.defense
 * @property {string} [facePhotoSrc]
 * @property {string} [teamLogoSrc]
 */

/** @type {PlayerData} */
export const ashtonAtkins = {
  name: 'Ashton Atkins',
  school: 'Martinsburg',
  positions: ['OL', 'DT'],
  classYear: 'Senior',
  height: '6\'6"',
  weightLbs: 350,
  age: 18,
  overallRating: 74,
  positionRatings: [
    { label: 'Off OL', value: 78 },
    { label: 'Def DT', value: 67 },
  ],
  attributes: {
    mental: {
      'Football IQ': 91,
      Coachability: 79,
      Composure: 78,
      Leadership: 69,
      Toughness: 57,
      Confidence: 62,
      Effort: 60,
      Discipline: 60,
    },
    offense: {
      'Pass block': 79,
      'Run block': 74,
      Catching: 68,
      Elusiveness: 69,
      Decisions: 65,
      'Break tackle': 61,
      'Route running': 59,
      Vision: 55,
      'Ball security': 54,
    },
    defense: {
      Coverage: 67,
      Blitz: 69,
      Tackling: 68,
      'Run defense': 65,
      'Block shed': 60,
      'Pass rush': 63,
      Pursuit: 56,
    },
    physical: {
      Acceleration: 84,
      Strength: 81,
      Balance: 81,
      Agility: 78,
      Stamina: 63,
      Frame: 65,
      Jumping: 54,
      Speed: 53,
      Injury: 57,
    },
    kicking: {
      'Kick power': 73,
      'Kick accuracy': 65,
    },
    development: {
      Potential: 71,
      Consistency: 79,
      'Growth rate': 65,
      'Early bloomer': 58,
      'Late bloomer': 56,
      'Peak age': 15,
      'Class year': 12,
    },
  },
  careerStats: [
    { label: "Fr · '23", gp: 8, tackles: 14, tfl: 2.0, sacks: 0.5, ff: 0, blk: null, ovr: 62, inProgress: false },
    { label: "So · '24", gp: 11, tackles: 22, tfl: 4.5, sacks: 1.5, ff: 1, blk: null, ovr: 68, inProgress: false },
    { label: "Jr · '25", gp: 13, tackles: 31, tfl: 7.0, sacks: 3.0, ff: 2, blk: null, ovr: 71, inProgress: false },
    {
      label: "Sr · '26",
      gp: null,
      tackles: null,
      tfl: null,
      sacks: null,
      ff: null,
      blk: null,
      ovr: 74,
      inProgress: true,
    },
  ],
  positionFitRatings: {
    offense: { QB: 38, RB: 52, TE: 61, WR: 44, OL: 78 },
    defense: { DE: 69, DT: 67, LB: 58, S: 51, CB: 43 },
  },
}

const OFFENSE_POS_ORDER = ['QB', 'RB', 'TE', 'WR', 'OL']
const DEFENSE_POS_ORDER = ['DE', 'DT', 'LB', 'S', 'CB']

const PHYS_HIGHLIGHT_KEYS = [
  { key: '__height__', label: 'Height' },
  { key: '__weight__', label: 'Weight' },
  { key: 'Acceleration', label: 'Accel' },
  { key: 'Strength', label: 'Strength' },
  { key: 'Agility', label: 'Agility' },
  { key: 'Balance', label: 'Balance' },
]

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/** @param {number} value */
function statBarTier(value) {
  const n = Number(value)
  if (n >= 75) return { bar: 'bar-high', val: 'val-high' }
  if (n >= 50) return { bar: 'bar-mid', val: 'val-mid' }
  return { bar: 'bar-low', val: 'val-low' }
}

/** @param {number} value */
function posChipTier(value) {
  const n = Number(value)
  if (n >= 75) return 'pv-great'
  if (n >= 65) return 'pv-good'
  if (n >= 50) return 'pv-avg'
  return 'pv-poor'
}

/** @param {Record<string, number>} attrs */
function renderStatRows(attrs) {
  if (!attrs || typeof attrs !== 'object') return ''
  return Object.entries(attrs)
    .map(([name, value]) => {
      const num = Number(value)
      const tier = statBarTier(num)
      const width = Math.max(0, Math.min(100, Math.round(num)))
      return `<div class="stat-row">
        <span class="stat-name">${escapeHtml(name)}</span>
        <div class="stat-bar-wrap"><div class="stat-bar ${tier.bar}" style="width:${width}%"></div></div>
        <span class="stat-val ${tier.val}">${escapeHtml(num)}</span>
      </div>`
    })
    .join('')
}

/** @param {string} title @param {string} titleClass @param {Record<string, number>} attrs */
function renderStatCard(title, titleClass, attrs) {
  return `<div class="stat-card">
    <div class="stat-card-title ${titleClass}">${escapeHtml(title)}</div>
    ${renderStatRows(attrs)}
  </div>`
}

/** @param {PlayerData} player */
function renderPhysicalHighlight(player) {
  const phys = player.attributes?.physical ?? {}
  return PHYS_HIGHLIGHT_KEYS.map((item, idx) => {
    let val = '—'
    if (item.key === '__height__') val = player.height || '—'
    else if (item.key === '__weight__') val = player.weightLbs != null ? String(player.weightLbs) : '—'
    else if (phys[item.key] != null) val = String(phys[item.key])
    const divider = idx > 0 ? '<div class="phys-divider"></div>' : ''
    return `${divider}<div class="phys-item"><div class="phys-val">${escapeHtml(val)}</div><div class="phys-lbl">${escapeHtml(item.label)}</div></div>`
  }).join('')
}

/** @param {string} sideLabel @param {string[]} order @param {Record<string, number>} ratings */
function renderPosGroup(sideLabel, order, ratings) {
  const chips = order
    .map((pos) => {
      const val = ratings?.[pos] ?? 0
      const cls = posChipTier(val)
      return `<div class="pos-chip"><span class="pos-chip-name">${escapeHtml(pos)}</span><span class="pos-chip-val ${cls}">${escapeHtml(Math.round(val))}</span></div>`
    })
    .join('')
  return `<div class="pos-group">
    <span class="pos-group-label">${escapeHtml(sideLabel)}</span>
    <div class="pos-group-divider"></div>
    <div class="pos-chips">${chips}</div>
  </div>`
}

/** @param {number|null|undefined} n @param {boolean} [isDecimal] */
function formatCareerNum(n, isDecimal = false) {
  if (n == null || Number.isNaN(Number(n))) return '—'
  const num = Number(n)
  if (isDecimal) {
    return Number.isInteger(num) ? String(num) : num.toFixed(1)
  }
  return String(Math.round(num))
}

/** @param {PlayerData['careerStats']} rows */
function computeCareerHighlights(rows) {
  const completed = (rows ?? []).filter((r) => !r.inProgress)
  let bestTfl = -Infinity
  let bestSacks = -Infinity
  for (const row of completed) {
    if (row.tfl != null && Number(row.tfl) > bestTfl) bestTfl = Number(row.tfl)
    if (row.sacks != null && Number(row.sacks) > bestSacks) bestSacks = Number(row.sacks)
  }
  return { bestTfl, bestSacks }
}

/** @param {PlayerData['careerStats']} rows */
function computeCareerTotals(rows) {
  const completed = (rows ?? []).filter((r) => !r.inProgress)
  const sum = (key) =>
    completed.reduce((acc, row) => {
      const v = row[key]
      return v == null ? acc : acc + Number(v)
    }, 0)
  return {
    gp: sum('gp'),
    tackles: sum('tackles'),
    tfl: sum('tfl'),
    sacks: sum('sacks'),
    ff: sum('ff'),
    blk: sum('blk'),
  }
}

/** @param {PlayerData['careerStats']} rows */
function renderCareerTable(rows) {
  const list = rows ?? []
  const { bestTfl, bestSacks } = computeCareerHighlights(list)
  const totals = computeCareerTotals(list)

  const bodyRows = list
    .map((row) => {
      if (row.inProgress) {
        return `<tr>
          <td>${escapeHtml(row.label)}</td>
          <td colspan="6" class="career-in-progress">Season in progress — no stats logged yet</td>
          <td>${escapeHtml(row.ovr ?? '—')}</td>
        </tr>`
      }
      const tflCls = row.tfl != null && Number(row.tfl) === bestTfl && bestTfl >= 0 ? ' stat-hi' : ''
      const sackCls = row.sacks != null && Number(row.sacks) === bestSacks && bestSacks >= 0 ? ' stat-hi' : ''
      return `<tr>
        <td>${escapeHtml(row.label)}</td>
        <td>${formatCareerNum(row.gp)}</td>
        <td>${formatCareerNum(row.tackles)}</td>
        <td class="${tflCls.trim()}">${formatCareerNum(row.tfl, true)}</td>
        <td class="${sackCls.trim()}">${formatCareerNum(row.sacks, true)}</td>
        <td>${formatCareerNum(row.ff)}</td>
        <td>${formatCareerNum(row.blk)}</td>
        <td>${formatCareerNum(row.ovr)}</td>
      </tr>`
    })
    .join('')

  const careerRow = `<tr>
    <td>Career</td>
    <td>${formatCareerNum(totals.gp)}</td>
    <td>${formatCareerNum(totals.tackles)}</td>
    <td>${formatCareerNum(totals.tfl, true)}</td>
    <td>${formatCareerNum(totals.sacks, true)}</td>
    <td>${formatCareerNum(totals.ff)}</td>
    <td>${formatCareerNum(totals.blk)}</td>
    <td>—</td>
  </tr>`

  return `<div class="career-section">
    <div class="career-title">Career stats</div>
    <table class="career-table">
      <thead>
        <tr>
          <th style="width:14%">Year</th>
          <th style="width:11%">GP</th>
          <th style="width:13%">Tackles</th>
          <th style="width:11%">TFL</th>
          <th style="width:11%">Sacks</th>
          <th style="width:10%">FF</th>
          <th style="width:10%">Blk</th>
          <th style="width:10%">OVR</th>
        </tr>
      </thead>
      <tbody>${bodyRows}${careerRow}</tbody>
    </table>
  </div>`
}

function setupUpload(input, img, placeholder, presetSrc) {
  if (!input || !img) return
  if (presetSrc) {
    img.src = presetSrc
    img.style.display = 'block'
    if (placeholder) placeholder.style.display = 'none'
  }
  input.addEventListener('change', (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      img.src = String(ev.target?.result ?? '')
      img.style.display = 'block'
      if (placeholder) placeholder.style.display = 'none'
    }
    reader.readAsDataURL(file)
  })
}

/**
 * Render a player card into a container element or by element id.
 * @param {PlayerData} playerData
 * @param {string | HTMLElement} containerIdOrElement
 */
export function renderPlayerCard(playerData, containerIdOrElement) {
  const container =
    typeof containerIdOrElement === 'string'
      ? document.getElementById(containerIdOrElement)
      : containerIdOrElement
  if (!container) {
    throw new Error('renderPlayerCard: container not found')
  }

  const uid = `pc-${Math.random().toString(36).slice(2, 9)}`
  const attrs = playerData.attributes ?? {}
  const posPill = (playerData.positions ?? []).join(' / ')
  const subRatings = (playerData.positionRatings ?? [])
    .map(
      (r) =>
        `<div class="sub-rat"><div class="sub-rat-val">${escapeHtml(Math.round(Number(r.value)))}</div><div class="sub-rat-lbl">${escapeHtml(r.label)}</div></div>`,
    )
    .join('')

  const faceImgStyle = playerData.facePhotoSrc ? 'block' : 'none'
  const facePhStyle = playerData.facePhotoSrc ? 'none' : 'flex'
  const logoImgStyle = playerData.teamLogoSrc ? 'block' : 'none'
  const logoPhStyle = playerData.teamLogoSrc ? 'none' : 'flex'

  container.innerHTML = `<div class="pc-root" role="region" aria-label="Player card for ${escapeHtml(playerData.name)}">
    <div class="pc-header">
      <div class="pc-face" title="Click to upload player photo">
        <div class="pc-face-placeholder" id="${uid}-face-ph" style="display:${facePhStyle}">
          <i class="ti ti-user" aria-hidden="true"></i>
          <span>Tap to add photo</span>
        </div>
        <img id="${uid}-face-img" alt="Player photo" style="display:${faceImgStyle}" src="${escapeHtml(playerData.facePhotoSrc ?? '')}">
        <input type="file" accept="image/*" id="${uid}-face-upload" aria-label="Upload player photo">
      </div>
      <div class="pc-identity">
        <p class="pc-name">${escapeHtml(playerData.name)}</p>
        <p class="pc-meta">${escapeHtml(playerData.height)} &nbsp;·&nbsp; ${escapeHtml(playerData.weightLbs)} lb &nbsp;·&nbsp; Age ${escapeHtml(playerData.age)}</p>
        <div class="pc-pills">
          ${posPill ? `<span class="pill pill-pos">${escapeHtml(posPill)}</span>` : ''}
          <span class="pill pill-team">${escapeHtml(playerData.school)}</span>
          <span class="pill pill-year">${escapeHtml(playerData.classYear)}</span>
        </div>
      </div>
      <div class="pc-right">
        <div class="pc-logo-zone" title="Click to upload team logo">
          <div class="pc-logo-placeholder" id="${uid}-logo-ph" style="display:${logoPhStyle}">
            <i class="ti ti-shield" aria-hidden="true"></i>
            <span>Logo</span>
          </div>
          <img id="${uid}-logo-img" alt="Team logo" style="display:${logoImgStyle}" src="${escapeHtml(playerData.teamLogoSrc ?? '')}">
          <input type="file" accept="image/*" id="${uid}-logo-upload" aria-label="Upload team logo">
        </div>
        <div>
          <div class="pc-ovr-block">
            <div class="pc-ovr-label">OVR</div>
            <div class="pc-ovr-num">${escapeHtml(Math.round(Number(playerData.overallRating)))}</div>
          </div>
          <div class="pc-sub-ratings">${subRatings}</div>
        </div>
      </div>
    </div>
    <div class="pc-phys-highlight">${renderPhysicalHighlight(playerData)}</div>
    <div class="pc-grid">
      ${renderStatCard('Mental', 'title-ment', attrs.mental ?? {})}
      ${renderStatCard('Offense', 'title-off', attrs.offense ?? {})}
      ${renderStatCard('Defense', 'title-def', attrs.defense ?? {})}
    </div>
    <div class="pc-grid-bottom">
      ${renderStatCard('Physical', 'title-phys', attrs.physical ?? {})}
      ${renderStatCard('Kicking', 'title-kick', attrs.kicking ?? {})}
      ${renderStatCard('Development', 'title-dev', attrs.development ?? {})}
    </div>
    <div class="pos-ratings-section">
      <div class="pos-ratings-title">Position ratings</div>
      ${renderPosGroup('Off', OFFENSE_POS_ORDER, playerData.positionFitRatings?.offense ?? {})}
      ${renderPosGroup('Def', DEFENSE_POS_ORDER, playerData.positionFitRatings?.defense ?? {})}
    </div>
    ${renderCareerTable(playerData.careerStats ?? [])}
  </div>`

  setupUpload(
    document.getElementById(`${uid}-face-upload`),
    document.getElementById(`${uid}-face-img`),
    document.getElementById(`${uid}-face-ph`),
    playerData.facePhotoSrc,
  )
  setupUpload(
    document.getElementById(`${uid}-logo-upload`),
    document.getElementById(`${uid}-logo-img`),
    document.getElementById(`${uid}-logo-ph`),
    playerData.teamLogoSrc,
  )
}
