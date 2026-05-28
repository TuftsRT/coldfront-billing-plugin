document.addEventListener('DOMContentLoaded', function () {
    var hideTimer;

    function scheduleHide($trigger) {
        clearTimeout(hideTimer);
        hideTimer = setTimeout(function () {
            if (!$('.popover:hover').length) {
                $trigger.popover('hide');
            }
        }, 150);
    }

    $('.js-ncq-inactive-popover').popover({
        trigger: 'manual',
        container: 'body',
        placement: 'right',
        title: '',
    }).on('mouseenter', function () {
        clearTimeout(hideTimer);
        $(this).popover('show');
    }).on('mouseleave', function () {
        scheduleHide($(this));
    });

    $(document).on('mouseenter', '.popover', function () {
        clearTimeout(hideTimer);
    }).on('mouseleave', '.popover', function () {
        $('.js-ncq-inactive-popover').each(function () {
            if (!$(this).is(':hover')) {
                scheduleHide($(this));
            }
        });
    });
});
