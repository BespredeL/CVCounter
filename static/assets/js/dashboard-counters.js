/**
 * Developed by: Aleksandr Kireev
 * Created: 04.06.2026
 * Updated: 04.06.2026
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
     * Get the strings
     *
     * @returns {object} The strings
     */
    strings() {
        return window.DASHBOARD_I18N || {};
    },

    /**
     * Get the status label
     *
     * @param {string} status - The status
     * @returns {string} The status label
     */
    statusLabel(status) {
        const s = this.strings();

        switch (status) {
            case "running":
                return s.running || "Running";
            case "paused":
                return s.paused || "Paused";
            case "error":
                return s.error || "Error";
            default:
                return s.stopped || "Stopped";
        }
    },

    /**
     * Get the card
     *
     * @param {string} location
     * @returns {jQuery}
     */
    card(location) {
        return $(".counter-card").filter(function () {
            return $(this).data("location") === location;
        });
    },

    /**
     * Get the toggle URL
     *
     * @param {jQuery} $card - The card element
     * @param {string} status - The status
     * @returns {string} The toggle URL
     */
    toggleUrl($card, status) {
        if (status === "running") {
            return $card.data("pauseUrl");
        }

        if (status === "paused") {
            return $card.data("resumeUrl");
        }

        return $card.data("bootstrapUrl");
    },

    /**
     * Refresh the preview
     *
     * @param {jQuery} $card - The card element
     * @param {number} previewTs - The preview timestamp
     * @returns {void}
     */
    refreshPreview($card, previewTs) {
        const base = $card.data("previewUrl");

        if (!base) {
            return;
        }

        const $preview = $card.find(".counter-card__preview");
        const bust = previewTs || Date.now();
        let $img = $card.find("[data-role=preview]");

        $card.find("[data-role=preview-placeholder]").remove();

        if (!$img.length) {
            $img = $('<img class="counter-card__preview-img" data-role="preview" alt="" loading="lazy">');
            $preview.prepend($img);
        }

        $img.attr("src", `${base}?t=${bust}`);
    },

    /**
     * Apply the status
     *
     * @param {string} location - The location
     * @param {string} status - The status
     * @returns {void}
     */
    applyStatus(location, status) {
        const $card = this.card(location);

        if (!$card.length) {
            return;
        }

        this.STATUS_CLASSES.forEach((name) => {
            $card.removeClass(`counter-card--${name}`);
        });

        $card.addClass(`counter-card--${status}`);
        $card.attr("data-status", status);
        $card.find("[data-role=status-badge]").text(this.statusLabel(status));
        $card.find("[data-role=status-dot]").attr("title", this.statusLabel(status));

        const $toggle = $card.find("[data-role=toggle]");
        const strings = this.strings();
        const $play = $toggle.find(".icon-play");
        const $pause = $toggle.find(".icon-pause");

        $card.find("[data-action=stop]").prop("disabled", status === "stopped");

        if (status === "running") {
            $play.addClass("d-none");
            $pause.removeClass("d-none");
            $toggle.attr("title", strings.pauseCounting || "Pause");
        } else {
            $play.removeClass("d-none");
            $pause.addClass("d-none");

            const label = status === "paused"
                ? (strings.resumeCounting || "Resume")
                : (strings.startCounter || "Start");

            $toggle.attr("title", label);
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
        const $stats = $("#counterStats");
        if (!$stats.length) {
            return;
        }

        const counts = {running: 0, paused: 0, stopped: 0, error: 0};
        $(".counter-card").each((_, el) => {
            const status = $(el).attr("data-status") || "stopped";
            if (counts[status] !== undefined) {
                counts[status] += 1;
            }
        });

        const total = counts.running + counts.paused + counts.stopped + counts.error;
        const template = this.strings().statsTemplate || "{total} counters · {running} running · {paused} paused";

        $stats.text(
            template
                .replace("{total}", total)
                .replace("{running}", counts.running)
                .replace("{paused}", counts.paused)
        );
    },

    /**
     * Apply the filters
     *
     * @returns {void}
     */
    applyFilters() {
        const query = ($("#counterSearch").val() || "").toLowerCase().trim();
        const statusFilter = $('input[name="counterStatusFilter"]:checked').val() || "all";
        let visible = 0;

        $(".counter-card").each((_, el) => {
            const $card = $(el);
            const status = $card.attr("data-status") || "stopped";
            const searchText = ($card.data("searchText") || "").toString();
            const matchesQuery = !query || searchText.indexOf(query) !== -1;
            const matchesStatus = statusFilter === "all" || status === statusFilter;
            const show = matchesQuery && matchesStatus;

            $card.toggleClass("counter-card--hidden", !show);

            if (show) {
                visible += 1;
            }
        });

        $("#counterFilterEmpty").toggleClass("d-none", visible > 0);
    },

    /**
     * Run the action
     *
     * @param {jQuery} $card - The card element
     * @param {string} url - The URL
     * @returns {void}
     */
    runAction($card, url) {
        const location = $card.data("location");
        const $toggle = $card.find("[data-role=toggle]");
        const spinner = $('<span class="spinner-border spinner-border-sm" role="status"></span>');

        $toggle.prop("disabled", true).addClass("is-loading").append(spinner);

        return $.ajax({
            url,
            method: "GET",
            headers: {"X-Requested-With": "XMLHttpRequest"},
        })
            .done((data) => {
                const status = data?.status;

                if (status === "started") {
                    this.applyStatus(location, "running");
                    if (data.preview_ts) {
                        this.refreshPreview($card, data.preview_ts);
                    }
                } else if (status === "paused") {
                    this.applyStatus(location, "paused");
                } else if (status === "stopped") {
                    this.applyStatus(location, "stopped");
                }
            })
            .fail(() => {
                showToast(this.strings().requestFailed || "Request failed", "danger");
            })
            .always(() => {
                spinner.remove();
                $toggle.prop("disabled", false).removeClass("is-loading");
            });
    },

    /**
     * Open the counter
     *
     * @param {jQuery} $card - The card element
     * @param {string} mode - The mode
     * @returns {void}
     */
    openCounter($card, mode) {
        const strings = this.strings();
        const location = $card.data("location");
        const status = $card.attr("data-status") || "stopped";
        const url = mode === "text" ? $card.data("textUrl") : $card.data("videoUrl");
        const $launch = $card.find(".counter-card__launch");
        const label = mode === "text" ? (strings.openText || "Text") : (strings.openVideo || "Video");

        $launch.attr("title", label);

        const openWindow = () => window.open(url, "_blank", "noopener");

        if (status === "stopped") {
            this.runAction($card, $card.data("bootstrapUrl")).done((data) => {
                if (data?.preview_ts) {
                    this.refreshPreview($card, data.preview_ts);
                }
                openWindow();
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

            const s = this.strings();

            switch (status) {
                case "started":
                    showToast(s.toastStarted || "Counting has started!", "success");
                    break;
                case "stopped":
                    showToast(s.toastStopped || "Counting has stopped!", "secondary");
                    break;
                case "paused":
                    showToast(s.toastPaused || "Counting has paused!", "warning");
                    break;
                case "error":
                    showToast(s.toastError || "Counting has error!", "danger");
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

        $("#counter-dashboard").on("click", "[data-role=toggle]", function (e) {
            e.preventDefault();
            const $card = $(this).closest(".counter-card");
            const status = $card.attr("data-status") || "stopped";
            self.runAction($card, self.toggleUrl($card, status));
        });

        $("#counter-dashboard").on("click", "[data-action=stop]", function (e) {
            e.preventDefault();

            const $btn = $(this);

            if ($btn.prop("disabled")) {
                return;
            }

            const $card = $btn.closest(".counter-card");
            const strings = self.strings();
            const name = $card.find(".counter-card__name").text().trim();

            if (!window.confirm(`${strings.confirmStop || "Stop counter"} «${name}»?`)) {
                return;
            }

            const spinner = $('<span class="spinner-border spinner-border-sm" role="status"></span>');

            $btn.prop("disabled", true).append(spinner);

            $.ajax({
                url: $card.data("stopUrl"),
                method: "GET",
                headers: {"X-Requested-With": "XMLHttpRequest"},
            }).done(() => self.applyStatus($card.data("location"), "stopped"))
                .fail(() => showToast(strings.requestFailed || "Request failed", "danger"))
                .always(() => {
                    spinner.remove();
                    $btn.prop("disabled", $card.attr("data-status") === "stopped");
                });
        });

        $("#counter-dashboard").on("click", "[data-open-mode]", function (e) {
            e.preventDefault();
            const $card = $(this).closest(".counter-card");
            const mode = $(this).data("openMode");
            self.openCounter($card, mode);
        });
    },

    /**
     * Bind the filters
     *
     * @returns {void}
     */
    bindFilters() {
        $("#counterSearch").on("input", () => this.applyFilters());
        $('input[name="counterStatusFilter"]').on("change", () => this.applyFilters());
    },

    /**
     * Bind the multi counter
     *
     * @returns {void}
     */
    bindMultiCounter() {
        const $panel = $("#counterMultiPicker");
        const $checkboxes = $('input[name="multi_counter_locations"]');
        const $count = $("#counterMultiCount");

        if (!$panel.length) {
            return;
        }

        const strings = this.strings();
        const updateCount = () => {
            const n = $checkboxes.filter(":checked").length;
            const template = strings.multiSelectedTemplate || "{n} selected";
            $count.text(template.replace("{n}", n));
        };

        $checkboxes.on("change", () => updateCount());

        $("#counterMultiSelectAll").on("click", () => {
            $checkboxes.prop("checked", true);
            updateCount();
        });

        $("#counterMultiClear").on("click", () => {
            $checkboxes.prop("checked", false);
            updateCount();
        });

        $("#counterMultiOpen").on("click", () => {
            const selected = $checkboxes.filter(":checked").map(function () {
                return $(this).val();
            }).get();

            if (!selected.length) {
                showToast(strings.selectAtLeastOne || "Select at least one counter", "warning");
                return;
            }

            const baseUrl = ($panel.data("multi-url") || "").replace(/\/+$/, "");
            const params = new URLSearchParams({locations: selected.join(",")});
            window.location.href = `${baseUrl}?${params.toString()}`;
        });

        updateCount();
    },

    /**
     * Initialize the counter dashboard
     *
     * @returns {void}
     */
    initialize() {
        $(".counter-card").each((_, el) => {
            const $card = $(el);
            this.applyStatus($card.data("location"), $card.attr("data-status") || "stopped");
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

/**
 * Initialize the counter dashboard
 */
$(function () {
    CounterDashboard.initialize();
});