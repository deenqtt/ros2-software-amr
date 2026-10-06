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
  // another language reads as broken. The robot speaks about itself ("Saya
  // berhenti"), never in commands, so nobody reads "STOP" as an order to them.
  const TEXT = {
    id: {
      idleTitle: 'Halo!',
      idleSub: 'Saya siap mengantar',
      movingTitle: (place) => `Menuju ${place}`,
      movingSub: 'Permisi, saya lewat ya',
      nearTitle: (place) => `Hampir sampai di ${place}`,
      nearSub: 'Sebentar lagi pesanan Anda tiba',
      blockedTitle: 'Permisi',
      blockedSub: 'Saya berhenti sebentar, ada yang menghalangi jalan',
      thanksTitle: 'Terima kasih!',
      thanksSub: 'Selamat menikmati',
      doneTitle: 'Semua pesanan terantar',
      doneSub: 'Saya siap mengantar lagi',
      tickleTitle: 'Hehe, geli!',
      tickleSub: 'Saya siap mengantar',
      annoyedTitle: 'Aduh, pelan-pelan ya',
      annoyedSub: 'Saya bukan tombol, hehe',
      turnLeft: 'Saya belok kiri',
      turnRight: 'Saya belok kanan',
      arrivedKicker: 'Pesanan Anda sudah tiba',
      arrivedHint: 'Ambil pesanan dari nampan, lalu tekan tombol hijau',
      confirm: 'Sudah diambil',
      countdown: 'Tidak ditekan? Robot lanjut sendiri',
      countdownEnding: 'Robot akan segera lanjut',
      chargingTitle: 'Sedang mengisi daya',
      chargingSub: 'Sebentar ya, saya istirahat dulu',
      chargingFull: 'Baterai penuh, siap bertugas',
      lowbatTitle: 'Baterai lemah',
      lowbatText: 'Saya kembali ke charger dulu ya',
      errorTitle: 'Saya butuh bantuan',
      errorText: 'Saya tidak bisa melanjutkan rute. Mohon panggil staf.',
      estopTitle: 'Robot berhenti',
      estopText: 'Tombol darurat ditekan. Mohon panggil staf.',
      pinTitle: 'Masukkan PIN staf',
      cancel: 'Batal',
      menuTitle: 'Menu staf',
      menuCancel: 'Batalkan misi',
      menuCharge: 'Kembali ke charger',
      menuLarge: 'Teks besar',
      menuInfo: 'Info teknis',
      menuClose: 'Tutup',
      sayArrived: (place) => `Pesanan untuk ${place} sudah tiba. Silakan diambil, lalu tekan tombol hijau.`,
      sayReminder: 'Pesanannya masih di sini. Silakan diambil ya.',
      sayThanks: 'Terima kasih, selamat menikmati.',
      sayBlocked: 'Permisi, saya mau lewat.',
      pill: {
        idle: 'Siap', moving: 'Mengantar', blocked: 'Terhalang', arrived: 'Tiba',
        thanks: 'Selesai', charging: 'Mengisi', lowbat: 'Baterai lemah', error: 'Butuh bantuan', estop: 'Darurat',
      },
    },
    en: {
      idleTitle: 'Hello!',
      idleSub: 'Ready to deliver',
      movingTitle: (place) => `Heading to ${place}`,
      movingSub: 'Excuse me, coming through',
      nearTitle: (place) => `Almost at ${place}`,
      nearSub: 'Your order is nearly here',
      blockedTitle: 'Excuse me',
      blockedSub: 'I have stopped for a moment, something is in my way',
      thanksTitle: 'Thank you!',
      thanksSub: 'Enjoy your meal',
      doneTitle: 'All orders delivered',
      doneSub: 'Ready for the next one',
      tickleTitle: 'Hehe, that tickles!',
      tickleSub: 'Ready to deliver',
      annoyedTitle: 'Gently, please',
      annoyedSub: 'I am not a button, hehe',
      turnLeft: 'I am turning left',
      turnRight: 'I am turning right',
      arrivedKicker: 'Your order has arrived',
      arrivedHint: 'Take your order from the tray, then press the green button',
      confirm: 'Picked up',
      countdown: 'Not pressed? I will carry on by myself',
      countdownEnding: 'I will carry on shortly',
      chargingTitle: 'Charging',
      chargingSub: 'Taking a short rest',
      chargingFull: 'Fully charged, ready to go',
      lowbatTitle: 'Battery low',
      lowbatText: 'Heading back to the charger',
      errorTitle: 'I need help',
      errorText: 'I cannot continue my route. Please call staff.',
      estopTitle: 'Robot stopped',
      estopText: 'Emergency stop pressed. Please call staff.',
      pinTitle: 'Enter staff PIN',
      cancel: 'Cancel',
      menuTitle: 'Staff menu',
      menuCancel: 'Cancel mission',
      menuCharge: 'Return to charger',
      menuLarge: 'Large text',
      menuInfo: 'Technical info',
      menuClose: 'Close',
      sayArrived: (place) => `Your order for ${place} has arrived. Please take it, then press the green button.`,
      sayReminder: 'Your order is still here. Please take it.',
      sayThanks: 'Thank you, enjoy your meal.',
      sayBlocked: 'Excuse me, coming through.',
      pill: {
        idle: 'Ready', moving: 'Delivering', blocked: 'Blocked', arrived: 'Arrived',
        thanks: 'Done', charging: 'Charging', lowbat: 'Low battery', error: 'Needs help', estop: 'Emergency',
      },
    },
  };

  // ── State ─────────────────────────────────────────────────────────────────
  const CONFIRM_TIMEOUT_S = 120;
  const REMIND_AT_S = 30;
  const STAFF_PIN = '1234';
  const DRIVE_SIM_MS = 7000;

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
    near: false,
    reaction: null, // 'tickle' | 'annoyed' while the face reacts to a touch
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

  const PILL_ICON = {
    idle: 'i-check', moving: 'i-play', blocked: 'i-pause', arrived: 'i-pin', thanks: 'i-check',
    charging: 'i-bolt', lowbat: 'i-battery-low', error: 'i-help', estop: 'i-stop',
  };

  const ALERT_ICON = { lowbat: 'i-battery-low', error: 'i-help', estop: 'i-stop' };

  const $ = (id) => document.getElementById(id);
  const t = () => TEXT[state.lang];
  const place = () => state.route[state.stop]?.name ?? '';
  const setIcon = (svg, id) => svg.querySelector('use').setAttribute('href', `#${id}`);

  // ── Rendering ─────────────────────────────────────────────────────────────
  function mood() {
    if (state.reaction === 'tickle') return 'happy';
    if (state.reaction === 'annoyed') return 'annoyed';
    if (state.mode === 'moving' && state.near) return 'eager';
    return MOOD[state.mode];
  }

  function render() {
    const text = t();
    document.body.dataset.mode = state.mode;
    document.body.dataset.mood = mood();
    document.documentElement.lang = state.lang;
    $('statusText').textContent = text.pill[state.mode];
    setIcon($('statusIcon'), PILL_ICON[state.mode]);

    let caption = {
      idle: state.finished ? [text.doneTitle, text.doneSub] : [text.idleTitle, text.idleSub],
      moving: state.near
        ? [text.nearTitle(place()), text.nearSub]
        : [text.movingTitle(place()), text.movingSub],
      blocked: [text.blockedTitle, text.blockedSub],
      thanks: [text.thanksTitle, text.thanksSub],
    }[state.mode];
    if (state.reaction === 'tickle') caption = [text.tickleTitle, text.tickleSub];
    if (state.reaction === 'annoyed') caption = [text.annoyedTitle, text.annoyedSub];
    if (caption) {
      $('title').textContent = caption[0];
      $('subtitle').textContent = caption[1];
    }

    renderRoute();
    renderBattery();

    $('arrivedKicker').textContent = text.arrivedKicker;
    $('arrivedPlace').textContent = place();
    $('arrivedHint').textContent = text.arrivedHint;
    $('confirmLabel').textContent = text.confirm;
    $('chargingTitle').textContent = text.chargingTitle;

    const alert = {
      lowbat: [text.lowbatTitle, text.lowbatText],
      error: [text.errorTitle, text.errorText],
      estop: [text.estopTitle, text.estopText],
    }[state.mode];
    if (alert) {
      setIcon($('alertIcon'), ALERT_ICON[state.mode]);
      [$('alertTitle').textContent, $('alertText').textContent] = alert;
    }

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
      const done = index < state.stop || (index === state.stop && state.mode === 'thanks');
      if (done) item.className = 'done';
      else if (index === state.stop) item.className = 'current';
      const mark = done ? '<svg class="icon"><use href="#i-check"/></svg>' : '';
      item.innerHTML = `<span class="dot">${mark}</span><span>${stop.name}</span>`;
      list.appendChild(item);
    });
  }

  function renderBattery() {
    const level = Math.round(state.battery);
    $('batteryFill').setAttribute('width', String(Math.max(1.5, (21 * level) / 100)));
    $('batteryText').textContent = `${level}%`;
    $('battery').classList.toggle('low', level <= 30 && level > 15);
    $('battery').classList.toggle('critical', level <= 15);
    $('bigBatteryFill').style.width = `${level}%`;
    $('chargingPercent').textContent = `${level}%`;
    $('chargingSub').textContent = level >= 100 ? t().chargingFull : t().chargingSub;
  }

  // ── Mode changes ──────────────────────────────────────────────────────────
  let timers = [];
  let countdownTimer = null;
  let chargeTimer = null;

  const later = (fn, ms) => timers.push(setTimeout(fn, ms));

  function clearTimers() {
    timers.forEach(clearTimeout);
    timers = [];
    [countdownTimer, chargeTimer].forEach(clearInterval);
    countdownTimer = chargeTimer = null;
    setTurn(null);
  }

  function setMode(mode) {
    clearTimers();
    state.mode = mode;
    state.near = false;
    state.reaction = null;
    if (mode !== 'idle') state.finished = false;
    render();

    if (mode === 'moving') {
      // Simulated drive: a turn on the way, "nearly there", then arrive.
      later(() => setTurn(Math.random() < 0.5 ? 'left' : 'right'), 1500);
      later(() => setTurn(null), 3600);
      later(() => { state.near = true; render(); }, DRIVE_SIM_MS - 2200);
      later(arriveAtStop, DRIVE_SIM_MS);
    } else if (mode === 'arrived') {
      startCountdown();
      chime('arrive');
      say(t().sayArrived(place()));
    } else if (mode === 'thanks') {
      chime('thanks');
      say(t().sayThanks);
      later(nextStop, 2800);
    } else if (mode === 'blocked') {
      chime('blocked');
      say(t().sayBlocked);
    } else if (mode === 'charging') {
      chargeTimer = setInterval(() => {
        state.battery = Math.min(100, state.battery + 0.5);
        renderBattery();
      }, 400);
    }
  }

  // Turn intent: the eyes look the way it's going, the chip says it, and the
  // LED strip blinks on that side — three channels for one message.
  function setTurn(side) {
    document.body.classList.toggle('turning', Boolean(side));
    document.body.classList.toggle('turn-left', side === 'left');
    document.body.classList.toggle('turn-right', side === 'right');
    if (!side) return;
    setIcon($('intentIcon'), side === 'left' ? 'i-turn-left' : 'i-turn-right');
    $('intentText').textContent = side === 'left' ? t().turnLeft : t().turnRight;
    look(side === 'left' ? -0.9 : 0.9, -0.1);
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

  function formatTime(seconds) {
    return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
  }

  function startCountdown() {
    let left = CONFIRM_TIMEOUT_S;
    const ring = $('ringValue');
    const update = () => {
      const ending = left <= REMIND_AT_S;
      $('countdownTime').textContent = formatTime(left);
      $('countdownText').textContent = ending ? t().countdownEnding : t().countdown;
      $('countdown').classList.toggle('ending', ending);
      ring.style.strokeDashoffset = String(100.53 * (1 - left / CONFIRM_TIMEOUT_S));
    };
    update();
    countdownTimer = setInterval(() => {
      left -= 1;
      update();
      // Half a minute left and nobody has come: ask once more, out loud.
      if (left === REMIND_AT_S) {
        chime('arrive');
        say(t().sayReminder);
      }
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
    setTimeout(() => face.classList.remove('blink'), 130);
  }

  function scheduleBlink() {
    // Every 2–6 s at random: a steady rhythm reads as a machine.
    const wait = 2000 + Math.random() * 4000;
    setTimeout(() => {
      if (!['happy', 'annoyed'].includes(document.body.dataset.mood)) {
        blink();
        // Now and then a double blink, which reads as far more alive.
        if (Math.random() < 0.25) setTimeout(blink, 250);
      }
      scheduleBlink();
    }, wait);
  }

  function scheduleGlance() {
    const wait = 1400 + Math.random() * 2600;
    setTimeout(() => {
      const mode = state.mode;
      if (document.body.classList.contains('turning') || state.reaction) {
        // Already looking somewhere on purpose.
      } else if (mode === 'idle') {
        // Looking around the room.
        look((Math.random() * 2 - 1) * 0.9, (Math.random() * 2 - 1) * 0.5);
      } else if (mode === 'moving') {
        // Eyes on the road, with the occasional check to the side.
        look(Math.random() < 0.3 ? (Math.random() < 0.5 ? -0.5 : 0.5) : 0, -0.1);
      } else if (mode === 'blocked') {
        // Looking for a way around.
        look(Math.random() < 0.5 ? -0.85 : 0.85, 0);
      } else {
        look(0, 0);
      }
      scheduleGlance();
    }, wait);
  }

  // The eyes follow a finger — people poke robot screens, and being looked
  // back at is most of the charm.
  window.addEventListener('pointermove', (event) => {
    if (state.mode !== 'idle' || state.reaction) return;
    const x = (event.clientX / window.innerWidth) * 2 - 1;
    const y = (event.clientY / window.innerHeight) * 2 - 1;
    look(x * 0.9, y * 0.6);
  });

  // A tap on the face giggles; a burst of taps gets a mildly fed-up look,
  // which is also the cheapest way to stop children drumming on the screen.
  let pokes = [];
  let reactionTimer = null;
  face.addEventListener('pointerdown', () => {
    if (state.mode !== 'idle') return;
    const now = Date.now();
    pokes = pokes.filter((at) => now - at < 4000).concat(now);
    state.reaction = pokes.length >= 6 ? 'annoyed' : 'tickle';
    if (state.reaction === 'annoyed') pokes = [];
    look(0, 0);
    render();
    chime(state.reaction);
    clearTimeout(reactionTimer);
    reactionTimer = setTimeout(() => {
      state.reaction = null;
      render();
    }, state.reaction === 'annoyed' ? 2600 : 1100);
  });

  // ── Sound ─────────────────────────────────────────────────────────────────
  let audio = null;
  const TUNES = {
    // Two rising notes: "ding-dong", the sound people already know means
    // "something arrived".
    arrive: [[880, 0, 0.6], [1320, 0.18, 0.7]],
    thanks: [[1046, 0, 0.25], [1318, 0.1, 0.25], [1568, 0.2, 0.45]],
    blocked: [[660, 0, 0.18], [660, 0.22, 0.18]],
    tickle: [[1500, 0, 0.08], [1900, 0.07, 0.12]],
    annoyed: [[520, 0, 0.18], [390, 0.16, 0.3]],
  };
  function chime(name) {
    if (!state.sound) return;
    try {
      audio = audio ?? new (window.AudioContext || window.webkitAudioContext)();
      TUNES[name].forEach(([freq, at, length]) => {
        const osc = audio.createOscillator();
        const gain = audio.createGain();
        const start = audio.currentTime + at;
        osc.type = 'sine';
        osc.frequency.value = freq;
        gain.gain.setValueAtTime(0.0001, start);
        gain.gain.exponentialRampToValueAtTime(0.22, start + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, start + length);
        osc.connect(gain).connect(audio.destination);
        osc.start(start);
        osc.stop(start + length + 0.05);
      });
    } catch {
      // No audio (blocked autoplay or no device): the screen still works.
    }
  }

  // Spoken prompts, as delivery robots do on arrival. The browser's own voice
  // stands in for the robot's speaker here.
  function say(sentence) {
    if (!state.sound || !('speechSynthesis' in window)) return;
    try {
      window.speechSynthesis.cancel();
      const line = new SpeechSynthesisUtterance(sentence);
      line.lang = state.lang === 'id' ? 'id-ID' : 'en-GB';
      line.rate = 1;
      line.pitch = 1.2;
      // Let the chime finish first.
      setTimeout(() => window.speechSynthesis.speak(line), 650);
    } catch {
      // No voice available: chime and screen carry the message.
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

  ['1', '2', '3', '4', '5', '6', '7', '8', '9', 'back', '0', 'ok'].forEach((key) => {
    const button = document.createElement('button');
    button.type = 'button';
    if (key === 'back') {
      button.className = 'key-quiet';
      button.setAttribute('aria-label', 'Hapus');
      button.innerHTML = '<svg class="icon"><use href="#i-backspace"/></svg>';
    } else if (key === 'ok') {
      button.className = 'key-ok';
      button.setAttribute('aria-label', 'OK');
      button.innerHTML = '<svg class="icon"><use href="#i-check"/></svg>';
    } else {
      button.textContent = key;
    }
    button.addEventListener('click', () => {
      if (key === 'back') pin = pin.slice(0, -1);
      else if (key === 'ok') checkPin();
      else if (pin.length < 4) pin += key;
      renderPin();
      if (pin.length === 4 && key !== 'ok') checkPin();
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
    setTimeout(renderPin, 360);
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
      } else if (action === 'large') {
        document.body.classList.toggle('large-text');
      } else if (action === 'info') {
        $('techInfo').textContent = [
          'Robot     : AMR-02 (7fc87960…)',
          'IP        : 192.168.2.133',
          'Bridge    : ws://localhost:9090',
          'Mode      : nav / running',
          `Baterai   : ${Math.round(state.battery)}%`,
          `Rute      : ${state.route.map((stop) => stop.name).join(' → ')}`,
          `Timeout   : ${CONFIRM_TIMEOUT_S} s per konfirmasi`,
        ].join('\n');
        $('techInfo').classList.toggle('show');
      } else {
        closeStaff();
      }
    });
  });

  // ── Simulation panel ──────────────────────────────────────────────────────
  function startMode(mode) {
    // Starting a delivery from idle restarts the route: it leaves the first
    // stop (the kitchen) for the second.
    if (mode === 'moving' && state.mode === 'idle') state.stop = 1;
    // Jumping straight to a mid-delivery screen: be on the way to a table,
    // not still at the kitchen.
    if (['blocked', 'arrived', 'thanks'].includes(mode) && !state.route[state.stop]?.confirm) {
      state.stop = 1;
    }
    setMode(mode);
  }

  MODES.forEach(([mode, label], index) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.dataset.mode = mode;
    button.textContent = `${index + 1}. ${label}`;
    button.addEventListener('click', () => startMode(mode));
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
  });
  $('soundToggle').addEventListener('click', (event) => {
    state.sound = !state.sound;
    const button = event.currentTarget;
    setIcon(button.querySelector('svg'), state.sound ? 'i-volume' : 'i-volume-off');
    button.querySelector('span').textContent = `Suara: ${state.sound ? 'on' : 'off'}`;
    if (!state.sound && 'speechSynthesis' in window) window.speechSynthesis.cancel();
  });

  window.addEventListener('keydown', (event) => {
    if (event.key.toLowerCase() === 'd') $('devPanel').classList.toggle('open');
    const index = Number(event.key) - 1;
    if (index >= 0 && index < MODES.length) startMode(MODES[index][0]);
  });

  // ── Clock ─────────────────────────────────────────────────────────────────
  function tick() {
    const now = new Date();
    $('clock').textContent = now.toLocaleTimeString(state.lang === 'id' ? 'id-ID' : 'en-GB', {
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  // ?mode=arrived&lang=en&panel=0&large=1 opens straight into a state, for
  // reviewing one screen or taking a screenshot of it.
  const params = new URLSearchParams(location.search);
  if (params.get('lang') === 'en') state.lang = 'en';
  if (params.get('sound') === '0') state.sound = false;
  if (params.get('large') === '1') document.body.classList.add('large-text');
  if (params.has('stop')) state.stop = Math.max(0, Number(params.get('stop')) || 0);

  tick();
  setInterval(tick, 1000);
  render();
  scheduleBlink();
  scheduleGlance();
  if (params.get('panel') !== '0') $('devPanel').classList.add('open');
  const initial = params.get('mode');
  if (initial && MODES.some(([mode]) => mode === initial)) startMode(initial);
})();
