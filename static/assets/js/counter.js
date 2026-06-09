/**
 * Developed by: Aleksandr Kireev
 * Created: 04.09.2024
 * Updated: 08.06.2026
 * Website: https://bespredel.name
 */

/**
 * @param {string} selector
 * @returns {number}
 */
function counterInputValue(selector) {
    return parseInt(document.querySelector(selector)?.value, 10) || 0;
}

/**
 * @param {string} selector
 * @param {string|number} value
 */
function setCounterInputValue(selector, value) {
    document.querySelectorAll(selector).forEach((el) => {
        el.value = value;
    });
}

/**
 * @param {string} id
 * @param {string|number} value
 */
function setCounterDisplay(id, value) {
    const el = document.getElementById(id);
    if (el) {
        el.textContent = value;
    }
}

/**
 * Save count
 *
 * @param {string} url - The endpoint to send data.
 */
function saveCount(url) {
    const defectCount = counterInputValue("#defect_keyboard input");
    const correctCount = counterInputValue("#correct_keyboard input");
    const customFields = {};

    document.querySelectorAll(".custom_field").forEach((el) => {
        customFields[el.name] = el.value;
    });

    fetch(url, {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body: new URLSearchParams({
            correct_count: correctCount,
            defect_count: defectCount,
            custom_fields: JSON.stringify(customFields),
        }),
    })
        .then((r) => r.json())
        .then((data = {total_count: 0}) => {
            setCounterDisplay("total_count", data.total_count);
            setCounterInputValue("#defect_keyboard input, #correct_keyboard input", 0);
        });
}

/**
 * Reset count
 *
 * @param {string} url - The endpoint to reset counts.
 */
function resetCount(url) {
    fetch(url)
        .then((r) => r.json())
        .then((data = {total_count: 0, defect_count: 0, correct_count: 0}) => {
            setCounterDisplay("total_count", data.total_count);
            setCounterInputValue("#defect_keyboard input", data.defect_count || 0);
            setCounterInputValue("#correct_keyboard input", data.correct_count || 0);

            document.querySelectorAll(".custom_field").forEach((el) => {
                if (el.matches(":checkbox, :radio")) {
                    el.checked = false;
                } else if (el.matches("input, textarea")) {
                    el.value = "";
                } else if (el.tagName === "SELECT") {
                    el.selectedIndex = 0;
                }
            });
        });
}

/**
 * Reset count current
 *
 * @param {string} url - The endpoint to reset current counts.
 */
function resetCountCurrent(url) {
    const defectCount = counterInputValue("#defect_keyboard input");
    const correctCount = counterInputValue("#correct_keyboard input");

    fetch(url, {
        method: "POST",
        headers: {"Content-Type": "application/x-www-form-urlencoded"},
        body: new URLSearchParams({
            correct_count: correctCount,
            defect_count: defectCount,
        }),
    })
        .then((r) => r.json())
        .then((data = {current_count: 0, defect_count: 0, correct_count: 0}) => {
            setCounterDisplay("current_count", data.current_count);
            setCounterInputValue("#defect_keyboard input", data.defect_count || 0);
            setCounterInputValue("#correct_keyboard input", data.correct_count || 0);
        });
}

/**
 * @param {boolean} paused
 */
function setPauseUI(paused) {
    const btnPause = document.getElementById("btn_pause");
    const btnStart = document.getElementById("btn_start");
    const pauseDisplay = document.getElementById("pause_display");

    if (!btnPause || !btnStart || !pauseDisplay) {
        return;
    }

    if (paused) {
        btnPause.classList.remove("btn-outline-secondary");
        btnPause.classList.add("btn-warning");
        btnStart.classList.remove("btn-outline-secondary");
        btnStart.classList.add("btn-info");
        pauseDisplay.classList.remove("d-none");
        pauseDisplay.classList.add("d-flex");
    } else {
        btnPause.classList.remove("btn-warning");
        btnPause.classList.add("btn-outline-secondary");
        btnStart.classList.remove("btn-info");
        btnStart.classList.add("btn-outline-secondary");
        pauseDisplay.classList.remove("d-flex");
        pauseDisplay.classList.add("d-none");
    }
}

/**
 * Start count
 *
 * @param {string} url - The endpoint to start counting.
 */
function startCount(url) {
    fetch(url).then(() => setPauseUI(false));
}

/**
 * Pause count
 *
 * @param {string} url - The endpoint to pause counting.
 */
function pauseCount(url) {
    fetch(url).then(() => setPauseUI(true));
}

/**
 * Save capture
 *
 * @param {string} url - The endpoint to save capture.
 */
function saveCapture(url) {
    fetch(url)
        .then((r) => r.json())
        .then((data) => {
            const statusClass = data.status === "saved" ? "btn-success" : "btn-danger";
            const btn = document.getElementById("save-capture");

            if (!btn) {
                return;
            }

            btn.classList.add(statusClass);
            setTimeout(() => {
                btn.classList.remove(statusClass);
            }, 500);
        });
}
