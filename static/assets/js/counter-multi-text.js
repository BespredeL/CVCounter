/**
 * Developed by: Aleksandr Kireev
 * Created: 03.06.2026
 * Updated: 04.06.2026
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
                const current = Math.max(0, parseInt(data.current, 10) || 0);
                const total = data.total > 0 ? Math.max(0, parseInt(data.total, 10) || 0) : 0;

                $(`.current_count_${slug}`).html(current);
                $(`.total_count_${slug}`).html(total);
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
        $(".btn_reset_current").on("click", function () {
            const location = this.dataset.location;
            const slug = CounterMultiText.items().find((i) => i.location === location)?.slug;

            if (!location || !slug) {
                return;
            }

            $.ajax({
                url: `/reset_count_current/${encodeURIComponent(location)}`,
                method: "POST",
                data: {correct_count: 0, defect_count: 0},
            }).done((data) => {
                const value = data?.current_count ?? 0;
                $(`.current_count_${slug}`).html(value);
            });
        });

        $(".btn_reset").on("click", function () {
            const location = this.dataset.location;
            const slug = CounterMultiText.items().find((i) => i.location === location)?.slug;

            if (!location || !slug) {
                return;
            }

            $.ajax({
                url: `/reset_count/${encodeURIComponent(location)}`,
                method: "GET",
            }).done((data) => {
                const value = data?.total_count ?? 0;
                $(`.total_count_${slug}`).html(value);
            });
        });
    },

    /**
     * Initialize the counter multi-text
     *
     * @returns {void}
     */
    initialize() {
        $(document).on("contextmenu", (e) => e.preventDefault());
        this.bindSocket();
        this.bindActions();
    },
};

/**
 * Initialize the counter multi-text
 */
$(function () {
    CounterMultiText.initialize();
});