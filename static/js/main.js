document.addEventListener('DOMContentLoaded', function() {
    console.log('Rori Hotel Careers loaded.');
    // Auto-dismiss alerts after 5 seconds
    document.querySelectorAll('.alert').forEach(function(alert) {
        setTimeout(function() {
            alert.classList.remove('show');
            setTimeout(function() { alert.remove(); }, 300);
        }, 5000);
    });
});