/**
 * Developed by: Aleksandr Kireev
 * Created: 03.06.2026
 * Updated: 25.07.2026
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
     * Render per-class breakdown for one counter card.
     *
     * @param {string} slug - DOM class suffix for this location
     * @param {Array<{name?: string, current?: number, total?: number}>} items - Class counts
     * @returns {void}
     */
    renderByClass(slug, items) {
        const listEl = document.querySelector(`.by_class_list_${slug}`);
        const emptyEl = document.querySelector(`.by_class_empty_${slug}`);
        if (!listEl) {
            return;
        }

        const rows = Array.isArray(items) ? items : [];
        listEl.replaceChildren();

        rows.forEach((item) => {
            const li = document.createElement("li");
            li.className = "multi-counter-card__class-item d-flex justify-content-between gap-2";

            const name = document.createElement("span");
            name.className = "text-truncate";
            name.textContent = item.name || "";
            name.title = item.name || "";

            const values = document.createElement("span");
            values.className = "text-nowrap multi-counter-card__class-values";

            const current = document.createElement("span");
            current.textContent = String(item.current || 0);

            const sep = document.createElement("span");
            sep.className = "opacity-75";
            sep.textContent = " / ";

            const total = document.createElement("span");
            total.className = "opacity-75";
            total.textContent = String(item.total || 0);

            values.append(current, sep, total);
            li.append(name, values);
            listEl.append(li);
        });

        if (emptyEl) {
            emptyEl.classList.toggle("d-none", rows.length > 0);
        }
    },

    /**
     * Update displayed counts for one counter card
     *
     * @param {string} slug - DOM class suffix for this location
     * @param {object} data - Count payload (current, total, by_class)
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
        this.renderByClass(slug, data.by_class || []);
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
                        CounterMultiText.applyCounts(slug, data);
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
                        CounterMultiText.applyCounts(slug, data);
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
