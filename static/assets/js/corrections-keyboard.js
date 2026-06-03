/**
 * Developed by: Aleksandr Kireev
 * Created: 17.12.2024
 * Updated: 03.06.2026
 * Website: https://bespredel.name
 */

/**
 * Numpad shortcuts for correct_count field
 */
const CorrectionsKeyboard = {
    prevVal: 0,
    nextVal: 0,

    initialize() {
        $(document).on("keydown", (e) => {
            const input = $('input[name="correct_count"]');
            const currentVal = parseInt(input.val(), 10) || 0;

            switch (e.keyCode) {
                case 96: // Key 0
                case 110: // Key Del
                    input.val(0);
                    break;
                case 97: // Key 1
                case 98: // Key 2
                case 99: // Key 3
                case 100: // Key 4
                case 101: // Key 5
                case 102: // Key 6
                case 103: // Key 7
                case 104: // Key 8
                case 105: // Key 9
                    this.prevVal = currentVal;
                    this.nextVal = currentVal + (e.keyCode - 96);
                    input.val(this.nextVal);
                    break;
                case 107: // Key +
                    input.val(this.nextVal);
                    break;
                case 109: // Key -
                    input.val(this.prevVal);
                    break;
            }
        });
    },
};

/**
 * Initialize the corrections keyboard
 */
$(function () {
    CorrectionsKeyboard.initialize();
});
