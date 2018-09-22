$(function() {
    // Activate tab state from URL fragment.
    $('.nav-tabs a').each(function() {
        if (window.location.hash == "#"+this.getAttribute("aria-controls"))
            $(this).tab('show');
    })
    $('.nav-tabs a').on('shown.bs.tab', function(e) {
        window.history.pushState(null, "", e.target.href);
    });

    // Place advertiements, if there are any zones on this page.
    $('.ads[data-zone]').each(function() {
        init_ad_zone($(this));
    });

    // Run any inline-defined scripts that have to wait until after jQuery is
    // available.
    for (var i = 0; i < window.post_jquery_load_scripts.length; i++)
        window.post_jquery_load_scripts[i]();
});

function show_modal(title, message) {
    $('#error_modal h2').text(title);
    if (message.charAt(0) != '<') {
        $('#error_modal .modal-dialog').toggleClass('modal-sm', true);
        $('#error_modal .modal-body').html($("<p/>").text(message).html());
    } else {
        $('#error_modal .modal-dialog').toggleClass('modal-sm', false);
        $('#error_modal .modal-body').html(message);
    }
    $('#error_modal').modal({});
}

function init_ad_zone(ad_container) {
    // Track some ad impression statistics.
    var ad_cookie = $.cookie("ads");
    if (ad_cookie) ad_cookie = parse_qs(ad_cookie);
    if (!ad_cookie) ad_cookie = { };

    // put users in buckets: assign each user a random number in [0,1].
    if (!ad_cookie.segment) ad_cookie.segment = Math.random();
    
    // save cookie
    $.cookie("ad_exp", form_qs(ad_cookie), { expires: 21, path: '/' });

    // Activate page-level auto-placement ads.
    if (!is_ad_free) {
        (adsbygoogle = window.adsbygoogle || []).push({
          google_ad_client: "ca-pub-3418906291605762",
          enable_page_level_ads: true
        });
    }

    // Show ad.

    function write_ad_code(html, text) {
        // Create DOM node and insert.
        var node = $(html);
        if (text) node.text(text);
        ad_container.prepend(node);
        ad_container.show();
    }

    if (is_ad_free) {
        // user has paid to hide the ads
        write_ad_code("<div></div>", "An ad would be here, but you've gone ad-free!");

    } else if (false) {
        // for debugging, show a green box
        write_ad_code('<div style="width:336px;height:280px;background:green"></div>')

    /*} else if (the_segment == "House" || the_segment == "Senate") {
        // ad unit targeting staff only
        write_ad_code('<ins class="adsbygoogle" style="display:inline-block;width:300px;height:250px" data-ad-client="ca-pub-3418906291605762" data-ad-slot="7881093146"></ins>');
        (adsbygoogle = window.adsbygoogle || []).push({});
        */

    } else if (ad_container.attr('data-zone') == "master_a" && $(window).width() >= 1170) {
		// Master A Google AdSense 336x280 unit.
        write_ad_code('<ins class="adsbygoogle" style="margin:0 -4px;display:inline-block;width:336px;height:280px" data-ad-client="ca-pub-3418906291605762" data-ad-slot="4342089141"></ins>');
        (adsbygoogle = window.adsbygoogle || []).push({});

    } else if (ad_container.attr('data-zone') == "master_a" && $(window).width() >= 970) {
		// Master A Google AdSense 200x200 unit.
        write_ad_code('<ins class="adsbygoogle" style="display:inline-block;width:200px;height:200px" data-ad-client="ca-pub-3418906291605762" data-ad-slot="8659683806"></ins>');
        (adsbygoogle = window.adsbygoogle || []).push({});

    } else if (ad_container.attr('data-zone') == "master_a") {
        // Master A Google AdSense Responsive unit
        write_ad_code('<ins class="adsbygoogle" style="display:block" data-ad-client="ca-pub-3418906291605762" data-ad-slot="3758146349" data-ad-format="auto"></ins>');
        (adsbygoogle = window.adsbygoogle || []).push({});

    } else if (ad_container.attr('data-zone') == "footer" && $(window).width() >= 800) {
        // Footer leaderboard Media.net unit, when the viewport is large enough to display it.
        write_ad_code('<div id="536175723"></div>');
        try { window._mNHandle.queue.push(function () {
            window._mNDetails.loadTag("536175723", "728x90", "536175723");
        }); } catch (error) { }

//    } else if (ad_container.attr('data-zone') == "footer" && $(window).width() >= 800) {
        // Footer leaderboard Google AdSense unit, when the viewport is large enough to display it.
        write_ad_code('<ins class="adsbygoogle" style="display:inline-block;width:728px;height:90px" data-ad-client="ca-pub-3418906291605762" data-ad-slot="5620102176"></ins>');
        (adsbygoogle = window.adsbygoogle || []).push({});
    }
}

function smooth_scroll_to(elem) {
    $("html, body").animate({ scrollTop: elem.offset().top - $(window).height()/10 });
    return false;
}
