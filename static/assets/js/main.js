/**
 * Developed by: Aleksandr Kireev
 * Created: 01.11.2023
 * Updated: 18.12.2024
 * Website: https://bespredel.name
 */

/**
 * Utility to manage cookies
 */
const CookieUtil = {
    set(name, value, days) {
        let expires = "";
        if (days) {
            const date = new Date();
            date.setTime(date.getTime() + days * 24 * 60 * 60 * 1000);
            expires = "; expires=" + date.toUTCString();
        }
        document.cookie = `${name}=${value}${expires}; path=/`;
    },

    get(name) {
        const nameEQ = `${name}=`;
        return document.cookie
            .split(';')
            .map(cookie => cookie.trim())
            .find(cookie => cookie.startsWith(nameEQ))?.substring(nameEQ.length) || null;
    },

    delete(name) {
        this.set(name, "", -1);
    },
};

/**
 * Theme management
 */
const ThemeManager = {
    set(theme) {
        $("html").attr("data-bs-theme", theme);
        const themeSwitch = $("#theme-switch");
        themeSwitch.find(".bi-brightness-high").toggleClass("d-none", theme !== "light");
        themeSwitch.find(".bi-moon-stars").toggleClass("d-none", theme === "light");
        CookieUtil.set("theme", theme, 365);
    },

    toggle() {
        const currentTheme = $("html").attr("data-bs-theme") || "dark";
        this.set(currentTheme === "light" ? "dark" : "light");
    },

    initialize() {
        this.set(CookieUtil.get("theme") || "dark");
        $("#theme-switch").on("click", () => this.toggle());
    },
};

/**
 * Fullscreen management
 */
const FullscreenManager = {
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

    initialize() {
        $("#toggle-fullscreen").on("click", function () {
            const isFullscreen = FullscreenManager.toggle();
            $(this).find(".bi-arrows-angle-expand").toggleClass("d-none", isFullscreen);
            $(this).find(".bi-arrows-angle-contract").toggleClass("d-none", !isFullscreen);
        });
    },
};

/**
 * Show toast notifications
 *
 * @param {string} message
 * @param {string} [type="primary"]
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
 * Initialize application
 */
$(function () {
    // Bootstrap tooltips
    document.querySelectorAll('[data-bs-toggle="tooltip"]')
        .forEach(el => new bootstrap.Tooltip(el));

    // Socket.IO connection management
    const socket = (window.socket = io());

    socket.io.on("reconnect", () => {
        const alertHtml = `
            <div class="alert alert-success mt-3 d-flex justify-content-between" role="alert">
                <span class="h3">${window.trans("Connection to server successful")}</span>
                <button id="reload-btn" class="btn btn-warning">${window.trans("Reload page")}</button>
            </div>`;

        $("#alert-container").html(alertHtml);

        $("#reload-btn").on("click", () => location.reload());

        setTimeout(() => {
            $("#alert-container").empty();
            location.reload();
        }, 1000 * 60 * 15);
    });

    socket.io.on("error", () => {
        const alertHtml = `
            <div class="alert alert-danger mt-3 d-flex justify-content-between" role="alert">
                <span class="h3">${window.trans("Error connecting to the server. Contact the IT department.")}</span>
                <button id="reload-btn" class="btn btn-warning">${window.trans("Reload page")}</button>
            </div>`;

        $("#alert-container").html(alertHtml);

        $("#reload-btn").on("click", () => location.reload());
    });

    ThemeManager.initialize();
    FullscreenManager.initialize();
});
