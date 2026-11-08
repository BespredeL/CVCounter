/**
 * Computer Vision Counter (CVCounter)
 * Setup wizard
 *
 * Developed by: Aleksandr Kireev
 * Website: https://bespredel.name
 */

(function () {
    'use strict';

    const root = document.getElementById('setup-wizard-root');
    if (!root) return;

    const TOTAL_STEPS = 7;
    const STEP_NAMES = ['System check', 'Goal', 'Video', 'Model', 'Components', 'Readiness', 'Finish'];
    const RESTART_STEP_KEY = 'cv_setup_wizard_step';
    let step = 1;
    let scenario = root.querySelector('.setup-scenario.is-selected')?.dataset?.scenario || null;
    let pendingBundles = [];
    let installing = false;
    let restartPending = false;
    let installPolling = null;
    const isAdmin = root.dataset.isAdmin === 'true';

    const progress = document.getElementById('setup-wizard-progress');
    const stepLabel = document.getElementById('setup-wizard-step-label');
    const btnPrev = document.getElementById('setup-wizard-prev');
    const btnNext = document.getElementById('setup-wizard-next');
    const btnSkip = document.getElementById('setup-wizard-skip');
    const btnComplete = document.getElementById('setup-wizard-complete');
    const btnCompleteBottom = document.getElementById('setup-wizard-complete-bottom');
    const bundlesBox = document.getElementById('setup-wizard-bundles');
    const preflightBox = document.getElementById('setup-wizard-preflight');
    const choiceNone = document.getElementById('setup-model-choice-none');
    const choiceSelect = document.getElementById('setup-model-choice-select');
    const choiceCustom = document.getElementById('setup-model-choice-custom');
    const modelSelect = document.getElementById('setup-model-select');
    const weightsInput = document.getElementById('setup-weights-path');
    let lastCriticalCount = 0;
    const panel = document.getElementById('setup-install-panel');
    const btnInstall = document.getElementById('setup-install-start');
    const btnCancel = document.getElementById('setup-install-cancel');
    const btnRestart = document.getElementById('setup-install-restart');
    const installBar = document.getElementById('setup-install-bar');
    const installStatus = document.getElementById('setup-install-status');
    const installLog = document.getElementById('setup-install-log');
    const installCount = document.getElementById('setup-install-count');
    const allowRestart = !(panel && panel.dataset.allowRestart === '0');

    function t(key, params) {
        if (typeof window.trans === 'function') return window.trans(key, params);
        return String(key);
    }

    function statusClass(status) {
        if (status === 'ok') return 'setup-check--ok';
        if (status === 'warning') return 'setup-check--warning';
        if (status === 'error') return 'setup-check--error';
        return 'setup-check--info';
    }

    function escapeHtml(value) {
        return String(value || '').replace(/[&<>"']/g, (ch) => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
        }[ch]));
    }

    function loadingHtml() {
        return `<div class="text-body-secondary small">${t('Loading')}…</div>`;
    }

    function checkCard(status, title, details) {
        return `
            <div class="setup-check ${statusClass(status)}">
                <span class="setup-check__mark" aria-hidden="true"></span>
                <div class="min-w-0">
                    <div class="setup-check__title">${escapeHtml(title)}</div>
                    ${details ? `<div class="setup-check__details">${escapeHtml(details)}</div>` : ''}
                </div>
            </div>
        `;
    }

    function renderChecks(container, checks) {
        if (!container) return;
        if (!checks || !checks.length) {
            container.innerHTML = checkCard('info', t('All checks passed'));
            return;
        }
        container.innerHTML = checks.map((c) => checkCard(c.status, t(c.title || c.status), t(c.details || ''))).join('');
    }

    function showStep(n) {
        step = Math.max(1, Math.min(TOTAL_STEPS, n));
        root.querySelectorAll('.setup-wizard-step').forEach((el) => {
            el.classList.toggle('d-none', Number(el.dataset.step) !== step);
        });
        root.querySelectorAll('.setup-stepper__item').forEach((el) => {
            const idx = Number(el.dataset.goto);
            el.classList.toggle('is-active', idx === step);
            el.classList.toggle('is-done', idx < step);
            el.setAttribute('aria-selected', idx === step ? 'true' : 'false');
        });
        progress.style.width = `${(step / TOTAL_STEPS) * 100}%`;
        stepLabel.textContent = `${t('Step')} ${step} / ${TOTAL_STEPS} — ${t(STEP_NAMES[step - 1])}`;
        btnNext.classList.toggle('d-none', step >= TOTAL_STEPS);
        if (btnCompleteBottom) btnCompleteBottom.classList.toggle('d-none', step < TOTAL_STEPS);
        btnPrev.disabled = installing || step <= 1;
        showInstallPanel();
        if (step === 1) refreshReadiness();
        if (step === 4) updateModelHint();
        if (step === 5 || step === 6) refreshComponents();
        if (step === 7) updateStep7Summary();
    }

    async function postJson(url, body) {
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body || {}),
        });
        return res.json();
    }

    function wizardFields() {
        return {
            video_path: document.getElementById('setup-video-path')?.value?.trim() || '',
            weights_path: document.getElementById('setup-weights-path')?.value?.trim() || '',
            label: document.getElementById('setup-camera-name')?.value?.trim() || '',
        };
    }

    async function saveWizardFields() {
        try {
            await postJson('/settings/api/onboarding/fields', wizardFields());
        } catch (error) {
            // A lost draft only costs a re-typed path; the wizard keeps working without it.
        }
    }

    async function onboardingAction(action) {
        const body = { action };
        if (action === 'complete') {
            Object.assign(body, wizardFields());
            if (btnComplete) {
                btnComplete.disabled = true;
                btnComplete.textContent = `${t('Loading')}…`;
            }
            if (btnCompleteBottom) {
                btnCompleteBottom.disabled = true;
                btnCompleteBottom.textContent = `${t('Loading')}…`;
            }
        }
        try {
            const data = await postJson('/settings/api/onboarding/complete', body);
            if (!data.ok) {
                window.alert(data.error || t('Request failed'));
                if (btnComplete) {
                    btnComplete.disabled = false;
                    btnComplete.textContent = t('Complete setup and go to Dashboard');
                }
                if (btnCompleteBottom) {
                    btnCompleteBottom.disabled = false;
                    btnCompleteBottom.textContent = t('Complete setup');
                }
                return;
            }
            if (action === 'skip' || action === 'complete') {
                window.location.href = '/';
            }
        } catch (err) {
            window.alert(err.message || t('Request failed'));
            if (btnComplete) {
                btnComplete.disabled = false;
                btnComplete.textContent = t('Complete setup and go to Dashboard');
            }
            if (btnCompleteBottom) {
                btnCompleteBottom.disabled = false;
                btnCompleteBottom.textContent = t('Complete setup');
            }
        }
    }

    async function refreshReadiness() {
        const box = document.getElementById('setup-wizard-readiness');
        if (!box) return;
        box.innerHTML = `<div class="text-body-secondary small">${t('Loading')}…</div>`;
        const q = scenario ? `?scenario=${encodeURIComponent(scenario)}` : '';
        try {
            const res = await fetch(`/settings/api/onboarding/readiness${q}`);
            const data = await res.json();
            if (!data.ok) {
                box.textContent = data.error || 'Error';
                return;
            }
            renderChecks(box, data.system_checks || []);
        } catch (e) {
            box.textContent = t('Request failed');
        }
    }

    function draftPayload() {
        const fields = wizardFields();
        let intent = 'collection';
        if (scenario === 'train') {
            intent = 'train';
        } else if (scenario === 'count_objects') {
            intent = fields.weights_path ? 'inference' : 'collection';
        } else if (scenario === 'explore') {
            intent = fields.weights_path ? 'inference' : 'explore';
        } else {
            intent = 'collection';
        }
        return {
            video_path: fields.video_path,
            weights_path: fields.weights_path,
            scenario: scenario,
            inference_intent: intent,
        };
    }

    function bundleCard(item) {
        const lines = [`<div class="setup-check__details">${escapeHtml(t('Not installed'))}</div>`];
        if (item.description) {
            lines.push(`<div class="setup-check__details">${escapeHtml(t(item.description))}</div>`);
        }
        if ((item.steps || []).length > 1) {
            const steps = item.steps.map(escapeHtml).join(' → ');
            lines.push(`<div class="setup-check__details">${escapeHtml(t('Installation steps'))}: ${steps}</div>`);
        }
        (item.warnings || []).forEach((warning) => {
            lines.push(`<div class="setup-check__details text-warning">${escapeHtml(t(warning))}</div>`);
        });
        return `
            <div class="setup-check setup-check--warning">
                <span class="setup-check__mark" aria-hidden="true"></span>
                <div class="min-w-0">
                    <div class="setup-check__title d-flex flex-wrap align-items-center gap-2">
                        <span>${escapeHtml(item.name || item.key)}</span>
                        ${item.license ? `<span class="badge bg-body-tertiary border text-body-secondary font-monospace">${escapeHtml(item.license)}</span>` : ''}
                    </div>
                    ${lines.join('')}
                </div>
            </div>
        `;
    }

    function blockedCard(item) {
        const reason = (item.reasons || []).map((text) => t(text)).join('; ') || t('Not available');
        return checkCard('error', `${item.name || item.key} — ${t('Cannot be installed here')}`, reason);
    }

    function renderBundles(bundles) {
        pendingBundles = bundles.items || [];
        const blocked = bundles.blocked || [];
        if (bundlesBox) {
            bundlesBox.innerHTML = (pendingBundles.length || blocked.length)
                ? [...pendingBundles.map(bundleCard), ...blocked.map(blockedCard)].join('')
                : checkCard('ok', t('No extra components required'), t('All required components installed'));
        }
        showInstallPanel();
    }

    function showInstallPanel() {
        if (!panel) return;
        const onInstallStep = step === 5 || step === 6;
        const visible = isAdmin && (installing || restartPending || (pendingBundles.length > 0 && onInstallStep));
        panel.classList.toggle('d-none', !visible);
        btnInstall.disabled = installing || !pendingBundles.length;
        btnCancel.disabled = !installing;
        installCount.textContent = pendingBundles.length > 1
            ? t('{count} components to install', {count: pendingBundles.length})
            : '';
    }

    function setInstallStatus(text, failed) {
        if (!installStatus) return;
        installStatus.textContent = text || '';
        installStatus.classList.toggle('text-danger', !!failed);
    }

    function setInstallLog(lines) {
        if (!installLog) return;
        if (!lines || !lines.length) {
            installLog.classList.add('d-none');
            return;
        }
        installLog.classList.remove('d-none');
        installLog.textContent = lines.join('\n');
        installLog.scrollTop = installLog.scrollHeight;
    }

    function setInstallProgress(index, total) {
        if (installBar) installBar.style.width = total ? `${Math.min(100, Math.round((index / total) * 100))}%` : '0%';
    }

    function setInstalling(active) {
        installing = active;
        if (active) {
            restartPending = false;
            if (btnRestart) btnRestart.classList.add('d-none');
        }
        btnPrev.disabled = active || step <= 1;
        btnNext.disabled = active;
        btnSkip.disabled = active;
        if (btnComplete) btnComplete.disabled = active;
        root.querySelectorAll('.setup-stepper__item').forEach((el) => {
            el.disabled = active;
        });
        showInstallPanel();
    }

    function pollInstallJob() {
        return new Promise((resolve) => {
            if (installPolling) clearInterval(installPolling);
            installPolling = setInterval(async () => {
                try {
                    const res = await fetch('/settings/api/runtimes/install/status');
                    const data = await res.json();
                    const job = data.job || {};
                    setInstallProgress(Number(job.step_index) || 0, Number(job.step_total) || 0);
                    setInstallLog(job.logs || []);
                    if (job.status && job.status !== 'running' && job.status !== 'idle') {
                        clearInterval(installPolling);
                        installPolling = null;
                        resolve(job);
                    }
                } catch (error) {
                    clearInterval(installPolling);
                    installPolling = null;
                    resolve({status: 'error', error: error.message});
                }
            }, 1500);
        });
    }

    function finishJob(job) {
        if (job.status === 'success') {
            if (!job.restart_required) {
                setInstallStatus(t('Installation finished'));
                return;
            }
            restartPending = true;
            setInstallStatus(allowRestart
                ? t('The packages were installed into the running environment. Restart the server so the new modules are loaded.')
                : t('Server control via web interface is disabled in configuration. Restart the server manually.'));
            if (allowRestart && btnRestart) btnRestart.classList.remove('d-none');
            return;
        }
        if (job.status === 'cancelled') {
            setInstallStatus(t('Installation cancelled.'), true);
            return;
        }
        setInstallStatus(job.error || t('Installation failed'), true);
    }

    async function installMissing() {
        if (!isAdmin || installing || !pendingBundles.length) return;
        const queue = pendingBundles.slice();
        await saveWizardFields();
        setInstalling(true);
        setInstallProgress(0, 0);
        let restartRequired = false;
        let failed = false;
        for (let index = 0; index < queue.length; index += 1) {
            const item = queue[index];
            setInstallStatus(`${t('Installing {name}', {name: item.name || item.key})} (${index + 1}/${queue.length})`);
            let started;
            try {
                started = await postJson('/settings/api/runtimes/install', {bundle: item.key});
            } catch (error) {
                finishJob({status: 'error', error: error.message});
                failed = true;
                break;
            }
            if (!started.ok) {
                finishJob({status: 'error', error: started.error});
                failed = true;
                break;
            }
            const job = await pollInstallJob();
            restartRequired = restartRequired || !!job.restart_required;
            if (job.status !== 'success') {
                finishJob(job);
                failed = true;
                break;
            }
        }
        setInstalling(false);
        if (!failed && restartRequired) finishJob({status: 'success', restart_required: true});
        await refreshComponents();
    }

    async function resumeRunningJob() {
        if (installing) return;
        let job;
        try {
            const res = await fetch('/settings/api/runtimes/install/status');
            job = (await res.json()).job || {};
        } catch (error) {
            return;
        }
        if (job.status !== 'running') return;
        setInstalling(true);
        setInstallStatus(job.current_step || t('Installation in progress...'));
        setInstallLog(job.logs || []);
        setInstallProgress(Number(job.step_index) || 0, Number(job.step_total) || 0);
        const finished = await pollInstallJob();
        setInstalling(false);
        finishJob(finished);
        await refreshComponents();
    }

    async function refreshComponents() {
        if (installing) return;
        if (bundlesBox && step === 5) bundlesBox.innerHTML = loadingHtml();
        if (preflightBox && step === 6) preflightBox.innerHTML = loadingHtml();
        let readiness;
        try {
            const res = await postJson('/settings/api/onboarding/draft', draftPayload());
            if (!res.ok) throw new Error(res.error || t('Request failed'));
            readiness = res.readiness || {};
        } catch (error) {
            if (bundlesBox && step === 5) bundlesBox.textContent = error.message;
            if (preflightBox && step === 6) preflightBox.textContent = error.message;
            return;
        }
        lastCriticalCount = readiness.critical_count || 0;
        renderBundles(readiness.bundles || {});
        if (preflightBox) renderChecks(preflightBox, readiness.checks || []);

        const summaryBox = document.getElementById('setup-preflight-summary');
        if (summaryBox) {
            if (lastCriticalCount > 0) {
                summaryBox.innerHTML = `
                    <div class="alert alert-danger d-flex align-items-center gap-2 mb-3">
                        <span class="fs-5">⚠️</span>
                        <div>
                            <strong>${escapeHtml(t('Some items need attention'))}</strong>
                            <div class="small">${escapeHtml(t('Fix the critical errors below before starting the counter.'))}</div>
                        </div>
                    </div>
                `;
            } else {
                summaryBox.innerHTML = `
                    <div class="alert alert-success d-flex align-items-center gap-2 mb-3">
                        <span class="fs-5">✅</span>
                        <div>
                            <strong>${escapeHtml(t('Ready to start!'))}</strong>
                            <div class="small">${escapeHtml(t('All readiness checks passed. You can proceed to the final step.'))}</div>
                        </div>
                    </div>
                `;
            }
        }
        await resumeRunningJob();
    }

    function updateModelHint() {
        const hintEl = document.getElementById('setup-model-context-hint');
        if (!hintEl) return;
        if (scenario === 'train') {
            hintEl.textContent = t('Setup hint train model');
        } else if (scenario === 'test_camera' || scenario === 'collect_dataset') {
            hintEl.textContent = t('Setup hint camera model');
        } else if (scenario === 'count_objects') {
            hintEl.textContent = t('Setup hint count model');
        } else {
            hintEl.textContent = t('Setup model skip hint');
        }
    }

    function updateStep7Summary() {
        const fields = wizardFields();
        const scenarioEl = document.getElementById('summary-scenario');
        const cameraEl = document.getElementById('summary-camera-name');
        const videoEl = document.getElementById('summary-video-path');
        const modelEl = document.getElementById('summary-model');
        const readinessEl = document.getElementById('summary-readiness');

        const scenarioNames = {
            count_objects: 'Count objects with a model',
            test_camera: 'Test camera / video',
            collect_dataset: 'Collect dataset images',
            train: 'Train a model',
            explore: 'Explore the app',
        };

        if (scenarioEl) {
            scenarioEl.textContent = scenario ? t(scenarioNames[scenario] || scenario) : t('Not specified');
        }
        if (cameraEl) {
            cameraEl.textContent = fields.label || t('Not specified');
        }
        if (videoEl) {
            videoEl.textContent = fields.video_path || t('Not configured (can be configured later)');
        }
        if (modelEl) {
            modelEl.textContent = fields.weights_path || t('Without model (data collection mode)');
        }
        if (readinessEl) {
            if (lastCriticalCount === 0) {
                readinessEl.innerHTML = `<span class="badge bg-success-subtle text-success border border-success-subtle px-2 py-1">${escapeHtml(t('Ready to start!'))}</span>`;
            } else {
                readinessEl.innerHTML = `<span class="badge bg-warning-subtle text-warning border border-warning-subtle px-2 py-1">${escapeHtml(t('Some items need attention'))}</span>`;
            }
        }
    }

    function initModelControls() {
        if (!weightsInput) return;
        const currentPath = weightsInput.value.trim();
        let matchedSelect = false;
        if (modelSelect && currentPath) {
            for (let i = 0; i < modelSelect.options.length; i += 1) {
                if (modelSelect.options[i].value === currentPath) {
                    modelSelect.selectedIndex = i;
                    matchedSelect = true;
                    break;
                }
            }
        }
        if (matchedSelect && choiceSelect) {
            choiceSelect.checked = true;
        } else if (currentPath && choiceCustom) {
            choiceCustom.checked = true;
        } else if (choiceNone) {
            choiceNone.checked = true;
        }

        choiceNone?.addEventListener('change', () => {
            if (choiceNone.checked) {
                weightsInput.value = '';
                if (modelSelect) modelSelect.value = '';
            }
        });

        choiceSelect?.addEventListener('change', () => {
            if (choiceSelect.checked && modelSelect) {
                if (!modelSelect.value && modelSelect.options.length > 1) {
                    modelSelect.selectedIndex = 1;
                }
                weightsInput.value = modelSelect.value;
            }
        });

        choiceCustom?.addEventListener('change', () => {
            if (choiceCustom.checked) {
                weightsInput.focus();
            }
        });

        modelSelect?.addEventListener('change', () => {
            weightsInput.value = modelSelect.value;
            if (choiceSelect) choiceSelect.checked = true;
        });

        weightsInput?.addEventListener('input', () => {
            if (weightsInput.value.trim()) {
                if (choiceCustom) choiceCustom.checked = true;
                if (modelSelect && modelSelect.value !== weightsInput.value.trim()) {
                    modelSelect.value = '';
                }
            } else if (choiceNone) {
                choiceNone.checked = true;
                if (modelSelect) modelSelect.value = '';
            }
        });
    }

    root.querySelectorAll('.setup-scenario').forEach((btn) => {
        btn.addEventListener('click', async () => {
            scenario = btn.dataset.scenario;
            root.querySelectorAll('.setup-scenario').forEach((b) => b.classList.remove('is-selected'));
            btn.classList.add('is-selected');
            updateModelHint();
            await postJson('/settings/api/onboarding/scenario', { scenario_id: scenario });
        });
    });

    document.getElementById('setup-source-chips')?.addEventListener('click', (event) => {
        const chip = event.target.closest('[data-fill]');
        if (!chip) return;
        const input = document.getElementById('setup-video-path');
        if (input) input.value = chip.dataset.fill;
        input?.focus();
    });

    root.querySelectorAll('.setup-stepper__item').forEach((btn) => {
        btn.addEventListener('click', () => showStep(Number(btn.dataset.goto)));
    });

    document.getElementById('setup-wizard-refresh-readiness')?.addEventListener('click', refreshReadiness);
    document.getElementById('setup-wizard-refresh-bundles')?.addEventListener('click', refreshComponents);
    btnPrev?.addEventListener('click', () => showStep(step - 1));
    btnNext?.addEventListener('click', async () => {
        await saveWizardFields();
        showStep(step + 1);
    });
    btnSkip?.addEventListener('click', () => onboardingAction('skip'));
    btnComplete?.addEventListener('click', () => onboardingAction('complete'));
    btnCompleteBottom?.addEventListener('click', () => onboardingAction('complete'));
    btnInstall?.addEventListener('click', installMissing);
    btnCancel?.addEventListener('click', async () => {
        btnCancel.disabled = true;
        setInstallStatus(t('Cancelling...'));
        try {
            await postJson('/settings/api/runtimes/install/cancel', {});
        } catch (error) {
            btnCancel.disabled = false;
            setInstallStatus(error.message || t('Request failed'), true);
        }
    });
    btnRestart?.addEventListener('click', async () => {
        btnRestart.disabled = true;
        await saveWizardFields();
        try {
            const res = await fetch('/settings/api/restart', {method: 'POST'});
            const data = await res.json();
            if (!data.ok) {
                btnRestart.disabled = false;
                setInstallStatus(data.error || t('Request failed'), true);
                return;
            }
            window.localStorage.setItem(RESTART_STEP_KEY, String(step));
            setInstallStatus(t('Restarting server...'));
            setTimeout(() => window.location.reload(), 6000);
        } catch (error) {
            btnRestart.disabled = false;
            setInstallStatus(error.message || t('Request failed'), true);
        }
    });

    function restoredStep() {
        let saved = null;
        try {
            saved = window.localStorage.getItem(RESTART_STEP_KEY);
            if (saved !== null) window.localStorage.removeItem(RESTART_STEP_KEY);
        } catch (error) {
            return 1;
        }
        const value = Number(saved);
        return value > 1 && value <= TOTAL_STEPS ? value : 1;
    }

    initModelControls();
    showStep(restoredStep());
})();
