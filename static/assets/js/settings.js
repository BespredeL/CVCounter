/**
 * Computer Vision Counter (CVCounter)
 * Settings Page Scripts (Navigation, Classes, Password Toggle, Model Export & Optimizations).
 *
 * Developed by: Aleksandr Kireev
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

    // Fast MD5 implementation for client-side camera ID generation
    function md5(string) {
        function rotateLeft(lValue, iShiftBits) {
            return (lValue << iShiftBits) | (lValue >>> (32 - iShiftBits));
        }
        function addUnsigned(lX, lY) {
            var lX4 = lX & 0x40000000;
            var lY4 = lY & 0x40000000;
            var lX8 = lX & 0x80000000;
            var lY8 = lY & 0x80000000;
            var lResult = (lX & 0x3fffffff) + (lY & 0x3fffffff);
            if (lX4 & lY4) return lResult ^ 0x80000000 ^ lX8 ^ lY8;
            if (lX4 | lY4) {
                if (lResult & 0x40000000) return lResult ^ 0xc0000000 ^ lX8 ^ lY8;
                return lResult ^ 0x40000000 ^ lX8 ^ lY8;
            }
            return lResult ^ lX8 ^ lY8;
        }
        function F(x, y, z) { return (x & y) | ((~x) & z); }
        function G(x, y, z) { return (x & z) | (y & (~z)); }
        function H(x, y, z) { return x ^ y ^ z; }
        function I(x, y, z) { return y ^ (x | (~z)); }
        function FF(a, b, c, d, x, s, ac) {
            a = addUnsigned(a, addUnsigned(addUnsigned(F(b, c, d), x), ac));
            return addUnsigned(rotateLeft(a, s), b);
        }
        function GG(a, b, c, d, x, s, ac) {
            a = addUnsigned(a, addUnsigned(addUnsigned(G(b, c, d), x), ac));
            return addUnsigned(rotateLeft(a, s), b);
        }
        function HH(a, b, c, d, x, s, ac) {
            a = addUnsigned(a, addUnsigned(addUnsigned(H(b, c, d), x), ac));
            return addUnsigned(rotateLeft(a, s), b);
        }
        function II(a, b, c, d, x, s, ac) {
            a = addUnsigned(a, addUnsigned(addUnsigned(I(b, c, d), x), ac));
            return addUnsigned(rotateLeft(a, s), b);
        }
        function convertToWordArray(string) {
            var lWordCount;
            var lMessageLength = string.length;
            var lNumberOfWords_temp1 = lMessageLength + 8;
            var lNumberOfWords_temp2 = (lNumberOfWords_temp1 - (lNumberOfWords_temp1 % 64)) / 64;
            var lNumberOfWords = (lNumberOfWords_temp2 + 1) * 16;
            var lWordArray = Array(lNumberOfWords - 1);
            var lBytePosition = 0;
            var lByteCount = 0;
            while (lByteCount < lMessageLength) {
                lWordCount = (lByteCount - (lByteCount % 4)) / 4;
                lBytePosition = (lByteCount % 4) * 8;
                lWordArray[lWordCount] = (lWordArray[lWordCount] | (string.charCodeAt(lByteCount) << lBytePosition));
                lByteCount++;
            }
            lWordCount = (lByteCount - (lByteCount % 4)) / 4;
            lBytePosition = (lByteCount % 4) * 8;
            lWordArray[lWordCount] = lWordArray[lWordCount] | (0x80 << lBytePosition);
            lWordArray[lNumberOfWords - 2] = lMessageLength << 3;
            lWordArray[lNumberOfWords - 1] = lMessageLength >>> 29;
            return lWordArray;
        }
        function wordToHex(lValue) {
            var WordToHexValue = '', WordToHexValue_temp = '', lByte, lCount;
            for (lCount = 0; lCount <= 3; lCount++) {
                lByte = (lValue >>> (lCount * 8)) & 255;
                WordToHexValue_temp = '0' + lByte.toString(16);
                WordToHexValue = WordToHexValue + WordToHexValue_temp.substr(WordToHexValue_temp.length - 2, 2);
            }
            return WordToHexValue;
        }
        function utf8Encode(string) {
            string = (string || '').replace(/\r\n/g, '\n');
            var utftext = '';
            for (var n = 0; n < string.length; n++) {
                var c = string.charCodeAt(n);
                if (c < 128) {
                    utftext += String.fromCharCode(c);
                } else if (c > 127 && c < 2048) {
                    utftext += String.fromCharCode((c >> 6) | 192);
                    utftext += String.fromCharCode((c & 63) | 128);
                } else {
                    utftext += String.fromCharCode((c >> 12) | 224);
                    utftext += String.fromCharCode(((c >> 6) & 63) | 128);
                    utftext += String.fromCharCode((c & 63) | 128);
                }
            }
            return utftext;
        }
        var x = convertToWordArray(utf8Encode(string));
        var k, AA, BB, CC, DD, a, b, c, d;
        var S11 = 7, S12 = 12, S13 = 17, S14 = 22;
        var S21 = 5, S22 = 9, S23 = 14, S24 = 20;
        var S31 = 4, S32 = 11, S33 = 16, S34 = 23;
        var S41 = 6, S42 = 10, S43 = 15, S44 = 21;
        a = 0x67452301; b = 0xefcdab89; c = 0x98badcfe; d = 0x10325476;
        for (k = 0; k < x.length; k += 16) {
            AA = a; BB = b; CC = c; DD = d;
            a = FF(a, b, c, d, x[k + 0], S11, 0xd76aa478);
            d = FF(d, a, b, c, x[k + 1], S12, 0xe8c7b756);
            c = FF(c, d, a, b, x[k + 2], S13, 0x242070db);
            b = FF(b, c, d, a, x[k + 3], S14, 0xc1bdceee);
            a = FF(a, b, c, d, x[k + 4], S11, 0xf57c0faf);
            d = FF(d, a, b, c, x[k + 5], S12, 0x4787c62a);
            c = FF(c, d, a, b, x[k + 6], S13, 0xa8304613);
            b = FF(b, c, d, a, x[k + 7], S14, 0xfd469501);
            a = FF(a, b, c, d, x[k + 8], S11, 0x698098d8);
            d = FF(d, a, b, c, x[k + 9], S12, 0x8b44f7af);
            c = FF(c, d, a, b, x[k + 10], S13, 0xffff5bb1);
            b = FF(b, c, d, a, x[k + 11], S14, 0x895cd7be);
            a = FF(a, b, c, d, x[k + 12], S11, 0x6b901122);
            d = FF(d, a, b, c, x[k + 13], S12, 0xfd987193);
            c = FF(c, d, a, b, x[k + 14], S13, 0xa679438e);
            b = FF(b, c, d, a, x[k + 15], S14, 0x49b40821);
            a = GG(a, b, c, d, x[k + 1], S21, 0xf61e2562);
            d = GG(d, a, b, c, x[k + 6], S22, 0xc040b340);
            c = GG(c, d, a, b, x[k + 11], S23, 0x265e5a51);
            b = GG(b, c, d, a, x[k + 0], S24, 0xe9b6c7aa);
            a = GG(a, b, c, d, x[k + 5], S21, 0xd62f105d);
            d = GG(d, a, b, c, x[k + 10], S22, 0x2441453);
            c = GG(c, d, a, b, x[k + 15], S23, 0xd8a1e681);
            b = GG(b, c, d, a, x[k + 4], S24, 0xe7d3fbc8);
            a = GG(a, b, c, d, x[k + 9], S21, 0x21e1cde6);
            d = GG(d, a, b, c, x[k + 14], S22, 0xc33707d6);
            c = GG(c, d, a, b, x[k + 3], S23, 0xf4d50d87);
            b = GG(b, c, d, a, x[k + 8], S24, 0x455a14ed);
            a = GG(a, b, c, d, x[k + 13], S21, 0xa9e3e905);
            d = GG(d, a, b, c, x[k + 2], S22, 0xfcefa3f8);
            c = GG(c, d, a, b, x[k + 7], S23, 0x676f02d9);
            b = GG(b, c, d, a, x[k + 12], S24, 0x8d2a4c8a);
            a = HH(a, b, c, d, x[k + 5], S31, 0xfffa3942);
            d = HH(d, a, b, c, x[k + 8], S32, 0x8771f681);
            c = HH(c, d, a, b, x[k + 11], S33, 0x6d9d6122);
            b = HH(b, c, d, a, x[k + 14], S34, 0xfde5380c);
            a = HH(a, b, c, d, x[k + 1], S31, 0xa4beea44);
            d = HH(d, a, b, c, x[k + 4], S32, 0x4bdecfa9);
            c = HH(c, d, a, b, x[k + 7], S33, 0xf6bb4b60);
            b = HH(b, c, d, a, x[k + 10], S34, 0xbebfbc70);
            a = HH(a, b, c, d, x[k + 13], S31, 0x289b7ec6);
            d = HH(d, a, b, c, x[k + 0], S32, 0xeaa127fa);
            c = HH(c, d, a, b, x[k + 3], S33, 0xd4ef3085);
            b = HH(b, c, d, a, x[k + 6], S34, 0x4881d05);
            a = HH(a, b, c, d, x[k + 9], S31, 0xd9d4d039);
            d = HH(d, a, b, c, x[k + 12], S32, 0xe6db99e5);
            c = HH(c, d, a, b, x[k + 15], S33, 0x1fa27cf8);
            b = HH(b, c, d, a, x[k + 2], S34, 0xc4ac5665);
            a = II(a, b, c, d, x[k + 0], S41, 0xf4292244);
            d = II(d, a, b, c, x[k + 7], S42, 0x432aff97);
            c = II(c, d, a, b, x[k + 14], S43, 0xab9423a7);
            b = II(b, c, d, a, x[k + 5], S44, 0xfc93a039);
            a = II(a, b, c, d, x[k + 12], S41, 0x655b59c3);
            d = II(d, a, b, c, x[k + 3], S42, 0x8f0ccc92);
            c = II(c, d, a, b, x[k + 10], S43, 0xffeff47d);
            b = II(b, c, d, a, x[k + 1], S44, 0x85845dd1);
            a = II(a, b, c, d, x[k + 8], S41, 0x6fa87e4f);
            d = II(d, a, b, c, x[k + 15], S42, 0xfe2ce6e0);
            c = II(c, d, a, b, x[k + 6], S43, 0xa3014314);
            b = II(b, c, d, a, x[k + 13], S44, 0x4e0811a1);
            a = II(a, b, c, d, x[k + 4], S41, 0xf7537e82);
            d = II(d, a, b, c, x[k + 11], S42, 0xbd3af235);
            c = II(c, d, a, b, x[k + 2], S43, 0x2ad7d2bb);
            b = II(b, c, d, a, x[k + 9], S44, 0xeb86d391);
            a = addUnsigned(a, AA);
            b = addUnsigned(b, BB);
            c = addUnsigned(c, CC);
            d = addUnsigned(d, DD);
        }
        return (wordToHex(a) + wordToHex(b) + wordToHex(c) + wordToHex(d)).toLowerCase();
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
                try {
                    target.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
                } catch (scrollErr) {}
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
                try {
                    matchBtn.scrollIntoView({ behavior: 'auto', block: 'nearest', inline: 'center' });
                } catch (scrollErr) {}
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

        // Camera card header click to expand/collapse (ignoring action buttons/links)
        document.addEventListener('click', function (e) {
            var header = e.target.closest('.cv-camera-card__header');
            if (!header) return;
            // Ignore clicks on buttons, links, inputs, badges with actions
            if (e.target.closest('button, a, input, select, textarea, label')) return;

            var targetSelector = header.getAttribute('data-bs-target');
            var collapseEl = targetSelector ? document.querySelector(targetSelector) : null;
            if (collapseEl && window.bootstrap && window.bootstrap.Collapse) {
                var bsCollapse = window.bootstrap.Collapse.getOrCreateInstance(collapseEl);
                bsCollapse.toggle();
            }
        });

        // Sync aria-expanded and .collapsed state on camera card header
        document.addEventListener('show.bs.collapse', function (e) {
            if (e.target.classList.contains('cv-camera-card__collapse')) {
                var card = e.target.closest('.cv-camera-card');
                var header = card ? card.querySelector('.cv-camera-card__header') : null;
                if (header) {
                    header.setAttribute('aria-expanded', 'true');
                    header.classList.remove('collapsed');
                }
            }
        });
        document.addEventListener('hide.bs.collapse', function (e) {
            if (e.target.classList.contains('cv-camera-card__collapse')) {
                var card = e.target.closest('.cv-camera-card');
                var header = card ? card.querySelector('.cv-camera-card__header') : null;
                if (header) {
                    header.setAttribute('aria-expanded', 'false');
                    header.classList.add('collapsed');
                }
            }
        });

        // Add new camera handler
        var formAddCamera = document.getElementById('form-add-camera');
        var modalAddCameraEl = document.getElementById('addCameraModal');
        var errAddCamera = document.getElementById('add-camera-error');
        var btnSubmitAddCamera = document.getElementById('btn-submit-add-camera');
        var spinnerAddCamera = document.getElementById('spinner-add-camera');
        var inputCameraLabel = document.getElementById('new_camera_label');
        var inputCameraLocation = document.getElementById('new_camera_location');
        var btnRegenCameraId = document.getElementById('btn-regen-camera-id');
        var isLocationManuallyEdited = false;

        if (inputCameraLocation) {
            inputCameraLocation.addEventListener('input', function () {
                isLocationManuallyEdited = inputCameraLocation.value.trim().length > 0;
            });
        }

        if (inputCameraLabel && inputCameraLocation) {
            inputCameraLabel.addEventListener('input', function () {
                if (!isLocationManuallyEdited) {
                    var val = inputCameraLabel.value.trim();
                    inputCameraLocation.value = val ? md5(val) : '';
                }
            });
        }

        if (btnRegenCameraId && inputCameraLabel && inputCameraLocation) {
            btnRegenCameraId.addEventListener('click', function () {
                var val = inputCameraLabel.value.trim();
                inputCameraLocation.value = val ? md5(val) : '';
                isLocationManuallyEdited = false;
                inputCameraLocation.focus();
            });
        }

        if (modalAddCameraEl) {
            modalAddCameraEl.addEventListener('show.bs.modal', function () {
                isLocationManuallyEdited = false;
                if (errAddCamera) {
                    errAddCamera.classList.add('d-none');
                    errAddCamera.textContent = '';
                }
                if (formAddCamera) {
                    formAddCamera.reset();
                }
            });
        }

        if (formAddCamera) {
            formAddCamera.addEventListener('submit', function (e) {
                e.preventDefault();
                if (errAddCamera) {
                    errAddCamera.classList.add('d-none');
                    errAddCamera.textContent = '';
                }

                var formData = new FormData(formAddCamera);
                var payload = {
                    location: (formData.get('location') || '').trim(),
                    label: (formData.get('label') || '').trim(),
                    video_path: (formData.get('video_path') || '').trim(),
                    model_type: formData.get('model_type'),
                    weights_path: (formData.get('weights_path') || '').trim(),
                    confidence: formData.get('confidence'),
                    video_fps: formData.get('video_fps')
                };

                if (!payload.location) {
                    if (errAddCamera) {
                        errAddCamera.textContent = t('Camera ID is required');
                        errAddCamera.classList.remove('d-none');
                    }
                    return;
                }

                if (!payload.video_path) {
                    if (errAddCamera) {
                        errAddCamera.textContent = t('Video source is required');
                        errAddCamera.classList.remove('d-none');
                    }
                    return;
                }

                if (btnSubmitAddCamera) btnSubmitAddCamera.disabled = true;
                if (spinnerAddCamera) spinnerAddCamera.classList.remove('d-none');

                fetch('/settings/api/detections/add', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify(payload)
                })
                    .then(function (res) { return res.json(); })
                    .then(function (data) {
                        if (data && data.ok) {
                            showToast(data.message || t('Camera added successfully'), 'success');
                            if (modalAddCameraEl) {
                                var modalInst = bootstrap.Modal.getInstance(modalAddCameraEl);
                                if (modalInst) modalInst.hide();
                            }
                            // Reload settings on detections tab
                            window.location.hash = '#pills-detections';
                            window.location.reload();
                        } else {
                            var msg = (data && data.error) ? data.error : t('Failed to add camera');
                            if (errAddCamera) {
                                errAddCamera.textContent = msg;
                                errAddCamera.classList.remove('d-none');
                            } else {
                                showToast(msg, 'danger');
                            }
                        }
                    })
                    .catch(function (err) {
                        var msg = (err && err.message) ? err.message : t('Failed to add camera');
                        if (errAddCamera) {
                            errAddCamera.textContent = msg;
                            errAddCamera.classList.remove('d-none');
                        } else {
                            showToast(msg, 'danger');
                        }
                    })
                    .finally(function () {
                        if (btnSubmitAddCamera) btnSubmitAddCamera.disabled = false;
                        if (spinnerAddCamera) spinnerAddCamera.classList.add('d-none');
                    });
            });
        }

        // Delete camera handler
        document.addEventListener('click', async function (e) {
            var btnDelete = e.target.closest('.btn-delete-camera');
            if (!btnDelete) return;

            e.preventDefault();
            e.stopPropagation();

            var camId = btnDelete.dataset.cameraId;
            var camLabel = btnDelete.dataset.cameraLabel || camId;
            var confirmMsg = (window.trans ? window.trans('Are you sure you want to delete camera "{name}"?', {name: camLabel}) : null)
                || ('Are you sure you want to delete camera "' + camLabel + '"?');

            var confirmed = typeof window.appConfirm === 'function'
                ? await window.appConfirm({
                    title: window.trans ? window.trans('Delete camera') : 'Delete camera',
                    message: confirmMsg,
                    confirmText: window.trans ? window.trans('Delete') : 'Delete',
                    tone: 'danger',
                })
                : confirm(confirmMsg);

            if (!confirmed) {
                return;
            }

            btnDelete.disabled = true;
            fetch('/settings/api/detections/' + encodeURIComponent(camId) + '/delete', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
                .then(function (res) { return res.json(); })
                .then(function (data) {
                    if (data && data.ok) {
                        showToast(data.message || t('Camera deleted successfully'), 'success');
                        var card = btnDelete.closest('.cv-camera-card');
                        if (card) {
                            card.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                            card.style.opacity = '0';
                            card.style.transform = 'scale(0.95)';
                            setTimeout(function () {
                                card.remove();
                            }, 300);
                        } else {
                            window.location.reload();
                        }
                    } else {
                        showToast((data && data.error) ? data.error : t('Failed to delete camera'), 'danger');
                        btnDelete.disabled = false;
                    }
                })
                .catch(function (err) {
                    showToast((err && err.message) ? err.message : t('Failed to delete camera'), 'danger');
                    btnDelete.disabled = false;
                });
        });

        // --- Custom Fields Management (Add / Delete) ---
        var modalAddCustomFieldEl = document.getElementById('addCustomFieldModal');
        var formAddCustomField = document.getElementById('form-add-custom-field');
        var errAddCustomField = document.getElementById('add-custom-field-error');
        var btnSubmitAddCustomField = document.getElementById('btn-submit-add-custom-field');
        var spinnerAddCustomField = document.getElementById('spinner-add-custom-field');
        var selectFieldScope = document.getElementById('new_field_scope');
        var selectFieldType = document.getElementById('new_field_type');
        var rowFieldOptions = document.getElementById('row-field-options');
        var inputFieldLabel = document.getElementById('new_field_label');
        var inputFieldName = document.getElementById('new_field_name');
        var btnRegenFieldId = document.getElementById('btn-regen-field-id');
        var isFieldNameManuallyEdited = false;

        // Transliterate and slugify string into valid identifier (Latin letters, digits, underscores)
        function slugifyIdentifier(text) {
            if (!text) return '';
            var ruMap = {
                'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e', 'ж': 'zh',
                'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o',
                'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
                'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
            };
            var str = String(text).toLowerCase().trim();
            var result = '';
            for (var i = 0; i < str.length; i++) {
                var ch = str[i];
                if (ruMap.hasOwnProperty(ch)) {
                    result += ruMap[ch];
                } else if (/[a-z0-9]/.test(ch)) {
                    result += ch;
                } else if (/[\s\-_.,/\\|:;+*!@#$%^&()\[\]{}<>=~`'"]/.test(ch)) {
                    result += '_';
                }
            }
            result = result.replace(/_+/g, '_').replace(/^_+|_+$/g, '');
            return result;
        }

        // Auto-generate Field ID from Display Label when adding field
        if (inputFieldLabel && inputFieldName) {
            inputFieldLabel.addEventListener('input', function () {
                if (!isFieldNameManuallyEdited) {
                    inputFieldName.value = slugifyIdentifier(inputFieldLabel.value);
                }
            });

            inputFieldName.addEventListener('input', function () {
                isFieldNameManuallyEdited = (inputFieldName.value.trim().length > 0);
            });
        }

        if (btnRegenFieldId && inputFieldLabel && inputFieldName) {
            btnRegenFieldId.addEventListener('click', function () {
                inputFieldName.value = slugifyIdentifier(inputFieldLabel.value);
                isFieldNameManuallyEdited = false;
                inputFieldName.focus();
            });
        }

        // Toggle options visibility based on field type in Add modal
        if (selectFieldType && rowFieldOptions) {
            selectFieldType.addEventListener('change', function () {
                if (selectFieldType.value === 'select') {
                    rowFieldOptions.classList.remove('d-none');
                    var optTextarea = rowFieldOptions.querySelector('textarea');
                    if (optTextarea) optTextarea.focus();
                } else {
                    rowFieldOptions.classList.add('d-none');
                }
            });
        }

        // Toggle options visibility when changing type inside existing custom field cards
        document.addEventListener('change', function (e) {
            var typeSelect = e.target.closest('.cv-custom-field-type-select');
            if (!typeSelect) return;

            var card = typeSelect.closest('.cv-custom-field-card');
            if (!card) return;

            var isSelect = (typeSelect.value === 'select');
            var optionsRow = card.querySelector('.cv-custom-field-options-row');
            var optionsInput = card.querySelector('.cv-custom-field-options-input');
            var typeBadge = card.querySelector('.cv-custom-field-badge-type');
            var iconBox = card.querySelector('.cv-custom-field-card__icon-box');

            if (typeBadge) {
                typeBadge.textContent = typeSelect.value;
            }

            if (iconBox) {
                var ftype = typeSelect.value;
                if (ftype === 'number') {
                    iconBox.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" fill="currentColor" class="bi bi-123 text-success" viewBox="0 0 16 16"><path d="M2.873 11.297V4.142H1.699L0 5.379v1.137l1.64-1.18h.06v5.961zm3.213-5.09v-.063c0-.618.44-1.169 1.196-1.169.676 0 1.174.44 1.174 1.106 0 .624-.42 1.101-.807 1.526L4.99 10.553v.744h4.78v-.99H6.643v-.069L8.41 8.252c.65-.724 1.237-1.332 1.237-2.27C9.646 4.849 8.723 4 7.308 4c-1.573 0-2.36 1.064-2.36 2.15v.057zm6.559 1.883h.786c.823 0 1.374.481 1.379 1.179.01.707-.55 1.216-1.421 1.21-.77-.005-1.326-.419-1.379-.953h-1.095c.042 1.053.938 1.918 2.464 1.918 1.478 0 2.642-.839 2.62-2.144-.02-1.143-.922-1.651-1.551-1.714v-.063c.535-.09 1.347-.66 1.326-1.678-.026-1.053-.933-1.855-2.359-1.845-1.5.005-2.317.88-2.348 1.898h1.116c.032-.498.498-.944 1.206-.944.703 0 1.206.435 1.206 1.07.005.64-.504 1.106-1.2 1.106h-.75z"/></svg>';
                } else if (ftype === 'textarea') {
                    iconBox.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" fill="currentColor" class="bi bi-text-paragraph text-info" viewBox="0 0 16 16"><path fill-rule="evenodd" d="M2 12.5a.5.5 0 0 1 .5-.5h7a.5.5 0 0 1 0 1h-7a.5.5 0 0 1-.5-.5m0-3a.5.5 0 0 1 .5-.5h11a.5.5 0 0 1 0 1h-11a.5.5 0 0 1-.5-.5m0-3a.5.5 0 0 1 .5-.5h11a.5.5 0 0 1 0 1h-11a.5.5 0 0 1-.5-.5m4-3a.5.5 0 0 1 .5-.5h7a.5.5 0 0 1 0 1h-7a.5.5 0 0 1-.5-.5"/></svg>';
                } else if (ftype === 'date' || ftype === 'datetime-local') {
                    iconBox.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" fill="currentColor" class="bi bi-calendar3 text-warning" viewBox="0 0 16 16"><path d="M14 0H2a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V2a2 2 0 0 0-2-2M1 3.857C1 3.384 1.448 3 2 3h12c.552 0 1 .384 1 .857v10.286c0 .473-.448.857-1 .857H2c-.552 0-1-.384-1-.857z"/><path d="M6.5 7a1 1 0 1 0 0-2 1 1 0 0 0 0 2m3 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2m3 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2m-9 3a1 1 0 1 0 0-2 1 1 0 0 0 0 2m3 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2m3 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2m3 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2m-9 3a1 1 0 1 0 0-2 1 1 0 0 0 0 2m3 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2m3 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2"/></svg>';
                } else if (ftype === 'select') {
                    iconBox.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" fill="currentColor" class="bi bi-menu-button-wide text-primary" viewBox="0 0 16 16"><path d="M0 1.5A1.5 1.5 0 0 1 1.5 0h13A1.5 1.5 0 0 1 16 1.5v2A1.5 1.5 0 0 1 14.5 5h-13A1.5 1.5 0 0 1 0 3.5zM1.5 1a.5.5 0 0 0-.5.5v2a.5.5 0 0 0 .5.5h13a.5.5 0 0 0 .5-.5v-2a.5.5 0 0 0-.5-.5z"/><path d="M2 2.5a.5.5 0 0 1 .5-.5h3a.5.5 0 0 1 0 1h-3a.5.5 0 0 1-.5-.5m10.823.323-.396-.396A.25.25 0 0 1 12.604 2h.792a.25.25 0 0 1 .177.427l-.396.396a.25.25 0 0 1-.354 0M0 8a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2zm1 3v2a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2zm14-1V8a1 1 0 0 0-1-1H2a1 1 0 0 0-1 1v2zM2 8.5a.5.5 0 0 1 .5-.5h9a.5.5 0 0 1 0 1h-9a.5.5 0 0 1-.5-.5m0 4a.5.5 0 0 1 .5-.5h6a.5.5 0 0 1 0 1h-6a.5.5 0 0 1-.5-.5"/></svg>';
                } else {
                    iconBox.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" fill="currentColor" class="bi bi-fonts text-primary" viewBox="0 0 16 16"><path d="M12.258 3h-8.51l-.083 2.46h.479c.26-1.544.758-1.783 2.693-1.845l.424-.013v7.827c0 .663-.144.82-1.3.923v.52h4.082v-.52c-1.162-.103-1.306-.26-1.306-.923V3.602l.431.013c1.934.062 2.434.301 2.693 1.846h.479z"/></svg>';
                }
            }

            if (optionsRow) {
                if (isSelect) {
                    optionsRow.classList.remove('d-none');
                    if (optionsInput) {
                        optionsInput.disabled = false;
                        optionsInput.focus();
                    }
                } else {
                    optionsRow.classList.add('d-none');
                    if (optionsInput) {
                        optionsInput.disabled = true;
                    }
                }
            }
        });

        // Live update card header title when editing label
        document.addEventListener('input', function (e) {
            var labelInput = e.target.closest('.cv-custom-field-input-label');
            if (!labelInput) return;

            var card = labelInput.closest('.cv-custom-field-card');
            if (!card) return;

            var headerLabel = card.querySelector('.cv-custom-field-header-label');
            if (headerLabel) {
                headerLabel.textContent = labelInput.value.trim() || card.dataset.fieldName || '';
            }
        });

        // Open Add Custom Field Modal on button click
        document.addEventListener('click', function (e) {
            var btnAdd = e.target.closest('.btn-add-custom-field');
            if (!btnAdd) return;

            e.preventDefault();
            var scope = btnAdd.dataset.scope || 'global';
            var location = btnAdd.dataset.location || '';
            isFieldNameManuallyEdited = false;

            if (formAddCustomField) {
                formAddCustomField.reset();
            }
            if (errAddCustomField) {
                errAddCustomField.classList.add('d-none');
                errAddCustomField.textContent = '';
            }
            if (rowFieldOptions) {
                rowFieldOptions.classList.add('d-none');
            }

            if (selectFieldScope) {
                if (scope === 'detection' && location) {
                    var targetVal = 'detection:' + location;
                    var matchOption = Array.from(selectFieldScope.options).find(function (opt) {
                        return opt.value === targetVal;
                    });
                    if (matchOption) {
                        selectFieldScope.value = targetVal;
                    } else {
                        selectFieldScope.value = 'global';
                    }
                } else {
                    selectFieldScope.value = 'global';
                }
            }

            if (modalAddCustomFieldEl) {
                var modalInst = bootstrap.Modal.getOrCreateInstance(modalAddCustomFieldEl);
                modalInst.show();
                setTimeout(function () {
                    if (inputFieldLabel) inputFieldLabel.focus();
                }, 200);
            }
        });

        // Submit Add Custom Field
        if (formAddCustomField) {
            formAddCustomField.addEventListener('submit', function (e) {
                e.preventDefault();
                if (errAddCustomField) {
                    errAddCustomField.classList.add('d-none');
                    errAddCustomField.textContent = '';
                }

                var formData = new FormData(formAddCustomField);
                var scopeTarget = formData.get('scope_target') || 'global';
                var scope = 'global';
                var location = '';
                if (scopeTarget.indexOf('detection:') === 0) {
                    scope = 'detection';
                    location = scopeTarget.substring('detection:'.length);
                }

                var name = (formData.get('name') || '').trim();
                var label = (formData.get('label') || '').trim();
                var type = formData.get('type') || 'text';
                var options = formData.get('options') || '';
                var defaultValue = (formData.get('default_value') || '').trim();

                if (!name) {
                    if (errAddCustomField) {
                        errAddCustomField.textContent = t('Field name (ID) is required');
                        errAddCustomField.classList.remove('d-none');
                    }
                    return;
                }

                if (!/^[a-zA-Z0-9_]+$/.test(name)) {
                    if (errAddCustomField) {
                        errAddCustomField.textContent = t('Invalid field ID. Use Latin letters, digits, and underscores.');
                        errAddCustomField.classList.remove('d-none');
                    }
                    return;
                }

                var payload = {
                    scope: scope,
                    location: location,
                    name: name,
                    label: label || name,
                    type: type,
                    options: options,
                    default_value: defaultValue
                };

                if (btnSubmitAddCustomField) btnSubmitAddCustomField.disabled = true;
                if (spinnerAddCustomField) spinnerAddCustomField.classList.remove('d-none');

                fetch('/settings/api/custom_fields/add', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify(payload)
                })
                    .then(function (res) { return res.json(); })
                    .then(function (data) {
                        if (data && data.ok) {
                            showToast(data.message || t('Field added successfully'), 'success');
                            if (modalAddCustomFieldEl) {
                                var modalInst = bootstrap.Modal.getInstance(modalAddCustomFieldEl);
                                if (modalInst) modalInst.hide();
                            }
                            if (scope === 'detection') {
                                window.location.hash = '#pills-detections';
                            } else {
                                window.location.hash = '#pills-form';
                            }
                            window.location.reload();
                        } else {
                            var msg = (data && data.error) ? data.error : t('Failed to add field');
                            if (errAddCustomField) {
                                errAddCustomField.textContent = msg;
                                errAddCustomField.classList.remove('d-none');
                            } else {
                                showToast(msg, 'danger');
                            }
                        }
                    })
                    .catch(function (err) {
                        var msg = (err && err.message) ? err.message : t('Failed to add field');
                        if (errAddCustomField) {
                            errAddCustomField.textContent = msg;
                            errAddCustomField.classList.remove('d-none');
                        } else {
                            showToast(msg, 'danger');
                        }
                    })
                    .finally(function () {
                        if (btnSubmitAddCustomField) btnSubmitAddCustomField.disabled = false;
                        if (spinnerAddCustomField) spinnerAddCustomField.classList.add('d-none');
                    });
            });
        }

        // Delete Custom Field Handler
        document.addEventListener('click', async function (e) {
            var btnDelete = e.target.closest('.btn-delete-custom-field');
            if (!btnDelete) return;

            e.preventDefault();
            e.stopPropagation();

            var fieldName = btnDelete.dataset.fieldName;
            var fieldLabel = btnDelete.dataset.fieldLabel || fieldName;
            var scope = btnDelete.dataset.scope || 'global';
            var location = btnDelete.dataset.location || '';

            var confirmMsg = (window.trans ? window.trans('Are you sure you want to delete field "{name}"?', {name: fieldLabel}) : null)
                || ('Are you sure you want to delete field "' + fieldLabel + '"?');

            var confirmed = typeof window.appConfirm === 'function'
                ? await window.appConfirm({
                    title: window.trans ? window.trans('Delete field') : 'Delete field',
                    message: confirmMsg,
                    confirmText: window.trans ? window.trans('Delete') : 'Delete',
                    tone: 'danger',
                })
                : confirm(confirmMsg);

            if (!confirmed) {
                return;
            }

            btnDelete.disabled = true;
            fetch('/settings/api/custom_fields/delete', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({
                    scope: scope,
                    location: location,
                    name: fieldName
                })
            })
                .then(function (res) { return res.json(); })
                .then(function (data) {
                    if (data && data.ok) {
                        showToast(data.message || t('Field deleted successfully'), 'success');
                        var card = btnDelete.closest('.cv-custom-field-card');
                        if (card) {
                            var section = card.closest('.cv-custom-fields-section');
                            card.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                            card.style.opacity = '0';
                            card.style.transform = 'scale(0.95)';
                            setTimeout(function () {
                                card.remove();
                                if (section) {
                                    var remaining = section.querySelectorAll('.cv-custom-field-card');
                                    var countBadge = section.querySelector('.cv-form-section__header .badge.font-monospace');
                                    if (countBadge) {
                                        countBadge.textContent = remaining.length;
                                    }
                                }
                            }, 300);
                        } else {
                            window.location.reload();
                        }
                    } else {
                        showToast((data && data.error) ? data.error : t('Failed to delete field'), 'danger');
                        btnDelete.disabled = false;
                    }
                })
                .catch(function (err) {
                    showToast((err && err.message) ? err.message : t('Failed to delete field'), 'danger');
                    btnDelete.disabled = false;
                });
        });

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
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initSettings);
    } else {
        initSettings();
    }
})();
