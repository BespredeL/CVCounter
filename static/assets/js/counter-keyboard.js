/**
 * Developed by: Aleksandr Kireev
 * Created: 08.06.2026
 * Website: https://bespredel.name
 */

/**
 * Counter sidebar keyboards: on-screen numpad and physical NumPad shortcuts.
 */
const CounterKeyboard = {
    /**
     * Previous correct_count value (physical NumPad undo).
     *
     * @type {number}
     */
    _correctPrevVal: 0,

    /**
     * Pending correct_count value (physical NumPad confirm).
     *
     * @type {number}
     */
    _correctNextVal: 0,

    /**
     * Bind +/- stepper buttons next to an input.
     *
     * @param {string} selector - The selector for the stepper button
     * @param {boolean} increment - Whether to increment the value
     */
    bindStepper(selector, increment) {
        document.querySelectorAll(selector).forEach((button) => {
            button.addEventListener("click", () => {
                const input = button.parentElement?.querySelector("input");
                if (!input) {
                    return;
                }

                let value = parseInt(input.value, 10) || 0;
                const max = parseInt(input.getAttribute("max"), 10);
                const min = parseInt(input.getAttribute("min"), 10);

                if ((increment && (isNaN(max) || value < max)) || (!increment && (isNaN(min) || value > min))) {
                    value += increment ? 1 : -1;

                    if (!isNaN(max) && value > max) {
                        value = max;
                    }

                    if (!isNaN(min) && value < min) {
                        value = min;
                    }

                    input.value = value;
                }
            });
        });
    },

    /**
     * On-screen numpad buttons for defect / correct keyboards.
     */
    bindOnScreenKeyboard() {
        document.getElementById("correct_clear")?.addEventListener("click", () => {
            const input = document.querySelector("#correct_keyboard input");
            if (input) {
                input.value = 0;
            }
        });

        document.getElementById("defect_clear")?.addEventListener("click", () => {
            const input = document.querySelector("#defect_keyboard input");
            if (input) {
                input.value = 0;
            }
        });

        document.querySelectorAll(".keyboard button").forEach((button) => {
            button.addEventListener("click", () => {
                const inputId = button.parentElement?.parentElement?.dataset.inputId;
                const input = inputId ? document.querySelector(`#${inputId} input`) : null;
                if (!input) {
                    return;
                }

                const value = button.dataset.value;
                let inputValue = parseInt(input.value.replace(/[^0-9\-]/g, ""), 10) || 0;
                const max = parseInt(input.getAttribute("max"), 10);
                const min = parseInt(input.getAttribute("min"), 10);

                if (button.classList.contains("reset")) {
                    input.value = 0;
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
                    input.value = inputValue;
                }
            });
        });

        document.querySelectorAll("input.valid_min_max").forEach((input) => {
            input.addEventListener("input", () => {
                let value = input.value.replace(/[^0-9\-]/g, "");

                if (value.includes("-") && value.indexOf("-") !== 0) {
                    value = `-${value.replace(/-/g, "")}`;
                }

                let numericValue = parseInt(value, 10) || 0;
                const max = parseInt(input.getAttribute("max"), 10);
                const min = parseInt(input.getAttribute("min"), 10);

                if (!isNaN(max) && numericValue > max) {
                    numericValue = max;
                }

                if (!isNaN(min) && numericValue < min) {
                    numericValue = min;
                }

                input.value = numericValue;
            });
        });
    },

    /**
     * Physical NumPad shortcuts for correct_count (add digit, confirm, undo).
     * Loaded only on counter pages via counter_sidebar_right.html.
     */
    bindPhysicalNumpad() {
        if (!document.querySelector('input[name="correct_count"]')) {
            return;
        }

        document.addEventListener("keydown", (e) => {
            const input = document.querySelector('input[name="correct_count"]');
            if (!input || !e.code.startsWith('Numpad') || document.activeElement === input) {
                return;
            }

            const currentVal = parseInt(input.value, 10) || 0;

            switch (e.code) {
                case "Numpad0":
                case "NumpadDecimal":
                    input.value = 0;
                    break;
                case "Numpad1":
                    input.value = currentVal + 1;
                    break;
                case "Numpad2":
                    input.value = currentVal + 2;
                    break;
                case "Numpad3":
                    input.value = currentVal + 3;
                    break;
                case "Numpad4":
                    input.value = currentVal + 4;
                    break;
                case "Numpad5":
                    input.value = currentVal + 5;
                    break;
                case "Numpad6":
                    input.value = currentVal + 6;
                    break;
                case "Numpad7":
                    input.value = currentVal + 7;
                    break;
                case "Numpad8":
                    input.value = currentVal + 8;
                    break;
                case "Numpad9":
                    input.value = currentVal + 9;
                    break;
                case "NumpadAdd": // Numpad +
                    input.value = currentVal + 1;
                    break;
                case "NumpadSubtract": // Numpad -
                    input.value = currentVal - 1;
                    break;
            }
        });
    },

    /**
     * Initialize all counter keyboard handlers.
     */
    initialize() {
        this.bindStepper(".input-plus", true);
        this.bindStepper(".input-minus", false);
        this.bindOnScreenKeyboard();
        this.bindPhysicalNumpad();
    },
};

document.addEventListener("DOMContentLoaded", () => {
    CounterKeyboard.initialize();
});
