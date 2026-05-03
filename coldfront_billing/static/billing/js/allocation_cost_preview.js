(function () {
    'use strict';

    function showModal(modalEl) {
        if (typeof jQuery !== 'undefined' && jQuery.fn.modal) {
            jQuery(modalEl).modal('show');
        } else if (window.bootstrap && window.bootstrap.Modal) {
            window.bootstrap.Modal.getOrCreateInstance(modalEl).show();
        }
    }

    function hideModal(modalEl) {
        if (typeof jQuery !== 'undefined' && jQuery.fn.modal) {
            jQuery(modalEl).modal('hide');
        } else if (window.bootstrap && window.bootstrap.Modal) {
            var inst = window.bootstrap.Modal.getInstance(modalEl);
            if (inst) {
                inst.hide();
            }
        }
    }

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

        form.addEventListener('submit', function (e) {
            if (skipPreview) {
                skipPreview = false;
                return;
            }
            e.preventDefault();

            if (typeof form.checkValidity === 'function' && !form.checkValidity()) {
                form.reportValidity();
                return;
            }

            var quotaStr = (quotaInput.value || '').trim();
            if (quotaStr === '') {
                quotaInput.setCustomValidity('Please enter a storage quota.');
                quotaInput.reportValidity();
                quotaInput.setCustomValidity('');
                return;
            }
            var quotaVal = parseFloat(quotaStr.replace(',', '.'));
            if (isNaN(quotaVal) || quotaVal < 0) {
                quotaInput.setCustomValidity('Enter a valid non-negative storage quota.');
                quotaInput.reportValidity();
                quotaInput.setCustomValidity('');
                return;
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
                        yesBtn.textContent = 'Proceed';
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
                            'Cost per TB: <strong>' +
                            perTb +
                            '$</strong><br>' +
                            'Estimated total cost: <strong>' +
                            total +
                            '$</strong><br><br>' +
                            'You have possibility to apply <strong>' +
                            applied +
                            ' TB</strong> of no-cost quota<br>Estimated cost would change to <strong>' +
                            reduced +
                            '$</strong>';
                    } else {
                        summaryEl.innerHTML =
                            'Storage quota: <strong>' +
                            quotaVal +
                            ' TB</strong><br>' +
                            'Cost per TB: <strong>' +
                            perTb +
                            '$</strong><br>' +
                            'Estimated total cost: <strong>' +
                            total +
                            '$</strong>';
                    }
                    showModal(modalEl);
                })
                .catch(function (err) {
                    lastPreviewHadQuotaId = false;
                    lastQuotaId = null;
                    noBtn.classList.add('d-none');
                    applyPromptEl.textContent = '';
                    yesBtn.textContent = 'Proceed';
                    summaryEl.textContent =
                        'Could not load cost preview: ' + (err && err.message ? err.message : 'unknown error');
                    showModal(modalEl);
                });
        });

        function submitWithApply(apply) {
            applyHidden.value =
                apply && lastPreviewHadQuotaId && lastQuotaId != null ? String(lastQuotaId) : '';
            hideModal(modalEl);
            skipPreview = true;
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
