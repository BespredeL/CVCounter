/**
 * Developed by: Aleksandr Kireev
 * Created: 04.06.2026
 * Updated: 08.06.2026
 * Website: https://bespredel.name
 */

/**
 * Dashboard - counter cards, filters, transport controls
 */
const CounterDashboard = {
    /**
     * The status classes
     *
     * @type {array}
     */
    STATUS_CLASSES: ["stopped", "running", "paused", "error"],

    /**
     * Get the status label
     *
     * @param {string} status - The status
     * @returns {string} The status label
     */
    statusLabel(status) {
        switch (status) {
            case "running":
                return window.trans("Counter running");
            case "paused":
                return window.trans("Counter paused");
            case "error":
                return window.trans("Counting has error!");
            default:
                return window.trans("Counter stopped");
        }
    },

    /**
     * Get the card
     *
     * @param {string} location
     * @returns {HTMLElement|null}
     */
    card(location) {
        return [...document.querySelectorAll(".counter-card")]
            .find(
                (el) => el.dataset.location === location
            ) || null;
    },

    /**
     * Get the toggle URL
     *
     * @param {HTMLElement} card - The card element
     * @param {string} status - The status
     * @returns {string} The toggle URL
     */
    toggleUrl(card, status) {
        if (status === "running") {
            return card.dataset.pauseUrl;
        }

        if (status === "paused") {
            return card.dataset.resumeUrl;
        }

        return card.dataset.bootstrapUrl;
    },

    /**
     * Refresh the preview
     *
     * @param {HTMLElement} card - The card element
     * @param {number} previewTs - The preview timestamp
     * @returns {void}
     */
    refreshPreview(card, previewTs) {
        const base = card.dataset.previewUrl;

        if (!base) {
            return;
        }

        const preview = card.querySelector(".counter-card__preview");
        const bust = previewTs || Date.now();
        let img = card.querySelector("[data-role=preview]");

        card.querySelector("[data-role=preview-placeholder]")?.remove();

        if (!img) {
            img = document.createElement("img");
            img.className = "counter-card__preview-img";
            img.dataset.role = "preview";
            img.alt = "";
            img.loading = "lazy";
            preview?.prepend(img);
        }

        img.src = `${base}?t=${bust}`;
    },

    /**
     * Apply the status
     *
     * @param {string} location - The location
     * @param {string} status - The status
     * @returns {void}
     */
    applyStatus(location, status) {
        const card = this.card(location);

        if (!card) {
            return;
        }

        this.STATUS_CLASSES.forEach((name) => {
            card.classList.remove(`counter-card--${name}`);
        });

        card.classList.add(`counter-card--${status}`);
        card.setAttribute("data-status", status);

        const label = this.statusLabel(status);
        const badge = card.querySelector("[data-role=status-badge]");
        const dot = card.querySelector("[data-role=status-dot]");
        if (badge) {
            badge.textContent = label;
        }
        if (dot) {
            dot.setAttribute("title", label);
        }

        const toggle = card.querySelector("[data-role=toggle]");
        const play = toggle?.querySelector(".icon-play");
        const pause = toggle?.querySelector(".icon-pause");
        const stopBtn = card.querySelector("[data-action=stop]");

        if (stopBtn) {
            stopBtn.disabled = status === "stopped";
        }

        if (status === "running") {
            play?.classList.add("d-none");
            pause?.classList.remove("d-none");
            toggle?.setAttribute("title", window.trans("Pause counting"));
        } else {
            play?.classList.remove("d-none");
            pause?.classList.add("d-none");

            const toggleLabel = status === "paused"
                ? window.trans("Resume counting")
                : window.trans("Start counter");

            toggle?.setAttribute("title", toggleLabel);
        }

        this.updateStats();
        this.applyFilters();
    },

    /**
     * Update the stats
     *
     * @returns {void}
     */
    updateStats() {
        const stats = document.getElementById("counterStats");
        if (!stats) {
            return;
        }

        const counts = {running: 0, paused: 0, stopped: 0, error: 0};
        document.querySelectorAll(".counter-card").forEach((el) => {
            const status = el.getAttribute("data-status") || "stopped";
            if (counts[status] !== undefined) {
                counts[status] += 1;
            }
        });

        const total = counts.running + counts.paused + counts.stopped + counts.error;
        stats.textContent = window.trans("Counters stats", {
            total,
            running: counts.running,
            paused: counts.paused,
        });
    },

    /**
     * Apply the filters
     *
     * @returns {void}
     */
    applyFilters() {
        const query = (document.getElementById("counterSearch")?.value || "").toLowerCase().trim();
        const statusFilter = document.querySelector('input[name="counterStatusFilter"]:checked')?.value || "all";
        let visible = 0;

        document.querySelectorAll(".counter-card").forEach((card) => {
            const status = card.getAttribute("data-status") || "stopped";
            const searchText = (card.dataset.searchText || "").toString();
            const matchesQuery = !query || searchText.indexOf(query) !== -1;
            const matchesStatus = statusFilter === "all" || status === statusFilter;
            const show = matchesQuery && matchesStatus;

            card.classList.toggle("counter-card--hidden", !show);

            if (show) {
                visible += 1;
            }
        });

        document.getElementById("counterFilterEmpty")?.classList.toggle("d-none", visible > 0);
    },

    /**
     * Apply server status from AJAX response
     *
     * @param {HTMLElement} card - The card element
     * @param {string} location - Counter location
     * @param {object} data - Response JSON
     * @returns {void}
     */
    applyActionResponse(card, location, data) {
        const status = data?.status;
        if (status === "started") {
            this.applyStatus(location, "running");
            if (data.preview_ts) {
                this.refreshPreview(card, data.preview_ts);
            }
        } else if (status === "paused") {
            this.applyStatus(location, "paused");
        } else if (status === "stopped") {
            this.applyStatus(location, "stopped");
        }
    },

    /**
     * Sync transport button disabled state after loading ends
     *
     * @param {HTMLElement} card - The card element
     * @returns {void}
     */
    syncTransportButtons(card) {
        const status = card.getAttribute("data-status") || "stopped";

        card.querySelectorAll(".counter-card__transport .btn").forEach((btn) => {
            btn.disabled = false;
        });

        const stopBtn = card.querySelector("[data-action=stop]");
        if (stopBtn) {
            stopBtn.disabled = status === "stopped";
        }
    },

    /**
     * Run counter control request (start / pause / resume / stop)
     *
     * @param {HTMLElement} card - The card element
     * @param {string} url - The URL
     * @param {HTMLElement} [activeBtn] - Button showing loading state (toggle or stop)
     * @returns {Promise<object>}
     */
    runAction(card, url, activeBtn) {
        const location = card.dataset.location;
        const btn = activeBtn || card.querySelector("[data-role=toggle]");
        const spinner = document.createElement("span");
        spinner.className = "spinner-border spinner-border-sm";
        spinner.setAttribute("role", "status");

        card.querySelectorAll(".counter-card__transport .btn").forEach((el) => {
            el.disabled = true;
        });
        btn?.classList.add("is-loading");
        btn?.appendChild(spinner);

        return fetch(url, {
            method: "GET",
            headers: {"X-Requested-With": "XMLHttpRequest"},
        })
            .then((r) => r.json())
            .then((data) => {
                this.applyActionResponse(card, location, data);
                return data;
            })
            .catch(() => {
                showToast(window.trans("Request failed"), "danger");
                throw new Error("Request failed");
            })
            .finally(() => {
                spinner.remove();
                btn?.classList.remove("is-loading");
                this.syncTransportButtons(card);
            });
    },

    /**
     * Open the counter
     *
     * @param {HTMLElement} card - The card element
     * @param {string} mode - The mode
     * @returns {void}
     */
    openCounter(card, mode) {
        const status = card.getAttribute("data-status") || "stopped";
        const url = mode === "text" ? card.dataset.textUrl : card.dataset.videoUrl;
        const launch = card.querySelector(".counter-card__launch");
        const label = mode === "text"
            ? window.trans("Open text")
            : window.trans("Open video");

        launch?.setAttribute("title", label);

        const openWindow = () => window.open(url, "_blank", "noopener");

        if (status === "stopped") {
            this.runAction(card, card.dataset.bootstrapUrl).then((data) => {
                if (data?.preview_ts) {
                    this.refreshPreview(card, data.preview_ts);
                }
                openWindow();
            }).catch(() => {
            });
        } else {
            openWindow();
        }
    },

    /**
     * Bind the socket
     *
     * @returns {void}
     */
    bindSocket() {
        if (!window.socket) {
            return;
        }

        window.socket.on("counter_status_event", (payload) => {
            const location = payload?.data?.location;
            const status = payload?.data?.status;

            if (!location || !status) {
                return;
            }

            const mapped = status === "started" ? "running" : status;
            if (this.STATUS_CLASSES.includes(mapped)) {
                this.applyStatus(location, mapped);
            }

            switch (status) {
                case "started":
                    showToast(window.trans("Counting has started!"), "success");
                    break;
                case "stopped":
                    showToast(window.trans("Counting has stopped!"), "secondary");
                    break;
                case "paused":
                    showToast(window.trans("Counting has paused!"), "warning");
                    break;
                case "error":
                    showToast(window.trans("Counting has error!"), "danger");
                    this.applyStatus(location, "error");
                    break;
            }
        });
    },

    /**
     * Bind the cards
     *
     * @returns {void}
     */
    bindCards() {
        const self = this;
        const dashboard = document.getElementById("counter-dashboard");
        if (!dashboard) {
            return;
        }

        dashboard.addEventListener("click", (e) => {
            const toggle = e.target.closest("[data-role=toggle]");
            if (toggle) {
                e.preventDefault();
                const card = toggle.closest(".counter-card");
                const status = card?.getAttribute("data-status") || "stopped";
                if (card) {
                    self.runAction(card, self.toggleUrl(card, status));
                }
                return;
            }

            const stopBtn = e.target.closest("[data-action=stop]");
            if (stopBtn) {
                e.preventDefault();

                if (stopBtn.disabled) {
                    return;
                }

                const card = stopBtn.closest(".counter-card");
                const name = card?.querySelector(".counter-card__name")?.textContent.trim() || "";

                if (!window.confirm(`${window.trans("Stop counter")} «${name}»?`)) {
                    return;
                }

                if (card) {
                    self.runAction(card, card.dataset.stopUrl, stopBtn);
                }
                return;
            }

            const openBtn = e.target.closest("[data-open-mode]");
            if (openBtn) {
                e.preventDefault();
                const card = openBtn.closest(".counter-card");
                const mode = openBtn.dataset.openMode;
                if (card && mode) {
                    self.openCounter(card, mode);
                }
            }
        });
    },

    /**
     * Bind the filters
     *
     * @returns {void}
     */
    bindFilters() {
        document.getElementById("counterSearch")?.addEventListener("input", () => this.applyFilters());
        document.querySelectorAll('input[name="counterStatusFilter"]').forEach((input) => {
            input.addEventListener("change", () => this.applyFilters());
        });
    },

    /**
     * Get the multi checkboxes
     *
     * @returns {NodeListOf<HTMLInputElement>}
     */
    multiCheckboxes() {
        return document.querySelectorAll("#counter-dashboard [data-role=multi-select]");
    },

    /**
     * Sync the card selected state
     *
     * @param {HTMLInputElement} checkbox - The checkbox element
     * @returns {void}
     */
    syncCardSelectedState(checkbox) {
        checkbox.closest(".counter-card")?.classList.toggle("counter-card--selected", checkbox.checked);
    },

    /**
     * Update the multi selection count
     *
     * @returns {void}
     */
    updateMultiSelectionCount() {
        const countEl = document.getElementById("counterMultiCount");
        if (!countEl) {
            return;
        }

        const n = [...this.multiCheckboxes()].filter((cb) => cb.checked).length;
        countEl.textContent = window.trans("Multi counter selected count", {n});
    },

    /**
     * Bind the multi counter
     *
     * @returns {void}
     */
    bindMultiCounter() {
        const section = document.querySelector(".counter-dashboard-section");
        const checkboxes = this.multiCheckboxes();

        if (!section || !checkboxes.length) {
            return;
        }

        checkboxes.forEach((checkbox) => {
            checkbox.addEventListener("change", (e) => {
                e.stopPropagation();
                this.syncCardSelectedState(checkbox);
                this.updateMultiSelectionCount();
            });
            checkbox.addEventListener("click", (e) => e.stopPropagation());
        });

        document.getElementById("counterMultiSelectVisible")?.addEventListener("click", () => {
            checkboxes.forEach((cb) => {
                const visible = !cb.closest(".counter-card")?.classList.contains("counter-card--hidden");
                cb.checked = visible;
                this.syncCardSelectedState(cb);
            });
            this.updateMultiSelectionCount();
        });

        document.getElementById("counterMultiSelectAll")?.addEventListener("click", () => {
            checkboxes.forEach((cb) => {
                cb.checked = true;
                this.syncCardSelectedState(cb);
            });
            this.updateMultiSelectionCount();
        });

        document.getElementById("counterMultiClear")?.addEventListener("click", () => {
            checkboxes.forEach((cb) => {
                cb.checked = false;
                this.syncCardSelectedState(cb);
            });
            this.updateMultiSelectionCount();
        });

        document.getElementById("counterMultiOpen")?.addEventListener("click", () => {
            const selected = [...checkboxes]
                .filter((cb) => cb.checked)
                .map((cb) => cb.value);

            if (!selected.length) {
                showToast(window.trans("Select at least one counter"), "warning");
                return;
            }

            const baseUrl = (section.dataset.multiUrl || "").replace(/\/+$/, "");
            const params = new URLSearchParams({locations: selected.join(",")});
            window.location.href = `${baseUrl}?${params.toString()}`;
        });

        this.updateMultiSelectionCount();
    },

    /**
     * Initialize the counter dashboard
     *
     * @returns {void}
     */
    initialize() {
        document.querySelectorAll(".counter-card").forEach((card) => {
            this.applyStatus(card.dataset.location, card.getAttribute("data-status") || "stopped");
        });

        this.bindSocket();
        this.bindCards();
        this.bindFilters();
        this.bindMultiCounter();
        this.updateStats();

        if (typeof CounterSettingsModal !== "undefined") {
            CounterSettingsModal.initialize();
        }
    },
};

document.addEventListener("DOMContentLoaded", () => {
    CounterDashboard.initialize();
});