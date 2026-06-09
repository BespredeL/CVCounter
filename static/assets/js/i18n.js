/**
 * Developed by: Aleksandr Kireev
 * Created: 04.06.2026
 * Updated: 08.06.2026
 * Website: https://bespredel.name
 */

/**
 * Client-side i18n (window.APP_I18N is rendered from the server in base.html).
 */
(function (global) {
    "use strict";

    /**
     * Translate a string key with optional {placeholder} replacement.
     * Keys match backend trans() and langs/*.json (English source strings).
     *
     * @param {string} key - Translation key, e.g. "Counter running"
     * @param {Record<string, string|number>} [params] - Placeholder values
     * @returns {string} - The translated string
     */
    function trans(key, params) {
        let value = global.APP_I18N?.[key];

        if (typeof value !== "string") {
            value = key;
        }

        if (params) {
            Object.entries(params).forEach(([name, replacement]) => {
                value = value.replace(
                    new RegExp(`\\{${name}\\}`, "g"),
                    String(replacement)
                );
            });
        }

        return value;
    }

    global.trans = trans;
})(window);