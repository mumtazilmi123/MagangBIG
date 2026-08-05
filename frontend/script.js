// ================================================================
// VERIDOC v5.0 — PREMIUM SPA ENGINE (Multi-Upload + Card Anomalies)
// ================================================================

let leafletMap = null;
let leafletMarkersGroup = null;
let currentAuditData = null;
let currentMapBounds = null;
let selectedMode = 'pdf';
let selectedFiles = [];
let mapAuditFile = null;
let vectorPredictFile = null;
let multiResults = [];

// ================================================================
// TAB SYSTEM
// ================================================================
function switchTab(tabId) {
    document.querySelectorAll('.tab-item').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));

    const activeBtn = document.querySelector(`.tab-item[data-tab="${tabId}"]`);
    if (activeBtn) activeBtn.classList.add('active');

    const activePane = document.getElementById(tabId);
    if (activePane) activePane.classList.add('active');

    if (tabId === 'tab-map-gis' && leafletMap) {
        [50, 200, 500].forEach(delay => {
            setTimeout(() => {
                try {
                    leafletMap.invalidateSize();
                    if (currentMapBounds && currentMapBounds.isValid()) {
                        leafletMap.fitBounds(currentMapBounds, { padding: [40, 40] });
                    }
                } catch (e) { console.warn("Leaflet resize:", e); }
            }, delay);
        });
    }
}

// ================================================================
// INIT
// ================================================================
document.addEventListener('DOMContentLoaded', function() {
    // Select2 Data
    const datumData = [
        { text: 'Indonesia', children: [
            { id: 'EPSG:9470', text: 'SRGI 2013 (EPSG:9470)' },
            { id: 'EPSG:4755', text: 'DGN95 (EPSG:4755)' },
            { id: 'EPSG:4238', text: 'ID74 (EPSG:4238)' }
        ]},
        { text: 'WGS 84 Global', children: [
            { id: 'EPSG:4326', text: 'WGS 84 (EPSG:4326)', selected: true }
        ]}
    ];

    function genZones(start, end, suffix) {
        let res = [];
        for(let i=start; i<=end; i++) res.push({id: i+suffix, text: 'Zona ' + i + suffix});
        return res;
    }

    const utmData = [
        { text: 'Rekomendasi', children: [{ id: 'Auto', text: 'Auto-Detect (Per-Titik)', selected: true }] },
        { text: 'Indonesia (UTM WGS 84)', children: genZones(46, 54, 'N').concat(genZones(46, 54, 'S')) }
    ];

    if ($('#datum').length) $('#datum').select2({ data: datumData, placeholder: 'Pilih Datum', width: '100%' });
    if ($('#utm-zone').length) $('#utm-zone').select2({ data: utmData, placeholder: 'Pilih Zona UTM', width: '100%' });



    // Tab click handlers
    document.querySelectorAll('.tab-item[data-tab]').forEach(btn => {
        btn.addEventListener('click', function() {
            switchTab(this.getAttribute('data-tab'));
        });
    });

    // Elements
    // Elements
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const mapAuditInput = document.getElementById('map-audit-input');
    const browseBtn = document.getElementById('btn-browse-action');
    const processBtn = document.getElementById('process-btn');
    const processBtnText = document.getElementById('process-btn-text');
    const filesList = document.getElementById('files-list');
    const filesChips = document.getElementById('files-chips');
    const filesCount = document.getElementById('files-count');
    const clearAllBtn = document.getElementById('clear-all-files');
    const errorMsg = document.getElementById('error-message');
    const progressContainer = document.getElementById('progress-container');
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');

    // Mode Switcher
    const btnPdf = document.getElementById('btn-mode-pdf');
    const btnMap = document.getElementById('btn-mode-map');

    function setMode(mode) {
        selectedMode = mode;
        [btnPdf, btnMap].forEach(btn => btn && btn.classList.remove('active'));

        const titleEl = document.getElementById('upload-title-element');
        const descEl = document.getElementById('upload-desc-element');
        const iconEl = document.getElementById('upload-icon-element');

        if (mode === 'pdf' && btnPdf) {
            btnPdf.classList.add('active');
            if(titleEl) titleEl.textContent = 'Unggah Dokumen PDF SKVT';
            if(descEl) descEl.textContent = 'Pilih atau seret satu atau beberapa file PDF sekaligus';
            if(iconEl) iconEl.className = 'fa-solid fa-cloud-arrow-up drop-icon-main';
            if(fileInput) fileInput.setAttribute('multiple', '');
        } else if (mode === 'map' && btnMap) {
            btnMap.classList.add('active');
            if(titleEl) titleEl.textContent = 'Unggah Berkas Peta (.pdf, .png, .jpg)';
            if(descEl) descEl.textContent = 'Pilih peta untuk pemeriksaan keterbacaan, typo, koordinat legenda, & teks bertumpuk';
            if(iconEl) iconEl.className = 'fa-solid fa-map-location-dot drop-icon-main';
        }
        resetSelection();
    }

    if (btnPdf) btnPdf.addEventListener('click', () => setMode('pdf'));
    if (btnMap) btnMap.addEventListener('click', () => setMode('map'));

    // File Selection
    if (browseBtn) {
        browseBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            if (selectedMode === 'map' && mapAuditInput) mapAuditInput.click();
            else if (fileInput) fileInput.click();
        });
    }

    if (dropZone) {
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(evt => {
            dropZone.addEventListener(evt, (e) => { e.preventDefault(); e.stopPropagation(); }, false);
        });
        dropZone.addEventListener('dragover', () => dropZone.classList.add('dragover'));
        dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
        dropZone.addEventListener('drop', (e) => {
            dropZone.classList.remove('dragover');
            handleFiles(e.dataTransfer.files);
        });
        dropZone.addEventListener('click', (e) => {
            if (e.target.tagName === 'BUTTON' || e.target.closest('button')) return;
            if (selectedMode === 'map' && mapAuditInput) mapAuditInput.click();
            else if (fileInput) fileInput.click();
        });
    }

    if (fileInput) fileInput.addEventListener('change', function() { handleFiles(this.files); });
    if (mapAuditInput) mapAuditInput.addEventListener('change', function() { handleFiles(this.files); });

    function handleFiles(files) {
        if (!files || files.length === 0) return;

        if (selectedMode === 'map') {
            mapAuditFile = files[0];
            selectedFiles = [files[0]];
            renderFileChips();
            if (processBtn) processBtn.disabled = false;
            if (processBtnText) processBtnText.textContent = 'Audit Pembacaan Peta';
        } else {
            const pdfFiles = Array.from(files).filter(f => f.name.toLowerCase().endsWith('.pdf') || f.type === 'application/pdf');
            if (pdfFiles.length === 0) {
                showError("Tidak ditemukan berkas PDF yang valid.");
                return;
            }
            // Ganti daftar berkas dengan pilihan berkas baru (tidak menumpuk berkas lama)
            selectedFiles = pdfFiles;
            renderFileChips();
            if (processBtn) processBtn.disabled = false;
            if (processBtnText) {
                processBtnText.textContent = selectedFiles.length === 1 
                    ? 'Jalankan Pengecekan Dokumen' 
                    : `Jalankan Pengecekan ${selectedFiles.length} Dokumen`;
            }
        }
        if (errorMsg) errorMsg.classList.add('hidden');
    }

    function renderFileChips() {
        if (!filesChips || !filesList || !filesCount) return;
        
        if (selectedFiles.length === 0) {
            filesList.classList.add('hidden');
            filesChips.innerHTML = '';
            return;
        }
        
        filesList.classList.remove('hidden');
        filesCount.textContent = selectedFiles.length;
        filesChips.innerHTML = '';
        
        selectedFiles.forEach((file, idx) => {
            const chip = document.createElement('div');
            chip.className = 'file-chip';
            const icon = selectedMode === 'map' ? 'fa-map-location-dot' : 'fa-file-pdf';
            const sizeKB = (file.size / 1024).toFixed(0);
            chip.innerHTML = `
                <i class="fa-solid ${icon}"></i>
                <span>${file.name}</span>
                <span style="color:var(--text-muted);font-size:0.72rem;">(${sizeKB} KB)</span>
                <button type="button" class="chip-remove" data-idx="${idx}"><i class="fa-solid fa-xmark"></i></button>
            `;
            filesChips.appendChild(chip);
        });

        // Remove individual file
        filesChips.querySelectorAll('.chip-remove').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const idx = parseInt(btn.getAttribute('data-idx'));
                selectedFiles.splice(idx, 1);
                if (selectedMode === 'map') mapAuditFile = null;
                renderFileChips();
                if (selectedFiles.length === 0) {
                    resetSelection();
                } else if (processBtnText) {
                    processBtnText.textContent = selectedFiles.length === 1 
                        ? (selectedMode === 'map' ? 'Audit Pembacaan Peta' : 'Jalankan Pengecekan Dokumen') 
                        : `Jalankan Pengecekan ${selectedFiles.length} Dokumen`;
                }
            });
        });
    }

    if (clearAllBtn) {
        clearAllBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            resetSelection();
        });
    }

    function resetSelection() {
        selectedFiles = [];
        mapAuditFile = null;
        if (fileInput) fileInput.value = '';
        if (mapAuditInput) mapAuditInput.value = '';
        if (filesChips) filesChips.innerHTML = '';
        if (filesList) filesList.classList.add('hidden');
        if (processBtn) processBtn.disabled = true;
        if (processBtnText) {
            processBtnText.textContent = selectedMode === 'map' ? 'Audit Pembacaan Peta' : 'Jalankan Pengecekan Dokumen';
        }
    }

    function showError(msg) {
        if (errorMsg) {
            errorMsg.textContent = msg;
            errorMsg.classList.remove('hidden');
        }
    }

    // Regulations
    loadRegulations();
    const btnSearchReg = document.getElementById('btn-search-reg');
    if (btnSearchReg) {
        btnSearchReg.addEventListener('click', () => {
            const query = (document.getElementById('reg-search-input').value || '').trim();
            loadRegulations(query);
        });
    }

    async function loadRegulations(query = '') {
        const container = document.getElementById('regulations-cards-container');
        if (!container) return;
        try {
            const res = await fetch(`/api/regulations?q=${encodeURIComponent(query)}`);
            const data = await res.json();
            container.innerHTML = '';
            (data.regulations || []).forEach(r => {
                const card = document.createElement('div');
                card.className = 'card';
                card.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:10px;">
                        <span class="badge-count">${r.id}</span>
                        <span style="font-size:0.78rem; color:var(--text-secondary); font-weight:600;">${r.authority}</span>
                    </div>
                    <h4 style="font-size:0.95rem; font-weight:700; margin-bottom:8px; color:var(--text-bright);">${r.title}</h4>
                    <p style="font-size:0.85rem; color:var(--text-secondary); margin-bottom:12px; line-height:1.5;">${r.summary}</p>
                    <a href="${r.url}" target="_blank" style="color:var(--accent-blue); font-size:0.82rem; font-weight:600; text-decoration:none;"><i class="fa-solid fa-arrow-up-right-from-square"></i> Baca Dokumen Resmi</a>
                `;
                container.appendChild(card);
            });
        } catch (e) { console.warn("Regulations:", e); }
    }

    // ================================================================
    // LIVE ANIMATED PROGRESS MODAL & BACKGROUND WORKER MANAGER
    // ================================================================
    let bgWorker = null;
    let currentProgressStep = 1;
    let currentPercent = 0;
    let progressIntervalId = null;

    const STEPS_DATA_PDF = [
        { id: 1, title: "1. Membaca & Extract Struktur PDF", desc: "Mengekstrak halaman, teks vektor, tabel koordinat, dan objek gambar map...", icon: "fa-file-pdf", percent: 15, status: "Mengekstrak teks & objek gambar map..." },
        { id: 2, title: "2. Transformasi Geodesi & Zona UTM", desc: "Proyeksi Ellipsoid WGS 84 ke UTM dan kalkulasi konvergensi meridian (γ)...", icon: "fa-globe", percent: 35, status: "Proyeksi WGS 84 -> UTM & γ meridian..." },
        { id: 3, title: "3. Evaluasi Presisi Spasial & RMSE", desc: "Menghitung residu koordinat (dX, dY), 2D RMSE, dan akurasi CE95 Standar BIG...", icon: "fa-draw-polygon", percent: 55, status: "Evaluasi dX, dY & CE95 Standar BIG..." },
        { id: 4, title: "4. Inspeksi Kartografi & Legenda Peta", desc: "Memeriksa citra peta lampiran & kelengkapan blok legenda kartografis resmi...", icon: "fa-map", percent: 75, status: "Inspeksi citra peta & blok legenda..." },
        { id: 5, title: "5. Evaluasi 9 Catatan Kritis & Tipografi", desc: "Inspeksi konsistensi font, format DMS/desimal, NIP penandatangan & kode Kemendagri...", icon: "fa-clipboard-check", percent: 90, status: "Audit tipografi, DMS & Permendagri..." },
        { id: 6, title: "6. Generasi Laporan & Database Spasial", desc: "Menyusun laporan akhir PDF & menyimpan data spasial ke DuckDB...", icon: "fa-database", percent: 98, status: "Menyusun laporan PDF & DuckDB..." }
    ];

    const STEPS_DATA_MAP = [
        { id: 1, title: "1. Memuat & Render Citra Peta", desc: "Mengonversi lembar peta ke citra high-DPI untuk analisis Vision AI...", icon: "fa-image", percent: 15, status: "Mengonversi lembar peta ke citra high-DPI..." },
        { id: 2, title: "2. Inspeksi Keterbacaan & Layout Peta", desc: "Memeriksa kejelasan peta, kelengkapan legenda, skala bar & orientasi utara...", icon: "fa-map-location-dot", percent: 35, status: "Memeriksa kelengkapan layout & legenda..." },
        { id: 3, title: "3. Pemindaian Typo di Peta & Legenda", desc: "Pemeriksaan ejaan judul peta, tabel legenda, dan nama wilayah (KBBI)...", icon: "fa-spell-check", percent: 55, status: "Scanning typo judul & tabel legenda..." },
        { id: 4, title: "4. Verifikasi Koordinat Legenda vs Peta", desc: "Mencocokkan nilai koordinat Titik Kartometrik (TK) legenda dengan titik peta...", icon: "fa-location-crosshairs", percent: 75, status: "Membandingkan koordinat legenda vs peta..." },
        { id: 5, title: "5. Deteksi Teks Titik TK Bertumpuk", desc: "Memeriksa kejelasan penomoran titik TK & angka koordinat agar tidak terpotong...", icon: "fa-layer-group", percent: 90, status: "Memeriksa teks bertumpuk / terpotong..." },
        { id: 6, title: "6. Generasi Hasil Pembacaan Peta Vision AI", desc: "Menyusun laporan analisis keterbacaan & 4 aspek pengecekan peta...", icon: "fa-chart-pie", percent: 98, status: "Menyusun laporan hasil pembacaan peta..." }
    ];

    function getActiveStepsData() {
        return selectedMode === 'map' ? STEPS_DATA_MAP : STEPS_DATA_PDF;
    }

    function requestNotificationPermission() {
        if ("Notification" in window && Notification.permission === "default") {
            Notification.requestPermission();
        }
    }

    function sendAuditCompleteNotification(filename) {
        if ("Notification" in window && Notification.permission === "granted") {
            try {
                new Notification("🎉 Audit Dokumen SKVT Selesai!", {
                    body: `Veridoc telah selesai mengaudit "${filename || 'Dokumen'}". Klik untuk melihat laporan.`,
                });
            } catch(e) { console.warn("Notification error:", e); }
        }
    }

    function createBackgroundWorker() {
        const workerBlob = new Blob([`
            let timer = null;
            onmessage = function(e) {
                if (e.data === 'start') {
                    if (timer) clearInterval(timer);
                    timer = setInterval(() => {
                        postMessage('tick');
                    }, 400);
                } else if (e.data === 'stop') {
                    if (timer) clearInterval(timer);
                    timer = null;
                }
            };
        `], { type: 'application/javascript' });
        return new Worker(URL.createObjectURL(workerBlob));
    }

    function startAnimatedProgress(docName) {
        requestNotificationPermission();
        
        const modal = document.getElementById('audit-progress-modal');
        const floatPill = document.getElementById('bg-floating-pill');
        if (modal) modal.classList.remove('hidden');
        if (floatPill) floatPill.classList.add('hidden');

        const steps = getActiveStepsData();
        for (let i = 1; i <= 6; i++) {
            const stepData = steps[i - 1];
            const item = document.getElementById(`step-${i}`);
            const badge = document.getElementById(`step-badge-${i}`);
            if (item && stepData) {
                item.className = 'progress-step-item pending';
                const titleEl = item.querySelector('.step-title');
                const descEl = item.querySelector('.step-desc');
                const iconEl = item.querySelector('.step-icon i');
                
                if (titleEl) titleEl.textContent = stepData.title;
                if (descEl) descEl.textContent = stepData.desc;
                if (iconEl) iconEl.className = `fa-solid ${stepData.icon}`;
            }
            if (badge) badge.innerHTML = '<i class="fa-solid fa-hourglass-start"></i> Menunggu';
        }

        currentProgressStep = 1;
        currentPercent = 5;
        updateProgressUI(currentProgressStep, currentPercent, steps[0].status, docName);
        setStepActive(1);

        try {
            if (!bgWorker) {
                bgWorker = createBackgroundWorker();
                bgWorker.onmessage = function(e) {
                    if (e.data === 'tick') {
                        advanceProgressTick(docName);
                    }
                };
            }
            bgWorker.postMessage('start');
        } catch(err) {
            if (progressIntervalId) clearInterval(progressIntervalId);
            progressIntervalId = setInterval(() => advanceProgressTick(docName), 400);
        }
    }

    function setStepActive(stepNum) {
        for (let i = 1; i <= 6; i++) {
            const item = document.getElementById(`step-${i}`);
            const badge = document.getElementById(`step-badge-${i}`);
            if (i < stepNum) {
                if (item) item.className = 'progress-step-item completed';
                if (badge) badge.innerHTML = '<i class="fa-solid fa-circle-check"></i> Selesai';
            } else if (i === stepNum) {
                if (item) item.className = 'progress-step-item active';
                if (badge) badge.innerHTML = '<i class="fa-solid fa-rotate spin-icon"></i> Diproses...';
            } else {
                if (item) item.className = 'progress-step-item pending';
                if (badge) badge.innerHTML = '<i class="fa-solid fa-hourglass-start"></i> Menunggu';
            }
        }
    }

    function advanceProgressTick(docName) {
        const steps = getActiveStepsData();
        if (currentPercent < 95) {
            currentPercent += Math.random() > 0.5 ? 2 : 1;
        }

        let activeStep = 1;
        for (let i = steps.length - 1; i >= 0; i--) {
            if (currentPercent >= steps[i].percent - 10) {
                activeStep = steps[i].id;
                break;
            }
        }

        if (activeStep !== currentProgressStep) {
            currentProgressStep = activeStep;
            setStepActive(currentProgressStep);
        }

        const stepInfo = steps.find(s => s.id === currentProgressStep) || steps[0];
        updateProgressUI(currentProgressStep, currentPercent, stepInfo.status, docName);
    }

    function updateProgressUI(step, percent, statusText, docName) {
        const percentEl = document.getElementById('modal-percent-text');
        const fillEl = document.getElementById('modal-progress-fill');
        const statusPill = document.getElementById('modal-status-pill');
        const pillSub = document.getElementById('floating-pill-sub');

        if (percentEl) percentEl.textContent = `${percent}%`;
        if (fillEl) fillEl.style.width = `${percent}%`;
        if (statusPill) statusPill.textContent = statusText;
        if (pillSub) pillSub.textContent = `Progres: ${percent}% — ${statusText}`;

        document.title = `[${percent}%] ${statusText} — Veridoc`;
    }

    function finishAnimatedProgress(docName) {
        if (bgWorker) bgWorker.postMessage('stop');
        if (progressIntervalId) clearInterval(progressIntervalId);

        currentPercent = 100;
        updateProgressUI(6, 100, "Audit Dokumen Selesai!", docName);
        setStepActive(7);

        document.title = "✅ Audit Selesai! — Veridoc";
        sendAuditCompleteNotification(docName);

        setTimeout(() => {
            const modal = document.getElementById('audit-progress-modal');
            const floatPill = document.getElementById('bg-floating-pill');
            if (modal) modal.classList.add('hidden');
            if (floatPill) floatPill.classList.add('hidden');
        }, 600);
    }

    function stopAnimatedProgressWithError() {
        if (bgWorker) bgWorker.postMessage('stop');
        if (progressIntervalId) clearInterval(progressIntervalId);
        document.title = "Veridoc — Audit Dokumen SKVT BIG";
        const modal = document.getElementById('audit-progress-modal');
        const floatPill = document.getElementById('bg-floating-pill');
        if (modal) modal.classList.add('hidden');
        if (floatPill) floatPill.classList.add('hidden');
    }

    // Modal Minimize & Float Pill handlers
    const btnMinModal = document.getElementById('btn-minimize-modal');
    const bgFloatingPill = document.getElementById('bg-floating-pill');
    const auditModal = document.getElementById('audit-progress-modal');

    if (btnMinModal) {
        btnMinModal.addEventListener('click', () => {
            if (auditModal) auditModal.classList.add('hidden');
            if (bgFloatingPill) bgFloatingPill.classList.remove('hidden');
        });
    }

    if (bgFloatingPill) {
        bgFloatingPill.addEventListener('click', () => {
            if (bgFloatingPill) bgFloatingPill.classList.add('hidden');
            if (auditModal) auditModal.classList.remove('hidden');
        });
    }

    // ================================================================
    // PROCESS BUTTON
    // ================================================================
    if (processBtn) {
        processBtn.addEventListener('click', async function() {
            if (errorMsg) errorMsg.classList.add('hidden');
            processBtn.disabled = true;

            const utmEl = document.getElementById('utm-zone');
            const datumEl = document.getElementById('datum');
            const utmVal = (utmEl && utmEl.value) ? utmEl.value : 'Auto';
            const datumVal = (datumEl && datumEl.value) ? datumEl.value : 'EPSG:4326';

            const outputDirEl = document.getElementById('output-dir-input');
            const outputDirVal = outputDirEl ? (outputDirEl.value || '').trim() : '';

            const docLabel = selectedMode === 'map' 
                ? (typeof mapAuditFile !== 'undefined' && mapAuditFile ? mapAuditFile.name : "Berkas Peta")
                : (selectedFiles.length > 0 ? selectedFiles[0].name : "Dokumen PDF");

            try {
                startAnimatedProgress(docLabel);

                if (selectedMode === 'map') {
                    const formData = new FormData();
                    formData.append('file', mapAuditFile);
                    const response = await fetch('/api/audit-map', { method: 'POST', body: formData });
                    if (!response.ok) {
                        const errRes = await response.json();
                        throw new Error(errRes.detail || "Gagal menganalisis pembacaan peta.");
                    }
                    const data = await response.json();
                    finishAnimatedProgress(docLabel);
                    renderMapResults(data);
                } else {
                    const formData = new FormData();
                    selectedFiles.forEach(f => formData.append('files', f));
                    formData.append('utm_zone', utmVal);
                    formData.append('datum', datumVal);
                    if (outputDirVal) formData.append('output_dir', outputDirVal);

                    const response = await fetch('/api/audit', { method: 'POST', body: formData });
                    if (!response.ok) {
                        const errRes = await response.json();
                        throw new Error(errRes.detail || "Gagal memproses dokumen PDF.");
                    }
                    const data = await response.json();
                    finishAnimatedProgress(docLabel);

                    if (data.mode === 'multi') {
                        renderMultiResults(data);
                    } else {
                        renderSingleResults(data);
                    }
                }

                // Reset daftar file upload agar tidak menumpuk untuk proses selanjutnya
                resetSelection();
            } catch (err) {
                stopAnimatedProgressWithError();
                showError("Terjadi kesalahan: " + err.message);
                processBtn.disabled = false;
            }
        });
    }

    // ================================================================
    // RENDER: Single PDF Results
    // ================================================================
    function renderSingleResults(data) {
        currentAuditData = data;
        const resultsSec = document.getElementById('results-section');
        if (resultsSec) resultsSec.classList.remove('hidden');

        const statGrid = document.getElementById('stat-grid');
        let existingAlert = document.getElementById('non-skvt-alert-banner');

        const multiNavEl = document.getElementById('multi-file-nav');
        const vectorContEl = document.getElementById('vector-result-container');
        const pdfTabsEl = document.getElementById('pdf-tabs-wrapper');
        const exporterEl = document.getElementById('exporter-section');

        const cardGreen = document.querySelector('.stat-card-green');
        if (cardGreen) cardGreen.classList.remove('hidden');
        const cardPurple = document.querySelector('.stat-card-purple');
        if (cardPurple) cardPurple.classList.remove('hidden');

        // Non-SKVT handling
        if (data.is_skvt === false || data.status === 'error_non_skvt') {
            if (statGrid) statGrid.classList.add('hidden');
            if (multiNavEl) multiNavEl.classList.add('hidden');
            if (vectorContEl) vectorContEl.classList.add('hidden');
            if (pdfTabsEl) pdfTabsEl.classList.add('hidden');
            if (exporterEl) exporterEl.classList.add('hidden');

            if (!existingAlert && resultsSec) {
                existingAlert = document.createElement('div');
                existingAlert.id = 'non-skvt-alert-banner';
                resultsSec.prepend(existingAlert);
            }
            if (existingAlert) {
                existingAlert.className = 'non-skvt-alert-card';
                existingAlert.innerHTML = `
                    <div style="width:72px; height:72px; background:var(--danger-bg); border-radius:50%; display:flex; align-items:center; justify-content:center; margin:0 auto 20px auto;">
                        <i class="fa-solid fa-file-circle-xmark" style="font-size:2.5rem; color:var(--danger);"></i>
                    </div>
                    <h3 style="color:var(--danger); font-size:1.5rem; font-weight:800; margin-bottom:12px;">Dokumen Bukan SKVT</h3>
                    <p style="color:var(--text-secondary); font-size:1rem; max-width:700px; margin:0 auto 20px auto; line-height:1.6;">
                        Berkas <strong style="color:var(--text-main);">"${data.filename || (selectedFiles[0] ? selectedFiles[0].name : 'PDF')}"</strong> 
                        tidak terdeteksi sebagai dokumen SKVT BIG.
                    </p>
                    <div style="background:var(--bg-surface); border-radius:var(--radius-sm); padding:14px 20px; display:inline-block; border:1px solid var(--border-color); color:var(--text-secondary); font-weight:600; font-size:0.92rem;">
                        <i class="fa-solid fa-lightbulb" style="color:var(--accent-amber); margin-right:6px;"></i> 
                        Pastikan Anda mengunggah naskah resmi SKVT BIG atau laporan verifikasi geospasial.
                    </div>
                `;
            }
            if (resultsSec) resultsSec.scrollIntoView({ behavior: 'smooth' });
            return;
        } else {
            if (existingAlert) existingAlert.remove();
            if (statGrid) statGrid.classList.remove('hidden');
            if (exporterEl) exporterEl.classList.remove('hidden');
        }

        // Stat cards
        const totalPages = (data.anomalies_9 && data.anomalies_9[0]) ? data.anomalies_9[0].total_pages : '?';
        const regEl = document.getElementById('res-region');
        if (regEl) regEl.textContent = data.region || '-';
        const totEl = document.getElementById('res-total');
        if (totEl) totEl.textContent = `${data.total_points || 0} Titik`;
        const failAnomalies = (data.anomalies_9 || []).filter(a => a.status !== 'PASS').length;
        const anomEl = document.getElementById('res-anomalies');
        if (anomEl) anomEl.textContent = `${failAnomalies} Catatan`;
        const ce95El = document.getElementById('res-ce95');
        if (ce95El) ce95El.textContent = `${(data.ce95 || 0).toFixed(4)} m`;

        // Visibility
        if (multiNavEl) multiNavEl.classList.add('hidden');
        if (vectorContEl) vectorContEl.classList.add('hidden');
        if (pdfTabsEl) pdfTabsEl.classList.remove('hidden');

        // Tab 1: Anomaly Table & Cards
        renderAnomalyTable(data.anomalies_9 || [], totalPages);
        renderAnomalyCards(data.anomalies_9 || [], totalPages);

        // Tab 2: Geomatics
        const rmseXEl = document.getElementById('geo-rmse-x');
        if (rmseXEl) rmseXEl.textContent = `${(data.rmse_x || 0).toFixed(4)} m`;
        const rmseYEl = document.getElementById('geo-rmse-y');
        if (rmseYEl) rmseYEl.textContent = `${(data.rmse_y || 0).toFixed(4)} m`;
        const rmseREl = document.getElementById('geo-rmse-r');
        if (rmseREl) rmseREl.textContent = `${(data.rmse_r || 0).toFixed(4)} m`;
        const ce95GeoEl = document.getElementById('geo-ce95');
        if (ce95GeoEl) ce95GeoEl.textContent = `${(data.ce95 || 0).toFixed(4)} m`;
        const gradeEl = document.getElementById('geo-big-grade');
        if (gradeEl) gradeEl.textContent = data.big_scale_grade || 'Standard BIG';

        // Tab 4: Components
        if (data.components) {
            const c1 = document.getElementById('comp-1-body');
            if (c1) c1.textContent = data.components.surat_keterangan?.status || 'Lengkap';
            const c2 = document.getElementById('comp-2-body');
            if (c2) c2.textContent = data.components.lampiran_1?.kugi_status || 'Lengkap';
            const c3 = document.getElementById('comp-3-body');
            if (c3) c3.textContent = `Total ${data.components.lampiran_2?.total_villages || 0} Desa/Kelurahan`;
            const c4 = document.getElementById('comp-4-body');
            if (c4) c4.textContent = `Total ${data.total_points || 0} Titik Kartometrik`;
        }

        // Tab 5: Villages
        const tbodyV = document.getElementById('villages-tbody');
        if (tbodyV) {
            tbodyV.innerHTML = '';
            if (data.components?.lampiran_2?.villages_sample) {
                data.components.lampiran_2.villages_sample.forEach(v => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td>${v.no}</td>
                        <td><code style="color:var(--accent-blue);">${v.code}</code></td>
                        <td><strong>${v.name}</strong></td>
                        <td>${v.kecamatan}</td>
                        <td>${v.kabupaten}</td>
                        <td>Halaman ${v.page || '-'}</td>
                    `;
                    tbodyV.appendChild(tr);
                });
            }
        }

        // Tab: Kesesuaian Kode Wilayah
        renderWilayahConsistencyAudit(data.wilayah_consistency_audit);

        // Tab: Pemeriksaan Unsur Peta
        renderMapElementsAudit(data.map_elements_audit);


        // Tab 6: Coordinates
        const tbodySamples = document.getElementById('samples-tbody');
        if (tbodySamples) {
            tbodySamples.innerHTML = '';
            (data.samples || []).forEach(s => {
                const tr = document.createElement('tr');
                const gmapUrl = `https://www.google.com/maps/place/${s.lat_dd},${s.lon_dd}`;
                tr.innerHTML = `
                    <td><strong>Titik #${s.index}</strong><br><small style="color:var(--text-secondary);">${s.code}</small><br><span class="anomaly-page-badge">Hal ${s.page}</span></td>
                    <td style="font-family:'JetBrains Mono',monospace;font-size:0.82rem;">${s.lat_dms}<br>${s.lon_dms}</td>
                    <td style="font-family:'JetBrains Mono',monospace;font-size:0.82rem;">${s.doc_x}<br>${s.doc_y}</td>
                    <td style="font-family:'JetBrains Mono',monospace;font-size:0.82rem;">${s.calc_x}<br>${s.calc_y}<br><small style="color:var(--accent-blue);">γ: ${s.meridian_convergence_sec || 0}"</small></td>
                    <td><a href="${gmapUrl}" target="_blank" class="btn btn-browse" style="padding:5px 12px;font-size:0.78rem;"><i class="fa-solid fa-map-location-dot"></i></a></td>
                `;
                tbodySamples.appendChild(tr);
            });
        }

        setupExporters(data);
        const pathEl = document.getElementById('res-saved-path');
        if (pathEl) pathEl.textContent = data.saved_path || 'Documents/Veridoc';

        if (resultsSec) {
            resultsSec.classList.remove('hidden');
            resultsSec.scrollIntoView({ behavior: 'smooth' });
        }

        setTimeout(() => {
            try { initLeafletMap(data.all_points || []); }
            catch (mErr) { console.warn("Leaflet init:", mErr); }
        }, 200);
    }

    // ================================================================
    // RENDER: Anomaly Cards (with Rule Filtering)
    // ================================================================
    let currentFilterMode = 'all';

    document.querySelectorAll('.rule-filter-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.rule-filter-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            currentFilterMode = this.getAttribute('data-filter') || 'all';
            if (currentAuditData && currentAuditData.anomalies_9) {
                const totalPages = currentAuditData.anomalies_9[0] ? currentAuditData.anomalies_9[0].total_pages : '?';
                renderAnomalyTable(currentAuditData.anomalies_9, totalPages);
                renderAnomalyCards(currentAuditData.anomalies_9, totalPages);
            }
        });
    });

    let currentViewMode = 'table';
    const btnViewTable = document.getElementById('btn-view-table');
    const btnViewCards = document.getElementById('btn-view-cards');
    const tableWrapper = document.getElementById('anomaly-table-wrapper');
    const cardsWrapper = document.getElementById('anomaly-cards-container');

    if (btnViewTable && btnViewCards) {
        btnViewTable.addEventListener('click', () => {
            currentViewMode = 'table';
            btnViewTable.style.background = '#e5322d';
            btnViewTable.style.color = '#fff';
            btnViewTable.style.border = 'none';
            btnViewCards.style.background = '#f1f5f9';
            btnViewCards.style.color = '#475569';
            btnViewCards.style.border = '1px solid #cbd5e1';
            if (tableWrapper) tableWrapper.classList.remove('hidden');
            if (cardsWrapper) cardsWrapper.classList.add('hidden');
        });

        btnViewCards.addEventListener('click', () => {
            currentViewMode = 'cards';
            btnViewCards.style.background = '#e5322d';
            btnViewCards.style.color = '#fff';
            btnViewCards.style.border = 'none';
            btnViewTable.style.background = '#f1f5f9';
            btnViewTable.style.color = '#475569';
            btnViewTable.style.border = '1px solid #cbd5e1';
            if (cardsWrapper) cardsWrapper.classList.remove('hidden');
            if (tableWrapper) tableWrapper.classList.add('hidden');
        });
    }

    function renderAnomalyTable(anomalies, totalPages) {
        const tbody = document.getElementById('anomaly-table-tbody');
        if (!tbody) return;
        tbody.innerHTML = '';

        const filteredAnomalies = (anomalies || []).filter(item => {
            if (currentFilterMode === 'issues') return item.status !== 'PASS';
            if (currentFilterMode === 'pass') return item.status === 'PASS';
            return true;
        });

        if (filteredAnomalies.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" style="text-align:center; padding:32px; color:var(--text-secondary);">
                        <i class="fa-solid fa-circle-check" style="font-size:2rem; color:var(--success); margin-bottom:12px; display:block;"></i>
                        <p style="font-weight:600;">Tidak ada parameter yang sesuai dengan filter '${currentFilterMode}'.</p>
                    </td>
                </tr>
            `;
            return;
        }

        filteredAnomalies.forEach((item, idx) => {
            const statusText = item.status === 'PASS' ? 'SESUAI' : (item.status === 'FAIL' ? 'EVALUASI' : 'CATATAN');
            const badgeClass = item.status === 'PASS' ? 'badge-pass' : (item.status === 'FAIL' ? 'badge-fail' : 'badge-warning');
            const hasDetails = item.details && item.details.length > 0;
            const pageDisplay = item.page_label || `Halaman ${item.page}`;

            let detailsHTML = '';
            if (hasDetails) {
                item.details.forEach(d => {
                    if (typeof d === 'object' && d !== null) {
                        let pageBadge = d.page_label ? `<span class="detail-page-badge" style="font-size:0.75rem; background:#f1f5f9; border:1px solid #e2e8f0; padding:2px 8px; border-radius:12px; margin-right:8px; color:#475569;"><i class="fa-regular fa-file-pdf"></i> ${d.page_label}</span>` : '';
                        let contextHTML = d.context ? `<div style="margin-top:4px; font-family:'JetBrains Mono',monospace; font-size:0.78rem; color:#d97706; background:#fffbeb; padding:4px 8px; border-radius:4px; border:1px solid #fef3c7;">${d.context}</div>` : '';
                        let suggHTML = d.suggestion ? `<div style="margin-top:6px; font-size:0.78rem; color:#059669; background:#ecfdf5; padding:6px 10px; border-radius:6px; border-left:3px solid #059669;"><i class="fa-solid fa-wrench"></i> <strong>Saran:</strong> ${d.suggestion}</div>` : '';
                        
                        detailsHTML += `
                            <div style="margin-bottom:10px; padding-bottom:8px; border-bottom:1px dashed #e2e8f0;">
                                <div>${pageBadge}<strong style="color:#0f172a; font-size:0.85rem;">${d.issue}</strong></div>
                                ${contextHTML}
                                ${suggHTML}
                            </div>
                        `;
                    } else {
                        detailsHTML += `<div style="margin-bottom:6px; font-size:0.85rem; color:#1e293b;">${d}</div>`;
                    }
                });
            } else {
                detailsHTML = `<span style="color:#059669; font-weight:600;"><i class="fa-solid fa-circle-check"></i> ${item.message}</span>`;
            }

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td style="text-align:center; font-weight:800; color:#e5322d; font-family:'JetBrains Mono',monospace;">Rule #${item.id}</td>
                <td>
                    <strong style="color:#0f172a; font-size:0.9rem;">${item.title}</strong>
                </td>
                <td><span class="anomaly-page-badge" style="background:#f1f5f9; color:#475569; padding:3px 10px; border-radius:12px; font-size:0.75rem; font-weight:700;">${pageDisplay}</span></td>
                <td style="text-align:center;"><span class="badge-status ${badgeClass}">${statusText}</span></td>
                <td style="vertical-align:top; line-height:1.5;">${detailsHTML}</td>
                <td style="font-size:0.8rem; color:#475569; vertical-align:top; line-height:1.5;">
                    <div style="margin-bottom:6px; background:#f8fafc; padding:6px 10px; border-radius:6px; border:1px solid #e2e8f0;">
                        ${item.explanation_standard || '-'}
                    </div>
                    <div style="background:#eff6ff; padding:6px 10px; border-radius:6px; border:1px solid #bfdbfe; color:#1e40af;">
                        <strong>💡 Rekomendasi:</strong> ${item.recommendation || '-'}
                    </div>
                </td>
            `;
            tbody.appendChild(tr);
        });
    }

    function renderAnomalyCards(anomalies, totalPages) {
        const container = document.getElementById('anomaly-cards-container');
        if (!container) return;
        container.innerHTML = '';

        const filteredAnomalies = (anomalies || []).filter(item => {
            if (currentFilterMode === 'issues') return item.status !== 'PASS';
            if (currentFilterMode === 'pass') return item.status === 'PASS';
            return true;
        });

        if (filteredAnomalies.length === 0) {
            container.innerHTML = `
                <div style="text-align:center; padding:32px; color:var(--text-secondary); background:var(--bg-surface); border-radius:var(--radius-md); border:1px solid var(--border-color);">
                    <i class="fa-solid fa-circle-check" style="font-size:2rem; color:var(--success); margin-bottom:12px;"></i>
                    <p style="font-weight:600;">Tidak ada parameter yang sesuai dengan filter '${currentFilterMode}'.</p>
                </div>
            `;
            return;
        }

        filteredAnomalies.forEach((item, idx) => {
            const statusClass = item.status === 'PASS' ? 'status-pass' : (item.status === 'FAIL' ? 'status-fail' : 'status-warning');
            const statusText = item.status === 'PASS' ? 'SESUAI' : (item.status === 'FAIL' ? 'EVALUASI' : 'CATATAN');
            const badgeClass = item.status === 'PASS' ? 'badge-pass' : (item.status === 'FAIL' ? 'badge-fail' : 'badge-warning');
            const hasDetails = item.details && item.details.length > 0;
            const isOpen = item.status !== 'PASS';
            
            const pageDisplay = item.page_label || `Halaman ${item.page}`;
            const totalPagesInfo = totalPages ? ` dari ${totalPages}` : '';
            
            const card = document.createElement('div');
            card.className = `anomaly-card ${statusClass}`;
            card.style.animationDelay = `${idx * 0.04}s`;

            // Build details HTML
            let detailsHTML = '';
            if (hasDetails) {
                item.details.forEach(d => {
                    if (typeof d === 'object' && d !== null) {
                        let suggestionHTML = d.suggestion ? `<div class="detail-suggestion" style="margin-top:10px; padding:10px; border-radius:6px; background:var(--success-bg); border-left:3px solid var(--success); color:var(--text-main); font-size:0.82rem;"><i class="fa-solid fa-wrench" style="color:var(--success); margin-right:6px;"></i> <strong>Saran Perbaikan:</strong> ${d.suggestion}</div>` : '';
                        let pageBadge = d.page_label ? `<span class="detail-page-badge" style="font-size:0.75rem; background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.1); padding:2px 8px; border-radius:12px; margin-right:8px; color:var(--text-secondary);"><i class="fa-regular fa-file-pdf"></i> ${d.page_label}</span>` : '';
                        
                        detailsHTML += `
                            <div class="anomaly-detail-item">
                                <div style="margin-bottom:6px;">${pageBadge}<span style="color:var(--text-bright);">${d.issue}</span></div>
                                ${suggestionHTML}
                            </div>
                        `;
                    } else {
                        let mainText = d;
                        const ctxMatch = typeof d === 'string' ? d.match(/(Konteks|Ditemukan|Contoh|Teks sel):\s*(".*?"|\\".*?\\")/) : null;
                        if (ctxMatch) {
                            mainText = d.substring(0, d.indexOf(ctxMatch[0]));
                        }
                        detailsHTML += `<div class="anomaly-detail-item">${mainText}</div>`;
                    }
                });
            }
            
            card.innerHTML = `
                <div class="anomaly-card-header" data-card-id="anomaly-body-${item.id}">
                    <div class="anomaly-card-left">
                        <div class="anomaly-num">${item.id}</div>
                        <div class="anomaly-title-area">
                            <h4>${item.title}</h4>
                            <span class="anomaly-page-badge">${pageDisplay}${totalPagesInfo} hal</span>
                        </div>
                    </div>
                    <div class="anomaly-card-right">
                        <span class="badge-status ${badgeClass}">${statusText}</span>
                        <button class="anomaly-toggle ${isOpen ? 'open' : ''}"><i class="fa-solid fa-chevron-down"></i></button>
                    </div>
                </div>
                <div class="anomaly-card-body ${isOpen ? 'open' : ''}" id="anomaly-body-${item.id}">
                    ${hasDetails ? detailsHTML : `<div class="anomaly-detail-item" style="border-left-color: var(--success);">${item.message}</div>`}
                    <div class="anomaly-standard">
                        ${item.explanation_standard || ''}
                    </div>
                    <div class="anomaly-recommendation">
                        <span>💡</span> ${item.recommendation || ''}
                    </div>
                </div>
            `;
            container.appendChild(card);
        });

        // Attach toggle listeners
        container.querySelectorAll('.anomaly-card-header').forEach(header => {
            header.addEventListener('click', function() {
                const bodyId = this.getAttribute('data-card-id');
                const body = document.getElementById(bodyId);
                const toggle = this.querySelector('.anomaly-toggle');
                if (body) body.classList.toggle('open');
                if (toggle) toggle.classList.toggle('open');
            });
        });
    }

    // ================================================================
    // RENDER: Multi-file Results
    // ================================================================
    function renderMultiResults(data) {
        multiResults = data.batch_results || [];
        
        const resultsSec = document.getElementById('results-section');
        if (resultsSec) resultsSec.classList.remove('hidden');

        const cardGreen = document.querySelector('.stat-card-green');
        if (cardGreen) cardGreen.classList.remove('hidden');
        const cardPurple = document.querySelector('.stat-card-purple');
        if (cardPurple) cardPurple.classList.remove('hidden');

        const regEl = document.getElementById('res-region');
        if (regEl) regEl.textContent = `${data.total_files || 0} Dokumen`;
        const totEl = document.getElementById('res-total');
        if (totEl) totEl.textContent = `${data.total_points_all || 0} Titik`;
        const anomEl = document.getElementById('res-anomalies');
        if (anomEl) anomEl.textContent = '100% Selesai';
        const ce95El = document.getElementById('res-ce95');
        if (ce95El) ce95El.textContent = '-';

        const multiNav = document.getElementById('multi-file-nav');
        multiNav.classList.remove('hidden');
        document.getElementById('vector-result-container').classList.add('hidden');
        document.getElementById('pdf-tabs-wrapper').classList.add('hidden');
        document.getElementById('exporter-section').classList.add('hidden');
        document.getElementById('multi-file-count').textContent = `${data.total_files || 0} File`;

        const tbody = document.getElementById('multi-file-tbody');
        tbody.innerHTML = '';

        multiResults.forEach((r, idx) => {
            const tr = document.createElement('tr');
            const statusBadge = r.status === 'error' 
                ? '<span class="badge-status badge-fail">GAGAL</span>' 
                : (r.is_skvt === false ? '<span class="badge-status badge-warning">NON-SKVT</span>' : '<span class="badge-status badge-pass">BERHASIL</span>');
            
            tr.innerHTML = `
                <td>${idx + 1}</td>
                <td><strong>${r.original_filename || r.filename || '-'}</strong></td>
                <td>${r.region || '-'}</td>
                <td>${r.total_points || 0} Titik</td>
                <td style="font-family:'JetBrains Mono',monospace;">${r.ce95 ? r.ce95.toFixed(4) + ' m' : '-'}</td>
                <td>${statusBadge}</td>
                <td>${r.status !== 'error' && r.is_skvt !== false ? `<button type="button" class="btn-view-detail" data-idx="${idx}" style="background:#0056A3; color:#fff; border:none; padding:5px 14px; border-radius:6px; font-weight:600; font-size:0.8rem; cursor:pointer;"><i class="fa-solid fa-chevron-down" id="icon-detail-${idx}"></i> Detail</button>` : '-'}</td>
            `;
            tbody.appendChild(tr);

            // Create Collapsible Dropdown Detail Row directly below
            if (r.status !== 'error' && r.is_skvt !== false) {
                const detailTr = document.createElement('tr');
                detailTr.id = `detail-row-${idx}`;
                detailTr.className = 'hidden';
                detailTr.style.background = '#f8fafc';

                const anomalies = r.anomalies_9 || [];
                let anomalyRowsHTML = '';
                anomalies.forEach(item => {
                    const stBadge = item.status === 'PASS' 
                        ? '<span class="badge-status badge-pass">SESUAI</span>' 
                        : (item.status === 'FAIL' ? '<span class="badge-status badge-fail">EVALUASI</span>' : '<span class="badge-status badge-warning">CATATAN</span>');
                    
                    let detailsListHTML = '';
                    if (item.details && item.details.length > 0) {
                        item.details.forEach(d => {
                            if (typeof d === 'object' && d !== null) {
                                let locBadge = d.page_label ? `<span style="font-size:0.75rem; background:#e2e8f0; padding:2px 8px; border-radius:10px; margin-right:6px; color:#334155; font-weight:600;">${d.page_label}</span>` : '';
                                let suggText = d.suggestion ? `<div style="margin-top:4px; font-size:0.78rem; color:#059669; background:#ecfdf5; padding:4px 8px; border-radius:4px;"><i class="fa-solid fa-wrench"></i> <strong>Saran:</strong> ${d.suggestion}</div>` : '';
                                detailsListHTML += `<div style="margin-bottom:6px; font-size:0.82rem;">${locBadge}<strong style="color:#0f172a;">${d.issue}</strong>${suggText}</div>`;
                            } else {
                                detailsListHTML += `<div style="margin-bottom:4px; font-size:0.82rem;">${d}</div>`;
                            }
                        });
                    } else {
                        detailsListHTML = `<span style="color:#059669; font-size:0.82rem; font-weight:600;"><i class="fa-solid fa-check-circle"></i> ${item.message}</span>`;
                    }

                    anomalyRowsHTML += `
                        <tr style="border-bottom:1px solid #e2e8f0;">
                            <td style="font-weight:700; color:#e5322d; text-align:center;">#${item.id}</td>
                            <td style="font-weight:700; color:#0f172a; font-size:0.85rem;">${item.title}</td>
                            <td style="text-align:center;">${stBadge}</td>
                            <td style="font-size:0.82rem; line-height:1.4;">${detailsListHTML}</td>
                            <td style="font-size:0.78rem; color:#475569; line-height:1.4;">
                                <div style="margin-bottom:4px;">${item.explanation_standard || '-'}</div>
                                <div style="color:#1e40af; background:#eff6ff; padding:3px 6px; border-radius:4px;"><strong>Saran:</strong> ${item.recommendation || '-'}</div>
                            </td>
                        </tr>
                    `;
                });

                detailTr.innerHTML = `
                    <td colspan="7" style="padding:16px 20px; border-bottom:2px solid #cbd5e1;">
                        <div style="background:#ffffff; border-radius:10px; border:1px solid #cbd5e1; padding:16px; box-shadow:0 4px 12px rgba(0,0,0,0.05);">
                            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; border-bottom:2px solid #0056A3; padding-bottom:8px;">
                                <h4 style="font-size:0.95rem; font-weight:800; color:#0056A3; margin:0;">
                                    <i class="fa-solid fa-list-check"></i> Detail Laporan Kesalahan & Catatan Audit — ${r.original_filename || r.filename}
                                </h4>
                                <span style="font-size:0.8rem; font-weight:700; color:#475569; background:#f1f5f9; padding:4px 12px; border-radius:14px; border:1px solid #cbd5e1;">
                                    Wilayah: ${r.region || '-'} | ${r.total_points || 0} Titik | CE95: ${r.ce95 ? r.ce95.toFixed(4) + 'm' : '-'}
                                </span>
                            </div>
                            <div class="table-container" style="max-height:400px; overflow-y:auto;">
                                <table class="table" style="font-size:0.82rem; width:100%;">
                                    <thead>
                                        <tr style="background:#0056A3; color:#ffffff;">
                                            <th style="width:40px;">No</th>
                                            <th style="width:200px;">Parameter Audit</th>
                                            <th style="width:90px; text-align:center;">Status</th>
                                            <th>Detail Temuan Laporan Kesalahan</th>
                                            <th style="width:260px;">Standar BIG & Rekomendasi</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        ${anomalyRowsHTML}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </td>
                `;
                tbody.appendChild(detailTr);
            }
        });

        // Detail button toggle handlers (Dropdown accordion in-line without navigating away)
        tbody.querySelectorAll('.btn-view-detail').forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                const idx = this.getAttribute('data-idx');
                const detailRow = document.getElementById(`detail-row-${idx}`);
                const icon = document.getElementById(`icon-detail-${idx}`);

                if (detailRow) {
                    const isHidden = detailRow.classList.contains('hidden');
                    if (isHidden) {
                        detailRow.classList.remove('hidden');
                        if (icon) icon.className = 'fa-solid fa-chevron-up';
                        this.style.background = '#e5322d';
                    } else {
                        detailRow.classList.add('hidden');
                        if (icon) icon.className = 'fa-solid fa-chevron-down';
                        this.style.background = '#0056A3';
                    }
                }
            });
        });

        // Setup Direct Batch PDF Download Button (Below table)
        const batchPdfBtn = document.getElementById('btn-download-batch-pdf');
        if (batchPdfBtn && data.pdf_base64) {
            batchPdfBtn.onclick = function() {
                const byteCharacters = atob(data.pdf_base64);
                const byteNumbers = new Array(byteCharacters.length);
                for (let i = 0; i < byteCharacters.length; i++) byteNumbers[i] = byteCharacters.charCodeAt(i);
                const pdfBlob = new Blob([new Uint8Array(byteNumbers)], {type: 'application/pdf'});
                const url = window.URL.createObjectURL(pdfBlob);
                const a = document.createElement('a'); a.href = url;
                a.download = data.filename || 'Laporan_Konsolidasi_Batch_Veridoc.pdf';
                document.body.appendChild(a); a.click();
                window.URL.revokeObjectURL(url);
            };
        }

        resultsSec.scrollIntoView({ behavior: 'smooth' });
    }

    // ================================================================
    // RENDER: Map Vision Audit Results (4 Pengecekan Peta)
    // ================================================================
    // RENDER: Map Vision Audit Results (Gemini Vision AI)
    // ================================================================
    function renderMapResults(data) {
        const getBadgeHtml = (status) => {
            if (status === 'PASS' || status === 'PASS_COMPLETELY') {
                return `<span class="badge badge-success" style="font-weight:700; padding:6px 14px; border-radius:20px; background:#ecfdf5; color:#059669; border:1px solid #a7f3d0;"><i class="fa-solid fa-circle-check"></i> Sesuai / PASS</span>`;
            }
            if (status === 'WARNING') {
                return `<span class="badge badge-warning" style="font-weight:700; padding:6px 14px; border-radius:20px; background:#fffbeb; color:#d97706; border:1px solid #fde68a;"><i class="fa-solid fa-triangle-exclamation"></i> Warning</span>`;
            }
            return `<span class="badge badge-danger" style="font-weight:700; padding:6px 14px; border-radius:20px; background:#fef2f2; color:#dc2626; border:1px solid #fecaca;"><i class="fa-solid fa-circle-xmark"></i> FAIL / Tidak Sesuai</span>`;
        };

        const baca = data.bisa_baca_peta || {};
        const typo = data.periksa_typo_peta || {};
        const coord = data.kesesuaian_koordinat_legenda_vs_peta || {};
        const overlap = data.keterangan_tk_bertumpuk || {};
        const grid = data.pemeriksaan_grid_koordinat || {};

        const bBaca = document.getElementById('map-stat-baca');
        if (bBaca) bBaca.innerHTML = getBadgeHtml(baca.status || 'PASS');
        const bTypo = document.getElementById('map-stat-typo');
        if (bTypo) bTypo.innerHTML = getBadgeHtml(typo.status || 'PASS');
        const bCoord = document.getElementById('map-stat-coord');
        if (bCoord) bCoord.innerHTML = getBadgeHtml(coord.status || 'PASS');
        const bOverlap = document.getElementById('map-stat-overlap');
        if (bOverlap) bOverlap.innerHTML = getBadgeHtml(overlap.status || 'PASS');

        const regEl = document.getElementById('res-region');
        if (regEl) {
            let regionName = data.region;
            if (!regionName || regionName === 'Peta Lampiran SKVT BIG') {
                if (typeof mapAuditFile !== 'undefined' && mapAuditFile && mapAuditFile.name) {
                    regionName = mapAuditFile.name.replace(/\.[^/.]+$/, "").replace(/_/g, " ").replace(/-/g, " ");
                    regionName = regionName.replace(/^(peta|skvt|laporan|audit)\s+/i, "").trim();
                }
            }
            regEl.textContent = regionName || 'Peta Lampiran SKVT BIG';
        }

        const modelUsed = data.ai_model_used || "gemini-2.0-flash";
        const anomEl = document.getElementById('res-anomalies');
        if (anomEl) anomEl.textContent = `5 Parameter (${modelUsed})`;

        const cardGreen = document.querySelector('.stat-card-green');
        if (cardGreen) cardGreen.classList.add('hidden');
        const cardPurple = document.querySelector('.stat-card-purple');
        if (cardPurple) cardPurple.classList.add('hidden');

        const multiNav = document.getElementById('multi-file-nav');
        if (multiNav) multiNav.classList.add('hidden');
        
        const mapContainer = document.getElementById('map-result-container');
        if (mapContainer) mapContainer.classList.remove('hidden');
        
        const pdfWrapper = document.getElementById('pdf-tabs-wrapper');
        if (pdfWrapper) pdfWrapper.classList.add('hidden');
        
        const exporterSec = document.getElementById('exporter-section');
        if (exporterSec) exporterSec.classList.add('hidden');

        let detailsHtml = `
            <div style="display:flex; flex-direction:column; gap:16px; margin-top:16px;">
                <div style="font-size:0.85rem; background:#eff6ff; border:1px solid #bfdbfe; color:#1e40af; padding:8px 14px; border-radius:8px; font-weight:600; display:flex; align-items:center; gap:8px;">
                    <i class="fa-solid fa-wand-magic-sparkles"></i> Model Gemini AI Aktif: <strong>${modelUsed}</strong> (Multimodal Visual Inspector)
                </div>

                <!-- 1. Keterbacaan Peta -->
                <div class="card" style="padding:20px; border-radius:12px; background:#ffffff; border:1px solid var(--border-color); border-left:5px solid ${baca.status === 'PASS' ? '#059669' : '#dc2626'}; box-shadow:0 2px 8px rgba(0,0,0,0.04);">
                    <h4 style="margin:0 0 8px 0; color:var(--text-bright); font-size:1.05rem; font-weight:800; display:flex; align-items:center; gap:8px;">
                        <i class="fa-solid fa-map" style="color:var(--accent-blue);"></i> 1. Keterbacaan & Kualitas Peta (Bisa Baca Peta)
                    </h4>
                    <p style="margin:0; color:var(--text-secondary); font-size:0.92rem; line-height:1.6;">
                        ${baca.catatan || 'Peta berhasil diekstrak dan dibaca utuh. Layout legenda, skala, orientasi utara, dan area peta terverifikasi jelas.'}
                    </p>
                    ${baca.kualitas_peta ? `<div style="margin-top:8px; font-size:0.82rem; color:var(--text-muted); font-weight:600;"><i class="fa-solid fa-circle-info"></i> Kualitas Peta: ${baca.kualitas_peta}</div>` : ''}
                </div>

                <!-- 2. Periksa Typo -->
                <div class="card" style="padding:20px; border-radius:12px; background:#ffffff; border:1px solid var(--border-color); border-left:5px solid ${typo.status === 'PASS' ? '#059669' : '#d97706'}; box-shadow:0 2px 8px rgba(0,0,0,0.04);">
                    <h4 style="margin:0 0 8px 0; color:var(--text-bright); font-size:1.05rem; font-weight:800; display:flex; align-items:center; gap:8px;">
                        <i class="fa-solid fa-spell-check" style="color:var(--accent-purple);"></i> 2. Hasil Pemeriksaan Typo di Peta & Legenda
                    </h4>
                    <p style="margin:0 0 8px 0; color:var(--text-secondary); font-size:0.92rem; line-height:1.6;">
                        ${typo.catatan || 'Pemeriksaan ejaan pada judul peta, tabel legenda, dan nama wilayah terverifikasi sesuai KBBI/Pedoman Geodesi.'}
                    </p>
                    ${(typo.typo_ditemukan && typo.typo_ditemukan.length > 0) ? `
                        <ul style="margin:8px 0 0 20px; padding:0; color:#dc2626; font-size:0.9rem; line-height:1.5;">
                            ${typo.typo_ditemukan.map(t => `<li>Typo <strong>"${t.kata_salah}"</strong> pada ${t.lokasi || 'Peta'} &rarr; Saran perbaikan: <strong style="color:#059669;">"${t.saran_perbaikan}"</strong></li>`).join('')}
                        </ul>
                    ` : ''}
                </div>

                <!-- 3. Kesesuaian Koordinat Legenda vs Peta -->
                <div class="card" style="padding:20px; border-radius:12px; background:#ffffff; border:1px solid var(--border-color); border-left:5px solid ${coord.status === 'PASS' ? '#059669' : '#dc2626'}; box-shadow:0 2px 8px rgba(0,0,0,0.04);">
                    <h4 style="margin:0 0 8px 0; color:var(--text-bright); font-size:1.05rem; font-weight:800; display:flex; align-items:center; gap:8px;">
                        <i class="fa-solid fa-location-crosshairs" style="color:var(--accent-amber);"></i> 3. Kesesuaian Koordinat TK Legenda vs Peta Utama
                    </h4>
                    <p style="margin:0 0 8px 0; color:var(--text-secondary); font-size:0.92rem; line-height:1.6;">
                        ${coord.catatan || 'Koordinat Titik Kartometrik (TK) pada tabel legenda terverifikasi presisi dan sesuai dengan angka pada titik lokasi peta.'}
                    </p>
                    ${(coord.ketidaksesuaian && coord.ketidaksesuaian.length > 0) ? `
                        <ul style="margin:8px 0 0 20px; padding:0; color:#dc2626; font-size:0.9rem; line-height:1.5;">
                            ${coord.ketidaksesuaian.map(c => `<li>Titik <strong>${c.titik_tk}</strong>: Legenda (${c.koordinat_legenda}) vs Peta (${c.koordinat_peta}) &rarr; ${c.catatan}</li>`).join('')}
                        </ul>
                    ` : ''}
                </div>

                <!-- 4. Keterangan Titik TK Bertumpuk -->
                <div class="card" style="padding:20px; border-radius:12px; background:#ffffff; border:1px solid var(--border-color); border-left:5px solid ${overlap.status === 'PASS' ? '#059669' : '#d97706'}; box-shadow:0 2px 8px rgba(0,0,0,0.04);">
                    <h4 style="margin:0 0 8px 0; color:var(--text-bright); font-size:1.05rem; font-weight:800; display:flex; align-items:center; gap:8px;">
                        <i class="fa-solid fa-layer-group" style="color:var(--accent-emerald);"></i> 4. Keterangan Titik TK Bertumpuk / Tidak Terbaca
                    </h4>
                    <p style="margin:0 0 8px 0; color:var(--text-secondary); font-size:0.92rem; line-height:1.6;">
                        ${overlap.catatan || 'Teks penomoran titik TK dan angka koordinat teratur rapi tanpa ada indikasi bertumpuk atau terpotong.'}
                    </p>
                    ${(overlap.teks_bertumpuk_ditemukan && overlap.teks_bertumpuk_ditemukan.length > 0) ? `
                        <ul style="margin:8px 0 0 20px; padding:0; color:#d97706; font-size:0.9rem; line-height:1.5;">
                            ${overlap.teks_bertumpuk_ditemukan.map(o => `<li>Titik <strong>${o.titik_tk}</strong> di ${o.lokasi}: ${o.catatan}</li>`).join('')}
                        </ul>
                    ` : ''}
                </div>

                <!-- 5. Pemeriksaan Grid Koordinat & Gratikul Peta -->
                <div class="card" style="padding:20px; border-radius:12px; background:#ffffff; border:1px solid var(--border-color); border-left:5px solid ${grid.status === 'PASS' ? '#059669' : '#dc2626'}; box-shadow:0 2px 8px rgba(0,0,0,0.04);">
                    <h4 style="margin:0 0 8px 0; color:var(--text-bright); font-size:1.05rem; font-weight:800; display:flex; align-items:center; gap:8px;">
                        <i class="fa-solid fa-border-all" style="color:#0284c7;"></i> 5. Pemeriksaan Grid Koordinat & Gratikul Peta
                    </h4>
                    <p style="margin:0 0 8px 0; color:var(--text-secondary); font-size:0.92rem; line-height:1.6;">
                        ${grid.catatan || 'Garis Grid Koordinat (Gratikul Spasial) & angka koordinat tepi bingkai peta terdeteksi lengkap, konsisten, dan sesuai format geodesi BIG.'}
                    </p>
                    <div style="display:flex; align-items:center; gap:12px; margin-top:8px;">
                        <span style="font-size:0.85rem; font-weight:700; color:var(--text-main);">Status Grid Spasial:</span>
                        ${getBadgeHtml(grid.status || 'PASS')}
                    </div>
                </div>
            </div>
        `;

        const detailsEl = document.getElementById('map-audit-details');
        if (detailsEl) detailsEl.innerHTML = detailsHtml;

        const resultsSection = document.getElementById('results-section');
        if (resultsSection) {
            resultsSection.classList.remove('hidden');
            resultsSection.scrollIntoView({ behavior: 'smooth' });
        }
    }



    // ================================================================
    // LEAFLET MAP
    // ================================================================
    function initLeafletMap(points) {
        if (!points || points.length === 0) return;
        const mapContainer = document.getElementById('leaflet-map');
        if (!mapContainer || typeof L === 'undefined') return;

        try {
            if (leafletMap) { leafletMap.remove(); leafletMap = null; }
        } catch (e) { leafletMap = null; }

        try {
            const osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 });
            const esriSatLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { maxZoom: 19 });

            leafletMap = L.map('leaflet-map', { preferCanvas: true, layers: [osmLayer] });
            L.control.layers({ "OpenStreetMap": osmLayer, "Esri Satelit": esriSatLayer }).addTo(leafletMap);
            leafletMarkersGroup = L.layerGroup().addTo(leafletMap);

            let latLngs = [];
            points.forEach(p => {
                const marker = L.circleMarker([p.lat_dd, p.lon_dd], {
                    radius: 6, fillColor: '#6366f1', color: '#ffffff', weight: 2, fillOpacity: 0.85
                });
                marker.bindPopup(`<strong>${p.code}</strong><br>Halaman: ${p.page}<br>UTM: ${p.doc_x}, ${p.doc_y}`);
                leafletMarkersGroup.addLayer(marker);
                latLngs.push([p.lat_dd, p.lon_dd]);
            });

            if (latLngs.length > 0) {
                currentMapBounds = L.latLngBounds(latLngs);
                leafletMap.fitBounds(currentMapBounds, { padding: [30, 30] });
            }
        } catch (err) { console.warn("Leaflet error:", err); }
    }

    // ================================================================
    // EXPORTERS
    // ================================================================
    function downloadLauncherShortcut() {
        const htmlContent = `<!DOCTYPE html><html><head><meta http-equiv="refresh" content="0; url=${window.location.origin}/"><title>Veridoc Launcher</title></head><body>Redirecting to Veridoc...</body></html>`;
        const blob = new Blob([htmlContent], { type: 'text/html' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a'); a.href = url;
        a.download = 'Buka_Veridoc.html';
        document.body.appendChild(a); a.click(); window.URL.revokeObjectURL(url);
    }

    const headerLauncherBtn = document.getElementById('btn-header-launcher');
    if (headerLauncherBtn) {
        headerLauncherBtn.addEventListener('click', downloadLauncherShortcut);
    }

    function setupExporters(data) {
        if (!data) return;

        const pdfBtn = document.getElementById('btn-download-pdf');
        if (pdfBtn && data.pdf_base64) {
            pdfBtn.onclick = function() {
                const byteCharacters = atob(data.pdf_base64);
                const byteNumbers = new Array(byteCharacters.length);
                for (let i = 0; i < byteCharacters.length; i++) byteNumbers[i] = byteCharacters.charCodeAt(i);
                const pdfBlob = new Blob([new Uint8Array(byteNumbers)], {type: 'application/pdf'});
                const url = window.URL.createObjectURL(pdfBlob);
                const a = document.createElement('a'); a.href = url;
                a.download = data.filename || 'Laporan_Veridoc.pdf';
                document.body.appendChild(a); a.click();
                window.URL.revokeObjectURL(url);
            };
        }

        const geoBtn = document.getElementById('btn-export-geojson');
        if (geoBtn) {
            geoBtn.onclick = async function() {
                const res = await fetch('/api/export/geojson', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ points: data.all_points || [] })
                });
                const blob = await res.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a'); a.href = url;
                a.download = `Veridoc_${(data.region || 'Export').replace(/[\s,]+/g, '_')}.geojson`;
                document.body.appendChild(a); a.click(); window.URL.revokeObjectURL(url);
            };
        }

        const kmlBtn = document.getElementById('btn-export-kml');
        if (kmlBtn) {
            kmlBtn.onclick = async function() {
                const res = await fetch('/api/export/kml', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ points: data.all_points || [] })
                });
                const blob = await res.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a'); a.href = url;
                a.download = `Veridoc_${(data.region || 'Export').replace(/[\s,]+/g, '_')}.kml`;
                document.body.appendChild(a); a.click(); window.URL.revokeObjectURL(url);
            };
        }

        const csvBtn = document.getElementById('btn-export-csv');
        if (csvBtn) {
            csvBtn.onclick = function() {
                let csv = "data:text/csv;charset=utf-8,No,Kode,Halaman,Lat_DD,Lon_DD,Doc_X,Doc_Y\n";
                (data.all_points || []).forEach(p => {
                    csv += `${p.id},"${p.code}",${p.page},${p.lat_dd},${p.lon_dd},${p.doc_x},${p.doc_y}\n`;
                });
                const a = document.createElement('a'); a.href = encodeURI(csv);
                a.download = `Veridoc_${(data.region || 'Export').replace(/[\s,]+/g, '_')}.csv`;
                document.body.appendChild(a); a.click();
            };
        }

        const launcherBtn = document.getElementById('btn-download-shortcut');
        if (launcherBtn) {
            launcherBtn.onclick = downloadLauncherShortcut;
        }
    }

    // ================================================================
    // AI ENGINE INFO
    // ================================================================
    async function loadAiModelsInfo() {
        try {
            const res = await fetch('/api/ai-info');
            const data = await res.json();
            if (data.status === 'success' && data.ai_models) {
                const container = document.getElementById('ai-models-cards-container');
                if (!container) return;
                container.innerHTML = '';
                data.ai_models.forEach(model => {
                    const card = document.createElement('div');
                    card.className = 'ai-card';
                    card.innerHTML = `
                        <div class="ai-card-header">
                            <span class="ai-card-title"><i class="fa-solid fa-microchip" style="color:var(--accent-purple);margin-right:6px;"></i> ${model.name}</span>
                            <span class="ai-card-badge">${model.category}</span>
                        </div>
                        <p class="ai-card-reason"><strong style="color:var(--text-main);">Alasan:</strong> ${model.reason}</p>
                        <div class="ai-card-accuracy"><i class="fa-solid fa-shield-check" style="margin-right:4px;"></i> ${model.accuracy}</div>
                    `;
                    container.appendChild(card);
                });
            }
        } catch (e) { console.warn("AI info:", e); }
    }

    // ================================================================
    // WILAYAH CONSISTENCY AUDIT RENDERER
    // ================================================================
    function renderWilayahConsistencyAudit(wilayahAudit) {
        const badgeEl = document.getElementById('wilayah-status-badge');
        const tbodyEl = document.getElementById('wilayah-audit-tbody');
        if (!badgeEl || !tbodyEl) return;

        tbodyEl.innerHTML = '';
        if (!wilayahAudit || !wilayahAudit.items || wilayahAudit.items.length === 0) {
            badgeEl.style.background = '#f1f5f9';
            badgeEl.style.color = '#475569';
            badgeEl.innerHTML = '<i class="fa-solid fa-circle-question"></i> Tidak Ada Data Kode Wilayah';
            tbodyEl.innerHTML = '<tr><td colspan="7" style="text-align:center; color:#64748b; padding:20px;">Tidak terdeteksi Kode Wilayah 10-digit bertitik pada dokumen ini.</td></tr>';
            return;
        }

        const isPass = (wilayahAudit.status === 'PASS');
        if (isPass) {
            badgeEl.style.background = '#dcfce7';
            badgeEl.style.color = '#15803d';
            badgeEl.innerHTML = '<i class="fa-solid fa-circle-check"></i> ✓ Kode Wilayah Sesuai';
        } else {
            badgeEl.style.background = '#fee2e2';
            badgeEl.style.color = '#b91c1c';
            badgeEl.innerHTML = '<i class="fa-solid fa-circle-xmark"></i> ✗ Kode Wilayah Tidak Sesuai';
        }

        wilayahAudit.items.forEach((item, index) => {
            const tr = document.createElement('tr');
            const isValid = item.is_valid;
            
            let mismatchBadge = '<span style="color:#16a34a; font-weight:700;"><i class="fa-solid fa-check"></i> Sesuai</span>';
            if (item.mismatch_type) {
                if (item.mismatch_type.includes("Perlu Verifikasi Manual")) {
                    mismatchBadge = `<span style="background:#fef3c7; color:#b45309; border:1px solid #fde68a; padding:4px 8px; border-radius:6px; font-weight:700; font-size:0.8rem; display:inline-block;"><i class="fa-solid fa-triangle-exclamation"></i> ${item.mismatch_type}</span>`;
                } else {
                    mismatchBadge = `<span style="background:#fee2e2; color:#991b1b; border:1px solid #fecaca; padding:4px 8px; border-radius:6px; font-weight:700; font-size:0.8rem; display:inline-block;"><i class="fa-solid fa-circle-xmark"></i> ${item.mismatch_type}</span>`;
                }
            }

            let warningHTML = '';
            if (item.context_warning) {
                warningHTML = `<div style="margin-top:6px; background:#fffbeb; color:#b45309; border:1px solid #fef3c7; border-left:3px solid #d97706; padding:6px 10px; border-radius:6px; font-size:0.8rem; font-weight:600;"><i class="fa-solid fa-circle-exclamation"></i> <strong>Peringatan Konteks:</strong> ${item.context_warning}</div>`;
            }

            tr.innerHTML = `
                <td style="text-align:center; font-weight:700;">${index + 1}</td>
                <td><small style="color:#64748b; font-weight:600;">${item.source || '-'}</small></td>
                <td><code style="color:#0056a3; font-weight:700; font-size:0.9rem;">${item.code_in_doc}</code></td>
                <td><strong style="color:#1e293b;">${item.written_in_doc || '-'}</strong></td>
                <td><strong style="color:#0f766e;">${item.expected_from_db || '-'}</strong></td>
                <td>${mismatchBadge}</td>
                <td style="font-size:0.85rem; color:#334155; line-height:1.4;">
                    <div>${item.recommendation || '-'}</div>
                    ${warningHTML}
                </td>
            `;
            if (!isValid) {
                tr.style.background = '#fffdf5';
            }
            tbodyEl.appendChild(tr);
        });
    }

    // ================================================================
    // MAP ELEMENTS INSPECTION RENDERER (10 Unsur Peta)
    // ================================================================
    function renderMapElementsAudit(mapElementsAudit) {
        const badgeEl = document.getElementById('map-elements-status-badge');
        const tbodyEl = document.getElementById('map-elements-audit-tbody');
        if (!badgeEl || !tbodyEl) return;

        tbodyEl.innerHTML = '';
        if (!mapElementsAudit || !mapElementsAudit.items || mapElementsAudit.items.length === 0) {
            badgeEl.style.background = '#f1f5f9';
            badgeEl.style.color = '#475569';
            badgeEl.innerHTML = '<i class="fa-solid fa-circle-question"></i> Tidak Ada Data Unsur Peta';
            tbodyEl.innerHTML = '<tr><td colspan="7" style="text-align:center; color:#64748b; padding:20px;">Unggah dokumen peta untuk memulai pemeriksaan visual 10 unsur peta.</td></tr>';
            return;
        }

        const isPass = (mapElementsAudit.status === 'Sesuai' || mapElementsAudit.status === 'PASS');
        if (isPass) {
            badgeEl.style.background = '#dcfce7';
            badgeEl.style.color = '#15803d';
            badgeEl.innerHTML = `<i class="fa-solid fa-circle-check"></i> ✓ Unsur Peta Lengkap (${mapElementsAudit.unsur_ada}/${mapElementsAudit.total_unsur})`;
        } else if (mapElementsAudit.status === 'Perlu Verifikasi') {
            badgeEl.style.background = '#fef3c7';
            badgeEl.style.color = '#b45309';
            badgeEl.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> Perlu Verifikasi (${mapElementsAudit.unsur_perlu_verifikasi} Unsur)`;
        } else {
            badgeEl.style.background = '#fee2e2';
            badgeEl.style.color = '#b91c1c';
            badgeEl.innerHTML = `<i class="fa-solid fa-circle-xmark"></i> ✗ Unsur Peta Tidak Lengkap (${mapElementsAudit.unsur_tidak_ada} Tidak Ada)`;
        }

        mapElementsAudit.items.forEach((item, index) => {
            const tr = document.createElement('tr');
            
            let statusBadge = '';
            if (item.status === 'Ada' || item.status === 'Sesuai') {
                statusBadge = `<span style="background:#dcfce7; color:#15803d; border:1px solid #bbf7d0; padding:4px 10px; border-radius:6px; font-weight:700; font-size:0.8rem; display:inline-block;"><i class="fa-solid fa-check"></i> ${item.status}</span>`;
            } else if (item.status === 'Perlu Verifikasi') {
                statusBadge = `<span style="background:#fef3c7; color:#b45309; border:1px solid #fde68a; padding:4px 10px; border-radius:6px; font-weight:700; font-size:0.8rem; display:inline-block;"><i class="fa-solid fa-triangle-exclamation"></i> ${item.status}</span>`;
            } else {
                statusBadge = `<span style="background:#fee2e2; color:#991b1b; border:1px solid #fecaca; padding:4px 10px; border-radius:6px; font-weight:700; font-size:0.8rem; display:inline-block;"><i class="fa-solid fa-xmark"></i> ${item.status}</span>`;
            }

            const confDisplay = `<span style="font-family:'JetBrains Mono',monospace; font-weight:700; color:#0056a3;">${item.confidence || 0}%</span>`;

            tr.innerHTML = `
                <td style="text-align:center; font-weight:700;">${index + 1}</td>
                <td><strong style="color:#1e293b;">${item.nama_unsur}</strong></td>
                <td style="text-align:center;">${statusBadge}</td>
                <td style="text-align:center;">${confDisplay}</td>
                <td><small style="color:#475569; font-weight:600;"><i class="fa-solid fa-gear"></i> ${item.metode || '-'}</small></td>
                <td style="font-size:0.85rem; color:#334155;">${item.penjelasan || '-'}</td>
                <td style="font-size:0.85rem; color:#0f766e; line-height:1.4;">${item.rekomendasi || '-'}</td>
            `;

            if (item.status === 'Tidak Ada' || item.status === 'Tidak Sesuai') {
                tr.style.background = '#fff5f5';
            } else if (item.status === 'Perlu Verifikasi') {
                tr.style.background = '#fffdf5';
            }
            tbodyEl.appendChild(tr);
        });
    }

    loadAiModelsInfo();
});


