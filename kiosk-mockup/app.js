/*
 * Robot kiosk mockup — behaviour.
 *
 * Everything the real kiosk would get from the robot (mode, route, battery)
 * is faked here by a small simulation, so the screens can be judged before
 * any ROS wiring exists. In the real thing, `setMode` and the route come from
 * /robot_mode_status over rosbridge, and the confirm button calls
 * /mission_confirm. See README.md.
 */
(() => {
  'use strict';

  // ── Copy ──────────────────────────────────────────────────────────────────
  // Two languages, one table: a guest-facing screen with half its words in
  // another language reads as broken.
  const TEXT = {
    id: {
      idleTitle: 'Halo! 👋',
      idleSub: 'Saya siap mengantar',
      movingTitle: (place) => `Menuju ${place}`,
      movingSub: 'Permisi, mohon beri jalan ya 🙂',
      blockedTitle: 'Permisi 🙏',
      blockedSub: 'Ada yang menghalangi, saya sedang mencari jalan',
      thanksTitle: 'Terima kasih! 😊',
      thanksSub: 'Selamat menikmati',
      doneTitle: 'Misi selesai ✨',
      doneSub: 'Kembali siap mengantar',
      arrivedKicker: 'Pesanan Anda sudah tiba!',
      arrivedHint: 'Silakan ambil pesanan Anda, lalu tekan tombol di bawah',
      confirm: 'SUDAH DIAMBIL',
      countdown: (s) => `Robot lanjut otomatis dalam ${s} detik`,
      chargingTitle: 'Sedang mengisi daya',
      lowbatTitle: 'Baterai lemah',
      lowbatText: 'Saya kembali ke charger dulu ya',
      errorTitle: 'Saya butuh bantuan',
      errorText: 'Tidak bisa melanjutkan rute — mohon hubungi staf',
      estopTitle: 'ROBOT BERHENTI',
      estopText: 'Tombol darurat ditekan. Hubungi staf.',
      pinTitle: 'Masukkan PIN staf',
      menuTitle: 'Menu staf',
      menuCancel: 'Batalkan misi',
      menuCharge: 'Kembali ke charger',
      menuInfo: 'Info teknis',
      menuClose: 'Tutup',
      pill: {
        idle: 'Siap', moving: 'Mengantar', blocked: 'Terhalang', arrived: 'Tiba',
        thanks: 'Selesai', charging: 'Mengisi', lowbat: 'Baterai lemah', error: 'Error', estop: 'E-STOP',
      },
    },
    en: {
      idleTitle: 'Hello! 👋',
      idleSub: 'Ready to deliver',
      movingTitle: (place) => `Heading to ${place}`,
      movingSub: 'Excuse me, coming through 🙂',
      blockedTitle: 'Excuse me 🙏',
      blockedSub: 'Something is in my way, finding another path',
      thanksTitle: 'Thank you! 😊',
      thanksSub: 'Enjoy!',
      doneTitle: 'Mission complete ✨',
      doneSub: 'Ready for the next one',
      arrivedKicker: 'Your order has arrived!',
      arrivedHint: 'Please take your order, then press the button below',
      confirm: 'PICKED UP',
      countdown: (s) => `Continuing automatically in ${s} s`,
      chargingTitle: 'Charging',
      lowbatTitle: 'Battery low',
      lowbatText: 'Heading back to the charger',
      errorTitle: 'I need help',
      errorText: 'Cannot continue the route — please call staff',
      estopTitle: 'ROBOT STOPPED',
      estopText: 'Emergency stop pressed. Call staff.',
      pinTitle: 'Enter staff PIN',
      menuTitle: 'Staff menu',
      menuCancel: 'Cancel mission',
      menuCharge: 'Return to charger',
      menuInfo: 'Technical info',
      menuClose: 'Close',
      pill: {
        idle: 'Ready', moving: 'Delivering', blocked: 'Blocked', arrived: 'Arrived',
        thanks: 'Done', charging: 'Charging', lowbat: 'Low battery', error: 'Error', estop: 'E-STOP',
      },
    },
  };

  // ── State ─────────────────────────────────────────────────────────────────
  const CONFIRM_TIMEOUT_S = 45;
  const STAFF_PIN = '1234';
  const DRIVE_SIM_MS = 6000;

  const state = {
    mode: 'idle',
    lang: 'id',
    sound: true,
    battery: 82,
    route: [
      { name: 'Dapur', confirm: false },
      { name: 'Meja 5', confirm: true },
      { name: 'Meja 8', confirm: true },
      { name: 'Dapur', confirm: false },
    ],
    stop: 0,
    finished: false,
  };

  const MODES = [
    ['idle', 'Idle'],
    ['moving', 'Jalan'],
    ['blocked', 'Terhalang'],
    ['arrived', 'Tiba (confirm)'],
    ['thanks', 'Terima kasih'],
    ['charging', 'Charging'],
    ['lowbat', 'Baterai lemah'],
    ['error', 'Error'],
    ['estop', 'E-STOP'],
  ];

  const MOOD = {
    idle: 'neutral', moving: 'focused', blocked: 'worried', arrived: 'happy',
    thanks: 'happy', charging: 'sleepy', lowbat: 'sleepy', error: 'worried', estop: 'worried',
  };

  const $ = (id) => document.getElementById(id);
  const t = () => TEXT[state.lang];
  const place = () => state.route[state.stop]?.name ?? '';

  // ── Rendering ─────────────────────────────────────────────────────────────
  function render() {
    const text = t();
    document.body.dataset.mode = state.mode;
    document.body.dataset.mood = MOOD[state.mode];
    document.documentElement.lang = state.lang;
    $('statusPill').textContent = text.pill[state.mode];

    const caption = {
      idle: state.finished ? [text.doneTitle, text.doneSub] : [text.idleTitle, text.idleSub],
      moving: [text.movingTitle(place()), text.movingSub],
      blocked: [text.blockedTitle, text.blockedSub],
      thanks: [text.thanksTitle, text.thanksSub],
    }[state.mode];
    if (caption) {
      $('title').textContent = caption[0];
      $('subtitle').textContent = caption[1];
    }

    renderRoute();
    renderBattery();

    $('arrivedKicker').textContent = text.arrivedKicker;
    $('arrivedPlace').textContent = place().toUpperCase();
    $('arrivedHint').textContent = text.arrivedHint;
    $('confirmLabel').textContent = text.confirm;
    $('chargingTitle').textContent = text.chargingTitle;

    const alert = {
      lowbat: ['🔋', text.lowbatTitle, text.lowbatText],
      error: ['🆘', text.errorTitle, text.errorText],
      estop: ['⛔', text.estopTitle, text.estopText],
    }[state.mode];
    if (alert) [$('alertIcon').textContent, $('alertTitle').textContent, $('alertText').textContent] = alert;

    $('pinTitle').textContent = text.pinTitle;
    $('menuTitle').textContent = text.menuTitle;
    document.querySelectorAll('[data-i18n]').forEach((node) => {
      node.textContent = text[node.dataset.i18n];
    });

    document.querySelectorAll('#devButtons button').forEach((button) => {
      button.classList.toggle('active', button.dataset.mode === state.mode);
    });
  }

  function renderRoute() {
    const list = $('route');
    // Only while there is a route to show; an idle robot has none.
    const show = ['moving', 'blocked', 'thanks'].includes(state.mode);
    list.innerHTML = '';
    if (!show) return;
    state.route.forEach((stop, index) => {
      const item = document.createElement('li');
      if (index < state.stop) item.className = 'done';
      else if (index === state.stop) item.className = 'current';
      item.innerHTML = `<span class="dot"></span><span>${stop.name}</span>`;
      list.appendChild(item);
    });
  }

  function renderBattery() {
    const level = Math.round(state.battery);
    $('batteryFill').style.width = `${level}%`;
    $('batteryText').textContent = `${level}%`;
    $('battery').classList.toggle('low', level <= 30 && level > 15);
    $('battery').classList.toggle('critical', level <= 15);
    $('bigBatteryFill').style.width = `${level}%`;
    $('chargingPercent').textContent = `${level}%`;
  }

  // ── Mode changes ──────────────────────────────────────────────────────────
  let driveTimer = null;
  let countdownTimer = null;
  let thanksTimer = null;
  let chargeTimer = null;

  function clearTimers() {
    [driveTimer, thanksTimer].forEach(clearTimeout);
    [countdownTimer, chargeTimer].forEach(clearInterval);
    driveTimer = countdownTimer = thanksTimer = chargeTimer = null;
  }

  function setMode(mode) {
    clearTimers();
    state.mode = mode;
    if (mode !== 'idle') state.finished = false;
    render();

    if (mode === 'moving') {
      // Simulated drive: arrive after a few seconds.
      driveTimer = setTimeout(arriveAtStop, DRIVE_SIM_MS);
    } else if (mode === 'arrived') {
      startCountdown();
      chime();
    } else if (mode === 'thanks') {
      thanksTimer = setTimeout(nextStop, 2500);
    } else if (mode === 'charging') {
      chargeTimer = setInterval(() => {
        state.battery = Math.min(100, state.battery + 0.5);
        renderBattery();
      }, 400);
    }
  }

  function arriveAtStop() {
    if (state.route[state.stop]?.confirm) setMode('arrived');
    else nextStop();
  }

  function nextStop() {
    if (state.stop >= state.route.length - 1) {
      state.stop = 0;
      state.finished = true;
      setMode('idle');
      return;
    }
    state.stop += 1;
    setMode('moving');
  }

  function startCountdown() {
    let left = CONFIRM_TIMEOUT_S;
    const ring = $('ringValue');
    const update = () => {
      $('countdownText').textContent = t().countdown(left);
      ring.style.strokeDashoffset = String(100.53 * (1 - left / CONFIRM_TIMEOUT_S));
    };
    update();
    countdownTimer = setInterval(() => {
      left -= 1;
      update();
      // Nobody came: carry on, as the real robot would after its timeout.
      if (left <= 0) nextStop();
    }, 1000);
  }

  $('confirmButton').addEventListener('click', () => {
    // In the real kiosk this is the /mission_confirm service call.
    setMode('thanks');
  });

  // ── Eyes ──────────────────────────────────────────────────────────────────
  const face = $('face');

  function look(x, y) {
    document.documentElement.style.setProperty('--lx', x.toFixed(2));
    document.documentElement.style.setProperty('--ly', y.toFixed(2));
  }

  function blink() {
    face.classList.add('blink');
    setTimeout(() => face.classList.remove('blink'), 140);
  }

  function scheduleBlink() {
    const wait = 2200 + Math.random() * 4200;
    setTimeout(() => {
      if (document.body.dataset.mood !== 'happy') {
        blink();
        // Now and then a double blink, which reads as far more alive.
        if (Math.random() < 0.25) setTimeout(blink, 260);
      }
      scheduleBlink();
    }, wait);
  }

  function scheduleGlance() {
    const wait = 1400 + Math.random() * 2600;
    setTimeout(() => {
      const mode = state.mode;
      if (mode === 'idle') {
        // Looking around the room.
        look((Math.random() * 2 - 1) * 0.9, (Math.random() * 2 - 1) * 0.5);
      } else if (mode === 'moving') {
        // Eyes on the road, with the occasional check to the side.
        look(Math.random() < 0.3 ? (Math.random() < 0.5 ? -0.6 : 0.6) : 0, -0.1);
      } else if (mode === 'blocked') {
        // Looking for a way around.
        look(Math.random() < 0.5 ? -0.8 : 0.8, 0);
      } else {
        look(0, 0);
      }
      scheduleGlance();
    }, wait);
  }

  // The eyes follow a touch — people poke robot screens, and being looked
  // back at is most of the charm.
  window.addEventListener('pointermove', (event) => {
    if (state.mode !== 'idle') return;
    const x = (event.clientX / window.innerWidth) * 2 - 1;
    const y = (event.clientY / window.innerHeight) * 2 - 1;
    look(x * 0.9, y * 0.6);
  });

  // ── Sound ─────────────────────────────────────────────────────────────────
  let audio = null;
  function chime() {
    if (!state.sound) return;
    try {
      audio = audio ?? new (window.AudioContext || window.webkitAudioContext)();
      // Two rising notes: "ding-dong", the sound people already know means
      // "something arrived".
      [[880, 0], [1320, 0.18]].forEach(([freq, at]) => {
        const osc = audio.createOscillator();
        const gain = audio.createGain();
        osc.type = 'sine';
        osc.frequency.value = freq;
        gain.gain.setValueAtTime(0.0001, audio.currentTime + at);
        gain.gain.exponentialRampToValueAtTime(0.25, audio.currentTime + at + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, audio.currentTime + at + 0.6);
        osc.connect(gain).connect(audio.destination);
        osc.start(audio.currentTime + at);
        osc.stop(audio.currentTime + at + 0.65);
      });
    } catch {
      // No audio (blocked autoplay or no device): the screen still works.
    }
  }

  // ── Staff menu ────────────────────────────────────────────────────────────
  let pin = '';
  let pressTimer = null;

  $('staffHotspot').addEventListener('pointerdown', () => {
    // A long press, so a guest leaning on the screen does not open it.
    pressTimer = setTimeout(openStaff, 1200);
  });
  ['pointerup', 'pointerleave', 'pointercancel'].forEach((name) =>
    $('staffHotspot').addEventListener(name, () => clearTimeout(pressTimer)),
  );

  function openStaff() {
    pin = '';
    renderPin();
    document.body.classList.add('staff-open');
    document.body.classList.remove('staff-unlocked');
    $('techInfo').classList.remove('show');
  }

  function closeStaff() {
    document.body.classList.remove('staff-open', 'staff-unlocked');
  }

  function renderPin() {
    document.querySelectorAll('#pinDots span').forEach((dot, index) => {
      dot.classList.toggle('filled', index < pin.length);
    });
  }

  ['1', '2', '3', '4', '5', '6', '7', '8', '9', '⌫', '0', '✓'].forEach((key) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = key;
    button.addEventListener('click', () => {
      if (key === '⌫') pin = pin.slice(0, -1);
      else if (key === '✓') checkPin();
      else if (pin.length < 4) pin += key;
      renderPin();
      if (pin.length === 4 && key !== '✓') checkPin();
    });
    $('pinPad').appendChild(button);
  });

  function checkPin() {
    if (pin === STAFF_PIN) {
      document.body.classList.add('staff-unlocked');
      return;
    }
    pin = '';
    const dots = $('pinDots');
    dots.classList.remove('shake');
    void dots.offsetWidth; // restart the animation
    dots.classList.add('shake');
    renderPin();
  }

  $('pinCancel').addEventListener('click', closeStaff);

  document.querySelectorAll('.staff-menu [data-action]').forEach((button) => {
    button.addEventListener('click', () => {
      const action = button.dataset.action;
      if (action === 'cancel') {
        state.stop = 0;
        closeStaff();
        setMode('idle');
      } else if (action === 'charge') {
        closeStaff();
        setMode('charging');
      } else if (action === 'info') {
        $('techInfo').textContent = [
          'Robot     : AMR-02 (7fc87960…)',
          'IP        : 192.168.2.133',
          'Bridge    : ws://localhost:9090',
          'Mode      : nav / running',
          `Baterai   : ${Math.round(state.battery)}%`,
          `Rute      : ${state.route.map((stop) => stop.name).join(' → ')}`,
        ].join('\n');
        $('techInfo').classList.toggle('show');
      } else {
        closeStaff();
      }
    });
  });

  // ── Simulation panel ──────────────────────────────────────────────────────
  MODES.forEach(([mode, label], index) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.dataset.mode = mode;
    button.textContent = `${index + 1}. ${label}`;
    button.addEventListener('click', () => {
      // Starting a delivery from idle restarts the route.
      if (mode === 'moving' && state.mode === 'idle') state.stop = 0;
      setMode(mode);
    });
    $('devButtons').appendChild(button);
  });

  $('devToggle').addEventListener('click', () => $('devPanel').classList.toggle('open'));
  $('batterySlider').addEventListener('input', (event) => {
    state.battery = Number(event.target.value);
    renderBattery();
  });
  $('langToggle').addEventListener('click', () => {
    state.lang = state.lang === 'id' ? 'en' : 'id';
    render();
    if (state.mode === 'arrived') $('countdownText').textContent = t().countdown(CONFIRM_TIMEOUT_S);
  });
  $('soundToggle').addEventListener('click', (event) => {
    state.sound = !state.sound;
    event.target.textContent = `🔔 Suara: ${state.sound ? 'on' : 'off'}`;
  });

  window.addEventListener('keydown', (event) => {
    if (event.key.toLowerCase() === 'd') $('devPanel').classList.toggle('open');
    const index = Number(event.key) - 1;
    if (index >= 0 && index < MODES.length) {
      const mode = MODES[index][0];
      if (mode === 'moving' && state.mode === 'idle') state.stop = 0;
      setMode(mode);
    }
  });

  // ── Clock ─────────────────────────────────────────────────────────────────
  function tick() {
    const now = new Date();
    $('clock').textContent = now.toLocaleTimeString(state.lang === 'id' ? 'id-ID' : 'en-GB', {
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  // ?mode=arrived&lang=en&panel=0 opens straight into a state, for reviewing
  // one screen or taking a screenshot of it.
  const params = new URLSearchParams(location.search);
  if (params.get('lang') === 'en') state.lang = 'en';
  if (params.has('stop')) state.stop = Math.max(0, Number(params.get('stop')) || 0);

  tick();
  setInterval(tick, 1000);
  render();
  scheduleBlink();
  scheduleGlance();
  if (params.get('panel') !== '0') $('devPanel').classList.add('open');
  const startMode = params.get('mode');
  if (startMode && MODES.some(([mode]) => mode === startMode)) setMode(startMode);
})();
