/**
 * Developed by: Aleksandr Kireev
 * Created: 04.09.2024
 * Updated: 04.09.2024
 * Website: https://bespredel.name
 */
$(function () {

    // Обработчик для изменения значения инпута
    function changeInputValue(selector, increment) {
        $(selector).on('click', function () {
            const $input = $(this).parent().find('input');
            const value = parseInt($input.val(), 10);
            const max = $input.attr('max');
            const min = $input.attr('min');
            let validateValue = true;

            if (max !== undefined) {
                validateValue = increment ? value < parseInt(max, 10) : value <= parseInt(max, 10);
            }
            if (min !== undefined) {
                validateValue = increment ? value >= parseInt(min, 10) : value > parseInt(min, 10);
            }

            if (!isNaN(value) && validateValue) {
                $input.val(value + (increment ? 1 : -1));
            }
        });
    }

    // Обработчики для кнопок плюс и минус
    changeInputValue('.input-plus', true);
    changeInputValue('.input-minus', false);

    // Обработчик для сброса значений инпутов
    $('#correct_clear').on('click', function () {
        $('#correct_keyboard input').val(0);
    });

    // Обработчик для кнопок клавиатуры
    $('.keyboard button').on('click', function () {
        let $this = $(this);
        let $input = $('#' + $this.parent().parent().data('input-id') + ' input');
        let value = $this.data('value');
        let input_val = $input.val();
        input_val = input_val.replace(/[^0-9\-]/g, '');

        if ($this.hasClass('reset')) {
            $input.val(0);
            return;
        }

        if (value === '-') {
            input_val = -(input_val);
        } else {
            input_val = input_val + value;
        }

        if (input_val > 999999 || input_val < -999999) {
            return;
        }

        $input.val(parseInt(input_val));
    });

});