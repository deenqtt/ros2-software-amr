/* Showcase only: switches the previewed page, screen size and theme. */
(function () {
  var PAGES = {
    403: {
      title: "You don't have access to this page",
      when: 'nginx refuses the address (deny rule, hidden path).',
      actions: 'Go to dashboard (/dashboard) · Go back (only if there is history)',
      status: 'No service chips: nothing is down.',
      safety: 'None needed: the control service is fine.',
    },
    404: {
      title: "This page isn't on the map",
      when: 'A file nginx serves directly is missing. App routes keep the in-app 404 (NotFoundView), whose title and drawing this copies.',
      actions: 'Go to dashboard · Go back (only if there is history)',
      status: 'No service chips.',
      safety: 'None needed.',
    },
    500: {
      title: 'Something went wrong on our side',
      when: 'The control service (backend) failed while handling the request.',
      actions: 'Try again (reload) · Go to dashboard',
      status: 'Control service: Error · Live robot data: Unavailable',
      safety: 'Robot status note: this page cannot see the robots; use the on-robot emergency stop if one must stop now.',
    },
    502: {
      title: "The control service isn't responding",
      when: 'nginx cannot reach the backend (stopped, restarting, crashed).',
      actions: 'Try again (reload) · Go to dashboard',
      status: 'Control service: Not responding · Live robot data: Unavailable',
      safety: 'Robot status note (same as 500). Never claims the robot stopped.',
    },
    503: {
      title: 'AMR Control is temporarily unavailable',
      when: 'Maintenance or start-up (e.g. a maintenance switch in nginx).',
      actions: 'Try again (reload) · Go to dashboard',
      status: 'Control service: Unavailable · Live robot data: Unavailable',
      safety: 'Robot status note (same as 500).',
    },
    504: {
      title: 'The control service took too long to respond',
      when: 'The backend did not answer within nginx’s timeout.',
      actions: 'Try again (reload) · Go to dashboard',
      status: 'Control service: Timed out · Live robot data: Unavailable',
      safety: 'Robot status note (same as 500).',
    },
  }
  var CODES = ['403', '404', '500', '502', '503', '504']

  var state = { page: '502', viewport: '1366x768', theme: 'light' }
  try {
    var saved = JSON.parse(localStorage.getItem('amr.errorMockup') || '{}')
    if (saved.page) state.page = saved.page
    if (saved.viewport) state.viewport = saved.viewport
    if (saved.theme) state.theme = saved.theme
  } catch (error) {
    /* first visit or storage blocked */
  }

  var frame = document.getElementById('frame')
  var device = document.getElementById('device')
  var stage = document.getElementById('stage')
  var single = document.getElementById('single')
  var all = document.getElementById('all')
  var viewport = document.getElementById('viewport')
  var notes = document.getElementById('notes')
  var meta = document.getElementById('single-meta')
  var openLink = document.getElementById('open-link')

  function src(code) {
    return 'pages/' + code + '.html#theme=' + state.theme
  }

  function save() {
    try {
      localStorage.setItem('amr.errorMockup', JSON.stringify(state))
    } catch (error) {
      /* not important */
    }
  }

  function applyShowcaseTheme() {
    var dark =
      state.theme === 'dark' ||
      (state.theme === 'system' && matchMedia('(prefers-color-scheme: dark)').matches)
    document.documentElement.classList.toggle('dark', dark)
  }

  function size() {
    if (state.viewport === 'fit') {
      var w = stage.clientWidth
      return [w, Math.max(560, window.innerHeight - stage.getBoundingClientRect().top - 24), w]
    }
    var parts = state.viewport.split('x')
    return [Number(parts[0]), Number(parts[1]), stage.clientWidth]
  }

  function layoutSingle() {
    var s = size()
    var w = s[0]
    var h = s[1]
    var scale = Math.min(1, s[2] / w)
    frame.style.width = w + 'px'
    frame.style.height = h + 'px'
    frame.style.transform = 'scale(' + scale + ')'
    device.style.width = Math.round(w * scale) + 'px'
    device.style.height = Math.round(h * scale) + 'px'
    var label = viewport.options[viewport.selectedIndex].text
    meta.innerHTML = ''
    var b = document.createElement('b')
    b.textContent = 'Error ' + state.page
    meta.appendChild(b)
    meta.appendChild(
      document.createTextNode(
        ' at ' + label + (scale < 1 ? ', shown at ' + Math.round(scale * 100) + '%' : ''),
      ),
    )
  }

  function renderNotes() {
    var info = PAGES[state.page]
    var rows = [
      ['Title', info.title],
      ['Shown when', info.when],
      ['Actions', info.actions],
      ['Status chips', info.status],
      ['Safety', info.safety],
      ['Never shown', 'Server or nginx version, host names, IPs, ports, container or upstream names, paths, stack traces.'],
    ]
    notes.innerHTML = ''
    rows.forEach(function (row) {
      var dt = document.createElement('dt')
      dt.textContent = row[0]
      var dd = document.createElement('dd')
      dd.textContent = row[1]
      notes.appendChild(dt)
      notes.appendChild(dd)
    })
  }

  function renderAll() {
    all.innerHTML = ''
    CODES.forEach(function (code) {
      var card = document.createElement('button')
      card.type = 'button'
      card.className = 'sc-card'
      card.setAttribute('aria-label', 'Error ' + code + ': ' + PAGES[code].title + '. Open larger.')
      var thumb = document.createElement('span')
      thumb.className = 'sc-thumb'
      thumb.style.display = 'block'
      var iframe = document.createElement('iframe')
      iframe.src = src(code)
      iframe.title = 'Error ' + code
      iframe.tabIndex = -1
      iframe.setAttribute('aria-hidden', 'true')
      iframe.style.width = '1366px'
      iframe.style.height = '768px'
      thumb.appendChild(iframe)
      var cap = document.createElement('span')
      cap.className = 'sc-cap'
      var b = document.createElement('b')
      b.textContent = code
      cap.appendChild(b)
      cap.appendChild(document.createTextNode(PAGES[code].title))
      card.appendChild(thumb)
      card.appendChild(cap)
      card.addEventListener('click', function () {
        select(code)
      })
      all.appendChild(card)
    })
    layoutAll()
  }

  function layoutAll() {
    var thumbs = all.querySelectorAll('.sc-thumb')
    for (var i = 0; i < thumbs.length; i++) {
      var w = thumbs[i].clientWidth
      var scale = w / 1366
      thumbs[i].style.height = Math.round(768 * scale) + 'px'
      thumbs[i].firstChild.style.transform = 'scale(' + scale + ')'
    }
  }

  function syncButtons() {
    var tabs = document.querySelectorAll('#pages button')
    for (var i = 0; i < tabs.length; i++) {
      var on = tabs[i].getAttribute('data-page') === state.page
      tabs[i].setAttribute('aria-selected', String(on))
      tabs[i].tabIndex = on ? 0 : -1
    }
    var radios = document.querySelectorAll('#themes button')
    for (var j = 0; j < radios.length; j++) {
      radios[j].setAttribute('aria-checked', String(radios[j].getAttribute('data-theme') === state.theme))
    }
    viewport.value = state.viewport
  }

  function render() {
    applyShowcaseTheme()
    syncButtons()
    var showAll = state.page === 'all'
    single.hidden = showAll
    all.hidden = !showAll
    viewport.disabled = showAll
    if (showAll) {
      renderAll()
    } else {
      frame.src = src(state.page)
      openLink.href = src(state.page)
      layoutSingle()
      renderNotes()
    }
    save()
  }

  function select(page) {
    state.page = page
    render()
    window.scrollTo(0, 0)
  }

  document.getElementById('pages').addEventListener('click', function (event) {
    var button = event.target.closest('button[data-page]')
    if (button) select(button.getAttribute('data-page'))
  })

  // Arrow keys move between tabs, as the tab pattern expects.
  document.getElementById('pages').addEventListener('keydown', function (event) {
    if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return
    var order = ['all'].concat(CODES)
    var next = order.indexOf(state.page) + (event.key === 'ArrowRight' ? 1 : -1)
    next = (next + order.length) % order.length
    select(order[next])
    document.querySelector('#pages button[data-page="' + order[next] + '"]').focus()
  })

  document.getElementById('themes').addEventListener('click', function (event) {
    var button = event.target.closest('button[data-theme]')
    if (!button) return
    state.theme = button.getAttribute('data-theme')
    render()
  })

  viewport.addEventListener('change', function () {
    state.viewport = viewport.value
    render()
  })

  window.addEventListener('resize', function () {
    if (state.page === 'all') layoutAll()
    else layoutSingle()
  })

  render()
})()
