/**
 * Computer Vision Counter (CVCounter) - Counting Zone Editor
 *
 * Developed by: Aleksandr Kireev
 * Created: 03.06.2026
 * Updated: 2026
 * Website: https://bespredel.name
 */

/**
 * Screen hit radius in pixels for grabbing a vertex
 * @type {number}
 */
const COUNTING_AREA_HIT_RADIUS_SCREEN = 14;

/**
 * Screen distance in pixels for detecting edge hover (point insertion)
 * @type {number}
 */
const COUNTING_AREA_EDGE_THRESHOLD_SCREEN = 10;

/**
 * Minimum number of points required for a valid polygon
 * @type {number}
 */
const COUNTING_AREA_MIN_POINTS = 3;

/**
 * Vibrant BGR color palette for zones
 * @type {number[][]}
 */
const COUNTING_AREA_ZONE_COLORS = [
    [255, 211, 67],  // Cyan/Sky (#43d3ff) in BGR: [B=255, G=211, R=67]
    [118, 230, 0],   // Green (#00e676)
    [82, 82, 255],   // Coral/Red (#ff5252)
    [129, 64, 255],  // Pink (#ff4081)
    [0, 171, 255],   // Amber (#ffab00)
    [255, 138, 68],  // Blue (#448aff)
    [255, 136, 179], // Purple (#b388ff)
    [182, 233, 29],  // Teal (#1de9b6)
];

/**
 * Utility functions for color conversions
 */
const CountingAreaColorUtil = {
    /**
     * Convert BGR array to Hex string (#rrggbb)
     * @param {number} b
     * @param {number} g
     * @param {number} r
     * @returns {string}
     */
    bgrToHex(b, g, r) {
        const h = (n) => Math.max(0, Math.min(255, Math.round(n))).toString(16).padStart(2, "0");
        return `#${h(r)}${h(g)}${h(b)}`;
    },

    /**
     * Convert Hex string (#rrggbb) to BGR array [b, g, r]
     * @param {string} hex
     * @returns {number[]}
     */
    hexToBgr(hex) {
        const clean = hex.replace("#", "");
        const r = parseInt(clean.slice(0, 2), 16) || 0;
        const g = parseInt(clean.slice(2, 4), 16) || 0;
        const b = parseInt(clean.slice(4, 6), 16) || 0;
        return [b, g, r];
    },

    /**
     * Convert BGR to RGBA string
     * @param {number[]} bgr
     * @param {number} alpha
     * @returns {string}
     */
    bgrToRgba(bgr, alpha = 1) {
        const [b, g, r] = bgr || [255, 211, 67];
        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    },
};

/**
 * Geometry helper functions
 */
const CountingAreaGeometry = {
    /**
     * Distance between two points
     */
    distance(p1, p2) {
        return Math.hypot(p2.x - p1.x, p2.y - p1.y);
    },

    /**
     * Closest point on line segment [a, b] to point p
     */
    closestPointOnSegment(p, a, b) {
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const lenSq = dx * dx + dy * dy;
        if (lenSq === 0) return { point: { x: a.x, y: a.y }, t: 0, dist: this.distance(p, a) };

        let t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / lenSq;
        t = Math.max(0, Math.min(1, t));

        const closest = {
            x: Math.round(a.x + t * dx),
            y: Math.round(a.y + t * dy),
        };
        return {
            point: closest,
            t,
            dist: this.distance(p, closest),
        };
    },

    /**
     * Calculate polygon area using Shoelace formula
     * @param {Array<{x: number, y: number}>} points
     * @returns {number}
     */
    polygonArea(points) {
        if (!points || points.length < 3) return 0;
        let area = 0;
        const n = points.length;
        for (let i = 0; i < n; i++) {
            const j = (i + 1) % n;
            area += points[i].x * points[j].y;
            area -= points[j].x * points[i].y;
        }
        return Math.abs(area) / 2;
    },

    /**
     * Calculate centroid of a polygon
     * @param {Array<{x: number, y: number}>} points
     * @returns {{x: number, y: number}}
     */
    polygonCentroid(points) {
        if (!points || points.length === 0) return { x: 0, y: 0 };
        let sumX = 0;
        let sumY = 0;
        points.forEach((p) => {
            sumX += p.x;
            sumY += p.y;
        });
        return {
            x: Math.round(sumX / points.length),
            y: Math.round(sumY / points.length),
        };
    },

    /**
     * Point in polygon test (Ray casting)
     * @param {{x: number, y: number}} p
     * @param {Array<{x: number, y: number}>} vs
     * @returns {boolean}
     */
    pointInPolygon(p, vs) {
        if (!vs || vs.length < 3) return false;
        let inside = false;
        for (let i = 0, j = vs.length - 1; i < vs.length; j = i++) {
            const xi = vs[i].x, yi = vs[i].y;
            const xj = vs[j].x, yj = vs[j].y;
            const intersect = ((yi > p.y) !== (yj > p.y)) &&
                (p.x < (xj - xi) * (p.y - yi) / (yj - yi) + xi);
            if (intersect) inside = !inside;
        }
        return inside;
    },
};

/**
 * Modern High-Performance Counting Zone Canvas Editor
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
        this.videoUrl = root.dataset.videoUrl;

        // Elements
        this.wrap = document.getElementById("ca-canvas-wrap");
        this.viewport = document.getElementById("ca-viewport");
        this.img = document.getElementById("ca-frame");
        this.canvas = document.getElementById("ca-canvas");
        this.ctx = this.canvas.getContext("2d");
        this.loadingEl = document.getElementById("ca-loading");
        this.statusEl = document.getElementById("ca-status");
        this.colorInput = document.getElementById("ca-color");
        this.zoneCardsListEl = document.getElementById("ca-zone-cards-list");
        this.zonesCountBadge = document.getElementById("ca-zones-count-badge");
        this.frameResBadge = document.getElementById("ca-frame-res-badge");
        this.cursorCoordsEl = document.getElementById("ca-cursor-coords");
        this.zoomLabelEl = document.getElementById("ca-zoom-label");
        this.hudModeIcon = document.getElementById("ca-hud-mode-icon");
        this.hudModeText = document.getElementById("ca-hud-mode-text");
        this.hudHintText = document.getElementById("ca-hud-hint-text");
        this.btnUndo = document.getElementById("ca-btn-undo");
        this.btnRedo = document.getElementById("ca-btn-redo");
        this.activeZoneTitle = document.getElementById("ca-active-zone-title");
        this.activeZonePtsBadge = document.getElementById("ca-active-zone-pts");

        // Native frame state
        this.frameWidth = 0;
        this.frameHeight = 0;

        // Pan and Zoom engine
        this.scale = 1.0;
        this.fitScale = 1.0;
        this.panX = 0;
        this.panY = 0;
        this.minScale = 0.1;
        this.maxScale = 8.0;

        // Tool Mode: 'edit' | 'draw' | 'rect'
        this.toolMode = "edit";

        // Zones collection
        this.zones = [this.createZone(COUNTING_AREA_ZONE_COLORS[0])];
        this.activeZoneIndex = 0;

        // Interaction state
        this.dragMode = null; // 'vertex' | 'polygon' | 'rect' | 'pan'
        this.dragVertexIndex = -1;
        this.dragStartNative = null;
        this.dragStartClient = null;
        this.polygonOriginalPoints = null;
        this.rectStartNative = null;
        this.hoverVertexIndex = -1;
        this.hoverEdge = null;
        this.mouseNative = { x: 0, y: 0 };
        this.isSpacePressed = false;
        this.isAltPressed = false;
        this.isFullscreen = false;

        // Undo / Redo History Stack
        this.historyStack = [];
        this.redoStack = [];

        this.init();
    }

    /**
     * Initialize editor components
     */
    init() {
        this.bindEvents();
        this.bindPaletteChips();
        this.renderZoneList();
        this.syncActiveZoneUI();
        this.load();
    }

    /**
     * Create a zone object
     * @param {number[]} colorBgr
     * @param {Array<{x: number, y: number}>} [points]
     * @returns {{points: Array<{x: number, y: number}>, colorBgr: number[], visible: boolean}}
     */
    createZone(colorBgr, points = []) {
        return {
            points: points ? points.map((p) => ({ x: p.x, y: p.y })) : [],
            colorBgr: [...(colorBgr || COUNTING_AREA_ZONE_COLORS[0])],
            visible: true,
        };
    }

    /**
     * Getter for current active zone
     */
    get activeZone() {
        if (!this.zones[this.activeZoneIndex]) {
            this.activeZoneIndex = 0;
        }
        return this.zones[this.activeZoneIndex];
    }

    /**
     * Active zone points shortcut
     */
    get points() {
        return this.activeZone.points;
    }

    set points(val) {
        this.activeZone.points = val;
    }

    /**
     * Push current state to undo history
     */
    pushState() {
        const snapshot = {
            activeZoneIndex: this.activeZoneIndex,
            zones: this.zones.map((z) => ({
                points: z.points.map((p) => ({ x: p.x, y: p.y })),
                colorBgr: [...z.colorBgr],
                visible: z.visible !== false,
            })),
        };

        this.historyStack.push(snapshot);
        if (this.historyStack.length > 40) {
            this.historyStack.shift();
        }
        this.redoStack = [];
        this.updateHistoryButtons();
    }

    /**
     * Undo last action
     */
    undo() {
        if (this.historyStack.length === 0) return;

        // Current state goes to redo stack
        const currentSnapshot = {
            activeZoneIndex: this.activeZoneIndex,
            zones: this.zones.map((z) => ({
                points: z.points.map((p) => ({ x: p.x, y: p.y })),
                colorBgr: [...z.colorBgr],
                visible: z.visible !== false,
            })),
        };
        this.redoStack.push(currentSnapshot);

        const state = this.historyStack.pop();
        this.zones = state.zones.map((z) => this.createZone(z.colorBgr, z.points));
        this.activeZoneIndex = Math.min(state.activeZoneIndex, this.zones.length - 1);

        this.updateHistoryButtons();
        this.syncActiveZoneUI();
        this.renderZoneList();
        this.redraw();
        showToast(window.trans("Undo applied"), "secondary");
    }

    /**
     * Redo last undone action
     */
    redo() {
        if (this.redoStack.length === 0) return;

        const currentSnapshot = {
            activeZoneIndex: this.activeZoneIndex,
            zones: this.zones.map((z) => ({
                points: z.points.map((p) => ({ x: p.x, y: p.y })),
                colorBgr: [...z.colorBgr],
                visible: z.visible !== false,
            })),
        };
        this.historyStack.push(currentSnapshot);

        const state = this.redoStack.pop();
        this.zones = state.zones.map((z) => this.createZone(z.colorBgr, z.points));
        this.activeZoneIndex = Math.min(state.activeZoneIndex, this.zones.length - 1);

        this.updateHistoryButtons();
        this.syncActiveZoneUI();
        this.renderZoneList();
        this.redraw();
    }

    /**
     * Update Undo/Redo button states
     */
    updateHistoryButtons() {
        if (this.btnUndo) this.btnUndo.disabled = this.historyStack.length === 0;
        if (this.btnRedo) this.btnRedo.disabled = this.redoStack.length === 0;
    }

    /**
     * Set active tool mode
     * @param {'edit' | 'draw' | 'rect'} mode
     */
    setToolMode(mode) {
        this.toolMode = mode;
        const radio = document.getElementById(`ca-tool-${mode}`);
        if (radio) radio.checked = true;

        if (mode === "edit") {
            if (this.hudModeIcon) this.hudModeIcon.textContent = "🖱️";
            if (this.hudModeText) this.hudModeText.textContent = window.trans("Select & Edit");
            if (this.hudHintText) this.hudHintText.textContent = window.trans("Edit mode hint");
            this.canvas.className = "counting-area-canvas";
        } else if (mode === "draw") {
            if (this.hudModeIcon) this.hudModeIcon.textContent = "✏️";
            if (this.hudModeText) this.hudModeText.textContent = window.trans("Draw polygon");
            if (this.hudHintText) this.hudHintText.textContent = window.trans("Draw mode hint");
            this.canvas.className = "counting-area-canvas";
        } else if (mode === "rect") {
            if (this.hudModeIcon) this.hudModeIcon.textContent = "🔲";
            if (this.hudModeText) this.hudModeText.textContent = window.trans("Draw rectangle");
            if (this.hudHintText) this.hudHintText.textContent = window.trans("Rect mode hint");
            this.canvas.className = "counting-area-canvas";
        }

        this.dragMode = null;
        this.hoverEdge = null;
        this.redraw();
    }

    /**
     * Select active zone by index
     * @param {number} index
     */
    selectZone(index) {
        if (index < 0 || index >= this.zones.length) return;
        this.activeZoneIndex = index;
        this.dragMode = null;
        this.hoverEdge = null;
        this.syncActiveZoneUI();
        this.renderZoneList();
        this.redraw();
    }

    /**
     * Add a new zone
     */
    addZone() {
        this.pushState();
        const nextColor = COUNTING_AREA_ZONE_COLORS[this.zones.length % COUNTING_AREA_ZONE_COLORS.length];
        const newZone = this.createZone(nextColor);
        this.zones.push(newZone);
        this.selectZone(this.zones.length - 1);
        this.setToolMode("draw");
        showToast(window.trans("Zone added"), "success");
    }

    /**
     * Duplicate the active zone
     * @param {number} [index]
     */
    duplicateZone(index = this.activeZoneIndex) {
        const source = this.zones[index];
        if (!source) return;

        this.pushState();
        const nextColor = COUNTING_AREA_ZONE_COLORS[this.zones.length % COUNTING_AREA_ZONE_COLORS.length];
        // Shift points slightly by 25px
        const offset = Math.max(15, Math.round(this.frameWidth * 0.025));
        const newPoints = source.points.map((p) => ({
            x: Math.min(this.frameWidth, p.x + offset),
            y: Math.min(this.frameHeight, p.y + offset),
        }));

        const newZone = this.createZone(nextColor, newPoints);
        this.zones.push(newZone);
        this.selectZone(this.zones.length - 1);
        showToast(window.trans("Zone duplicated"), "info");
    }

    /**
     * Toggle visibility of a zone
     * @param {number} index
     */
    toggleZoneVisibility(index) {
        const zone = this.zones[index];
        if (!zone) return;
        zone.visible = zone.visible === false ? true : false;
        this.renderZoneList();
        this.redraw();
    }

    /**
     * Delete a zone
     * @param {number} [index]
     */
    deleteZone(index = this.activeZoneIndex) {
        if (this.zones.length <= 1) {
            showToast(window.trans("At least one zone required"), "warning");
            return;
        }

        this.pushState();
        this.zones.splice(index, 1);
        this.activeZoneIndex = Math.max(0, Math.min(this.activeZoneIndex, this.zones.length - 1));
        this.syncActiveZoneUI();
        this.renderZoneList();
        this.redraw();
        showToast(window.trans("Zone deleted"), "secondary");
    }

    /**
     * Sync UI controls with the active zone
     */
    syncActiveZoneUI() {
        const zone = this.activeZone;
        if (!zone) return;

        const hex = CountingAreaColorUtil.bgrToHex(zone.colorBgr[0], zone.colorBgr[1], zone.colorBgr[2]);
        if (this.colorInput) this.colorInput.value = hex;

        // Update active palette chip indicator
        document.querySelectorAll(".ca-color-chip").forEach((chip) => {
            chip.classList.toggle("active", chip.dataset.color.toLowerCase() === hex.toLowerCase());
        });

        // Update active zone info in sidebar
        if (this.activeZoneTitle) {
            this.activeZoneTitle.textContent = window.trans("Zone {index}", { index: this.activeZoneIndex + 1 });
        }
        if (this.activeZonePtsBadge) {
            const count = zone.points.length;
            this.activeZonePtsBadge.textContent = `${count} ${window.trans("Points").toLowerCase()}`;
            this.activeZonePtsBadge.className = `badge ${count >= COUNTING_AREA_MIN_POINTS ? "bg-success-subtle text-success-emphasis border border-success-subtle" : "bg-warning-subtle text-warning-emphasis border border-warning-subtle"}`;
        }
    }

    /**
     * Render the zone list cards in the sidebar
     */
    renderZoneList() {
        if (!this.zoneCardsListEl) return;
        this.zoneCardsListEl.replaceChildren();

        if (this.zonesCountBadge) {
            this.zonesCountBadge.textContent = this.zones.length;
        }

        this.zones.forEach((zone, idx) => {
            const isActive = idx === this.activeZoneIndex;
            const hex = CountingAreaColorUtil.bgrToHex(zone.colorBgr[0], zone.colorBgr[1], zone.colorBgr[2]);
            const count = zone.points.length;
            const area = this.frameWidth && this.frameHeight
                ? ((CountingAreaGeometry.polygonArea(zone.points) / (this.frameWidth * this.frameHeight)) * 100).toFixed(1)
                : 0;

            const card = document.createElement("div");
            card.className = `ca-zone-card d-flex align-items-center justify-content-between gap-2 ${isActive ? "active" : ""} ${zone.visible === false ? "is-hidden" : ""}`;
            card.style.setProperty("--zone-card-color", hex);

            // Left: Swatch + Title + Stats
            const left = document.createElement("div");
            left.className = "d-flex align-items-center gap-2 flex-grow-1 min-w-0";

            const swatch = document.createElement("span");
            swatch.className = "ca-zone-swatch";
            swatch.style.backgroundColor = hex;
            swatch.title = hex;

            const info = document.createElement("div");
            info.className = "d-flex flex-column min-w-0";

            const name = document.createElement("span");
            name.className = "fw-medium small text-truncate";
            name.textContent = window.trans("Zone {index}", { index: idx + 1 });

            const stats = document.createElement("span");
            stats.className = "text-body-secondary font-monospace";
            stats.style.fontSize = "0.72rem";
            stats.textContent = `${count} pts · ${area}%`;

            info.append(name, stats);
            left.append(swatch, info);

            // Right: Actions (Visibility, Duplicate, Delete)
            const actions = document.createElement("div");
            actions.className = "btn-group btn-group-sm flex-shrink-0";

            // Visibility button
            const visBtn = document.createElement("button");
            visBtn.type = "button";
            visBtn.className = "btn btn-sm btn-outline-secondary p-1 border-0";
            visBtn.title = zone.visible === false ? window.trans("Show zone") : window.trans("Hide zone");
            visBtn.innerHTML = zone.visible === false
                ? `<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" fill="currentColor" class="bi bi-eye-slash" viewBox="0 0 16 16"><path d="M13.359 11.238C15.06 9.72 16 8 16 8s-3-5.5-8-5.5a7.028 7.028 0 0 0-2.79.588l.77.771A5.944 5.944 0 0 1 8 3.5c2.12 0 3.879 1.168 5.168 2.457A13.134 13.134 0 0 1 14.828 8c-.058.087-.122.183-.195.288-.335.48-.83 1.12-1.465 1.755-.165.165-.337.328-.517.486l.708.709z"/><path d="M11.297 9.176a3.5 3.5 0 0 0-4.474-4.474l.823.823a2.5 2.5 0 0 1 2.829 2.829l.822.822zm-2.943 1.299.822.822a3.5 3.5 0 0 1-4.474-4.474l.823.823a2.5 2.5 0 0 0 2.829 2.829z"/><path d="M3.35 5.47c-.18.16-.353.322-.518.487A13.134 13.134 0 0 0 1.172 8l.195.288c.335.48.83 1.12 1.465 1.755C4.121 11.332 5.881 12.5 8 12.5c.716 0 1.39-.133 2.02-.36l.77.772A7.029 7.029 0 0 1 8 13.5C3 13.5 0 8 0 8s.939-1.721 2.641-3.238l.708.709zm10.296 8.884-12-12 .708-.708 12 12-.708.708z"/></svg>`
                : `<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" fill="currentColor" class="bi bi-eye" viewBox="0 0 16 16"><path d="M16 8s-3-5.5-8-5.5S0 8 0 8s3 5.5 8 5.5S16 8 16 8zM1.173 8a13.133 13.133 0 0 1 1.66-2.043C4.12 4.668 5.88 3.5 8 3.5c2.12 0 3.879 1.168 5.168 2.457A13.133 13.133 0 0 1 14.828 8c-.058.087-.122.182-.195.288-.335.48-.83 1.12-1.465 1.755C11.879 11.332 10.119 12.5 8 12.5c-2.12 0-3.879-1.168-5.168-2.457A13.134 13.134 0 0 1 1.172 8z"/><path d="M8 5.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5zM4.5 8a3.5 3.5 0 1 1 7 0 3.5 3.5 0 0 1-7 0z"/></svg>`;
            visBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                this.toggleZoneVisibility(idx);
            });

            // Duplicate button
            const dupBtn = document.createElement("button");
            dupBtn.type = "button";
            dupBtn.className = "btn btn-sm btn-outline-secondary p-1 border-0";
            dupBtn.title = window.trans("Duplicate zone");
            dupBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" fill="currentColor" class="bi bi-copy" viewBox="0 0 16 16"><path fill-rule="evenodd" d="M4 2a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2zm2-1a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V2a1 1 0 0 0-1-1zM2 5a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1v-1h1v1a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h1v1z"/></svg>`;
            dupBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                this.duplicateZone(idx);
            });

            // Delete button
            const delBtn = document.createElement("button");
            delBtn.type = "button";
            delBtn.className = "btn btn-sm btn-outline-danger p-1 border-0";
            delBtn.title = window.trans("Delete zone");
            delBtn.disabled = this.zones.length <= 1;
            delBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" fill="currentColor" class="bi bi-x-lg" viewBox="0 0 16 16"><path d="M2.146 2.854a.5.5 0 1 1 .708-.708L8 7.293l5.146-5.147a.5.5 0 0 1 .708.708L8.707 8l5.147 5.146a.5.5 0 0 1-.708.708L8 8.707l-5.146 5.147a.5.5 0 0 1-.708-.708L7.293 8z"/></svg>`;
            delBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                this.deleteZone(idx);
            });

            actions.append(visBtn, dupBtn, delBtn);

            card.append(left, actions);
            card.addEventListener("click", () => this.selectZone(idx));
            this.zoneCardsListEl.append(card);
        });
    }

    /**
     * Bind palette color chips
     */
    bindPaletteChips() {
        document.querySelectorAll(".ca-color-chip").forEach((chip) => {
            chip.addEventListener("click", () => {
                const hex = chip.dataset.color;
                this.pushState();
                this.activeZone.colorBgr = CountingAreaColorUtil.hexToBgr(hex);
                this.syncActiveZoneUI();
                this.renderZoneList();
                this.redraw();
            });
        });
    }

    /**
     * Bind toolbar, canvas, and keyboard events
     */
    bindEvents() {
        // Mode buttons
        document.querySelectorAll("input[name='ca-tool-mode']").forEach((radio) => {
            radio.addEventListener("change", (e) => this.setToolMode(e.target.value));
        });

        // Add zone
        document.getElementById("ca-btn-add-zone")?.addEventListener("click", () => this.addZone());

        // History
        this.btnUndo?.addEventListener("click", () => this.undo());
        this.btnRedo?.addEventListener("click", () => this.redo());

        // Utilities
        document.getElementById("ca-btn-refresh")?.addEventListener("click", () => this.loadSnapshot(true));
        document.getElementById("ca-btn-save")?.addEventListener("click", () => this.save());

        // Preset actions on active zone
        document.getElementById("ca-btn-rect-preset")?.addEventListener("click", () => this.applyRectPreset());
        document.getElementById("ca-btn-full")?.addEventListener("click", () => this.applyFullFramePreset());
        document.getElementById("ca-btn-center")?.addEventListener("click", () => this.applyCenterPreset());
        document.getElementById("ca-btn-clear")?.addEventListener("click", () => this.clearActiveZone());

        // Color input
        this.colorInput?.addEventListener("input", (e) => {
            this.activeZone.colorBgr = CountingAreaColorUtil.hexToBgr(e.target.value);
            this.syncActiveZoneUI();
            this.renderZoneList();
            this.redraw();
        });

        // Zoom controls
        document.getElementById("ca-zoom-in")?.addEventListener("click", () => this.zoomStep(1.25));
        document.getElementById("ca-zoom-out")?.addEventListener("click", () => this.zoomStep(1 / 1.25));
        document.getElementById("ca-zoom-label")?.addEventListener("click", () => this.resetZoomTo100());
        document.getElementById("ca-zoom-fit")?.addEventListener("click", () => this.fitToView());
        document.getElementById("ca-fullscreen")?.addEventListener("click", () => this.toggleFullscreen());

        // Window resize
        window.addEventListener("resize", () => {
            this.fitToView(false);
        });

        // Fullscreen change
        document.addEventListener("fullscreenchange", () => {
            this.isFullscreen = !!document.fullscreenElement;
            this.fitToView();
        });

        // Keyboard shortcuts
        window.addEventListener("keydown", (e) => this.onKeyDown(e));
        window.addEventListener("keyup", (e) => this.onKeyUp(e));

        // Canvas / Viewport pointer events
        this.bindPointerEvents();
    }

    /**
     * Bind canvas pointer interaction
     */
    bindPointerEvents() {
        this.canvas.addEventListener("pointerdown", (e) => this.onPointerDown(e));
        window.addEventListener("pointermove", (e) => this.onPointerMove(e));
        window.addEventListener("pointerup", (e) => this.onPointerUp(e));
        window.addEventListener("pointercancel", (e) => this.onPointerUp(e));

        // Wheel zoom with focal point
        this.wrap.addEventListener("wheel", (e) => this.onWheel(e), { passive: false });

        // Double-click vertex deletion
        this.canvas.addEventListener("dblclick", (e) => this.onDoubleClick(e));

        // Prevent context menu when right-click panning
        this.wrap.addEventListener("contextmenu", (e) => {
            if (e.button === 2) e.preventDefault();
        });
    }

    /**
     * Convert client (screen) coordinates to native frame coordinates
     * @param {number} clientX
     * @param {number} clientY
     * @returns {{x: number, y: number}}
     */
    clientToNative(clientX, clientY) {
        if (!this.frameWidth || !this.frameHeight) return { x: 0, y: 0 };
        const rect = this.canvas.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return { x: 0, y: 0 };

        const normX = (clientX - rect.left) / rect.width;
        const normY = (clientY - rect.top) / rect.height;

        return {
            x: Math.max(0, Math.min(this.frameWidth, Math.round(normX * this.frameWidth))),
            y: Math.max(0, Math.min(this.frameHeight, Math.round(normY * this.frameHeight))),
        };
    }

    /**
     * Hit test active-zone vertices
     * @param {number} nx
     * @param {number} ny
     * @returns {number} Vertex index or -1
     */
    hitTestVertex(nx, ny) {
        const threshold = COUNTING_AREA_HIT_RADIUS_SCREEN / this.scale;
        for (let i = 0; i < this.points.length; i++) {
            if (CountingAreaGeometry.distance({ x: nx, y: ny }, this.points[i]) <= threshold) {
                return i;
            }
        }
        return -1;
    }

    /**
     * Hit test active-zone edges for point insertion
     * @param {number} nx
     * @param {number} ny
     * @returns {{index: number, point: {x: number, y: number}} | null}
     */
    hitTestEdge(nx, ny) {
        if (this.points.length < 2) return null;
        const threshold = COUNTING_AREA_EDGE_THRESHOLD_SCREEN / this.scale;
        const p = { x: nx, y: ny };

        for (let i = 0; i < this.points.length; i++) {
            const nextIdx = (i + 1) % this.points.length;
            if (this.points.length === 2 && i === 1) break; // open 2-point line

            const a = this.points[i];
            const b = this.points[nextIdx];
            const proj = CountingAreaGeometry.closestPointOnSegment(p, a, b);

            // Avoid triggering near endpoints
            if (proj.dist <= threshold && proj.t > 0.08 && proj.t < 0.92) {
                return { index: i, point: proj.point };
            }
        }
        return null;
    }

    /**
     * Handle pointerdown
     */
    onPointerDown(e) {
        if (!this.frameWidth) return;

        // Space + drag or Middle-click / Right-click => Pan canvas
        if (this.isSpacePressed || e.button === 1 || e.button === 2) {
            this.dragMode = "pan";
            this.dragStartClient = { x: e.clientX, y: e.clientY };
            this.canvas.classList.add("cursor-grabbing");
            e.preventDefault();
            return;
        }

        if (e.button !== 0) return; // Only primary button for drawing
        this.canvas.setPointerCapture(e.pointerId);

        const pt = this.clientToNative(e.clientX, e.clientY);
        this.mouseNative = pt;

        // Tool Mode: DRAW POLYGON
        if (this.toolMode === "draw") {
            // Check if clicking near the first point to close polygon
            if (this.points.length >= COUNTING_AREA_MIN_POINTS) {
                const firstHit = CountingAreaGeometry.distance(pt, this.points[0]) <= (COUNTING_AREA_HIT_RADIUS_SCREEN / this.scale);
                if (firstHit) {
                    this.setToolMode("edit");
                    showToast(window.trans("Zone saved"), "success");
                    return;
                }
            }

            this.pushState();
            this.points.push(pt);
            this.syncActiveZoneUI();
            this.renderZoneList();
            this.redraw();
            return;
        }

        // Tool Mode: RECTANGLE
        if (this.toolMode === "rect") {
            this.pushState();
            this.dragMode = "rect";
            this.rectStartNative = pt;
            this.points = [
                { x: pt.x, y: pt.y },
                { x: pt.x, y: pt.y },
                { x: pt.x, y: pt.y },
                { x: pt.x, y: pt.y },
            ];
            this.redraw();
            return;
        }

        // Tool Mode: SELECT & EDIT
        if (this.toolMode === "edit") {
            // 1. Check vertex hit
            const vHit = this.hitTestVertex(pt.x, pt.y);
            if (vHit >= 0) {
                this.pushState();
                this.dragMode = "vertex";
                this.dragVertexIndex = vHit;
                this.canvas.classList.add("cursor-grabbing");
                return;
            }

            // 2. Check edge hit (insert point!)
            const edgeHit = this.hitTestEdge(pt.x, pt.y);
            if (edgeHit) {
                this.pushState();
                this.points.splice(edgeHit.index + 1, 0, edgeHit.point);
                this.dragMode = "vertex";
                this.dragVertexIndex = edgeHit.index + 1;
                this.hoverEdge = null;
                this.syncActiveZoneUI();
                this.renderZoneList();
                this.redraw();
                return;
            }

            // 3. Check inside polygon (or Alt key) => Move whole polygon
            const inside = CountingAreaGeometry.pointInPolygon(pt, this.points);
            if (inside || this.isAltPressed) {
                this.pushState();
                this.dragMode = "polygon";
                this.dragStartNative = pt;
                this.polygonOriginalPoints = this.points.map((p) => ({ ...p }));
                this.canvas.classList.add("cursor-move");
                return;
            }

            // 4. Click outside: check if clicked inside another visible zone to select it
            for (let i = 0; i < this.zones.length; i++) {
                if (i !== this.activeZoneIndex && this.zones[i].visible !== false) {
                    if (CountingAreaGeometry.pointInPolygon(pt, this.zones[i].points)) {
                        this.selectZone(i);
                        return;
                    }
                }
            }
        }
    }

    /**
     * Handle pointermove
     */
    onPointerMove(e) {
        if (!this.frameWidth) return;

        // Pan execution
        if (this.dragMode === "pan") {
            const dx = e.clientX - this.dragStartClient.x;
            const dy = e.clientY - this.dragStartClient.y;
            this.panX += dx;
            this.panY += dy;
            this.dragStartClient = { x: e.clientX, y: e.clientY };
            this.updateViewportTransform();
            return;
        }

        const pt = this.clientToNative(e.clientX, e.clientY);
        this.mouseNative = pt;
        this.updateCursorCoords(pt.x, pt.y);

        // Vertex drag execution
        if (this.dragMode === "vertex" && this.dragVertexIndex >= 0) {
            this.points[this.dragVertexIndex] = pt;
            this.syncActiveZoneUI();
            this.renderZoneList();
            this.redraw();
            return;
        }

        // Whole polygon drag execution
        if (this.dragMode === "polygon" && this.dragStartNative && this.polygonOriginalPoints) {
            let dx = pt.x - this.dragStartNative.x;
            let dy = pt.y - this.dragStartNative.y;

            // Clamp delta so all points remain in [0, frameWidth] x [0, frameHeight]
            this.polygonOriginalPoints.forEach((p) => {
                if (p.x + dx < 0) dx = -p.x;
                if (p.x + dx > this.frameWidth) dx = this.frameWidth - p.x;
                if (p.y + dy < 0) dy = -p.y;
                if (p.y + dy > this.frameHeight) dy = this.frameHeight - p.y;
            });

            this.points = this.polygonOriginalPoints.map((p) => ({
                x: p.x + dx,
                y: p.y + dy,
            }));
            this.redraw();
            return;
        }

        // Rectangle drag execution
        if (this.dragMode === "rect" && this.rectStartNative) {
            const x1 = Math.min(this.rectStartNative.x, pt.x);
            const y1 = Math.min(this.rectStartNative.y, pt.y);
            const x2 = Math.max(this.rectStartNative.x, pt.x);
            const y2 = Math.max(this.rectStartNative.y, pt.y);

            this.points = [
                { x: x1, y: y1 },
                { x: x2, y: y1 },
                { x: x2, y: y2 },
                { x: x1, y: y2 },
            ];
            this.syncActiveZoneUI();
            this.renderZoneList();
            this.redraw();
            return;
        }

        // Hover inspection when not dragging
        if (this.toolMode === "edit") {
            const vHit = this.hitTestVertex(pt.x, pt.y);
            if (vHit !== this.hoverVertexIndex) {
                this.hoverVertexIndex = vHit;
                this.canvas.className = vHit >= 0 ? "counting-area-canvas cursor-pointer" : "counting-area-canvas";
                this.redraw();
            }

            if (vHit < 0) {
                const edgeHit = this.hitTestEdge(pt.x, pt.y);
                const hasChanged = (!this.hoverEdge && edgeHit) || (this.hoverEdge && !edgeHit) ||
                    (this.hoverEdge && edgeHit && this.hoverEdge.index !== edgeHit.index);
                if (hasChanged) {
                    this.hoverEdge = edgeHit;
                    this.redraw();
                }
            } else if (this.hoverEdge) {
                this.hoverEdge = null;
                this.redraw();
            }
        } else if (this.toolMode === "draw") {
            // Redraw for rubber-band preview line
            this.redraw();
        }
    }

    /**
     * Handle pointerup
     */
    onPointerUp(e) {
        if (this.dragMode === "rect") {
            this.dragMode = null;
            this.rectStartNative = null;
            this.setToolMode("edit");
            return;
        }

        if (this.dragMode === "pan") {
            this.dragMode = null;
            this.dragStartClient = null;
            this.canvas.classList.remove("cursor-grabbing");
            return;
        }

        if (this.dragMode === "vertex" || this.dragMode === "polygon") {
            this.dragMode = null;
            this.dragVertexIndex = -1;
            this.polygonOriginalPoints = null;
            this.canvas.classList.remove("cursor-grabbing", "cursor-move");
            this.renderZoneList();
            this.redraw();
        }

        try {
            if (e.pointerId !== undefined && this.canvas.hasPointerCapture(e.pointerId)) {
                this.canvas.releasePointerCapture(e.pointerId);
            }
        } catch (ignored) {}
    }

    /**
     * Handle double-click (delete vertex)
     */
    onDoubleClick(e) {
        const pt = this.clientToNative(e.clientX, e.clientY);
        const vHit = this.hitTestVertex(pt.x, pt.y);

        if (vHit >= 0) {
            if (this.points.length > COUNTING_AREA_MIN_POINTS) {
                this.pushState();
                this.points.splice(vHit, 1);
                this.hoverVertexIndex = -1;
                this.syncActiveZoneUI();
                this.renderZoneList();
                this.redraw();
            } else {
                showToast(window.trans("Need at least 3 points"), "warning");
            }
        }
    }

    /**
     * Mouse wheel zoom centered at cursor
     */
    onWheel(e) {
        e.preventDefault();
        const factor = e.deltaY < 0 ? 1.15 : (1 / 1.15);
        this.zoomAt(factor, e.clientX, e.clientY);
    }

    /**
     * Zoom centered at a screen point
     */
    zoomAt(factor, clientX, clientY) {
        const rect = this.wrap.getBoundingClientRect();
        const mouseX = clientX - rect.left;
        const mouseY = clientY - rect.top;

        const newScale = Math.max(this.minScale, Math.min(this.maxScale, this.scale * factor));
        const actualFactor = newScale / this.scale;

        this.scale = newScale;
        this.panX = mouseX - (mouseX - this.panX) * actualFactor;
        this.panY = mouseY - (mouseY - this.panY) * actualFactor;

        this.updateViewportTransform();
        this.updateZoomLabel();
        this.redraw();
    }

    /**
     * Step zoom in/out from center of container
     */
    zoomStep(factor) {
        const rect = this.wrap.getBoundingClientRect();
        this.zoomAt(factor, rect.left + rect.width / 2, rect.top + rect.height / 2);
    }

    /**
     * Reset zoom to 100% native size
     */
    resetZoomTo100() {
        const rect = this.wrap.getBoundingClientRect();
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;

        this.scale = 1.0;
        this.panX = Math.round(centerX - (this.frameWidth / 2));
        this.panY = Math.round(centerY - (this.frameHeight / 2));
        this.updateViewportTransform();
        this.updateZoomLabel();
        this.redraw();
    }

    /**
     * Fit entire frame to wrapper view
     * @param {boolean} [animate]
     */
    fitToView(animate = false) {
        if (!this.frameWidth || !this.frameHeight) return;

        const wrapW = this.wrap.clientWidth;
        const wrapH = this.wrap.clientHeight;
        if (!wrapW || !wrapH) return;

        const padding = 24;
        const availW = Math.max(100, wrapW - padding * 2);
        const availH = Math.max(100, wrapH - padding * 2);

        this.fitScale = Math.min(availW / this.frameWidth, availH / this.frameHeight);
        this.scale = this.fitScale;
        this.panX = Math.round((wrapW - this.frameWidth * this.scale) / 2);
        this.panY = Math.round((wrapH - this.frameHeight * this.scale) / 2);

        this.updateViewportTransform();
        this.updateZoomLabel();
        this.redraw();
    }

    /**
     * Toggle fullscreen mode
     */
    toggleFullscreen() {
        if (!this.isFullscreen) {
            if (this.wrap.requestFullscreen) {
                this.wrap.requestFullscreen().catch(() => {
                    this.wrap.classList.add("ca-fullscreen-active");
                    this.isFullscreen = true;
                    this.fitToView();
                });
            } else {
                this.wrap.classList.add("ca-fullscreen-active");
                this.isFullscreen = true;
                this.fitToView();
            }
        } else {
            if (document.exitFullscreen) {
                document.exitFullscreen().catch(() => {});
            }
            this.wrap.classList.remove("ca-fullscreen-active");
            this.isFullscreen = false;
            this.fitToView();
        }
    }

    /**
     * Apply viewport CSS transform
     */
    updateViewportTransform() {
        if (!this.viewport) return;
        this.viewport.style.transform = `translate3d(${Math.round(this.panX)}px, ${Math.round(this.panY)}px, 0) scale(${this.scale})`;
    }

    /**
     * Update zoom label badge in HUD
     */
    updateZoomLabel() {
        if (this.zoomLabelEl) {
            const pct = Math.round((this.scale / this.fitScale) * 100);
            this.zoomLabelEl.textContent = `${pct}%`;
        }
    }

    /**
     * Update cursor coordinates badge in HUD
     */
    updateCursorCoords(x, y) {
        if (this.cursorCoordsEl) {
            this.cursorCoordsEl.textContent = `X: ${x}  Y: ${y}`;
        }
    }

    /**
     * Handle keydown shortcuts
     */
    onKeyDown(e) {
        if (e.target.matches("input, textarea, select")) return;

        // Ctrl+Z: Undo
        if ((e.ctrlKey || e.metaKey) && (e.key === "z" || e.key === "Z") && !e.shiftKey) {
            e.preventDefault();
            this.undo();
            return;
        }

        // Ctrl+Y or Ctrl+Shift+Z: Redo
        if ((e.ctrlKey || e.metaKey) && (e.key === "y" || e.key === "Y" || (e.shiftKey && (e.key === "z" || e.key === "Z")))) {
            e.preventDefault();
            this.redo();
            return;
        }

        // Ctrl+S: Save
        if ((e.ctrlKey || e.metaKey) && (e.key === "s" || e.key === "S")) {
            e.preventDefault();
            this.save();
            return;
        }

        // Space: Pan tool
        if (e.code === "Space" && !this.isSpacePressed) {
            this.isSpacePressed = true;
            this.canvas.classList.add("cursor-grab");
            e.preventDefault();
            return;
        }

        // Alt: Whole zone drag
        if (e.key === "Alt") {
            this.isAltPressed = true;
        }

        // Tool shortcuts
        if (e.key === "v" || e.key === "V" || e.key === "1") {
            this.setToolMode("edit");
        } else if (e.key === "p" || e.key === "P" || e.key === "2") {
            this.setToolMode("draw");
        } else if (e.key === "r" || e.key === "R" || e.key === "3") {
            this.setToolMode("rect");
        } else if (e.key === "f" || e.key === "F") {
            this.fitToView();
        } else if (e.key === "+" || e.key === "=") {
            this.zoomStep(1.25);
        } else if (e.key === "-" || e.key === "_") {
            this.zoomStep(1 / 1.25);
        } else if (e.key === "0") {
            this.fitToView();
        } else if (e.key === "Escape") {
            if (this.toolMode !== "edit") {
                this.setToolMode("edit");
            }
        } else if (e.key === "Delete" || e.key === "Backspace") {
            // Delete hovered vertex or clear active
            if (this.hoverVertexIndex >= 0 && this.points.length > COUNTING_AREA_MIN_POINTS) {
                this.pushState();
                this.points.splice(this.hoverVertexIndex, 1);
                this.hoverVertexIndex = -1;
                this.syncActiveZoneUI();
                this.renderZoneList();
                this.redraw();
            }
        }
    }

    /**
     * Handle keyup
     */
    onKeyUp(e) {
        if (e.code === "Space") {
            this.isSpacePressed = false;
            this.canvas.classList.remove("cursor-grab", "cursor-grabbing");
        }
        if (e.key === "Alt") {
            this.isAltPressed = false;
        }
    }

    /**
     * Shape preset: Full Frame
     */
    applyFullFramePreset() {
        if (!this.frameWidth || !this.frameHeight) return;
        this.pushState();
        this.points = [
            { x: 0, y: 0 },
            { x: this.frameWidth, y: 0 },
            { x: this.frameWidth, y: this.frameHeight },
            { x: 0, y: this.frameHeight },
        ];
        this.syncActiveZoneUI();
        this.renderZoneList();
        this.redraw();
    }

    /**
     * Shape preset: Rectangle (centered 50% box)
     */
    applyRectPreset() {
        if (!this.frameWidth || !this.frameHeight) return;
        this.pushState();
        const w = Math.round(this.frameWidth * 0.5);
        const h = Math.round(this.frameHeight * 0.5);
        const x1 = Math.round((this.frameWidth - w) / 2);
        const y1 = Math.round((this.frameHeight - h) / 2);

        this.points = [
            { x: x1, y: y1 },
            { x: x1 + w, y: y1 },
            { x: x1 + w, y: y1 + h },
            { x: x1, y: y1 + h },
        ];
        this.syncActiveZoneUI();
        this.renderZoneList();
        this.redraw();
    }

    /**
     * Shape preset: Center Box (centered 30% diamond/box)
     */
    applyCenterPreset() {
        if (!this.frameWidth || !this.frameHeight) return;
        this.pushState();
        const cx = Math.round(this.frameWidth / 2);
        const cy = Math.round(this.frameHeight / 2);
        const rx = Math.round(this.frameWidth * 0.2);
        const ry = Math.round(this.frameHeight * 0.2);

        this.points = [
            { x: cx - rx, y: cy - ry },
            { x: cx + rx, y: cy - ry },
            { x: cx + rx, y: cy + ry },
            { x: cx - rx, y: cy + ry },
        ];
        this.syncActiveZoneUI();
        this.renderZoneList();
        this.redraw();
    }

    /**
     * Clear active zone points
     */
    clearActiveZone() {
        if (this.points.length === 0) return;
        this.pushState();
        this.points = [];
        this.syncActiveZoneUI();
        this.renderZoneList();
        this.redraw();
        showToast(window.trans("Points cleared"), "secondary");
    }

    /**
     * Redraw canvas elements
     */
    redraw() {
        if (!this.ctx || !this.frameWidth) return;

        this.ctx.clearRect(0, 0, this.frameWidth, this.frameHeight);

        // 1. Draw all non-active visible zones
        this.zones.forEach((zone, index) => {
            if (index !== this.activeZoneIndex && zone.visible !== false) {
                this.drawZoneShape(zone, false, index);
            }
        });

        // 2. Draw active zone if visible
        if (this.activeZone && this.activeZone.visible !== false) {
            this.drawZoneShape(this.activeZone, true, this.activeZoneIndex);
        }

        // 3. Draw Rubber-band line in 'draw' mode
        if (this.toolMode === "draw" && this.points.length > 0) {
            const last = this.points[this.points.length - 1];
            this.ctx.beginPath();
            this.ctx.moveTo(last.x, last.y);
            this.ctx.lineTo(this.mouseNative.x, this.mouseNative.y);
            this.ctx.strokeStyle = CountingAreaColorUtil.bgrToRgba(this.activeZone.colorBgr, 0.85);
            this.ctx.lineWidth = 2 / this.scale;
            this.ctx.setLineDash([6 / this.scale, 4 / this.scale]);
            this.ctx.stroke();
            this.ctx.setLineDash([]);

            // If mouse is near the first point, highlight close polygon target
            if (this.points.length >= COUNTING_AREA_MIN_POINTS) {
                const distToFirst = CountingAreaGeometry.distance(this.mouseNative, this.points[0]);
                if (distToFirst <= (COUNTING_AREA_HIT_RADIUS_SCREEN / this.scale)) {
                    this.ctx.beginPath();
                    this.ctx.arc(this.points[0].x, this.points[0].y, 12 / this.scale, 0, Math.PI * 2);
                    this.ctx.fillStyle = "rgba(0, 230, 118, 0.4)";
                    this.ctx.fill();
                    this.ctx.strokeStyle = "#00e676";
                    this.ctx.lineWidth = 2.5 / this.scale;
                    this.ctx.stroke();
                }
            }
        }

        // Update status text in HUD
        const ptsCount = this.points.length;
        const area = ((CountingAreaGeometry.polygonArea(this.points) / (this.frameWidth * this.frameHeight)) * 100).toFixed(1);
        let status = `${window.trans("Zone {index}", { index: this.activeZoneIndex + 1 })}: ${ptsCount} ${window.trans("Points").toLowerCase()} (${area}%)`;
        if (ptsCount < COUNTING_AREA_MIN_POINTS) {
            status += ` — ${window.trans("Need at least 3 points")}`;
        }
        if (this.statusEl) {
            this.statusEl.textContent = status;
        }
    }

    /**
     * Draw a single zone polygon and vertices
     * @param {{points: Array<{x: number, y: number}>, colorBgr: number[]}} zone
     * @param {boolean} isActive
     * @param {number} zoneIndex
     */
    drawZoneShape(zone, isActive, zoneIndex) {
        const points = zone.points || [];
        const colorBgr = zone.colorBgr || COUNTING_AREA_ZONE_COLORS[0];
        const hex = CountingAreaColorUtil.bgrToHex(colorBgr[0], colorBgr[1], colorBgr[2]);

        const fillAlpha = isActive ? 0.35 : 0.16;
        const lineWidth = (isActive ? 3 : 1.8) / this.scale;

        // Draw closed polygon
        if (points.length >= 3) {
            this.ctx.beginPath();
            this.ctx.moveTo(points[0].x, points[0].y);
            for (let i = 1; i < points.length; i++) {
                this.ctx.lineTo(points[i].x, points[i].y);
            }
            this.ctx.closePath();
            this.ctx.fillStyle = CountingAreaColorUtil.bgrToRgba(colorBgr, fillAlpha);
            this.ctx.fill();

            this.ctx.strokeStyle = hex;
            this.ctx.lineWidth = lineWidth;
            this.ctx.stroke();

            // Centroid zone badge
            const centroid = CountingAreaGeometry.polygonCentroid(points);
            this.drawCentroidBadge(centroid.x, centroid.y, window.trans("Zone {index}", { index: zoneIndex + 1 }), hex, isActive);
        } else if (points.length === 2) {
            this.ctx.beginPath();
            this.ctx.moveTo(points[0].x, points[0].y);
            this.ctx.lineTo(points[1].x, points[1].y);
            this.ctx.strokeStyle = hex;
            this.ctx.lineWidth = lineWidth;
            this.ctx.stroke();
        }

        // Draw vertices only for active zone
        if (!isActive) return;

        // Hover edge point insertion indicator
        if (this.toolMode === "edit" && this.hoverEdge) {
            const ep = this.hoverEdge.point;
            const radius = 6 / this.scale;
            this.ctx.beginPath();
            this.ctx.arc(ep.x, ep.y, radius, 0, Math.PI * 2);
            this.ctx.fillStyle = "#ffffff";
            this.ctx.fill();
            this.ctx.strokeStyle = "#00e676";
            this.ctx.lineWidth = 2 / this.scale;
            this.ctx.stroke();

            // Plus symbol
            const d = 3 / this.scale;
            this.ctx.beginPath();
            this.ctx.moveTo(ep.x - d, ep.y);
            this.ctx.lineTo(ep.x + d, ep.y);
            this.ctx.moveTo(ep.x, ep.y - d);
            this.ctx.lineTo(ep.x, ep.y + d);
            this.ctx.strokeStyle = "#000000";
            this.ctx.lineWidth = 1.5 / this.scale;
            this.ctx.stroke();
        }

        // Vertices markers
        points.forEach((pt, i) => {
            const isHovered = i === this.hoverVertexIndex;
            const isDragged = i === this.dragVertexIndex;
            const radius = (isHovered || isDragged ? 8.5 : 6) / this.scale;

            // Outer glow ring
            this.ctx.beginPath();
            this.ctx.arc(pt.x, pt.y, radius + (2 / this.scale), 0, Math.PI * 2);
            this.ctx.fillStyle = isHovered || isDragged ? "rgba(255, 255, 255, 0.5)" : "rgba(0, 0, 0, 0.45)";
            this.ctx.fill();

            // Main vertex circle
            this.ctx.beginPath();
            this.ctx.arc(pt.x, pt.y, radius, 0, Math.PI * 2);
            this.ctx.fillStyle = isHovered || isDragged ? "#ffffff" : hex;
            this.ctx.fill();
            this.ctx.strokeStyle = isHovered || isDragged ? hex : "#ffffff";
            this.ctx.lineWidth = 2 / this.scale;
            this.ctx.stroke();

            // Vertex index number
            if (this.scale >= 0.6) {
                const fontSize = Math.max(9, Math.min(13, Math.round(11 / this.scale)));
                this.ctx.font = `600 ${fontSize}px sans-serif`;
                this.ctx.fillStyle = "#ffffff";
                this.ctx.shadowColor = "rgba(0,0,0,0.8)";
                this.ctx.shadowBlur = 4;
                this.ctx.fillText(String(i + 1), pt.x + radius + (3 / this.scale), pt.y - (3 / this.scale));
                this.ctx.shadowBlur = 0;
            }
        });
    }

    /**
     * Draw centroid zone label badge
     */
    drawCentroidBadge(cx, cy, label, hex, isActive) {
        const fontSize = Math.max(10, Math.min(15, Math.round(12 / this.scale)));
        this.ctx.font = `600 ${fontSize}px sans-serif`;
        const textWidth = this.ctx.measureText(label).width;

        const padX = 6 / this.scale;
        const padY = 3 / this.scale;
        const bgW = textWidth + padX * 2;
        const bgH = fontSize + padY * 2;

        const bx = cx - bgW / 2;
        const by = cy - bgH / 2;
        const r = 4 / this.scale;

        this.ctx.beginPath();
        this.ctx.roundRect(bx, by, bgW, bgH, r);
        this.ctx.fillStyle = "rgba(10, 12, 16, 0.78)";
        this.ctx.fill();
        this.ctx.strokeStyle = isActive ? hex : "rgba(255, 255, 255, 0.3)";
        this.ctx.lineWidth = 1 / this.scale;
        this.ctx.stroke();

        this.ctx.fillStyle = "#ffffff";
        this.ctx.textAlign = "center";
        this.ctx.textBaseline = "middle";
        this.ctx.fillText(label, cx, cy);
        this.ctx.textAlign = "start";
        this.ctx.textBaseline = "alphabetic";
    }

    /**
     * Load initial configuration data from server
     */
    async load() {
        if (this.loadingEl) this.loadingEl.classList.remove("d-none");

        try {
            const response = await fetch(this.dataUrl, { credentials: "same-origin" });
            if (!response.ok) throw new Error(response.statusText);

            const data = await response.json();
            this.zones = this.zonesFromPayload(data);
            this.activeZoneIndex = 0;
            this.syncActiveZoneUI();
            this.renderZoneList();
            await this.loadSnapshot(false);
        } catch (err) {
            if (this.statusEl) this.statusEl.textContent = err.message || "Load failed";
        } finally {
            if (this.loadingEl) this.loadingEl.classList.add("d-none");
        }
    }

    /**
     * Parse zones from server API response
     */
    zonesFromPayload(data) {
        const areas = Array.isArray(data.counting_areas) ? data.counting_areas : [];
        if (areas.length > 0) {
            return areas.map((area, index) => {
                const color = Array.isArray(area.color) && area.color.length === 3
                    ? area.color
                    : COUNTING_AREA_ZONE_COLORS[index % COUNTING_AREA_ZONE_COLORS.length];
                return this.createZone(color, (area.points || []).map((p) => ({ x: p[0], y: p[1] })));
            });
        }

        const fallbackColor = Array.isArray(data.counting_area_color) && data.counting_area_color.length === 3
            ? data.counting_area_color
            : COUNTING_AREA_ZONE_COLORS[0];

        return [
            this.createZone(fallbackColor, (data.counting_area || []).map((p) => ({ x: p[0], y: p[1] }))),
        ];
    }

    /**
     * Load background camera frame
     * @param {boolean} bustCache
     */
    loadSnapshot(bustCache) {
        return new Promise((resolve, reject) => {
            const url = this.snapshotUrl + (bustCache ? `?t=${Date.now()}` : "");

            this.img.onload = () => {
                this.frameWidth = parseInt(this.img.naturalWidth || this.img.width, 10);
                this.frameHeight = parseInt(this.img.naturalHeight || this.img.height, 10);
                this.img.hidden = false;

                // Sync canvas resolution exactly with video frame
                this.canvas.width = this.frameWidth;
                this.canvas.height = this.frameHeight;
                this.canvas.style.width = `${this.frameWidth}px`;
                this.canvas.style.height = `${this.frameHeight}px`;
                this.img.style.width = `${this.frameWidth}px`;
                this.img.style.height = `${this.frameHeight}px`;

                // Update resolution badge
                if (this.frameResBadge) {
                    this.frameResBadge.textContent = `${this.frameWidth} × ${this.frameHeight}`;
                }

                this.fitToView(false);
                this.redraw();
                resolve();
            };

            this.img.onerror = () => reject(new Error("Failed to load snapshot frame"));
            this.img.src = url;
        });
    }

    /**
     * Save counting zones to server config
     */
    async save() {
        const incomplete = this.zones.findIndex((zone) => zone.points.length < COUNTING_AREA_MIN_POINTS);
        if (incomplete >= 0) {
            this.selectZone(incomplete);
            showToast(window.trans("At least 3 points required"), "warning");
            return;
        }

        const body = {
            counting_areas: this.zones.map((zone) => ({
                points: zone.points.map((p) => [p.x, p.y]),
                color: zone.colorBgr,
            })),
        };

        const saveBtn = document.getElementById("ca-btn-save");
        if (saveBtn) saveBtn.disabled = true;

        try {
            const response = await fetch(this.saveUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            });

            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(data.message || data.error || response.statusText);
            }

            showToast(window.trans("Zone saved"), "success");
        } catch (err) {
            showToast(err.message || "Save failed", "danger");
        } finally {
            if (saveBtn) saveBtn.disabled = false;
        }
    }
}

/**
 * Page bootstrap
 */
document.addEventListener("DOMContentLoaded", () => {
    const root = document.getElementById("counting-area-app");
    if (root) {
        window.countingAreaEditor = new CountingAreaEditor(root);
    }
});
