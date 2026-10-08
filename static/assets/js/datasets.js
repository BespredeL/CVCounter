/**
 * Dataset hub UI (list + detail + training).
 * Developed by: Aleksandr Kireev — https://bespredel.name
 */

(function () {
    const t = (key) => (typeof window.trans === 'function' ? window.trans(key) : key);

    function toast(message, type) {
        if (typeof window.showToast === 'function') {
            window.showToast(message, type || 'primary');
            return;
        }
        const el = document.getElementById('alert-container');
        if (!el) return;
        el.innerHTML = `<div class="alert alert-${type || 'info'} alert-dismissible fade show" role="alert">${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>`;
    }

    function setBusy(btn, busy) {
        if (!btn) return;
        btn.classList.toggle('is-busy', !!busy);
        btn.disabled = !!busy;
    }

    async function api(url, options) {
        const opts = Object.assign({}, options || {});
        opts.headers = Object.assign({
            'X-Requested-With': 'XMLHttpRequest',
        }, opts.headers || {});
        if (opts.json !== undefined) {
            opts.headers['Content-Type'] = 'application/json';
            opts.body = JSON.stringify(opts.json);
            delete opts.json;
        }
        const res = await fetch(url, opts);
        const data = await res.json().catch(() => ({}));
        if (!res.ok || data.status === 'error') {
            throw new Error(data.message || res.statusText || t('Request failed'));
        }
        return data;
    }

    // ---- list page ----
    const listPage = document.getElementById('datasets-page');
    if (listPage) {
        const form = document.getElementById('create-dataset-form');
        const errEl = document.getElementById('create-dataset-error');
        const submitBtn = document.getElementById('create-dataset-submit');
        form?.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (errEl) {
                errEl.classList.add('d-none');
                errEl.textContent = '';
            }
            setBusy(submitBtn, true);
            try {
                const data = await api(listPage.dataset.createUrl, {
                    method: 'POST',
                    json: {
                        name: document.getElementById('ds-name').value,
                        classes: document.getElementById('ds-classes').value,
                        task: document.getElementById('ds-task').value,
                    },
                });
                window.location.href = `/datasets/${encodeURIComponent(data.dataset.name)}`;
            } catch (err) {
                if (errEl) {
                    errEl.textContent = err.message;
                    errEl.classList.remove('d-none');
                } else {
                    toast(err.message, 'danger');
                }
                setBusy(submitBtn, false);
            }
        });

        const searchInput = document.getElementById('dataset-search-input');
        const emptyResults = document.getElementById('no-search-results');
        searchInput?.addEventListener('input', (e) => {
            const query = (e.target.value || '').trim().toLowerCase();
            let visibleCount = 0;
            document.querySelectorAll('.dataset-item-col').forEach((col) => {
                const searchData = col.dataset.search || '';
                const match = !query || searchData.includes(query);
                col.style.display = match ? '' : 'none';
                if (match) visibleCount += 1;
            });
            if (emptyResults) {
                emptyResults.classList.toggle('d-none', visibleCount > 0);
            }
        });
    }

    // ---- detail page ----
    const detail = document.getElementById('dataset-detail');
    if (!detail) return;

    const name = detail.dataset.name;

    function selectedImages() {
        return Array.from(new Set(Array.from(document.querySelectorAll('.img-check:checked')).map((el) => el.value)));
    }

    function withBusy(btn, fn) {
        return async () => {
            setBusy(btn, true);
            try {
                await fn();
            } catch (err) {
                toast(err.message || t('Request failed'), 'danger');
            } finally {
                setBusy(btn, false);
            }
        };
    }

    function updateSelectionState() {
        const selected = selectedImages();
        const counterEl = document.getElementById('selected-counter');
        const counterNum = document.getElementById('selected-counter-num');
        const autolabelText = document.getElementById('btn-autolabel-text');

        if (counterEl && counterNum) {
            counterNum.textContent = String(selected.length);
            counterEl.classList.toggle('d-none', selected.length === 0);
        }
        if (autolabelText) {
            autolabelText.textContent = selected.length > 0
                ? t('Auto-label selected ({n})', { n: selected.length })
                : t('Auto-label');
        }
    }

    // Sync checkboxes across table and grid view
    document.addEventListener('change', (e) => {
        if (e.target && e.target.classList.contains('img-check')) {
            const val = e.target.value;
            const state = e.target.checked;
            document.querySelectorAll(`.img-check[value="${CSS.escape(val)}"]`).forEach((cb) => {
                if (cb !== e.target) cb.checked = state;
            });
            updateSelectionState();
        }
    });

    document.getElementById('check-all-images')?.addEventListener('change', (e) => {
        const checked = e.target.checked;
        document.querySelectorAll('#images-tbody tr:not([style*="display: none"]) .img-check').forEach((c) => {
            c.checked = checked;
            document.querySelectorAll(`.img-check[value="${CSS.escape(c.value)}"]`).forEach((other) => {
                other.checked = checked;
            });
        });
        updateSelectionState();
    });

    function formatImportResult(data) {
        const imported = Number(data.imported || 0);
        const skipped = Number(data.skipped || 0);
        let msg = `${t('Imported')}: ${imported}`;
        if (skipped) {
            msg += ` · ${t('Skipped (already in dataset)')}: ${skipped}`;
        }
        return { msg, imported, skipped };
    }

    document.getElementById('btn-import-camera')?.addEventListener('click', withBusy(
        document.getElementById('btn-import-camera'),
        async () => {
            const loc = document.getElementById('import-location').value;
            const data = await api(`/datasets/api/${name}/import/camera`, {
                method: 'POST',
                json: { location: loc, split: 'inbox' },
            });
            const { msg, imported } = formatImportResult(data);
            toast(msg, imported ? 'success' : 'info');
            if (imported) setTimeout(() => window.location.reload(), 500);
        },
    ));

    document.getElementById('btn-import-upload')?.addEventListener('click', withBusy(
        document.getElementById('btn-import-upload'),
        async () => {
            const input = document.getElementById('import-files');
            if (!input.files.length) {
                toast(t('No files uploaded'), 'warning');
                return;
            }
            const fd = new FormData();
            Array.from(input.files).forEach((f) => fd.append('files', f));
            fd.append('split', 'inbox');
            const res = await fetch(`/datasets/api/${name}/import/upload`, {
                method: 'POST',
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                body: fd,
            });
            const data = await res.json();
            if (data.status === 'error') throw new Error(data.message);
            const { msg, imported } = formatImportResult(data);
            toast(msg, imported ? 'success' : 'info');
            if (imported) setTimeout(() => window.location.reload(), 500);
        },
    ));

    document.getElementById('btn-import-recording')?.addEventListener('click', withBusy(
        document.getElementById('btn-import-recording'),
        async () => {
            const path = document.getElementById('import-recording').value;
            if (!path) {
                toast(t('Select recording'), 'warning');
                return;
            }
            const data = await api(`/datasets/api/${name}/import/recording`, {
                method: 'POST',
                json: {
                    path,
                    every_n: Number(document.getElementById('rec-every-n').value || 10),
                    max_frames: Number(document.getElementById('rec-max').value || 200),
                },
            });
            const { msg, imported } = formatImportResult(data);
            toast(msg, imported ? 'success' : 'info');
            if (imported) setTimeout(() => window.location.reload(), 500);
        },
    ));

    document.getElementById('btn-auto-split')?.addEventListener('click', withBusy(
        document.getElementById('btn-auto-split'),
        async () => {
            const data = await api(`/datasets/api/${name}/split`, {
                method: 'POST',
                json: { val_ratio: Number(document.getElementById('val-ratio').value || 0.2) },
            });
            toast(`${t('Train')}: ${data.train}, ${t('Val')}: ${data.val}`, 'success');
            setTimeout(() => window.location.reload(), 500);
        },
    ));

    document.getElementById('btn-copy-inbox')?.addEventListener('click', async () => {
        const text = detail.dataset.inboxPath || document.getElementById('inbox-path-text')?.textContent || '';
        try {
            await navigator.clipboard.writeText(text);
            toast(t('Copied'), 'success');
        } catch (_) {
            toast(text, 'info');
        }
    });

    async function moveSelected(split) {
        const images = selectedImages();
        if (!images.length) {
            toast(t('No images'), 'warning');
            return;
        }
        await api(`/datasets/api/${name}/images/move`, { method: 'POST', json: { images, split } });
        window.location.reload();
    }

    document.getElementById('btn-move-train')?.addEventListener('click', () => {
        moveSelected('train').catch((err) => toast(err.message, 'danger'));
    });
    document.getElementById('btn-move-val')?.addEventListener('click', () => {
        moveSelected('val').catch((err) => toast(err.message, 'danger'));
    });
    document.getElementById('btn-move-inbox')?.addEventListener('click', () => {
        moveSelected('inbox').catch((err) => toast(err.message, 'danger'));
    });

    document.getElementById('btn-delete-images')?.addEventListener('click', async () => {
        const images = selectedImages();
        if (!images.length) {
            toast(t('No images'), 'warning');
            return;
        }
        const ok = await window.appConfirm({
            title: t('Delete'),
            message: t('Delete selected images?'),
            confirmText: t('Delete'),
            tone: 'danger',
        });
        if (!ok) return;
        try {
            await api(`/datasets/api/${name}/images/delete`, { method: 'POST', json: { images } });
            window.location.reload();
        } catch (err) {
            toast(err.message, 'danger');
        }
    });

    document.getElementById('btn-delete-dataset')?.addEventListener('click', async () => {
        const ok = await window.appConfirm({
            title: t('Delete'),
            message: t('Delete this dataset permanently?'),
            confirmText: t('Delete'),
            tone: 'danger',
        });
        if (!ok) return;
        try {
            await api(`/datasets/api/${name}`, { method: 'DELETE' });
            window.location.href = '/datasets';
        } catch (err) {
            toast(err.message, 'danger');
        }
    });

    async function loadClassesFromDetector(detector) {
        const input = document.getElementById('meta-classes');
        if (!input) return;

        const params = new URLSearchParams();
        if (detector) params.set('detector', detector);
        const qs = params.toString();
        const data = await api(`/datasets/api/detector-classes${qs ? `?${qs}` : ''}`);
        const next = (data.classes || []).join(', ');
        if (!next) {
            throw new Error(t('No classes found for this model'));
        }

        const current = input.value.trim();
        const isPlaceholder = !current || current === 'object';
        if (current && !isPlaceholder && current !== next) {
            const ok = typeof window.appConfirm === 'function'
                ? await window.appConfirm({
                    title: t('Classes'),
                    message: t('Replace classes with model classes?'),
                    confirmText: t('Apply'),
                    tone: 'warning',
                })
                : window.confirm(t('Replace classes with model classes?'));
            if (!ok) return;
        }

        input.value = next;
        toast(t('Classes loaded from model'), 'success');
    }

    document.getElementById('meta-autolabel-detector')?.addEventListener('change', async (e) => {
        try {
            await loadClassesFromDetector(e.target.value || '');
        } catch (err) {
            toast(err.message || t('Request failed'), 'danger');
        }
    });

    document.getElementById('btn-save-meta')?.addEventListener('click', withBusy(
        document.getElementById('btn-save-meta'),
        async () => {
            let attributes = [];
            let keypoints = [];
            try {
                attributes = JSON.parse(document.getElementById('meta-attributes').value || '[]');
            } catch (_) {
                throw new Error('Invalid attributes JSON');
            }
            try {
                keypoints = JSON.parse(document.getElementById('meta-keypoints').value || '[]');
            } catch (_) {
                throw new Error('Invalid keypoints JSON');
            }
            const classes = document.getElementById('meta-classes').value
                .split(',')
                .map((s) => s.trim())
                .filter(Boolean);
            await api(`/datasets/api/${name}/meta`, {
                method: 'POST',
                json: {
                    display_name: document.getElementById('meta-display-name').value,
                    classes,
                    task: document.getElementById('meta-task').value,
                    attributes,
                    keypoints_schema: keypoints,
                    autolabel_detector: document.getElementById('meta-autolabel-detector')?.value || '',
                },
            });
            toast(t('Settings saved'), 'success');
        },
    ));

    document.getElementById('btn-merge')?.addEventListener('click', withBusy(
        document.getElementById('btn-merge'),
        async () => {
            const data = await api(`/datasets/api/${name}/merge`, {
                method: 'POST',
                json: { source: document.getElementById('merge-source').value },
            });
            toast(`${t('Imported')}: ${data.imported}`, 'success');
            setTimeout(() => window.location.reload(), 500);
        },
    ));

    document.getElementById('btn-reassign')?.addEventListener('click', withBusy(
        document.getElementById('btn-reassign'),
        async () => {
            const data = await api(`/datasets/api/${name}/reassign-class`, {
                method: 'POST',
                json: {
                    from: document.getElementById('reassign-from').value,
                    to: document.getElementById('reassign-to').value,
                },
            });
            toast(`${t('Changed')}: ${data.changed}`, 'success');
        },
    ));

    document.getElementById('btn-autolabel')?.addEventListener('click', withBusy(
        document.getElementById('btn-autolabel'),
        async () => {
            const selected = selectedImages();
            const payload = selected.length > 0
                ? { images: selected }
                : { limit: 100, only_unlabeled: true };
            toast(t('Auto-label running…'), 'info');
            const data = await api(`/datasets/api/${name}/autolabel`, {
                method: 'POST',
                json: payload,
            });
            toast(`${t('Labeled')}: ${data.labeled}/${data.processed}`, 'success');
            setTimeout(() => window.location.reload(), 700);
        },
    ));

    document.getElementById('btn-run-qa')?.addEventListener('click', withBusy(
        document.getElementById('btn-run-qa'),
        async () => {
            const data = await api(`/datasets/api/${name}/qa`);
            const rep = data.report || {};
            document.getElementById('qa-output').textContent = JSON.stringify(rep, null, 2);

            const summary = document.getElementById('qa-cards-summary');
            const statImages = document.getElementById('qa-stat-images');
            const statLabels = document.getElementById('qa-stat-labels');
            const statUnlabeled = document.getElementById('qa-stat-unlabeled');
            if (summary) summary.classList.remove('d-none');
            if (statImages) statImages.textContent = rep.total_images ?? '0';
            if (statLabels) statLabels.textContent = rep.labeled_images ?? '0';
            if (statUnlabeled) statUnlabeled.textContent = rep.unlabeled_images ?? '0';
        },
    ));

    document.getElementById('btn-active-learning')?.addEventListener('click', withBusy(
        document.getElementById('btn-active-learning'),
        async () => {
            toast(t('Ranking…'), 'info');
            const data = await api(`/datasets/api/${name}/active-learning`, { method: 'POST', json: {} });
            document.getElementById('qa-output').textContent = JSON.stringify(data.uncertainty, null, 2);
        },
    ));

    document.getElementById('btn-quick-split')?.addEventListener('click', () => {
        document.querySelector('[data-bs-target="#tab-import"]')?.click();
        const splitBtn = document.getElementById('btn-auto-split');
        if (splitBtn) {
            splitBtn.scrollIntoView({ behavior: 'smooth', block: 'center' });
            splitBtn.classList.add('btn-warning');
            setTimeout(() => splitBtn.classList.remove('btn-warning'), 1500);
        }
    });

    const fillBestWeightsBtn = document.getElementById('btn-fill-best-weights');
    fillBestWeightsBtn?.addEventListener('click', () => {
        const w = detail.dataset.bestWeights;
        if (w) {
            const applyInput = document.getElementById('apply-weights');
            if (applyInput) applyInput.value = w;
            toast(t('Weights applied'), 'info');
        }
    });

    function setKnownBestWeights(weights) {
        if (!weights) return;
        detail.dataset.bestWeights = weights;
        if (fillBestWeightsBtn) fillBestWeightsBtn.classList.remove('d-none');
    }

    // ---- training ----
    const logEl = document.getElementById('training-log');
    const statusBadge = document.getElementById('train-status-badge');
    const progressBar = document.getElementById('train-progress-bar');
    const epochBadge = document.getElementById('train-epoch-badge');

    function updateTrainProgress(epoch, epochs) {
        if (!epoch || !epochs) return;
        if (epochBadge) {
            epochBadge.textContent = `${t('Epoch')} ${epoch}/${epochs}`;
            epochBadge.classList.remove('d-none');
        }
        if (progressBar) {
            const pct = Math.min(100, Math.max(0, Math.round((Number(epoch) / Number(epochs)) * 100)));
            progressBar.style.width = `${pct}%`;
        }
    }

    function appendLog(line) {
        if (!logEl) return;
        const atBottom = logEl.scrollHeight - logEl.scrollTop <= logEl.clientHeight + 40;
        logEl.textContent += `${line}\n`;
        if (atBottom) logEl.scrollTop = logEl.scrollHeight;
    }

    function setTrainStatus(text, tone) {
        if (!statusBadge) return;
        statusBadge.textContent = text;
        statusBadge.className = 'badge';
        const map = {
            success: 'text-bg-success',
            warning: 'text-bg-warning',
            danger: 'text-bg-danger',
            info: 'text-bg-info',
            running: 'text-bg-primary',
        };
        statusBadge.classList.add(map[tone] || 'text-bg-secondary');
    }

    async function refreshTrainStatus() {
        try {
            const data = await api('/datasets/api/training/status');
            if (data.log && logEl) {
                const nextLog = `${data.log.join('\n')}${data.log.length ? '\n' : ''}`;
                if (logEl.textContent !== nextLog) {
                    const atBottom = logEl.scrollHeight - logEl.scrollTop <= logEl.clientHeight + 40;
                    logEl.textContent = nextLog;
                    if (atBottom) logEl.scrollTop = logEl.scrollHeight;
                }
            }
            if (data.job) {
                const tone = data.job.status === 'completed' ? 'success'
                    : data.job.status === 'failed' ? 'danger'
                        : data.job.status === 'running' ? 'running' : undefined;
                setTrainStatus(t(data.job.status), tone);
                if (data.job.epoch && data.job.epochs) {
                    updateTrainProgress(data.job.epoch, data.job.epochs);
                }
                if (data.job.status === 'completed' && progressBar) {
                    progressBar.style.width = '100%';
                    progressBar.classList.remove('progress-bar-animated');
                    progressBar.classList.add('bg-success');
                }
                if (data.job.weights) {
                    setKnownBestWeights(data.job.weights);
                    const applyInput = document.getElementById('apply-weights');
                    if (applyInput && !applyInput.value) applyInput.value = data.job.weights;
                }
            } else {
                setTrainStatus(t(data.busy ? 'busy' : 'idle'));
            }
        } catch (_) {
            /* ignore polling errors */
        }
    }

    document.getElementById('btn-start-train')?.addEventListener('click', withBusy(
        document.getElementById('btn-start-train'),
        async () => {
            const data = await api(`/datasets/api/${name}/train`, {
                method: 'POST',
                json: {
                    base_model: document.getElementById('train-base-model').value,
                    epochs: Number(document.getElementById('train-epochs').value),
                    imgsz: Number(document.getElementById('train-imgsz').value),
                    batch: Number(document.getElementById('train-batch').value),
                    device: document.getElementById('train-device').value,
                    export_format: document.getElementById('train-export').value,
                    dedupe_val: document.getElementById('train-dedupe').checked,
                    task: detail.dataset.task,
                },
            });
            setTrainStatus('running', 'running');
            appendLog(`Job ${data.job.id} started`);
            toast(t('Training started'), 'success');
        },
    ));

    document.getElementById('btn-cancel-train')?.addEventListener('click', async () => {
        try {
            await api('/datasets/api/training/cancel', { method: 'POST', json: {} });
            toast(t('Cancel requested'), 'warning');
            setTrainStatus('cancel_requested', 'warning');
        } catch (err) {
            toast(err.message, 'danger');
        }
    });

    document.getElementById('btn-apply-weights')?.addEventListener('click', withBusy(
        document.getElementById('btn-apply-weights'),
        async () => {
            let classes = [];
            try {
                classes = JSON.parse(detail.dataset.classes || '[]');
            } catch (_) {
                classes = [];
            }
            await api('/datasets/api/training/apply-weights', {
                method: 'POST',
                json: {
                    location: document.getElementById('apply-location').value,
                    weights: document.getElementById('apply-weights').value,
                    classes,
                },
            });
            toast(t('Weights applied. Restart the counter.'), 'success');
        },
    ));

    if (window.io && window.SOCKETIO_OPTIONS) {
        const socket = window.io(window.SOCKETIO_OPTIONS);
        socket.on('training_progress', (payload) => {
            if (typeof payload === 'string') {
                appendLog(payload);
            } else if (payload.message) {
                appendLog(payload.message);
            } else {
                appendLog(JSON.stringify(payload));
            }
            if (payload.event === 'job_complete') {
                if (payload.job?.weights) {
                    const applyInput = document.getElementById('apply-weights');
                    if (applyInput) applyInput.value = payload.job.weights;
                }
                if (progressBar) {
                    progressBar.style.width = '100%';
                    progressBar.classList.remove('progress-bar-animated');
                    progressBar.classList.add('bg-success');
                }
                setTrainStatus('completed', 'success');
            }
            if (payload.event === 'job_failed') {
                setTrainStatus('failed', 'danger');
            }
            if (payload.event === 'epoch_end') {
                updateTrainProgress(payload.epoch, payload.epochs);
                setTrainStatus(`epoch ${payload.epoch}/${payload.epochs}`, 'running');
            }
        });
    }

    refreshTrainStatus();
    setInterval(refreshTrainStatus, 5000);

    if (window.location.hash === '#train') {
        document.getElementById('train-tab-btn')?.click();
    }

    // ---- view mode (table vs grid) ----
    const btnViewTable = document.getElementById('btn-view-table');
    const btnViewGrid = document.getElementById('btn-view-grid');
    const tableView = document.getElementById('images-table-view');
    const gridView = document.getElementById('images-grid-view');

    function setViewMode(mode) {
        const isGrid = mode === 'grid';
        btnViewTable?.classList.toggle('active', !isGrid);
        btnViewGrid?.classList.toggle('active', isGrid);
        tableView?.classList.toggle('d-none', isGrid);
        gridView?.classList.toggle('d-none', !isGrid);
        try {
            localStorage.setItem('cv_dataset_view', isGrid ? 'grid' : 'table');
        } catch (_) {}
    }

    btnViewTable?.addEventListener('click', () => setViewMode('table'));
    btnViewGrid?.addEventListener('click', () => setViewMode('grid'));

    const savedView = (() => {
        try { return localStorage.getItem('cv_dataset_view'); } catch (_) { return null; }
    })();
    if (savedView === 'grid') {
        setViewMode('grid');
    }

    // ---- filters & pagination ----
    let currentPage = 1;
    const pageSize = 48;

    function applyImageFilters() {
        const split = document.getElementById('filter-split')?.value || '';
        const labeled = document.getElementById('filter-labeled')?.value || '';
        const classFilter = document.getElementById('filter-class')?.value || '';
        const searchVal = (document.getElementById('images-search-input')?.value || '').trim().toLowerCase();

        const tableRows = Array.from(document.querySelectorAll('#images-tbody tr[data-name]'));
        const gridCols = Array.from(document.querySelectorAll('#images-grid-cards .grid-card-col[data-name]'));

        const visibleNames = [];

        tableRows.forEach((tr) => {
            const name = tr.dataset.name;
            const sp = tr.dataset.split || '';
            const isLab = tr.dataset.labeled === '1';
            const rawLabels = tr.dataset.labels || '';
            const labels = rawLabels ? rawLabels.split(',') : [];

            let show = true;
            if (split && sp !== split) show = false;
            if (labeled === '1' && !isLab) show = false;
            if (labeled === '0' && isLab) show = false;
            if (classFilter && !labels.includes(classFilter)) show = false;
            if (searchVal && !name.toLowerCase().includes(searchVal)) show = false;

            if (show) visibleNames.push(name);
        });

        const totalMatching = visibleNames.length;
        const totalPages = Math.max(1, Math.ceil(totalMatching / pageSize));
        if (currentPage > totalPages) currentPage = totalPages;
        if (currentPage < 1) currentPage = 1;

        const startIndex = (currentPage - 1) * pageSize;
        const endIndex = startIndex + pageSize;
        const pageNames = new Set(visibleNames.slice(startIndex, endIndex));

        tableRows.forEach((tr) => {
            tr.style.display = pageNames.has(tr.dataset.name) ? '' : 'none';
        });

        gridCols.forEach((col) => {
            col.style.display = pageNames.has(col.dataset.name) ? '' : 'none';
        });

        const paginationInfo = document.getElementById('pagination-info');
        const pageNum = document.getElementById('page-current-num');
        const prevBtn = document.getElementById('btn-page-prev');
        const nextBtn = document.getElementById('btn-page-next');

        if (paginationInfo) {
            if (totalMatching === 0) {
                paginationInfo.textContent = `0 ${t('images')}`;
            } else {
                const end = Math.min(endIndex, totalMatching);
                paginationInfo.textContent = `${startIndex + 1}–${end} / ${totalMatching} ${t('images')}`;
            }
        }
        if (pageNum) {
            pageNum.textContent = `${currentPage} / ${totalPages}`;
        }
        if (prevBtn) prevBtn.disabled = currentPage <= 1;
        if (nextBtn) nextBtn.disabled = currentPage >= totalPages;
    }

    document.getElementById('filter-split')?.addEventListener('change', () => {
        currentPage = 1;
        applyImageFilters();
    });
    document.getElementById('filter-labeled')?.addEventListener('change', () => {
        currentPage = 1;
        applyImageFilters();
    });
    document.getElementById('filter-class')?.addEventListener('change', () => {
        currentPage = 1;
        applyImageFilters();
    });
    document.getElementById('images-search-input')?.addEventListener('input', () => {
        currentPage = 1;
        applyImageFilters();
    });

    document.getElementById('btn-page-prev')?.addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage -= 1;
            applyImageFilters();
        }
    });
    document.getElementById('btn-page-next')?.addEventListener('click', () => {
        currentPage += 1;
        applyImageFilters();
    });

    applyImageFilters();
})();
