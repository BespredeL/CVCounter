/**
 * Developed by: Aleksandr Kireev
 * Created: 04.09.2024
 * Updated: 18.12.2024
 * Website: https://bespredel.name
 */

/**
 * Save count
 *
 * @param {string} url - The endpoint to send data.
 */
function saveCount(url) {
    const defectCount = parseInt($('#defect_keyboard input').val()) || 0;
    const correctCount = parseInt($('#correct_keyboard input').val()) || 0;
    const customFields = {};

    $('.custom_field').each(function () {
        customFields[this.name] = this.value;
    });

    $.post(url, {
        correct_count: correctCount,
        defect_count: defectCount,
        custom_fields: JSON.stringify(customFields)
    }).done((data = {total_count: 0, defect_count: 0, correct_count: 0}) => {
        $("#total_count").html(data.total_count);
        $("#defect_keyboard input, #correct_keyboard input").val(0);
    });
}

/**
 * Reset count
 *
 * @param {string} url - The endpoint to reset counts.
 */
function resetCount(url) {
    $.get(url).done((data = {total_count: 0, defect_count: 0, correct_count: 0}) => {
        $("#total_count").html(data.total_count);
        $("#defect_keyboard input").val(data.defect_count || 0);
        $("#correct_keyboard input").val(data.correct_count || 0);

        $(".custom_field").each(function () {
            if ($(this).is(':checkbox, :radio')) {
                $(this).prop('checked', false);
            } else if ($(this).is('input, textarea')) {
                $(this).val('');
            } else if ($(this).is('select')) {
                $(this).prop('selectedIndex', 0);
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
    const defectCount = parseInt($('#defect_keyboard input').val()) || 0;
    const correctCount = parseInt($('#correct_keyboard input').val()) || 0;

    $.post(url, {
        correct_count: correctCount,
        defect_count: defectCount
    }).done((data = {current_count: 0, defect_count: 0, correct_count: 0}) => {
        $("#current_count").val(data.current_count);
        $("#defect_keyboard input").val(data.defect_count || 0);
        $("#correct_keyboard input").val(data.correct_count || 0);
    });
}

/**
 * Start count
 *
 * @param {string} url - The endpoint to start counting.
 */
function startCount(url) {
    $.get(url).done(() => {
        $('#btn_pause').removeClass('btn-warning').addClass('btn-outline-secondary');
        $('#btn_start').removeClass('btn-info').addClass('btn-outline-secondary');
        $('#pause_display').removeClass('d-flex').addClass('d-none');
    });
}

/**
 * Pause count
 *
 * @param {string} url - The endpoint to pause counting.
 */
function pauseCount(url) {
    $.get(url).done(() => {
        $('#btn_pause').removeClass('btn-outline-secondary').addClass('btn-warning');
        $('#btn_start').removeClass('btn-outline-secondary').addClass('btn-info');
        $('#pause_display').removeClass('d-none').addClass('d-flex');
    });
}


/**
 * Save capture
 *
 * @param {string} url - The endpoint to save capture.
 */
function saveCapture(url) {
    $.get(url).done((data) => {
        const statusClass = data.status === 'saved' ? 'btn-success' : 'btn-danger';
        const btn = document.getElementById('save-capture');
        btn.classList.add(statusClass);
        setTimeout(() => {
            btn.classList.remove(statusClass);
        }, 500);
    });
}