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

// Override native alert to always use the stylized Bootstrap app dialog
const _nativeAlert = window.alert;
window.alert = function (message) {
    if (window.AppDialog && typeof window.AppDialog.alert === "function") {
        return window.AppDialog.alert({
            title: typeof window.trans === "function" ? window.trans("Notice") : "Notice",
            message: String(message ?? ""),
            tone: "warning",
        });
    }
    return _nativeAlert ? _nativeAlert.call(window, message) : undefined;
};

/**
 * Trigger graceful application server restart via web control
 */
window.restartServer = async function () {
    const title = typeof window.trans === "function" ? window.trans("Restart server") : "Restart server";
    const message = typeof window.trans === "function"
        ? window.trans("Are you sure you want to restart the application server? Video streams and active connections will be temporarily interrupted.")
        : "Are you sure you want to restart the application server? Video streams and active connections will be temporarily interrupted.";
    const confirmText = typeof window.trans === "function" ? window.trans("Restart") : "Restart";
    const cancelText = typeof window.trans === "function" ? window.trans("Cancel") : "Cancel";

    const confirmed = await window.appConfirm({
        title: title,
        message: message,
        confirmText: confirmText,
        cancelText: cancelText,
        tone: "danger",
    });

    if (!confirmed) return;

    // Show persistent restart modal
    const restartModalEl = document.getElementById("server-restart-modal");
    let bsModal = null;
    if (restartModalEl && window.bootstrap) {
        bsModal = new bootstrap.Modal(restartModalEl, { backdrop: "static", keyboard: false });
        bsModal.show();
    } else if (window.appAlert) {
        window.appAlert({
            title: title,
            message: typeof window.trans === "function"
                ? window.trans("Please wait, the server is restarting. This page will reload automatically.")
                : "Please wait, the server is restarting. This page will reload automatically.",
            tone: "info",
        });
    }

    try {
        const resp = await fetch("/settings/api/restart", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest",
            },
        });
        const data = await resp.json().catch(() => ({}));
        if (!resp.ok || (!data.ok && !data.success)) {
            if (bsModal) bsModal.hide();
            await window.appAlert({
                title: typeof window.trans === "function" ? window.trans("Error") : "Error",
                message: data.error || (typeof window.trans === "function" ? window.trans("Failed to initiate server restart") : "Failed to initiate server restart"),
                tone: "danger",
            });
            return;
        }
    } catch (err) {
        console.warn("Restart request sent (server is shutting down):", err);
    }

    // Poll until server is back online
    let attempts = 0;
    const maxAttempts = 60;
    const pollInterval = setInterval(async () => {
        attempts++;
        try {
            const check = await fetch("/?_ping=" + Date.now(), { method: "HEAD", cache: "no-store" });
            if (check.ok || check.status === 200 || check.status === 302) {
                clearInterval(pollInterval);
                window.location.reload();
            }
        } catch (e) {
            // Still waiting for server process to restart and bind
        }
        if (attempts >= maxAttempts) {
            clearInterval(pollInterval);
            window.location.reload();
        }
    }, 1500);
};

// Global click listener for any server restart trigger button
document.addEventListener("click", function (e) {
    const btn = e.target.closest(".btn-restart-server-trigger");
    if (btn) {
        e.preventDefault();
        window.restartServer();
    }
});

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
        Diagnostics.addBreadcrumb("network", "socket_connect_error");
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
    Diagnostics.initialize();
    initSystemDoctor();

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

/**
 * Frontend Diagnostics and Error Telemetry
 */
const Diagnostics = {
    breadcrumbs: [],
    maxBreadcrumbs: 15,
    recentErrors: new Map(),

    addBreadcrumb(category, message, data = {}) {
        this.breadcrumbs.push({
            ts: new Date().toISOString(),
            category: String(category || "info"),
            message: String(message || "").slice(0, 100),
            data: data && typeof data === "object" ? data : {},
        });
        if (this.breadcrumbs.length > this.maxBreadcrumbs) {
            this.breadcrumbs.shift();
        }
    },

    track(eventName, props = {}) {
        this.addBreadcrumb("event", eventName, props);
        this.send({
            type: "usage",
            name: eventName,
            props: props,
        });
    },

    captureError(err, context = {}) {
        const message = String(err?.message || err || "Unknown client error").slice(0, 500);
        const stack = String(err?.stack || "").slice(0, 4000);
        const dedupKey = `${message}:${context.filename || ""}:${context.lineno || ""}`;
        const now = Date.now();
        const lastSent = this.recentErrors.get(dedupKey);
        if (lastSent && (now - lastSent) < 60000) {
            return;
        }
        this.recentErrors.set(dedupKey, now);

        this.addBreadcrumb("error", message);
        this.send({
            type: "error",
            name: "client_javascript_error",
            error: {
                type: err?.name || "JavaScriptError",
                message: message,
                stack: stack,
            },
            props: {
                url: window.location.pathname + window.location.search,
                line: context.lineno || 0,
                col: context.colno || 0,
                breadcrumbs: this.breadcrumbs,
                ...context,
            },
        });
    },

    send(payload) {
        try {
            const data = JSON.stringify(payload);
            const endpoint = "/api/telemetry/client-event";
            if (navigator.sendBeacon) {
                const blob = new Blob([data], { type: "application/json" });
                navigator.sendBeacon(endpoint, blob);
            } else {
                fetch(endpoint, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: data,
                    keepalive: true,
                }).catch(() => {});
            }
        } catch (_) {}
    },

    initialize() {
        window.addEventListener("error", (event) => {
            Diagnostics.captureError(event.error || event.message, {
                filename: event.filename,
                lineno: event.lineno,
                colno: event.colno,
            });
        });

        window.addEventListener("unhandledrejection", (event) => {
            Diagnostics.captureError(event.reason || "Unhandled Promise rejection", {
                type: "unhandledrejection",
            });
        });

        document.addEventListener("click", (e) => {
            const target = e.target.closest("button, a, input[type='submit']");
            if (target) {
                const label = (target.innerText || target.value || target.title || target.id || "").trim().slice(0, 40);
                Diagnostics.addBreadcrumb("ui_click", label, {
                    id: target.id || undefined,
                    tagName: target.tagName,
                });
            }
        }, { passive: true });

        Diagnostics.addBreadcrumb("navigation", "page_load", { path: window.location.pathname });
        window.Diagnostics = Diagnostics;
    },
};

/**
 * System Doctor interactive UI handler
 */
function initSystemDoctor() {
    const btn = document.getElementById("btn-run-doctor");
    const container = document.getElementById("system-doctor-results");
    if (!btn || !container) return;

    btn.addEventListener("click", async () => {
        btn.disabled = true;
        const origHtml = btn.innerHTML;
        const t = (key) => (typeof window.trans === "function" ? window.trans(key) : key);
        btn.innerHTML = `<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>${t("Running diagnostics...")}`;
        container.classList.remove("d-none");
        container.innerHTML = `
            <div class="p-3 text-center text-body-secondary">
                <div class="spinner-border text-primary mb-2" role="status"></div>
                <div>${t("Running diagnostics...")}</div>
            </div>`;

        try {
            const res = await fetch("/settings/system_doctor");
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            renderDoctorResults(container, data, t);
        } catch (err) {
            container.innerHTML = `
                <div class="alert alert-danger mb-0">
                    <i class="bi bi-x-circle me-1"></i>${t("Failed to run diagnostics")}: ${err.message}
                </div>`;
        } finally {
            btn.disabled = false;
            btn.innerHTML = origHtml;
        }
    });
}

function renderDoctorResults(container, data, t) {
    const checks = data.checks || [];
    const allOk = data.all_ok;
    const alertClass = allOk ? "alert-success" : "alert-warning";
    const headerTitle = allOk ? t("System doctor completed. All checks passed!") : t("System doctor found issues.");

    let listHtml = checks.map(c => {
        let badgeClass = "bg-success";
        let icon = "bi-check-circle-fill text-success";
        if (c.status === "error") {
            badgeClass = "bg-danger";
            icon = "bi-x-circle-fill text-danger";
        } else if (c.status === "warning") {
            badgeClass = "bg-warning text-dark";
            icon = "bi-exclamation-triangle-fill text-warning";
        } else if (c.status === "info") {
            badgeClass = "bg-info text-dark";
            icon = "bi-info-circle-fill text-info";
        }
        return `
            <li class="list-group-item d-flex justify-content-between align-items-start py-2">
                <div class="ms-2 me-auto">
                    <div class="fw-semibold"><i class="bi ${icon} me-1"></i>${t(c.title)}</div>
                    <small class="text-body-secondary">${t(c.details) || c.details || ""}</small>
                </div>
                <span class="badge ${badgeClass} rounded-pill text-uppercase">${c.status}</span>
            </li>`;
    }).join("");

    container.innerHTML = `
        <div class="alert ${alertClass} mb-3 py-2 px-3 fw-semibold">
            ${headerTitle}
        </div>
        <ul class="list-group mb-0">
            ${listHtml}
        </ul>`;
}
