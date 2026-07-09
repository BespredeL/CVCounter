/**
 * Developed by: Aleksandr Kireev
 * Created: 04.09.2024
 * Updated: 09.07.2026
 * Website: https://bespredel.name
 */

/**
 * Single counter page UI (video / text views)
 */
const CounterPage = {
    /**
     * Last committed count payload from the server.
     *
     * @type {{total: number, current: number, defect: number, correct: number}}
     */
    _baseCounts: {
        total: 0,
        current: 0,
        defect: 0,
        correct: 0,
    },

    /**
     * Debounce timer for pending-count sync.
     *
     * @type {number|null}
     */
    _pendingSyncTimer: null,

    /**
     * Page bootstrap options rendered from the server.
     *
     * @returns {object|null}
     */
    options() {
        return window.COUNTER_PAGE_OPTIONS || null;
    },

    /**
     * Read numeric value from a counter input.
     *
     * @param {string} selector - Input selector
     * @returns {number}
     */
    counterInputValue(selector) {
        return parseInt(document.querySelector(selector)?.value, 10) || 0;
    },

    /**
     * Set input values without triggering a server sync.
     *
     * @param {string} selector - Input selector
     * @param {number|string} value - Value to set
     * @returns {void}
     */
    _setInputValueSilently(selector, value) {
        document.querySelectorAll(selector).forEach((el) => {
            el.value = value;
        });
    },

    /**
     * Set the same value on all matching counter inputs.
     *
     * @param {string} selector - Input selector
     * @param {number|string} value - Value to set
     * @returns {void}
     */
    setCounterInputValue(selector, value) {
        this._setInputValueSilently(selector, value);
        this.refreshDisplays();
    },

    /**
     * Update a counter display element by id.
     *
     * @param {string} id - Element id
     * @param {number|string} value - Display value
     * @returns {void}
     */
    setCounterDisplay(id, value) {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = value;
        }
    },

    /**
     * Persist pending keyboard values on the server.
     *
     * @returns {Promise<void>}
     */
    syncPendingCounts() {
        const url = this.options()?.urls?.pending;
        if (!url) {
            return Promise.resolve();
        }

        return fetch(url, {
            method: "POST",
            headers: {"Content-Type": "application/x-www-form-urlencoded"},
            body: new URLSearchParams({
                defect_count: this.counterInputValue("#defect_keyboard input"),
                correct_count: this.counterInputValue("#correct_keyboard input"),
            }),
        })
            .then((r) => r.json())
            .then((data) => {
                this.applyCounts(data);
            })
            .catch(() => {
            });
    },

    /**
     * Debounce pending-count sync to the server.
     *
     * @returns {void}
     */
    schedulePendingSync() {
        clearTimeout(this._pendingSyncTimer);

        this._pendingSyncTimer = setTimeout(() => {
            this.syncPendingCounts();
        }, 250);
    },

    /**
     * Save defect / correct counts and custom fields.
     *
     * @param {string} url - Save endpoint
     * @returns {void}
     */
    saveCount(url) {
        const customFields = {};

        document.querySelectorAll(".custom_field").forEach((el) => {
            customFields[el.name] = el.value;
        });

        this.syncPendingCounts().then(() => fetch(url, {
            method: "POST",
            headers: {"Content-Type": "application/x-www-form-urlencoded"},
            body: new URLSearchParams({
                correct_count: this.counterInputValue("#correct_keyboard input"),
                defect_count: this.counterInputValue("#defect_keyboard input"),
                custom_fields: JSON.stringify(customFields),
            }),
        }))
            .then((r) => r.json())
            .then((data) => {
                this.applyCounts(data);
            });
    },

    /**
     * Reset all counts and custom fields.
     *
     * @param {string} url - Reset endpoint
     * @returns {void}
     */
    resetCount(url) {
        fetch(url)
            .then((r) => r.json())
            .then((data) => {
                this.applyCounts(data);

                document.querySelectorAll(".custom_field").forEach((el) => {
                    if (el.matches('input[type="checkbox"], input[type="radio"]')) {
                        el.checked = false;
                    } else if (el.matches("input, textarea")) {
                        el.value = "";
                    } else if (el.tagName === "SELECT") {
                        el.selectedIndex = 0;
                    }
                });
            });
    },

    /**
     * Reset the current batch count.
     *
     * @param {string} url - Reset current endpoint
     * @returns {void}
     */
    resetCountCurrent(url) {
        this.syncPendingCounts().then(() => fetch(url, {
            method: "POST",
            headers: {"Content-Type": "application/x-www-form-urlencoded"},
            body: new URLSearchParams({
                correct_count: this.counterInputValue("#correct_keyboard input"),
                defect_count: this.counterInputValue("#defect_keyboard input"),
            }),
        }))
            .then((r) => r.json())
            .then((data) => {
                this.applyCounts(data);
            });
    },

    /**
     * Toggle pause overlay and transport button styles.
     *
     * @param {boolean} paused - Whether counting is paused
     * @returns {void}
     */
    setPauseUI(paused) {
        const btnPause = document.getElementById("btn_pause");
        const btnStart = document.getElementById("btn_start");
        const pauseDisplay = document.getElementById("pause_display");
        if (!btnPause || !btnStart || !pauseDisplay) {
            return;
        }

        if (paused) {
            btnPause.classList.remove("btn-outline-secondary");
            btnPause.classList.add("btn-warning");
            btnStart.classList.remove("btn-outline-secondary");
            btnStart.classList.add("btn-info");
            pauseDisplay.classList.remove("d-none");
            pauseDisplay.classList.add("d-flex");
        } else {
            btnPause.classList.remove("btn-warning");
            btnPause.classList.add("btn-outline-secondary");
            btnStart.classList.remove("btn-info");
            btnStart.classList.add("btn-outline-secondary");
            pauseDisplay.classList.remove("d-flex");
            pauseDisplay.classList.add("d-none");
        }
    },

    /**
     * Resume counting.
     *
     * @param {string} url - Start endpoint
     * @returns {void}
     */
    startCount(url) {
        fetch(url).then(() => this.setPauseUI(false));
    },

    /**
     * Pause counting.
     *
     * @param {string} url - Pause endpoint
     * @returns {void}
     */
    pauseCount(url) {
        fetch(url).then(() => this.setPauseUI(true));
    },

    /**
     * Save a video frame capture to disk.
     *
     * @param {string} url - Capture endpoint
     * @returns {void}
     */
    saveCapture(url) {
        fetch(url)
            .then((r) => r.json())
            .then((data) => {
                const statusClass = data?.status === "saved" ? "btn-success" : "btn-danger";
                const btn = document.getElementById("save-capture");

                if (!btn) {
                    return;
                }

                btn.classList.add(statusClass);

                setTimeout(() => {
                    btn.classList.remove(statusClass);
                }, 500);
            });
    },

    /**
     * Refresh displayed totals using server counts and keyboard inputs.
     *
     * @returns {void}
     */
    refreshDisplays() {
        const data = this._baseCounts;
        const defectCount = Math.max(this.counterInputValue("#defect_keyboard input"), 0);
        const correctCount = this.counterInputValue("#correct_keyboard input");
        const updateCount = (id, count) => {
            this.setCounterDisplay(id, Math.max(count - defectCount + correctCount, 0));
        };

        updateCount("total_count", data.total || 0);
        updateCount("current_count", data.current || 0);

        const defectEl = document.getElementById("defect_count");
        const correctEl = document.getElementById("correct_count");
        if (defectEl) {
            defectEl.textContent = defectCount + (data.defect || 0);
        }

        if (correctEl) {
            correctEl.textContent = correctCount + (data.correct || 0);
        }
    },

    /**
     * Apply live count payload to the page.
     *
     * @param {object} data - Count payload
     * @returns {void}
     */
    applyCounts(data) {
        if (!data) {
            return;
        }

        this._baseCounts = {
            total: data.total || 0,
            current: data.current || 0,
            defect: data.defect || 0,
            correct: data.correct || 0,
        };

        this._setInputValueSilently("#defect_keyboard input", data.pending_defect ?? 0);
        this._setInputValueSilently("#correct_keyboard input", data.pending_correct ?? 0);
        this.refreshDisplays();
    },

    /**
     * Update displays when defect / correct keyboard values change.
     *
     * @returns {void}
     */
    bindInputListeners() {
        const onPendingChange = () => {
            CounterPage.refreshDisplays();
            CounterPage.schedulePendingSync();
        };
        const schedulePendingChange = () => setTimeout(onPendingChange, 0);

        document.querySelector("#defect_keyboard input")?.addEventListener("input", onPendingChange);
        document.querySelector("#correct_keyboard input")?.addEventListener("input", onPendingChange);
        document.querySelector(".sidebar-right")?.addEventListener("click", (e) => {
            if (e.target.closest("#defect_keyboard, #correct_keyboard, .keyboard, #defect_clear, #correct_clear")) {
                schedulePendingChange();
            }
        });

        document.getElementById("defect_clear")?.addEventListener("click", schedulePendingChange);
        document.getElementById("correct_clear")?.addEventListener("click", schedulePendingChange);
        document.addEventListener("keydown", (e) => {
            if (e.code.startsWith("Numpad") && document.querySelector('input[name="correct_count"]')) {
                schedulePendingChange();
            }
        });
    },

    /**
     * Bind Socket.IO count and status events for this counter.
     *
     * @param {string} location - Counter location key
     * @returns {void}
     */
    bindSocket(location) {
        if (!window.socket) {
            return;
        }

        window.socket.on(`${location}_count`, (data) => {
            CounterPage.applyCounts(data);
        });

        window.socket.on(`${location}_notification`, (data) => {
            if (data?.message?.length > 0) {
                showToast(data.message, data.type);
            }
        });

        window.socket.on("counter_status_event", (payload) => {
            if (payload?.data?.location !== location) {
                return;
            }

            if (payload.data.status === "paused") {
                CounterPage.setPauseUI(true);
            } else if (payload.data.status === "started") {
                CounterPage.setPauseUI(false);
            }
        });
    },

    /**
     * Stop the video feed when leaving the page.
     *
     * @returns {void}
     */
    bindVideoFeedRelease() {
        const releaseVideoFeed = () => {
            const img = document.getElementById("video_feed");
            if (img) {
                img.removeAttribute("src");
            }
        };

        window.addEventListener("pagehide", releaseVideoFeed);

        document.addEventListener("click", (e) => {
            const link = e.target.closest('a[href]:not([target="_blank"])');
            if (link) {
                releaseVideoFeed();
            }
        });
    },

    /**
     * Bind sidebar transport and save buttons.
     *
     * @param {object} urls - Action endpoints
     * @returns {void}
     */
    bindSidebarButtons(urls) {
        document.getElementById("btn_save")?.addEventListener("click", () => {
            this.saveCount(urls.save);
        });

        document.getElementById("btn_reset")?.addEventListener("click", () => {
            this.resetCount(urls.reset);
        });

        document.getElementById("btn_reset_current")?.addEventListener("click", () => {
            this.resetCountCurrent(urls.resetCurrent);
        });

        document.getElementById("btn_start")?.addEventListener("click", () => {
            this.startCount(urls.start);
        });

        document.getElementById("btn_pause")?.addEventListener("click", () => {
            this.pauseCount(urls.pause);
        });

        document.getElementById("save-capture")?.addEventListener("click", () => {
            this.saveCapture(urls.capture);
        });
    },

    /**
     * Initialize the single counter page.
     *
     * @returns {void}
     */
    initialize() {
        const options = this.options();
        if (!options?.location || !options?.urls) {
            return;
        }

        document.addEventListener("contextmenu", (e) => e.preventDefault());

        this.bindSidebarButtons(options.urls);
        this.applyCounts(options.counts);
        this.bindInputListeners();
        this.bindSocket(options.location);

        if (options.video) {
            this.bindVideoFeedRelease();
        }

        if (options.isPaused) {
            this.setPauseUI(true);
        }
    },
};


document.addEventListener("DOMContentLoaded", () => {
    CounterPage.initialize();
});