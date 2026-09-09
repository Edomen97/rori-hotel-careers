/* ============================================
   MULTI-STEP WIZARD ENGINE
   Rori Hotel Careers Application Portal
   ============================================ */

let currentStep = 1;
const totalSteps = 5;

function changeStep(direction) {
    const targetStep = currentStep + direction;

    // Guard Clause: Prevent out-of-bounds navigation
    if (targetStep < 1 || targetStep > totalSteps) return;

    const currentFormStep = document.getElementById(`wizard-step-${currentStep}`);

    // Validate current step fields before advancing forward
    if (direction === 1 && currentFormStep) {
        const inputs = Array.from(
            currentFormStep.querySelectorAll('input[required], select[required], textarea[required]')
        );

        // Find first invalid input and trigger native HTML5 validation UI
        const firstInvalid = inputs.find(input => !input.checkValidity());
        if (firstInvalid) {
            firstInvalid.reportValidity();
            return; // Block step transition
        }
    }

    // Update UI for current step
    if (currentFormStep) {
        currentFormStep.classList.remove('active');
    }

    const currentIndicator = document.getElementById(`p-step-${currentStep}`);
    if (currentIndicator) {
        currentIndicator.classList.remove('active');
        if (direction === 1) {
            currentIndicator.classList.add('completed');
        }
    }

    // Advance step pointer
    currentStep = targetStep;

    // Update UI for target step
    const targetFormStep = document.getElementById(`wizard-step-${currentStep}`);
    const targetIndicator = document.getElementById(`p-step-${currentStep}`);

    if (targetFormStep) {
        targetFormStep.classList.add('active');
    }

    if (targetIndicator) {
        targetIndicator.classList.add('active');
        // Remove completed status when navigating backwards
        if (direction === -1) {
            targetIndicator.classList.remove('completed');
        }
    }

    // Toggle navigation button visibility & state
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const submitBtn = document.getElementById('submitBtn');

    if (prevBtn) {
        prevBtn.disabled = (currentStep === 1);
    }

    if (currentStep === totalSteps) {
        if (nextBtn) nextBtn.classList.add('d-none');
        if (submitBtn) submitBtn.classList.remove('d-none');
    } else {
        if (nextBtn) nextBtn.classList.remove('d-none');
        if (submitBtn) submitBtn.classList.add('d-none');
    }

    // Dynamic Progress Bar Width Update
    const progressBar = document.getElementById('wizardProgressBar');
    if (progressBar) {
        const progressPercentage = ((currentStep - 1) / (totalSteps - 1)) * 100;
        progressBar.style.width = `${progressPercentage}%`;
        progressBar.setAttribute('aria-valuenow', progressPercentage);
    }

    // Smooth scroll back to form header on step change
    const wizardHeader = document.querySelector('.wizard-container') || currentFormStep?.closest('form');
    if (wizardHeader) {
        wizardHeader.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}
