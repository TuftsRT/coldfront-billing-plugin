const toastDurationMs = 3000;
const costCenterScrollThreshold = 8;
const BILLING_SUCCESS_KEY = 'billing_assignment_success';

document.addEventListener('DOMContentLoaded', function () {

    var maxCostCenters = window.COLDFRONT_MAX_COST_CENTER_ASSIGNMENTS;

    $("#navbar-main > ul > li.active").removeClass("active");
    $("#navbar-project-menu").addClass("active");
    $("#navbar-project").addClass("active");
    $('[data-toggle="popover"]').popover();

    // Show success toast if we just reloaded after a save
    var storedMessage = sessionStorage.getItem(BILLING_SUCCESS_KEY);
    if (storedMessage) {
        sessionStorage.removeItem(BILLING_SUCCESS_KEY);
        showFloatingMessage(storedMessage, toastDurationMs);
    }
    var costCenterBody = $('#cost-center-body');

    // Helper: Calculate Cost for a specific row
    function calculateRowCost(row) {
        var percentage = parseInt(row.find('.percent-input').val()) || 0;
        var totalProjectCostRaw = $('#id_total_project_cost').val();
        var cleanCost = totalProjectCostRaw;
        if (typeof cleanCost === 'string') {
            cleanCost = cleanCost.replace(/[$,\s]/g, '');
        }
        var totalProjectCost = parseFloat(cleanCost) || 0;
        var assignedCost = (totalProjectCost * percentage) / 100;
        row.find('.cost-input').val(assignedCost.toFixed(2));

        // Update totals after calculating row cost
        updateTotals();
    }

    // Helper: Update Total Percent and Total Cost
    function updateTotals() {
        var totalPercent = 0;
        var totalCost = 0;
        var hasDeptWithoutPercent = false;
        var hasDuplicateDepts = false;
        var seenDeptGrantPairs = {};
        var errorRows = [];
        var rowsWithDeptCount = 0;

        $('#cost-center-body tr').each(function () {
            var row = $(this);
            var deptId = (row.find('.dept-autocomplete-input').val() || '').trim();
            var grant = (row.find('.grant-autocomplete-input').val() || '').trim();
            var percentage = parseInt(row.find('.percent-input').val(), 10);
            var cost = parseFloat(row.find('.cost-input').val()) || 0;

            if (deptId && isNaN(percentage)) {
                hasDeptWithoutPercent = true;
            }
            if (deptId) {

                const pairKey = deptId + '||' + grant;

                rowsWithDeptCount++;
                if (!seenDeptGrantPairs[pairKey]) {
                    seenDeptGrantPairs[pairKey] = [];
                }
                seenDeptGrantPairs[pairKey].push(row);
                if (seenDeptGrantPairs[pairKey].length > 1) {
                    hasDuplicateDepts = true;
                }
            }
            totalPercent += isNaN(percentage) ? 0 : percentage;
            totalCost += cost;
        });

        // Collect duplicate rows
        if (hasDuplicateDepts) {
            $.each(seenDeptGrantPairs, function (pairKey, rows) {
                if (rows.length > 1) {
                    errorRows = errorRows.concat(rows);
                }
            });
        }

        // Update the total fields
        $('#total-percent').text(totalPercent + '%');
        $('#total-cost').text('$' + totalCost.toFixed(2));

        updateValidationState(totalPercent, hasDeptWithoutPercent, hasDuplicateDepts, rowsWithDeptCount, errorRows);
        requestAnimationFrame(updateCostCenterTableScroll);
    }

    // Helper: Vertical scrollbar when many assignment rows are shown
    function updateCostCenterTableScroll() {
        var wrap = $('#cost-center-table-scroll-wrap');
        if (!wrap.length) {
            return;
        }
        var $tbodyRows = $('#cost-center-body tr');
        var tbodyRowCount = $tbodyRows.length;
        if (tbodyRowCount > costCenterScrollThreshold) {
            var theadH = wrap.find('thead').outerHeight(true) || 0;
            var rowH = Math.max($tbodyRows.first().outerHeight(true) || 0, 36);
            var maxPx = theadH + rowH * costCenterScrollThreshold;
            wrap.css({
                maxHeight: maxPx + 'px',
                overflowY: 'scroll',
                overflowX: 'auto',
                scrollbarGutter: 'stable'
            });
        } else {
            wrap.css({
                maxHeight: '',
                overflowY: '',
                overflowX: '',
                scrollbarGutter: ''
            });
        }
    }

    // Helper: Disable save button and show error when validation fails
    function updateValidationState(totalPercent, hasDeptWithoutPercent, hasDuplicateDepts, rowsWithDeptCount, errorRows) {
        var saveBtn = $('#save-changes-btn');
        var errorEl = $('#cost-center-validation-error');

        $('#cost-center-body tr').removeClass('table-danger');
        if (errorRows && errorRows.length > 0) {
            errorRows.forEach(function (row) {
                row.addClass('table-danger');
            });
        }

        if (hasDuplicateDepts) {
            saveBtn.prop('disabled', true);
            errorEl.removeClass('d-none').text('Each pair department/grant can only be selected once.');
        } else if (hasDeptWithoutPercent) {
            saveBtn.prop('disabled', true);
            errorEl.removeClass('d-none').text('Please enter percentage for all rows with a selected department.');
        } else if (totalPercent !== 100) {
            saveBtn.prop('disabled', true);
            errorEl.removeClass('d-none').text('Total percentage must equal 100%.');
        } else if (rowsWithDeptCount > maxCostCenters) {
            saveBtn.prop('disabled', true);
            errorEl.removeClass('d-none').text('Maximum ' + maxCostCenters + ' cost centers allowed.');
        } else {
            saveBtn.prop('disabled', false);
            errorEl.addClass('d-none');
        }
    }

    // Helper: Show form-level validation error in modal
    function showFormError(message) {
        var errorEl = $('#cost-center-validation-error');
        errorEl.text(message).removeClass('d-none');
    }

    // Helper: Show floating toast message that auto-dismisses
    function showFloatingMessage(message, durationMs) {
        durationMs = durationMs || toastDurationMs;
        var toast = $('<div class="billing-toast alert alert-success" role="alert">')
            .css({
                position: 'fixed',
                top: '20px',
                right: '20px',
                zIndex: 9999,
                minWidth: '280px',
                boxShadow: '0 4px 12px rgba(0,0,0,0.15)'
            })
            .text(message)
            .hide()
            .appendTo('body')
            .fadeIn(200);

        setTimeout(function () {
            toast.fadeOut(300, function () {
                $(this).remove();
            });
        }, durationMs);
    }

    // Helper: Add a row and optionally fill it with data
    function addRow(data = null) {
        var rowHtml = $('#sample-row').html();
        var newRow = $('<tr>').html(rowHtml);

        // Append to table
        costCenterBody.append(newRow);
        newRow.find('.remove-row-btn').popover({ container: 'body' });

        // If data exists (from JSON), fill the fields
        if (data) {
            newRow.find('.dept-autocomplete-input').val(data.department);
            newRow.find('.grant-autocomplete-input').val(data.grant || '');
            newRow.find('.percent-input').val(data.percentage);
            // Trigger calculation for this row after a brief delay to ensure values are set
            setTimeout(function () {
                calculateRowCost(newRow);
            }, 50);
        } else {
            updateTotals();
        }
    }


    // Handle modal data population
    $('#costCentersModal').on('show.bs.modal', function (event) {
        var button = $(event.relatedTarget); // Button that triggered the modal

        // Extract info from data-* attributes
        var projectId = button.data('project-id');
        var projectName = button.attr('data-project-name');
        var projectCost = button.data('project-cost');
        var rawAssignments = button.data('assignments');
        var assignmentsArray = [];

        if (Array.isArray(rawAssignments) && rawAssignments.length > 0) {
            assignmentsArray = rawAssignments;
        }

        var modal = $(this);
        modal.find('.modal-title').text('Assign costs for project: ' + projectName + ' (' + projectId + ')');
        modal.find('#id_project_id').val(projectId);
        modal.find('#id_total_project_cost').val(projectCost);
        $('#cost-center-validation-error').addClass('d-none');

        // 4. Clear and Fill Table
        costCenterBody.empty();

        if (assignmentsArray.length > 0) {
            assignmentsArray.forEach(function (item) {
                addRow(item);
            });
        } else {
            addRow();
        }

        // Trigger calculation for all existing rows after modal is populated
        setTimeout(function () {
            $('#cost-center-body tr').each(function () {
                calculateRowCost($(this));
            });
            updateTotals();
        }, 100);
    });

    // 2. Add Row Button
    $('#add-row-btn').on('click', function () {
        addRow();
    });

    // 3. Remove Row Button
    costCenterBody.on('click', '.remove-row-btn', function () {
        $(this).closest('tr').remove();
        updateTotals(); // Update totals after removing row
    });

    // 4. Live Calculation and Validation on Input Change
    costCenterBody.on('keypress', '.percent-input', function (e) {
        var key = e.which || e.keyCode;
        if (key !== 8 && (key < 48 || key > 57)) {
            e.preventDefault();
        }
    });
    costCenterBody.on('input blur', '.percent-input', function () {
        var input = $(this);
        var val = input.val().replace(/\D/g, '').slice(0, 3);
        if (val !== input.val()) {
            val = val === '' ? '' : Math.min(100, Math.max(0, parseInt(val, 10)));
            input.val(val);
        }
        var row = input.closest('tr');
        calculateRowCost(row);
    });

    costCenterBody.on('input change', '.dept-autocomplete-input', function () {
        var row = $(this).closest('tr');
        calculateRowCost(row);
    });

    costCenterBody.on('input change', '.grant-autocomplete-input', function () {
        var row = $(this).closest('tr');
        calculateRowCost(row);
    });

    if (typeof window.initColdfrontCostCenterAutocomplete === 'function') {
        var billingAutocompleteUrl = $('#costCentersModal').data('autocomplete-url');
        if (billingAutocompleteUrl) {
            window.initColdfrontCostCenterAutocomplete({
                delegateRoot: costCenterBody,
                autocompleteUrl: billingAutocompleteUrl,
            });
        }
    }

    // 5. Save Changes Button Handler
    $('#save-changes-btn').on('click', function () {
        updateTotals();
        var projectId = $('#id_project_id').val();
        var csrfToken = $('[name=csrfmiddlewaretoken]').val();
        var rows = $('#cost-center-body tr');
        var assignmentsPayload = [];
        var seenDeptGrantPairs = {};
        var totalPercentage = 0;

        // --- VALIDATION & DATA GATHERING ---
        var hasDuplicate = false;
        var hasMissingPercent = false;
        rows.each(function () {
            var deptId = (($(this).find('.dept-autocomplete-input').val()) || '').trim();
            var grantId = (($(this).find('.grant-autocomplete-input').val()) || '').trim();
            var percentage = parseInt($(this).find('.percent-input').val(), 10);

            if (deptId && !isNaN(percentage)) {
                const pairKey = deptId + '||' + grantId;

                if (seenDeptGrantPairs.hasOwnProperty(pairKey)) {
                    hasDuplicate = true;
                } else {
                    seenDeptGrantPairs[pairKey] = true;
                    var payload = {department: deptId, percentage: percentage};
                    if (grantId) {
                        payload.grant = grantId;
                    }
                    assignmentsPayload.push(payload);
                    totalPercentage += percentage;
                }
            } else if (deptId && isNaN(percentage)) {
                hasMissingPercent = true;
            }
        });

        if (hasDuplicate) {
            showFormError('Each department/grant pair can only be selected once.');
            return;
        }
        if (hasMissingPercent) {
            showFormError('Please enter percentage for all rows with a selected department.');
            return;
        }

        if (totalPercentage !== 100) {
            return;
        }

        // Disable save button to prevent double submission
        var saveBtn = $(this);
        saveBtn.prop('disabled', true).text('Saving...');

        // Prepare the URL
        var finalUrl = $('#costCentersModal').data('update-url');


        // --- SINGLE AJAX REQUEST ---
        $.ajax({
            url: finalUrl,
            method: 'POST',
            dataType: 'json',
            data: {
                project_id: projectId,
                assignments: JSON.stringify(assignmentsPayload)
            },
            headers: {'X-CSRFToken': csrfToken}, // Django-friendly
        })
            .done((response) => {
                var message = response?.message ?? 'Cost center assignment updated successfully.';
                sessionStorage.setItem(BILLING_SUCCESS_KEY, message);
                $('#costCentersModal').modal('hide');
                location.reload();
            })
            .fail((xhr) => {
                const resp = xhr.responseJSON ?? safeJsonParse(xhr.responseText);

                const errorMsg = extractDjangoErrors(resp) || resp?.error || 'Error saving assignments. Please try again.';

                showFormError(errorMsg);
            })
            .always(() => {
                saveBtn.prop('disabled', false).text('Save changes');
            });

        function safeJsonParse(text) {
            try {
                return JSON.parse(text);
            } catch {
                return null;
            }
        }

        function extractDjangoErrors(resp) {
            const errs = resp?.errors;
            if (!errs) return '';

            const messages = [];
            Object.values(errs).forEach((msgs) => {
                if (Array.isArray(msgs)) messages.push(...msgs); else if (msgs) messages.push(msgs);
            });
            return messages.filter(Boolean).join(' ');
        }
    });
});
