/* ============================================
   MAIN.JS - Common Utilities & Initialization
   Rori Hotel Careers Portal
   ============================================ */

document.addEventListener('DOMContentLoaded', function() {
    console.log('Rori Hotel Careers loaded.');

    /**
     * Auto-dismisses alert notifications with pause-on-hover and Bootstrap 5 compatibility.
     * @param {HTMLElement} alertEl - Target alert DOM element
     * @param {number} delay - Duration before auto-dismissal in ms (default: 5000ms)
     */
    function setupAlertAutoDismiss(alertEl, delay = 5000) {
        // Skip permanent alerts
        if (alertEl.classList.contains('alert-permanent')) return;

        let dismissTimer = null;

        const startTimer = () => {
            dismissTimer = setTimeout(() => {
                dismissAlert(alertEl);
            }, delay);
        };

        const stopTimer = () => {
            if (dismissTimer) {
                clearTimeout(dismissTimer);
                dismissTimer = null;
            }
        };

        // Pause auto-dismiss when user hovers over the alert to read content
        alertEl.addEventListener('mouseenter', stopTimer);
        alertEl.addEventListener('mouseleave', startTimer);

        // Clear timer if manually closed
        const closeBtn = alertEl.querySelector('.btn-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', stopTimer, { once: true });
        }

        // Start initial auto-dismiss countdown
        startTimer();
    }

    /**
     * Gracefully removes alert using Bootstrap 5 JS API or CSS fallback transition.
     * @param {HTMLElement} alertEl 
     */
    function dismissAlert(alertEl) {
        if (!document.body.contains(alertEl)) return;

        // Use Bootstrap 5 Alert component instance if available
        if (typeof bootstrap !== 'undefined' && bootstrap.Alert) {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alertEl);
            bsAlert.close();
        } else {
            // Vanilla JS fallback with smooth fade and collapse
            alertEl.classList.remove('show');
            alertEl.style.transition = 'opacity 0.3s cubic-bezier(0.16, 1, 0.3, 1), transform 0.3s cubic-bezier(0.16, 1, 0.3, 1)';
            alertEl.style.opacity = '0';
            alertEl.style.transform = 'translateY(-8px)';

            setTimeout(() => {
                if (alertEl.parentNode) {
                    alertEl.remove();
                }
            }, 300);
        }
    }

    // Initialize auto-dismiss for all initial page alerts
    document.querySelectorAll('.alert').forEach(alert => {
        setupAlertAutoDismiss(alert, 5000);
    });

    // Expose utility globally for dynamically injected flash messages
    window.RoriCareers = window.RoriCareers || {};
    window.RoriCareers.setupAlertAutoDismiss = setupAlertAutoDismiss;
});
