// Set a cookie
function setCookie(name, value, days) {
    let expires = "";
    if (days) {
        const date = new Date();
        date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
        expires = "; expires=" + date.toGMTString();
    }
    document.cookie = name + "=" + value + expires + "; path=/";
}

// Get a cookie value
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

// Delete a cookie
function deleteCookie(name) {
    document.cookie = name + '=; expires=Thu, 01 Jan 1970 00:00:01 GMT; path=/;';
}

$(function () {
    // Bootstrap Tooltip
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]')
    const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl))

    // Соединение с сервером
    window.socket = io();
    let timerReload = 0;

    // Успешное переподключение к серверу
    socket.io.on("reconnect", (attempt) => {
        $('#alert-container').html(
            '<div class="alert alert-success mt-3 d-flex justify-content-between" role="alert">' +
            '<span class="h3">Соединение с сервером установлено</span>' +
            '<a href="#" onclick="location.reload()" class="btn btn-warning">Перезагрузить страницу</a>' +
            '</div>'
        );

        timerReload = setTimeout(function () {
            $('#alert-container').html('');
            location.reload();
        }, 1000 * 60 * 15);
    });

    // Ошибка соединения с сервером
    window.socket.io.on("error", (error) => {
        $('#alert-container').html(
            '<div class="alert alert-danger mt-3 d-flex justify-content-between" role="alert">' +
            '<span class="h3">Ошибка соединения с сервером. Обратитесь в IT отдел.</span>' +
            '<a href="#" onclick="location.reload()" class="btn btn-warning" id="reload-btn"> Перезагрузить страницу</a>' +
            '</div>'
        );

        /*setTimeout(function () {
            $('#reload-btn').removeClass('d-none');
        }, 60 * 2 * 1000);

        timerReload && clearTimeout(timerReload);*/
    });

    // Всплывающие уведомления
    window.showToast = function (message, type = 'primary') {
        let toast = document.createElement("div");
        toast.className = "toast align-items-center text-bg-" + type + " border-0";
        //toast.textContent = message;
        toast.innerHTML = '<div class="d-flex">' +
            '<div class="toast-body">' + message + '</div>' +
            '<button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>' +
            '</div>'
        toast.setAttribute("role", "alert");
        toast.setAttribute("aria-live", "assertive");
        toast.setAttribute("aria-atomic", "true");

        document.getElementById('toast-container').appendChild(toast);

        let bsToast = new bootstrap.Toast(toast);
        bsToast.show();
    }

    // Смена темы
    $('html').attr('data-bs-theme', function () {
        let theme = getCookie('theme') || 'dark';
        let themeSwitch = $('#theme-switch');
        if (theme === 'light') {
            themeSwitch.find('.bi-brightness-high').addClass('d-none');
            themeSwitch.find('.bi-moon-stars').removeClass('d-none');
        } else {
            themeSwitch.find('.bi-moon-stars').addClass('d-none');
            themeSwitch.find('.bi-brightness-high').removeClass('d-none');
        }
        return theme;
    });

    $('#theme-switch').on('click', function () {
        let theme = $('html').attr('data-bs-theme');
        let themeSwitch = $('#theme-switch');
        if (theme === 'light') {
            $('html').attr('data-bs-theme', 'dark');
            themeSwitch.find('.bi-brightness-high').removeClass('d-none');
            themeSwitch.find('.bi-moon-stars').addClass('d-none');
            setCookie('theme', 'dark', 365);
        } else {
            $('html').attr('data-bs-theme', 'light');
            themeSwitch.find('.bi-moon-stars').removeClass('d-none');
            themeSwitch.find('.bi-brightness-high').addClass('d-none');
            setCookie('theme', 'light', 365);
        }
    });

    // Bootstrap Select
    //$('.selectpicker').selectpicker();
});
