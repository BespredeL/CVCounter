/**
 * Developed by: Aleksandr Kireev
 * Created: 04.09.2024
 * Updated: 03.06.2026
 * Website: https://bespredel.name
 */

/**
 * Sidebar numeric keyboards (defect / correct)
 */
const SidebarKeyboard = {
    /**
     * Bind the stepper events
     * 
     * @param {string} selector - The selector for the input
     * @param {boolean} increment - Whether to increment the value
     */
    bindStepper(selector, increment) {
        $(selector).on("click", function () {
            const $input = $(this).siblings("input");
            let value = parseInt($input.val(), 10) || 0;
            const max = parseInt($input.attr("max"), 10);
            const min = parseInt($input.attr("min"), 10);

            if ((increment && (isNaN(max) || value < max)) || (!increment && (isNaN(min) || value > min))) {
                value += increment ? 1 : -1;

                if (!isNaN(max) && value > max) {
                    value = max;
                }

                if (!isNaN(min) && value < min) {
                    value = min;
                }

                $input.val(value);
            }
        });
    },

    /**
     * Initialize the sidebar keyboard
     */
    initialize() {
        this.bindStepper(".input-plus", true);
        this.bindStepper(".input-minus", false);

        $("#correct_clear").on("click", () => {
            $("#correct_keyboard input").val(0);
        });

        $("#defect_clear").on("click", () => {
            $("#defect_keyboard input").val(0);
        });

        $(".keyboard button").on("click", function () {
            const $button = $(this);
            const $input = $(`#${$button.parent().parent().data("input-id")} input`);
            const value = $button.data("value");
            let inputValue = parseInt($input.val().replace(/[^0-9\-]/g, ""), 10) || 0;
            const max = parseInt($input.attr("max"), 10);
            const min = parseInt($input.attr("min"), 10);

            if ($button.hasClass("reset")) {
                $input.val(0);
                return;
            }

            if (value === "-") {
                inputValue = -inputValue;
            } else {
                inputValue = inputValue * 10 + parseInt(value, 10);
            }

            if (!isNaN(max) && inputValue > max) {
                inputValue = max;
            }

            if (!isNaN(min) && inputValue < min) {
                inputValue = min;
            }

            if (inputValue >= min && inputValue <= max) {
                $input.val(inputValue);
            }
        });

        $("input.valid_min_max").on("input", function () {
            const $input = $(this);
            let value = $input.val().replace(/[^0-9\-]/g, "");

            if (value.includes("-") && value.indexOf("-") !== 0) {
                value = `-${value.replace(/-/g, "")}`;
            }

            let numericValue = parseInt(value, 10) || 0;
            const max = parseInt($input.attr("max"), 10);
            const min = parseInt($input.attr("min"), 10);

            if (!isNaN(max) && numericValue > max) {
                numericValue = max;
            }

            if (!isNaN(min) && numericValue < min) {
                numericValue = min;
            }

            $input.val(numericValue);
        });
    },
};

$(function () {
    SidebarKeyboard.initialize();
});
