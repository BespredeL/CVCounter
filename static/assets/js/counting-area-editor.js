/**
 * Developed by: Aleksandr Kireev
 * Created: 03.06.2026
 * Updated: 04.06.2026
 * Website: https://bespredel.name
 */


/**
 * The hit radius for the counting area editor
 *
 * @type {number}
 */
const COUNTING_AREA_HIT_RADIUS = 12;

/**
 * The minimum number of points for the counting area editor
 *
 * @type {number}
 */
const COUNTING_AREA_MIN_POINTS = 3;

/**
 * Utility functions for counting area color conversion
 */
const CountingAreaColorUtil = {
    /**
     * Convert BGR to hex color string
     *
     * @param {number} b - Blue component
     * @param {number} g - Green component
     * @param {number} r - Red component
     * @returns {string}
     */
    bgrToHex(b, g, r) {
        const hex = (n) => n.toString(16).padStart(2, "0");
        return `#${hex(r)}${hex(g)}${hex(b)}`;
    },

    /**
     * Convert hex color string to BGR array
     *
     * @param {string} hex - Hex color string
     * @returns {number[]}
     */
    hexToBgr(hex) {
        const value = hex.replace("#", "");
        const r = parseInt(value.slice(0, 2), 16);
        const g = parseInt(value.slice(2, 4), 16);
        const b = parseInt(value.slice(4, 6), 16);
        return [b, g, r];
    },
};

/**
 * Canvas editor for detection counting_area polygon
 */
class CountingAreaEditor {
    /**
     * @param {HTMLElement} root
     */
    constructor(root) {
        this.root = root;
        this.location = root.dataset.location;
        this.dataUrl = root.dataset.dataUrl;
        this.snapshotUrl = root.dataset.snapshotUrl;
        this.saveUrl = root.dataset.saveUrl;

        this.img = document.getElementById("ca-frame");
        this.canvas = document.getElementById("ca-canvas");
        this.ctx = this.canvas.getContext("2d");
        this.wrap = document.getElementById("ca-canvas-wrap");
        this.statusEl = document.getElementById("ca-status");
        this.loadingEl = document.getElementById("ca-loading");
        this.colorInput = document.getElementById("ca-color");

        this.frameWidth = 0;
        this.frameHeight = 0;
        this.displayWidth = 0;
        this.displayHeight = 0;
        this.points = [];
        this.areaColorBgr = [67, 211, 255];

        this.dragIndex = -1;
        this.rectMode = false;
        this.rectStart = null;

        this.bindToolbar();
        this.bindCanvas();
        this.load();
    }

    /**
     * Set the status of the editor
     *
     * @param {string} text - The text to set as the status
     * @param {boolean} [isError] - Whether the status is an error
     */
    setStatus(text, isError = false) {
        this.statusEl.textContent = text;
        this.statusEl.classList.toggle("text-danger", isError);
    }

    /**
     * Get the internationalization strings
     *
     * @returns {object}
     */
    i18n() {
        return window.i18nGroup("countingArea");
    }

    /**
     * Bind the toolbar events
     */
    bindToolbar() {
        const strings = this.i18n();

        $("#ca-btn-undo").on("click", () => {
            if (this.points.length > 0) {
                this.points.pop();
                this.redraw();
            }
        });

        $("#ca-btn-clear").on("click", () => {
            this.points = [];
            this.redraw();
        });

        $("#ca-btn-full").on("click", () => this.setFullFrame());

        $("#ca-btn-rect").on("click", () => {
            this.rectMode = !this.rectMode;
            this.rectStart = null;
            $("#ca-btn-rect").toggleClass("active", this.rectMode);
            this.setStatus(this.rectMode ? strings.rectHint : strings.defaultHint);
        });

        $("#ca-btn-refresh").on("click", () => this.loadSnapshot(true));
        $("#ca-btn-save").on("click", () => this.save());

        this.colorInput.addEventListener("input", () => this.redraw());
        window.addEventListener("resize", () => this.resizeCanvas());
    }

    /**
     * Bind the canvas events
     */
    bindCanvas() {
        const onPointer = (e) => {
            if (!this.frameWidth) {
                return;
            }

            const pt = this.eventToDisplay(e);
            if (e.type === "pointerdown") {
                this.onPointerDown(pt, e);
            } else if (e.type === "pointermove") {
                this.onPointerMove(pt, e);
            } else if (e.type === "pointerup" || e.type === "pointercancel") {
                this.onPointerUp(e);
            }
        };

        this.canvas.addEventListener("pointerdown", onPointer);
        this.canvas.addEventListener("pointermove", onPointer);
        this.canvas.addEventListener("pointerup", onPointer);
        this.canvas.addEventListener("pointercancel", onPointer);

        this.canvas.addEventListener("dblclick", (e) => {
            const pt = this.eventToDisplay(e);
            const idx = this.hitTest(pt.x, pt.y);

            if (idx >= 0 && this.points.length > COUNTING_AREA_MIN_POINTS) {
                this.points.splice(idx, 1);
                this.redraw();
            }
        });
    }

    /**
     * Load the counting area data
     */
    async load() {
        this.loadingEl.classList.remove("d-none");

        try {
            const response = await fetch(this.dataUrl, {credentials: "same-origin"});

            if (!response.ok) {
                throw new Error(response.statusText);
            }

            const data = await response.json();

            this.points = (data.counting_area || []).map((p) => ({x: p[0], y: p[1]}));
            if (data.counting_area_color?.length === 3) {
                this.areaColorBgr = data.counting_area_color;
                this.colorInput.value = CountingAreaColorUtil.bgrToHex(
                    this.areaColorBgr[0],
                    this.areaColorBgr[1],
                    this.areaColorBgr[2]
                );
            }
            await this.loadSnapshot(false);
        } catch (err) {
            this.setStatus(err.message || "Load failed", true);
        } finally {
            this.loadingEl.classList.add("d-none");
        }
    }

    /**
     * Load the snapshot image
     *
     * @param {boolean} bustCache
     * @returns {Promise<void>}
     */
    loadSnapshot(bustCache) {
        return new Promise((resolve, reject) => {
            const url = this.snapshotUrl + (bustCache ? `?t=${Date.now()}` : "");

            this.img.onload = () => {
                this.frameWidth = parseInt(this.img.naturalWidth || this.img.width, 10);
                this.frameHeight = parseInt(this.img.naturalHeight || this.img.height, 10);
                this.img.hidden = false;
                this.resizeCanvas();
                this.redraw();
                this.setStatus(this.i18n().defaultHint || "");
                resolve();
            };

            this.img.onerror = () => reject(new Error("Snapshot failed"));
            this.img.src = url;
        });
    }

    /**
     * Resize the canvas
     */
    resizeCanvas() {
        if (!this.frameWidth) {
            return;
        }

        const maxW = this.wrap.clientWidth;
        const scale = Math.min(1, maxW / this.frameWidth);

        this.displayWidth = Math.round(this.frameWidth * scale);
        this.displayHeight = Math.round(this.frameHeight * scale);
        this.canvas.width = this.displayWidth;
        this.canvas.height = this.displayHeight;
        this.canvas.style.width = `${this.displayWidth}px`;
        this.canvas.style.height = `${this.displayHeight}px`;
        this.img.style.width = `${this.displayWidth}px`;
        this.img.style.height = `${this.displayHeight}px`;
        this.redraw();
    }

    /**
     * Convert display coordinates to native coordinates
     *
     * @param {number} dx - The x coordinate in display coordinates
     * @param {number} dy - The y coordinate in display coordinates
     * @returns {{x: number, y: number}} - The native coordinates
     */
    displayToNative(dx, dy) {
        return {
            x: Math.round((dx / this.displayWidth) * this.frameWidth),
            y: Math.round((dy / this.displayHeight) * this.frameHeight),
        };
    }

    /**
     * Convert native coordinates to display coordinates
     *
     * @param {number} nx - The x coordinate in native coordinates
     * @param {number} ny - The y coordinate in native coordinates
     * @returns {{x: number, y: number}} - The display coordinates
     */
    nativeToDisplay(nx, ny) {
        return {
            x: (nx / this.frameWidth) * this.displayWidth,
            y: (ny / this.frameHeight) * this.displayHeight,
        };
    }

    /**
     * Convert event coordinates to display coordinates
     *
     * @param {PointerEvent} e - The pointer event
     * @returns {{x: number, y: number}} - The display coordinates
     * @returns {{x: number, y: number}}
     */
    eventToDisplay(e) {
        const rect = this.canvas.getBoundingClientRect();
        return {
            x: e.clientX - rect.left,
            y: e.clientY - rect.top,
        };
    }

    /**
     * Test if a point is within the hit radius of a point
     *
     * @param {number} dx - The x coordinate of the point to test
     * @param {number} dy - The y coordinate of the point to test
     * @returns {number} - The index of the point if it is within the hit radius, otherwise -1
     */
    hitTest(dx, dy) {
        for (let i = 0; i < this.points.length; i++) {
            const p = this.nativeToDisplay(this.points[i].x, this.points[i].y);
            const dist = Math.hypot(p.x - dx, p.y - dy);

            if (dist <= COUNTING_AREA_HIT_RADIUS) {
                return i;
            }
        }

        return -1;
    }

    /**
     * Clamp a point to the frame
     *
     * @param {{x: number, y: number}} point - The point to clamp
     * @returns {{x: number, y: number}} - The clamped point
     */
    clampNative(point) {
        return {
            x: Math.max(0, Math.min(this.frameWidth, point.x)),
            y: Math.max(0, Math.min(this.frameHeight, point.y))
        };
    }

    /**
     * Handle pointer down event
     *
     * @param {{x: number, y: number}} pt - The point to clamp
     * @param {PointerEvent} e - The pointer event
     * @param {PointerEvent} e
     */
    onPointerDown(pt, e) {
        this.canvas.setPointerCapture(e.pointerId);

        const hit = this.hitTest(pt.x, pt.y);
        if (hit >= 0) {
            this.dragIndex = hit;
            return;
        }

        if (this.rectMode) {
            this.rectStart = this.clampNative(this.displayToNative(pt.x, pt.y));
            return;
        }

        this.points.push(this.clampNative(this.displayToNative(pt.x, pt.y)));
        this.redraw();
    }

    /**
     * Handle pointer move event
     *
     * @param {{x: number, y: number}} pt - The point to clamp
     * @param {PointerEvent} e - The pointer event
     * @param {PointerEvent} e
     */
    onPointerMove(pt, e) {
        if (this.dragIndex >= 0) {
            this.points[this.dragIndex] = this.clampNative(this.displayToNative(pt.x, pt.y));
            this.redraw();
            return;
        }

        if (this.rectMode && this.rectStart && e.buttons === 1) {
            const end = this.clampNative(this.displayToNative(pt.x, pt.y));
            const x1 = Math.min(this.rectStart.x, end.x);
            const y1 = Math.min(this.rectStart.y, end.y);
            const x2 = Math.max(this.rectStart.x, end.x);
            const y2 = Math.max(this.rectStart.y, end.y);

            this.points = [
                {x: x1, y: y1},
                {x: x2, y: y1},
                {x: x2, y: y2},
                {x: x1, y: y2},
            ];

            this.redraw();
        }
    }

    /**
     * Handle pointer up event
     *
     * @param {PointerEvent} e
     */
    onPointerUp(e) {
        if (this.rectMode && this.rectStart) {
            this.rectStart = null;
            this.rectMode = false;
            $("#ca-btn-rect").removeClass("active");
        }

        this.dragIndex = -1;

        try {
            this.canvas.releasePointerCapture(e.pointerId);
        } catch (ignored) {
            // pointer may already be released
        }
    }

    /**
     * Set the full frame
     */
    setFullFrame() {
        if (!this.frameWidth) {
            return;
        }

        this.points = [
            {x: 0, y: 0},
            {x: this.frameWidth, y: 0},
            {x: this.frameWidth, y: this.frameHeight},
            {x: 0, y: this.frameHeight},
        ];

        this.redraw();
    }

    /**
     * Get the fill color rgba
     *
     * @param {number} alpha - The alpha value
     * @returns {string}
     */
    fillColorRgba(alpha) {
        const hex = this.colorInput.value;
        const value = hex.replace("#", "");
        const r = parseInt(value.slice(0, 2), 16);
        const g = parseInt(value.slice(2, 4), 16);
        const b = parseInt(value.slice(4, 6), 16);

        return `rgba(${r},${g},${b},${alpha})`;
    }

    /**
     * Get the stroke color
     *
     * @returns {string} - The stroke color
     */
    strokeColor() {
        return this.colorInput.value;
    }

    /**
     * Redraw the canvas
     */
    redraw() {
        if (!this.ctx || !this.displayWidth) {
            return;
        }

        const strings = this.i18n();

        this.ctx.clearRect(0, 0, this.displayWidth, this.displayHeight);

        if (this.points.length >= 3) {
            this.ctx.beginPath();
            const first = this.nativeToDisplay(this.points[0].x, this.points[0].y);
            this.ctx.moveTo(first.x, first.y);

            for (let i = 1; i < this.points.length; i++) {
                const p = this.nativeToDisplay(this.points[i].x, this.points[i].y);
                this.ctx.lineTo(p.x, p.y);
            }

            this.ctx.closePath();
            this.ctx.fillStyle = this.fillColorRgba(0.35);
            this.ctx.fill();
            this.ctx.strokeStyle = this.strokeColor();
            this.ctx.lineWidth = 2;
            this.ctx.stroke();
        } else if (this.points.length === 2) {
            this.ctx.beginPath();
            const a = this.nativeToDisplay(this.points[0].x, this.points[0].y);
            const b = this.nativeToDisplay(this.points[1].x, this.points[1].y);
            this.ctx.moveTo(a.x, a.y);
            this.ctx.lineTo(b.x, b.y);
            this.ctx.strokeStyle = this.strokeColor();
            this.ctx.lineWidth = 2;
            this.ctx.stroke();
        }

        this.points.forEach((pt, i) => {
            const d = this.nativeToDisplay(pt.x, pt.y);
            this.ctx.beginPath();
            this.ctx.arc(d.x, d.y, 6, 0, Math.PI * 2);
            this.ctx.fillStyle = i === this.dragIndex ? "#fff" : this.strokeColor();
            this.ctx.fill();
            this.ctx.strokeStyle = "#000";
            this.ctx.lineWidth = 1.5;
            this.ctx.stroke();
        });

        const ptsLabel = this.points.length;
        let status = `${strings.points || "Points"}: ${ptsLabel}`;

        if (ptsLabel < COUNTING_AREA_MIN_POINTS) {
            status += ` - ${strings.minPoints || `need at least ${COUNTING_AREA_MIN_POINTS}`}`;
        }

        this.statusEl.textContent = status;
    }

    /**
     * Save the counting area
     */
    async save() {
        const strings = this.i18n();

        if (this.points.length < COUNTING_AREA_MIN_POINTS) {
            showToast(
                strings.minPointsToast || `At least ${COUNTING_AREA_MIN_POINTS} points required`,
                "warning"
            );
            return;
        }

        const body = {
            counting_area: this.points.map((p) => [p.x, p.y]),
            counting_area_color: CountingAreaColorUtil.hexToBgr(this.colorInput.value),
        };

        $("#ca-btn-save").prop("disabled", true);

        try {
            const response = await fetch(this.saveUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify(body),
            });

            const data = await response.json().catch(() => ({}));

            if (!response.ok) {
                throw new Error(data.message || data.error || response.statusText);
            }

            showToast(strings.saved || "Zone saved", "success");
        } catch (err) {
            showToast(err.message || "Save failed", "danger");
        } finally {
            $("#ca-btn-save").prop("disabled", false);
        }
    }
}

/**
 * Counting zone editor page bootstrap
 */
const CountingAreaEditorManager = {
    initialize() {
        const root = document.getElementById("counting-area-app");

        if (root) {
            new CountingAreaEditor(root);
        }
    },
};

/**
 * Initialize the counting area editor
 */
$(function () {
    CountingAreaEditorManager.initialize();
});