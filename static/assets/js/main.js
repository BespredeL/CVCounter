/**
 * Developed by: Aleksandr Kireev
 * Created: 01.11.2023
 * Updated: 04.09.2024
 * Website: https://bespredel.name
 */

/**
 * Set a cookie
 *
 * @param name
 * @param value
 * @param days
 */
function setCookie(name, value, days) {
    let expires = "";
    if (days) {
        const date = new Date();
        date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
        expires = "; expires=" + date.toGMTString();
    }
    document.cookie = name + "=" + value + expires + "; path=/";
}

/**
 * Get a cookie
 *
 * @param name
 * @returns {null|string}
 */
function getCookie(name) {
    const nameEQ = name + "=";
    const ca = document.cookie.split(';');
    for (let i = 0; i < ca.length; i++) {
        let c = ca[i];
        while (c.charAt(0) === ' ') c = c.substring(1, c.length);
        if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
    }
    return null;
}

/**
 * Delete a cookie
 *
 * @param name
 */
function deleteCookie(name) {
    document.cookie = name + '=; expires=Thu, 01 Jan 1970 00:00:01 GMT; path=/;';
}

/**
 * Set theme
 *
 * @param theme
 */
function setTheme(theme) {
    $('html').attr('data-bs-theme', theme);
    let themeSwitch = $('#theme-switch');
    if (theme === 'light') {
        themeSwitch.find('.bi-brightness-high').removeClass('d-none');
        themeSwitch.find('.bi-moon-stars').addClass('d-none');
    } else {
        themeSwitch.find('.bi-moon-stars').removeClass('d-none');
        themeSwitch.find('.bi-brightness-high').addClass('d-none');
    }
    setCookie('theme', theme, 365);
}

/**
 * Toggle fullscreen
 *
 * @returns {boolean}
 */
function toggleFullscreen() {
    const element = document.documentElement;

    if (!document.fullscreenElement && !document.webkitFullscreenElement && !document.mozFullScreenElement && !document.msFullscreenElement) {
        if (element.requestFullscreen) {
            element.requestFullscreen();
        } else if (element.webkitRequestFullscreen) { // Chrome, Safari, and Opera
            element.webkitRequestFullscreen();
        } else if (element.mozRequestFullScreen) { // Firefox
            element.mozRequestFullScreen();
        } else if (element.msRequestFullscreen) { // IE/Edge
            element.msRequestFullscreen();
        }

        return true;
    } else {
        if (document.exitFullscreen) {
            document.exitFullscreen();
        } else if (document.webkitExitFullscreen) { /* Safari */
            document.webkitExitFullscreen();
        } else if (document.mozCancelFullScreen) { /* Firefox */
            document.mozCancelFullScreen();
        } else if (document.msExitFullscreen) { /* IE11 */
            document.msExitFullscreen();
        }

        return false;
    }
}

$(function () {
    // Bootstrap Tooltip
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]')
    const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl))

    // Connection to the server socket IO
    window.socket = io();

    // Successful reconnection to the server socket IO
    socket.io.on("reconnect", (attempt) => {
        const alertContainer = $('#alert-container');
        const alertHtml = `
            <div class="alert alert-success mt-3 d-flex justify-content-between" role="alert">
                <span class="h3">${window.trans('Connection to server successful')}</span>
                <button id="reload-btn" class="btn btn-warning">${window.trans('Reload page')}</button>
            </div>`;

        alertContainer.html(alertHtml);

        $('#reload-btn').on('click', () => {
            location.reload();
        });

        const timerReload = setTimeout(() => {
            alertContainer.html('');
            location.reload();
        }, 1000 * 60 * 15);
    });

    // Error connecting to server socket IO
    window.socket.io.on("error", (error) => {
        const alertContainer = $('#alert-container');
        const alertHtml = `
            <div class="alert alert-danger mt-3 d-flex justify-content-between" role="alert">
                <span class="h3">${window.trans('Error connecting to the server. Contact the IT department.')}</span>
                <button id="reload-btn" class="btn btn-warning" id="reload-btn">${window.trans('Reload page')}</button>
            </div>`;

        alertContainer.html(alertHtml);

        $('#reload-btn').on('click', () => {
            location.reload();
        });

        /*const timerReload = setTimeout(() => {
            alertContainer.html('');
            location.reload();
        }, 1000 * 60 * 15);*/
    });

    // Toast notifications
    window.showToast = function (message, type = 'primary') {
        const toastContainer = document.getElementById('toast-container');
        if (!toastContainer) return;

        const toast = document.createElement("div");
        toast.className = `toast align-items-center text-bg-${type} border-0`;
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body user-select-none">${message}</div>
                <button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>`;
        toast.setAttribute("role", "alert");
        toast.setAttribute("aria-live", "assertive");
        toast.setAttribute("aria-atomic", "true");

        toastContainer.appendChild(toast);

        const bsToast = new bootstrap.Toast(toast);
        bsToast.show();

        toast.addEventListener('hidden.bs.toast', () => {
            toast.remove();
        });
    }

    // Setting the initial theme on page load
    $(document).ready(function () {
        let theme = getCookie('theme') || 'dark';
        setTheme(theme);
    });

    // Change theme by clicking on the switch
    $('#theme-switch').on('click', function () {
        let currentTheme = $('html').attr('data-bs-theme');
        let newTheme = currentTheme === 'light' ? 'dark' : 'light';
        setTheme(newTheme);
    });

    // Switching full screen mode
    $('#toggle-fullscreen').on('click', function () {
        if (toggleFullscreen()) {
            $(this).find('.bi-arrows-angle-expand').addClass('d-none');
            $(this).find('.bi-arrows-angle-contract').removeClass('d-none');
        } else {
            $(this).find('.bi-arrows-angle-expand').removeClass('d-none');
            $(this).find('.bi-arrows-angle-contract').addClass('d-none');
        }
    });
});
