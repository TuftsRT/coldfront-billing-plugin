(function () {
    'use strict';

    function init() {
        var form = document.getElementById('allocation-details-form');
        if (!form || !form.dataset.costPreviewUrl) {
            return;
        }

        var modalEl = document.getElementById('allocationCostConfirmModal');
        var summaryEl = document.getElementById('allocation-cost-modal-summary');
        var applyPromptEl = document.getElementById('allocation-cost-modal-apply-prompt');
        var noBtn = document.getElementById('allocation-cost-confirm-no');
        var yesBtn = document.getElementById('allocation-cost-confirm-yes');
        var quotaInput = document.getElementById('id_quota_in_terabyte');
        var applyHidden = document.getElementById('id_apply_allocation_quota');
        if (!modalEl || !summaryEl || !applyPromptEl || !noBtn || !yesBtn || !quotaInput || !applyHidden) {
            return;
        }

        var skipPreview = false;
        var lastPreviewHadQuotaId = false;
        var lastQuotaId = null;

        // "Complete Request" opens the modal through Bootstrap's data API (data-bs-toggle="modal"),
        // because ColdFront doesn't expose Bootstrap's API to open it from script. Its click opens
        // the modal before the form's submit event fires, so this checks the form and cancels the
        // opening if it's invalid.
        var previewRequest = 0;

        form.addEventListener('submit', function (e) {
            if (e.submitter && e.submitter.id === 'cancel-btn') {
                return;
            }
            if (skipPreview) {
                skipPreview = false;
                return;
            }
            e.preventDefault(); // the modal asks first; its buttons submit the form
        });

        modalEl.addEventListener('show.bs.modal', function (e) {
            if (typeof form.checkValidity === 'function' && !form.checkValidity()) {
                e.preventDefault();
                form.reportValidity();
                return;
            }

            var quotaStr = (quotaInput.value || '').trim();
            if (quotaStr === '') {
                e.preventDefault();
                quotaInput.setCustomValidity('Please enter a storage quota.');
                quotaInput.reportValidity();
                quotaInput.setCustomValidity('');
                return;
            }
            var quotaVal = parseFloat(quotaStr.replace(',', '.'));
            if (isNaN(quotaVal) || quotaVal < 0) {
                e.preventDefault();
                quotaInput.setCustomValidity('Enter a valid non-negative storage quota.');
                quotaInput.reportValidity();
                quotaInput.setCustomValidity('');
                return;
            }

            var request = ++previewRequest;
            lastPreviewHadQuotaId = false;
            lastQuotaId = null;
            noBtn.classList.add('d-none');
            applyPromptEl.textContent = '';
            yesBtn.textContent = 'Confirm';
            summaryEl.textContent = 'Loading cost preview…';
            noBtn.disabled = true;
            yesBtn.disabled = true;

            function formatCurrency(value) {
                const decimals = 2;
                const parsed = parseFloat(value);
            
                // Check if the parsing failed (yields NaN)
                if (isNaN(parsed)) {
                    return `$${(0).toFixed(decimals)}`;
                }
                
                if (parsed < 0) {
                    return `-$${Math.abs(parsed).toFixed(decimals)}`;
                } else {
                    return `$${parsed.toFixed(decimals)}`;
                }
            }

            var base = form.dataset.costPreviewUrl;
            var sep = base.indexOf('?') >= 0 ? '&' : '?';
            var url = base + sep + 'quota_in_terabyte=' + encodeURIComponent(quotaStr);

            fetch(url, {
                method: 'GET',
                headers: {Accept: 'application/json'},
                credentials: 'same-origin',
            })
                .then(function (r) {
                    return r.json().then(function (body) {
                        if (!r.ok) {
                            throw new Error((body && body.error) || r.statusText);
                        }
                        return body;
                    });
                })
                .then(function (data) {
                    if (request !== previewRequest) {
                        return;
                    }
                    var total = data.total_cost;
                    var perTb = data.cost_per_tb;
                    var reduced = data.reduced_cost;
                    var applied = data.applied_quota;
                    var hasQuotaChoice = data.quota_id != null;
                    lastQuotaId = hasQuotaChoice ? data.quota_id : null;
                    lastPreviewHadQuotaId = hasQuotaChoice;
                    if (hasQuotaChoice) {
                        noBtn.classList.remove('d-none');
                        applyPromptEl.textContent = 'Would you like to apply the quota?';
                        yesBtn.textContent = 'Yes';
                    } else {
                        noBtn.classList.add('d-none');
                        applyPromptEl.textContent = '';
                        yesBtn.textContent = 'Confirm';
                    }
                    if (typeof applied === 'number' && applied > 0 && reduced !== undefined) {
                        var appliedStr =
                            applied % 1 === 0
                                ? String(applied)
                                : applied.toFixed(2).replace(/\.?0+$/, '');
                        summaryEl.innerHTML =
                            'Storage quota: <strong>' +
                            quotaVal +
                            ' TB</strong><br>' +
                            'Monthly Cost per TB: <strong>' +
                            formatCurrency(perTb) +
                            '</strong><br>' +
                            'Estimated total cost: <strong>' +
                            formatCurrency(total) +
                            '</strong><br><br>' +
                            'You may apply <strong>' +
                            applied +
                            ' TB</strong> of no-cost quota, <br>reducing estimated cost to <strong>' +
                            formatCurrency(reduced) +
                            ' monthly.</strong>';
                    } else {
                        summaryEl.innerHTML =
                            'Storage quota: <strong>' +
                            quotaVal +
                            ' TB</strong><br>' +
                            'Monthly Cost per TB: <strong>' +
                            formatCurrency(perTb) +
                            '</strong><br>' +
                            'Estimated total cost: <strong>' +
                            formatCurrency(total) +
                            '</strong>';
                    }
                })
                .catch(function (err) {
                    if (request !== previewRequest) {
                        return;
                    }
                    lastPreviewHadQuotaId = false;
                    lastQuotaId = null;
                    noBtn.classList.add('d-none');
                    applyPromptEl.textContent = '';
                    yesBtn.textContent = 'Confirm';
                    summaryEl.textContent =
                        'Could not load cost preview: ' + (err && err.message ? err.message : 'unknown error');
                })
                .finally(function () {
                    if (request === previewRequest) {
                        noBtn.disabled = false;
                        yesBtn.disabled = false;
                    }
                });
        });

        function submitWithApply(apply) {
            applyHidden.value =
                apply && lastPreviewHadQuotaId && lastQuotaId != null ? String(lastQuotaId) : '';
            skipPreview = true; // the submit leaves the page, so the modal needn't be closed
            if (typeof form.requestSubmit === 'function') {
                form.requestSubmit();
            } else {
                form.submit();
            }
        }

        noBtn.addEventListener('click', function () {
            submitWithApply(false);
        });

        yesBtn.addEventListener('click', function () {
            submitWithApply(lastPreviewHadQuotaId);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
