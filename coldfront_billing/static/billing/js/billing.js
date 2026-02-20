document.addEventListener('DOMContentLoaded', function() {

    $("#navbar-main > ul > li.active").removeClass("active");
    $("#navbar-project-menu").addClass("active");
    $("#navbar-project").addClass("active");

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

        $('#cost-center-body tr').each(function() {
            var percentage = parseInt($(this).find('.percent-input').val()) || 0;
            var cost = parseFloat($(this).find('.cost-input').val()) || 0;

            totalPercent += percentage;
            totalCost += cost;
        });

        // Update the total fields
        $('#total-percent').text(totalPercent + '%');
        $('#total-cost').text('$' + totalCost.toFixed(2));
    }

    // Helper: Add a row and optionally fill it with data
    function addRow(data = null) {
        var rowHtml = $('#sample-row').html();
        var newRow = $('<tr>').html(rowHtml);

        // Append to table
        $('#cost-center-body').append(newRow);

        // If data exists (from JSON), fill the fields
        if (data) {
            newRow.find('.dept-select').val(data.dept_id);
            newRow.find('.percent-input').val(data.percentage);
            // Trigger calculation for this row after a brief delay to ensure values are set
            setTimeout(function() {
                calculateRowCost(newRow);
            }, 50);
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

      if (rawAssignments) {
      // If it's already an object (jQuery parsed it automatically)
      if (typeof rawAssignments === 'object' && !Array.isArray(rawAssignments)) {
          // CONVERT MAP TO ARRAY: {"105": 50} -> [{dept_id: "105", percentage: 50}]
          Object.keys(rawAssignments).forEach(function(key) {
              assignmentsArray.push({
                  dept_id: key,
                  percentage: rawAssignments[key]
              });
          });
      }
      // If it's already an array (rare case based on your code)
      else if (Array.isArray(rawAssignments)) {
          assignmentsArray = rawAssignments;
      }
  }

      var modal = $(this);
      modal.find('.modal-title').text('Assign IDs to Project: ' + projectName + ' ('+projectId+')');
      modal.find('#id_project_id').val(projectId);
      modal.find('#id_total_project_cost').val(projectCost);

      // 4. Clear and Fill Table
      $('#cost-center-body').empty();

      if (assignmentsArray.length > 0) {
          assignmentsArray.forEach(function(item) {
              addRow(item);
          });
      } else {
          addRow();
      }

      // Trigger calculation for all existing rows after modal is populated
      setTimeout(function() {
          $('#cost-center-body tr').each(function() {
              calculateRowCost($(this));
          });
      }, 100);
  });

    // 2. Add Row Button
    $('#add-row-btn').on('click', function() {
        addRow();
    });

    // 3. Remove Row Button
    $('#cost-center-body').on('click', '.remove-row-btn', function() {
        $(this).closest('tr').remove();
        updateTotals(); // Update totals after removing row
    });

    // 4. Live Calculation on Input Change
    $('#cost-center-body').on('input', '.percent-input', function() {
        var row = $(this).closest('tr');
        calculateRowCost(row);
    });

    // 5. Save Changes Button Handler
    $('#save-changes-btn').on('click', function() {
        var projectId = $('#id_project_id').val();
        var csrfToken = $('[name=csrfmiddlewaretoken]').val();
        var rows = $('#cost-center-body tr');
        var errors = [];
        var assignmentsMap = {}; // Object to store our "Dept : Percent" map
        var totalPercentage = 0;

        // --- VALIDATION & DATA GATHERING ---
        rows.each(function() {
            var deptId = $(this).find('.dept-select').val();
            // Parse as Integer (10, not 10.00)
            var percentage = parseInt($(this).find('.percent-input').val());

            if (deptId && !isNaN(percentage)) {
                // Add to our map: { "COST_CENTER_1": 50, "COST_CENTER_2": 50 }
                assignmentsMap[deptId] = percentage;
                totalPercentage += percentage;
            } else if (deptId || !isNaN(percentage)) {
                errors.push('Please fill in both department and percentage for all rows.');
            }
        });

        if (errors.length > 0) {
            alert(errors.join('\n'));
            return;
        }

        // Check if total is 100%
        if (totalPercentage !== 100) {
            if (!confirm('Total percentage is ' + totalPercentage + '%, not 100%. Do you want to continue?')) {
                return;
            }
        }

        // Disable save button to prevent double submission
        var saveBtn = $(this);
        saveBtn.prop('disabled', true).text('Saving...');

        // Prepare the URL
        var finalUrl = $('#costCentersModal').data('update-url');


        // --- SINGLE AJAX REQUEST ---
        $.ajax({
            url: finalUrl,
            type: 'POST',
            data: {
                'project_id': projectId,
                'csrfmiddlewaretoken': csrfToken,
                // Send assignments as a JSON string
                'assignments': JSON.stringify(assignmentsMap)
            },
            success: function(response) {
                alert('Cost center assignments saved successfully!');
                $('#costCentersModal').modal('hide');
                location.reload();
            },
            error: function(xhr, status, error) {
                console.log('Error:', xhr.responseText);
                alert('Error saving assignments. Please try again.');
            },
            complete: function() {
                // Re-enable save button
                saveBtn.prop('disabled', false).text('Save changes');
            }
        });
    });
});
