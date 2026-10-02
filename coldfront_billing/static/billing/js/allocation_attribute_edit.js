document.addEventListener('DOMContentLoaded', function () {
  $(document).ready(function () {
    const form = $('.js-allocation-quota-confirm-form').first();
    if (!form.length) {
      return;
    }
    const quotaAttributeNameFromConfig = String(form.data('quota-attribute-name') || '');
    const costPreviewUrl = String(form.data('cost-preview-url') || '');
    const applyHidden = $('#id_apply_allocation_quota');
    const noButton = $('#quota-change-confirm-no');
    const confirmButton = $('#quota-change-confirm-button');
    const applyPrompt = $('#quota-change-modal-apply-prompt');
    const summaryEl = $('#quota-change-modal-summary');
    const metas = $('.js-allocation-attribute-meta');

    let quotaInput = null;
    let quotaOriginalValue = null;
    let quotaChangeConfirmed = false;
    let lastPreviewHasQuotaChoice = false;
    let lastPreviewQuotaId = null;

    function parseQuotaValue(value) {
      const normalized = String(value || '').trim().replace(',', '.');
      if (normalized === '') {
        return null;
      }
      const parsed = Number(normalized);
      if (Number.isNaN(parsed)) {
        return null;
      }
      return parsed;
    }

    function formatCurrency(value) {
        if (!Number.isFinite(value)) {
          return String(value);
        }
        
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

    function formatSignedNumber(value) {
      if (!Number.isFinite(value)) {
        return String(value);
      }
      const abs = Math.abs(value);
      const normalized = abs % 1 === 0 ? String(abs) : abs.toFixed(2).replace(/\.?0+$/, '');
      return (value >= 0 ? '+' : '-') + normalized;
    }

    function getCostPreview(quotaDiffValue) {
      const separator = costPreviewUrl.indexOf('?') >= 0 ? '&' : '?';
      const url = costPreviewUrl + separator + 'quota_in_terabyte=' + encodeURIComponent(String(quotaDiffValue));
      return fetch(url, {
        method: 'GET',
        headers: { Accept: 'application/json' },
        credentials: 'same-origin',
      }).then(function (response) {
        return response.json().then(function (body) {
          if (!response.ok) {
            throw new Error((body && body.error) || response.statusText);
          }
          return body;
        });
      });
    }

    metas.each(function () {
      const meta = $(this);
      const inputId = meta.data('input-id');
      const attributeName = String(meta.data('attribute-name') || '');
      const originalValue = String(meta.data('original-value') || '');
      const changeIndicatorId = String(meta.data('change-indicator-id') || '');
      const input = $('#' + inputId);
      const changeIndicator = $('#' + changeIndicatorId);

      if (input.length === 0) {
        return;
      }

      if (quotaAttributeNameFromConfig && attributeName === quotaAttributeNameFromConfig) {
        quotaInput = input;
        quotaOriginalValue = originalValue;
      }

      input.on('input', function () {
        if ($(this).val() != originalValue) {
          changeIndicator.removeClass('d-none');
        } else {
          changeIndicator.addClass('d-none');
        }
      });
      input.trigger('input');
    });

    const modalEl = document.getElementById('quota-change-confirmation-modal');
    const modalButtons = noButton.add(confirmButton);
    let previewRequest = 0;

    function needsConfirmation() {
      return Boolean(quotaInput) && !quotaChangeConfirmed && quotaInput.val() != quotaOriginalValue;
    }

    // The submit button opens this modal through Bootstrap's data API (data-bs-toggle="modal"),
    // because ColdFront doesn't expose Bootstrap's API to open it from script. The click opens
    // the modal before the form's submit event fires, so this decides whether it opens at all.
    modalEl.addEventListener('show.bs.modal', function (event) {
      if (!needsConfirmation()) {
        event.preventDefault(); // nothing to confirm: the form submits normally
        return;
      }
      if (!form[0].checkValidity()) {
        event.preventDefault();
        form[0].reportValidity();
        return;
      }

      const request = ++previewRequest;
      summaryEl.text('');
      applyPrompt.text('');
      noButton.addClass('d-none');
      confirmButton.text('Confirm');
      lastPreviewHasQuotaChoice = false;
      lastPreviewQuotaId = null;
      applyHidden.val('');

      const currentQuota = parseQuotaValue(quotaOriginalValue);
      const newQuota = parseQuotaValue(quotaInput.val());
      const quotaDiff = currentQuota !== null && newQuota !== null ? newQuota - currentQuota : null;

      if (!costPreviewUrl || quotaDiff === null || quotaDiff === 0) {
        summaryEl.text('Please confirm this storage modification to continue.');
        return;
      }

      summaryEl.text('Loading cost preview…');
      modalButtons.prop('disabled', true);

      const absDiff = Math.abs(quotaDiff);
      const requestedChangeLabel =
        quotaDiff >= 0
          ? 'Requested increase: <strong>+ ' + absDiff + ' TB</strong>'
          : 'Requested decrease: <strong>- ' + absDiff + ' TB</strong>';
      getCostPreview(absDiff)
        .then(function (data) {
          if (request !== previewRequest) {
            return;
          }
          const totalCost = Number(data.total_cost || 0);
          const signedCostDiff = quotaDiff >= 0 ? totalCost : -totalCost;
          const costPerTb = Number(data.cost_per_tb || 0);
          const hasQuotaChoice = data.quota_id != null;
          const reducedCost = Number(data.reduced_cost || 0);
          const appliedQuota = Number(data.applied_quota || 0);

          if (quotaDiff < 0) {
            const quotaCost = Number(data.quota_cost || 0);
            lastPreviewHasQuotaChoice = false;
            lastPreviewQuotaId = null;
            noButton.addClass('d-none');
            applyPrompt.text('');
            confirmButton.text('Confirm');
            summaryEl.html(
              requestedChangeLabel +
                '<br>' +
                'Final storage quota: <strong>' +
                newQuota +
                ' TB</strong><br>' +
                'Monthly Cost per TB: <strong>' +
                formatCurrency(costPerTb) +
                '</strong><br>' +
                'Estimated cost change: <strong>' +
                formatCurrency(-quotaCost) +
                ' monthly.</strong>'
            );
            return;
          }

          lastPreviewHasQuotaChoice = hasQuotaChoice;
          lastPreviewQuotaId = hasQuotaChoice ? String(data.quota_id) : null;
          if (hasQuotaChoice) {
            noButton.removeClass('d-none');
            applyPrompt.text('Would you like to apply the quota?');
            confirmButton.text('Yes');
          } else {
            noButton.addClass('d-none');
            applyPrompt.text('');
            confirmButton.text('Confirm');
          }

          if (hasQuotaChoice && appliedQuota > 0) {
            summaryEl.html(
              requestedChangeLabel +
                '<br>' +
                'Final storage quota: <strong>' +
                newQuota +
                ' TB</strong><br>' +
                'Monthly Cost per TB: <strong>' +
                formatCurrency(costPerTb) +
                '</strong><br>' +
                'Estimated total cost: <strong>' +
                formatCurrency(signedCostDiff) +
                '</strong><br><br>' +
                'You may apply <strong>' +
                appliedQuota +
                ' TB</strong> of no-cost quota<br>Estimated cost would change to <strong>' +
                formatCurrency(reducedCost) +
                ' monthly.</strong>'
            );
          } else {
            summaryEl.html(
              requestedChangeLabel +
                '<br>' +
                'Final storage quota: <strong>' +
                newQuota +
                ' TB</strong><br>' +
                'Monthly Cost per TB: <strong>' +
                formatCurrency(costPerTb) +
                '</strong><br>' +
                'Estimated total cost: <strong>' +
                formatCurrency(signedCostDiff) +
                ' monthly.</strong>'
            );
          }
        })
        .catch(function (err) {
          if (request !== previewRequest) {
            return;
          }
          summaryEl.text('Could not load cost preview: ' + (err && err.message ? err.message : 'unknown error'));
        })
        .finally(function () {
          if (request === previewRequest) {
            modalButtons.prop('disabled', false);
          }
        });
    });

    form.on('submit', function (event) {
      if (needsConfirmation()) {
        event.preventDefault(); // the modal asks first; its buttons submit the form
      }
    });

    function submitWithApply(applyQuota) {
      if (applyQuota && lastPreviewHasQuotaChoice && lastPreviewQuotaId !== null) {
        applyHidden.val(lastPreviewQuotaId);
      } else {
        applyHidden.val('');
      }
      quotaChangeConfirmed = true;
      form[0].submit(); // leaves the page, so the modal needn't be closed
    }

    noButton.on('click', function () {
      submitWithApply(false);
    });

    confirmButton.on('click', function () {
      submitWithApply(lastPreviewHasQuotaChoice);
    });
  });
});
