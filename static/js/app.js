/* ═══════════════════════════════════════════════════════════════════════
   AgriSense Pro — SPA Controller
   ═══════════════════════════════════════════════════════════════════════ */

// ── State ─────────────────────────────────────────────────────────────────
let currentPage = 'dashboard';
let currentMode = 'model';   // detection mode
let selectedFile = null;
let diseaseChart = null;
let trendChart = null;

// Maps
let registrationMap = null;
let registrationMarker = null;
let viewMap = null;
let farmCluster = null;

// ── Boot ────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  liveClock();
  await checkSession();
});

function hideSplash() {
  const splash = document.getElementById('splash');
  if (!splash) return;
  splash.classList.add('fade-out');
  setTimeout(() => { splash.style.display = 'none'; }, 420);
}

async function checkSession() {
  try {
    const res = await fetch('/api/auth/me');
    const data = await res.json();
    hideSplash();
    if (data.logged_in) {
      loginSuccess(data.farmer_id, data.farmer_name);
    } else {
      show('auth-screen');
    }
  } catch (e) {
    hideSplash();
    show('auth-screen');
    console.warn('Session check failed:', e);
  }
}

function loginSuccess(fid, fname) {
  hide('auth-screen');
  // Force display:flex on main-app before removing hidden
  const mainApp = document.getElementById('main-app');
  mainApp.style.display = 'flex';
  mainApp.classList.remove('hidden');
  document.getElementById('user-name-display').textContent = fname;
  navigate('dashboard');
}

// ── Time ─────────────────────────────────────────────────────────────────
function liveClock() {
  const el = document.getElementById('topbar-time');
  function tick() {
    el.textContent = new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }
  tick(); setInterval(tick, 1000);
}

// ── Auth Logic ─────────────────────────────────────────────────────────────
function togglePw(id, btn) {
  const input = document.getElementById(id);
  const isPw = input.type === 'password';
  input.type = isPw ? 'text' : 'password';
  btn.textContent = isPw ? '🙈' : '👁';
}

function updatePwStrength(pw) {
  const wrap = document.getElementById('pw-strength-wrap');
  const fill = document.getElementById('pw-strength-fill');
  const lbl = document.getElementById('pw-strength-label');
  if (!pw) { wrap.className = 'pw-strength-wrap hidden'; return; }
  wrap.classList.remove('hidden');

  let strength = 0;
  if (pw.length >= 8) strength++;
  if (/[A-Z]/.test(pw) || /[a-z]/.test(pw)) strength++;
  if (/\d/.test(pw)) strength++;

  const levels = [
    { cls: 'strength-0', txt: 'Too weak' },
    { cls: 'strength-1', txt: 'Weak' },
    { cls: 'strength-2', txt: 'Medium' },
    { cls: 'strength-3', txt: 'Strong' },
  ];
  const level = levels[strength];
  wrap.className = `pw-strength-wrap ${level.cls}`;
  lbl.textContent = level.txt;
}

async function checkLockout() {
  const res = await fetch('/api/auth/lockout-status');
  const data = await res.json();
  const banner = document.getElementById('lockout-banner');
  const timer = document.getElementById('lockout-timer');
  const btn = document.getElementById('login-btn');

  if (data.locked) {
    show(banner);
    btn.disabled = true;
    let rem = data.remaining_seconds;
    const tick = setInterval(() => {
      rem--;
      if (rem <= 0) {
        clearInterval(tick);
        hide(banner);
        btn.disabled = false;
      }
      const m = Math.floor(rem / 60);
      const s = rem % 60;
      timer.textContent = `${m}m ${s}s`;
    }, 1000);
  } else {
    hide(banner);
    btn.disabled = false;
  }
}

async function handleLogin(e) {
  e.preventDefault();
  const btn = document.getElementById('login-btn');
  const errEl = document.getElementById('login-error');
  setLoading(btn, true);
  hide(errEl);
  clearFieldErrors('login');

  const body = new FormData();
  body.append('name', document.getElementById('login-name').value.trim());
  body.append('password', document.getElementById('login-pass').value);

  try {
    const res = await fetch('/api/auth/login', { method: 'POST', body });
    const data = await res.json();
    if (data.ok) {
      loginSuccess(data.farmer_id, data.farmer_name);
    } else {
      if (data.locked) checkLockout();
      if (data.field) markFieldError('login', data.field, data.error);
      else showError(errEl, data.error || 'Login failed');
    }
  } catch { showError(errEl, 'Network error'); }
  finally { setLoading(btn, false); }
}

async function handleRegister(e) {
  e.preventDefault();
  const btn = e.target.querySelector('button[type="submit"]');
  const errEl = document.getElementById('reg-error');
  hide(errEl);
  clearFieldErrors('reg');
  btn.disabled = true;

  const body = new FormData();
  body.append('name', document.getElementById('reg-name').value.trim());
  body.append('aadhaar', document.getElementById('reg-aadhaar').value.trim());
  body.append('village', document.getElementById('reg-village').value.trim());
  body.append('phone', document.getElementById('reg-phone').value.trim());
  body.append('password', document.getElementById('reg-pass').value);

  try {
    const res = await fetch('/api/auth/register', { method: 'POST', body });
    const data = await res.json();
    if (data.ok) {
      loginSuccess(data.farmer_id, data.farmer_name);
      toast('Welcome to AgriSense Pro! 🌿', 'success');
    } else {
      if (data.all_errors) {
        Object.keys(data.all_errors).forEach(f => markFieldError('reg', f, data.all_errors[f]));
      } else if (data.field) {
        markFieldError('reg', data.field, data.error);
      } else {
        showError(errEl, data.error || 'Registration failed');
      }
    }
  } catch { showError(errEl, 'Network error'); }
  finally { btn.disabled = false; }
}

function markFieldError(prefix, field, msg) {
  const wrap = document.getElementById(`wrap-${prefix}-${field}`);
  const hint = document.getElementById(`hint-${prefix}-${field}`);
  if (wrap) wrap.style.borderColor = 'var(--danger)';
  if (hint) { hint.textContent = msg; hint.classList.add('error'); }
}

function clearFieldErrors(prefix) {
  document.querySelectorAll(`[id^="wrap-${prefix}"]`).forEach(el => el.style.borderColor = '');
  document.querySelectorAll(`[id^="hint-${prefix}"]`).forEach(el => { el.textContent = ''; el.classList.remove('error'); });
}

async function handleLogout() {
  toast('Signing out of your cockpit...', 'info');
  await fetch('/api/auth/logout', { method: 'POST' });
  setTimeout(() => location.reload(), 800);
}

// ── Navigation ────────────────────────────────────────────────────────────
function navigate(page, linkEl) {
  // Hide all pages, show the target
  document.querySelectorAll('.page').forEach(p => {
    p.classList.remove('active');
    p.classList.add('hidden');
  });
  const target = document.getElementById(`page-${page}`);
  if (target) {
    target.classList.remove('hidden');
    target.classList.add('active');
  }

  // Update nav active state
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  if (linkEl) linkEl.classList.add('active');
  else {
    const el = document.querySelector(`.nav-item[data-page="${page}"]`);
    if (el) el.classList.add('active');
  }

  // Update topbar title
  const titles = {
    dashboard: 'Dashboard',
    detection: 'Disease Detection',
    farm: 'Farm Registration',
    history: 'Detection History',
    report: 'Reports',
    map: 'Farm Map View',
    profile: 'My Profile'
  };
  document.getElementById('topbar-title').textContent = titles[page] || page;

  currentPage = page;

  // Lazy-load page data
  if (page === 'dashboard') loadDashboard();
  if (page === 'history') loadHistory();
  if (page === 'farm') {
    loadMyFarms();
    setTimeout(initRegistrationMap, 100);
  }
  if (page === 'map') {
    setTimeout(initViewMap, 100);
  }
  if (page === 'profile') loadProfile();

  // Scroll to top
  window.scrollTo({ top: 0, behavior: 'smooth' });

  // Close sidebar on mobile
  if (window.innerWidth <= 768) document.getElementById('sidebar').classList.remove('open');

  return false;
}

function toggleSidebar() {
  document.getElementById('sidebar').classList.toggle('open');
}

// ── Dashboard ─────────────────────────────────────────────────────────────
async function loadDashboard() {
  try {
    const res = await fetch('/api/dashboard/stats');
    const data = await res.json();
    if (data.error) return;

    setText('dash-total', data.total);
    setText('dash-today', data.today);
    setText('dash-common', data.most_common);
    setText('dash-last', data.last_detected);

    renderDiseaseChart(data.chart || []);
    renderTrendChart(data.trend || []);

    // Try to load weather for the first farm by default
    const farmRes = await fetch('/api/farm/my-farms');
    const farms = await farmRes.json();
    if (farms && farms.length > 0) {
      const firstFarmWithGPS = farms.find(f => f.latitude && f.longitude);
      if (firstFarmWithGPS) {
        fetchWeatherInsight(firstFarmWithGPS.farm_id);
        fetchNdviInsight(firstFarmWithGPS.farm_id);
      }
    }
  } catch (e) { console.error('Dashboard load:', e); }
}

function renderDiseaseChart(rows) {
  const ctx = document.getElementById('chart-disease').getContext('2d');
  if (diseaseChart) diseaseChart.destroy();

  if (!rows.length) {
    ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    return;
  }

  diseaseChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: rows.map(r => shortenLabel(r.disease)),
      datasets: [{
        data: rows.map(r => r.count),
        backgroundColor: [
          '#00ff88', '#00cc6a', '#00a85d', '#00854a', '#75ffc1',
          '#00ffb3', '#2effa1', '#004a2d',
        ],
        borderWidth: 0,
        hoverOffset: 12,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'right',
          labels: { color: '#8ea598', font: { family: 'Outfit', size: 12, weight: '500' }, boxWidth: 8, usePointStyle: true, padding: 20 }
        }
      },
      cutout: '65%',
    }
  });
}

function renderTrendChart(rows) {
  const ctx = document.getElementById('chart-trend').getContext('2d');
  if (trendChart) trendChart.destroy();

  trendChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: rows.map(r => r.day),
      datasets: [{
        label: 'Detections',
        data: rows.map(r => r.count),
        fill: true,
        backgroundColor: 'rgba(0, 255, 136, 0.05)',
        borderColor: '#00ff88',
        borderWidth: 3,
        pointBackgroundColor: '#00ff88',
        pointBorderColor: '#004a2d',
        pointBorderWidth: 2,
        pointRadius: 6,
        pointHoverRadius: 8,
        tension: 0.4,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: {
        x: { ticks: { color: '#8ea598', font: { family: 'Outfit', size: 11 } }, grid: { display: false } },
        y: { ticks: { color: '#8ea598', font: { family: 'Outfit', size: 11 } }, grid: { color: 'rgba(255, 255, 255, 0.03)' }, beginAtZero: true }
      },
      plugins: { legend: { display: false } }
    }
  });
}

// ── Detection Page ────────────────────────────────────────────────────────
let isCameraActive = false;

function switchMode(mode) {
  currentMode = mode;
  document.getElementById('btn-mode-model').classList.toggle('active', mode === 'model');
  document.getElementById('btn-mode-ai').classList.toggle('active', mode === 'ai');
  document.getElementById('btn-mode-camera').classList.toggle('active', mode === 'camera');

  document.getElementById('detect-model-panel').classList.toggle('hidden', mode !== 'model');
  document.getElementById('detect-ai-panel').classList.toggle('hidden', mode !== 'ai');
  document.getElementById('detect-camera-panel').classList.toggle('hidden', mode !== 'camera');

  if (mode !== 'camera' && isCameraActive) stopCamera();
  hide('detect-result');
}

function startCamera() {
  const stream = document.getElementById('webcam-stream');
  const placeholder = document.getElementById('camera-placeholder');
  const startBtn = document.getElementById('btn-camera-start');
  const stopBtn = document.getElementById('btn-camera-stop');

  stream.src = '/api/detection/video_feed?t=' + Date.now();
  stream.classList.remove('hidden');
  placeholder.classList.add('hidden');
  startBtn.classList.add('hidden');
  stopBtn.classList.remove('hidden');
  isCameraActive = true;
  toast('Webcam active — Localizing diseases 🎥', 'success');
}

function stopCamera() {
  const stream = document.getElementById('webcam-stream');
  const placeholder = document.getElementById('camera-placeholder');
  const startBtn = document.getElementById('btn-camera-start');
  const stopBtn = document.getElementById('btn-camera-stop');

  stream.src = '';
  stream.classList.add('hidden');
  placeholder.classList.remove('hidden');
  startBtn.classList.remove('hidden');
  stopBtn.classList.add('hidden');
  isCameraActive = false;
}

function handleDrop(e) {
  e.preventDefault();
  document.getElementById('upload-zone').classList.remove('dragover');
  const file = e.dataTransfer.files[0];
  if (file) previewFile(file);
}

function handleFileSelect(e) {
  const file = e.target.files[0];
  if (file) previewFile(file);
}

function previewFile(file) {
  selectedFile = file;
  const url = URL.createObjectURL(file);
  document.getElementById('image-preview').src = url;
  hide('upload-zone');
  show('image-preview-wrap');
  document.getElementById('btn-detect-model').disabled = false;
}

function clearImage() {
  selectedFile = null;
  document.getElementById('file-input').value = '';
  document.getElementById('image-preview').src = '';
  show('upload-zone');
  hide('image-preview-wrap');
  hide('detect-result');
  document.getElementById('btn-detect-model').disabled = true;
}

async function runModelDetection() {
  if (!selectedFile) return;

  showDetectLoader('Analysing crop image with AI…');
  hide('detect-result');

  try {
    const body = new FormData();
    body.append('image', selectedFile);

    const res = await fetch('/api/detection/model', { method: 'POST', body });
    const data = await res.json();

    hideDetectLoader();

    if (data.ok) {
      showResult({
        mode: 'Model',
        disease: data.disease,
        confidence: data.confidence,
        treatment: data.treatment,
        image_url: data.image_url,
        heatmap_url: data.heatmap_url,
      });
      toast('Detection complete! 🔬', 'success');
    } else {
      toast(data.error || 'Detection failed', 'error');
    }
  } catch (e) {
    hideDetectLoader();
    toast('Network error: ' + e.message, 'error');
  }
}

async function runAIDetection(e) {
  e.preventDefault();
  showDetectLoader('Consulting AI Expert…');
  hide('detect-result');

  const body = new FormData();
  body.append('leaf', document.getElementById('ai-leaf').value.trim());
  body.append('color', document.getElementById('ai-color').value.trim());
  body.append('symptoms', document.getElementById('ai-symptoms').value.trim());

  try {
    const res = await fetch('/api/detection/ai', { method: 'POST', body });
    const data = await res.json();
    hideDetectLoader();

    if (data.ok) {
      showResult({ mode: 'AI Expert', disease: 'AI Diagnosis', confidence: null, treatment: data.diagnosis });
      toast('AI diagnosis complete! 🧠', 'success');
    } else {
      toast(data.error || 'AI failed', 'error');
    }
  } catch (e) {
    hideDetectLoader();
    toast('Network error: ' + e.message, 'error');
  }
}

function showResult({ mode, disease, confidence, treatment, image_url, heatmap_url }) {
  document.getElementById('result-mode-badge').textContent = mode;
  document.getElementById('result-disease').textContent = disease;
  document.getElementById('result-treatment').textContent = treatment;

  const confWrap = document.getElementById('confidence-bar-wrap');
  if (confidence !== null && confidence !== undefined) {
    document.getElementById('result-confidence').textContent = `${confidence}%`;
    document.getElementById('confidence-fill').style.width = `${Math.min(confidence, 100)}%`;
    show(confWrap);
  } else {
    hide(confWrap);
  }

  const resultImages = document.getElementById('result-images');
  if (image_url) {
    document.getElementById('result-image').src = image_url;
    const heatmapEl = document.getElementById('result-heatmap');
    const heatmapBox = heatmapEl.closest('.image-box');

    if (heatmap_url) {
      heatmapEl.src = heatmap_url + '?t=' + Date.now();
      heatmapEl.onerror = () => {
        heatmapBox.classList.add('hidden');
        console.warn("Heatmap failed to load");
      };
      heatmapBox.classList.remove('hidden');
    } else {
      heatmapBox.classList.add('hidden');
    }
    show(resultImages);
  } else {
    hide(resultImages);
  }

  show('detect-result');
  document.getElementById('detect-result').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function showDetectLoader(text) {
  document.getElementById('detect-loader-text').textContent = text || 'Processing…';
  show('detect-loader');
}
function hideDetectLoader() { hide('detect-loader'); }

// ── Farm Page ─────────────────────────────────────────────────────────────
async function handleFarmRegister(e) {
  e.preventDefault();
  const errEl = document.getElementById('farm-error');
  const sucEl = document.getElementById('farm-success');
  hide(errEl); hide(sucEl);

  const lat = document.getElementById('farm-lat').value;
  const lng = document.getElementById('farm-lng').value;

  if (!lat || !lng) {
    showError(errEl, 'Please select a location on the map.');
    return;
  }

  const body = new FormData();
  body.append('crop_type', document.getElementById('farm-crop').value.trim());
  body.append('area_acres', document.getElementById('farm-area').value);
  body.append('soil_type', document.getElementById('farm-soil').value.trim());
  body.append('latitude', lat);
  body.append('longitude', lng);

  try {
    const res = await fetch('/api/farm/register', { method: 'POST', body });
    const data = await res.json();
    if (data.ok) {
      show(sucEl); sucEl.textContent = '✓ Farm registered successfully!';
      e.target.reset();
      if (registrationMarker) {
        registrationMap.removeLayer(registrationMarker);
        registrationMarker = null;
      }
      loadMyFarms();
      toast('Farm registered! 🌾', 'success');
    } else {
      showError(errEl, data.error);
    }
  } catch (err) { showError(errEl, err.message); }
}

// ── Maps Implementation ───────────────────────────────────────────────────

function initRegistrationMap() {
  if (registrationMap) return; // Only init once

  // Center on India
  registrationMap = L.map('farm-reg-map').setView([20.5937, 78.9629], 5);

  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; CartoDB'
  }).addTo(registrationMap);

  registrationMap.on('click', function (e) {
    const { lat, lng } = e.latlng;

    if (registrationMarker) {
      registrationMarker.setLatLng(e.latlng);
    } else {
      const pinIcon = L.divIcon({
        className: 'custom-div-icon',
        html: `<div style="background-color:var(--accent); width:18px; height:18px; border-radius:50%; border:3px solid #fff; box-shadow:0 0 15px var(--accent-glow);"></div>`,
        iconSize: [18, 18],
        iconAnchor: [9, 9]
      });
      registrationMarker = L.marker(e.latlng, { draggable: true, icon: pinIcon }).addTo(registrationMap);
      registrationMarker.on('dragend', function () {
        const pos = registrationMarker.getLatLng();
        document.getElementById('farm-lat').value = pos.lat.toFixed(6);
        document.getElementById('farm-lng').value = pos.lng.toFixed(6);
      });
    }

    document.getElementById('farm-lat').value = lat.toFixed(6);
    document.getElementById('farm-lng').value = lng.toFixed(6);
  });

  // Ensure map resizes correctly if container was hidden during init
  setTimeout(() => registrationMap.invalidateSize(), 300);
}

function initViewMap() {
  if (!viewMap) {
    viewMap = L.map('main-farm-map', { zoomControl: false }).setView([20.5937, 78.9629], 5);
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; CartoDB'
    }).addTo(viewMap);
    L.control.zoom({ position: 'bottomright' }).addTo(viewMap);

    farmCluster = L.markerClusterGroup();
    viewMap.addLayer(farmCluster);
  } else {
    viewMap.invalidateSize();
  }

  loadMapData();
}

async function loadMapData() {
  try {
    const res = await fetch('/api/farm/map-data');
    const farms = await res.json();

    farmCluster.clearLayers();
    const bounds = [];

    farms.forEach(f => {
      if (!f.latitude || !f.longitude) return;

      const pos = [f.latitude, f.longitude];
      bounds.push(pos);

      // Select marker color based on status
      let markerColor = '#00ff88'; // success
      if (f.status === 'Disease Detected') markerColor = '#ffcc33'; // warning
      if (f.status === 'High Risk') markerColor = '#ff5e5e'; // danger

      const customIcon = L.divIcon({
        className: 'custom-div-icon',
        html: `<div style="background-color:${markerColor}; width:16px; height:16px; border-radius:50%; border:2px solid #fff; box-shadow:0 0 15px ${markerColor}aa; cursor:pointer;"></div>`,
        iconSize: [16, 16],
        iconAnchor: [8, 8]
      });

      const marker = L.marker(pos, { icon: customIcon });

      const popupContent = `
        <div style="font-family:var(--font); padding:5px; min-width:180px;">
          <h4 style="margin:0 0 8px; color:#e4f5ec; border-bottom:1px solid var(--card-border); padding-bottom:5px;">🌾 Farm #${f.farm_id}</h4>
          <p style="margin:3px 0; font-size:0.9rem;"><b>Crop:</b> ${f.crop_type}</p>
          <p style="margin:3px 0; font-size:0.9rem;"><b>AI Health:</b> <span style="color:${markerColor}">${f.latest_disease}</span></p>
          
          <div id="popup-weather-${f.farm_id}" style="margin-top:10px; padding-top:8px; border-top:1px dashed #444;">
             <div style="font-size:0.75rem; color:#888; text-transform:uppercase;">Real-time Weather</div>
             <div class="weather-loading" style="font-size:0.85rem; color:var(--accent); margin-top:4px;">⏳ Loading environmental risk...</div>
          </div>

          <div id="popup-ndvi-${f.farm_id}" style="margin-top:10px; padding-top:8px; border-top:1px dashed #444;">
             <div style="font-size:0.75rem; color:#888; text-transform:uppercase;">Satellite Monitoring</div>
             <div class="ndvi-loading" style="font-size:0.85rem; color:var(--accent); margin-top:4px;">📡 Syncing NDVI analysis...</div>
          </div>
        </div>
      `;

      marker.bindPopup(popupContent);

      marker.on('click', () => {
        fetchWeatherForPopup(f.farm_id);
        fetchWeatherInsight(f.farm_id);
        fetchNdviForPopup(f.farm_id);
        fetchNdviInsight(f.farm_id);
      });

      farmCluster.addLayer(marker);
    });

    if (bounds.length > 0) {
      viewMap.fitBounds(bounds, { padding: [50, 50] });
    }
  } catch (e) {
    console.error('Error loading map data:', e);
    toast('Error loading map data', 'error');
  }
}

async function loadMyFarms() {
  const container = document.getElementById('my-farms-list');
  container.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem">Loading…</p>';

  try {
    const res = await fetch('/api/farm/my-farms');
    const data = await res.json();

    if (!data.length) {
      container.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem">No farms registered yet.</p>';
      return;
    }

    container.innerHTML = data.map(f => `
      <div class="farm-card">
        <div class="farm-icon">🌾</div>
        <div class="farm-details">
          <div class="farm-crop">${f.crop_type}</div>
          <div class="farm-meta">🪨 ${f.soil_type} &nbsp;|&nbsp; 📐 ${f.area_acres} acres &nbsp;|&nbsp; ID #${f.farm_id}</div>
        </div>
      </div>
    `).join('');
  } catch (e) {
    container.innerHTML = '<p style="color:var(--danger)">Error loading farms.</p>';
  }
}

// ── History Page ──────────────────────────────────────────────────────────
async function loadHistory() {
  const search = document.getElementById('hist-search').value.trim();
  const mode = document.getElementById('hist-mode').value;
  const dateFrom = document.getElementById('hist-from').value;
  const dateTo = document.getElementById('hist-to').value;

  const params = new URLSearchParams({ search, mode, date_from: dateFrom, date_to: dateTo });
  const container = document.getElementById('history-list');
  container.innerHTML = '<p style="color:var(--text-muted);padding:1rem">Loading…</p>';

  try {
    const res = await fetch(`/api/history/list?${params}`);
    const rows = await res.json();

    if (!rows.length) {
      container.innerHTML = '<p style="color:var(--text-muted);padding:1rem">No records found.</p>';
      return;
    }

    container.innerHTML = rows.map(r => `
      <div class="history-card">
        ${r.image_path
        ? `<img class="history-thumb" src="${r.image_path}" alt="Detection" onerror="this.style.display='none'" />`
        : ''}
        <div class="history-body">
          <div class="history-disease">
            ${r.disease_name || 'AI Diagnosis'}
            <span class="history-badge ${r.mode === 'model' ? 'badge-model' : 'badge-ai'}">${r.mode}</span>
          </div>
          <div class="history-meta">
            ${r.confidence ? `🎯 Confidence: <strong>${r.confidence}%</strong> &nbsp;|&nbsp; ` : ''}
            ${r.leaf_name ? `🍃 Leaf: ${r.leaf_name} &nbsp;|&nbsp; ` : ''}
            ${r.leaf_color ? `🎨 Colour: ${r.leaf_color} &nbsp;|&nbsp; ` : ''}
            📅 ${r.created_at ? r.created_at.slice(0, 16) : '—'}
            ${r.symptoms ? `<br/>📝 ${r.symptoms}` : ''}
          </div>
        </div>
        <div class="history-actions">
          <button class="btn-danger" onclick="deleteHistory(${r.id})">🗑 Delete</button>
        </div>
      </div>
    `).join('');
  } catch (e) {
    container.innerHTML = `<p style="color:var(--danger)">Error: ${e.message}</p>`;
  }
}

async function deleteHistory(id) {
  if (!confirm('Delete this detection record?')) return;
  try {
    const res = await fetch(`/api/history/${id}`, { method: 'DELETE' });
    const d = await res.json();
    if (d.ok) { loadHistory(); toast('Record deleted', 'success'); }
    else toast(d.error, 'error');
  } catch (e) { toast('Delete failed', 'error'); }
}

// ── Report Page ───────────────────────────────────────────────────────────
async function loadReport() {
  const wrap = document.getElementById('report-table-wrap');
  show(wrap);
  wrap.innerHTML = '<p style="color:var(--text-muted);padding:1rem">Loading report…</p>';

  try {
    const res = await fetch('/api/report/');
    const data = await res.json();
    const rows = data.history || [];

    if (!rows.length) {
      wrap.innerHTML = '<p style="color:var(--text-muted);padding:1rem">No data available.</p>';
      return;
    }

    wrap.innerHTML = `
      <table class="report-table">
        <thead>
          <tr>
            <th>#</th><th>Mode</th><th>Disease</th><th>Confidence</th>
            <th>Leaf</th><th>Colour</th><th>Symptoms</th><th>Date</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((r, i) => `
            <tr>
              <td>${i + 1}</td>
              <td><span class="history-badge ${r.mode === 'model' ? 'badge-model' : 'badge-ai'}">${r.mode}</span></td>
              <td>${r.disease_name || '—'}</td>
              <td>${r.confidence ? r.confidence + '%' : '—'}</td>
              <td>${r.leaf_name || '—'}</td>
              <td>${r.leaf_color || '—'}</td>
              <td>${r.symptoms || '—'}</td>
              <td>${r.created_at ? r.created_at.slice(0, 16) : '—'}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  } catch (e) {
    wrap.innerHTML = `<p style="color:var(--danger)">Error: ${e.message}</p>`;
  }
}

// ── Profile Page ──────────────────────────────────────────────────────────
async function loadProfile() {
  try {
    const res = await fetch('/api/auth/profile');
    if (res.status === 401) return location.reload();
    const data = await res.json();

    setText('prof-name', data.name);
    setText('prof-aadhaar', data.aadhaar_masked);
    setText('prof-village', data.village);
    setText('prof-phone', data.phone);
    setText('prof-det-count', data.detection_count || 0);
    setText('prof-farm-count', data.farm_count || 0);
  } catch (e) {
    toast('Error loading profile', 'error');
  }
}

function openUpdateProfile() {
  const v = document.getElementById('prof-village').textContent;
  const p = document.getElementById('prof-phone').textContent;

  const village = prompt('Enter new village name:', v === '—' ? '' : v);
  if (village === null) return;
  const phone = prompt('Enter new 10-digit phone number:', p === '—' ? '' : p);
  if (phone === null) return;

  updateProfile(village, phone);
}

async function updateProfile(village, phone) {
  const body = new FormData();
  body.append('village', village);
  body.append('phone', phone);

  try {
    const res = await fetch('/api/auth/profile', { method: 'PUT', body });
    const data = await res.json();
    if (data.ok) {
      toast('Profile updated successfully! ✅', 'success');
      loadProfile();
    } else {
      toast(data.error || 'Update failed', 'error');
    }
  } catch (e) { toast('Network error', 'error'); }
}

// ── Helpers ───────────────────────────────────────────────────────────────
function showTab(tab) {
  document.getElementById('tab-login').classList.toggle('active', tab === 'login');
  document.getElementById('tab-register').classList.toggle('active', tab === 'register');
  document.getElementById('login-form').classList.toggle('hidden', tab !== 'login');
  document.getElementById('register-form').classList.toggle('hidden', tab !== 'register');
}

function show(el) {
  const e = typeof el === 'string' ? document.getElementById(el) : el;
  if (e) e.classList.remove('hidden');
}
function hide(el) {
  const e = typeof el === 'string' ? document.getElementById(el) : el;
  if (e) e.classList.add('hidden');
}
function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val ?? '—';
}
function showError(el, msg) {
  if (el) { el.textContent = msg; el.classList.remove('hidden'); }
}
function setLoading(btn, loading) {
  if (!btn) return;
  btn.disabled = loading;
  const txt = btn.querySelector('.btn-text');
  if (txt) txt.textContent = loading ? 'Processing…' : 'Login';
}

function shortenLabel(label) {
  if (!label) return 'Unknown';
  return label.length > 22 ? label.slice(0, 20) + '…' : label;
}

let toastTimer;
function toast(msg, type = 'success') {
  const el = document.getElementById('toast');
  if (!el) return;
  el.textContent = msg;
  el.className = `toast ${type}`;
  el.classList.remove('hidden');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add('hidden'), 3400);
}

// Drag-over highlight
document.addEventListener('DOMContentLoaded', () => {
  const zone = document.getElementById('upload-zone');
  if (!zone) return;
  zone.addEventListener('dragover', () => zone.classList.add('dragover'));
  zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));

  // Background session check
  setInterval(async () => {
    const res = await fetch('/api/auth/me');
    const data = await res.json();
    if (!data.logged_in && !document.getElementById('auth-screen').classList.contains('hidden')) {
      // already on auth screen
    } else if (!data.logged_in) {
      location.reload(); // session expired
    }
  }, 60000); // Check every minute
});

// ── Weather & Disease Insights ─────────────────────────────────────────────

async function fetchWeatherForPopup(id) {
  const container = document.getElementById('popup-weather-' + id);
  if (!container) return;

  try {
    const res = await fetch('/api/farm/farm-weather/' + id);
    const data = await res.json();

    if (!data.ok) throw new Error(data.error);

    const riskColor = data.disease_risk === 'HIGH' ? '#ff4444' : (data.disease_risk === 'MEDIUM' ? '#ffbb33' : '#00C851');

    container.innerHTML = `
      <div style="font-size:0.75rem; color:#888; text-transform:uppercase; margin-bottom:5px;">Real-time Weather</div>
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:5px; font-size:0.85rem;">
        <span style="color:#e4f5ec">🌡️ ${data.temperature}°C</span>
        <span style="color:#e4f5ec">💧 ${data.humidity}%</span>
        <span style="color:#e4f5ec">🌧️ ${data.rainfall}mm</span>
        <span style="color:#e4f5ec">💨 ${data.wind_speed}m/s</span>
      </div>
      <div style="margin-top:8px; display:flex; align-items:center; gap:5px; font-size:0.92rem; font-weight:600;">
        <span style="color:${riskColor}">⚠️ ${data.disease_risk} RISK</span>
      </div>
      <div style="font-size:0.8rem; font-style:italic; color:var(--text-muted);">${data.possible_disease}</div>
    `;
  } catch (err) {
    container.innerHTML = `<div style="color:var(--danger); font-size:0.8rem;">Weather data failed...</div>`;
  }
}

async function fetchWeatherInsight(id) {
  const wrap = document.getElementById('weather-insights-wrap');
  if (!wrap) return;

  wrap.classList.remove('hidden');

  try {
    const res = await fetch('/api/farm/farm-weather/' + id);
    const data = await res.json();

    if (!data.ok) throw new Error(data.error);

    document.getElementById('weather-farm-name').textContent = 'Farm #' + id + ' (' + data.crop + ')';
    document.getElementById('weather-temp').textContent = Math.round(data.temperature) + '°C';
    document.getElementById('weather-hum').textContent = data.humidity + '%';
    document.getElementById('weather-rain').textContent = (data.rainfall || 0) + 'mm';
    document.getElementById('weather-wind').textContent = data.wind_speed + 'm/s';

    const riskBadge = document.getElementById('weather-risk-badge');
    riskBadge.textContent = data.disease_risk + ' RISK';
    riskBadge.className = 'risk-badge ' + data.disease_risk.toLowerCase();

    document.getElementById('weather-predicted-disease').textContent = data.possible_disease;

    const recs = {
      'LOW': 'Environmental conditions are stable. Continue regular irrigation and monitor for early signs of pests.',
      'MEDIUM': 'Risk is increasing due to existing humidity. Consider reducing evening irrigation and checking lower leaves.',
      'HIGH': 'CRITICAL! High humidity and temperature detected. Apply preventive fungicide (e.g., Azoxystrobin) immediately to prevent spreading.'
    };

    document.getElementById('weather-recommendation').textContent = recs[data.disease_risk] || 'Monitor closely.';

  } catch (err) {
    console.warn('Weather sync error:', err);
  }
}

// ── NDVI & Satellite Insights ────────────────────────────────────────────────

async function fetchNdviForPopup(id) {
  const container = document.getElementById('popup-ndvi-' + id);
  if (!container) return;

  try {
    const res = await fetch('/api/farm/farm-ndvi/' + id);
    const data = await res.json();

    if (!data.ok) throw new Error(data.error);

    let healthColor = '#ef4444'; // Red for poor
    if (data.ndvi_value >= 0.6) healthColor = '#22c55e'; // Green for healthy
    else if (data.ndvi_value >= 0.4) healthColor = '#eab308'; // Yellow for moderate

    container.innerHTML = `
            <div style="font-size:0.75rem; color:#888; text-transform:uppercase; margin-bottom:5px;">Satellite Crop Health</div>
            <div style="display:flex; flex-direction:column; gap:2px;">
                <div style="font-size:0.95rem; font-weight:700; color:${healthColor}">NDVI: ${data.ndvi_value}</div>
                <div style="font-size:0.8rem; color:#e4f5ec">Health: ${data.crop_health}</div>
            </div>
        `;
  } catch (err) {
    container.innerHTML = `<div style="color:var(--danger); font-size:0.8rem;">Satellite data unavailable</div>`;
  }
}

async function fetchNdviInsight(id) {
  const wrap = document.getElementById('ndvi-insights-wrap');
  if (!wrap) return;

  wrap.classList.remove('hidden');

  try {
    const res = await fetch('/api/farm/farm-ndvi/' + id);
    const data = await res.json();

    if (!data.ok) throw new Error(data.error);

    document.getElementById('ndvi-farm-name').textContent = 'Farm #' + id;
    document.getElementById('ndvi-value-display').textContent = data.ndvi_value;
    document.getElementById('ndvi-date').textContent = 'Satellite Image: ' + data.last_satellite_date;
    document.getElementById('ndvi-interpretation').textContent = data.crop_health;

    // Progress bar percentage calculation
    const percentage = Math.max(0, Math.min(100, data.ndvi_value * 100));
    const progressBar = document.getElementById('ndvi-progress-bar');
    progressBar.style.width = percentage + '%';

    const healthBadge = document.getElementById('ndvi-health-badge');
    healthBadge.textContent = data.crop_health.toUpperCase();

    // Color coding
    if (data.ndvi_value >= 0.6) {
      progressBar.style.background = '#22c55e';
      healthBadge.style.color = '#22c55e';
    } else if (data.ndvi_value >= 0.4) {
      progressBar.style.background = '#eab308';
      healthBadge.style.color = '#eab308';
    } else {
      progressBar.style.background = '#ef4444';
      healthBadge.style.color = '#ef4444';
    }

  } catch (err) {
    console.warn('NDVI sync error:', err);
  }
}
