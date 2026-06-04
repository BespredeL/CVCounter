/**
 * Developed by: Aleksandr Kireev
 * Created: 04.06.2026
 * Updated: 04.06.2026
 * Website: https://bespredel.name
 */

/**
 * Dashboard modal - per-counter detection settings
 */
const CounterSettingsModal = {
    /**
     * The modal instance
     *
     * @type {object}
     */
    _modal: null,

    /**
     * The location
     *
     * @type {string}
     */
    _location: null,

    /**
     * Get the strings
     *
     * @returns {object} The strings
     */
    strings() {
        return window.DASHBOARD_I18N || {};
    },

    /**
     * Get the modal
     *
     * @returns {object} The modal
     */
    getModal() {
        if (!this._modal) {
            const el = document.getElementById("counterSettingsModal");

            if (el) {
                this._modal = bootstrap.Modal.getOrCreateInstance(el);
            }
        }

        return this._modal;
    },

    /**
     * Get the form URL
     *
     * @param {string} location - The location
     * @returns {string} The form URL
     */
    formUrl(location) {
        return `/counter/${encodeURIComponent(location)}/settings/form`;
    },

    /**
     * Set the loading state
     *
     * @returns {void}
     */
    setLoading() {
        const s = this.strings();

        $("#counterSettingsModalBody").html(`<div class="counter-settings-modal__loading text-center py-5">
                <span class="spinner-border" role="status" aria-hidden="true"></span>
                <p class="text-muted small mt-2 mb-0">${s.loadingSettings || "Loading settings"}</p>
            </div>`);

        $("#counterSettingsSaveBtn").prop("disabled", true);
    },

    /**
     * Bind the form submit event
     *
     * @returns {void}
     */
    bindFormSubmit() {
        const self = this;
        const $form = $("#counterSettingsForm");

        $form.off("submit.counterSettings").on("submit.counterSettings", function (e) {
            e.preventDefault();

            const $btn = $("#counterSettingsSaveBtn");
            const strings = self.strings();
            const spinner = $('<span class="spinner-border spinner-border-sm ms-2" role="status"></span>');

            $btn.prop("disabled", true).append(spinner);

            $.ajax({
                url: $form.attr("action"), method: "POST", data: $form.serialize(), headers: {"X-Requested-With": "XMLHttpRequest"},
            })
                .done((data) => {
                    showToast(strings.settingsSaved || "Settings saved", "success");

                    if (data?.restart_recommended) {
                        showToast(strings.settingsRestartHint || "Stop and start the counter to apply all changes", "info");
                    }

                    self.getModal()?.hide();
                })
                .fail(() => {
                    showToast(strings.requestFailed || "Request failed", "danger");
                })
                .always(() => {
                    spinner.remove();
                    $btn.prop("disabled", false);
                });
        });
    },

    /**
     * Open the modal
     *
     * @param {jQuery} $card - The card element
     * @returns {void}
     */
    open($card) {
        const location = $card.data("location");
        const title = $card.find(".counter-card__name").text().trim();
        const strings = this.strings();
        const modal = this.getModal();

        if (!modal || !location) {
            return;
        }

        this._location = location;
        $("#counterSettingsModalTitle").text(strings.counterSettings || "Counter settings");
        $("#counterSettingsModalSubtitle").text(`${title} · ${location}`);
        this.setLoading();
        modal.show();

        $.get(this.formUrl(location))
            .done((html) => {
                $("#counterSettingsModalBody").html(html);
                $("#counterSettingsSaveBtn").prop("disabled", false);
                this.bindFormSubmit();
            })
            .fail(() => {
                $("#counterSettingsModalBody").html(`<p class="text-danger mb-0">${strings.requestFailed || "Request failed"}</p>`);
                showToast(strings.requestFailed || "Request failed", "danger");
            });
    },

    /**
     * Initialize the counter settings modal
     *
     * @returns {void}
     */
    initialize() {
        const self = this;

        $("#counter-dashboard").on("click", "[data-action=settings]", function (e) {
            e.preventDefault();
            e.stopPropagation();

            const $toggle = $(this).closest(".counter-card__open").find(".dropdown-toggle")[0];

            if ($toggle) {
                bootstrap.Dropdown.getOrCreateInstance($toggle).hide();
            }

            self.open($(this).closest(".counter-card"));
        });

        document.getElementById("counterSettingsModal")?.addEventListener("hidden.bs.modal", () => {
            $("#counterSettingsModalBody").empty();
            $("#counterSettingsSaveBtn").prop("disabled", true);
            self._location = null;
        });
    },
};