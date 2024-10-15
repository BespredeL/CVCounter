/**
 * Developed by: Aleksandr Kireev
 * Created: 04.09.2024
 * Updated: 04.09.2024
 * Website: https://bespredel.name
 */

/**
 * Save count
 *
 * @param url
 */
function saveCount(url) {
    let defect_count = $('#defect_keyboard input').val() || 0;
    let correct_count = $('#correct_keyboard input').val() || 0;
    let custom_fields = {};

    $('.custom_field').each(function () {
        custom_fields[this.name] = this.value;
    });

    $.ajax({
        url: url,
        method: 'post',
        data: {
            'correct_count': parseInt(correct_count),
            'defect_count': parseInt(defect_count),
            'custom_fields': JSON.stringify(custom_fields)
        },
        success: function (data) {
            if (!data) {
                data = {
                    'total_count': 0,
                    'defect_count': 0,
                    'correct_count': 0
                };
            }
            $("#total_count").html(data.total_count);
            $("#defect_keyboard input").val(data.defect_count);
            $("#correct_keyboard input").val(data.correct_count);
        }
    });
}

/**
 * Reset count
 *
 * @param url
 */
function resetCount(url) {
    $.ajax({
        url: url,
        method: 'get',
        data: {},
        success: function (data) {
            if (!data) {
                data = {
                    'total_count': 0,
                    'defect_count': 0,
                    'correct_count': 0
                };
            }
            $("#total_count").html(data.total_count);
            $("#defect_keyboard input").val(data.defect_count || 0);
            $("#correct_keyboard input").val(data.correct_count || 0);
        }
    });
}

/**
 * Reset count current
 *
 * @param url
 */
function resetCountCurrent(url) {
    let defect_count = $('#defect_keyboard input').val();
    let correct_count = $('#correct_keyboard input').val();

    $.ajax({
        url: url,
        method: 'post',
        data: {
            'correct_count': parseInt(correct_count) || 0,
            'defect_count': parseInt(defect_count) || 0
        },
        success: function (data) {
            if (!data) {
                data = {
                    'current_count': 0,
                    'defect_count': 0,
                    'correct_count': 0
                };
            }
            $("#current_count").val(data.current_count);
            $("#defect_keyboard input").val(data.defect_count || 0);
            $("#correct_keyboard input").val(data.correct_count || 0);
        }
    });
}

/**
 * Start count
 *
 * @param url
 */
function startCount(url) {
    $.ajax({
        url: url,
        method: 'get',
        data: {},
        success: function () {
            $('#btn_pause').removeClass('btn-warning').addClass('btn-outline-secondary');
            $('#btn_start').removeClass('btn-info').addClass('btn-outline-secondary');
            $('#pause_display').removeClass('d-flex').addClass('d-none');
        }
    });
}

/**
 * Pause count
 *
 * @param url
 */
function pauseCount(url) {
    $.ajax({
        url: url,
        method: 'get',
        data: {},
        success: function () {
            $('#btn_pause').removeClass('btn-outline-secondary').addClass('btn-warning');
            $('#btn_start').removeClass('btn-outline-secondary').addClass('btn-info');
            $('#pause_display').removeClass('d-none').addClass('d-flex');
        }
    });
}