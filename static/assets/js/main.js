/**
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

    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body user-select-none">${message}</div>
            <button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>`;

    toastContainer.appendChild(toast);

    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();
    toast.addEventListener("hidden.bs.toast", () => toast.remove());
}

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
});