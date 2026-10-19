/**
 * Computer Vision Counter (CVCounter)
 * Dashboard modal - per-counter detection settings.
 *
 * Developed by: Aleksandr Kireev
 * Created: 04.06.2026
 * Updated: 08.06.2026
 * Website: https://bespredel.name
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
     * Load the form HTML for the specified location
     *
     * @param {string} location - The location identifier
     * @returns {Promise<void>}
     */
    loadForm(location) {
        const self = this;
        this.setLoading();

        return fetch(this.formUrl(location), {
            headers: {"X-Requested-With": "XMLHttpRequest"},
        })
            .then((r) => {
                if (r.status === 401) {
                    window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
                    return null;
                }
                if (!r.ok) {
                    throw new Error(`HTTP ${r.status}`);
                }
                return r.text();
            })
            .then((html) => {
                if (!html) {
                    return;
                }
                const body = document.getElementById("counterSettingsModalBody");
                const saveBtn = document.getElementById("counterSettingsSaveBtn");
                if (body) {
                    body.innerHTML = html;
                }
                if (saveBtn) {
                    saveBtn.disabled = false;
                }
                self.bindFormSubmit();
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
                .then((r) => {
                    if (r.status === 401) {
                        window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
                        return null;
                    }
                    if (!r.ok) {
                        throw new Error(`HTTP ${r.status}`);
                    }
                    return r.json();
                })
                .then((data) => {
                    if (!data) {
                        return;
                    }
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
     * Transliterate and slugify string into valid identifier (Latin letters, digits, underscores)
     *
     * @param {string} text - The input text
     * @returns {string} Sanitized field ID
     */
    slugifyIdentifier(text) {
        if (!text) return "";
        const ruMap = {
            "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
            "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
            "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts",
            "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
        };
        const str = String(text).toLowerCase().trim();
        let result = "";
        for (let i = 0; i < str.length; i++) {
            const ch = str[i];
            if (Object.prototype.hasOwnProperty.call(ruMap, ch)) {
                result += ruMap[ch];
            } else if (/[a-z0-9]/.test(ch)) {
                result += ch;
            } else if (/[\s\-_.,/\\|:;+*!@#$%^&()\[\]{}<>=~`'"]/.test(ch)) {
                result += "_";
            }
        }
        return result.replace(/_+/g, "_").replace(/^_+|_+$/g, "");
    },

    /**
     * Bind custom field management events (Add modal, Delete, Type change)
     *
     * @returns {void}
     */
    bindCustomFields() {
        const self = this;
        const modalAddEl = document.getElementById("addCustomFieldModal");
        const formAdd = document.getElementById("form-add-custom-field");
        const errAdd = document.getElementById("add-custom-field-error");
        const btnSubmit = document.getElementById("btn-submit-add-custom-field");
        const spinner = document.getElementById("spinner-add-custom-field");
        const selectScope = document.getElementById("new_field_scope");
        const selectType = document.getElementById("new_field_type");
        const rowOptions = document.getElementById("row-field-options");
        const inputLabel = document.getElementById("new_field_label");
        const inputName = document.getElementById("new_field_name");
        const btnRegenId = document.getElementById("btn-regen-field-id");
        let isNameManuallyEdited = false;

        if (inputLabel && inputName) {
            inputLabel.addEventListener("input", () => {
                if (!isNameManuallyEdited) {
                    inputName.value = self.slugifyIdentifier(inputLabel.value);
                }
            });
            inputName.addEventListener("input", () => {
                isNameManuallyEdited = inputName.value.trim().length > 0;
            });
        }

        if (btnRegenId && inputLabel && inputName) {
            btnRegenId.addEventListener("click", () => {
                inputName.value = self.slugifyIdentifier(inputLabel.value);
                isNameManuallyEdited = false;
                inputName.focus();
            });
        }

        if (selectType && rowOptions) {
            selectType.addEventListener("change", () => {
                if (selectType.value === "select") {
                    rowOptions.classList.remove("d-none");
                    rowOptions.querySelector("textarea")?.focus();
                } else {
                    rowOptions.classList.add("d-none");
                }
            });
        }

        if (modalAddEl) {
            modalAddEl.addEventListener("show.bs.modal", () => {
                setTimeout(() => {
                    const backdrops = document.querySelectorAll(".modal-backdrop");
                    if (backdrops.length > 1) {
                        backdrops[backdrops.length - 1].style.zIndex = "1065";
                    }
                }, 0);
            });
            modalAddEl.addEventListener("hidden.bs.modal", () => {
                if (document.querySelector(".modal.show")) {
                    document.body.classList.add("modal-open");
                }
            });
        }

        document.addEventListener("change", (e) => {
            const typeSelect = e.target.closest(".cv-custom-field-type-select");
            if (!typeSelect) return;
            const card = typeSelect.closest(".cv-custom-field-card");
            if (!card) return;

            const isSelect = typeSelect.value === "select";
            const optionsRow = card.querySelector(".cv-custom-field-options-row");
            const optionsInput = card.querySelector(".cv-custom-field-options-input");
            const typeBadge = card.querySelector(".cv-custom-field-badge-type");
            const iconBox = card.querySelector(".cv-custom-field-card__icon-box");

            if (typeBadge) {
                typeBadge.textContent = typeSelect.value;
            }
            if (iconBox) {
                const ftype = typeSelect.value;
                if (ftype === "number") {
                    iconBox.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" fill="currentColor" class="bi bi-123 text-success" viewBox="0 0 16 16"><path d="M2.873 11.297V4.142H1.699L0 5.379v1.137l1.64-1.18h.06v5.961zm3.213-5.09v-.063c0-.618.44-1.169 1.196-1.169.676 0 1.174.44 1.174 1.106 0 .624-.42 1.101-.807 1.526L4.99 10.553v.744h4.78v-.99H6.643v-.069L8.41 8.252c.65-.724 1.237-1.332 1.237-2.27C9.646 4.849 8.723 4 7.308 4c-1.573 0-2.36 1.064-2.36 2.15v.057zm6.559 1.883h.786c.823 0 1.374.481 1.379 1.179.01.707-.55 1.216-1.421 1.21-.77-.005-1.326-.419-1.379-.953h-1.095c.042 1.053.938 1.918 2.464 1.918 1.478 0 2.642-.839 2.62-2.144-.02-1.143-.922-1.651-1.551-1.714v-.063c.535-.09 1.347-.66 1.326-1.678-.026-1.053-.933-1.855-2.359-1.845-1.5.005-2.317.88-2.348 1.898h1.116c.032-.498.498-.944 1.206-.944.703 0 1.206.435 1.206 1.07.005.64-.504 1.106-1.2 1.106h-.75z"/></svg>';
                } else if (ftype === "textarea") {
                    iconBox.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" fill="currentColor" class="bi bi-text-paragraph text-info" viewBox="0 0 16 16"><path fill-rule="evenodd" d="M2 12.5a.5.5 0 0 1 .5-.5h7a.5.5 0 0 1 0 1h-7a.5.5 0 0 1-.5-.5m0-3a.5.5 0 0 1 .5-.5h11a.5.5 0 0 1 0 1h-11a.5.5 0 0 1-.5-.5m0-3a.5.5 0 0 1 .5-.5h11a.5.5 0 0 1 0 1h-11a.5.5 0 0 1-.5-.5m4-3a.5.5 0 0 1 .5-.5h7a.5.5 0 0 1 0 1h-7a.5.5 0 0 1-.5-.5"/></svg>';
                } else if (ftype === "date" || ftype === "datetime-local") {
                    iconBox.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" fill="currentColor" class="bi bi-calendar3 text-warning" viewBox="0 0 16 16"><path d="M14 0H2a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V2a2 2 0 0 0-2-2M1 3.857C1 3.384 1.448 3 2 3h12c.552 0 1 .384 1 .857v10.286c0 .473-.448.857-1 .857H2c-.552 0-1-.384-1-.857z"/><path d="M6.5 7a1 1 0 1 0 0-2 1 1 0 0 0 0 2m3 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2m3 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2m-9 3a1 1 0 1 0 0-2 1 1 0 0 0 0 2m3 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2m3 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2m3 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2m-9 3a1 1 0 1 0 0-2 1 1 0 0 0 0 2m3 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2m3 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2"/></svg>';
                } else if (ftype === "select") {
                    iconBox.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" fill="currentColor" class="bi bi-menu-button-wide text-primary" viewBox="0 0 16 16"><path d="M0 1.5A1.5 1.5 0 0 1 1.5 0h13A1.5 1.5 0 0 1 16 1.5v2A1.5 1.5 0 0 1 14.5 5h-13A1.5 1.5 0 0 1 0 3.5zM1.5 1a.5.5 0 0 0-.5.5v2a.5.5 0 0 0 .5.5h13a.5.5 0 0 0 .5-.5v-2a.5.5 0 0 0-.5-.5z"/><path d="M2 2.5a.5.5 0 0 1 .5-.5h3a.5.5 0 0 1 0 1h-3a.5.5 0 0 1-.5-.5m10.823.323-.396-.396A.25.25 0 0 1 12.604 2h.792a.25.25 0 0 1 .177.427l-.396.396a.25.25 0 0 1-.354 0M0 8a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2zm1 3v2a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-2zm14-1V8a1 1 0 0 0-1-1H2a1 1 0 0 0-1 1v2zM2 8.5a.5.5 0 0 1 .5-.5h9a.5.5 0 0 1 0 1h-9a.5.5 0 0 1-.5-.5m0 4a.5.5 0 0 1 .5-.5h6a.5.5 0 0 1 0 1h-6a.5.5 0 0 1-.5-.5"/></svg>';
                } else {
                    iconBox.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" fill="currentColor" class="bi bi-fonts text-primary" viewBox="0 0 16 16"><path d="M12.258 3h-8.51l-.083 2.46h.479c.26-1.544.758-1.783 2.693-1.845l.424-.013v7.827c0 .663-.144.82-1.3.923v.52h4.082v-.52c-1.162-.103-1.306-.26-1.306-.923V3.602l.431.013c1.934.062 2.434.301 2.693 1.846h.479z"/></svg>';
                }
            }

            if (optionsRow) {
                if (isSelect) {
                    optionsRow.classList.remove("d-none");
                    if (optionsInput) {
                        optionsInput.disabled = false;
                        optionsInput.focus();
                    }
                } else {
                    optionsRow.classList.add("d-none");
                    if (optionsInput) {
                        optionsInput.disabled = true;
                    }
                }
            }
        });

        document.addEventListener("input", (e) => {
            const labelInput = e.target.closest(".cv-custom-field-input-label");
            if (!labelInput) return;
            const card = labelInput.closest(".cv-custom-field-card");
            if (!card) return;
            const headerLabel = card.querySelector(".cv-custom-field-header-label");
            if (headerLabel) {
                headerLabel.textContent = labelInput.value.trim() || card.dataset.fieldName || "";
            }
        });

        // Open Add Custom Field Modal on click
        document.addEventListener("click", (e) => {
            const btnAdd = e.target.closest(".btn-add-custom-field");
            if (!btnAdd) return;

            const inCounterModal = btnAdd.closest("#counterSettingsModal");
            if (!inCounterModal && !modalAddEl) return;

            e.preventDefault();
            const loc = btnAdd.dataset.location || self._location || "";
            const scope = btnAdd.dataset.scope || (loc ? "detection" : "global");
            isNameManuallyEdited = false;

            if (formAdd) formAdd.reset();
            if (errAdd) {
                errAdd.classList.add("d-none");
                errAdd.textContent = "";
            }
            if (rowOptions) rowOptions.classList.add("d-none");

            if (selectScope) {
                if (scope === "detection" && loc) {
                    const targetVal = "detection:" + loc;
                    const matchOption = Array.from(selectScope.options).find((opt) => opt.value === targetVal);
                    if (matchOption) {
                        selectScope.value = targetVal;
                    } else {
                        const newOpt = document.createElement("option");
                        newOpt.value = targetVal;
                        newOpt.textContent = loc;
                        selectScope.appendChild(newOpt);
                        selectScope.value = targetVal;
                    }
                } else {
                    selectScope.value = "global";
                }
            }

            if (modalAddEl) {
                const modalInst = bootstrap.Modal.getOrCreateInstance(modalAddEl);
                modalInst.show();
                setTimeout(() => {
                    inputLabel?.focus();
                }, 200);
            }
        });

        // Submit Add Custom Field
        if (formAdd) {
            formAdd.addEventListener("submit", (e) => {
                e.preventDefault();
                if (errAdd) {
                    errAdd.classList.add("d-none");
                    errAdd.textContent = "";
                }

                const formData = new FormData(formAdd);
                const scopeTarget = formData.get("scope_target") || "global";
                let scope = "global";
                let loc = "";
                if (scopeTarget.startsWith("detection:")) {
                    scope = "detection";
                    loc = scopeTarget.substring("detection:".length);
                }

                const name = (formData.get("name") || "").trim();
                const label = (formData.get("label") || "").trim();
                const type = formData.get("type") || "text";
                const options = formData.get("options") || "";
                const defaultValue = (formData.get("default_value") || "").trim();

                if (!name) {
                    if (errAdd) {
                        errAdd.textContent = window.trans("Field name (ID) is required");
                        errAdd.classList.remove("d-none");
                    }
                    return;
                }

                if (!/^[a-zA-Z0-9_]+$/.test(name)) {
                    if (errAdd) {
                        errAdd.textContent = window.trans("Invalid field ID. Use Latin letters, digits, and underscores.");
                        errAdd.classList.remove("d-none");
                    }
                    return;
                }

                const payload = {
                    scope: scope,
                    location: loc,
                    name: name,
                    label: label || name,
                    type: type,
                    options: options,
                    default_value: defaultValue,
                };

                if (btnSubmit) btnSubmit.disabled = true;
                if (spinner) spinner.classList.remove("d-none");

                fetch("/settings/api/custom_fields/add", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-Requested-With": "XMLHttpRequest",
                    },
                    body: JSON.stringify(payload),
                })
                    .then((res) => res.json())
                    .then((data) => {
                        if (data && data.ok) {
                            showToast(data.message || window.trans("Field added successfully"), "success");
                            if (modalAddEl) {
                                const modalInst = bootstrap.Modal.getInstance(modalAddEl);
                                modalInst?.hide();
                            }
                            if (self._location) {
                                self.loadForm(self._location);
                            }
                        } else {
                            const msg = (data && data.error) ? data.error : window.trans("Failed to add field");
                            if (errAdd) {
                                errAdd.textContent = msg;
                                errAdd.classList.remove("d-none");
                            } else {
                                showToast(msg, "danger");
                            }
                        }
                    })
                    .catch((err) => {
                        const msg = (err && err.message) ? err.message : window.trans("Failed to add field");
                        if (errAdd) {
                            errAdd.textContent = msg;
                            errAdd.classList.remove("d-none");
                        } else {
                            showToast(msg, "danger");
                        }
                    })
                    .finally(() => {
                        if (btnSubmit) btnSubmit.disabled = false;
                        if (spinner) spinner.classList.add("d-none");
                    });
            });
        }

        // Delete Custom Field
        document.addEventListener("click", async (e) => {
            const btnDelete = e.target.closest(".btn-delete-custom-field");
            if (!btnDelete) return;
            const inCounterModal = btnDelete.closest("#counterSettingsModal");
            if (!inCounterModal) return;

            e.preventDefault();
            e.stopPropagation();

            const fieldName = btnDelete.dataset.fieldName;
            const fieldLabel = btnDelete.dataset.fieldLabel || fieldName;
            const loc = btnDelete.dataset.location || self._location || "";
            const scope = btnDelete.dataset.scope || (loc ? "detection" : "global");

            const confirmMsg = (window.trans ? window.trans("Are you sure you want to delete field \"{name}\"?", {name: fieldLabel}) : null)
                || `Are you sure you want to delete field "${fieldLabel}"?`;

            const confirmed = typeof window.appConfirm === "function"
                ? await window.appConfirm({
                    title: window.trans ? window.trans("Delete field") : "Delete field",
                    message: confirmMsg,
                    confirmText: window.trans ? window.trans("Delete") : "Delete",
                    tone: "danger",
                })
                : confirm(confirmMsg);

            if (!confirmed) {
                return;
            }

            btnDelete.disabled = true;
            fetch("/settings/api/custom_fields/delete", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: JSON.stringify({
                    scope: scope,
                    location: loc,
                    name: fieldName,
                }),
            })
                .then((res) => res.json())
                .then((data) => {
                    if (data && data.ok) {
                        showToast(data.message || window.trans("Field deleted successfully"), "success");
                        if (self._location) {
                            self.loadForm(self._location);
                        }
                    } else {
                        btnDelete.disabled = false;
                        showToast((data && data.error) ? data.error : window.trans("Failed to delete field"), "danger");
                    }
                })
                .catch((err) => {
                    btnDelete.disabled = false;
                    showToast((err && err.message) ? err.message : window.trans("Failed to delete field"), "danger");
                });
        });
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

        modal.show();
        this.loadForm(location);
    },

    /**
     * Initialize the counter settings modal
     *
     * @returns {void}
     */
    initialize() {
        const self = this;

        this.bindCustomFields();

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
