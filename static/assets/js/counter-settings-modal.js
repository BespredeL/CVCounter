/**
 * Developed by: Aleksandr Kireev
 * Created: 04.06.2026
 * Updated: 08.06.2026
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
     * Bound form submit handler
     *
     * @type {Function|null}
     */
    _formSubmitHandler: null,

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
        const body = document.getElementById("counterSettingsModalBody");
        const saveBtn = document.getElementById("counterSettingsSaveBtn");

        if (body) {
            body.innerHTML = `
                <div class="counter-settings-modal__loading text-center py-5">
                    <span class="spinner-border" role="status" aria-hidden="true"></span>
                    <p class="text-muted small mt-2 mb-0">${window.trans("Loading settings")}</p>
                </div>`;
        }

        if (saveBtn) {
            saveBtn.disabled = true;
        }
    },

    /**
     * Bind the form submit event
     *
     * @returns {void}
     */
    bindFormSubmit() {
        const self = this;
        const form = document.getElementById("counterSettingsForm");
        if (!form) {
            return;
        }

        if (this._formSubmitHandler) {
            form.removeEventListener("submit", this._formSubmitHandler);
        }

        this._formSubmitHandler = (e) => {
            e.preventDefault();

            const btn = document.getElementById("counterSettingsSaveBtn");
            const spinner = document.createElement("span");
            spinner.className = "spinner-border spinner-border-sm ms-2";
            spinner.setAttribute("role", "status");

            if (btn) {
                btn.disabled = true;
                btn.appendChild(spinner);
            }

            fetch(form.getAttribute("action"), {
                method: "POST",
                headers: {"X-Requested-With": "XMLHttpRequest"},
                body: new URLSearchParams(new FormData(form)),
            })
                .then((r) => r.json())
                .then((data) => {
                    showToast(window.trans("Settings saved"), "success");
                    if (data?.restart_recommended) {
                        showToast(window.trans("Stop and start the counter to apply all changes"), "info");
                    }
                    self.getModal()?.hide();
                })
                .catch(() => {
                    showToast(window.trans("Request failed"), "danger");
                })
                .finally(() => {
                    spinner.remove();
                    if (btn) {
                        btn.disabled = false;
                    }
                });
        };

        form.addEventListener("submit", this._formSubmitHandler);
    },

    /**
     * Open the modal
     *
     * @param {HTMLElement} card - The card element
     * @returns {void}
     */
    open(card) {
        const location = card.dataset.location;
        const title = card.querySelector(".counter-card__name")?.textContent.trim() || "";
        const modal = this.getModal();

        if (!modal || !location) {
            return;
        }

        this._location = location;

        const titleEl = document.getElementById("counterSettingsModalTitle");
        const subtitleEl = document.getElementById("counterSettingsModalSubtitle");
        if (titleEl) {
            titleEl.textContent = window.trans("Counter settings");
        }
        if (subtitleEl) {
            subtitleEl.textContent = `${title} · ${location}`;
        }

        this.setLoading();
        modal.show();

        fetch(this.formUrl(location))
            .then((r) => r.text())
            .then((html) => {
                const body = document.getElementById("counterSettingsModalBody");
                const saveBtn = document.getElementById("counterSettingsSaveBtn");
                if (body) {
                    body.innerHTML = html;
                }
                if (saveBtn) {
                    saveBtn.disabled = false;
                }
                this.bindFormSubmit();
            })
            .catch(() => {
                const body = document.getElementById("counterSettingsModalBody");
                if (body) {
                    body.innerHTML = `<p class="text-danger mb-0">${window.trans("Request failed")}</p>`;
                }
                showToast(window.trans("Request failed"), "danger");
            });
    },

    /**
     * Initialize the counter settings modal
     *
     * @returns {void}
     */
    initialize() {
        const self = this;

        document.getElementById("counter-dashboard")?.addEventListener("click", (e) => {
            const settingsBtn = e.target.closest("[data-action=settings]");
            if (!settingsBtn) {
                return;
            }

            e.preventDefault();
            e.stopPropagation();

            const toggle = settingsBtn.closest(".counter-card__open")?.querySelector(".dropdown-toggle");
            if (toggle) {
                bootstrap.Dropdown.getOrCreateInstance(toggle).hide();
            }

            const card = settingsBtn.closest(".counter-card");
            if (card) {
                self.open(card);
            }
        });

        document.getElementById("counterSettingsModal")?.addEventListener("hidden.bs.modal", () => {
            const body = document.getElementById("counterSettingsModalBody");
            const saveBtn = document.getElementById("counterSettingsSaveBtn");
            body?.replaceChildren();
            if (saveBtn) {
                saveBtn.disabled = true;
            }
            self._location = null;
        });
    },
};