/**
 * Computer Vision Counter (CVCounter)
 * Settings Page Scripts (Navigation, Classes, Password Toggle, Model Export & Optimizations).
 *
 * Developed by: Aleksandr Kireev
 * Created: 13.10.2026
 * Website: https://bespredel.name
 */

(function () {
    'use strict';

    const t = (key, params) => (typeof window.trans === 'function' ? window.trans(key, params) : key);

    const endpoints = Object.assign({
        modelClasses: '/settings/api/model_classes',
        modelsList: '/settings/api/models/list',
        runtimesStatus: '/settings/api/runtimes/status',
        modelsExport: '/settings/api/models/export',
        modelsExportStatus: '/settings/api/models/export/status'
    }, window.SETTINGS_ENDPOINTS || {});

    // Escape HTML helper
    function escapeHtml(str) {
        if (str === null || str === undefined) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function initSettings() {
        var tabButtons = document.querySelectorAll('#pills-tab button[data-bs-toggle="pill"]');
        var activeTabInput = document.getElementById('settings-active-tab');
        var toolbarTitle = document.getElementById('settings-toolbar-section-title');
        var toolbarIcon = document.getElementById('settings-toolbar-section-icon');
        var searchInput = document.getElementById('settings-search-input');

        function syncActiveTabUI(btn) {
            if (!btn) return;
            var key = btn.dataset.sectionKey;
            if (activeTabInput && key) {
                activeTabInput.value = key;
            }
            var textSpan = btn.querySelector('.text-truncate');
            var iconSpan = btn.querySelector('.settings-nav-icon');
            if (toolbarTitle && textSpan) {
                toolbarTitle.textContent = textSpan.textContent.trim();
            }
            if (toolbarIcon && iconSpan) {
                toolbarIcon.innerHTML = iconSpan.innerHTML;
            }
        }

        tabButtons.forEach(function (btn) {
            btn.addEventListener('shown.bs.tab', function (e) {
                var target = e.target;
                var key = target.dataset.sectionKey;
                syncActiveTabUI(target);
                if (key) {
                    try {
                        history.replaceState(null, '', '#pills-' + key);
                    } catch (err) {
                    }
                }
            });
        });

        // Restore active tab from hash
        var hash = window.location.hash;
        if (hash) {
            var cleanHash = hash.replace(/^#/, '');
            var matchBtn = document.getElementById(cleanHash + '-tab') ||
                document.querySelector('#pills-tab button[data-section-key="' + cleanHash.replace(/^pills-/, '') + '"]');
            if (matchBtn) {
                var tabInst = bootstrap.Tab.getOrCreateInstance(matchBtn);
                tabInst.show();
                syncActiveTabUI(matchBtn);
            }
        } else {
            var firstActive = document.querySelector('#pills-tab button.active');
            if (firstActive) syncActiveTabUI(firstActive);
        }

        // Password visibility toggle handler
        document.addEventListener('click', function (e) {
            var toggleBtn = e.target.closest('.cv-password-toggle');
            if (!toggleBtn) return;
            e.preventDefault();
            var group = toggleBtn.closest('.input-group');
            if (!group) return;
            var input = group.querySelector('.cv-password-input') || group.querySelector('input');
            if (!input) return;
            var isPass = input.type === 'password';
            input.type = isPass ? 'text' : 'password';
            toggleBtn.setAttribute('title', isPass ? t('Hide password') : t('Show password'));
            toggleBtn.innerHTML = isPass ?
                '<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" fill="currentColor" class="bi bi-eye-slash" viewBox="0 0 16 16"><path d="M13.359 11.238C15.06 9.72 16 8 16 8s-3-5.5-8-5.5a7 7 0 0 0-2.79.588l.77.771A6 6 0 0 1 8 3.5c2.12 0 3.879 1.168 5.168 2.457A13 13 0 0 1 14.828 8q-.086.13-.195.288c-.335.48-.83 1.12-1.465 1.755q-.247.248-.506.476z"/><path d="M11.297 9.176a3.5 3.5 0 0 0-4.474-4.474l.823.823a2.5 2.5 0 0 1 2.829 2.829zm-2.943 1.299.822.822a3.5 3.5 0 0 1-4.474-4.474l.823.823a2.5 2.5 0 0 0 2.829 2.829"/><path d="M3.35 5.47q-.27.24-.518.487A13 13 0 0 0 1.172 8l.195.288c.335.48.83 1.12 1.465 1.755C4.121 11.332 5.881 12.5 8 12.5c.716 0 1.39-.133 2.02-.36l.77.772A7 7 0 0 1 8 13.5C3 13.5 0 8 0 8s.939-1.721 2.641-3.238l.71.708zm10.296 8.884-12-12 .708-.708 12 12z"/></svg>' :
                '<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" fill="currentColor" class="bi bi-eye" viewBox="0 0 16 16"><path d="M16 8s-3-5.5-8-5.5S0 8 0 8s3 5.5 8 5.5S16 8 16 8M1.173 8a13 13 0 0 1 1.66-2.043C4.12 4.668 5.88 3.5 8 3.5s3.879 1.168 5.168 2.457A13 13 0 0 1 14.828 8q-.086.13-.195.288c-.335.48-8.3 1.12-1.465 1.755C11.879 11.332 10.119 12.5 8 12.5s-3.879-1.168-5.168-2.457A13 13 0 0 1 1.172 8z"/><path d="M8 5.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5M4.5 8a3.5 3.5 0 1 1 7 0 3.5 3.5 0 0 1-7 0"/></svg>';
        });

        // Live rate percentage badges
        document.addEventListener('input', function (e) {
            if (e.target.classList.contains('cv-rate-input')) {
                var group = e.target.closest('.cv-input-group');
                if (!group) return;
                var badge = group.querySelector('.cv-rate-badge');
                if (badge) {
                    var val = parseFloat(e.target.value);
                    if (!isNaN(val)) {
                        badge.textContent = Math.round(val * 100) + '%';
                    }
                }
            }
        });

        // Camera collapse & expand all
        var btnCollapseAll = document.getElementById('btn-collapse-all-cameras');
        var btnExpandAll = document.getElementById('btn-expand-all-cameras');
        if (btnCollapseAll) {
            btnCollapseAll.addEventListener('click', function () {
                document.querySelectorAll('#pills-detections .cv-camera-card__collapse').forEach(function (el) {
                    bootstrap.Collapse.getOrCreateInstance(el, {toggle: false}).hide();
                });
            });
        }
        if (btnExpandAll) {
            btnExpandAll.addEventListener('click', function () {
                document.querySelectorAll('#pills-detections .cv-camera-card__collapse').forEach(function (el) {
                    bootstrap.Collapse.getOrCreateInstance(el, {toggle: false}).show();
                });
            });
        }

        // Quick live search across form fields
        if (searchInput) {
            searchInput.addEventListener('input', function (e) {
                var q = (e.target.value || '').trim().toLowerCase();
                var allFields = document.querySelectorAll('.tab-pane .cv-form-field, .tab-pane .cv-form-section, .tab-pane .cv-camera-card');
                var tabsWithMatches = new Set();

                if (!q) {
                    allFields.forEach(function (el) {
                        el.classList.remove('is-search-match', 'is-search-dimmed');
                        el.style.display = '';
                    });
                    return;
                }

                allFields.forEach(function (el) {
                    var text = (el.textContent || '').toLowerCase();
                    var isMatch = text.indexOf(q) !== -1;
                    el.classList.toggle('is-search-match', isMatch);
                    el.classList.toggle('is-search-dimmed', !isMatch);
                    if (isMatch) {
                        var pane = el.closest('.tab-pane');
                        if (pane && pane.dataset.sectionKey) {
                            tabsWithMatches.add(pane.dataset.sectionKey);
                        }
                        // Auto expand camera card if matched inside
                        var parentCameraCard = el.closest('.cv-camera-card');
                        if (parentCameraCard) {
                            var collapseEl = parentCameraCard.querySelector('.cv-camera-card__collapse');
                            if (collapseEl) {
                                bootstrap.Collapse.getOrCreateInstance(collapseEl, {toggle: false}).show();
                            }
                        }
                    }
                });

                // If matches exist outside current tab, auto-switch to first matching tab
                if (tabsWithMatches.size > 0) {
                    var activePane = document.querySelector('.tab-pane.active');
                    var activeKey = activePane ? activePane.dataset.sectionKey : null;
                    if (!tabsWithMatches.has(activeKey)) {
                        var firstMatchKey = Array.from(tabsWithMatches)[0];
                        var targetBtn = document.querySelector('#pills-tab button[data-section-key="' + firstMatchKey + '"]');
                        if (targetBtn) {
                            bootstrap.Tab.getOrCreateInstance(targetBtn).show();
                        }
                    }
                }
            });
        }

        // --- Classes Management (Toggles & Dynamic Model Loading) ---
        function updateClassItemUI(switchEl) {
            var item = switchEl.closest('.cv-class-item');
            if (!item) return;
            var badge = item.querySelector('.cv-class-status-badge');
            var isChecked = switchEl.checked;
            item.classList.toggle('opacity-75', !isChecked);
            if (badge) {
                badge.textContent = isChecked ? t('Active') : t('Disabled');
                badge.classList.toggle('text-success', isChecked);
                badge.classList.toggle('text-body-secondary', !isChecked);
            }
        }

        // Live toggle switch handler
        document.addEventListener('change', function (e) {
            if (e.target && e.target.classList.contains('cv-class-enable-switch')) {
                updateClassItemUI(e.target);
            }
        });

        // Enable all classes in section
        document.addEventListener('click', function (e) {
            var btn = e.target.closest('.btn-enable-all-classes');
            if (!btn) return;
            var section = btn.closest('.cv-classes-section');
            if (!section) return;
            var switches = section.querySelectorAll('.cv-class-enable-switch');
            switches.forEach(function (sw) {
                sw.checked = true;
                updateClassItemUI(sw);
            });
        });

        // Disable all classes in section
        document.addEventListener('click', function (e) {
            var btn = e.target.closest('.btn-disable-all-classes');
            if (!btn) return;
            var section = btn.closest('.cv-classes-section');
            if (!section) return;
            var switches = section.querySelectorAll('.cv-class-enable-switch');
            switches.forEach(function (sw) {
                sw.checked = false;
                updateClassItemUI(sw);
            });
        });

        // Quick filter classes within a section
        document.addEventListener('input', function (e) {
            if (e.target && e.target.classList.contains('cv-classes-filter-input')) {
                var filterText = (e.target.value || '').trim().toLowerCase();
                var section = e.target.closest('.cv-classes-section');
                if (!section) return;
                var items = section.querySelectorAll('.cv-class-item');
                items.forEach(function (item) {
                    var nameInput = item.querySelector('.cv-class-name-input');
                    var classId = item.getAttribute('data-class-id') || '';
                    var val = ((nameInput ? nameInput.value : '') + ' ' + classId).toLowerCase();
                    item.style.display = (!filterText || val.indexOf(filterText) !== -1) ? '' : 'none';
                });
            }
        });

        // Load classes from model via AJAX
        document.addEventListener('click', async function (e) {
            var btn = e.target.closest('.btn-load-model-classes');
            if (!btn) return;

            var prefix = btn.dataset.classesPrefix || '';
            var section = btn.closest('.cv-classes-section');
            if (!section) return;

            // Find corresponding weights_path input
            var weightsInput = document.querySelector('input[name="' + prefix + 'weights_path"]');
            if (!weightsInput) {
                var container = btn.closest('.cv-camera-card') || btn.closest('.tab-pane') || document;
                weightsInput = container.querySelector('input[name$="weights_path"]');
            }

            var weightsPath = weightsInput ? (weightsInput.value || '').trim() : '';
            if (!weightsPath) {
                if (window.appAlert) {
                    await window.appAlert({
                        title: t('Notice'),
                        message: t('Weights path is required'),
                        tone: 'warning'
                    });
                } else {
                    alert(t('Weights path is required'));
                }
                if (weightsInput) weightsInput.focus();
                return;
            }

            var origContent = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>' + escapeHtml(t('Loading...'));

            try {
                var response = await fetch(endpoints.modelClasses, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify({weights_path: weightsPath})
                });

                var data = await response.json();
                if (!response.ok || (!data.ok && !data.success)) {
                    var errMsg = (data && data.error) ? data.error : t('Failed to extract classes from model');
                    if (window.appAlert) {
                        await window.appAlert({
                            title: t('Error'),
                            message: errMsg,
                            tone: 'danger'
                        });
                    } else {
                        alert(errMsg);
                    }
                    return;
                }

                var classes = data.classes;
                if (!classes || typeof classes !== 'object' || Object.keys(classes).length === 0) {
                    if (window.appAlert) {
                        await window.appAlert({
                            title: t('Error'),
                            message: t('Failed to extract classes from model'),
                            tone: 'danger'
                        });
                    } else {
                        alert(t('Failed to extract classes from model'));
                    }
                    return;
                }

                var containerEl = section.querySelector('.cv-classes-container');
                if (!containerEl) return;

                var fieldId = prefix + 'classes';
                var html = '';

                // Sort numerical keys properly
                var sortedKeys = Object.keys(classes).sort(function (a, b) {
                    var na = parseInt(a, 10), nb = parseInt(b, 10);
                    if (!isNaN(na) && !isNaN(nb)) return na - nb;
                    return a.localeCompare(b);
                });

                sortedKeys.forEach(function (cid) {
                    var cname = classes[cid];
                    var safeName = escapeHtml(cname);
                    var safeCid = escapeHtml(cid);
                    html += '<div class="cv-form-field cv-class-item" data-class-id="' + safeCid + '">\n' +
                        '    <div class="d-flex align-items-center justify-content-between mb-1">\n' +
                        '        <label for="' + fieldId + '-' + safeCid + '-name" class="cv-form-label d-flex align-items-center gap-2 mb-0">\n' +
                        '            <div class="form-check form-switch m-0 d-inline-flex align-items-center" style="min-height: auto;">\n' +
                        '                <input class="form-check-input cv-class-enable-switch" type="checkbox" role="switch"\n' +
                        '                       name="' + fieldId + '-' + safeCid + '-enabled"\n' +
                        '                       id="' + fieldId + '-' + safeCid + '-enabled"\n' +
                        '                       value="on"\n' +
                        '                       checked>\n' +
                        '            </div>\n' +
                        '            <span class="badge bg-secondary-subtle text-secondary-emphasis font-monospace px-1.5 py-0.5" style="font-size: 0.72rem;">ID ' + safeCid + '</span>\n' +
                        '            <span>' + escapeHtml(t('Class name')) + '</span>\n' +
                        '        </label>\n' +
                        '        <span class="cv-class-status-badge small fw-semibold text-success ms-2 flex-shrink-0">\n' +
                        '            ' + escapeHtml(t('Active')) + '\n' +
                        '        </span>\n' +
                        '    </div>\n' +
                        '    <input type="text" id="' + fieldId + '-' + safeCid + '-name" name="' + fieldId + '-' + safeCid + '-name"\n' +
                        '           value="' + safeName + '" class="form-control cv-form-control cv-class-name-input py-1 px-2.5" style="font-size: 0.85rem;">\n' +
                        '</div>\n';
                });

                containerEl.innerHTML = html;

                var filterBar = section.querySelector('.cv-classes-filter-bar');
                if (filterBar) {
                    filterBar.classList.remove('d-none');
                    var filterInput = filterBar.querySelector('.cv-classes-filter-input');
                    if (filterInput) filterInput.value = '';
                }

                var countBadge = section.querySelector('.cv-classes-count');
                if (countBadge) {
                    countBadge.textContent = sortedKeys.length;
                }

                // Temporary visual feedback
                btn.classList.remove('btn-outline-primary');
                btn.classList.add('btn-success');
                setTimeout(function () {
                    btn.classList.remove('btn-success');
                    btn.classList.add('btn-outline-primary');
                }, 2000);

            } catch (err) {
                console.error('Failed to load model classes:', err);
                var errMsg = t('Failed to extract classes from model') + ': ' + (err.message || err);
                if (window.appAlert) {
                    await window.appAlert({
                        title: t('Error'),
                        message: errMsg,
                        tone: 'danger'
                    });
                } else {
                    alert(errMsg);
                }
            } finally {
                btn.disabled = false;
                btn.innerHTML = origContent;
            }
        });

        // --- Model Export & Optimization Modal Logic ---
        var exportModalEl = document.getElementById('modelExportModal');
        if (exportModalEl) {
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
                var gpu = cachedRuntimes.gpu || {};
                var onnx = cachedRuntimes.onnx || {};
                var trt = cachedRuntimes.tensorrt || {};

                exportDepAlert.classList.add('d-none');
                btnStartExport.disabled = false;

                if (fmt === 'engine') {
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
                                }
                            });
                        });

                        if (exportSourceInput && !exportSourceInput.value.trim() && data.models.length > 0) {
                            exportSourceInput.value = data.models[0].path;
                        }
                    })
                    .catch(function () {
                        exportDropdownList.innerHTML = '<li><span class="dropdown-item-text text-danger small">' + escapeHtml(t('Failed to load models list')) + '</span></li>';
                    });
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
                        exportWeightsHint.innerHTML = '<span class="text-info d-flex align-items-center gap-1.5">'
                            + '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" class="flex-shrink-0" viewBox="0 0 16 16"><path d="M8 16A8 8 0 1 0 8 0a8 8 0 0 0 0 16m.93-9.412-1 4.705c-.07.34.029.533.304.533.194 0 .487-.07.686-.246l-.088.416c-.287.346-.92.598-1.465.598-.703 0-1.002-.422-.808-1.319l.738-3.468c.064-.293.006-.399-.287-.47l-.451-.081.082-.381 2.29-.287zM8 5.5a1 1 0 1 1 0-2 1 1 0 0 1 0 2"/></svg>'
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
                            exportStatusBadge.innerHTML = '<span class="text-success fw-bold d-inline-flex align-items-center gap-1.5"><svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" fill="currentColor" viewBox="0 0 16 16"><path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0m-3.97-3.03a.75.75 0 0 0-1.08.022L7.477 9.417 5.384 7.323a.75.75 0 0 0-1.06 1.06L6.97 11.03a.75.75 0 0 0 1.079-.02l3.992-4.99a.75.75 0 0 0-.01-1.05z"/></svg><span>' + escapeHtml(t('Export completed!')) + '</span></span>';
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
                            exportStatusBadge.innerHTML = '<span class="text-danger fw-bold d-inline-flex align-items-center gap-1.5"><svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" fill="currentColor" viewBox="0 0 16 16"><path d="M8.982 1.566a1.13 1.13 0 0 0-1.96 0L.165 13.233c-.457.778.091 1.767.98 1.767h13.713c.889 0 1.438-.99.98-1.767zM8 5c.535 0 .954.462.9.995l-.35 3.507a.552.552 0 0 1-1.1 0L7.1 5.995A.905.905 0 0 1 8 5m.002 6a1 1 0 1 1 0 2 1 1 0 0 1 0-2"/></svg><span>' + escapeHtml(t('Export failed')) + ': ' + escapeHtml(exp.error || '') + '</span></span>';
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
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initSettings);
    } else {
        initSettings();
    }
})();
