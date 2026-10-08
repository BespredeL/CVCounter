/**
 * Reports saved media viewer (images + recordings).
 * Developed by: Aleksandr Kireev — https://bespredel.name
 */

(function () {
    const root = document.getElementById('reports-media');
    if (!root) return;

    const modalEl = document.getElementById('reportsMediaModal');
    if (!modalEl || typeof bootstrap === 'undefined') return;

    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    const titleEl = document.getElementById('reportsMediaModalLabel');
    const metaEl = document.getElementById('reportsMediaModalMeta');
    const imgEl = document.getElementById('reportsMediaModalImage');
    const videoEl = document.getElementById('reportsMediaModalVideo');
    const loadingEl = document.getElementById('reportsMediaModalLoading');
    const loadingTextEl = document.getElementById('reportsMediaModalLoadingText');
    const errorEl = document.getElementById('reportsMediaModalError');
    const footerEl = document.getElementById('reportsMediaModalFooter');
    const downloadEl = document.getElementById('reportsMediaModalDownload');

    const i18nPreparing = root.dataset.i18nPreparing || 'Preparing video for playback…';
    const i18nPlayError = root.dataset.i18nPlayError
        || 'This video cannot be played in the browser. You can download the original file.';

    let pendingVideoUrl = null;

    function setLoading(visible, text) {
        if (!loadingEl) return;
        loadingEl.classList.toggle('d-none', !visible);
        if (loadingTextEl) loadingTextEl.textContent = text || '';
    }

    function setError(message) {
        if (!errorEl) return;
        if (!message) {
            errorEl.classList.add('d-none');
            errorEl.textContent = '';
            return;
        }
        errorEl.textContent = message;
        errorEl.classList.remove('d-none');
    }

    function setDownload(url) {
        if (!footerEl || !downloadEl) return;
        if (!url) {
            footerEl.classList.add('d-none');
            downloadEl.removeAttribute('href');
            return;
        }
        downloadEl.href = url;
        footerEl.classList.remove('d-none');
    }

    function resetMedia() {
        pendingVideoUrl = null;
        setLoading(false);
        setError('');
        setDownload(null);

        if (imgEl) {
            imgEl.classList.add('d-none');
            imgEl.removeAttribute('src');
            imgEl.alt = '';
        }
        if (videoEl) {
            videoEl.pause();
            videoEl.removeAttribute('src');
            while (videoEl.firstChild) {
                videoEl.removeChild(videoEl.firstChild);
            }
            videoEl.load();
            videoEl.classList.add('d-none');
        }
    }

    function attachVideoSource(url) {
        while (videoEl.firstChild) {
            videoEl.removeChild(videoEl.firstChild);
        }
        const source = document.createElement('source');
        source.src = url;
        // Server may return mp4 or webm after conversion.
        source.type = url.includes('.webm') ? 'video/webm' : 'video/mp4';
        videoEl.appendChild(source);
        videoEl.src = url;
        videoEl.classList.remove('d-none');
        videoEl.load();
    }

    function openMedia(btn) {
        const type = btn.dataset.mediaType;
        const url = btn.dataset.mediaUrl;
        const title = btn.dataset.mediaTitle || '';
        const meta = btn.dataset.mediaMeta || '';
        const downloadUrl = btn.dataset.mediaDownload || '';
        if (!url || !type) return;

        resetMedia();
        if (titleEl) titleEl.textContent = title;
        if (metaEl) metaEl.textContent = meta;
        setDownload(downloadUrl || (type === 'image' ? url : null));

        if (type === 'image' && imgEl) {
            imgEl.src = url;
            imgEl.alt = title;
            imgEl.classList.remove('d-none');
            modal.show();
            return;
        }

        if (type === 'video' && videoEl) {
            pendingVideoUrl = url;
            setLoading(true, i18nPreparing);
            modal.show();
            return;
        }
    }

    root.querySelectorAll('[data-media-url]').forEach((btn) => {
        btn.addEventListener('click', () => openMedia(btn));
    });

    modalEl.addEventListener('shown.bs.modal', () => {
        if (!pendingVideoUrl || !videoEl) return;
        const url = pendingVideoUrl;
        pendingVideoUrl = null;
        attachVideoSource(url);

        const onReady = () => {
            setLoading(false);
            videoEl.play().catch(() => {});
        };
        const onError = () => {
            setLoading(false);
            setError(i18nPlayError);
            videoEl.classList.add('d-none');
        };

        videoEl.addEventListener('loadeddata', onReady, { once: true });
        videoEl.addEventListener('error', onError, { once: true });
        // Long first-load (server-side convert): keep spinner until ready/error.
        videoEl.addEventListener('canplay', onReady, { once: true });
    });

    modalEl.addEventListener('hidden.bs.modal', () => {
        resetMedia();
    });
})();
