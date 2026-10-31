/**
 * Computer Vision Counter (CVCounter)
 * Inference device picker - shared by the settings page and the counter settings modal.
 *
 * Developed by: Aleksandr Kireev
 * Website: https://bespredel.name
 */
(function () {
    'use strict';

    const t = (key, params) => (typeof window.trans === 'function' ? window.trans(key, params) : key);

    var RUNTIMES_STATUS_ENDPOINT = '/settings/api/runtimes/status';
    var DEVICE_CUSTOM = '__custom__';
    var DEVICE_AUTO_TYPES = ['yolo', 'ultralytics', 'auto'];
    var DEVICE_OPENVINO_TYPES = ['openvino', 'openvino_dnn'];
    var DEVICE_IGNORED_TYPES = ['opencv', 'opencv_dnn'];
    var runtimesStatusCache = null;
    var runtimesStatusWaiters = [];

    function loadRuntimesStatus(callback) {
        if (runtimesStatusCache) {
            callback(runtimesStatusCache);
            return;
        }
        runtimesStatusWaiters.push(callback);
        if (runtimesStatusWaiters.length > 1) {
            return;
        }
        function deliver() {
            var waiters = runtimesStatusWaiters.slice();
            runtimesStatusWaiters = [];
            waiters.forEach(function (waiter) {
                waiter(runtimesStatusCache);
            });
        }
        fetch(RUNTIMES_STATUS_ENDPOINT)
            .then(function (res) {
                return res.json();
            })
            .then(function (data) {
                if (data && data.ok && data.runtimes) {
                    runtimesStatusCache = data.runtimes;
                }
                deliver();
            })
            .catch(deliver);
    }

    function deviceOptionsFor(modelType, runtimes) {
        var mt = String(modelType || 'yolo').toLowerCase();
        var gpu = (runtimes && runtimes.gpu) || {};
        var options = [];
        var index;

        // OpenCV DNN addresses accelerators through backend/target, so device stays free text
        if (DEVICE_IGNORED_TYPES.indexOf(mt) !== -1) {
            return [];
        }

        if (DEVICE_OPENVINO_TYPES.indexOf(mt) !== -1) {
            return [
                {value: 'CPU', label: t('Processor') + ' (CPU)'},
                {value: 'AUTO', label: t('Auto-detect') + ' (AUTO)'},
                {value: 'GPU', label: t('Graphics') + ' (GPU)'},
                {value: 'GPU.0', label: t('Graphics') + ' 0 (GPU.0)'},
                {value: 'GPU.1', label: t('Graphics') + ' 1 (GPU.1)'},
                {value: 'NPU', label: t('Neural engine') + ' (NPU)'}
            ];
        }

        var gpuCount = gpu.cuda_available ? (parseInt(gpu.device_count, 10) || 0) : 0;
        for (index = 0; index < gpuCount; index++) {
            options.push({
                value: String(index),
                label: (gpu.device_name || t('Graphics')) + ' (' + index + ')'
            });
        }
        options.push({value: 'cpu', label: t('Processor') + ' (cpu)'});
        if (DEVICE_AUTO_TYPES.indexOf(mt) !== -1) {
            options.push({value: 'auto', label: t('Auto-detect') + ' (auto)'});
        }
        if (!gpuCount) {
            options.unshift({value: '', label: t('No CUDA GPU detected'), disabled: true});
        }
        return options;
    }

    function siblingModelTypeInput(deviceInput) {
        return document.getElementById(String(deviceInput.id || '').replace(/-device$/, '-model_type'));
    }

    function sameDeviceValue(optionValue, inputValue) {
        return String(optionValue).trim().toLowerCase() === String(inputValue).trim().toLowerCase();
    }

    function initDeviceField(deviceInput) {
        var group = deviceInput.closest('.cv-device-group');
        if (!group || deviceInput.dataset.devicePickerReady) return;
        deviceInput.dataset.devicePickerReady = '1';

        var select = document.createElement('select');
        select.className = 'form-select cv-form-control cv-form-select cv-device-select';
        select.setAttribute('aria-label', t('Inference device'));
        select.hidden = true;
        group.insertBefore(select, deviceInput);

        var modelInput = siblingModelTypeInput(deviceInput);

        function render() {
            var modelType = modelInput && modelInput.value ? modelInput.value : 'yolo';
            var options = deviceOptionsFor(modelType, runtimesStatusCache);
            if (!options.length) {
                select.hidden = true;
                return;
            }
            select.hidden = false;
            var current = deviceInput.value.trim();
            var matched = false;
            select.textContent = '';
            options.forEach(function (option) {
                var node = document.createElement('option');
                node.value = option.value;
                node.textContent = option.label;
                node.disabled = !!option.disabled;
                if (!matched && !option.disabled && sameDeviceValue(option.value, current)) {
                    node.selected = true;
                    matched = true;
                }
                select.appendChild(node);
            });
            var custom = document.createElement('option');
            custom.value = DEVICE_CUSTOM;
            custom.textContent = matched ? t('Custom value') : current + ' (' + t('Custom value') + ')';
            custom.selected = !matched;
            select.appendChild(custom);
        }

        select.addEventListener('change', function () {
            if (select.value === DEVICE_CUSTOM) {
                deviceInput.focus();
                return;
            }
            deviceInput.value = select.value;
            render();
        });

        deviceInput.addEventListener('change', render);
        if (modelInput) modelInput.addEventListener('change', render);

        loadRuntimesStatus(render);
    }

    /**
     * Attach pickers to every device field inside the given root.
     *
     * @param {Element|Document} [root] - Scope of the search, document by default
     * @returns {void}
     */
    function init(root) {
        (root || document).querySelectorAll('input[data-device-input]').forEach(initDeviceField);
    }

    window.DevicePicker = { init: init };
})();
