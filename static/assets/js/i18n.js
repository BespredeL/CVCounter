/**
 * Developed by: Aleksandr Kireev
 * Created: 04.06.2026
 * Updated: 04.06.2026
 * Website: https://bespredel.name
 */

/**
 * Client-side i18n (window.APP_I18N is rendered from the server in base.html).
 */
(function (global) {
    "use strict";

    /**
     * Get a value by path
     *
     * @param {object} root - The root object
     * @param {string} path - Dot-separated key path, e.g. dashboard.running
     * @returns {*} - The value
     */
    function getByPath(root, path) {
        if (!root || !path) {
            return undefined;
        }

        return String(path).split(".").reduce((value, part) => {
            if (value === undefined || value === null) {
                return undefined;
            }

            return value[part];
        }, root);
    }

    /**
     * Translate a key with optional {placeholder} replacement.
     *
     * @param {string} key - Dot path inside APP_I18N
     * @param {Record<string, string|number>} [params] - The parameters
     * @returns {string} - The translated string
     */
    function trans(key, params) {
        let value = getByPath(global.APP_I18N, key);

        if (typeof value !== "string") {
            return key;
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

    /**
     * Return a translation group (dashboard, countingArea, socket, etc.)
     *
     * @param {string} group - The group name
     * @returns {Record<string, string>} - The translation group
     */
    function i18nGroup(group) {
        const bucket = global.APP_I18N?.[group];

        return bucket && typeof bucket === "object" ? bucket : {};
    }

    global.trans = trans;
    global.i18nGroup = i18nGroup;
})(window);
