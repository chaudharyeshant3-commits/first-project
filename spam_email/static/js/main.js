const socket = io();
const tray = document.getElementById('notif-tray');
let currentFilter = 'all';
const seenEmailIds = new Set();

// ── WebSocket ──────────────────────────────────────────────────────────────────
socket.on('connect', () => console.log('🔌 Connected to MailGuard'));

socket.on('new_email', (email) => {
  if (seenEmailIds.has(email.id)) return;
  seenEmailIds.add(email.id);
  showNotification(email);
  prependEmailRow(email);
  requestBrowserNotif(email);
  playVoiceAlert(email);
  if (typeof updateCharts === 'function') updateCharts();
});

// ── In-app Notification Card ───────────────────────────────────────────────────
function showNotification(email) {
  const card = document.createElement('div');
  const riskClass = 'notif-' + email.risk_level.toLowerCase();
  card.className = `notif-card ${riskClass}`;
  card.innerHTML = `
    <div class="notif-header">
      <span class="notif-icon">${email.category_icon}</span>
      <strong class="notif-category">${email.category}</strong>
      <span class="notif-risk risk-badge risk-${email.risk_level.toLowerCase()}">${email.risk_level}</span>
    </div>
    <div class="notif-subject">${escHtml(email.subject)}</div>
    <div class="notif-sender">From: ${escHtml(email.sender)}</div>
  `;
  card.onclick = () => showDetail(email);
  tray.prepend(card);

  // Auto-dismiss after 6s
  setTimeout(() => {
    card.classList.add('notif-out');
    setTimeout(() => card.remove(), 300);
  }, 6000);
}

// ── Browser Notification ───────────────────────────────────────────────────────
function requestBrowserNotif(email) {
  if (!('Notification' in window)) return;
  if (Notification.permission === 'granted') {
    sendBrowserNotif(email);
  } else if (Notification.permission !== 'denied') {
    Notification.requestPermission().then(p => { if (p === 'granted') sendBrowserNotif(email); });
  }
}

function sendBrowserNotif(email) {
  const n = new Notification(`MailGuard: ${email.category} ${email.category_icon}`, {
    body: `${email.subject}\nFrom: ${email.sender}\nRisk: ${email.risk_level}`,
    icon: '/static/favicon.ico',
    tag: email.id,
  });
  n.onclick = () => { window.focus(); showDetail(email); n.close(); };
}

// ── Voice Alert ────────────────────────────────────────────────────────────────
function playVoiceAlert(email) {
  if (!('speechSynthesis' in window)) return;
  
  // Create dynamic alert text based on risk level
  const isHighRisk = email.risk_level === 'Critical' || email.risk_level === 'High';
  const alertText = isHighRisk 
    ? `Warning. High risk ${email.category} email detected from ${email.sender || 'unknown sender'}.` 
    : `New ${email.category} email received.`;
    
  const utterance = new SpeechSynthesisUtterance(alertText);
  // Optional: customize voice properties
  utterance.rate = 1.0;
  utterance.pitch = isHighRisk ? 1.2 : 1.0;
  window.speechSynthesis.speak(utterance);
}

// ── Prepend row to table ───────────────────────────────────────────────────────
function prependEmailRow(email) {
  const tbody = document.getElementById('email-tbody');
  const empty = document.querySelector('.empty-state');
  if (empty) empty.remove();

  const catSlug = (email.category || '').toLowerCase().replace(/[\s\/]+/g, '');
  const tr = document.createElement('tr');
  tr.className = `email-row cat-row-${email.risk_level.toLowerCase()}`;
  tr.dataset.category = email.category;
  tr.onclick = () => showDetail(email);
  tr.innerHTML = `
    <td><span class="cat-badge cat-${catSlug}">${email.category_icon} ${email.category}</span></td>
    <td class="sender-cell">${escHtml((email.sender || '').slice(0,30))}</td>
    <td class="subject-cell">${escHtml((email.subject || '').slice(0,60))}</td>
    <td><span class="risk-badge risk-${email.risk_level.toLowerCase()}">${email.risk_level}</span></td>
    <td>
      <div class="conf-wrap">
        <div class="conf-bar"><div class="conf-fill" style="width:${email.confidence}%"></div></div>
        <span class="conf-num">${email.confidence}%</span>
      </div>
    </td>
    <td class="time-cell">${email.received_at || ''}</td>
  `;
  tbody.prepend(tr);
  if (currentFilter !== 'all' && email.category !== currentFilter) {
    tr.style.display = 'none';
  }
}

// ── Filter by category ─────────────────────────────────────────────────────────
function showSection(event, category) {
  currentFilter = category;
  document.getElementById('section-title').textContent =
    category === 'all' ? 'All Emails' : category;

  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  if (event && event.currentTarget) {
    event.currentTarget.classList.add('active');
  }

  const statsRow = document.querySelector('.stats-row');
  const chartsRow = document.querySelector('.charts-row');
  if (statsRow) statsRow.style.display = category === 'all' ? '' : 'none';
  if (chartsRow) chartsRow.style.display = category === 'all' ? '' : 'none';

  document.querySelectorAll('.email-row').forEach(row => {
    if (category === 'all' || row.dataset.category === category) {
      row.style.display = '';
    } else {
      row.style.display = 'none';
    }
  });
}

// ── Detail Modal ───────────────────────────────────────────────────────────────
function showDetail(email) {
  const overlay = document.getElementById('modal-overlay');
  const content = document.getElementById('modal-content');
  const catSlug = (email.category || '').toLowerCase().replace(/[\s\/]+/g, '');
  const kws = Array.isArray(email.keywords_found) ? email.keywords_found : [];
  const links = Array.isArray(email.suspicious_links) ? email.suspicious_links : [];

  content.innerHTML = `
    <h3 class="modal-title">${escHtml(email.subject || '(No Subject)')}</h3>
    <p class="modal-sender">From: ${escHtml(email.sender || '')} &lt;${escHtml(email.sender_email || '')}&gt;</p>
    <div class="modal-badges">
      <span class="cat-badge cat-${catSlug}">${email.category_icon} ${email.category}</span>
      <span class="risk-badge risk-${email.risk_level.toLowerCase()}">${email.risk_level}</span>
      <span class="total-badge">${email.confidence}% confidence</span>
      ${email.has_dangerous_attachment ? '<span class="risk-badge risk-critical">⚠️ Dangerous Attachment</span>' : ''}
    </div>
    ${kws.length ? `
    <div class="modal-section">
      <h4>🔍 Detected Keywords</h4>
      ${kws.map(k => `<span class="kw-tag">${escHtml(k)}</span>`).join('')}
    </div>` : ''}
    ${links.length ? `
    <div class="modal-section">
      <h4>🔗 Suspicious Links (${links.length})</h4>
      ${links.map(l => `<span class="kw-tag" style="color:#f97316">${escHtml(l.slice(0,60))}...</span>`).join('')}
    </div>` : ''}
    ${email.snippet ? `
    <div class="modal-section">
      <h4>📝 Preview</h4>
      <div class="modal-snippet">${escHtml(email.snippet)}</div>
    </div>` : ''}
    <div class="modal-section">
      <h4>🕐 Received</h4>
      <p style="font-size:.85rem;color:#64748b">${email.received_at || ''}</p>
    </div>
  `;
  overlay.classList.add('open');
}

function closeModal() {
  document.getElementById('modal-overlay').classList.remove('open');
}

// ── Utils ──────────────────────────────────────────────────────────────────────
function escHtml(str) {
  return (str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// Request notification permission on page load
if ('Notification' in window && Notification.permission === 'default') {
  setTimeout(() => Notification.requestPermission(), 2000);
}

// Ensure initial table rows are tracked
window.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.email-row').forEach(r => {
    try {
      const e = JSON.parse(r.dataset.email);
      if (e && e.id) seenEmailIds.add(e.id);
    } catch(err){}
  });
});

// Fallback polling for updates that might have missed the socket window (e.g., initial sync)
setInterval(async () => {
  try {
    const res = await fetch('/api/emails');
    const emails = await res.json();
    let missed = false;
    for (let i = emails.length - 1; i >= 0; i--) {
      const e = emails[i];
      if (!seenEmailIds.has(e.id)) {
        seenEmailIds.add(e.id);
        prependEmailRow(e);
        showNotification(e);
        requestBrowserNotif(e);
        missed = true;
      }
    }
  } catch(err){ }
}, 4000);

// ── AI Chat Widget ─────────────────────────────────────────────────────────────
function toggleChat() {
  const window = document.getElementById('ai-chat-window');
  window.classList.toggle('open');
  if (window.classList.contains('open')) {
    document.getElementById('ai-chat-input').focus();
  }
}

function handleChatKeyPress(event) {
  if (event.key === 'Enter') {
    sendChatMessage();
  }
}

async function sendChatMessage() {
  const input = document.getElementById('ai-chat-input');
  const message = input.value.trim();
  if (!message) return;
  
  const messagesContainer = document.getElementById('ai-chat-messages');
  
  // Add user message
  const userMsgDiv = document.createElement('div');
  userMsgDiv.className = 'user-message';
  userMsgDiv.textContent = message;
  messagesContainer.appendChild(userMsgDiv);
  
  // Add loading indicator
  const loadingDiv = document.createElement('div');
  loadingDiv.className = 'ai-message';
  loadingDiv.textContent = 'Thinking...';
  messagesContainer.appendChild(loadingDiv);
  
  input.value = '';
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
  
  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message })
    });
    const data = await res.json();
    
    // Replace loading with actual response
    loadingDiv.innerHTML = formatMarkdown(data.response || 'No response.');
  } catch (err) {
    loadingDiv.textContent = '⚠️ Error communicating with the AI server.';
  }
  
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function formatMarkdown(text) {
  let html = escHtml(text);
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
  html = html.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  html = html.replace(/\n/g, '<br>');
  return html;
}

// ── Charts ─────────────────────────────────────────────────────────────────────
let catChartInstance = null;
let riskChartInstance = null;

const catColors = {
  'Spam': '#ef4444',
  'Phishing': '#f97316',
  'Virus / Malware': '#991b1b',
  'Marketing': '#a855f7',
  'Newsletter': '#3b82f6',
  'Transaction': '#eab308',
  'Work': '#22c55e',
  'Personal': '#06b6d4',
  'Notification': '#6b7280'
};

const riskColors = {
  'Critical': '#ef4444',
  'High': '#f97316',
  'Medium': '#eab308',
  'Low': '#9ca3af',
  'Safe': '#22c55e'
};

function initCharts() {
  if (!window.INITIAL_STATS || !window.INITIAL_RISK_STATS) return;
  
  const ctxCat = document.getElementById('categoryChart');
  const ctxRisk = document.getElementById('riskChart');
  if (!ctxCat || !ctxRisk) return;

  Chart.defaults.color = '#94a3b8';
  Chart.defaults.borderColor = 'rgba(255,255,255,0.05)';

  const catLabels = Object.keys(window.INITIAL_STATS);
  const catData = Object.values(window.INITIAL_STATS);
  const catBg = catLabels.map(l => catColors[l] || '#6366f1');

  catChartInstance = new Chart(ctxCat, {
    type: 'doughnut',
    data: {
      labels: catLabels,
      datasets: [{
        data: catData,
        backgroundColor: catBg,
        borderWidth: 0,
        hoverOffset: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'right', labels: { boxWidth: 12, font: { size: 10 } } }
      }
    }
  });

  const riskLabels = Object.keys(window.INITIAL_RISK_STATS);
  const riskData = Object.values(window.INITIAL_RISK_STATS);
  const riskBg = riskLabels.map(l => riskColors[l] || '#6366f1');

  riskChartInstance = new Chart(ctxRisk, {
    type: 'bar',
    data: {
      labels: riskLabels,
      datasets: [{
        label: 'Emails',
        data: riskData,
        backgroundColor: riskBg,
        borderRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      scales: {
        y: { beginAtZero: true, ticks: { precision: 0 } }
      }
    }
  });
}

async function updateCharts() {
  if (!catChartInstance || !riskChartInstance) return;
  try {
    const res = await fetch('/api/stats');
    const data = await res.json();
    
    // Update Cat Chart
    const catLabels = Object.keys(data.by_category);
    const catData = Object.values(data.by_category);
    catChartInstance.data.labels = catLabels;
    catChartInstance.data.datasets[0].data = catData;
    catChartInstance.data.datasets[0].backgroundColor = catLabels.map(l => catColors[l] || '#6366f1');
    catChartInstance.update();

    // Update Risk Chart
    const riskLabels = Object.keys(data.by_risk);
    const riskData = Object.values(data.by_risk);
    riskChartInstance.data.labels = riskLabels;
    riskChartInstance.data.datasets[0].data = riskData;
    riskChartInstance.data.datasets[0].backgroundColor = riskLabels.map(l => riskColors[l] || '#6366f1');
    riskChartInstance.update();
  } catch (err) { }
}

window.addEventListener('DOMContentLoaded', initCharts);
