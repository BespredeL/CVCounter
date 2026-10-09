/**
 * Computer Vision Counter (CVCounter)
 * Reports saved media viewer (images and recordings) with lightbox navigation.
 *
 * Developed by: Aleksandr Kireev
 * Created: 09.10.2026
 * Website: https://bespredel.name
 */

(function () {
    "use strict";

    const root = document.getElementById("reports-media");
    if (!root) return;

    const modalEl = document.getElementById("reportsMediaModal");
    if (!modalEl || typeof bootstrap === "undefined") return;

    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    const titleEl = document.getElementById("reportsMediaModalLabel");
    const metaEl = document.getElementById("reportsMediaModalMeta");
    const counterEl = document.getElementById("reportsMediaModalCounter");
    const imgEl = document.getElementById("reportsMediaModalImage");
    const videoEl = document.getElementById("reportsMediaModalVideo");
    const loadingEl = document.getElementById("reportsMediaModalLoading");
    const loadingTextEl = document.getElementById("reportsMediaModalLoadingText");
    const errorEl = document.getElementById("reportsMediaModalError");
    const footerEl = document.getElementById("reportsMediaModalFooter");
    const downloadEl = document.getElementById("reportsMediaModalDownload");
    const btnPrev = document.getElementById("reportsMediaBtnPrev");
    const btnNext = document.getElementById("reportsMediaBtnNext");
    const speedWrap = document.getElementById("reportsMediaVideoSpeedWrap");

    const i18nPreparing = root.dataset.i18nPreparing || "Preparing video for playback…";
    const i18nPlayError = root.dataset.i18nPlayError || "This video cannot be played in the browser. You can download the original file.";

    let pendingVideoUrl = null;
    let currentMediaList = [];
    let currentIndex = -1;

    function getMediaItems() {
        /* Collect visible tab's items first, or all items */
        const activePane = root.querySelector(".tab-pane.active");
        if (activePane) {
            const tabItems = Array.from(activePane.querySelectorAll("[data-media-url]"));
            if (tabItems.length > 0) return tabItems;
        }
        return Array.from(root.querySelectorAll("[data-media-url]"));
    }

    function setLoading(visible, text) {
        if (!loadingEl) return;
        loadingEl.classList.toggle("d-none", !visible);
        if (loadingTextEl) loadingTextEl.textContent = text || "";
    }

    function setError(message) {
        if (!errorEl) return;
        if (!message) {
            errorEl.classList.add("d-none");
            errorEl.textContent = "";
            return;
        }
        errorEl.textContent = message;
        errorEl.classList.remove("d-none");
    }

    function setDownload(url) {
        if (!downloadEl) return;
        if (!url) {
            downloadEl.classList.add("d-none");
            downloadEl.removeAttribute("href");
            return;
        }
        downloadEl.href = url;
        downloadEl.classList.remove("d-none");
    }

    function resetMedia() {
        pendingVideoUrl = null;
        setLoading(false);
        setError("");
        setDownload(null);

        if (imgEl) {
            imgEl.classList.add("d-none");
            imgEl.removeAttribute("src");
            imgEl.alt = "";
        }
        if (videoEl) {
            videoEl.pause();
            videoEl.removeAttribute("src");
            while (videoEl.firstChild) {
                videoEl.removeChild(videoEl.firstChild);
            }
            videoEl.load();
            videoEl.classList.add("d-none");
            videoEl.playbackRate = 1.0;
        }

        if (speedWrap) {
            speedWrap.classList.add("d-none");
            speedWrap.querySelectorAll(".reports-media-speed-btn").forEach((btn) => {
                btn.classList.toggle("active", btn.dataset.speed === "1.0");
            });
        }
    }

    function attachVideoSource(url) {
        while (videoEl.firstChild) {
            videoEl.removeChild(videoEl.firstChild);
        }
        const source = document.createElement("source");
        source.src = url;
        source.type = url.includes(".webm") ? "video/webm" : "video/mp4";
        videoEl.appendChild(source);
        videoEl.src = url;
        videoEl.classList.remove("d-none");
        videoEl.load();
        if (speedWrap) {
            speedWrap.classList.remove("d-none");
        }
    }

    function updateNavButtons() {
        if (btnPrev) {
            btnPrev.disabled = currentIndex <= 0;
            btnPrev.classList.toggle("opacity-25", currentIndex <= 0);
        }
        if (btnNext) {
            btnNext.disabled = currentIndex >= currentMediaList.length - 1;
            btnNext.classList.toggle("opacity-25", currentIndex >= currentMediaList.length - 1);
        }
        if (counterEl) {
            if (currentMediaList.length > 1 && currentIndex >= 0) {
                counterEl.textContent = `${currentIndex + 1} / ${currentMediaList.length}`;
                counterEl.classList.remove("d-none");
            } else {
                counterEl.classList.add("d-none");
            }
        }
    }

    function openMediaByIndex(index) {
        currentMediaList = getMediaItems();
        if (index < 0 || index >= currentMediaList.length) return;
        currentIndex = index;

        const btn = currentMediaList[currentIndex];
        const type = btn.dataset.mediaType;
        const url = btn.dataset.mediaUrl;
        const title = btn.dataset.mediaTitle || "";
        const meta = btn.dataset.mediaMeta || "";
        const downloadUrl = btn.dataset.mediaDownload || "";
        if (!url || !type) return;

        resetMedia();
        if (titleEl) titleEl.textContent = title;
        if (metaEl) metaEl.textContent = meta;
        setDownload(downloadUrl || (type === "image" ? url : null));
        updateNavButtons();

        if (type === "image" && imgEl) {
            imgEl.src = url;
            imgEl.alt = title;
            imgEl.classList.remove("d-none");
            modal.show();
            return;
        }

        if (type === "video" && videoEl) {
            pendingVideoUrl = url;
            setLoading(true, i18nPreparing);
            modal.show();
            return;
        }
    }

    /* --- Thumbnail click handler --- */
    root.addEventListener("click", (e) => {
        const btn = e.target.closest("[data-media-url]");
        if (!btn) return;
        currentMediaList = getMediaItems();
        const idx = currentMediaList.indexOf(btn);
        if (idx >= 0) {
            openMediaByIndex(idx);
        }
    });

    /* --- Lightbox navigation buttons --- */
    btnPrev?.addEventListener("click", () => {
        if (currentIndex > 0) {
            openMediaByIndex(currentIndex - 1);
        }
    });

    btnNext?.addEventListener("click", () => {
        if (currentIndex < currentMediaList.length - 1) {
            openMediaByIndex(currentIndex + 1);
        }
    });

    /* --- Keyboard navigation (ArrowLeft / ArrowRight) --- */
    window.addEventListener("keydown", (e) => {
        if (!modalEl.classList.contains("show")) return;
        if (e.target.matches("input, textarea, select")) return;

        if (e.key === "ArrowLeft") {
            if (currentIndex > 0) {
                e.preventDefault();
                openMediaByIndex(currentIndex - 1);
            }
        } else if (e.key === "ArrowRight") {
            if (currentIndex < currentMediaList.length - 1) {
                e.preventDefault();
                openMediaByIndex(currentIndex + 1);
            }
        }
    });

    /* --- Video playback speed controls --- */
    document.querySelectorAll(".reports-media-speed-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            const speed = parseFloat(btn.dataset.speed) || 1.0;
            if (videoEl) {
                videoEl.playbackRate = speed;
            }
            document.querySelectorAll(".reports-media-speed-btn").forEach((b) => {
                b.classList.toggle("active", b === btn);
            });
        });
    });

    /* --- Modal lifecycle events --- */
    modalEl.addEventListener("shown.bs.modal", () => {
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
            videoEl.classList.add("d-none");
        };

        videoEl.addEventListener("loadeddata", onReady, { once: true });
        videoEl.addEventListener("error", onError, { once: true });
        videoEl.addEventListener("canplay", onReady, { once: true });
    });

    modalEl.addEventListener("hidden.bs.modal", () => {
        resetMedia();
        currentIndex = -1;
    });
})();
