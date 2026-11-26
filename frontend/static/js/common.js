/* RETINOVA — shared helpers, loaded on every page before the page script */

const DR_CLASSES = ['No DR', 'Mild', 'Moderate', 'Severe', 'Proliferative'];

const URGENCY = {
  urgent: ['risk', 'Urgent'],
  refer: ['risk', 'Refer'],
  monitor: ['warn', 'Monitor'],
  clear: ['ok', 'Clear']
};

const $ = id => document.getElementById(id);


// ======================================================
// API AND FORMATTING
// ======================================================

async function api(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => null);
  if (response.status === 401) {
    location.href = '/login';
  }
  if (!response.ok) {
    throw new Error(data?.detail || 'Request failed.');
  }
  return data;
}

function esc(value) {
  const div = document.createElement('div');
  div.textContent = value ?? '';
  return div.innerHTML;
}

function size(bytes) {
  return bytes < 1024 * 1024
    ? (bytes / 1024).toFixed(1) + ' KB'
    : (bytes / 1048576).toFixed(2) + ' MB';
}

// SQLite CURRENT_TIMESTAMP is UTC without a zone marker
function fmtDate(ts, withTime = true) {
  if (!ts) {
    return '—';
  }
  const date = new Date(ts.length > 10 ? ts.replace(' ', 'T') + 'Z' : ts + 'T00:00:00');
  return withTime
    ? date.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })
    : date.toLocaleDateString([], { dateStyle: 'medium' });
}

const gradeLabel = g => 'Grade ' + g + ' · ' + DR_CLASSES[g];
const eyeLabel = eye => ({ left: 'Left', right: 'Right' })[eye] || '—';


// ======================================================
// PILLS AND COUNTERS
// ======================================================

function pill(urgency) {
  const [cls, text] = URGENCY[urgency] || ['', '—'];
  return '<span class="pill ' + cls + '">' + text + '</span>';
}

function setPill(el, urgency, text) {
  el.className = 'pill ' + (URGENCY[urgency] || [''])[0];
  el.textContent = text;
}

function statusPill(s) {
  if (s.status === 'retake') {
    return '<span class="pill warn">Retake photo</span>';
  }
  if (s.status === 'reviewed') {
    return pill(s.urgency);
  }
  return '<span class="pill warn">Pending review</span>';
}

function animateCount(el) {
  const target = parseFloat(el.dataset.count);
  const dec = parseInt(el.dataset.dec || '0', 10);
  const suffix = el.dataset.suffix || '';
  let n = 0;
  const t = setInterval(() => {
    n += target / 60;
    if (n >= target) {
      n = target;
      clearInterval(t);
    }
    el.textContent = n.toFixed(dec) + suffix;
  }, 20);
}

function setCount(id, value, dec = 0, suffix = '') {
  const el = $(id);
  if (value === null || value === undefined) {
    el.textContent = '—';
    return;
  }
  el.dataset.count = value;
  el.dataset.dec = dec;
  el.dataset.suffix = suffix;
  animateCount(el);
}


// ======================================================
// EVERY PAGE: scroll reveal, counters, logout
// ======================================================

const revealObserver = new IntersectionObserver(
  es => es.forEach(e => e.isIntersecting && e.target.classList.add('in')),
  { threshold: 0.12 }
);
document.querySelectorAll('.reveal').forEach(el => revealObserver.observe(el));
document.querySelectorAll('[data-count]').forEach(animateCount);

$('logout')?.addEventListener('click', async event => {
  event.preventDefault();
  try {
    await fetch('/api/auth/logout', { method: 'POST' });
  } finally {
    location.href = '/login';
  }
});
