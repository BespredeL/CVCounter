/**
 * Dataset image annotator (boxes, polygons, tracks, attributes).
 * Developed by: Aleksandr Kireev — https://bespredel.name
 */

(function () {
    const root = document.getElementById('dataset-annotator');
    if (!root) return;

    const t = (key) => (typeof window.trans === 'function' ? window.trans(key) : key);

    const COLORS = [
        '#43d3ff', '#00c85a', '#ff4000', '#ff00c8', '#008cff', '#b450ff', '#ffcc00', '#ffffff',
    ];
    const HANDLE = 7;
    const MIN_ZOOM = 0.25;
    const MAX_ZOOM = 8;
    const MIN_BOX = 0.004;

    function parseJsonAttr(value, fallback) {
        try {
            const parsed = JSON.parse(value || 'null');
            return parsed == null ? fallback : parsed;
        } catch (_) {
            return fallback;
        }
    }

    function clamp(v, lo, hi) {
        return Math.min(hi, Math.max(lo, v));
    }

    class DatasetAnnotator {
        constructor(el) {
            this.root = el;
            this.name = el.dataset.name;
            this.task = el.dataset.task || 'detect';
            this.classes = parseJsonAttr(el.dataset.classes, ['object']);
            this.classIdMap = parseJsonAttr(el.dataset.classIdMap, {});
            this.attrSchema = parseJsonAttr(el.dataset.attributes, []);
            this.keypointsSchema = parseJsonAttr(el.dataset.keypoints, []);
            this.imageNames = parseJsonAttr(el.dataset.images, []);
            this.currentName = el.dataset.current || this.imageNames[0] || '';

            this.img = document.getElementById('ann-image');
            this.canvas = document.getElementById('ann-canvas');
            this.ctx = this.canvas.getContext('2d');
            this.wrap = document.getElementById('ann-canvas-wrap');
            this.loadingEl = document.getElementById('ann-loading');
            this.emptyEl = document.getElementById('ann-empty');
            this.statusEl = document.getElementById('ann-status');
            this.indexEl = document.getElementById('ann-index');
            this.filenameEl = document.getElementById('ann-filename');
            this.shapesEl = document.getElementById('ann-shapes');
            this.shapeCountEl = document.getElementById('ann-shape-count');
            this.attrsEl = document.getElementById('ann-attrs');
            this.queueEl = document.getElementById('ann-queue');
            this.classSelect = document.getElementById('ann-class');
            this.trackInput = document.getElementById('ann-track-id');
            this.imageLabelSelect = document.getElementById('ann-image-label');
            this.zoomLabelEl = document.getElementById('ann-zoom-label');

            this.doc = { shapes: [], width: 0, height: 0, image_label: null, keypoints: [] };
            this.mode = 'select';
            this.selectedId = null;
            this.drawing = null;
            this.polyPoints = [];
            this.dirty = false;
            this.naturalW = 0;
            this.naturalH = 0;
            this.imageMeta = {};
            this.interpStart = null;
            this._opening = false;
            this._objectUrl = null;

            this.fitScale = 1;
            this.zoom = 1;
            this.panX = 0;
            this.panY = 0;
            this.panning = null;
            this.editDrag = null;

            this.fillClassSelect();
            this.bindUi();
            this.loadImageList().then(() => {
                if (!this.imageNames.length) {
                    this.setLoading(false);
                    this.emptyEl?.classList.remove('d-none');
                    this.setStatus(t('No images'));
                    return;
                }
                this.openImage(this.currentName || this.imageNames[0]);
            });
        }

        fillClassSelect() {
            this.classSelect.innerHTML = this.classes
                .map((c, i) => `<option value="${this.escapeAttr(c)}">${i + 1}. ${this.escapeHtml(c)}</option>`)
                .join('');
            if (this.task === 'classify' && this.imageLabelSelect) {
                this.imageLabelSelect.innerHTML = `<option value="">—</option>` + this.classes
                    .map((c) => `<option value="${this.escapeAttr(c)}">${this.escapeHtml(c)}</option>`)
                    .join('');
            }
        }

        /**
         * Resolve stored label: numeric YOLO ids → class names via detector map.
         */
        resolveLabel(label) {
            if (label == null || label === '') return '';
            const raw = String(label);
            if (this.classes.includes(raw)) return raw;
            if (/^\d+$/.test(raw) && this.classIdMap[raw]) {
                const mapped = this.classIdMap[raw];
                if (mapped) return mapped;
            }
            return raw;
        }

        displayLabel(label) {
            return this.resolveLabel(label);
        }

        normalizeShapeLabels({ markDirty = false } = {}) {
            let changed = false;
            (this.doc.shapes || []).forEach((shape) => {
                const resolved = this.resolveLabel(shape.label);
                if (resolved && resolved !== shape.label) {
                    shape.label = resolved;
                    changed = true;
                }
            });
            if (changed && markDirty) this.markDirty();
            return changed;
        }

        escapeHtml(s) {
            return String(s)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;');
        }

        escapeAttr(s) {
            return this.escapeHtml(s).replace(/'/g, '&#39;');
        }

        setStatus(text, tone) {
            this.statusEl.textContent = text;
            this.statusEl.className = 'badge rounded-pill';
            const map = {
                success: 'text-bg-success',
                warning: 'text-bg-warning',
                danger: 'text-bg-danger',
                info: 'text-bg-info',
            };
            this.statusEl.classList.add(map[tone] || 'text-bg-secondary');
        }

        setLoading(on) {
            this.loadingEl?.classList.toggle('d-none', !on);
        }

        setMode(mode) {
            this.mode = mode;
            document.querySelectorAll('[data-mode]').forEach((b) => {
                b.classList.toggle('active', b.dataset.mode === mode);
            });
            this.polyPoints = [];
            this.drawing = null;
            this.editDrag = null;
            this.updateCursor();
        }

        updateCursor() {
            if (this.panning) {
                this.canvas.style.cursor = 'grabbing';
                this.wrap.classList.add('is-panning');
                return;
            }
            this.wrap.classList.remove('is-panning');
            if (this.editDrag) {
                this.canvas.style.cursor = this.editDrag.cursor || 'move';
                return;
            }
            if (this.mode === 'select') {
                this.canvas.style.cursor = 'default';
            } else {
                this.canvas.style.cursor = 'crosshair';
            }
        }

        bindUi() {
            document.getElementById('ann-prev').addEventListener('click', () => this.navigate(-1));
            document.getElementById('ann-next').addEventListener('click', () => this.navigate(1));
            document.getElementById('ann-skip').addEventListener('click', () => this.navigate(1, true));
            document.getElementById('ann-save').addEventListener('click', () => this.save());
            document.getElementById('ann-delete').addEventListener('click', () => this.deleteSelected());
            document.getElementById('ann-delete-image')?.addEventListener('click', () => this.deleteCurrentImage());
            document.getElementById('ann-copy-prev').addEventListener('click', () => this.copyPrev());
            document.getElementById('ann-interpolate').addEventListener('click', () => this.interpolate());
            document.getElementById('ann-autolabel')?.addEventListener('click', () => this.autoLabelCurrent());
            document.getElementById('ann-zoom-in')?.addEventListener('click', () => this.nudgeZoom(1.25));
            document.getElementById('ann-zoom-out')?.addEventListener('click', () => this.nudgeZoom(1 / 1.25));
            document.getElementById('ann-zoom-fit')?.addEventListener('click', () => this.resetView());
            document.getElementById('ann-zoom-label')?.addEventListener('click', () => this.resetView());

            document.querySelectorAll('[data-mode]').forEach((btn) => {
                btn.addEventListener('click', () => this.setMode(btn.dataset.mode));
            });

            document.getElementById('ann-filter').addEventListener('change', () => this.renderQueue());

            this.imageLabelSelect?.addEventListener('change', () => {
                this.doc.image_label = this.imageLabelSelect.value || null;
                this.markDirty();
            });

            this.canvas.addEventListener('mousedown', (e) => this.onPointerDown(e));
            this.wrap.addEventListener('mousedown', (e) => {
                if (e.button === 2) this.startPan(e);
            });
            window.addEventListener('mousemove', (e) => this.onPointerMove(e));
            window.addEventListener('mouseup', (e) => this.onPointerUp(e));
            this.canvas.addEventListener('dblclick', (e) => {
                e.preventDefault();
                this.finishPolygon();
            });
            this.wrap.addEventListener('wheel', (e) => this.onWheel(e), { passive: false });
            this.wrap.addEventListener('contextmenu', (e) => e.preventDefault());
            this.canvas.addEventListener('contextmenu', (e) => e.preventDefault());
            window.addEventListener('resize', () => this.fitCanvas());
            window.addEventListener('keydown', (e) => this.onKey(e));
        }

        revokeObjectUrl() {
            if (this._objectUrl) {
                URL.revokeObjectURL(this._objectUrl);
                this._objectUrl = null;
            }
        }

        async loadImageElement(imageName) {
            this.revokeObjectUrl();
            const url = `/datasets/api/${encodeURIComponent(this.name)}/images/${encodeURIComponent(imageName)}`;
            const res = await fetch(url, {
                credentials: 'same-origin',
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            if (!res.ok) {
                throw new Error(`${t('Request failed')} (${res.status})`);
            }
            const blob = await res.blob();
            if (!blob || !blob.size) {
                throw new Error(t('Request failed'));
            }
            const objectUrl = URL.createObjectURL(blob);
            this._objectUrl = objectUrl;

            await new Promise((resolve, reject) => {
                const onLoad = () => {
                    cleanup();
                    resolve();
                };
                const onError = () => {
                    cleanup();
                    reject(new Error(t('Request failed')));
                };
                const cleanup = () => {
                    this.img.removeEventListener('load', onLoad);
                    this.img.removeEventListener('error', onError);
                };
                this.img.addEventListener('load', onLoad);
                this.img.addEventListener('error', onError);
                this.img.hidden = false;
                this.img.src = objectUrl;
            });

            this.naturalW = this.img.naturalWidth;
            this.naturalH = this.img.naturalHeight;
            this.doc.width = this.naturalW;
            this.doc.height = this.naturalH;
            this.resetView(false);
        }

        markDirty() {
            this.dirty = true;
            this.setStatus(t('Unsaved'), 'warning');
        }

        async loadImageList() {
            try {
                const res = await fetch(`/datasets/api/${this.name}/images`, {
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                });
                const data = await res.json();
                if (data.images) {
                    this.imageMeta = {};
                    this.imageNames = data.images.map((i) => {
                        this.imageMeta[i.name] = i;
                        return i.name;
                    });
                }
            } catch (_) {
                /* keep server-rendered list */
            }
            this.renderQueue();
        }

        updateIndex() {
            const idx = this.imageNames.indexOf(this.currentName);
            this.indexEl.textContent = idx >= 0
                ? `${idx + 1} / ${this.imageNames.length}`
                : `— / ${this.imageNames.length}`;
            this.filenameEl.textContent = this.currentName || '';
            this.filenameEl.title = this.currentName || '';
        }

        renderQueue() {
            if (!this.queueEl) return;
            const filter = document.getElementById('ann-filter')?.value || 'all';
            this.queueEl.innerHTML = '';
            let shown = 0;
            let activeBtn = null;
            this.imageNames.forEach((name, idx) => {
                const meta = this.imageMeta[name] || {};
                if (filter === 'unlabeled' && meta.labeled) return;
                if (filter === 'labeled' && !meta.labeled) return;
                shown += 1;
                const a = document.createElement('button');
                a.type = 'button';
                a.className = `list-group-item list-group-item-action py-2 px-2 ${name === this.currentName ? 'active' : ''}`;
                a.innerHTML = `
                    <span class="annotator__queue-item">
                        <span class="annotator__queue-item__idx">${idx + 1}</span>
                        <span class="annotator__queue-item__dot ${meta.labeled ? 'is-labeled' : ''}"></span>
                        <span class="annotator__queue-item__name">${this.escapeHtml(name)}</span>
                    </span>`;
                a.title = name;
                a.addEventListener('click', () => this.openImage(name));
                this.queueEl.appendChild(a);
                if (name === this.currentName) activeBtn = a;
            });
            if (!shown) {
                const empty = document.createElement('div');
                empty.className = 'list-group-item small text-body-secondary';
                empty.textContent = t('No images');
                this.queueEl.appendChild(empty);
            }
            if (activeBtn) {
                requestAnimationFrame(() => {
                    activeBtn.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
                });
            }
        }

        async openImage(imageName, { force = false } = {}) {
            if (!imageName || this._opening) return;
            const alreadyShown = imageName === this.currentName && this.naturalW > 0 && this.img?.src;
            if (!force && alreadyShown && !this.dirty) {
                this.updateIndex();
                this.renderQueue();
                return;
            }
            if (this.dirty && this.naturalW > 0) {
                const ok = await window.appConfirm({
                    title: t('Unsaved'),
                    message: t('Discard unsaved changes?'),
                    confirmText: t('Discard'),
                    tone: 'warning',
                });
                if (!ok) return;
            }

            this._opening = true;
            this.currentName = imageName;
            this.selectedId = null;
            this.polyPoints = [];
            this.drawing = null;
            this.editDrag = null;
            this.setLoading(true);
            this.emptyEl?.classList.add('d-none');
            this.setStatus(t('Loading…'));
            this.updateIndex();
            this.renderQueue();

            try {
                await this.loadImageElement(imageName);

                const res = await fetch(`/datasets/api/${encodeURIComponent(this.name)}/annotations/${encodeURIComponent(imageName)}`, {
                    credentials: 'same-origin',
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                });
                const data = await res.json();
                if (!res.ok || data.status === 'error') {
                    throw new Error(data.message || `${t('Request failed')} (${res.status})`);
                }
                this.doc = data.annotation || { shapes: [], width: 0, height: 0 };
                this.doc.shapes = this.doc.shapes || [];
                this.doc.width = this.doc.width || this.naturalW;
                this.doc.height = this.doc.height || this.naturalH;
                this.normalizeShapeLabels({ markDirty: false });
                if (this.imageLabelSelect) {
                    this.imageLabelSelect.value = this.doc.image_label || '';
                }
                this.dirty = false;
                this.setStatus(t('Ready'));
                this.redraw();
            } catch (err) {
                this.setStatus(err.message || t('Request failed'), 'danger');
            } finally {
                this.setLoading(false);
                this._opening = false;
            }

            this.renderShapesList();
            this.renderAttrs();
            const url = new URL(window.location.href);
            url.searchParams.set('image', imageName);
            window.history.replaceState({}, '', url);
        }

        async navigate(delta, skipSave) {
            const idx = this.imageNames.indexOf(this.currentName);
            const next = idx + delta;
            if (next < 0 || next >= this.imageNames.length) return;
            if (!skipSave && this.dirty) {
                await this.save();
            }
            await this.openImage(this.imageNames[next]);
        }

        resetView(redraw = true) {
            this.zoom = 1;
            this.panX = 0;
            this.panY = 0;
            this.fitCanvas(redraw);
        }

        nudgeZoom(factor) {
            const rect = this.wrap.getBoundingClientRect();
            this.setZoom(this.zoom * factor, rect.width / 2, rect.height / 2);
        }

        setZoom(nextZoom, focusX, focusY) {
            const z0 = this.zoom;
            const z1 = clamp(nextZoom, MIN_ZOOM, MAX_ZOOM);
            if (Math.abs(z1 - z0) < 1e-6) return;
            if (focusX != null && focusY != null) {
                const cx = focusX - this.wrap.clientWidth / 2;
                const cy = focusY - this.wrap.clientHeight / 2;
                const ratio = z1 / z0;
                this.panX = cx - (cx - this.panX) * ratio;
                this.panY = cy - (cy - this.panY) * ratio;
            }
            this.zoom = z1;
            this.applyView();
        }

        onWheel(e) {
            if (!this.naturalW) return;
            e.preventDefault();
            const rect = this.wrap.getBoundingClientRect();
            const focusX = e.clientX - rect.left;
            const focusY = e.clientY - rect.top;
            const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
            this.setZoom(this.zoom * factor, focusX, focusY);
        }

        startPan(e) {
            e.preventDefault();
            this.panning = {
                x: e.clientX,
                y: e.clientY,
                panX: this.panX,
                panY: this.panY,
            };
            this.updateCursor();
        }

        fitCanvas(redraw = true) {
            if (!this.naturalW || !this.naturalH) return;
            const maxW = Math.max(280, this.wrap.clientWidth);
            const maxH = Math.max(240, this.wrap.clientHeight || Math.min(window.innerHeight * 0.62, 720));
            this.fitScale = Math.min(maxW / this.naturalW, maxH / this.naturalH, 1);
            this.applyView(redraw);
        }

        applyView(redraw = true) {
            if (!this.naturalW || !this.naturalH) return;
            const scale = this.fitScale * this.zoom;
            const w = Math.max(1, Math.round(this.naturalW * scale));
            const h = Math.max(1, Math.round(this.naturalH * scale));
            this.canvas.width = w;
            this.canvas.height = h;
            this.canvas.style.width = `${w}px`;
            this.canvas.style.height = `${h}px`;
            this.img.style.width = `${w}px`;
            this.img.style.height = `${h}px`;
            const left = `calc(50% + ${this.panX}px)`;
            const top = `calc(50% + ${this.panY}px)`;
            this.canvas.style.left = left;
            this.canvas.style.top = top;
            this.img.style.left = left;
            this.img.style.top = top;
            if (this.zoomLabelEl) {
                this.zoomLabelEl.textContent = `${Math.round(this.zoom * 100)}%`;
            }
            if (redraw) this.redraw();
        }

        toNorm(x, y) {
            return [
                clamp(x / this.canvas.width, 0, 1),
                clamp(y / this.canvas.height, 0, 1),
            ];
        }

        toCanvas(nx, ny) {
            return [nx * this.canvas.width, ny * this.canvas.height];
        }

        pointerPos(e) {
            const rect = this.canvas.getBoundingClientRect();
            const sx = this.canvas.width / Math.max(1, rect.width);
            const sy = this.canvas.height / Math.max(1, rect.height);
            return [(e.clientX - rect.left) * sx, (e.clientY - rect.top) * sy];
        }

        onPointerDown(e) {
            if (e.button === 2) {
                this.startPan(e);
                return;
            }
            if (e.button !== 0) return;
            const [x, y] = this.pointerPos(e);
            if (x < -2 || y < -2 || x > this.canvas.width + 2 || y > this.canvas.height + 2) return;
            const [nx, ny] = this.toNorm(x, y);

            if (this.mode === 'select') {
                this.beginSelectEdit(x, y, nx, ny);
                return;
            }

            if (this.mode === 'rect') {
                this.drawing = { x0: nx, y0: ny, x1: nx, y1: ny };
                return;
            }

            if (this.mode === 'poly') {
                this.polyPoints.push(nx, ny);
                this.redraw();
            }
        }

        beginSelectEdit(x, y, nx, ny) {
            const selected = this.selectedShape();
            if (selected) {
                if (selected.type === 'rectangle') {
                    const handle = this.hitTestHandle(selected, x, y);
                    if (handle) {
                        this.editDrag = {
                            kind: 'resize',
                            shapeId: selected.id,
                            handle,
                            startX: x,
                            startY: y,
                            origPoints: selected.points.slice(),
                            cursor: `${handle}-resize`,
                        };
                        this.updateCursor();
                        return;
                    }
                }
                if (selected.type === 'polygon') {
                    const vIdx = this.hitTestVertex(selected, x, y);
                    if (vIdx >= 0) {
                        this.editDrag = {
                            kind: 'vertex',
                            shapeId: selected.id,
                            vertex: vIdx,
                            startX: x,
                            startY: y,
                            origPoints: selected.points.slice(),
                            cursor: 'pointer',
                        };
                        this.updateCursor();
                        return;
                    }
                }
            }

            const hit = this.hitTest(x, y);
            this.selectedId = hit ? hit.id : null;
            this.renderShapesList();
            this.renderAttrs();
            this.redraw();

            if (hit) {
                this.editDrag = {
                    kind: 'move',
                    shapeId: hit.id,
                    startX: x,
                    startY: y,
                    startNx: nx,
                    startNy: ny,
                    origPoints: hit.points.slice(),
                    cursor: 'move',
                    moved: false,
                };
                this.updateCursor();
            }
        }

        onPointerMove(e) {
            if (this.panning) {
                this.panX = this.panning.panX + (e.clientX - this.panning.x);
                this.panY = this.panning.panY + (e.clientY - this.panning.y);
                this.applyView();
                return;
            }

            if (this.editDrag) {
                this.applyEditDrag(e);
                return;
            }

            if (this.drawing) {
                const [x, y] = this.pointerPos(e);
                const [nx, ny] = this.toNorm(x, y);
                this.drawing.x1 = nx;
                this.drawing.y1 = ny;
                this.redraw();
                return;
            }

            if (this.mode === 'select') {
                this.updateHoverCursor(e);
            }
        }

        updateHoverCursor(e) {
            const [x, y] = this.pointerPos(e);
            const selected = this.selectedShape();
            if (selected?.type === 'rectangle') {
                const handle = this.hitTestHandle(selected, x, y);
                if (handle) {
                    this.canvas.style.cursor = `${handle}-resize`;
                    return;
                }
            }
            if (selected?.type === 'polygon' && this.hitTestVertex(selected, x, y) >= 0) {
                this.canvas.style.cursor = 'pointer';
                return;
            }
            this.canvas.style.cursor = this.hitTest(x, y) ? 'move' : 'default';
        }

        applyEditDrag(e) {
            const drag = this.editDrag;
            const shape = (this.doc.shapes || []).find((s) => s.id === drag.shapeId);
            if (!shape) return;
            const [x, y] = this.pointerPos(e);
            const [nx, ny] = this.toNorm(x, y);

            if (drag.kind === 'move') {
                const dx = nx - drag.startNx;
                const dy = ny - drag.startNy;
                if (Math.abs(dx) > 0.0005 || Math.abs(dy) > 0.0005) drag.moved = true;
                const pts = drag.origPoints.slice();
                for (let i = 0; i < pts.length; i += 2) {
                    pts[i] = clamp(pts[i] + dx, 0, 1);
                    pts[i + 1] = clamp(pts[i + 1] + dy, 0, 1);
                }
                shape.points = pts;
            } else if (drag.kind === 'resize' && shape.type === 'rectangle') {
                let minX = Math.min(drag.origPoints[0], drag.origPoints[2]);
                let maxX = Math.max(drag.origPoints[0], drag.origPoints[2]);
                let minY = Math.min(drag.origPoints[1], drag.origPoints[3]);
                let maxY = Math.max(drag.origPoints[1], drag.origPoints[3]);
                if (drag.handle.includes('w')) minX = nx;
                if (drag.handle.includes('e')) maxX = nx;
                if (drag.handle.includes('n')) minY = ny;
                if (drag.handle.includes('s')) maxY = ny;
                shape.points = [
                    clamp(minX, 0, 1), clamp(minY, 0, 1),
                    clamp(maxX, 0, 1), clamp(maxY, 0, 1),
                ];
            } else if (drag.kind === 'vertex' && shape.type === 'polygon') {
                const pts = drag.origPoints.slice();
                pts[drag.vertex] = nx;
                pts[drag.vertex + 1] = ny;
                shape.points = pts;
            }

            this.redraw();
        }

        onPointerUp() {
            if (this.panning) {
                this.panning = null;
                this.updateCursor();
                return;
            }

            if (this.editDrag) {
                const drag = this.editDrag;
                this.editDrag = null;
                this.updateCursor();
                if (drag.kind === 'move' && !drag.moved) {
                    this.renderAttrs();
                    return;
                }
                const shape = (this.doc.shapes || []).find((s) => s.id === drag.shapeId);
                if (shape?.type === 'rectangle' && shape.points.length >= 4) {
                    const [x0, y0, x1, y1] = shape.points;
                    if (Math.abs(x1 - x0) < MIN_BOX || Math.abs(y1 - y0) < MIN_BOX) {
                        shape.points = drag.origPoints.slice();
                        this.redraw();
                        return;
                    }
                }
                this.markDirty();
                this.renderShapesList();
                this.renderAttrs();
                this.redraw();
                return;
            }

            if (!this.drawing) return;
            const { x0, y0, x1, y1 } = this.drawing;
            this.drawing = null;
            if (Math.abs(x1 - x0) < MIN_BOX || Math.abs(y1 - y0) < MIN_BOX) {
                this.redraw();
                return;
            }
            const shape = this.newShape('rectangle', [x0, y0, x1, y1]);
            this.doc.shapes.push(shape);
            this.selectedId = shape.id;
            this.markDirty();
            this.renderShapesList();
            this.renderAttrs();
            this.redraw();
        }

        finishPolygon() {
            if (this.mode !== 'poly' || this.polyPoints.length < 6) return;
            const shape = this.newShape('polygon', [...this.polyPoints]);
            this.doc.shapes.push(shape);
            this.selectedId = shape.id;
            this.polyPoints = [];
            this.markDirty();
            this.renderShapesList();
            this.renderAttrs();
            this.redraw();
        }

        newShape(type, points) {
            const trackRaw = this.trackInput.value;
            const trackId = trackRaw === '' ? null : Number(trackRaw);
            return {
                id: `s${Math.random().toString(16).slice(2, 12)}`,
                type,
                label: this.classSelect.value || this.classes[0],
                points,
                track_id: Number.isFinite(trackId) ? trackId : null,
                attributes: {},
            };
        }

        hitTest(x, y) {
            for (let i = this.doc.shapes.length - 1; i >= 0; i -= 1) {
                const s = this.doc.shapes[i];
                if (s.type === 'rectangle' && s.points.length >= 4) {
                    const [x1, y1] = this.toCanvas(s.points[0], s.points[1]);
                    const [x2, y2] = this.toCanvas(s.points[2], s.points[3]);
                    const minX = Math.min(x1, x2);
                    const maxX = Math.max(x1, x2);
                    const minY = Math.min(y1, y2);
                    const maxY = Math.max(y1, y2);
                    if (x >= minX && x <= maxX && y >= minY && y <= maxY) return s;
                }
                if (s.type === 'polygon' && s.points.length >= 6) {
                    if (this.pointInPoly(x, y, s.points)) return s;
                }
            }
            return null;
        }

        hitTestHandle(shape, x, y) {
            const handles = this.rectHandles(shape);
            for (const [name, hx, hy] of handles) {
                if (Math.abs(x - hx) <= HANDLE && Math.abs(y - hy) <= HANDLE) return name;
            }
            return null;
        }

        hitTestVertex(shape, x, y) {
            for (let i = 0; i < shape.points.length; i += 2) {
                const [px, py] = this.toCanvas(shape.points[i], shape.points[i + 1]);
                if (Math.abs(x - px) <= HANDLE && Math.abs(y - py) <= HANDLE) return i;
            }
            return -1;
        }

        rectHandles(shape) {
            const [x1, y1] = this.toCanvas(shape.points[0], shape.points[1]);
            const [x2, y2] = this.toCanvas(shape.points[2], shape.points[3]);
            const minX = Math.min(x1, x2);
            const maxX = Math.max(x1, x2);
            const minY = Math.min(y1, y2);
            const maxY = Math.max(y1, y2);
            const mx = (minX + maxX) / 2;
            const my = (minY + maxY) / 2;
            return [
                ['nw', minX, minY],
                ['n', mx, minY],
                ['ne', maxX, minY],
                ['e', maxX, my],
                ['se', maxX, maxY],
                ['s', mx, maxY],
                ['sw', minX, maxY],
                ['w', minX, my],
            ];
        }

        pointInPoly(x, y, points) {
            const pts = [];
            for (let i = 0; i < points.length; i += 2) {
                pts.push(this.toCanvas(points[i], points[i + 1]));
            }
            let inside = false;
            for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
                const xi = pts[i][0];
                const yi = pts[i][1];
                const xj = pts[j][0];
                const yj = pts[j][1];
                const intersect = ((yi > y) !== (yj > y))
                    && (x < ((xj - xi) * (y - yi)) / ((yj - yi) || 1e-6) + xi);
                if (intersect) inside = !inside;
            }
            return inside;
        }

        redraw() {
            const ctx = this.ctx;
            ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
            (this.doc.shapes || []).forEach((s, idx) => {
                const shownLabel = this.displayLabel(s.label);
                const classIdx = Math.max(0, this.classes.indexOf(shownLabel));
                const color = COLORS[classIdx % COLORS.length] || COLORS[idx % COLORS.length];
                const selected = s.id === this.selectedId;
                ctx.strokeStyle = color;
                ctx.fillStyle = `${color}${selected ? '66' : '33'}`;
                ctx.lineWidth = selected ? 3 : 2;

                if (s.type === 'rectangle' && s.points.length >= 4) {
                    const [x1, y1] = this.toCanvas(s.points[0], s.points[1]);
                    const [x2, y2] = this.toCanvas(s.points[2], s.points[3]);
                    const w = x2 - x1;
                    const h = y2 - y1;
                    ctx.fillRect(x1, y1, w, h);
                    ctx.strokeRect(x1, y1, w, h);
                    ctx.fillStyle = color;
                    ctx.font = '12px sans-serif';
                    const label = s.track_id != null ? `${shownLabel}#${s.track_id}` : shownLabel;
                    ctx.fillText(label, Math.min(x1, x2) + 4, Math.min(y1, y2) + 14);
                    if (selected) this.drawHandles(ctx, this.rectHandles(s));
                } else if (s.type === 'polygon' && s.points.length >= 6) {
                    ctx.beginPath();
                    for (let i = 0; i < s.points.length; i += 2) {
                        const [px, py] = this.toCanvas(s.points[i], s.points[i + 1]);
                        if (i === 0) ctx.moveTo(px, py);
                        else ctx.lineTo(px, py);
                    }
                    ctx.closePath();
                    ctx.fill();
                    ctx.stroke();
                    if (selected) {
                        const verts = [];
                        for (let i = 0; i < s.points.length; i += 2) {
                            const [px, py] = this.toCanvas(s.points[i], s.points[i + 1]);
                            verts.push(['', px, py]);
                        }
                        this.drawHandles(ctx, verts);
                    }
                }
            });

            if (this.drawing) {
                const [x1, y1] = this.toCanvas(this.drawing.x0, this.drawing.y0);
                const [x2, y2] = this.toCanvas(this.drawing.x1, this.drawing.y1);
                ctx.strokeStyle = '#fff';
                ctx.setLineDash([6, 4]);
                ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
                ctx.setLineDash([]);
            }

            if (this.polyPoints.length >= 2) {
                ctx.strokeStyle = '#fff';
                ctx.fillStyle = '#fff';
                ctx.setLineDash([4, 4]);
                ctx.beginPath();
                for (let i = 0; i < this.polyPoints.length; i += 2) {
                    const [px, py] = this.toCanvas(this.polyPoints[i], this.polyPoints[i + 1]);
                    if (i === 0) ctx.moveTo(px, py);
                    else ctx.lineTo(px, py);
                }
                ctx.stroke();
                ctx.setLineDash([]);
                for (let i = 0; i < this.polyPoints.length; i += 2) {
                    const [px, py] = this.toCanvas(this.polyPoints[i], this.polyPoints[i + 1]);
                    ctx.beginPath();
                    ctx.arc(px, py, 3, 0, Math.PI * 2);
                    ctx.fill();
                }
            }
        }

        drawHandles(ctx, handles) {
            handles.forEach(([, hx, hy]) => {
                ctx.fillStyle = '#fff';
                ctx.strokeStyle = '#111';
                ctx.lineWidth = 1;
                ctx.fillRect(hx - HANDLE / 2, hy - HANDLE / 2, HANDLE, HANDLE);
                ctx.strokeRect(hx - HANDLE / 2, hy - HANDLE / 2, HANDLE, HANDLE);
            });
        }

        renderShapesList() {
            this.shapesEl.innerHTML = '';
            const shapes = this.doc.shapes || [];
            if (this.shapeCountEl) this.shapeCountEl.textContent = String(shapes.length);
            if (!shapes.length) {
                const empty = document.createElement('div');
                empty.className = 'list-group-item small text-body-secondary';
                empty.textContent = t('Select a shape');
                this.shapesEl.appendChild(empty);
                return;
            }
            shapes.forEach((s) => {
                const shownLabel = this.displayLabel(s.label);
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = `list-group-item list-group-item-action py-1 px-2 ${s.id === this.selectedId ? 'active' : ''}`;
                btn.textContent = `${s.type} · ${shownLabel}${s.track_id != null ? ` #${s.track_id}` : ''}`;
                btn.addEventListener('click', () => {
                    this.selectedId = s.id;
                    this.renderShapesList();
                    this.renderAttrs();
                    this.redraw();
                });
                this.shapesEl.appendChild(btn);
            });
        }

        selectedShape() {
            return (this.doc.shapes || []).find((s) => s.id === this.selectedId) || null;
        }

        renderAttrs() {
            const shape = this.selectedShape();
            if (!shape) {
                this.attrsEl.innerHTML = `<div class="small text-body-secondary">${t('Select a shape')}</div>`;
                return;
            }
            shape.attributes = shape.attributes || {};
            const currentLabel = this.resolveLabel(shape.label);
            if (currentLabel && currentLabel !== shape.label) {
                shape.label = currentLabel;
            }
            const classOptions = [...this.classes];
            if (shape.label && !classOptions.includes(shape.label)) {
                classOptions.push(shape.label);
            }
            let html = `
                <div class="mb-2">
                    <label class="form-label small mb-0">${t('Class')}</label>
                    <select class="form-select form-select-sm" id="attr-class">
                        ${classOptions.map((c) => `<option value="${this.escapeAttr(c)}" ${c === shape.label ? 'selected' : ''}>${this.escapeHtml(c)}</option>`).join('')}
                    </select>
                </div>
                <div class="mb-2">
                    <label class="form-label small mb-0">${t('Track ID')}</label>
                    <input type="number" class="form-control form-control-sm" id="attr-track" value="${shape.track_id ?? ''}">
                </div>`;
            (this.attrSchema || []).forEach((schema) => {
                const key = schema.name || schema;
                const type = schema.type || 'text';
                const val = shape.attributes[key];
                if (type === 'bool') {
                    html += `<div class="form-check mb-1">
                        <input class="form-check-input attr-field" data-key="${this.escapeAttr(key)}" data-type="bool" type="checkbox" id="attr-${this.escapeAttr(key)}" ${val ? 'checked' : ''}>
                        <label class="form-check-label small" for="attr-${this.escapeAttr(key)}">${this.escapeHtml(key)}</label>
                    </div>`;
                } else if (type === 'enum' && schema.options) {
                    html += `<div class="mb-2"><label class="form-label small mb-0">${this.escapeHtml(key)}</label>
                        <select class="form-select form-select-sm attr-field" data-key="${this.escapeAttr(key)}" data-type="enum">
                            ${schema.options.map((o) => `<option value="${this.escapeAttr(o)}" ${val === o ? 'selected' : ''}>${this.escapeHtml(o)}</option>`).join('')}
                        </select></div>`;
                } else {
                    html += `<div class="mb-2"><label class="form-label small mb-0">${this.escapeHtml(key)}</label>
                        <input class="form-control form-control-sm attr-field" data-key="${this.escapeAttr(key)}" data-type="${this.escapeAttr(type)}" value="${this.escapeAttr(val ?? '')}"></div>`;
                }
            });
            this.attrsEl.innerHTML = html;

            document.getElementById('attr-class')?.addEventListener('change', (e) => {
                shape.label = e.target.value;
                this.markDirty();
                this.renderShapesList();
                this.redraw();
            });
            document.getElementById('attr-track')?.addEventListener('change', (e) => {
                const v = e.target.value;
                shape.track_id = v === '' ? null : Number(v);
                this.markDirty();
                this.renderShapesList();
                this.redraw();
            });
            this.attrsEl.querySelectorAll('.attr-field').forEach((el) => {
                el.addEventListener('change', () => {
                    const key = el.dataset.key;
                    if (el.dataset.type === 'bool') shape.attributes[key] = el.checked;
                    else if (el.dataset.type === 'number') shape.attributes[key] = Number(el.value);
                    else shape.attributes[key] = el.value;
                    this.markDirty();
                });
            });
        }

        deleteSelected() {
            if (!this.selectedId) return;
            this.doc.shapes = this.doc.shapes.filter((s) => s.id !== this.selectedId);
            this.selectedId = null;
            this.markDirty();
            this.renderShapesList();
            this.renderAttrs();
            this.redraw();
        }

        async deleteCurrentImage() {
            if (!this.currentName) return;
            const ok = typeof window.appConfirm === 'function'
                ? await window.appConfirm({
                    title: t('Delete image'),
                    message: t('Delete this image permanently?'),
                    confirmText: t('Delete'),
                    tone: 'danger',
                })
                : window.confirm(t('Delete this image permanently?'));
            if (!ok) return;

            const deleting = this.currentName;
            const idx = this.imageNames.indexOf(deleting);
            try {
                const res = await fetch(`/datasets/api/${encodeURIComponent(this.name)}/images/delete`, {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                    body: JSON.stringify({ images: [deleting] }),
                });
                const data = await res.json();
                if (!res.ok || data.status === 'error') {
                    throw new Error(data.message || t('Request failed'));
                }

                this.dirty = false;
                this.imageNames = this.imageNames.filter((n) => n !== deleting);
                delete this.imageMeta[deleting];

                if (!this.imageNames.length) {
                    this.currentName = '';
                    this.doc = { shapes: [], width: 0, height: 0, image_label: null, keypoints: [] };
                    this.revokeObjectUrl();
                    this.img.hidden = true;
                    this.img.removeAttribute('src');
                    this.emptyEl?.classList.remove('d-none');
                    this.renderQueue();
                    this.renderShapesList();
                    this.renderAttrs();
                    this.updateIndex();
                    this.setStatus(t('No images'));
                    const url = new URL(window.location.href);
                    url.searchParams.delete('image');
                    window.history.replaceState({}, '', url);
                    return;
                }

                const next = this.imageNames[Math.min(Math.max(idx, 0), this.imageNames.length - 1)];
                await this.openImage(next, { force: true });
                this.setStatus(t('Image deleted'), 'success');
            } catch (err) {
                this.setStatus(err.message || t('Request failed'), 'danger');
            }
        }

        async save() {
            this.setStatus(t('Saving…'), 'info');
            try {
                const res = await fetch(`/datasets/api/${this.name}/annotations/${encodeURIComponent(this.currentName)}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                    body: JSON.stringify(this.doc),
                });
                const data = await res.json();
                if (data.status === 'error') throw new Error(data.message);
                this.dirty = false;
                if (this.imageMeta[this.currentName]) {
                    const labeled = this.task === 'classify'
                        ? !!this.doc.image_label
                        : (this.doc.shapes || []).length > 0;
                    this.imageMeta[this.currentName].labeled = labeled;
                }
                this.setStatus(t('Saved'), 'success');
                this.renderQueue();
            } catch (err) {
                this.setStatus(err.message || t('Request failed'), 'danger');
            }
        }

        async copyPrev() {
            try {
                const res = await fetch(`/datasets/api/${this.name}/annotations/${encodeURIComponent(this.currentName)}/copy-prev`, {
                    method: 'POST',
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                });
                const data = await res.json();
                if (data.status === 'error') throw new Error(data.message);
                this.doc = data.annotation;
                this.normalizeShapeLabels({ markDirty: false });
                this.markDirty();
                this.renderShapesList();
                this.redraw();
                this.setStatus(t('Copied from previous'), 'info');
            } catch (err) {
                this.setStatus(err.message || t('Request failed'), 'danger');
            }
        }

        async interpolate() {
            const shape = this.selectedShape();
            if (!shape || shape.track_id == null) {
                this.setStatus(t('Select a shape with track ID'), 'warning');
                return;
            }
            if (!this.interpStart) {
                this.interpStart = this.currentName;
                this.setStatus(`${t('Interpolate start')}: ${this.currentName}`, 'info');
                return;
            }
            try {
                const res = await fetch(`/datasets/api/${this.name}/tracks/interpolate`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                    body: JSON.stringify({
                        track_id: shape.track_id,
                        start_image: this.interpStart,
                        end_image: this.currentName,
                    }),
                });
                const data = await res.json();
                if (data.status === 'error') throw new Error(data.message);
                this.setStatus(`${t('Interpolated frames')}: ${data.filled}`, 'success');
                this.interpStart = null;
                await this.loadImageList();
            } catch (err) {
                this.setStatus(err.message || t('Request failed'), 'danger');
            }
        }

        async autoLabelCurrent() {
            if (!this.currentName) return;
            if (this.dirty) {
                const okDiscard = await window.appConfirm({
                    title: t('Unsaved'),
                    message: t('Discard unsaved changes?'),
                    confirmText: t('Discard'),
                    tone: 'warning',
                });
                if (!okDiscard) return;
            }
            const hasShapes = (this.doc.shapes || []).length > 0;
            if (hasShapes) {
                const okReplace = await window.appConfirm({
                    title: t('Auto-label'),
                    message: t('Replace annotations with auto-label?'),
                    confirmText: t('Auto-label'),
                    tone: 'warning',
                });
                if (!okReplace) return;
            }

            const btn = document.getElementById('ann-autolabel');
            btn?.classList.add('is-busy');
            this.dirty = false;
            this.setStatus(t('Auto-label running…'), 'info');
            try {
                const res = await fetch(`/datasets/api/${encodeURIComponent(this.name)}/autolabel`, {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                    body: JSON.stringify({
                        image: this.currentName,
                        only_unlabeled: false,
                        limit: 1,
                    }),
                });
                const data = await res.json();
                if (!res.ok || data.status === 'error') {
                    throw new Error(data.message || t('Request failed'));
                }
                await this.openImage(this.currentName, { force: true });
                this.setStatus(`${t('Labeled')}: ${data.labeled}/${data.processed}`, 'success');
            } catch (err) {
                this.setStatus(err.message || t('Request failed'), 'danger');
            } finally {
                btn?.classList.remove('is-busy');
            }
        }

        onKey(e) {
            if (e.target.matches('input, textarea, select')) return;
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'a') {
                e.preventDefault();
                this.autoLabelCurrent();
            } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
                e.preventDefault();
                this.save();
            } else if (e.key === 'a' || e.key === 'A') {
                e.preventDefault();
                this.navigate(-1);
            } else if (e.key === 'd' || e.key === 'D') {
                e.preventDefault();
                this.navigate(1);
            } else if (e.key === ' ') {
                e.preventDefault();
                this.navigate(1, true);
            } else if (e.key === 'w' || e.key === 'W') {
                this.setMode('rect');
            } else if (e.key === 'v' || e.key === 'V' || e.key === 'Escape') {
                this.setMode('select');
            } else if (e.key === 'Delete' || e.key === 'Backspace') {
                e.preventDefault();
                this.deleteSelected();
            } else if (e.key === '=' || e.key === '+') {
                e.preventDefault();
                this.nudgeZoom(1.25);
            } else if (e.key === '-' || e.key === '_') {
                e.preventDefault();
                this.nudgeZoom(1 / 1.25);
            } else if (e.key === '0') {
                e.preventDefault();
                this.resetView();
            } else if (/^[1-9]$/.test(e.key)) {
                const idx = Number(e.key) - 1;
                if (this.classes[idx]) {
                    this.classSelect.value = this.classes[idx];
                    const shape = this.selectedShape();
                    if (shape) {
                        shape.label = this.classes[idx];
                        this.markDirty();
                        this.renderShapesList();
                        this.redraw();
                    }
                }
            } else if (e.key === 'Enter' && this.mode === 'poly') {
                this.finishPolygon();
            }
        }
    }

    window.datasetAnnotator = new DatasetAnnotator(root);
})();
