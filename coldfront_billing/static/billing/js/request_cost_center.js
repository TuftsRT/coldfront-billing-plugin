/**
 * The cost center and grant autocomplete in the billing_cost card on the allocation request form.
 * The card is swapped in by htmx when the resource changes, so each card is started on htmx:load
 * (ColdFront's bundle doesn't make htmx a global), and on page load for the card the page starts with.
 * The visible search boxes are copied into the section's hidden fields as they change and on submit.
 * The card loads this script each time it's swapped in; it sets itself up once. The submit copy is one
 * listener for the page, which looks the live card up when the form is sent, so swapped-out cards leave
 * nothing behind.
 */
(function () {
    'use strict';

    var $ = window.jQuery;
    if (!$ || window.billingRequestCostCenter) {
        return;
    }
    window.billingRequestCostCenter = true;

    function fields(root) {
        return {
            deptHidden: $('#' + root.data('cost-center-id')),
            grantHidden: $('#' + root.data('grant-id')),
            deptSearch: root.find('.dept-autocomplete-input'),
            grantSearch: root.find('.grant-autocomplete-input'),
        };
    }

    // copy the search boxes into the hidden fields; a grant only goes with a cost center, so without one the
    // grant is cleared and can't be typed
    function copyToHidden(root) {
        var f = fields(root);
        var dept = (f.deptSearch.val() || '').trim();
        f.deptHidden.val(dept);
        if (!dept) {
            f.grantSearch.val('');
        }
        f.grantHidden.val(dept ? (f.grantSearch.val() || '').trim() : '');
        f.grantSearch.prop('disabled', !dept);
    }

    function startCard(root) {
        if (root.data('billing-started')) {
            return;
        }
        root.data('billing-started', true);
        if (typeof window.initColdfrontCostCenterAutocomplete === 'function') {
            window.initColdfrontCostCenterAutocomplete({delegateRoot: root, autocompleteUrl: root.data('autocomplete-url')});
        }
        var f = fields(root);
        f.deptSearch.val((f.deptHidden.val() || '').trim());
        f.grantSearch.val((f.grantHidden.val() || '').trim());
        copyToHidden(root);
        root.on('input change', '.dept-autocomplete-input, .grant-autocomplete-input', function () {
            copyToHidden(root);
        });
    }

    function startAll(element) {
        $(element).find('.billing-cost-center-autocomplete').addBack('.billing-cost-center-autocomplete').each(function () {
            startCard($(this));
        });
    }

    document.addEventListener('htmx:load', function (event) {
        startAll(event.target);
    });
    // capture, so the hidden fields are filled before the form's own submit handlers run
    document.addEventListener('submit', function (event) {
        $(event.target).find('.billing-cost-center-autocomplete').each(function () {
            copyToHidden($(this));
        });
    }, true);
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            startAll(document);
        });
    } else {
        startAll(document);
    }
})();
