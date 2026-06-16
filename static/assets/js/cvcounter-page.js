/**
 * Developed by: Aleksandr Kireev
 * Created: 04.09.2024
 * Updated: 16.06.2026
 * Website: https://bespredel.name
 *
 * CVCounterWEB - single counter page UI (video / text views).
 */

const CounterPage = {
    counterInputValue(selector) {
        return parseInt(document.querySelector(selector)?.value, 10) || 0;
    },

    setCounterInputValue(selector, value) {
        document.querySelectorAll(selector).forEach((el) => {
            el.value = value;
        });
    },

    setCounterDisplay(id, value) {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = value;
        }
    },

    saveCount(url) {
        const defectCount = this.counterInputValue("#defect_keyboard input");
        const correctCount = this.counterInputValue("#correct_keyboard input");
        const customFields = {};

        document.querySelectorAll(".custom_field").forEach((el) => {
            customFields[el.name] = el.value;
        });

        fetch(url, {
            method: "POST",
            headers: {"Content-Type": "application/x-www-form-urlencoded"},
            body: new URLSearchParams({
                correct_count: correctCount,
                defect_count: defectCount,
                custom_fields: JSON.stringify(customFields),
            }),
        })
            .then((r) => r.json())
            .then((data = {total_count: 0}) => {
                this.setCounterDisplay("total_count", data.total_count);
                this.setCounterInputValue("#defect_keyboard input, #correct_keyboard input", 0);
            });
    },

    resetCount(url) {
        fetch(url)
            .then((r) => r.json())
            .then((data = {total_count: 0, defect_count: 0, correct_count: 0}) => {
                this.setCounterDisplay("total_count", data.total_count);
                this.setCounterInputValue("#defect_keyboard input", data.defect_count || 0);
                this.setCounterInputValue("#correct_keyboard input", data.correct_count || 0);

                document.querySelectorAll(".custom_field").forEach((el) => {
                    if (el.matches(":checkbox, :radio")) {
                        el.checked = false;
                    } else if (el.matches("input, textarea")) {
                        el.value = "";
                    } else if (el.tagName === "SELECT") {
                        el.selectedIndex = 0;
                    }
                });
            });
    },

    resetCountCurrent(url) {
        const defectCount = this.counterInputValue("#defect_keyboard input");
        const correctCount = this.counterInputValue("#correct_keyboard input");

        fetch(url, {
            method: "POST",
            headers: {"Content-Type": "application/x-www-form-urlencoded"},
            body: new URLSearchParams({
                correct_count: correctCount,
                defect_count: defectCount,
            }),
        })
            .then((r) => r.json())
            .then((data = {current_count: 0}) => {
                this.setCounterDisplay("current_count", data.current_count);
                this.setCounterInputValue("#defect_keyboard input", data.defect_count || 0);
                this.setCounterInputValue("#correct_keyboard input", data.correct_count || 0);
            });
    },

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

    startCount(url) {
        fetch(url).then(() => this.setPauseUI(false));
    },

    pauseCount(url) {
        fetch(url).then(() => this.setPauseUI(true));
    },

    saveCapture(url) {
        fetch(url)
            .then((r) => r.json())
            .then((data) => {
                const statusClass = data.status === "saved" ? "btn-success" : "btn-danger";
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

    applyCounts(data) {
        if (!data) {
            return;
        }

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

    bindCountSocket(location) {
        if (!window.socket) {
            return;
        }

        window.socket.on(`${location}_count`, (data) => {
            this.applyCounts(data);
        });

        window.socket.on(`${location}_notification`, (data) => {
            if (data.message && data.message.length > 0) {
                showToast(data.message, data.type);
            }
        });

        window.socket.on("counter_status_event", (payload) => {
            if (payload?.data?.location !== location) {
                return;
            }

            if (payload.data.status === "paused") {
                this.setPauseUI(true);
            } else if (payload.data.status === "started") {
                this.setPauseUI(false);
            }
        });
    },

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

    init(options) {
        if (!options?.location || !options?.urls) {
            return;
        }

        document.addEventListener("contextmenu", (e) => e.preventDefault());

        this.bindSidebarButtons(options.urls);
        this.applyCounts(options.counts);
        this.bindCountSocket(options.location);

        if (options.video) {
            this.bindVideoFeedRelease();
        }

        if (options.isPaused) {
            this.setPauseUI(true);
        }
    },
};

window.CounterPage = CounterPage;
window.saveCount = (url) => CounterPage.saveCount(url);
window.resetCount = (url) => CounterPage.resetCount(url);
window.resetCountCurrent = (url) => CounterPage.resetCountCurrent(url);
window.startCount = (url) => CounterPage.startCount(url);
window.pauseCount = (url) => CounterPage.pauseCount(url);
window.saveCapture = (url) => CounterPage.saveCapture(url);
window.setPauseUI = (paused) => CounterPage.setPauseUI(paused);
