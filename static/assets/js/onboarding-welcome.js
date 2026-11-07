/**
 * Computer Vision Counter (CVCounter)
 * Onboarding
 *
 * Developed by: Aleksandr Kireev
 * Website: https://bespredel.name
 */

(function () {
    'use strict';

    document.querySelectorAll('[data-onboarding-action="skip"]').forEach((btn) => {
        btn.addEventListener('click', async () => {
            await fetch('/settings/api/onboarding/complete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'skip' }),
            });
            const banner = document.getElementById('onboarding-welcome-banner');
            if (banner) banner.remove();
        });
    });
})();
