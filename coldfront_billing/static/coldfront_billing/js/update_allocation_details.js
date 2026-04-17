(function () {
    'use strict';

    function syncGrantEnabled($, deptHidden, grantSearch, grantHidden) {
        var hasDept = Boolean((deptHidden.val() || '').trim());
        grantSearch.prop('disabled', !hasDept);
        if (!hasDept) {
            grantHidden.val('');
            grantSearch.val('');
        }
    }

    function syncVisibleFromHidden($) {
        var deptHidden = $('#id_cost_center');
        var grantHidden = $('#id_grant');
        var deptSearch = $('#allocation-dept-search');
        var grantSearch = $('#allocation-grant-search');
        if (!deptHidden.length || !deptSearch.length) {
            return;
        }
        deptSearch.val((deptHidden.val() || '').trim());
        grantSearch.val((grantHidden.val() || '').trim());
        syncGrantEnabled($, deptHidden, grantSearch, grantHidden);
    }

    function syncHiddenFromVisible($) {
        var deptHidden = $('#id_cost_center');
        var grantHidden = $('#id_grant');
        var deptSearch = $('#allocation-dept-search');
        var grantSearch = $('#allocation-grant-search');
        deptHidden.val((deptSearch.val() || '').trim());
        if (!deptHidden.val()) {
            grantHidden.val('');
            grantSearch.val('');
        } else {
            grantHidden.val((grantSearch.val() || '').trim());
        }
        deptHidden.trigger('change');
    }

    function initAllocationCostCenterAutocomplete($) {
        var root = $('#allocation-cost-center-autocomplete');
        if (!root.length) {
            return;
        }
        var url = root.data('autocomplete-url');
        if (typeof window.initColdfrontCostCenterAutocomplete !== 'function' || !url) {
            return;
        }
        window.initColdfrontCostCenterAutocomplete({
            delegateRoot: root,
            autocompleteUrl: url,
        });

        var deptHidden = $('#id_cost_center');
        var grantHidden = $('#id_grant');
        var deptSearch = $('#allocation-dept-search');
        var grantSearch = $('#allocation-grant-search');

        syncVisibleFromHidden($);

        root.on('input', '.dept-autocomplete-input', function () {
            var v = (($(this).val() || '') + '').trim();
            if (!v) {
                deptHidden.val('');
                grantHidden.val('');
                grantSearch.val('');
                syncGrantEnabled($, deptHidden, grantSearch, grantHidden);
            }
        });

        root.on('change', '.dept-autocomplete-input', function () {
            deptHidden.val((($(this).val() || '') + '').trim());
            if (!deptHidden.val()) {
                grantHidden.val('');
                grantSearch.val('');
            }
            syncGrantEnabled($, deptHidden, grantSearch, grantHidden);
        });

        $('#allocation-details-form').on('submit', function () {
            syncHiddenFromVisible($);
        });
    }

    function run() {
        if (typeof jQuery === 'undefined') {
            return;
        }
        var $ = jQuery;
        initAllocationCostCenterAutocomplete($);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', run);
    } else {
        run();
    }
})();
