(function () {
    var btn = document.getElementById('run-report-once-btn');
    var toast = document.getElementById('send-report-toast');
    var toastMsg = document.getElementById('send-report-toast-message');
    if (!btn || !toast || !toastMsg) return;
    var sendUrl = btn.dataset.sendReportUrl;
    if (!sendUrl) return;

    function showSendReportToast(success, message) {
        toast.classList.remove('alert-success', 'alert-danger');
        toast.classList.add(success ? 'alert-success' : 'alert-danger');
        toastMsg.textContent = message;
        toast.style.display = 'block';
        void toast.offsetWidth;
        toast.classList.add('show');
        clearTimeout(showSendReportToast._hideTimer);
        showSendReportToast._hideTimer = setTimeout(function () {
            toast.classList.remove('show');
            setTimeout(function () {
                toast.style.display = 'none';
            }, 150);
        }, 6000);
    }

    btn.addEventListener('click', function () {
        btn.disabled = true;
        var prevHtml = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin" aria-hidden="true"></i> Sending…';
        fetch(sendUrl, {
            credentials: 'same-origin',
            headers: { 'Accept': 'application/json' },
        })
            .then(function (response) {
                return response.json().then(function (data) {
                    return { response: response, data: data };
                });
            })
            .catch(function () {
                return {
                    response: { ok: false },
                    data: {
                        success: false,
                        message: 'Could not reach the server or the response was not valid JSON.',
                    },
                };
            })
            .then(function (result) {
                var data = result.data || {};
                var message = data.message || (result.response.ok ? 'Done.' : 'Request failed.');
                var success = data.success === true;
                showSendReportToast(success, message);
            })
            .finally(function () {
                btn.disabled = false;
                btn.innerHTML = prevHtml;
            });
    });
})();
