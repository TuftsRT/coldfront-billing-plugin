const toastDurationMs = 3000;
const maxCostCenters = 4;
const BILLING_SUCCESS_KEY = 'billing_assignment_success';
const DEBOUNCE_TIME_MS = 250;

document.addEventListener('DOMContentLoaded', function () {

    $("#navbar-main > ul > li.active").removeClass("active");
    $("#navbar-project-menu").addClass("active");
    $("#navbar-project").addClass("active");

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
        var seenDepts = {};
        var errorRows = [];
        var rowsWithDeptCount = 0;

        $('#cost-center-body tr').each(function () {
            var row = $(this);
            var deptId = (row.find('.dept-autocomplete-input').val() || '').trim();
            var percentage = parseInt(row.find('.percent-input').val(), 10);
            var cost = parseFloat(row.find('.cost-input').val()) || 0;

            if (deptId && isNaN(percentage)) {
                hasDeptWithoutPercent = true;
            }
            if (deptId) {
                rowsWithDeptCount++;
                if (!seenDepts[deptId]) {
                    seenDepts[deptId] = [];
                }
                seenDepts[deptId].push(row);
                if (seenDepts[deptId].length > 1) {
                    hasDuplicateDepts = true;
                }
            }
            totalPercent += isNaN(percentage) ? 0 : percentage;
            totalCost += cost;
        });

        // Collect duplicate rows
        if (hasDuplicateDepts) {
            $.each(seenDepts, function (deptId, rows) {
                if (rows.length > 1) {
                    errorRows = errorRows.concat(rows);
                }
            });
        }

        // Update the total fields
        $('#total-percent').text(totalPercent + '%');
        $('#total-cost').text('$' + totalCost.toFixed(2));

        updateValidationState(totalPercent, hasDeptWithoutPercent, hasDuplicateDepts, rowsWithDeptCount, errorRows);
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
            errorEl.removeClass('d-none').text('Each department can only be selected once.');
        } else if (hasDeptWithoutPercent) {
            saveBtn.prop('disabled', true);
            errorEl.removeClass('d-none').text('Please enter percentage for all rows with a selected department.');
        } else if (totalPercent !== 100) {
            saveBtn.prop('disabled', true);
            errorEl.removeClass('d-none').text('Total percentage must equal 100%.');
        } else if (rowsWithDeptCount > maxCostCenters) {
            saveBtn.prop('disabled', true);
            errorEl.removeClass('d-none').text('Maximum 4 cost centers allowed.');
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
        modal.find('.modal-title').text('Assign IDs to Project: ' + projectName + ' (' + projectId + ')');
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

    // Cost center autocomplete (CostCenterAutocompleteView: GET ?q= & type=, min 3 chars, { results: string[] })
    (function initCostCenterAutocomplete() {
        var autocompleteUrl = $('#costCentersModal').data('autocomplete-url');
        if (!autocompleteUrl) {
            return;
        }

        var AC_HIGHLIGHT_CLASS = 'active';

        function hideResults(list, input) {
            list.addClass('d-none').empty();
            if (input && input.length) {
                input.removeData('ac-highlight-idx');
            }
        }

        function clearResultHighlight(list) {
            list.find('li').removeClass(AC_HIGHLIGHT_CLASS);
        }

        function setResultHighlight(input, list, index) {
            var items = list.find('li');
            clearResultHighlight(list);
            input.data('ac-highlight-idx', index);
            if (index >= 0 && index < items.length) {
                var el = items.eq(index);
                el.addClass(AC_HIGHLIGHT_CLASS);
                var dom = el.get(0);
                if (dom && dom.scrollIntoView) {
                    dom.scrollIntoView({ block: 'nearest' });
                }
            }
        }

        function applyAutocompleteChoice(input, list, li, triggerChangeOnSelect) {
            input.val(li.text().trim());
            hideResults(list, input);
            if (triggerChangeOnSelect) {
                input.trigger('change');
            }
        }

        function resultsListForInput(input, resultsSelector) {
            return input.closest('.autocomplete-wrapper').find(resultsSelector);
        }

        function bumpSeq(input) {
            var n = (input.data('ac-seq') || 0) + 1;
            input.data('ac-seq', n);
            return n;
        }

        function abortPending(input) {
            var xhr = input.data('ac-xhr');
            if (xhr && typeof xhr.abort === 'function') {
                xhr.abort();
            }
        }

        function bindAutocomplete(config) {
            var inputSel = config.inputSelector;
            var resultsSel = config.resultsSelector;
            var typeParam = config.typeParam;
            var triggerChangeOnSelect = !!config.triggerChangeOnSelect;

            costCenterBody.on('input', inputSel, function () {
                var input = $(this);
                var list = resultsListForInput(input, resultsSel);
                clearTimeout(input.data('ac-debounce'));

                var q = input.val().trim();
                if (q.length < 3) {
                    abortPending(input);
                    hideResults(list, input);
                    return;
                }

                input.data('ac-debounce', setTimeout(function () {
                    var seq = bumpSeq(input);
                    abortPending(input);

                    var xhr = $.getJSON(autocompleteUrl, {q: q, type: typeParam})
                        .done(function (data) {
                            if (input.data('ac-seq') !== seq) {
                                return;
                            }
                            list.empty();
                            var results = data.results || [];
                            results.forEach(function (name) {
                                $('<li>')
                                    .addClass('list-group-item list-group-item-action py-1 px-2 text-left')
                                    .attr('role', 'option')
                                    .text(name)
                                    .appendTo(list);
                            });
                            input.data('ac-highlight-idx', -1);
                            if (results.length) {
                                list.removeClass('d-none');
                            } else {
                                hideResults(list, input);
                            }
                        })
                        .fail(function (jqXHR, textStatus) {
                            if (textStatus === 'abort') {
                                return;
                            }
                            if (input.data('ac-seq') === seq) {
                                hideResults(list, input);
                            }
                        });
                    input.data('ac-xhr', xhr);
                }, DEBOUNCE_TIME_MS));
            });

            costCenterBody.on('mousedown', resultsSel + ' li', function (e) {
                e.preventDefault();
                var li = $(this);
                var list = li.parent();
                var input = list.closest('.autocomplete-wrapper').find(inputSel);
                applyAutocompleteChoice(input, list, li, triggerChangeOnSelect);
            });

            costCenterBody.on('blur', inputSel, function () {
                var input = $(this);
                var list = resultsListForInput(input, resultsSel);
                setTimeout(function () {
                    hideResults(list, input);
                }, 200);
            });

            costCenterBody.on('keydown', inputSel, function (e) {
                var input = $(this);
                var list = resultsListForInput(input, resultsSel);
                var items = list.find('li');
                var open = !list.hasClass('d-none') && items.length > 0;

                if (e.key === 'Escape') {
                    if (open) {
                        e.preventDefault();
                        hideResults(list, input);
                    }
                    return;
                }

                if (!open) {
                    return;
                }

                var idx = input.data('ac-highlight-idx');
                if (typeof idx !== 'number' || idx < -1) {
                    idx = -1;
                }

                if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    idx = idx < 0 ? 0 : Math.min(idx + 1, items.length - 1);
                    setResultHighlight(input, list, idx);
                    return;
                }

                if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    idx = idx <= 0 ? -1 : idx - 1;
                    setResultHighlight(input, list, idx);
                    return;
                }

                if (e.key === 'Enter') {
                    if (idx >= 0 && idx < items.length) {
                        e.preventDefault();
                        applyAutocompleteChoice(input, list, items.eq(idx), triggerChangeOnSelect);
                    }
                }
            });
        }

        bindAutocomplete({
            inputSelector: '.dept-autocomplete-input',
            resultsSelector: '.dept-autocomplete-results',
            typeParam: 'department',
            triggerChangeOnSelect: true
        });
        bindAutocomplete({
            inputSelector: '.grant-autocomplete-input',
            resultsSelector: '.grant-autocomplete-results',
            typeParam: 'grant',
            triggerChangeOnSelect: false
        });
    })();

    // 5. Save Changes Button Handler
    $('#save-changes-btn').on('click', function () {
        updateTotals();
        var projectId = $('#id_project_id').val();
        var csrfToken = $('[name=csrfmiddlewaretoken]').val();
        var rows = $('#cost-center-body tr');
        var assignmentsPayload = [];
        var seenDepts = {};
        var totalPercentage = 0;

        // --- VALIDATION & DATA GATHERING ---
        var hasDuplicate = false;
        var hasMissingPercent = false;
        rows.each(function () {
            var deptId = (($(this).find('.dept-autocomplete-input').val()) || '').trim();
            var grantId = (($(this).find('.grant-autocomplete-input').val()) || '').trim();
            var percentage = parseInt($(this).find('.percent-input').val(), 10);

            if (deptId && !isNaN(percentage)) {
                if (seenDepts.hasOwnProperty(deptId)) {
                    hasDuplicate = true;
                } else {
                    seenDepts[deptId] = true;
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
            showFormError('Each department can only be selected once.');
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
