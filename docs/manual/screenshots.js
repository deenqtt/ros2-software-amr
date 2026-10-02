// Screenshots of every web UI screen, for docs/manual/manual.html.
//
// Read-only: nothing here presses a control that sends anything to a robot.
// Needs the backend (:3002), the web UI (:3100) and — for live pictures — the
// robot or simulator online. Run:
//
//   cd docs/manual
//   npm i --no-save playwright@1.63.0      # first time only
//   node screenshots.js                    # all screens
//   node screenshots.js 01,04,05           # only these
//
// Then rebuild the PDF with ./build_pdf.sh.
const { chromium } = require('playwright')
const fs = require('fs')
const path = require('path')

const BASE = process.env.AMR_UI_URL || 'http://localhost:3100'
const OUT = path.resolve(__dirname, '../images/web-ui')
// Ids of the robot, map and mission shown in the manual. Override per site.
const ROBOT = process.env.AMR_ROBOT || '7fc87960-8c98-4d98-8a83-a4401d6bef0a'
const ROBOT_OFFLINE = process.env.AMR_ROBOT_OFFLINE || 'e10844cd-11ee-45b1-af20-3648c5ce4356'
const MAP = process.env.AMR_MAP || '95d0c109-f2af-47c1-96a5-f6b8a14eaee2'
const MISSION = process.env.AMR_MISSION || '32408d5c-7780-4833-8d50-49331b0373c7'

const WIDTH = 1440
const MIN_HEIGHT = 900
const MAX_HEIGHT = 2400
const only = process.argv[2] ? new Set(process.argv[2].split(',')) : null

fs.mkdirSync(OUT, { recursive: true })

async function contentHeight(page) {
  // The app scrolls inside <main>, not the body: a "full page" shot would stop
  // at the viewport, so the viewport is grown to the content instead.
  return page.evaluate(() => {
    const main = document.querySelector('main')
    const header = document.querySelector('header')
    return (main ? main.scrollHeight : document.body.scrollHeight) +
      (header ? header.getBoundingClientRect().height : 0)
  })
}

async function fitHeight(page) {
  // Twice: the live map's height follows the viewport, so the page grows once
  // the viewport does.
  for (let pass = 0; pass < 2; pass += 1) {
    const height = Math.max(MIN_HEIGHT, Math.min(MAX_HEIGHT, Math.ceil(await contentHeight(page))))
    await page.setViewportSize({ width: WIDTH, height })
    await page.waitForTimeout(600)
  }
}

async function shot(page, name, { fit = true } = {}) {
  if (only && !only.has(name.slice(0, 2))) return
  if (fit) await fitHeight(page)
  await page.screenshot({ path: path.join(OUT, `${name}.png`) })
  console.log('saved', name)
}

async function visit(page, route, settleMs = 2500) {
  await page.setViewportSize({ width: WIDTH, height: MIN_HEIGHT })
  await page.goto(BASE + route, { waitUntil: 'networkidle' })
  await page.waitForTimeout(settleMs)
}

async function waitFor(page, regex, ms = 20000) {
  // Live data: wait until the link is up, so a healthy robot is never pictured
  // as offline just because the shot was taken too early.
  try {
    await page.getByText(regex).first().waitFor({ state: 'visible', timeout: ms })
    await page.waitForTimeout(1500)
  } catch {
    console.log('warn: never saw', regex)
  }
}

async function tryClick(page, locator, label) {
  try {
    await locator.first().click({ timeout: 3000 })
    await page.waitForTimeout(800)
    return true
  } catch {
    console.log('skip (not found):', label)
    return false
  }
}

;(async () => {
  const browser = await chromium.launch()
  const context = await browser.newContext({
    viewport: { width: WIDTH, height: MIN_HEIGHT },
    deviceScaleFactor: 2,
  })
  const page = await context.newPage()

  await visit(page, '/dashboard', 2000)
  await waitFor(page, /[1-9] online/)
  await shot(page, '01-dashboard')

  await visit(page, '/robot')
  await shot(page, '02-robots')
  if (await tryClick(page, page.getByRole('button', { name: /add robot/i }), 'add robot')) {
    await shot(page, '03-robots-add-dialog', { fit: false })
    await page.keyboard.press('Escape')
  }

  await visit(page, `/robot/${ROBOT}/nav`, 3000)
  await waitFor(page, /^Online$/)
  await page.waitForTimeout(4000)
  await shot(page, '04-robot-navigation')
  if (await tryClick(page, page.getByRole('button', { name: /^costmap$/i }), 'costmap layer')) {
    await page.waitForTimeout(3000)
    await waitFor(page, /^Online$/)
    await shot(page, '05-robot-navigation-costmap')
    await tryClick(page, page.getByRole('button', { name: /^costmap$/i }), 'costmap off')
  }
  await page.setViewportSize({ width: WIDTH, height: MIN_HEIGHT })
  if (await tryClick(page, page.getByRole('button', { name: /alarm/i }), 'bell')) {
    await shot(page, '06-notifications-bell', { fit: false })
    await page.keyboard.press('Escape')
  }

  await visit(page, `/robot/${ROBOT_OFFLINE}/nav`, 4000)
  await shot(page, '07-robot-navigation-offline')

  await visit(page, `/robot/${ROBOT}/detail`, 3000)
  await waitFor(page, /^Online$/)
  await page.waitForTimeout(5000)
  await shot(page, '08-robot-detail')

  await visit(page, '/maps')
  await shot(page, '09-maps')
  await visit(page, `/maps/edit/${MAP}`, 4000)
  await shot(page, '10-map-editor')
  await visit(page, `/maps/survey/${ROBOT}`, 5000)
  await shot(page, '11-map-survey')

  await visit(page, '/mission')
  await shot(page, '12-missions')
  if (await tryClick(page, page.getByRole('button', { name: /new mission/i }), 'new mission')) {
    // Typed, never submitted: an example name rather than the empty-field error.
    await page.getByRole('dialog').getByRole('textbox').first().fill('Shuttle A to B')
    await page.waitForTimeout(300)
    await shot(page, '13-missions-new-dialog', { fit: false })
    await page.keyboard.press('Escape')
  }
  await visit(page, `/mission/edit/${MISSION}`, 3000)
  await shot(page, '14-mission-editor')

  await visit(page, '/station', 3000)
  await shot(page, '15-stations')
  await visit(page, '/zone', 3000)
  await shot(page, '16-zones')
  await visit(page, '/alarm')
  await shot(page, '17-alarms')
  await visit(page, '/this-page-does-not-exist', 1000)
  await shot(page, '18-not-found')

  await browser.close()
})().catch((error) => {
  console.error(error)
  process.exit(1)
})
