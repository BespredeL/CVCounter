/**
 * Computer Vision Counter (CVCounter)
 * Main application client script (theme, fullscreen, toasts, dialogs).
 *
 * Developed by: Aleksandr Kireev
 * Created: 01.11.2023
 * Updated: 08.06.2026
 * Website: https://bespredel.name
 */

/**
 * Utility to manage cookies
 */
const CookieUtil = {
    /**
     * Set a cookie
     *
     * @param {string} name - The name of the cookie
     * @param {string} value - The value of the cookie
     * @param {number} days - The number of days to expire the cookie
     */
    set(name, value, days) {
        let expires = "";
        if (days) {
            const date = new Date();
            date.setTime(date.getTime() + days * 24 * 60 * 60 * 1000);
            expires = "; expires=" + date.toUTCString();
        }
        document.cookie = `${name}=${value}${expires}; path=/`;
    },

    /**
     * Get a cookie
     *
     * @param {string} name - The name of the cookie
     * @returns {string} - The value of the cookie
     */
    get(name) {
        const nameEQ = `${name}=`;
        return document.cookie
            .split(';')
            .map(cookie => cookie.trim())
            .find(cookie => cookie.startsWith(nameEQ))?.substring(nameEQ.length) || null;
    },

    /**
     * Delete a cookie
     *
     * @param {string} name - The name of the cookie
     */
    delete(name) {
        this.set(name, "", -1);
    },
};

/**
 * Theme management
 */
const ThemeManager = {
    /**
     * Set the theme
     *
     * @param {string} theme - The theme to set
     */
    set(theme) {
        document.documentElement.setAttribute("data-bs-theme", theme);
        const themeSwitch = document.getElementById("theme-switch");
        if (themeSwitch) {
            themeSwitch.querySelector(".bi-brightness-high")?.classList.toggle("d-none", theme !== "light");
            themeSwitch.querySelector(".bi-moon-stars")?.classList.toggle("d-none", theme === "light");
        }
        CookieUtil.set("theme", theme, 365);

        const metaTheme = document.querySelector('meta[name="theme-color"]:not([media])');
        if (metaTheme) {
            metaTheme.content = theme === "light" ? "#f4f6f9" : "#16181d";
        }
    },

    /**
     * Toggle the theme
     *
     * @returns {void}
     */
    toggle() {
        const currentTheme = document.documentElement.getAttribute("data-bs-theme") || "dark";
        this.set(currentTheme === "light" ? "dark" : "light");
    },

    /**
     * Initialize the theme manager
     *
     * @returns {void}
     */
    initialize() {
        this.set(CookieUtil.get("theme") || "dark");
        document.getElementById("theme-switch")?.addEventListener("click", () => this.toggle());

        let printOriginalTheme = null;
        window.addEventListener("beforeprint", () => {
            printOriginalTheme = document.documentElement.getAttribute("data-bs-theme") || "dark";
            document.documentElement.setAttribute("data-bs-theme", "light");
            document.documentElement.style.setProperty("color-scheme", "light");
            document.documentElement.style.setProperty("background-color", "#ffffff", "important");
            document.body.style.setProperty("background-color", "#ffffff", "important");
        });
        window.addEventListener("afterprint", () => {
            if (printOriginalTheme) {
                document.documentElement.setAttribute("data-bs-theme", printOriginalTheme);
            }
            document.documentElement.style.removeProperty("color-scheme");
            document.documentElement.style.removeProperty("background-color");
            document.body.style.removeProperty("background-color");
        });
    },
};

/**
 * Fullscreen management
 */
const FullscreenManager = {
    /**
     * Toggle the fullscreen mode
     *
     * @returns {boolean} - The new fullscreen state
     */
    toggle() {
        const doc = document;
        const elem = document.documentElement;

        if (!doc.fullscreenElement) {
            elem.requestFullscreen?.() || elem.webkitRequestFullscreen?.() || elem.mozRequestFullScreen?.() || elem.msRequestFullscreen?.();
            return true;
        } else {
            doc.exitFullscreen?.() || doc.webkitExitFullscreen?.() || doc.mozCancelFullScreen?.() || doc.msExitFullscreen?.();
            return false;
        }
    },

    /**
     * Initialize the fullscreen manager
     */
    initialize() {
        document.getElementById("toggle-fullscreen")?.addEventListener("click", function () {
            const isFullscreen = FullscreenManager.toggle();
            this.querySelector(".bi-arrows-angle-expand")?.classList.toggle("d-none", isFullscreen);
            this.querySelector(".bi-arrows-angle-contract")?.classList.toggle("d-none", !isFullscreen);
        });
    },
};

/**
 * Show toast notifications
 *
 * @param {string} message - The message to show
 * @param {string} [type="primary"] - The type of toast
 */
function showToast(message, type = "primary") {
    const toastContainer = document.getElementById("toast-container");
    if (!toastContainer) return;

    const toast = document.createElement("div");
    toast.className = `toast align-items-center text-bg-${type} border-0`;
    toast.setAttribute("role", "alert");
    toast.setAttribute("aria-live", "assertive");
    toast.setAttribute("aria-atomic", "true");

    const body = document.createElement("div");
    body.className = "toast-body user-select-none";
    body.textContent = String(message ?? "");

    const closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "btn-close me-2 m-auto";
    closeBtn.setAttribute("data-bs-dismiss", "toast");
    closeBtn.setAttribute("aria-label", "Close");

    const row = document.createElement("div");
    row.className = "d-flex";
    row.appendChild(body);
    row.appendChild(closeBtn);
    toast.appendChild(row);

    toastContainer.appendChild(toast);

    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    toast.addEventListener("hidden.bs.toast", () => toast.remove());
}

window.showToast = showToast;

/**
 * App dialog (confirm / alert) on top of Bootstrap Modal.
 */
const AppDialog = {
    _modal: null,
    _resolver: null,
    _els: null,

    _ensure() {
        if (this._modal) return true;
        const root = document.getElementById("app-dialog");
        if (!root || typeof bootstrap === "undefined") return false;
        this._els = {
            root,
            title: document.getElementById("app-dialog-title"),
            message: document.getElementById("app-dialog-message"),
            cancel: document.getElementById("app-dialog-cancel"),
            confirm: document.getElementById("app-dialog-confirm"),
        };
        this._modal = bootstrap.Modal.getOrCreateInstance(root, {
            backdrop: "static",
            keyboard: true,
        });
        this._els.confirm.addEventListener("click", () => this._finish(true));
        this._els.cancel.addEventListener("click", () => this._finish(false));
        root.addEventListener("hidden.bs.modal", () => {
            if (this._resolver) this._finish(false);
        });
        return true;
    },

    _finish(result) {
        const resolve = this._resolver;
        this._resolver = null;
        if (resolve) resolve(result);
        try {
            this._modal?.hide();
        } catch (_) {
            /* already closing */
        }
    },

    _open({ title, message, confirmText, cancelText, tone, showCancel }) {
        if (!this._ensure()) {
            if (showCancel) return Promise.resolve(window.confirm(String(message ?? "")));
            window.alert(String(message ?? ""));
            return Promise.resolve(true);
        }

        if (this._resolver) this._finish(false);

        const t = (key) => (typeof window.trans === "function" ? window.trans(key) : key);
        this._els.root.classList.remove("app-dialog--danger", "app-dialog--warning");
        if (tone === "danger" || tone === "warning") {
            this._els.root.classList.add(`app-dialog--${tone}`);
        }
        this._els.title.textContent = title || t("Confirm");
        this._els.message.textContent = String(message ?? "");
        this._els.confirm.textContent = confirmText || t("OK");
        this._els.confirm.className = `btn ${tone === "danger" ? "btn-danger" : tone === "warning" ? "btn-warning" : "btn-primary"}`;
        this._els.cancel.textContent = cancelText || t("Cancel");
        this._els.cancel.classList.toggle("d-none", !showCancel);

        return new Promise((resolve) => {
            this._resolver = resolve;
            this._modal.show();
            requestAnimationFrame(() => this._els.confirm.focus());
        });
    },

    confirm(options = {}) {
        if (typeof options === "string") options = { message: options };
        return this._open({
            title: options.title,
            message: options.message,
            confirmText: options.confirmText,
            cancelText: options.cancelText,
            tone: options.tone || "primary",
            showCancel: true,
        });
    },

    alert(options = {}) {
        if (typeof options === "string") options = { message: options };
        return this._open({
            title: options.title || (typeof window.trans === "function" ? window.trans("Notice") : "Notice"),
            message: options.message,
            confirmText: options.okText || options.confirmText,
            tone: options.tone || "primary",
            showCancel: false,
        }).then(() => undefined);
    },
};

window.AppDialog = AppDialog;
window.appConfirm = (opts) => AppDialog.confirm(opts);
window.appAlert = (opts) => AppDialog.alert(opts);

/**
 * Show flashed toasts rendered server-side
 */
function showFlashedToasts() {
    document.querySelectorAll(".toast-show").forEach((el) => {
        new bootstrap.Toast(el).show();
    });
}

/**
 * Initialize application
 */
document.addEventListener("DOMContentLoaded", () => {
    showFlashedToasts();

    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => new bootstrap.Tooltip(el));

    const socketOptions = window.SOCKETIO_OPTIONS || {
        path: "/socket.io",
        transports: ["polling", "websocket"],
        upgrade: true,
        reconnection: true,
    };
    const socket = (window.socket = io(socketOptions));

    socket.io.on("reconnect", () => {
        const alertHtml = `
            <div class="alert alert-success mt-3 d-flex justify-content-between" role="alert">
                <span class="h3">${window.trans("Connection to server successful")}</span>
                <button id="reload-btn" class="btn btn-warning">${window.trans("Reload page")}</button>
            </div>`;

        const alertContainer = document.getElementById("alert-container");
        if (alertContainer) {
            alertContainer.innerHTML = alertHtml;
            document.getElementById("reload-btn")?.addEventListener("click", () => location.reload());
        }

        setTimeout(() => {
            alertContainer?.replaceChildren();
            location.reload();
        }, 1000 * 60 * 15);
    });

    socket.on("connect_error", () => {
        const alertHtml = `
            <div class="alert alert-danger mt-3 d-flex justify-content-between" role="alert">
                <span class="h3">${window.trans("Error connecting to the server. Contact the IT department.")}</span>
                <button id="reload-btn" class="btn btn-warning">${window.trans("Reload page")}</button>
            </div>`;

        const alertContainer = document.getElementById("alert-container");
        if (alertContainer) {
            alertContainer.innerHTML = alertHtml;
            document.getElementById("reload-btn")?.addEventListener("click", () => location.reload());
        }
    });

    ThemeManager.initialize();
    FullscreenManager.initialize();

    document.getElementById("btn-logout")?.addEventListener("click", async () => {
        const btn = document.getElementById("btn-logout");
        const logoutUrl = btn?.dataset.logoutUrl || "/logout";
        const t = (key) => (typeof window.trans === "function" ? window.trans(key) : key);

        const ok = typeof window.appConfirm === "function"
            ? await window.appConfirm({
                title: t("Log out"),
                message: t("Log out of the application?"),
                confirmText: t("Log out"),
                tone: "warning",
            })
            : window.confirm(t("Log out of the application?"));
        if (!ok) return;

        window.location.assign(logoutUrl);
    });
});
