// ================================================================
// PEMERIKSAAN DOKUMEN PETA BATAS DESA — Dynamic Document Inspection Engine
// ================================================================

'use strict';

// ── State ──
const API_BASE = 'http://localhost:8001';
let currentAuditData = null;
let currentFilter = 'all';
let selectedFile = null;
let currentBlobUrl = null;
let currentZoom = 1.0;
let isPanning = false;
let startX = 0, startY = 0;
let scrollLeft = 0, scrollTop = 0;

// ── DOM Elements ──
let dropZone, fileInput, browseBtn, processBtn, fileBadge, fileNameSpan,
    btnRemoveFile, errorBox, progressModal, progressBar, progressPct,
    uploadSection, resultsSection, docPreviewIframe, docPreviewImg, imageWrapper,
    viewerContainer, viewerPlaceholder, zoomBadge, btnZoomIn, btnZoomOut,
    btnZoomFit, btnZoomReset, btnOpenNewTab, btnReupload;

// ================================================================
// INIT
// ================================================================
document.addEventListener('DOMContentLoaded', () => {
    // Bind Elements
    dropZone          = document.getElementById('drop-zone');
    fileInput         = document.getElementById('file-input');
    browseBtn         = document.getElementById('btn-browse');
    processBtn        = document.getElementById('btn-process');
    fileBadge         = document.getElementById('file-selected-badge');
    fileNameSpan      = document.getElementById('file-name-display');
    btnRemoveFile     = document.getElementById('btn-remove-file');
    errorBox          = document.getElementById('error-box');
    progressModal     = document.getElementById('progress-modal');
    progressBar       = document.getElementById('prog-fill');
    progressPct       = document.getElementById('prog-pct');
    uploadSection     = document.getElementById('upload-section');
    resultsSection    = document.getElementById('results-section');

    docPreviewIframe  = document.getElementById('doc-preview-iframe');
    docPreviewImg     = document.getElementById('doc-preview-img');
    imageWrapper      = document.getElementById('image-wrapper');
    viewerContainer   = document.getElementById('viewer-container');
    viewerPlaceholder = document.getElementById('viewer-placeholder');
    zoomBadge         = document.getElementById('zoom-level-badge');

    btnZoomIn         = document.getElementById('btn-zoom-in');
    btnZoomOut        = document.getElementById('btn-zoom-out');
    btnZoomFit        = document.getElementById('btn-zoom-fit');
    btnZoomReset      = document.getElementById('btn-zoom-reset');
    btnOpenNewTab     = document.getElementById('btn-open-newtab');
    btnReupload      = document.getElementById('btn-reupload');

    // Dropzone Events
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

    if (btnReupload) {
        btnReupload.addEventListener('click', () => {
            resultsSection.classList.add('hidden');
            uploadSection.classList.remove('hidden');
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }

    // Dynamic Viewer Controls
    if (btnZoomIn) {
        btnZoomIn.addEventListener('click', () => {
            currentZoom = Math.min(currentZoom + 0.25, 4.0);
            applyZoom();
        });
    }
    if (btnZoomOut) {
        btnZoomOut.addEventListener('click', () => {
            currentZoom = Math.max(currentZoom - 0.25, 0.4);
            applyZoom();
        });
    }
    if (btnZoomFit) {
        btnZoomFit.addEventListener('click', () => {
            currentZoom = 1.0;
            if (docPreviewImg && viewerContainer) {
                const containerWidth = viewerContainer.clientWidth - 24;
                const imgWidth = docPreviewImg.naturalWidth || containerWidth;
                if (imgWidth > 0) {
                    currentZoom = Math.min(containerWidth / imgWidth, 1.5);
                }
            }
            applyZoom();
        });
    }
    if (btnZoomReset) {
        btnZoomReset.addEventListener('click', () => {
            currentZoom = 1.0;
            applyZoom();
        });
    }
    if (btnOpenNewTab) {
        btnOpenNewTab.addEventListener('click', () => {
            if (currentBlobUrl) window.open(currentBlobUrl, '_blank');
        });
    }

    // Mouse Wheel Zoom on Viewer Container
    if (viewerContainer) {
        viewerContainer.addEventListener('wheel', (e) => {
            if (docPreviewImg && !docPreviewImg.classList.contains('hidden')) {
                e.preventDefault();
                const delta = e.deltaY < 0 ? 0.15 : -0.15;
                currentZoom = Math.min(Math.max(currentZoom + delta, 0.4), 4.0);
                applyZoom();
            }
        }, { passive: false });

        // Grab & Pan Drag Scroll
        viewerContainer.addEventListener('mousedown', (e) => {
            isPanning = true;
            startX = e.pageX - viewerContainer.offsetLeft;
            startY = e.pageY - viewerContainer.offsetTop;
            scrollLeft = viewerContainer.scrollLeft;
            scrollTop = viewerContainer.scrollTop;
            viewerContainer.style.cursor = 'grabbing';
        });

        viewerContainer.addEventListener('mouseleave', () => {
            isPanning = false;
            if (viewerContainer) viewerContainer.style.cursor = 'grab';
        });

        viewerContainer.addEventListener('mouseup', () => {
            isPanning = false;
            if (viewerContainer) viewerContainer.style.cursor = 'grab';
        });

        viewerContainer.addEventListener('mousemove', (e) => {
            if (!isPanning) return;
            e.preventDefault();
            const x = e.pageX - viewerContainer.offsetLeft;
            const y = e.pageY - viewerContainer.offsetTop;
            const walkX = (x - startX) * 1.5;
            const walkY = (y - startY) * 1.5;
            viewerContainer.scrollLeft = scrollLeft - walkX;
            viewerContainer.scrollTop = scrollTop - walkY;
        });
    }

    // Double-click on Image to Toggle 200% Zoom
    if (docPreviewImg) {
        docPreviewImg.addEventListener('dblclick', () => {
            if (currentZoom === 1.0) currentZoom = 2.0;
            else currentZoom = 1.0;
            applyZoom();
        });
    }

    // Filter Buttons
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentFilter = btn.dataset.filter;
            applyFilter(currentFilter);
        });
    });

    // Tab Buttons
    document.querySelectorAll('.tab-btn[data-tab]').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            const target = document.getElementById(btn.dataset.tab);
            if (target) target.classList.add('active');
        });
    });

    // Health Check
    checkApiHealth();
});

// ================================================================
// HEALTH CHECK
// ================================================================
async function checkApiHealth() {
    const dot  = document.getElementById('api-status-dot');
    const text = document.getElementById('api-status-text');
    try {
        const res = await fetch(`${API_BASE}/api/peta/health`, { method: 'GET' });
        if (res.ok) {
            if (dot) dot.style.background = '#10B981';
            if (text) text.textContent = 'Server Online (Port 8001)';
        } else {
            if (dot) dot.style.background = '#EF4444';
            if (text) text.textContent = 'Server Offline';
        }
    } catch {
        if (dot) dot.style.background = '#EF4444';
        if (text) text.textContent = 'Server Offline — Jalankan backend terlebih dahulu';
    }
}

// ================================================================
// FILE HANDLING & PREVIEW
// ================================================================
function handleFileSelected(file) {
    const ext = file.name.split('.').pop().toLowerCase();
    const allowed = ['pdf'];
    if (!allowed.includes(ext)) {
        showError(`Format berkas tidak didukung: .${ext}. Hanya file PDF (.pdf) yang diperbolehkan.`);
        return;
    }
    if (file.size > 50 * 1024 * 1024) {
        showError('Ukuran berkas melebihi batas 50 MB.');
        return;
    }

    selectedFile = file;
    hideError();
    fileNameSpan.textContent = file.name + ` (${formatSize(file.size)})`;
    fileBadge.classList.remove('hidden');
    processBtn.disabled = false;

    // Create Blob URL for document viewer
    if (currentBlobUrl) URL.revokeObjectURL(currentBlobUrl);
    currentBlobUrl = URL.createObjectURL(file);
    setupDocumentViewer(file, currentBlobUrl);
}

function clearFile() {
    selectedFile = null;
    if (currentBlobUrl) {
        URL.revokeObjectURL(currentBlobUrl);
        currentBlobUrl = null;
    }
    fileInput.value = '';
    fileBadge.classList.add('hidden');
    processBtn.disabled = true;
}

function setupDocumentViewer(file, blobUrl) {
    if (viewerPlaceholder) viewerPlaceholder.classList.add('hidden');
    if (docPreviewIframe) {
        docPreviewIframe.src = `${blobUrl}#toolbar=1&navpanes=0&view=FitH`;
        docPreviewIframe.classList.remove('hidden');
    }
}

function applyZoom() {
    if (zoomBadge) {
        zoomBadge.textContent = `${Math.round(currentZoom * 100)}%`;
    }
    if (imageWrapper) {
        imageWrapper.style.transform = `scale(${currentZoom})`;
    } else if (docPreviewImg) {
        docPreviewImg.style.transform = `scale(${currentZoom})`;
    }
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
    { id: 1, label: 'Preprocessing PDF & Visual' },
    { id: 2, label: 'Ekstraksi Teks OCR' },
    { id: 3, label: 'Deteksi Layout & Grid' },
    { id: 4, label: 'Computer Vision' },
    { id: 5, label: 'Evaluasi 16 Komponen Wajib' },
    { id: 6, label: 'Ekstraksi Titik Kartometrik' },
    { id: 7, label: 'Penyusunan Lembar Audit' },
];

async function startAudit() {
    if (!selectedFile) return;

    hideError();
    showProgressModal();

    const formData = new FormData();
    formData.append('file', selectedFile);

    let stepIdx = 0;
    const stepTimer = setInterval(() => {
        if (stepIdx < STEPS.length) {
            setStep(stepIdx, 'running');
            if (stepIdx > 0) setStep(stepIdx - 1, 'done');
            const pct = Math.round(((stepIdx + 1) / STEPS.length) * 85);
            setProgress(pct);
            stepIdx++;
        }
    }, 700);

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

        STEPS.forEach((_, i) => setStep(i, 'done'));
        setProgress(100);

        await sleep(500);
        hideProgressModal();

        currentAuditData = data;
        renderInspectionWorkspace(data);

        uploadSection.classList.add('hidden');
        resultsSection.classList.remove('hidden');
        window.scrollTo({ top: 0, behavior: 'smooth' });

    } catch (err) {
        clearInterval(stepTimer);
        hideProgressModal();
        showError(`Pemeriksaan gagal: ${err.message || 'Terjadi kesalahan tidak terduga.'}`);
    }
}

// ================================================================
// PROGRESS MODAL
// ================================================================
function showProgressModal() {
    STEPS.forEach((_, i) => setStep(i, 'pending'));
    setProgress(0);
    progressModal.classList.remove('hidden');
}
function hideProgressModal() {
    progressModal.classList.add('hidden');
}
function setProgress(pct) {
    if (progressBar) progressBar.style.width = pct + '%';
    if (progressPct) progressPct.textContent = pct + '%';
}
function setStep(idx, state) {
    const item = document.getElementById(`step-item-${idx}`);
    const dot  = document.getElementById(`step-dot-${idx}`);
    if (!item || !dot) return;

    item.className = 'step-item ' + state;
    if (state === 'done') {
        dot.innerHTML = '<i class="fa-solid fa-check"></i>';
    } else if (state === 'running') {
        dot.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
    } else {
        dot.innerHTML = (idx + 1);
    }
}

// ================================================================
// RENDER INSPECTION WORKSPACE
// ================================================================
function renderInspectionWorkspace(data) {
    // Topbar
    setText('topbar-filename', data.filename || selectedFile?.name || '-');
    setText('topbar-timestamp', formatTimestamp(data.audit_timestamp));

    // Verification Stamp Card
    renderStampCard(data);

    // Summary Metrics
    setText('stat-completeness', (data.completeness_percent || 0).toFixed(1) + '%');
    setText('stat-found', data.found_count || 0);
    setText('stat-uncertain', data.uncertain_count || 0);
    setText('stat-notfound', data.not_found_count || 0);

    // Inspection Matrix Table
    renderAuditTable(data.components || []);

    // Kartometrik Table
    renderTitikKartometrik(data.titik_kartometrik || {});

    // Ensure tab-matriks is active
    currentFilter = 'all';
    document.querySelectorAll('.filter-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.filter === 'all');
    });
}

// ── Verification Stamp Banner ──
function renderStampCard(data) {
    const banner   = document.getElementById('audit-banner');
    const icon     = document.getElementById('banner-icon');
    const status   = document.getElementById('banner-status');
    const summary  = document.getElementById('banner-summary-text');

    if (!banner || !status) return;

    banner.className = 'verification-stamp-card';

    if (data.audit_status === 'LAYAK') {
        banner.classList.add('stamp-layak');
        if (icon) icon.innerHTML = '<i class="fa-solid fa-square-check"></i>';
        status.textContent = '✓ DOKUMEN PETA LAYAK (MEMENUHI TEMPLATE BIG)';
        status.style.color = 'var(--green-text)';
    } else if (data.audit_status === 'PERLU_PERBAIKAN') {
        banner.classList.add('stamp-perbaikan');
        if (icon) icon.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i>';
        status.textContent = '⚠ PERLU PERBAIKAN / REVISI KOMPONEN';
        status.style.color = 'var(--amber-text)';
    } else {
        banner.classList.add('stamp-sesuai');
        if (icon) icon.innerHTML = '<i class="fa-solid fa-circle-xmark"></i>';
        status.textContent = '✗ DOKUMEN TIDAK SESUAI TEMPLATE';
        status.style.color = 'var(--red-text)';
    }

    if (summary) summary.textContent = data.summary || 'Audit komponen kartografi selesai.';
}

// ── Inspection Table ──
function renderAuditTable(components) {
    const tbody = document.getElementById('audit-tbody');
    if (!tbody) return;
    tbody.innerHTML = '';

    components.forEach((comp, idx) => {
        const tr = document.createElement('tr');
        tr.dataset.status   = comp.status;
        tr.dataset.optional = comp.is_optional ? '1' : '0';

        tr.innerHTML = `
            <td class="th-no" style="font-weight:700; color:var(--text-muted);">${comp.no}</td>
            <td class="th-comp">
                <div style="font-weight:700; color:var(--text-main);">${esc(comp.name)}</div>
                ${comp.is_optional ? '<span style="font-size:0.70rem; color:var(--text-muted); font-style:italic;">(Opsional)</span>' : ''}
            </td>
            <td class="th-status">${renderBadge(comp.status)}</td>
            <td class="th-conf" style="text-align:center;">${renderConfBadge(comp.confidence)}</td>
            <td class="th-method"><span class="method-chip">${esc(comp.method || '-')}</span></td>
            <td class="th-value">
                <div style="font-weight:600; color:var(--text-main); font-family:'JetBrains Mono', monospace; font-size:0.80rem;">${esc(comp.value || '-')}</div>
                ${comp.evidence && comp.evidence !== '-' ? `<div style="font-size:0.74rem; color:var(--text-muted); margin-top:2px;">Bukti: "${esc(comp.evidence)}"</div>` : ''}
            </td>
            <td class="th-action" style="text-align:center;">
                <button type="button" class="btn btn-sm btn-outline" style="padding:2px 8px;" onclick="toggleDetail(${idx})" title="Buka Detail">
                    <i class="fa-solid fa-angle-down"></i>
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
            <td colspan="7" style="padding:0 14px;">
                <div class="detail-box">
                    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px; margin-bottom:6px;">
                        <div><strong>Komponen:</strong> ${esc(comp.name)}</div>
                        <div><strong>Confidence:</strong> ${Math.round((comp.confidence || 0) * 100)}%</div>
                        <div><strong>Metode Deteksi:</strong> ${esc(comp.method || '-')}</div>
                        <div><strong>Bounding Box:</strong> ${comp.bbox ? JSON.stringify(comp.bbox) : '-'}</div>
                    </div>
                    ${comp.evidence && comp.evidence !== '-' ? `<div style="margin-top:6px; color:var(--primary);"><strong>Evidence OCR / CV:</strong> ${esc(comp.evidence)}</div>` : ''}
                    ${comp.notes ? `<div style="margin-top:6px; color:var(--amber-text); font-weight:600;"><i class="fa-solid fa-triangle-exclamation"></i> Catatan: ${esc(comp.notes)}</div>` : ''}
                </div>
            </td>
        `;
        tbody.appendChild(detailTr);
    });
}

function toggleDetail(idx) {
    const detailRow = document.getElementById(`detail-row-${idx}`);
    if (detailRow) detailRow.classList.toggle('visible');
}

// ── Filter ──
function applyFilter(filter) {
    const rows = document.querySelectorAll('#audit-tbody tr');
    rows.forEach(tr => {
        if (tr.classList.contains('detail-row')) return;
        const status = tr.dataset.status;
        let visible = false;
        if (filter === 'all') visible = true;
        else if (filter === 'found') visible = status === 'found';
        else if (filter === 'uncertain') visible = status === 'uncertain';
        else if (filter === 'not_found') visible = status === 'not_found';
        tr.classList.toggle('hidden-row', !visible);
    });
}

// ── Kartometrik Table ──
function renderTitikKartometrik(kartData) {
    const tbody    = document.getElementById('kartometrik-tbody');
    const method   = document.getElementById('kartometrik-method');
    const total    = document.getElementById('kartometrik-total');
    const emptyMsg = document.getElementById('kartometrik-empty');

    if (!tbody) return;
    const rows = kartData.rows || [];
    tbody.innerHTML = '';

    if (method) method.textContent = kartData.method || '-';
    if (total)  total.textContent  = rows.length + ' Titik';

    if (rows.length === 0) {
        if (emptyMsg) emptyMsg.classList.remove('hidden');
        tbody.parentElement.style.display = 'none';
        return;
    }

    if (emptyMsg) emptyMsg.classList.add('hidden');
    tbody.parentElement.style.display = 'table';

    rows.forEach((row, i) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td style="text-align:center; font-weight:600;">${esc(row.no || (i+1).toString())}</td>
            <td style="font-weight:700; font-family:'JetBrains Mono', monospace;">${esc(row.kode || '-')}</td>
            <td style="font-family:'JetBrains Mono', monospace;">${esc(row.lintang || '-')}</td>
            <td style="font-family:'JetBrains Mono', monospace;">${esc(row.bujur || '-')}</td>
            <td style="font-family:'JetBrains Mono', monospace;">${esc(row.x || '-')}</td>
            <td style="font-family:'JetBrains Mono', monospace;">${esc(row.y || '-')}</td>
        `;
        tbody.appendChild(tr);
    });
}

// ================================================================
// HELPERS
// ================================================================
function renderBadge(status) {
    if (status === 'found') return '<span class="badge-status badge-found"><i class="fa-solid fa-check"></i> Ditemukan</span>';
    if (status === 'uncertain') return '<span class="badge-status badge-uncertain"><i class="fa-solid fa-triangle-exclamation"></i> Perlu Dipastikan</span>';
    return '<span class="badge-status badge-notfound"><i class="fa-solid fa-xmark"></i> Tidak Ditemukan</span>';
}

function renderConfBadge(conf) {
    const pct = Math.round((conf || 0) * 100);
    let color = 'var(--red-text)';
    if (pct >= 70) color = 'var(--green-text)';
    else if (pct >= 40) color = 'var(--amber-text)';
    return `<span class="conf-badge" style="color:${color};">${pct}%</span>`;
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

// ================================================================
// EXPORT PDF REPORT (html2pdf.js)
// ================================================================
function formatTimestamp(ts) {
    if (!ts) {
        return new Date().toLocaleString('id-ID', {
            dateStyle: 'long',
            timeStyle: 'medium'
        });
    }
    try {
        const d = new Date(ts);
        if (isNaN(d.getTime())) return ts;
        return d.toLocaleString('id-ID', {
            dateStyle: 'long',
            timeStyle: 'medium'
        });
    } catch (e) {
        return ts;
    }
}


