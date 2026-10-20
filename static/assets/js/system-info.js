/**
 * Computer Vision Counter (CVCounter)
 * System Info & ML Runtimes Manager (CUDA, ONNX, TensorRT, OpenVINO).
 *
 * Developed by: Aleksandr Kireev
 * Website: https://bespredel.name
 */

(function () {
    'use strict';

    const t = (key, params) => (typeof window.trans === 'function' ? window.trans(key, params) : key);

    const endpoints = Object.assign({
        runtimesStatus: '/settings/api/runtimes/status',
        runtimesInstall: '/settings/api/runtimes/install',
        runtimesInstallStatus: '/settings/api/runtimes/install/status',
        logs: '/settings/api/logs',
        logsClear: '/settings/api/logs/clear'
    }, window.SYSTEM_INFO_ENDPOINTS || {});

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function initSystemInfo() {
        const runtimesContainer = document.getElementById('runtimes-container');
        const refreshBtn = document.getElementById('btn-refresh-runtimes');
        const installModalEl = document.getElementById('runtimeInstallModal');
        if (!runtimesContainer || !installModalEl) return;

        const installModal = new bootstrap.Modal(installModalEl);
        const installLogTerminal = document.getElementById('installLogTerminal');
        const installStatusText = document.getElementById('installStatusText');
        const installSpinner = document.getElementById('installSpinner');
        const installBundleBadge = document.getElementById('installBundleBadge');
        const installModalTitle = document.getElementById('installModalTitle');
        const refreshAfterInstallBtn = document.getElementById('btn-refresh-after-install');
        const closeInstallBtn = document.getElementById('btn-close-install-modal');
        const cancelInstallBtn = document.getElementById('btn-cancel-install');

        let pollInterval = null;

        function loadRuntimes() {
            runtimesContainer.innerHTML = `
                <div class="col-12 text-center py-3 text-body-secondary">
                    <div class="spinner-border spinner-border-sm me-2" role="status"></div>
                    <span>${escapeHtml(t('Loading runtime status...'))}</span>
                </div>
            `;

            fetch(endpoints.runtimesStatus)
                .then(res => res.json())
                .then(data => {
                    if (!data.ok || !data.runtimes) {
                        runtimesContainer.innerHTML = `<div class="col-12 text-danger">${escapeHtml(t('Failed to load runtime information.'))}</div>`;
                        return;
                    }
                    renderRuntimes(data.runtimes);
                })
                .catch(err => {
                    runtimesContainer.innerHTML = `<div class="col-12 text-danger">${escapeHtml(t('Error loading runtime information'))}: ${escapeHtml(err.message)}</div>`;
                });
        }

        function formatProviders(providers) {
            if (!providers || !Array.isArray(providers) || providers.length === 0) {
                return '<span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle">CPU</span>';
            }
            return providers.map(p => {
                if (p === 'TensorrtExecutionProvider') return '<span class="badge bg-warning-subtle text-warning border border-warning-subtle me-1 mb-1">TensorRT</span>';
                if (p === 'CUDAExecutionProvider') return '<span class="badge bg-success-subtle text-success border border-success-subtle me-1 mb-1">CUDA</span>';
                if (p === 'DmlExecutionProvider') return '<span class="badge bg-info-subtle text-info border border-info-subtle me-1 mb-1">DirectML</span>';
                if (p === 'OpenVINOExecutionProvider') return '<span class="badge bg-info-subtle text-info border border-info-subtle me-1 mb-1">OpenVINO</span>';
                if (p === 'CPUExecutionProvider') return '<span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle me-1 mb-1">CPU</span>';
                return `<span class="badge bg-light text-dark border me-1 mb-1">${escapeHtml(p.replace('ExecutionProvider', ''))}</span>`;
            }).join('');
        }

        function renderRuntimes(r) {
            const gpu = r.gpu || {};
            const pkgs = r.packages || {};
            const onnx = r.onnx || {};
            const trt = r.tensorrt || {};

            let cardsHtml = '';

            // 1. GPU & PyTorch CUDA
            const cudaOk = gpu.cuda_available;
            const torchPkg = pkgs.torch || {};
            cardsHtml += `
                <div class="col-12 col-md-6 col-xl-3">
                    <div class="card h-100 border rounded-3 p-3 d-flex flex-column" style="background: var(--cv-surface-elevated, #1e2128); border-color: var(--cv-border, rgba(255,255,255,0.08)) !important;">
                        <div class="d-flex align-items-center justify-content-between mb-2">
                            <span class="fw-bold d-flex align-items-center gap-2 text-body">
                                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-nvidia text-success flex-shrink-0" viewBox="0 0 16 16"><path d="M1.635 7.146S3.08 5.012 5.97 4.791v-.774C2.77 4.273 0 6.983 0 6.983s1.57 4.536 5.97 4.952v-.824c-3.23-.406-4.335-3.965-4.335-3.965M5.97 9.475v.753c-2.44-.435-3.118-2.972-3.118-2.972S4.023 5.958 5.97 5.747v.828h-.004c-1.021-.123-1.82.83-1.82.83s.448 1.607 1.824 2.07M6 2l-.03 2.017A7 7 0 0 1 6.252 4c3.637-.123 6.007 2.983 6.007 2.983s-2.722 3.31-5.557 3.31q-.39-.002-.732-.065v.883q.292.039.61.04c2.638 0 4.546-1.348 6.394-2.943.307.246 1.561.842 1.819 1.104-1.757 1.47-5.852 2.657-8.173 2.657a7 7 0 0 1-.65-.034V14H16l.03-12zm-.03 3.747v-.956a6 6 0 0 1 .282-.015c2.616-.082 4.332 2.248 4.332 2.248S8.73 9.598 6.743 9.598c-.286 0-.542-.046-.773-.123v-2.9c1.018.123 1.223.572 1.835 1.593L9.167 7.02s-.994-1.304-2.67-1.304a5 5 0 0 0-.527.031"/></svg>
                                <span>NVIDIA CUDA</span>
                            </span>
                            ${cudaOk
                                ? `<span class="badge bg-success-subtle text-success border border-success-subtle px-2 py-1">${escapeHtml(t('Active'))}</span>`
                                : `<span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle px-2 py-1">${escapeHtml(t('CPU Mode'))}</span>`}
                        </div>
                        <div class="mb-3">
                            <p class="small mb-1 text-body-secondary">${escapeHtml(t('Device'))}: <strong class="text-body">${escapeHtml(gpu.device_name || t('Not detected'))}</strong></p>
                            <p class="small mb-1 text-body-secondary">${escapeHtml(t('CUDA Version'))}: <strong class="text-body">${escapeHtml(gpu.cuda_version || '-')}</strong></p>
                            <p class="small mb-0 text-body-secondary">PyTorch: <strong class="text-body">${escapeHtml(torchPkg.version || '-')}</strong></p>
                        </div>
                        <div class="pt-2 border-top mt-auto" style="border-color: var(--cv-border, rgba(255,255,255,0.08)) !important;">
                            <div class="btn btn-sm w-100 disabled d-inline-flex align-items-center justify-content-center gap-2 ${cudaOk ? 'btn-outline-success text-success border-success-subtle' : 'btn-outline-secondary text-body-secondary'}" style="pointer-events: none; opacity: 0.95;">
                                ${cudaOk
                                    ? `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" class="bi bi-check-circle-fill" viewBox="0 0 16 16"><path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0m-3.97-3.03a.75.75 0 0 0-1.08.022L7.477 9.417 5.384 7.323a.75.75 0 0 0-1.06 1.06L6.97 11.03a.75.75 0 0 0 1.079-.02l3.992-4.99a.75.75 0 0 0-.01-1.05z"/></svg>`
                                    : `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" class="bi bi-cpu flex-shrink-0" viewBox="0 0 16 16"><path d="M5 0a.5.5 0 0 1 .5.5V2h1V.5a.5.5 0 0 1 1 0V2h1V.5a.5.5 0 0 1 1 0V2h1V.5a.5.5 0 0 1 1 0V2A2.5 2.5 0 0 1 14 4.5h1.5a.5.5 0 0 1 0 1H14v1h1.5a.5.5 0 0 1 0 1H14v1h1.5a.5.5 0 0 1 0 1H14v1h1.5a.5.5 0 0 1 0 1H14a2.5 2.5 0 0 1-2.5 2.5v1.5a.5.5 0 0 1-1 0V14h-1v1.5a.5.5 0 0 1-1 0V14h-1v1.5a.5.5 0 0 1-1 0V14h-1v1.5a.5.5 0 0 1-1 0V14A2.5 2.5 0 0 1 2 11.5H.5a.5.5 0 0 1 0-1H2v-1H.5a.5.5 0 0 1 0-1H2v-1H.5a.5.5 0 0 1 0-1H2v-1H.5a.5.5 0 0 1 0-1H2A2.5 2.5 0 0 1 4.5 2V.5A.5.5 0 0 1 5 0m-.5 3A1.5 1.5 0 0 0 3 4.5v7A1.5 1.5 0 0 0 4.5 13h7a1.5 1.5 0 0 0 1.5-1.5v-7A1.5 1.5 0 0 0 11.5 3zM5 6.5A1.5 1.5 0 0 1 6.5 5h3A1.5 1.5 0 0 1 11 6.5v3A1.5 1.5 0 0 1 9.5 11h-3A1.5 1.5 0 0 1 5 9.5zM6.5 6a.5.5 0 0 0-.5.5v3a.5.5 0 0 0 .5.5h3a.5.5 0 0 0 .5-.5v-3a.5.5 0 0 0-.5-.5z"/></svg>`}
                                <span>${escapeHtml(cudaOk ? t('CUDA is ready for GPU acceleration') : t('CPU Mode'))}</span>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            // 2. ONNX & ONNX Runtime
            const onnxSlimPkg = pkgs.onnxslim || {};
            const ortPkg = pkgs.onnxruntime || {};
            const onnxExportReady = onnx.export_ready;
            cardsHtml += `
                <div class="col-12 col-md-6 col-xl-3">
                    <div class="card h-100 border rounded-3 p-3 d-flex flex-column" style="background: var(--cv-surface-elevated, #1e2128); border-color: var(--cv-border, rgba(255,255,255,0.08)) !important;">
                        <div class="d-flex align-items-center justify-content-between mb-2">
                            <span class="fw-bold d-flex align-items-center gap-2 text-body">
                                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-box text-primary flex-shrink-0" viewBox="0 0 16 16"><path d="M8.186 1.113a.5.5 0 0 0-.372 0L1.846 3.5 8 5.961 14.154 3.5zM15 4.239l-6.5 2.6v7.922l6.5-2.6V4.24zM7.5 14.762V6.838L1 4.239v7.923zM7.443.184a1.5 1.5 0 0 1 1.114 0l7.129 2.852A.5.5 0 0 1 16 3.5v8.662a1 1 0 0 1-.629.928l-7.185 2.874a.5.5 0 0 1-.372 0L.63 13.09a1 1 0 0 1-.63-.928V3.5a.5.5 0 0 1 .314-.464z"/></svg>
                                <span>ONNX Runtime</span>
                            </span>
                            ${ortPkg.installed
                                ? `<span class="badge bg-success-subtle text-success border border-success-subtle px-2 py-1">v${escapeHtml(ortPkg.version || 'OK')}</span>`
                                : `<span class="badge bg-warning-subtle text-warning border border-warning-subtle px-2 py-1">${escapeHtml(t('Not installed'))}</span>`}
                        </div>
                        <div class="mb-3">
                            <div class="small mb-1 text-body-secondary d-flex align-items-center gap-1">
                                <span>${escapeHtml(t('Export Tools'))}:</span>
                                <span class="badge ${onnxExportReady ? 'bg-success-subtle text-success border border-success-subtle' : 'bg-danger-subtle text-danger border border-danger-subtle'}">
                                    ${escapeHtml(onnxExportReady ? t('Ready') : t('Missing onnx'))}
                                </span>
                                ${onnxSlimPkg.installed ? '<span class="badge bg-body-tertiary border text-body-secondary font-monospace" style="font-size: 0.7rem;">slim</span>' : ''}
                            </div>
                            <div class="small mb-0 text-body-secondary">
                                <div class="mb-1">${escapeHtml(t('Execution Providers'))}:</div>
                                <div class="d-flex flex-wrap align-items-center pt-0.5">
                                    ${formatProviders(ortPkg.providers)}
                                </div>
                            </div>
                        </div>
                        <div class="pt-2 border-top mt-auto" style="border-color: var(--cv-border, rgba(255,255,255,0.08)) !important;">
                            <button type="button" class="btn btn-outline-primary btn-sm w-100 btn-install-bundle d-inline-flex align-items-center justify-content-center gap-2" data-bundle="onnx_export">
                                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 16 16" class="bi bi-download"><path d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5"/><path d="M7.646 11.854a.5.5 0 0 0 .708 0l3-3a.5.5 0 0 0-.708-.708L8.5 10.293V1.5a.5.5 0 0 0-1 0v8.793L5.354 8.146a.5.5 0 1 0-.708.708z"/></svg>
                                <span>${escapeHtml(onnxExportReady ? t('Update ONNX Tools') : t('Install ONNX Tools'))}</span>
                            </button>
                        </div>
                    </div>
                </div>
            `;

            // 3. TensorRT (.engine)
            const trtPkg = pkgs.tensorrt || {};
            const trtSupported = trt.supported_on_hardware;
            const trtReady = trt.export_ready;
            cardsHtml += `
                <div class="col-12 col-md-6 col-xl-3">
                    <div class="card h-100 border rounded-3 p-3 d-flex flex-column" style="background: var(--cv-surface-elevated, #1e2128); border-color: var(--cv-border, rgba(255,255,255,0.08)) !important;">
                        <div class="d-flex align-items-center justify-content-between mb-2">
                            <span class="fw-bold d-flex align-items-center gap-2 text-body">
                                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-lightning-charge-fill text-warning flex-shrink-0" viewBox="0 0 16 16"><path d="M11.251.068a.5.5 0 0 1 .227.58L9.677 6.5H13a.5.5 0 0 1 .364.843l-8 8.5a.5.5 0 0 1-.842-.49L6.323 9.5H3a.5.5 0 0 1-.364-.843l8-8.5a.5.5 0 0 1 .615-.09z"/></svg>
                                <span>TensorRT</span>
                            </span>
                            ${trtPkg.installed
                                ? `<span class="badge bg-success-subtle text-success border border-success-subtle px-2 py-1">v${escapeHtml(trtPkg.version || 'OK')}</span>`
                                : (trtSupported
                                    ? `<span class="badge bg-warning-subtle text-warning border border-warning-subtle px-2 py-1">${escapeHtml(t('Not installed'))}</span>`
                                    : `<span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle px-2 py-1">${escapeHtml(t('GPU Required'))}</span>`)}
                        </div>
                        <div class="mb-3">
                            <p class="small mb-1 text-body-secondary">${escapeHtml(t('Format'))}: <strong class="text-body font-monospace">.engine / .trt</strong></p>
                            <p class="small mb-0 text-body-secondary">
                                ${escapeHtml(t('Status'))}: 
                                <strong class="${trtReady ? 'text-success' : (trtSupported ? 'text-warning' : 'text-secondary')}">
                                    ${escapeHtml(trtReady ? t('Ready for Engine Export') : (trtSupported ? t('Requires tensorrt package') : t('NVIDIA GPU required')))}
                                </strong>
                            </p>
                        </div>
                        <div class="pt-2 border-top mt-auto" style="border-color: var(--cv-border, rgba(255,255,255,0.08)) !important;">
                            <button type="button" class="btn btn-outline-warning btn-sm w-100 btn-install-bundle d-inline-flex align-items-center justify-content-center gap-2" 
                                    data-bundle="tensorrt" ${trtSupported ? '' : 'disabled title="' + escapeHtml(t('Requires NVIDIA GPU')) + '"'}>
                                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 16 16" class="bi bi-download"><path d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5"/><path d="M7.646 11.854a.5.5 0 0 0 .708 0l3-3a.5.5 0 0 0-.708-.708L8.5 10.293V1.5a.5.5 0 0 0-1 0v8.793L5.354 8.146a.5.5 0 1 0-.708.708z"/></svg>
                                <span>${escapeHtml(trtPkg.installed ? t('Update TensorRT') : t('Install TensorRT'))}</span>
                            </button>
                        </div>
                    </div>
                </div>
            `;

            // 4. OpenVINO
            const ovPkg = pkgs.openvino || {};
            cardsHtml += `
                <div class="col-12 col-md-6 col-xl-3">
                    <div class="card h-100 border rounded-3 p-3 d-flex flex-column" style="background: var(--cv-surface-elevated, #1e2128); border-color: var(--cv-border, rgba(255,255,255,0.08)) !important;">
                        <div class="d-flex align-items-center justify-content-between mb-2">
                            <span class="fw-bold d-flex align-items-center gap-2 text-body">
                                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-speedometer2 text-info flex-shrink-0" viewBox="0 0 16 16"><path d="M8 4a.5.5 0 0 1 .5.5V6a.5.5 0 0 1-1 0V4.5A.5.5 0 0 1 8 4M3.732 5.732a.5.5 0 0 1 .707 0l.915.914a.5.5 0 1 1-.708.708l-.914-.915a.5.5 0 0 1 0-.707M2 10a.5.5 0 0 1 .5-.5h1.586a.5.5 0 0 1 0 1H2.5A.5.5 0 0 1 2 10m9.5 0a.5.5 0 0 1 .5-.5h1.5a.5.5 0 0 1 0 1H12a.5.5 0 0 1-.5-.5m.754-4.246a.39.39 0 0 0-.527-.02L7.547 9.31a.91.91 0 1 0 1.302 1.258l3.434-4.297a.39.39 0 0 0-.029-.518z"/><path fill-rule="evenodd" d="M0 10a8 8 0 1 1 15.547 2.661c-.442 1.253-1.845 1.602-2.932 1.25C11.309 13.488 9.475 13 8 13c-1.474 0-3.31.488-4.615.911-1.087.352-2.49.003-2.932-1.25A8 8 0 0 1 0 10m8-7a7 7 0 0 0-6.603 9.329c.203.575.923.876 1.68.63C4.397 12.533 6.358 12 8 12s3.604.532 4.923.96c.757.245 1.477-.056 1.68-.631A7 7 0 0 0 8 3"/></svg>
                                <span>OpenVINO</span>
                            </span>
                            ${ovPkg.installed
                                ? `<span class="badge bg-success-subtle text-success border border-success-subtle px-2 py-1">v${escapeHtml(ovPkg.version || 'OK')}</span>`
                                : `<span class="badge bg-secondary-subtle text-secondary border border-secondary-subtle px-2 py-1">${escapeHtml(t('Not installed'))}</span>`}
                        </div>
                        <div class="mb-3">
                            <p class="small mb-1 text-body-secondary">${escapeHtml(t('Acceleration'))}: <strong class="text-body">${escapeHtml(t('Intel CPU / iGPU'))}</strong></p>
                            <p class="small mb-0 text-body-secondary">${escapeHtml(t('Format'))}: <strong class="text-body font-monospace">.xml / .bin</strong></p>
                        </div>
                        <div class="pt-2 border-top mt-auto" style="border-color: var(--cv-border, rgba(255,255,255,0.08)) !important;">
                            <button type="button" class="btn btn-outline-info btn-sm w-100 btn-install-bundle d-inline-flex align-items-center justify-content-center gap-2" data-bundle="openvino">
                                <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 16 16" class="bi bi-download"><path d="M.5 9.9a.5.5 0 0 1 .5.5v2.5a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2.5a.5.5 0 0 1 1 0v2.5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2v-2.5a.5.5 0 0 1 .5-.5"/><path d="M7.646 11.854a.5.5 0 0 0 .708 0l3-3a.5.5 0 0 0-.708-.708L8.5 10.293V1.5a.5.5 0 0 0-1 0v8.793L5.354 8.146a.5.5 0 1 0-.708.708z"/></svg>
                                <span>${escapeHtml(ovPkg.installed ? t('Update OpenVINO') : t('Install OpenVINO'))}</span>
                            </button>
                        </div>
                    </div>
                </div>
            `;

            runtimesContainer.innerHTML = cardsHtml;

            // Attach install button listeners
            document.querySelectorAll('.btn-install-bundle').forEach(btn => {
                btn.addEventListener('click', function () {
                    const bundle = this.getAttribute('data-bundle');
                    startBundleInstall(bundle);
                });
            });
        }

        function startBundleInstall(bundle) {
            if (!bundle) return;
            installBundleBadge.textContent = bundle;
            installModalTitle.textContent = t('Installing') + ' ' + bundle;
            installLogTerminal.textContent = t('Initializing pip installation...') + '\n';
            installStatusText.textContent = t('Installation in progress...');
            installSpinner.classList.remove('d-none');
            refreshAfterInstallBtn.classList.add('d-none');
            closeInstallBtn.disabled = true;
            cancelInstallBtn.disabled = true;

            installModal.show();

            fetch(endpoints.runtimesInstall, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({bundle: bundle}),
            })
                .then(res => res.json())
                .then(data => {
                    if (!data.ok) {
                        installStatusText.textContent = t('Error') + ': ' + (data.error || 'Failed to start');
                        installSpinner.classList.add('d-none');
                        closeInstallBtn.disabled = false;
                        cancelInstallBtn.disabled = false;
                        return;
                    }
                    startPolling();
                })
                .catch(err => {
                    installStatusText.textContent = t('Error') + ': ' + err.message;
                    installSpinner.classList.add('d-none');
                    closeInstallBtn.disabled = false;
                    cancelInstallBtn.disabled = false;
                });
        }

        function startPolling() {
            if (pollInterval) clearInterval(pollInterval);
            pollInterval = setInterval(checkInstallStatus, 1500);
        }

        function checkInstallStatus() {
            fetch(endpoints.runtimesInstallStatus)
                .then(res => res.json())
                .then(data => {
                    if (!data.ok || !data.job) return;
                    const job = data.job;

                    if (job.logs && job.logs.length > 0) {
                        installLogTerminal.textContent = job.logs.join('\n');
                        installLogTerminal.scrollTop = installLogTerminal.scrollHeight;
                    }

                    if (job.status === 'success') {
                        clearInterval(pollInterval);
                        pollInterval = null;
                        installSpinner.classList.add('d-none');
                        installStatusText.innerHTML = '<span class="text-success d-inline-flex align-items-center gap-2"><svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" fill="currentColor" viewBox="0 0 16 16" class="bi bi-check-circle-fill"><path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0m-3.97-3.03a.75.75 0 0 0-1.08.022L7.477 9.417 5.384 7.323a.75.75 0 0 0-1.06 1.06L6.97 11.03a.75.75 0 0 0 1.079-.02l3.992-4.99a.75.75 0 0 0-.01-1.05z"/></svg><span>' + escapeHtml(t('Installation completed successfully!')) + '</span></span>';
                        refreshAfterInstallBtn.classList.remove('d-none');
                        closeInstallBtn.disabled = false;
                        cancelInstallBtn.disabled = false;
                        loadRuntimes();
                    } else if (job.status === 'error') {
                        clearInterval(pollInterval);
                        pollInterval = null;
                        installSpinner.classList.add('d-none');
                        installStatusText.innerHTML = `<span class="text-danger d-inline-flex align-items-center gap-2"><svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" fill="currentColor" viewBox="0 0 16 16" class="bi bi-exclamation-triangle-fill"><path d="M8.982 1.566a1.13 1.13 0 0 0-1.96 0L.165 13.233c-.457.778.091 1.767.98 1.767h13.713c.889 0 1.438-.99.98-1.767zM8 5c.535 0 .954.462.9.995l-.35 3.507a.552.552 0 0 1-1.1 0L7.1 5.995A.905.905 0 0 1 8 5m.002 6a1 1 0 1 1 0 2 1 1 0 0 1 0-2"/></svg><span>${escapeHtml(t('Installation failed'))}: ${escapeHtml(job.error || '')}</span></span>`;
                        closeInstallBtn.disabled = false;
                        cancelInstallBtn.disabled = false;
                    }
                })
                .catch(() => {
                });
        }

        if (refreshBtn) {
            refreshBtn.addEventListener('click', loadRuntimes);
        }

        if (refreshAfterInstallBtn) {
            refreshAfterInstallBtn.addEventListener('click', function () {
                window.location.reload();
            });
        }

        // Initial runtimes load
        loadRuntimes();

        // -------------------------------------------------------------
        // Log Viewer Implementation
        // -------------------------------------------------------------
        function initLogViewer() {
            const logTerminal = document.getElementById('log-terminal');
            if (!logTerminal) return;

            const refreshLogsBtn = document.getElementById('btn-refresh-logs');
            const copyLogsBtn = document.getElementById('btn-copy-logs');
            const copyLogsText = document.getElementById('btn-copy-logs-text');
            const clearLogsBtn = document.getElementById('btn-clear-logs');
            const levelFilterSelect = document.getElementById('log-level-filter');
            const linesLimitSelect = document.getElementById('log-lines-limit');
            const searchInput = document.getElementById('log-search-input');
            const searchClearBtn = document.getElementById('log-search-clear');
            const autoRefreshSwitch = document.getElementById('log-auto-refresh');
            const autoScrollSwitch = document.getElementById('log-auto-scroll');
            const scrollBottomBtn = document.getElementById('log-scroll-bottom-btn');
            const metaInfoBadge = document.getElementById('log-meta-info');
            const fileBadge = document.getElementById('log-file-badge');

            let logAutoRefreshTimer = null;
            let currentRawLogs = '';
            let isFetchingLogs = false;
            let searchDebounceTimer = null;

            function formatLogLine(line, searchQ) {
                // Match standard Python Logger pattern: "YYYY-MM-DD HH:MM:SS - LEVEL - message"
                const match = line.match(/^(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}(?:,\d+)?)\s*-\s*([A-Z]+)\s*-\s*(.*)$/);
                if (match) {
                    const ts = escapeHtml(match[1]);
                    const level = match[2];
                    let msg = escapeHtml(match[3]);

                    let levelStyle = 'color: #94a3b8; background: rgba(148,163,184,0.12);';
                    if (level === 'INFO') {
                        levelStyle = 'color: #38bdf8; background: rgba(56,189,248,0.14);';
                    } else if (level === 'WARNING') {
                        levelStyle = 'color: #fbbf24; background: rgba(251,191,36,0.16);';
                    } else if (level === 'ERROR') {
                        levelStyle = 'color: #f87171; background: rgba(248,113,113,0.18); font-weight: 700;';
                    } else if (level === 'DEBUG') {
                        levelStyle = 'color: #a78bfa; background: rgba(167,139,250,0.14);';
                    }

                    if (searchQ) {
                        const regex = new RegExp('(' + searchQ.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi');
                        msg = msg.replace(regex, '<mark style="background:#fef08a;color:#1e293b;padding:0 2px;border-radius:2px;">$1</mark>');
                    }

                    return `<div class="cv-log-row py-0.5"><span class="text-secondary opacity-75 me-2">${ts}</span><span class="badge font-monospace px-1.5 py-0.5 me-2" style="${levelStyle}">${level}</span><span>${msg}</span></div>`;
                } else {
                    let escapedLine = escapeHtml(line);
                    if (searchQ) {
                        const regex = new RegExp('(' + searchQ.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi');
                        escapedLine = escapedLine.replace(regex, '<mark style="background:#fef08a;color:#1e293b;padding:0 2px;border-radius:2px;">$1</mark>');
                    }
                    return `<div class="cv-log-row py-0.5 text-body-secondary">${escapedLine}</div>`;
                }
            }

            function scrollToBottom() {
                if (logTerminal) {
                    logTerminal.scrollTop = logTerminal.scrollHeight;
                }
            }

            function fetchLogs(silent = false) {
                if (isFetchingLogs) return;
                isFetchingLogs = true;

                const lines = linesLimitSelect ? linesLimitSelect.value : '100';
                const level = levelFilterSelect ? levelFilterSelect.value : '';
                const q = searchInput ? searchInput.value.trim() : '';

                if (!silent && (!logTerminal.textContent.trim() || logTerminal.querySelector('.spinner-border'))) {
                    logTerminal.innerHTML = `
                        <div class="text-body-secondary text-center py-4">
                            <div class="spinner-border spinner-border-sm me-2" role="status"></div>
                            <span>${escapeHtml(t('Loading logs...'))}</span>
                        </div>
                    `;
                }

                const url = `${endpoints.logs}?lines=${encodeURIComponent(lines)}&level=${encodeURIComponent(level)}&q=${encodeURIComponent(q)}`;

                fetch(url)
                    .then(res => res.json())
                    .then(data => {
                        isFetchingLogs = false;
                        if (!data.ok) {
                            logTerminal.innerHTML = `<div class="text-danger py-2">${escapeHtml(data.error || t('Failed to load logs.'))}</div>`;
                            return;
                        }

                        if (fileBadge && data.path) {
                            fileBadge.textContent = data.path;
                        }

                        if (metaInfoBadge) {
                            if (data.exists) {
                                metaInfoBadge.textContent = `${data.total_lines} ${t('lines')} | ${data.file_size_formatted} | ${data.mtime || ''}`;
                            } else {
                                metaInfoBadge.textContent = t('Log file not found');
                            }
                        }

                        currentRawLogs = (data.lines || []).join('\n');

                        if (!data.lines || data.lines.length === 0) {
                            logTerminal.innerHTML = `<div class="text-body-secondary text-center py-4"><em>${escapeHtml(t('No logs matching current filter'))}</em></div>`;
                            return;
                        }

                        const wasAtBottom = (logTerminal.scrollHeight - logTerminal.clientHeight <= logTerminal.scrollTop + 40);
                        const html = data.lines.map(l => formatLogLine(l, q)).join('');
                        logTerminal.innerHTML = html;

                        if (autoScrollSwitch && autoScrollSwitch.checked) {
                            scrollToBottom();
                        } else if (wasAtBottom) {
                            scrollToBottom();
                        }
                    })
                    .catch(err => {
                        isFetchingLogs = false;
                        logTerminal.innerHTML = `<div class="text-danger py-2">${escapeHtml(err.message)}</div>`;
                    });
            }

            // Copy logs
            if (copyLogsBtn) {
                copyLogsBtn.addEventListener('click', async function () {
                    if (!currentRawLogs) return;
                    try {
                        await navigator.clipboard.writeText(currentRawLogs);
                        const origText = copyLogsText ? copyLogsText.textContent : '';
                        if (copyLogsText) copyLogsText.textContent = t('Copied!');
                        copyLogsBtn.classList.replace('btn-outline-secondary', 'btn-success');
                        setTimeout(() => {
                            if (copyLogsText) copyLogsText.textContent = origText;
                            copyLogsBtn.classList.replace('btn-success', 'btn-outline-secondary');
                        }, 2000);
                    } catch (err) {
                        console.error('Failed to copy logs:', err);
                    }
                });
            }

            // Clear logs
            if (clearLogsBtn) {
                clearLogsBtn.addEventListener('click', async function () {
                    const confirmed = typeof window.appConfirm === 'function'
                        ? await window.appConfirm({
                            title: t('Clear log file'),
                            message: t('Are you sure you want to clear the application log file?'),
                            confirmText: t('Clear'),
                            tone: 'danger',
                        })
                        : window.confirm(t('Are you sure you want to clear the application log file?'));
                    if (!confirmed) return;

                    clearLogsBtn.disabled = true;
                    try {
                        const res = await fetch(endpoints.logsClear, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-Requested-With': 'XMLHttpRequest'
                            }
                        });
                        const data = await res.json();
                        if (data.ok) {
                            fetchLogs(false);
                        } else {
                            alert(data.error || t('Failed to clear log file'));
                        }
                    } catch (err) {
                        alert(err.message || t('Request error'));
                    } finally {
                        clearLogsBtn.disabled = false;
                    }
                });
            }

            // Filter changes
            if (levelFilterSelect) {
                levelFilterSelect.addEventListener('change', () => fetchLogs(false));
            }
            if (linesLimitSelect) {
                linesLimitSelect.addEventListener('change', () => fetchLogs(false));
            }

            // Search input
            if (searchInput) {
                searchInput.addEventListener('input', function () {
                    const val = this.value.trim();
                    if (searchClearBtn) {
                        searchClearBtn.classList.toggle('d-none', !val);
                    }
                    if (searchDebounceTimer) clearTimeout(searchDebounceTimer);
                    searchDebounceTimer = setTimeout(() => fetchLogs(true), 300);
                });
            }
            if (searchClearBtn) {
                searchClearBtn.addEventListener('click', function () {
                    if (searchInput) {
                        searchInput.value = '';
                        searchClearBtn.classList.add('d-none');
                        fetchLogs(false);
                    }
                });
            }

            // Refresh button
            if (refreshLogsBtn) {
                refreshLogsBtn.addEventListener('click', () => fetchLogs(false));
            }

            // Scroll detection for "Scroll to bottom" button
            if (logTerminal && scrollBottomBtn) {
                logTerminal.addEventListener('scroll', function () {
                    const isNearBottom = (logTerminal.scrollHeight - logTerminal.clientHeight <= logTerminal.scrollTop + 50);
                    scrollBottomBtn.classList.toggle('d-none', isNearBottom);
                });
                const bottomInnerBtn = scrollBottomBtn.querySelector('button');
                if (bottomInnerBtn) {
                    bottomInnerBtn.addEventListener('click', function () {
                        scrollToBottom();
                        if (autoScrollSwitch) autoScrollSwitch.checked = true;
                    });
                }
            }

            // Auto-refresh timer
            function startAutoRefresh() {
                stopAutoRefresh();
                if (autoRefreshSwitch && autoRefreshSwitch.checked) {
                    logAutoRefreshTimer = setInterval(() => {
                        fetchLogs(true);
                    }, 5000);
                }
            }

            function stopAutoRefresh() {
                if (logAutoRefreshTimer) {
                    clearInterval(logAutoRefreshTimer);
                    logAutoRefreshTimer = null;
                }
            }

            if (autoRefreshSwitch) {
                autoRefreshSwitch.addEventListener('change', function () {
                    if (this.checked) {
                        startAutoRefresh();
                        fetchLogs(true);
                    } else {
                        stopAutoRefresh();
                    }
                });
            }

            // Start initial logs load & auto-refresh
            fetchLogs(false);
            startAutoRefresh();
        }

        initLogViewer();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initSystemInfo);
    } else {
        initSystemInfo();
    }
})();
