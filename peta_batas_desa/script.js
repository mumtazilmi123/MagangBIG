// ================================================================
// AUDIT PETA BATAS DESA — Dashboard JS Engine
// ================================================================

'use strict';

// ── State ──
const API_BASE = 'http://localhost:8001';
let currentAuditData = null;
let currentFilter = 'all';

// ── DOM References (resolved after DOMContentLoaded) ──
let dropZone, fileInput, browseBtn, processBtn, fileBadge, fileNameSpan,
    btnRemoveFile, errorBox, progressModal, progressBar, progressPct,
    resultsSection;

// ================================================================
// INIT
// ================================================================
document.addEventListener('DOMContentLoaded', () => {
    dropZone     = document.getElementById('drop-zone');
    fileInput    = document.getElementById('file-input');
    browseBtn    = document.getElementById('btn-browse');
    processBtn   = document.getElementById('btn-process');
    fileBadge    = document.getElementById('file-selected-badge');
    fileNameSpan = document.getElementById('file-name-display');
    btnRemoveFile= document.getElementById('btn-remove-file');
    errorBox     = document.getElementById('error-box');
    progressModal= document.getElementById('progress-modal');
    progressBar  = document.getElementById('prog-fill');
    progressPct  = document.getElementById('prog-pct');
    resultsSection=document.getElementById('results-section');

    // Dropzone events
    dropZone.addEventListener('click', () => fileInput.click());
    browseBtn.addEventListener('click', (e) => { e.stopPropagation(); fileInput.click(); });

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
        const files = e.dataTransfer.files;
        if (files.length > 0) handleFileSelected(files[0]);
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) handleFileSelected(fileInput.files[0]);
    });

    btnRemoveFile.addEventListener('click', (e) => {
        e.stopPropagation();
        clearFile();
    });

    processBtn.addEventListener('click', startAudit);

    // Filter buttons
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentFilter = btn.dataset.filter;
            applyFilter(currentFilter);
        });
    });

    // Health check on load
    checkApiHealth();
});

// ================================================================
// HEALTH CHECK
// ================================================================
async function checkApiHealth() {
    try {
        const res = await fetch(`${API_BASE}/api/peta/health`, { method: 'GET' });
        if (res.ok) {
            setApiStatus(true);
        } else {
            setApiStatus(false);
        }
    } catch {
        setApiStatus(false);
    }
}

function setApiStatus(online) {
    const dot  = document.getElementById('api-status-dot');
    const text = document.getElementById('api-status-text');
    if (!dot || !text) return;
    if (online) {
        dot.style.background = '#10B981';
        text.textContent = 'Server Online';
    } else {
        dot.style.background = '#EF4444';
        text.textContent = 'Server Offline — Jalankan backend terlebih dahulu';
    }
}

// ================================================================
// FILE HANDLING
// ================================================================
let selectedFile = null;

function handleFileSelected(file) {
    const ext = file.name.split('.').pop().toLowerCase();
    const allowed = ['pdf', 'jpg', 'jpeg', 'png', 'tiff', 'tif'];
    if (!allowed.includes(ext)) {
        showError(`Format file tidak didukung: .${ext}. Gunakan PDF, JPG, PNG, atau TIFF.`);
        return;
    }
    if (file.size > 50 * 1024 * 1024) {
        showError('Ukuran file melebihi batas 50 MB.');
        return;
    }

    selectedFile = file;
    hideError();
    fileNameSpan.textContent = file.name + ` (${formatSize(file.size)})`;
    fileBadge.classList.remove('hidden');
    processBtn.disabled = false;
}

function clearFile() {
    selectedFile = null;
    fileInput.value = '';
    fileBadge.classList.add('hidden');
    processBtn.disabled = true;
}

function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1024 / 1024).toFixed(1) + ' MB';
}

// ================================================================
// AUDIT PROCESS
// ================================================================
const STEPS = [
    { id: 1, label: 'Preprocessing', desc: 'Konversi file → gambar, normalisasi resolusi...' },
    { id: 2, label: 'OCR & Ekstraksi Teks', desc: 'Membaca teks dari peta menggunakan Tesseract OCR...' },
    { id: 3, label: 'Deteksi Layout', desc: 'Mendeteksi region judul, legenda, inset, body peta...' },
    { id: 4, label: 'Computer Vision', desc: 'Mendeteksi arah utara, skala grafis, grid, batas...' },
    { id: 5, label: 'Validasi Komponen', desc: 'Memeriksa 16 komponen wajib Template BIG...' },
    { id: 6, label: 'Ekstraksi Titik Kartometrik', desc: 'Membaca tabel koordinat batas desa...' },
    { id: 7, label: 'Generate Laporan', desc: 'Menyusun laporan audit dan statistik kelengkapan...' },
];

async function startAudit() {
    if (!selectedFile) return;

    hideError();
    showProgressModal();
    resultsSection.classList.remove('visible');

    const formData = new FormData();
    formData.append('file', selectedFile);

    // Simulate step progression
    let stepIdx = 0;
    const stepTimer = setInterval(() => {
        if (stepIdx < STEPS.length) {
            setStep(stepIdx, 'running');
            if (stepIdx > 0) setStep(stepIdx - 1, 'done');
            const pct = Math.round((stepIdx / STEPS.length) * 85);
            setProgress(pct);
            stepIdx++;
        }
    }, 800);

    try {
        const res = await fetch(`${API_BASE}/api/peta/audit`, {
            method: 'POST',
            body: formData
        });

        clearInterval(stepTimer);

        if (!res.ok) {
            let errMsg = `HTTP ${res.status}`;
            try { const j = await res.json(); errMsg = j.detail || errMsg; } catch {}
            throw new Error(errMsg);
        }

        const data = await res.json();

        // Mark all steps done
        STEPS.forEach((_, i) => setStep(i, 'done'));
        setProgress(100);

        await sleep(600);
        hideProgressModal();

        currentAuditData = data;
        renderDashboard(data);
        resultsSection.classList.add('visible');
        resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

    } catch (err) {
        clearInterval(stepTimer);
        hideProgressModal();
        showError(`Audit gagal: ${err.message || 'Terjadi kesalahan tidak terduga.'}`);
    }
}

// ================================================================
// PROGRESS MODAL
// ================================================================
function showProgressModal() {
    // Reset steps
    STEPS.forEach((s, i) => {
        renderStep(s, i, 'pending');
    });
    setProgress(0);
    progressModal.classList.remove('hidden');
}
function hideProgressModal() {
    progressModal.classList.add('hidden');
}
function setProgress(pct) {
    progressBar.style.width = pct + '%';
    progressPct.textContent = pct + '%';
}
function setStep(idx, state) {
    const dot = document.getElementById(`step-dot-${idx}`);
    if (!dot) return;
    dot.className = 'step-dot ' + state;
    if (state === 'done') dot.innerHTML = '<i class="fa-solid fa-check" style="font-size:0.65rem;"></i>';
    else if (state === 'running') dot.innerHTML = '<i class="fa-solid fa-spinner spin" style="font-size:0.65rem;"></i>';
    else dot.innerHTML = (idx + 1);
}
function renderStep(step, idx, state) {
    // Created in HTML, just reset
    const dot = document.getElementById(`step-dot-${idx}`);
    if (dot) {
        dot.className = 'step-dot pending';
        dot.innerHTML = (idx + 1);
    }
}

// ================================================================
// RENDER DASHBOARD
// ================================================================
function renderDashboard(data) {
    // Status banner
    renderBanner(data);
    // Stat cards
    renderStatCards(data);
    // Audit table
    renderAuditTable(data.components || []);
    // Titik kartometrik
    renderTitikKartometrik(data.titik_kartometrik || {});
    // Reset filter
    currentFilter = 'all';
    document.querySelectorAll('.filter-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.filter === 'all');
    });
}

// ── Banner ──
function renderBanner(data) {
    const banner    = document.getElementById('audit-banner');
    const icon      = document.getElementById('banner-icon');
    const filename  = document.getElementById('banner-filename');
    const status    = document.getElementById('banner-status');
    const timestamp = document.getElementById('banner-ts');

    const colorMap = {
        green:  ['audit-banner-green',  'banner-icon-green',  'fa-circle-check'],
        yellow: ['audit-banner-yellow', 'banner-icon-yellow', 'fa-triangle-exclamation'],
        red:    ['audit-banner-red',    'banner-icon-red',    'fa-circle-xmark'],
    };
    const clr = data.audit_status_color || 'yellow';
    const [bannerClass, iconClass, iconName] = colorMap[clr] || colorMap.yellow;

    banner.className = `audit-banner ${bannerClass} anim-fade-in`;
    banner.style.display = '';    // ensure visible
    icon.className   = `banner-icon ${iconClass}`;
    icon.innerHTML   = `<i class="fa-solid ${iconName}"></i>`;

    filename.textContent  = data.filename || '-';
    status.textContent    = data.audit_status_label || data.audit_status || '-';
    timestamp.textContent = `Waktu Audit: ${formatTimestamp(data.audit_timestamp)}`;
}

// ── Stat Cards ──
function renderStatCards(data) {
    setText('stat-completeness', (data.completeness_percent || 0).toFixed(1) + '%');
    setText('stat-found',        data.found_count     || 0);
    setText('stat-notfound',     data.not_found_count || 0);
    setText('stat-uncertain',    data.uncertain_count || 0);
    setText('stat-confidence',   ((data.avg_confidence || 0) * 100).toFixed(0) + '%');
    setText('stat-total',        data.total_components || 0);
}

// ── Audit Table ──
function renderAuditTable(components) {
    const tbody = document.getElementById('audit-tbody');
    tbody.innerHTML = '';

    components.forEach((comp, idx) => {
        // Main row
        const tr = document.createElement('tr');
        tr.className = comp.is_optional ? 'optional-row' : '';
        tr.dataset.status   = comp.status;
        tr.dataset.optional = comp.is_optional ? '1' : '0';
        tr.innerHTML = `
            <td class="col-no">${comp.no}</td>
            <td class="col-component">
                <div style="font-weight:600; color:var(--text-bright); margin-bottom:2px;">${esc(comp.name)}</div>
                ${comp.is_optional ? '<span style="font-size:0.70rem; color:var(--text-muted);">(Opsional)</span>' : ''}
            </td>
            <td class="col-status">${renderBadge(comp.status)}</td>
            <td class="col-conf">${renderConfBar(comp.confidence)}</td>
            <td class="col-method"><span class="method-tag">${esc(comp.method || '-')}</span></td>
            <td class="col-evidence"><span class="evidence-text">${esc(comp.evidence || '-')}</span></td>
            <td class="col-value"><span class="value-text">${esc(comp.value || '-')}</span></td>
            <td class="col-notes"><span class="notes-text">${esc(comp.notes || '')}</span></td>
            <td class="col-expand">
                <button class="btn-expand" id="expand-btn-${idx}" onclick="toggleDetail(${idx})" title="Lihat Detail">
                    <i class="fa-solid fa-chevron-down"></i> Detail
                </button>
            </td>
        `;
        tbody.appendChild(tr);

        // Detail row
        const detailTr = document.createElement('tr');
        detailTr.className = 'detail-row';
        detailTr.id = `detail-row-${idx}`;
        detailTr.dataset.status   = comp.status;
        detailTr.dataset.optional = comp.is_optional ? '1' : '0';
        detailTr.innerHTML = `
            <td colspan="9" style="padding:4px 14px 12px;">
                <div class="detail-panel">
                    <div class="detail-grid">
                        <div class="detail-item">
                            <label>Komponen</label>
                            <span>${esc(comp.name)}</span>
                        </div>
                        <div class="detail-item">
                            <label>Status</label>
                            <span>${esc(comp.status_label)}</span>
                        </div>
                        <div class="detail-item">
                            <label>Confidence</label>
                            <span>${((comp.confidence || 0) * 100).toFixed(0)}%</span>
                        </div>
                        <div class="detail-item">
                            <label>Metode</label>
                            <span>${esc(comp.method || '-')}</span>
                        </div>
                        <div class="detail-item">
                            <label>Nilai Diekstrak</label>
                            <span>${esc(comp.value || '-')}</span>
                        </div>
                        <div class="detail-item">
                            <label>Bounding Box</label>
                            <span>${comp.bbox ? JSON.stringify(comp.bbox) : '-'}</span>
                        </div>
                    </div>
                    ${comp.evidence && comp.evidence !== '-' ? `
                    <div class="detail-evidence">
                        <strong style="color:var(--primary-hover);">Evidence:</strong> ${esc(comp.evidence)}
                    </div>` : ''}
                    ${comp.notes ? `
                    <div class="detail-notes">
                        <i class="fa-solid fa-circle-exclamation"></i>
                        <strong>Catatan:</strong> ${esc(comp.notes)}
                    </div>` : ''}
                </div>
            </td>
        `;
        tbody.appendChild(detailTr);
    });
}

// ── Expand/Collapse Detail ──
function toggleDetail(idx) {
    const detailRow = document.getElementById(`detail-row-${idx}`);
    const btn       = document.getElementById(`expand-btn-${idx}`);
    if (!detailRow) return;

    const isVisible = detailRow.classList.contains('visible');
    detailRow.classList.toggle('visible', !isVisible);
    btn.classList.toggle('expanded', !isVisible);
    btn.innerHTML = isVisible
        ? '<i class="fa-solid fa-chevron-down"></i> Detail'
        : '<i class="fa-solid fa-chevron-up"></i> Tutup';
}

// ── Filter ──
function applyFilter(filter) {
    const rows = document.querySelectorAll('#audit-tbody tr');
    rows.forEach(tr => {
        if (tr.classList.contains('detail-row')) {
            // Detail rows follow their parent
            return;
        }
        const status   = tr.dataset.status;
        const optional = tr.dataset.optional === '1';

        let visible = false;
        if (filter === 'all') {
            visible = true;
        } else if (filter === 'found') {
            visible = status === 'found';
        } else if (filter === 'uncertain') {
            visible = status === 'uncertain';
        } else if (filter === 'not_found') {
            visible = status === 'not_found';
        }

        tr.classList.toggle('hidden-row', !visible);
    });

    // Also hide detail rows of hidden parents
    const allRows = document.querySelectorAll('#audit-tbody tr');
    allRows.forEach((tr, i) => {
        if (tr.classList.contains('detail-row')) {
            // Check previous sibling
            const prev = allRows[i - 1];
            if (prev && prev.classList.contains('hidden-row')) {
                tr.classList.add('hidden-row');
                tr.classList.remove('visible');
            } else if (prev) {
                tr.classList.remove('hidden-row');
            }
        }
    });
}

// ── Titik Kartometrik ──
function renderTitikKartometrik(kartData) {
    const tbody  = document.getElementById('kartometrik-tbody');
    const method = document.getElementById('kartometrik-method');
    const total  = document.getElementById('kartometrik-total');
    const emptyMsg = document.getElementById('kartometrik-empty');

    if (!tbody) return;

    const rows = kartData.rows || [];
    tbody.innerHTML = '';

    if (method) method.textContent = kartData.method || '-';
    if (total)  total.textContent  = rows.length + ' Titik';

    if (rows.length === 0) {
        tbody.parentElement.style.display = 'none';
        if (emptyMsg) emptyMsg.classList.remove('hidden');
        return;
    }

    tbody.parentElement.style.display = '';
    if (emptyMsg) emptyMsg.classList.add('hidden');

    rows.forEach((row, i) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td style="text-align:center; font-weight:600; color:var(--text-muted);">${esc(row.no || (i+1).toString())}</td>
            <td style="font-weight:600; color:var(--text-bright);">${esc(row.kode || '-')}</td>
            <td>${esc(row.lintang || '-')}</td>
            <td>${esc(row.bujur || '-')}</td>
            <td>${esc(row.x || '-')}</td>
            <td>${esc(row.y || '-')}</td>
        `;
        tbody.appendChild(tr);
    });
}

// ================================================================
// RENDER HELPERS
// ================================================================
function renderBadge(status) {
    if (status === 'found')
        return '<span class="badge badge-found"><i class="fa-solid fa-check"></i> Ditemukan</span>';
    if (status === 'uncertain')
        return '<span class="badge badge-uncertain"><i class="fa-solid fa-triangle-exclamation"></i> Tidak Dapat Dipastikan</span>';
    return '<span class="badge badge-notfound"><i class="fa-solid fa-xmark"></i> Tidak Ditemukan</span>';
}

function renderConfBar(conf) {
    const pct   = Math.round((conf || 0) * 100);
    let color   = '#EF4444';
    if (pct >= 70) color = '#10B981';
    else if (pct >= 40) color = '#F59E0B';

    return `
        <div class="conf-bar-wrap">
            <div class="conf-bar">
                <div class="conf-bar-fill" style="width:${pct}%; background:${color};"></div>
            </div>
            <span class="conf-val">${pct}%</span>
        </div>`;
}

function formatTimestamp(ts) {
    if (!ts) return '-';
    try {
        const d = new Date(ts);
        return d.toLocaleString('id-ID', {
            day: '2-digit', month: 'long', year: 'numeric',
            hour: '2-digit', minute: '2-digit'
        });
    } catch { return ts; }
}

function esc(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function setText(id, val) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
}

function showError(msg) {
    if (!errorBox) return;
    const span = errorBox.querySelector('span');
    if (span) span.textContent = msg;
    else errorBox.textContent = msg;
    errorBox.classList.remove('hidden');
}
function hideError() {
    if (!errorBox) return;
    errorBox.classList.add('hidden');
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
