/**
 * Computer Vision Counter (CVCounter)
 * Reports saved media viewer (images and recordings) with lightbox navigation
 * and administrative management (deletion, bulk selection).
 *
 * Developed by: Aleksandr Kireev
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
    const downloadEl = document.getElementById("reportsMediaModalDownload");
    const modalDeleteBtn = document.getElementById("reportsMediaModalDelete");
    const btnPrev = document.getElementById("reportsMediaBtnPrev");
    const btnNext = document.getElementById("reportsMediaBtnNext");
    const speedWrap = document.getElementById("reportsMediaVideoSpeedWrap");

    const toggleSelectBtn = document.getElementById("reportsMediaToggleSelectBtn");
    const toggleSelectText = document.getElementById("reportsMediaToggleSelectText");
    const selectAllBtn = document.getElementById("reportsMediaSelectAllBtn");
    const bulkDeleteBtn = document.getElementById("reportsMediaBulkDeleteBtn");
    const selectedCountEl = document.getElementById("reportsMediaSelectedCount");

    const locationName = root.dataset.location || "";
    const isAdmin = root.dataset.isAdmin === "1";
    const bulkDeleteUrl = root.dataset.deleteUrl || `/reports/${encodeURIComponent(locationName)}/media/delete`;

    const t = (key, params) => (typeof window.trans === "function" ? window.trans(key, params) : key);

    const i18nPreparing = root.dataset.i18nPreparing || t("Preparing video for playback...");
    const i18nPlayError = root.dataset.i18nPlayError || t("This video cannot be played in the browser. You can download the original file.");

    let pendingVideoUrl = null;
    let currentMediaList = [];
    let currentIndex = -1;
    let isSelectMode = false;

    function toast(message, type = "primary") {
        if (typeof window.showToast === "function") {
            window.showToast(message, type);
        }
    }

    function getMediaItems() {
        /* Collect visible tab's items first, or all items */
        const activePane = root.querySelector(".tab-pane.active");
        if (activePane) {
            const tabItems = Array.from(activePane.querySelectorAll("[data-media-url]"));
            if (tabItems.length > 0) return tabItems;
        }
        return Array.from(root.querySelectorAll("[data-media-url]"));
    }

    function getActiveTabType() {
        const activePane = root.querySelector(".tab-pane.active");
        if (activePane && activePane.id === "tab-saved-videos") {
            return "video";
        }
        return "image";
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

    /* --- DOM Updates after deletion --- */
    function decrementCounter(selector, amount = 1) {
        const el = document.querySelector(selector);
        if (!el) return;
        const current = parseInt(el.textContent || "0", 10);
        el.textContent = Math.max(0, current - amount);
    }

    function removeMediaItemFromDOM(itemEl, mediaType) {
        if (!itemEl) return;
        const parentPane = itemEl.closest(".tab-pane");
        itemEl.remove();

        if (mediaType === "video") {
            decrementCounter("#tab-btn-videos .badge", 1);
        } else {
            decrementCounter("#tab-btn-images .badge", 1);
        }
        decrementCounter(".reports-kpi-value.text-info", 1);

        if (parentPane) {
            const remaining = parentPane.querySelectorAll(".reports-media__item");
            if (remaining.length === 0) {
                const grid = parentPane.querySelector(".reports-media__grid");
                const nav = parentPane.querySelector("nav[aria-label]");
                if (grid) grid.remove();
                if (nav) nav.remove();

                const emptyHtml = mediaType === "video"
                    ? `<div class="reports-media__empty py-5">
                            <svg xmlns="http://www.w3.org/2000/svg" width="44" height="44" fill="currentColor" viewBox="0 0 16 16" aria-hidden="true" class="bi bi-camera-video-fill"><path fill-rule="evenodd" d="M0 5a2 2 0 0 1 2-2h7.5a2 2 0 0 1 1.983 1.738l3.11-1.382A1 1 0 0 1 16 4.269v7.462a1 1 0 0 1-1.406.913l-3.111-1.382A2 2 0 0 1 9.5 13H2a2 2 0 0 1-2-2z"/></svg>
                            <div class="mt-2 text-body-secondary">${t("No saved recordings for this location.")}</div>
                       </div>`
                    : `<div class="reports-media__empty py-5">
                            <svg xmlns="http://www.w3.org/2000/svg" width="44" height="44" fill="currentColor" viewBox="0 0 16 16" aria-hidden="true" class="bi bi-images"><path d="M4.502 9a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3"/><path d="M14.002 13a2 2 0 0 1-2 2h-10a2 2 0 0 1-2-2V5A2 2 0 0 1 2 3a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v8a2 2 0 0 1-1.998 2M14 2H4a1 1 0 0 0-1 1h9.002a2 2 0 0 1 2 2v7A1 1 0 0 0 15 11V3a1 1 0 0 0-1-1M2.002 4a1 1 0 0 0-1 1v8l2.646-2.354a.5.5 0 0 1 .63-.062l2.66 1.773 3.71-3.71a.5.5 0 0 1 .577-.094l1.777 1.947V5a1 1 0 0 0-1-1z"/></svg>
                            <div class="mt-2 text-body-secondary">${t("No saved images for this location.")}</div>
                       </div>`;
                parentPane.insertAdjacentHTML("beforeend", emptyHtml);
            }
        }
    }

    /* --- Delete single item handler --- */
    async function handleDeleteSingle(triggerEl, fromModal = false) {
        let btnEl = triggerEl;
        let filename = "";
        let mediaType = "";
        let deleteUrl = "";

        if (fromModal) {
            currentMediaList = getMediaItems();
            if (currentIndex < 0 || currentIndex >= currentMediaList.length) return;
            btnEl = currentMediaList[currentIndex];
        }

        filename = btnEl.dataset.mediaTitle || btnEl.dataset.filename || "";
        mediaType = btnEl.dataset.mediaType || (btnEl.closest(".reports-media__item")?.dataset.mediaType || "image");
        deleteUrl = btnEl.dataset.mediaDeleteUrl || btnEl.dataset.deleteUrl || "";

        if (!deleteUrl && locationName && filename) {
            deleteUrl = `/reports/${encodeURIComponent(locationName)}/media/${encodeURIComponent(mediaType)}/${encodeURIComponent(filename)}/delete`;
        }
        if (!deleteUrl || !filename) return;

        const confirmMsg = t('Are you sure you want to delete media file "{name}"?', { name: filename });
        const confirmed = typeof window.appConfirm === "function"
            ? await window.appConfirm({
                title: t("Delete media"),
                message: confirmMsg,
                confirmText: t("Delete"),
                tone: "danger"
            })
            : window.confirm(confirmMsg);

        if (!confirmed) return;

        try {
            const res = await fetch(deleteUrl, {
                method: "POST",
                headers: {
                    "X-Requested-With": "XMLHttpRequest",
                    "Content-Type": "application/json"
                }
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok || !data.ok) {
                throw new Error(data.error || t("Failed to delete media file"));
            }

            const itemEl = btnEl.closest(".reports-media__item") || root.querySelector(`[data-media-filename="${CSS.escape(filename)}"]`);
            removeMediaItemFromDOM(itemEl, mediaType);
            toast(data.message || t("Media file deleted successfully"), "success");

            if (fromModal) {
                currentMediaList = getMediaItems();
                if (currentMediaList.length === 0) {
                    modal.hide();
                } else {
                    if (currentIndex >= currentMediaList.length) {
                        currentIndex = currentMediaList.length - 1;
                    }
                    openMediaByIndex(currentIndex);
                }
            }
        } catch (err) {
            toast(err.message || t("Failed to delete media file"), "danger");
        }
    }

    /* --- Bulk selection management --- */
    function updateSelectedUI() {
        const activePane = root.querySelector(".tab-pane.active");
        if (!activePane) return;
        const checkedBoxes = Array.from(activePane.querySelectorAll(".reports-media__checkbox:checked"));
        const count = checkedBoxes.length;

        if (selectedCountEl) selectedCountEl.textContent = String(count);
        if (bulkDeleteBtn) {
            bulkDeleteBtn.classList.toggle("d-none", count === 0);
        }

        const totalBoxes = activePane.querySelectorAll(".reports-media__checkbox").length;
        if (selectAllBtn) {
            const allChecked = totalBoxes > 0 && count === totalBoxes;
            selectAllBtn.innerHTML = allChecked
                ? `<span>${t("Clear selection")}</span>`
                : `<span>${t("Select all")}</span>`;
        }
    }

    function exitSelectMode() {
        isSelectMode = false;
        root.classList.remove("is-select-mode");
        if (toggleSelectText) toggleSelectText.textContent = t("Select");
        if (selectAllBtn) selectAllBtn.classList.add("d-none");
        if (bulkDeleteBtn) bulkDeleteBtn.classList.add("d-none");

        root.querySelectorAll(".reports-media__checkbox").forEach((cb) => {
            cb.checked = false;
        });
        root.querySelectorAll(".reports-media__item").forEach((it) => {
            it.classList.remove("is-selected");
        });
        if (selectedCountEl) selectedCountEl.textContent = "0";
    }

    function toggleSelectMode() {
        isSelectMode = !isSelectMode;
        root.classList.toggle("is-select-mode", isSelectMode);

        if (isSelectMode) {
            if (toggleSelectText) toggleSelectText.textContent = t("Cancel");
            if (selectAllBtn) selectAllBtn.classList.remove("d-none");
            updateSelectedUI();
        } else {
            exitSelectMode();
        }
    }

    toggleSelectBtn?.addEventListener("click", () => {
        toggleSelectMode();
    });

    selectAllBtn?.addEventListener("click", () => {
        const activePane = root.querySelector(".tab-pane.active");
        if (!activePane) return;
        const boxes = Array.from(activePane.querySelectorAll(".reports-media__checkbox"));
        if (!boxes.length) return;

        const allChecked = boxes.every((b) => b.checked);
        boxes.forEach((b) => {
            b.checked = !allChecked;
            const item = b.closest(".reports-media__item");
            if (item) item.classList.toggle("is-selected", !allChecked);
        });
        updateSelectedUI();
    });

    root.addEventListener("change", (e) => {
        const cb = e.target.closest(".reports-media__checkbox");
        if (!cb) return;
        const item = cb.closest(".reports-media__item");
        if (item) {
            item.classList.toggle("is-selected", cb.checked);
        }
        updateSelectedUI();
    });

    /* --- Bulk Delete Handler --- */
    bulkDeleteBtn?.addEventListener("click", async () => {
        const activePane = root.querySelector(".tab-pane.active");
        if (!activePane) return;

        const checkedBoxes = Array.from(activePane.querySelectorAll(".reports-media__checkbox:checked"));
        if (checkedBoxes.length === 0) return;

        const filenames = checkedBoxes.map((b) => b.value).filter(Boolean);
        const count = filenames.length;
        const activeType = getActiveTabType();

        const confirmMsg = t("Are you sure you want to delete {count} selected files?", { count: count });
        const confirmed = typeof window.appConfirm === "function"
            ? await window.appConfirm({
                title: t("Delete media"),
                message: confirmMsg,
                confirmText: t("Delete"),
                tone: "danger"
            })
            : window.confirm(confirmMsg);

        if (!confirmed) return;

        bulkDeleteBtn.disabled = true;
        try {
            const res = await fetch(bulkDeleteUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest"
                },
                body: JSON.stringify({
                    filenames: filenames,
                    media_type: activeType
                })
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok || !data.ok) {
                throw new Error(data.error || t("Failed to delete selected media files"));
            }

            const deletedList = data.deleted || filenames;
            deletedList.forEach((fn) => {
                const itemEl = root.querySelector(`[data-media-filename="${CSS.escape(fn)}"]`);
                removeMediaItemFromDOM(itemEl, activeType);
            });

            toast(data.message || t("Selected media files deleted successfully"), "success");
            exitSelectMode();
        } catch (err) {
            toast(err.message || t("Failed to delete selected media files"), "danger");
        } finally {
            bulkDeleteBtn.disabled = false;
        }
    });

    /* --- Thumbnail and actions click handler --- */
    root.addEventListener("click", (e) => {
        // 1. Delete button on thumbnail
        const delBtn = e.target.closest("[data-action='delete-media']");
        if (delBtn) {
            e.preventDefault();
            e.stopPropagation();
            handleDeleteSingle(delBtn, false);
            return;
        }

        // 2. Click in select mode
        if (isSelectMode) {
            const item = e.target.closest(".reports-media__item");
            if (item) {
                const cb = item.querySelector(".reports-media__checkbox");
                if (cb && e.target !== cb) {
                    cb.checked = !cb.checked;
                    item.classList.toggle("is-selected", cb.checked);
                    updateSelectedUI();
                }
            }
            return;
        }

        // 3. Normal thumbnail click to open lightbox
        const btn = e.target.closest("[data-media-url]");
        if (!btn) return;
        currentMediaList = getMediaItems();
        const idx = currentMediaList.indexOf(btn);
        if (idx >= 0) {
            openMediaByIndex(idx);
        }
    });

    /* --- Modal Delete button --- */
    modalDeleteBtn?.addEventListener("click", () => {
        handleDeleteSingle(null, true);
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

    /* --- Tab switch resets select mode --- */
    root.querySelectorAll('[data-bs-toggle="tab"]').forEach((tabBtn) => {
        tabBtn.addEventListener("show.bs.tab", () => {
            if (isSelectMode) {
                exitSelectMode();
            }
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

    /* --- Lazy Loading for Media Thumbnails --- */
    function initMediaLazyLoading() {
        const lazyImages = root.querySelectorAll("img.reports-media__lazy-img");
        if (!lazyImages.length) return;

        function markLoaded(img) {
            img.classList.add("is-loaded");
            const frame = img.closest(".reports-media__thumb-frame");
            if (frame) {
                frame.classList.add("is-loaded");
            }
        }

        function loadImage(img) {
            const dataSrc = img.dataset.src;
            if (!dataSrc || img.dataset.lazyLoaded === "true") return;
            img.dataset.lazyLoaded = "true";

            img.addEventListener("load", () => markLoaded(img), { once: true });
            img.addEventListener("error", () => markLoaded(img), { once: true });

            img.src = dataSrc;
            if (img.complete) {
                markLoaded(img);
            }
        }

        if (!("IntersectionObserver" in window)) {
            lazyImages.forEach(loadImage);
            return;
        }

        const observer = new IntersectionObserver((entries, obs) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    obs.unobserve(img);
                    loadImage(img);
                }
            });
        }, {
            rootMargin: "200px 0px",
            threshold: 0.01
        });

        lazyImages.forEach((img) => observer.observe(img));

        root.querySelectorAll('[data-bs-toggle="tab"]').forEach((tabBtn) => {
            tabBtn.addEventListener("shown.bs.tab", () => {
                const activePane = root.querySelector(".tab-pane.active");
                if (activePane) {
                    activePane.querySelectorAll("img.reports-media__lazy-img:not([data-lazy-loaded='true'])").forEach((img) => {
                        observer.observe(img);
                    });
                }
            });
        });
    }

    initMediaLazyLoading();
})();
