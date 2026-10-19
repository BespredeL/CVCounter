/**
 * Computer Vision Counter (CVCounter)
 * Reports page interactions and deletion.
 *
 * Developed by: Aleksandr Kireev
 * Created: 19.10.2026
 * Website: https://bespredel.name
 */

(function () {
    const t = (key, params) => {
        let msg = typeof window.trans === 'function' ? window.trans(key) : key;
        if (params && typeof params === 'object') {
            for (const [k, v] of Object.entries(params)) {
                msg = msg.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
            }
        }
        return msg;
    };

    function toast(message, type = 'primary') {
        if (typeof window.showToast === 'function') {
            window.showToast(message, type);
        }
    }

    document.addEventListener('click', async function (e) {
        const btn = e.target.closest('.btn-delete-report');
        if (!btn) return;

        e.preventDefault();
        e.stopPropagation();

        const reportId = btn.dataset.reportId;
        const redirectUrl = btn.dataset.redirectUrl;
        if (!reportId) return;

        const confirmMsg = t('Are you sure you want to delete report #{id}?', { id: reportId });
        const confirmed = typeof window.appConfirm === 'function'
            ? await window.appConfirm({
                title: t('Delete report'),
                message: confirmMsg,
                confirmText: t('Delete'),
                tone: 'danger',
            })
            : confirm(confirmMsg);

        if (!confirmed) return;

        btn.disabled = true;

        try {
            const res = await fetch(`/reports/api/${encodeURIComponent(reportId)}/delete`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            const data = await res.json().catch(() => ({}));

            if (!res.ok || !data.ok) {
                throw new Error((data && data.error) ? data.error : t('Failed to delete report'));
            }

            toast(data.message || t('Report deleted successfully'), 'success');

            if (redirectUrl) {
                setTimeout(() => {
                    window.location.href = redirectUrl;
                }, 400);
            } else {
                const row = btn.closest('tr');
                if (row) {
                    row.style.transition = 'opacity 0.25s ease, transform 0.25s ease';
                    row.style.opacity = '0';
                    row.style.transform = 'scale(0.97)';
                    setTimeout(() => {
                        row.remove();
                        // If no more rows, reload to update pagination and metrics
                        const remaining = document.querySelectorAll('tbody tr:not(.empty-state)');
                        if (remaining.length === 0) {
                            window.location.reload();
                        }
                    }, 250);
                } else {
                    window.location.reload();
                }
            }
        } catch (err) {
            toast(err.message || t('Failed to delete report'), 'danger');
            btn.disabled = false;
        }
    });
})();
