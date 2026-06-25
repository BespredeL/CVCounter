/**
 * Developed by: Aleksandr Kireev
 * Created: 03.06.2026
 * Updated: 25.06.2026
 * Website: https://bespredel.name
 */

/**
 * Fullscreen multi-location text counter view
 */
const CounterMultiText = {
    /**
     * Get the items
     *
     * @returns {array} The items
     */
    items() {
        return window.MULTI_COUNTER_ITEMS || [];
    },

    /**
     * Update displayed counts for one counter card
     *
     * @param {string} slug - DOM class suffix for this location
     * @param {object} data - Count payload (current, total)
     * @returns {void}
     */
    applyCounts(slug, data) {
        if (!slug || !data) {
            return;
        }

        const current = Math.max(0, parseInt(data.current, 10) || 0);
        const total = data.total > 0
            ? Math.max(0, parseInt(data.total, 10) || 0)
            : 0;

        document.querySelectorAll(`.current_count_${slug}`).forEach((el) => {
            el.textContent = current;
        });
        document.querySelectorAll(`.total_count_${slug}`).forEach((el) => {
            el.textContent = total;
        });
    },

    /**
     * Bind the socket events
     *
     * @returns {void}
     */
    bindSocket() {
        if (!window.socket) {
            return;
        }

        this.items().forEach((item) => {
            const location = item.location;
            const slug = item.slug;

            window.socket.on(`${location}_count`, (data) => {
                CounterMultiText.applyCounts(slug, data);
            });

            window.socket.on(`${location}_notification`, (data) => {
                if (data?.message?.length > 0) {
                    showToast(data.message, data.type);
                }
            });
        });
    },

    /**
     * Bind the actions
     *
     * @returns {void}
     */
    bindActions() {
        document.querySelectorAll(".btn_reset_current").forEach((button) => {
            button.addEventListener("click", function () {
                const location = this.dataset.location;
                const slug = CounterMultiText.items().find((i) => i.location === location)?.slug;

                if (!location || !slug) {
                    return;
                }

                fetch(`/reset_count_current/${encodeURIComponent(location)}`, {
                    method: "POST",
                    headers: {"Content-Type": "application/x-www-form-urlencoded"},
                    body: new URLSearchParams({correct_count: 0, defect_count: 0}),
                })
                    .then((r) => r.json())
                    .then((data) => {
                        const value = data?.current_count ?? 0;
                        document.querySelectorAll(`.current_count_${slug}`).forEach((el) => {
                            el.textContent = value;
                        });
                    });
            });
        });

        document.querySelectorAll(".btn_reset").forEach((button) => {
            button.addEventListener("click", function () {
                const location = this.dataset.location;
                const slug = CounterMultiText.items().find((i) => i.location === location)?.slug;

                if (!location || !slug) {
                    return;
                }

                fetch(`/reset_count/${encodeURIComponent(location)}`)
                    .then((r) => r.json())
                    .then((data) => {
                        const value = data?.total_count ?? 0;
                        document.querySelectorAll(`.total_count_${slug}`).forEach((el) => {
                            el.textContent = value;
                        });
                    });
            });
        });
    },

    /**
     * Initialize the counter multi-text
     *
     * @returns {void}
     */
    initialize() {
        document.addEventListener("contextmenu", (e) => e.preventDefault());

        this.items().forEach((item) => {
            this.applyCounts(item.slug, item.counts);
        });

        this.bindSocket();
        this.bindActions();
    },
};

document.addEventListener("DOMContentLoaded", () => {
    CounterMultiText.initialize();
});