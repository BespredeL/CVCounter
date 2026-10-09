/**
 * Computer Vision Counter (CVCounter)
 * Help & Documentation interactive client-side logic.
 *
 * Developed by: Aleksandr Kireev
 * Website: https://bespredel.name
 */

document.addEventListener('DOMContentLoaded', function () {
    const t = (key) => (typeof window.trans === 'function' ? window.trans(key) : key);

    // 1. Live Search & Category Filtering
    const searchInput = document.getElementById('help-search');
    const searchClear = document.getElementById('help-search-clear');
    const filterChips = document.querySelectorAll('.help-chip');
    const searchableItems = document.querySelectorAll('.help-searchable-item');
    const topicGroups = document.querySelectorAll('.help-topic-group');
    const emptyState = document.getElementById('help-empty-state');
    const resetSearchBtn = document.getElementById('help-reset-search-btn');
    const totalBadge = document.getElementById('help-total-items-badge');

    if (totalBadge) {
        totalBadge.textContent = searchableItems.length;
    }

    function filterDocumentation() {
        const query = (searchInput.value || '').trim().toLowerCase();
        const activeChip = document.querySelector('.help-chip.active');
        const activeCategory = activeChip ? activeChip.getAttribute('data-filter') : 'all';

        if (searchClear) {
            searchClear.style.display = query.length > 0 ? 'block' : 'none';
        }

        let visibleCount = 0;

        searchableItems.forEach(function (item) {
            const text = (item.innerText || '').toLowerCase();
            const keywords = (item.getAttribute('data-keywords') || '').toLowerCase();
            const matchesQuery = !query || text.includes(query) || keywords.includes(query);

            let matchesCategory = true;
            if (activeCategory && activeCategory !== 'all') {
                const parentGroup = item.closest('.help-topic-group');
                matchesCategory = parentGroup && parentGroup.id === activeCategory;
            }

            if (matchesQuery && matchesCategory) {
                item.style.display = '';
                visibleCount++;
            } else {
                item.style.display = 'none';
            }
        });

        // Show/hide section containers based on whether they have visible children
        topicGroups.forEach(function (group) {
            if (activeCategory !== 'all' && group.id !== activeCategory && !query) {
                group.style.display = 'none';
                return;
            }

            const visibleChildren = group.querySelectorAll('.help-searchable-item:not([style*="display: none"])');
            const isWorkflow = group.id === 'sec-workflow';
            if (visibleChildren.length > 0 || (isWorkflow && (!query || 'workflow общая схема'.includes(query)))) {
                group.style.display = '';
            } else {
                group.style.display = 'none';
            }
        });

        if (emptyState) {
            emptyState.style.display = visibleCount === 0 ? 'block' : 'none';
        }
    }

    if (searchInput) {
        searchInput.addEventListener('input', filterDocumentation);
    }

    if (searchClear) {
        searchClear.addEventListener('click', function () {
            searchInput.value = '';
            filterDocumentation();
            searchInput.focus();
        });
    }

    if (resetSearchBtn) {
        resetSearchBtn.addEventListener('click', function () {
            searchInput.value = '';
            filterChips.forEach(c => c.classList.remove('active'));
            const allChip = document.querySelector('.help-chip[data-filter="all"]');
            if (allChip) allChip.classList.add('active');
            filterDocumentation();
        });
    }

    filterChips.forEach(function (chip) {
        chip.addEventListener('click', function () {
            filterChips.forEach(c => c.classList.remove('active'));
            this.classList.add('active');
            filterDocumentation();

            const filterTarget = this.getAttribute('data-filter');
            if (filterTarget && filterTarget !== 'all') {
                const targetEl = document.getElementById(filterTarget);
                if (targetEl) {
                    targetEl.scrollIntoView({behavior: 'smooth', block: 'start'});
                }
            }
        });
    });

    // Global Keyboard Shortcut: Ctrl+K or / to focus search, Space to test Pause/Start on demo
    document.addEventListener('keydown', function (e) {
        if ((e.ctrlKey && e.key.toLowerCase() === 'k') || (e.key === '/' && document.activeElement !== searchInput && !['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName))) {
            e.preventDefault();
            if (searchInput) {
                searchInput.focus();
                searchInput.select();
            }
        } else if (e.key === 'Escape' && document.activeElement === searchInput) {
            searchInput.value = '';
            filterDocumentation();
            searchInput.blur();
        } else if ((e.code === 'Space' || e.key === ' ' || e.key === 'Spacebar') && document.activeElement !== searchInput && !['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) {
            const mockToggle = document.getElementById('help-mock-toggle');
            if (mockToggle) {
                e.preventDefault();
                mockToggle.click();
                // Flash the shortcut cheat-sheet card
                const spaceCard = document.querySelector('.help-shortcut-card[data-keywords*="space"]');
                if (spaceCard) {
                    spaceCard.classList.add('help-shortcut-card--active');
                    setTimeout(() => spaceCard.classList.remove('help-shortcut-card--active'), 350);
                }
            }
        }
    });

    // 2. Interactive Status Mock Switcher
    const mockCard = document.getElementById('help-status-mock');
    const mockBadge = document.getElementById('help-status-badge');
    const btnRunning = document.getElementById('btn-mock-running');
    const btnPaused = document.getElementById('btn-mock-paused');
    const btnStopped = document.getElementById('btn-mock-stopped');

    if (mockCard && mockBadge && btnRunning && btnPaused && btnStopped) {
        const mockToggle = document.getElementById('help-mock-toggle');
        const mockStop = document.getElementById('help-mock-stop');

        function setMockStatus(statusClass, badgeText, activeBtn) {
            mockCard.classList.remove('counter-card--running', 'counter-card--paused', 'counter-card--stopped');
            mockCard.classList.add(statusClass);
            mockBadge.textContent = badgeText;

            [btnRunning, btnPaused, btnStopped].forEach(b => b.classList.remove('active'));
            activeBtn.classList.add('active');

            // Update toggle icon: running → show pause, else → show play
            if (mockToggle) {
                const iconPlay = mockToggle.querySelector('.icon-play');
                const iconPause = mockToggle.querySelector('.icon-pause');
                if (statusClass === 'counter-card--running') {
                    iconPlay && iconPlay.classList.add('d-none');
                    iconPause && iconPause.classList.remove('d-none');
                } else {
                    iconPlay && iconPlay.classList.remove('d-none');
                    iconPause && iconPause.classList.add('d-none');
                }
            }

            // Stop button is disabled when already stopped
            if (mockStop) {
                mockStop.disabled = (statusClass === 'counter-card--stopped');
            }
        }

        // Allow clicking the transport buttons directly on the card
        if (mockToggle) {
            mockToggle.addEventListener('click', function () {
                if (mockCard.classList.contains('counter-card--running')) {
                    setMockStatus('counter-card--paused', t('Counter paused'), btnPaused);
                } else {
                    setMockStatus('counter-card--running', t('Counter running'), btnRunning);
                }
            });
        }
        if (mockStop) {
            mockStop.addEventListener('click', function () {
                setMockStatus('counter-card--stopped', t('Counter stopped'), btnStopped);
            });
        }

        // Init: running state
        setMockStatus('counter-card--running', t('Counter running'), btnRunning);

        btnRunning.addEventListener('click', () => setMockStatus('counter-card--running', t('Counter running'), btnRunning));
        btnPaused.addEventListener('click', () => setMockStatus('counter-card--paused', t('Counter paused'), btnPaused));
        btnStopped.addEventListener('click', () => setMockStatus('counter-card--stopped', t('Counter stopped'), btnStopped));
    }

    // 3. Interactive Defective Keyboard Mock
    const defectInput = document.getElementById('help-demo-defect-val');
    const defectKeys = document.querySelectorAll('.help-demo-defect-key');
    const defectPlus = document.querySelector('.help-demo-defect-plus');
    const defectMinus = document.querySelector('.help-demo-defect-minus');
    const defectResets = document.querySelectorAll('.help-demo-defect-reset');
    const defectKbToggle = document.getElementById('help-demo-defect-kb-toggle');
    const defectCollapse = document.getElementById('help-demo-defect-collapse');

    if (defectKbToggle && defectCollapse) {
        defectKbToggle.addEventListener('click', function () {
            defectCollapse.classList.toggle('d-none');
        });
    }

    if (defectInput) {
        defectKeys.forEach(function (keyBtn) {
            keyBtn.addEventListener('click', function () {
                const digit = (this.getAttribute('data-value') || this.textContent).trim();
                let cur = defectInput.value.toString();
                if (cur === '0') cur = '';
                defectInput.value = (cur + digit).slice(0, 6) || '0';
            });
        });

        if (defectPlus) {
            defectPlus.addEventListener('click', function () {
                defectInput.value = Math.max(0, parseInt(defectInput.value || 0, 10) + 1);
            });
        }

        if (defectMinus) {
            defectMinus.addEventListener('click', function () {
                defectInput.value = Math.max(0, parseInt(defectInput.value || 0, 10) - 1);
            });
        }

        defectResets.forEach(function (rBtn) {
            rBtn.addEventListener('click', function () {
                defectInput.value = '0';
            });
        });
    }

    // 3b. Interactive Correction Keyboard Mock
    const correctInput = document.getElementById('help-demo-correct-val');
    const correctKeys = document.querySelectorAll('.help-demo-correct-key');
    const correctPlus = document.querySelector('.help-demo-correct-plus');
    const correctMinus = document.querySelector('.help-demo-correct-minus');
    const correctSign = document.querySelector('.help-demo-correct-sign');
    const correctResets = document.querySelectorAll('.help-demo-correct-reset');
    const correctKbToggle = document.getElementById('help-demo-correct-kb-toggle');
    const correctCollapse = document.getElementById('help-demo-correct-collapse');

    if (correctKbToggle && correctCollapse) {
        correctKbToggle.addEventListener('click', function () {
            correctCollapse.classList.toggle('d-none');
        });
    }

    if (correctInput) {
        correctKeys.forEach(function (keyBtn) {
            keyBtn.addEventListener('click', function () {
                const digit = (this.getAttribute('data-value') || this.textContent).trim();
                let cur = correctInput.value.toString();
                const isNeg = cur.startsWith('-');
                let raw = isNeg ? cur.slice(1) : cur;
                if (raw === '0') raw = '';
                raw = (raw + digit).slice(0, 6) || '0';
                correctInput.value = (isNeg && raw !== '0' ? '-' : '') + raw;
            });
        });

        if (correctSign) {
            correctSign.addEventListener('click', function () {
                let val = parseInt(correctInput.value || 0, 10);
                if (val !== 0) {
                    correctInput.value = (-val).toString();
                } else if (correctInput.value === '0') {
                    correctInput.value = '-0';
                } else if (correctInput.value === '-0') {
                    correctInput.value = '0';
                }
            });
        }

        if (correctPlus) {
            correctPlus.addEventListener('click', function () {
                let val = parseInt(correctInput.value || 0, 10);
                correctInput.value = (val + 1).toString();
            });
        }

        if (correctMinus) {
            correctMinus.addEventListener('click', function () {
                let val = parseInt(correctInput.value || 0, 10);
                correctInput.value = (val - 1).toString();
            });
        }

        correctResets.forEach(function (rBtn) {
            rBtn.addEventListener('click', function () {
                correctInput.value = '0';
            });
        });
    }

    // 4. Copy-to-clipboard buttons
    const copyButtons = document.querySelectorAll('.help-code-copy');
    copyButtons.forEach(function (btn) {
        btn.addEventListener('click', function () {
            const textToCopy = this.getAttribute('data-copy');
            if (!textToCopy) return;

            navigator.clipboard.writeText(textToCopy).then(() => {
                const originalHTML = this.innerHTML;
                this.classList.add('copied');
                this.innerHTML = `<span>${textToCopy}</span> <span class="bi bi-check-lg text-success"></span>`;
                setTimeout(() => {
                    this.classList.remove('copied');
                    this.innerHTML = originalHTML;
                }, 2000);
            }).catch(() => {
            });
        });
    });

    // 5. ScrollSpy & Back to Top
    const backToTopBtn = document.getElementById('help-back-to-top');
    const tocLinks = document.querySelectorAll('.help-toc-link');

    function handleScroll() {
        const scrollY = window.scrollY;

        // Back to top visibility
        if (backToTopBtn) {
            if (scrollY > 300) {
                backToTopBtn.classList.add('visible');
            } else {
                backToTopBtn.classList.remove('visible');
            }
        }

        // TOC Active tracking
        const sections = document.querySelectorAll('.help-section');
        let currentSectionId = '';

        sections.forEach(function (section) {
            const rect = section.getBoundingClientRect();
            if (rect.top <= 120 && rect.bottom >= 120) {
                currentSectionId = section.id;
            }
        });

        if (currentSectionId) {
            tocLinks.forEach(function (link) {
                if (link.getAttribute('href') === '#' + currentSectionId) {
                    link.classList.add('active');
                } else {
                    link.classList.remove('active');
                }
            });
        }
    }

    window.addEventListener('scroll', handleScroll, {passive: true});

    if (backToTopBtn) {
        backToTopBtn.addEventListener('click', function () {
            window.scrollTo({top: 0, behavior: 'smooth'});
        });
    }
});
