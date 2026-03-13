document.addEventListener('DOMContentLoaded', function() {
    var form = document.getElementById('assignQuotaForm');
    var allocationIdInput = document.getElementById('assignQuotaAllocationId');
    var allocationDisplayEl = document.getElementById('assignQuotaModalAllocation');
    var limitsDisplayEl = document.getElementById('assignQuotaModalLimits');
    var amountInput = document.getElementById('assignQuotaAmount');
    var units = form ? form.getAttribute('data-units') || 'TB' : 'TB';

    document.querySelectorAll('[data-target="#assignQuotaModal"], [data-bs-target="#assignQuotaModal"]').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var allocationId = this.getAttribute('data-allocation-id');
            var allocationDisplay = this.getAttribute('data-allocation-display');
            var existingAmount = (this.getAttribute('data-existing-amount') || '').replace(',', '.');
            var maxAmount = this.getAttribute('data-max-amount');
            var increment = this.getAttribute('data-increment');
            allocationIdInput.value = allocationId || '';
            allocationDisplayEl.textContent = allocationDisplay || '';
            amountInput.value = existingAmount;
            amountInput.max = maxAmount || '';
            if (limitsDisplayEl && maxAmount != null && increment != null) {
                limitsDisplayEl.textContent = 'Max: ' + maxAmount + ' ' + units + ', Increment: ' + increment + ' ' + units;
            } else if (limitsDisplayEl) {
                limitsDisplayEl.textContent = '';
            }
        });
    });

    if (form) {
        form.addEventListener('submit', function(e) {
            if (!allocationIdInput.value) {
                e.preventDefault();
                alert('Please select an allocation first.');
                return false;
            }
        });
    }
});
