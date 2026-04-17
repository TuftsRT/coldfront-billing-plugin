/**
 * Typeahead for cost centers / grants (CostCenterAutocompleteView: GET ?q= & type=).
 * Depends on jQuery. Used by billing modal and allocation completion form.
 * Registers on DOMContentLoaded so jQuery can load after this tag in the document.
 */
(function () {
    'use strict';

    function register($) {
        var DEBOUNCE_TIME_MS = 250;
        var AC_HIGHLIGHT_CLASS = 'active';

        /**
         * @param {object} config
         * @param {JQuery} config.delegateRoot - element to attach delegated handlers (e.g. table tbody or wrapper div)
         * @param {string} config.autocompleteUrl - URL returning { results: string[] }
         */
        function initColdfrontCostCenterAutocomplete(config) {
            var delegateRoot = config.delegateRoot;
            var autocompleteUrl = config.autocompleteUrl;
            if (!delegateRoot || !delegateRoot.length || !autocompleteUrl) {
                return;
            }

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

            function bindAutocomplete(acConfig) {
                var inputSel = acConfig.inputSelector;
                var resultsSel = acConfig.resultsSelector;
                var typeParam = acConfig.typeParam;
                var triggerChangeOnSelect = !!acConfig.triggerChangeOnSelect;

                delegateRoot.on('input', inputSel, function () {
                var input = $(this);
                var list = resultsListForInput(input, resultsSel);
                clearTimeout(input.data('ac-debounce'));

                var q = input.val().trim();
                if (q.length < 3) {
                    abortPending(input);
                    hideResults(list, input);
                    return;
                }

                input.data(
                    'ac-debounce',
                    setTimeout(function () {
                        var seq = bumpSeq(input);
                        abortPending(input);

                        var xhr = $.getJSON(autocompleteUrl, { q: q, type: typeParam })
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
                    }, DEBOUNCE_TIME_MS)
                );
            });

            delegateRoot.on('mousedown', resultsSel + ' li', function (e) {
                e.preventDefault();
                var li = $(this);
                var list = li.parent();
                var input = list.closest('.autocomplete-wrapper').find(inputSel);
                applyAutocompleteChoice(input, list, li, triggerChangeOnSelect);
            });

            delegateRoot.on('blur', inputSel, function () {
                var input = $(this);
                var list = resultsListForInput(input, resultsSel);
                setTimeout(function () {
                    hideResults(list, input);
                }, 200);
            });

            delegateRoot.on('keydown', inputSel, function (e) {
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
            triggerChangeOnSelect: true,
        });
        bindAutocomplete({
            inputSelector: '.grant-autocomplete-input',
            resultsSelector: '.grant-autocomplete-results',
            typeParam: 'grant',
            triggerChangeOnSelect: false,
        });
        }

        window.initColdfrontCostCenterAutocomplete = initColdfrontCostCenterAutocomplete;
    }

    function boot() {
        if (typeof jQuery === 'undefined') {
            return;
        }
        register(jQuery);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }
})();
