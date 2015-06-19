function show_mysoc_survey() {
    // Percentage of users to display the survey for
    var p = .25;

    // Is cookie existing?

    var ct = null;
    var ca = document.cookie.split(';');
    for(var i=0;i < ca.length;i++) {
        var c = ca[i];
        while (c.charAt(0)==' ') {
            c = c.substring(1,c.length);
        }
        if (c.indexOf('ms_srv_t=') == 0) {
            // Cookie for time...
            var ct = c.substring('ms_srv_t='.length,c.length);
        }
        if (c.indexOf('ms_srv_r=') == 0) {
            // Cookie for referrer...
            var cr = c.substring('ms_srv_r='.length,c.length);
        }
    }

    if (ct == null) {
        // No cookie!
        if (Math.random() < p) {
            // Chosen to survey
            // Set the cookie to current timestamp
            var t = Math.round(new Date().getTime() / 1000);
            document.cookie = 'ms_srv_t='+t+'; path=/';
            document.cookie = 'ms_srv_r='+document.referrer+'; path=/';
            ct = t;
            cr = document.referrer;

        } else {
            // Not chosen to survey
            // Set cookie to X
            document.cookie = 'ms_srv_t=X; path=/';
            ct = 'X'
        }
    }

    // Only bother to do this if the cookie is set and the link exists
    if (ct != 'X' && !! document.getElementById('ms_srv_wrapper')) {

        // Find the time on site thus far
        var st = Math.round(new Date().getTime() / 1000) - ct;

        // Find if the user is signed in
        var su = !! document.getElementById('user-meta');

        // Find the URL on the page
        var l = document.getElementById('ms_srv_link');

        data = {
            'ms_time': st,
            'ms_referrer': cr || null,
            'ms_registered': su,
            'ms_transaction': l.getAttribute('data-transaction')
        }

        // Assemble the query string
        var qs = [];
        for (var d in data) {
           qs.push(encodeURIComponent(d) + "=" + encodeURIComponent(data[d]));
        }

        // Append query string to the URL
        l.href = l.href + '?' + qs.join('&');

        // Show the survey link element
        $('#mysoc_survey_modal').modal();

        // Track in GovTrack analytics.
        _paq.push(['trackEvent', 'mysociety-survey', 'shown', '']);
    }

}

$(function() {
    window.setTimeout(show_mysoc_survey, 5000);
})
