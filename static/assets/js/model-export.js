/**
 * Computer Vision Counter (CVCounter)
 * Model export modal, opened from settings and the dashboard counter settings.
 *
 * Developed by: Aleksandr Kireev
 * Website: https://bespredel.name
 */

(function () {
    'use strict';

    const t = (key, params) => (typeof window.trans === 'function' ? window.trans(key, params) : key);

    const endpoints = Object.assign({
        modelsList: '/settings/api/models/list',
        runtimesStatus: '/settings/api/runtimes/status',
        modelExportCapabilities: '/settings/api/models/export/capabilities',
        modelsExport: '/settings/api/models/export',
        modelsExportStatus: '/settings/api/models/export/status'
    }, window.SETTINGS_ENDPOINTS || {});

    function escapeHtml(str) {
        if (str === null || str === undefined) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function initModelExport() {
        var exportModalEl = document.getElementById('modelExportModal');
        if (!exportModalEl) return;

        var exportModal = new bootstrap.Modal(exportModalEl);
        var exportSourceInput = document.getElementById('exportSourceWeights');
        var exportWeightsHint = document.getElementById('exportWeightsHint');
        var exportDropdownList = document.getElementById('exportModelsDropdownList');
        var exportFormatRadios = document.querySelectorAll('input[name="exportFormatRadio"]');
        var formatCards = document.querySelectorAll('.cv-format-card');
        var exportHalfCheckbox = document.getElementById('exportHalfFp16');
        var exportImgSizeInput = document.getElementById('exportImgSize');
        var exportDepAlert = document.getElementById('exportDependencyAlert');
        var exportDepMsg = document.getElementById('exportDependencyMsg');
        var btnStartExport = document.getElementById('btn-start-export');
        var btnCancelExport = document.getElementById('btn-cancel-export');
        var btnCloseExportModal = document.getElementById('btn-close-export-modal');
        var btnApplyExported = document.getElementById('btn-apply-exported-model');
        var exportProgressSec = document.getElementById('exportProgressSection');
        var exportLogTerminal = document.getElementById('exportLogTerminal');
        var exportStatusBadge = document.getElementById('exportStatusBadge');
        var exportSpinner = document.getElementById('exportSpinner');

        var activeTargetInput = null;
        var exportPollInterval = null;
        var cachedRuntimes = null;
        var cachedModelCapabilities = null;
        var capabilityRequestId = 0;
        var lastExportedPath = null;

        function getSelectedFormat() {
            var checked = document.querySelector('input[name="exportFormatRadio"]:checked');
            return checked ? checked.value : 'onnx';
        }

        function updateFormatCardsVisual(selectedFmt) {
            formatCards.forEach(function (card) {
                var fmt = card.getAttribute('data-format');
                var radio = card.querySelector('input[type="radio"]');
                if (fmt === selectedFmt) {
                    card.classList.add('active');
                    if (radio) radio.checked = true;
                } else {
                    card.classList.remove('active');
                    if (radio) radio.checked = false;
                }
            });
        }

        formatCards.forEach(function (card) {
            card.addEventListener('click', function () {
                var fmt = this.getAttribute('data-format');
                updateFormatCardsVisual(fmt);
                checkDependencies();
            });
        });

        function checkDependencies() {
            if (!cachedRuntimes) return;
            var fmt = getSelectedFormat();
            var modelCapability = cachedModelCapabilities
                && cachedModelCapabilities.export_capabilities
                ? cachedModelCapabilities.export_capabilities[fmt]
                : null;
            var runtimeCapability = (cachedRuntimes.export_capabilities || {})[fmt];
            var gpu = cachedRuntimes.gpu || {};
            var onnx = cachedRuntimes.onnx || {};
            var trt = cachedRuntimes.tensorrt || {};

            exportDepAlert.classList.add('d-none');
            btnStartExport.disabled = false;

            if (modelCapability) {
                if (!modelCapability.supported || !modelCapability.available) {
                    exportDepMsg.textContent = (modelCapability.reasons || []).join('; ')
                        || t('The selected model cannot be exported with this provider.');
                    exportDepAlert.classList.remove('d-none');
                    btnStartExport.disabled = true;
                }
            } else if (runtimeCapability) {
                if (!runtimeCapability.available) {
                    exportDepMsg.textContent = (runtimeCapability.reasons || []).join('; ')
                        || t('The selected export provider is unavailable.');
                    exportDepAlert.classList.remove('d-none');
                    btnStartExport.disabled = true;
                }
            } else if (fmt === 'engine') {
                if (!gpu.has_nvidia_gpu) {
                    exportDepMsg.textContent = t('TensorRT Engine export requires an NVIDIA GPU, none was detected.');
                    exportDepAlert.classList.remove('d-none');
                    btnStartExport.disabled = true;
                } else if (!trt.export_ready) {
                    exportDepMsg.textContent = t('Package tensorrt is not installed. Please install it on the System Info page.');
                    exportDepAlert.classList.remove('d-none');
                }
            } else if (fmt === 'onnx') {
                if (!onnx.export_ready) {
                    exportDepMsg.textContent = t('Package onnx is not installed. Please install it on the System Info page.');
                    exportDepAlert.classList.remove('d-none');
                }
            }

            var halfOn = exportHalfCheckbox && exportHalfCheckbox.checked;
            var capabilityNote = (runtimeCapability && runtimeCapability.fp16_note)
                || (modelCapability && modelCapability.export_capabilities
                    && modelCapability.export_capabilities.engine
                    && modelCapability.export_capabilities.engine.fp16_note);
            if (!btnStartExport.disabled && fmt === 'engine' && halfOn && capabilityNote) {
                exportDepMsg.textContent = t(capabilityNote);
                exportDepAlert.classList.remove('d-none');
                btnStartExport.disabled = true;
            }
        }

        if (exportHalfCheckbox) {
            exportHalfCheckbox.addEventListener('change', checkDependencies);
        }

        function fetchModelCapabilities() {
            var weights = exportSourceInput ? exportSourceInput.value.trim() : '';
            var requestId = ++capabilityRequestId;
            cachedModelCapabilities = null;
            if (!weights) {
                checkDependencies();
                return;
            }

            fetch(endpoints.modelExportCapabilities + '?weights=' + encodeURIComponent(weights))
                .then(function (res) {
                    return res.json().then(function (data) {
                        return {ok: res.ok, data: data};
                    });
                })
                .then(function (result) {
                    if (requestId !== capabilityRequestId) return;
                    if (result.ok && result.data.ok) {
                        cachedModelCapabilities = result.data.artifact;
                    } else {
                        cachedModelCapabilities = {
                            export_capabilities: {
                                onnx: {supported: false, available: false, reasons: [result.data.error || t('Model capabilities could not be resolved.')]},
                                engine: {supported: false, available: false, reasons: [result.data.error || t('Model capabilities could not be resolved.')]}
                            }
                        };
                    }
                    checkDependencies();
                })
                .catch(function () {
                    if (requestId !== capabilityRequestId) return;
                    var reason = t('Model capabilities could not be resolved.');
                    cachedModelCapabilities = {
                        export_capabilities: {
                            onnx: {supported: false, available: false, reasons: [reason]},
                            engine: {supported: false, available: false, reasons: [reason]}
                        }
                    };
                    checkDependencies();
                });
        }

        exportFormatRadios.forEach(function (radio) {
            radio.addEventListener('change', function () {
                updateFormatCardsVisual(this.value);
                checkDependencies();
            });
        });

        function loadAvailableModels() {
            if (!exportDropdownList) return;
            exportDropdownList.innerHTML = '<li><span class="dropdown-item-text text-body-secondary small">' + escapeHtml(t('Loading models...')) + '</span></li>';

            fetch(endpoints.modelsList)
                .then(function (res) {
                    return res.json();
                })
                .then(function (data) {
                    if (!data.ok || !data.models || data.models.length === 0) {
                        exportDropdownList.innerHTML = '<li><span class="dropdown-item-text text-body-secondary small">' + escapeHtml(t('No .pt models found')) + '</span></li>';
                        return;
                    }
                    var itemsHtml = '';
                    data.models.forEach(function (m) {
                        itemsHtml += '<li><button class="dropdown-item py-1.5 px-3 small d-flex align-items-center justify-content-between btn-select-model" type="button" data-path="' + escapeHtml(m.path) + '">' +
                            '<span class="fw-semibold font-monospace">' + escapeHtml(m.name) + '</span>' +
                            '<span class="badge bg-body-secondary text-body ms-2 font-monospace">' + m.size_mb + ' MB</span>' +
                            '</button></li>';
                    });
                    exportDropdownList.innerHTML = itemsHtml;

                    exportDropdownList.querySelectorAll('.btn-select-model').forEach(function (btn) {
                        btn.addEventListener('click', function () {
                            var p = this.getAttribute('data-path');
                            if (p && exportSourceInput) {
                                exportSourceInput.value = p;
                                if (exportWeightsHint) exportWeightsHint.textContent = '';
                                capabilityRequestId += 1;
                                cachedModelCapabilities = data.models.find(function (model) {
                                    return model.path === p;
                                }) || null;
                                checkDependencies();
                            }
                        });
                    });

                    if (exportSourceInput && !exportSourceInput.value.trim() && data.models.length > 0) {
                        exportSourceInput.value = data.models[0].path;
                    }
                    if (exportSourceInput) {
                        var selectedModel = data.models.find(function (model) {
                            return model.path === exportSourceInput.value.trim();
                        });
                        capabilityRequestId += 1;
                        cachedModelCapabilities = selectedModel || null;
                        if (selectedModel) {
                            checkDependencies();
                        } else {
                            fetchModelCapabilities();
                        }
                    }
                })
                .catch(function () {
                    exportDropdownList.innerHTML = '<li><span class="dropdown-item-text text-danger small">' + escapeHtml(t('Failed to load models list')) + '</span></li>';
                });
        }

        if (exportSourceInput) {
            exportSourceInput.addEventListener('change', fetchModelCapabilities);
            exportSourceInput.addEventListener('blur', fetchModelCapabilities);
        }

        function fetchRuntimesStatus() {
            fetch(endpoints.runtimesStatus)
                .then(function (res) {
                    return res.json();
                })
                .then(function (data) {
                    if (data.ok && data.runtimes) {
                        cachedRuntimes = data.runtimes;
                        checkDependencies();
                    }
                })
                .catch(function () {
                });
        }

        // Open modal trigger
        document.addEventListener('click', function (e) {
            var trigger = e.target.closest('.btn-model-export-trigger');
            if (!trigger) return;

            var inputId = trigger.getAttribute('data-weights-input-id');
            var targetInput = inputId ? document.getElementById(inputId) : null;
            if (!targetInput) {
                var container = trigger.closest('.input-group') || trigger.closest('.cv-form-field');
                targetInput = container ? container.querySelector('input') : null;
            }

            activeTargetInput = targetInput;
            var currentVal = targetInput ? (targetInput.value || '').trim() : '';

            var convertedVal = currentVal;
            var wasCompiled = false;
            if (/\.(engine|onnx|trt)$/i.test(currentVal)) {
                convertedVal = currentVal.replace(/\.(engine|onnx|trt)$/i, '.pt');
                wasCompiled = true;
            }

            if (exportSourceInput) {
                exportSourceInput.value = convertedVal;
            }

            if (exportWeightsHint) {
                if (wasCompiled) {
                    exportWeightsHint.innerHTML = '<span class="text-info d-flex align-items-center gap-1">'
                        + '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" class="bi bi-info-circle-fill flex-shrink-0" viewBox="0 0 16 16"><path d="M8 16A8 8 0 1 0 8 0a8 8 0 0 0 0 16m.93-9.412-1 4.705c-.07.34.029.533.304.533.194 0 .487-.07.686-.246l-.088.416c-.287.346-.92.598-1.465.598-.703 0-1.002-.422-.808-1.319l.738-3.468c.064-.293.006-.399-.287-.47l-.451-.081.082-.381 2.29-.287zM8 5.5a1 1 0 1 1 0-2 1 1 0 0 1 0 2"/></svg>'
                        + '<span>' + escapeHtml(t('Source .pt model suggested for export')) + '</span></span>';
                } else {
                    exportWeightsHint.textContent = '';
                }
            }

            // Reset selected format to ONNX by default
            updateFormatCardsVisual('onnx');

            exportProgressSec.classList.add('d-none');
            btnApplyExported.classList.add('d-none');
            btnStartExport.classList.remove('d-none');
            btnStartExport.disabled = false;
            btnCancelExport.disabled = false;
            btnCloseExportModal.disabled = false;
            lastExportedPath = null;

            loadAvailableModels();
            fetchRuntimesStatus();
            fetchModelCapabilities();
            exportModal.show();
        });

        // Start export handler
        if (btnStartExport) {
            btnStartExport.addEventListener('click', function () {
                var weightsVal = exportSourceInput ? exportSourceInput.value.trim() : '';
                if (!weightsVal) {
                    alert(t('Please specify the source weights path.'));
                    if (exportSourceInput) exportSourceInput.focus();
                    return;
                }

                var fmt = getSelectedFormat();
                var half = exportHalfCheckbox ? exportHalfCheckbox.checked : false;
                var imgsz = exportImgSizeInput ? parseInt(exportImgSizeInput.value, 10) || 640 : 640;

                btnStartExport.disabled = true;
                btnCancelExport.disabled = true;
                btnCloseExportModal.disabled = true;
                btnApplyExported.classList.add('d-none');

                exportProgressSec.classList.remove('d-none');
                exportSpinner.classList.remove('d-none');
                exportStatusBadge.textContent = t('Starting export...');
                exportLogTerminal.textContent = t('Submitting export job...') + '\n';

                fetch(endpoints.modelsExport, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        weights: weightsVal,
                        format: fmt,
                        half: half,
                        imgsz: imgsz
                    })
                })
                    .then(function (res) {
                        return res.json();
                    })
                    .then(function (data) {
                        if (!data.ok) {
                            exportSpinner.classList.add('d-none');
                            exportStatusBadge.innerHTML = '<span class="text-danger">' + escapeHtml(t('Error')) + ': ' + escapeHtml(data.error || 'Export failed') + '</span>';
                            btnStartExport.disabled = false;
                            btnCancelExport.disabled = false;
                            btnCloseExportModal.disabled = false;
                            return;
                        }
                        startExportPolling();
                    })
                    .catch(function (err) {
                        exportSpinner.classList.add('d-none');
                        exportStatusBadge.innerHTML = '<span class="text-danger">' + escapeHtml(t('Request error')) + ': ' + escapeHtml(err.message) + '</span>';
                        btnStartExport.disabled = false;
                        btnCancelExport.disabled = false;
                        btnCloseExportModal.disabled = false;
                    });
            });
        }

        function startExportPolling() {
            if (exportPollInterval) clearInterval(exportPollInterval);
            exportPollInterval = setInterval(checkExportStatus, 1500);
        }

        function checkExportStatus() {
            fetch(endpoints.modelsExportStatus)
                .then(function (res) {
                    return res.json();
                })
                .then(function (data) {
                    if (!data.ok || !data.export) return;
                    var exp = data.export;

                    if (exp.logs && exp.logs.length > 0) {
                        exportLogTerminal.textContent = exp.logs.join('\n');
                        exportLogTerminal.scrollTop = exportLogTerminal.scrollHeight;
                    }

                    if (exp.status === 'completed') {
                        clearInterval(exportPollInterval);
                        exportPollInterval = null;
                        exportSpinner.classList.add('d-none');
                        exportStatusBadge.innerHTML = '<span class="text-success fw-bold d-inline-flex align-items-center gap-1"><svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" fill="currentColor" viewBox="0 0 16 16" class="bi bi-check-circle-fill"><path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0m-3.97-3.03a.75.75 0 0 0-1.08.022L7.477 9.417 5.384 7.323a.75.75 0 0 0-1.06 1.06L6.97 11.03a.75.75 0 0 0 1.079-.02l3.992-4.99a.75.75 0 0 0-.01-1.05z"/></svg><span>' + escapeHtml(t('Export completed!')) + '</span></span>';
                        btnCancelExport.disabled = false;
                        btnCloseExportModal.disabled = false;
                        btnStartExport.classList.add('d-none');

                        if (exp.result_path) {
                            lastExportedPath = exp.result_path;
                            btnApplyExported.classList.remove('d-none');
                        }
                    } else if (exp.status === 'error') {
                        clearInterval(exportPollInterval);
                        exportPollInterval = null;
                        exportSpinner.classList.add('d-none');
                        exportStatusBadge.innerHTML = '<span class="text-danger fw-bold d-inline-flex align-items-center gap-1"><svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" fill="currentColor" viewBox="0 0 16 16" class="bi bi-exclamation-triangle-fill"><path d="M8.982 1.566a1.13 1.13 0 0 0-1.96 0L.165 13.233c-.457.778.091 1.767.98 1.767h13.713c.889 0 1.438-.99.98-1.767zM8 5c.535 0 .954.462.9.995l-.35 3.507a.552.552 0 0 1-1.1 0L7.1 5.995A.905.905 0 0 1 8 5m.002 6a1 1 0 1 1 0 2 1 1 0 0 1 0-2"/></svg><span>' + escapeHtml(t('Export failed')) + ': ' + escapeHtml(exp.error || '') + '</span></span>';
                        btnStartExport.disabled = false;
                        btnCancelExport.disabled = false;
                        btnCloseExportModal.disabled = false;
                    }
                })
                .catch(function () {
                });
        }

        // Apply exported model path to input
        if (btnApplyExported) {
            btnApplyExported.addEventListener('click', function () {
                if (lastExportedPath && activeTargetInput) {
                    activeTargetInput.value = lastExportedPath;
                    // Trigger change event
                    var event = new Event('change', {bubbles: true});
                    activeTargetInput.dispatchEvent(event);

                    // Optional: auto-adjust model_type dropdown if present in the same section
                    var formSection = activeTargetInput.closest('.cv-camera-card') || activeTargetInput.closest('.tab-pane') || activeTargetInput.closest('form');
                    if (formSection) {
                        var modelTypeSelect = formSection.querySelector('select[name$="model_type"]');
                        if (modelTypeSelect) {
                            var fmt = getSelectedFormat();
                            if (fmt === 'onnx') {
                                modelTypeSelect.value = 'onnx';
                            } else if (fmt === 'engine') {
                                modelTypeSelect.value = 'yolo';
                            }
                        }
                    }
                }
                exportModal.hide();
            });
        }

        exportModalEl.addEventListener('shown.bs.modal', function () {
            var backdrops = document.querySelectorAll('.modal-backdrop');
            if (backdrops.length > 1) {
                backdrops[backdrops.length - 1].style.zIndex = '1070';
            }
        });

        exportModalEl.addEventListener('hidden.bs.modal', function () {
            if (document.querySelector('.modal.show')) {
                document.body.classList.add('modal-open');
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initModelExport);
    } else {
        initModelExport();
    }
})();
