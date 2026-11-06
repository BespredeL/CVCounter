/**
 * Computer Vision Counter (CVCounter)
 * Classes editor shared by the settings page and the dashboard counter modal.
 *
 * Developed by: Aleksandr Kireev
 * Website: https://bespredel.name
 */

(function () {
    'use strict';

    const t = (key, params) => (typeof window.trans === 'function' ? window.trans(key, params) : key);

    const endpoints = Object.assign({
        modelClasses: '/settings/api/model_classes'
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
})();
