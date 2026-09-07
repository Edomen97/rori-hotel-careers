let currentStep = 1;
const totalSteps = 5;

function changeStep(direction) {
    const currentFormStep = document.getElementById(`wizard-step-${currentStep}`);
    if (direction === 1) {
        const inputs = currentFormStep.querySelectorAll('input[required], select[required], textarea[required]');
        let isValid = true;
        inputs.forEach(function(input) {
            if (!input.checkValidity()) {
                input.reportValidity();
                isValid = false;
                return false;
            }
        });
        if (!isValid) return;
    }
    currentFormStep.classList.remove('active');
    document.getElementById(`p-step-${currentStep}`).classList.remove('active');
    if (direction === 1) {
        document.getElementById(`p-step-${currentStep}`).classList.add('completed');
    }
    currentStep += direction;
    document.getElementById(`wizard-step-${currentStep}`).classList.add('active');
    document.getElementById(`p-step-${currentStep}`).classList.add('active');
    document.getElementById('prevBtn').disabled = (currentStep === 1);
    if (currentStep === totalSteps) {
        document.getElementById('nextBtn').classList.add('d-none');
        document.getElementById('submitBtn').classList.remove('d-none');
    } else {
        document.getElementById('nextBtn').classList.remove('d-none');
        document.getElementById('submitBtn').classList.add('d-none');
    }
}