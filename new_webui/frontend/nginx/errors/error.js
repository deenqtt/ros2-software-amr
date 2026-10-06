/*
 * AMR Control — error pages. Optional enhancement only: every page works
 * without this file (links reload or go to the dashboard on their own).
 *
 * A separate file, not an inline <script>, because the site's CSP is
 * script-src 'self'.
 *
 *  - Theme: the same choice the app stores (localStorage "amr.ui.theme":
 *    light | dark | system; the app's default is light). `#theme=…` in the
 *    address overrides it, which the mockup showcase uses.
 *  - "Try again" reloads with location.reload() instead of following the link.
 *  - "Go back" is shown only when there is a page to go back to.
 *  - The footer shows the local time the page was shown, so an operator can
 *    tell an administrator when it happened. Nothing about the server.
 */
(function () {
  var root = document.documentElement

  function storedTheme() {
    var fromHash = /(?:^|[#&])theme=(light|dark|system)\b/.exec(location.hash)
    if (fromHash) return fromHash[1]
    try {
      return localStorage.getItem('amr.ui.theme')
    } catch {
      return null
    }
  }

  function applyTheme() {
    var theme = storedTheme() || 'light'
    var dark =
      theme === 'dark' ||
      (theme === 'system' && window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches)
    root.classList.toggle('dark', Boolean(dark))
  }

  applyTheme()
  window.addEventListener('hashchange', applyTheme)

  document.addEventListener('DOMContentLoaded', function () {
    var reload = document.querySelectorAll('[data-action="reload"]')
    for (var i = 0; i < reload.length; i++) {
      reload[i].addEventListener('click', function (event) {
        event.preventDefault()
        window.location.reload()
      })
    }

    var back = document.querySelector('[data-action="back"]')
    if (back && window.history.length > 1) {
      back.hidden = false
      back.addEventListener('click', function () {
        window.history.back()
      })
    }

    var stamp = document.querySelector('[data-shown-at]')
    if (stamp) {
      var now = new Date()
      var pad = function (n) {
        return (n < 10 ? '0' : '') + n
      }
      stamp.textContent =
        'Shown ' +
        now.getFullYear() +
        '-' +
        pad(now.getMonth() + 1) +
        '-' +
        pad(now.getDate()) +
        ' ' +
        pad(now.getHours()) +
        ':' +
        pad(now.getMinutes()) +
        ':' +
        pad(now.getSeconds())
      stamp.hidden = false
    }
  })
})()
