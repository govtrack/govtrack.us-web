$(function() {
    // Place advertiements, depending on which page layout is used on this page.

    var master_a_ad_container = $('#master_a_ad');
    if (master_a_ad_container.length)
        master_a_ad(master_a_ad_container);

    var footer_leaderboard_ad_container = $('#footer_leaderboard_ad_container');
    if (footer_leaderboard_ad_container.length)
        footer_leaderboard_ad(footer_leaderboard_ad_container);

    var bill_text_ad_container = $('#bill-text-ad-container');
    if (bill_text_ad_container.length)
        bill_text_ad(bill_text_ad_container);

    // Run any inline-defined scripts that have to wait until after jQuery is
    // available.
    for (var i = 0; i < window.post_jquery_load_scripts.length; i++)
        window.post_jquery_load_scripts[i]();
});

function show_modal(title, message) {
    $('#error_modal h4').text(title);
    if (message.charAt(0) != '<') {
        $('#error_modal .modal-dialog').toggleClass('modal-sm', true);
        $('#error_modal .modal-body').html($("<p/>").text(message).html());
    } else {
        $('#error_modal .modal-dialog').toggleClass('modal-sm', false);
        $('#error_modal .modal-body').html(message);
    }
    $('#error_modal').modal({});
}

function master_a_ad(ad_container) {
    // Track some ad impression statistics.
    var ad_exp_user = $.cookie("ad_exp");
    if (ad_exp_user) ad_exp_user = parse_qs(ad_exp_user);
    if (!ad_exp_user) ad_exp_user = { };

    // increment impression count
    if (!ad_exp_user.impression) ad_exp_user.impression = 0;
    ad_exp_user.impression += 1;

    // put users in buckets: assign each user a random number in [0,1].
    if (!ad_exp_user.segment) ad_exp_user.segment = Math.random();
    
    // save cookie
    $.cookie("ad_exp", form_qs(ad_exp_user), { expires: 21, path: '/' });

    // Show ad.

    function write_ad_code(html, text) {
        // Create DOM node and insert.
        var node = $(html);
        if (text) node.text(text);
        ad_container.append(node);
    }

    var did_show_ad = false;
    if (is_ad_free) {
        // user has paid to hide the ads
        write_ad_code("<div></div>", "An ad would be here, but you've gone ad-free!");

    } else if (false) {
        // for debugging, show a green box
        write_ad_code('<div style="width:336px;height:280px;background:green"></div>')

    } else if (the_segment == "House" || the_segment == "Senate") {
        // ad unit targeting staff only
        write_ad_code('<ins class="adsbygoogle" style="display:inline-block;width:300px;height:250px" data-ad-client="ca-pub-3418906291605762" data-ad-slot="7881093146"></ins>');
        (adsbygoogle = window.adsbygoogle || []).push({});
        did_show_ad = true;

    } else {
        // Master A Responsive
        write_ad_code('<ins class="adsbygoogle" style="display:block" data-ad-client="ca-pub-3418906291605762" data-ad-slot="3758146349" data-ad-format="auto"></ins>');
        (adsbygoogle = window.adsbygoogle || []).push({});
        did_show_ad = true;
    }

    if (did_show_ad) $(function() { setTimeout(pop_ad, 250); });
    function pop_ad() {
        // Make the ad fixed to where it is in the viewport. First, pop it out of
        // its natural container.

        // get its original location
        var row = $('#master-a-sidebar').parent('.row');
        var col = $('#master-a-sidebar');
        var ads = $('#master-a-sidebar').find('.ads');
        var ads_height = ads.outerHeight();
        var original_offset = ads.offset(); // works when making it 'fixed' positioned
        var original_pos = ads.position(); // for 'absolute' positioned because it's in a relatively positioned column

        // because in a responsive layout the column may move, make the
        // fixed positioning relative to the column
        original_offset.left -= col.offset().left;

        // adjust for any top/bottom margins that mess with how top: works in fixed positioning
        original_offset.top -= parseInt(ads.css("marginTop"));
        var marginBottom = parseInt(ads.css("marginBottom"));

        function update_ad_pos() {
            var row_height = row.innerHeight();
            var top = original_pos.top + $(window).scrollTop();
            if ($(window).width() < 768 || row.offset().left == col.offset().left) {
                // the column is collapsed in xs layout
                // - two ways of checking, the latter is because IE8 doesn't support
                //   grid layouts at all
                ads.css({
                    position: "static"
                })
            } else if (original_offset.top + ads_height > $(window).height()) {
                // The ad isn't entirely visible anyway -- it's too tall -- so don't
                // try to keep it where it is. Allow it to be scrolled to come into view.
                ads.css({
                    position: "static"
                })
            } else if (top < row_height - ads_height - marginBottom) {
                // fixed positioning works here
                ads.css({
                    position: "fixed",
                    left: original_offset.left + col.offset().left - $(window).scrollLeft()/2,
                    top: original_offset.top
                })
            } else {
                // scrolled too far, now need to go back to absolute to lock it
                // in at the location that is as low as it can go so it doesn't
                // cover the page footer
                ads.css({
                    position: "absolute",
                    left: original_pos.left,
                    top: row_height - ads_height - marginBottom
                });
            }
        }
        $(window).scroll(update_ad_pos);
        $(window).resize(update_ad_pos);
        update_ad_pos();
    };

    // track how many hits have the ads blocked - seems to work with AdBlockPlus
    if (did_show_ad)
        setTimeout(function() {
            var are_ads_blocked = ($(".adsbygoogle iframe:visible").length == 0);
            ga('send', 'event', 'ads', 'adblocker', are_ads_blocked ? 'blocked' : 'not-blocked');
        }, 3000);
}

function footer_leaderboard_ad(container) {
    // Don't display on small screens or if the user has bought out of ads.
    if ($(window).width() < 800 || is_ad_free)
        return;

    // Place the ad.
    var node = $('<ins class="adsbygoogle" style="display:inline-block;width:728px;height:90px" data-ad-client="ca-pub-3418906291605762" data-ad-slot="5620102176"></ins>');
    container.append(node);
    (adsbygoogle = window.adsbygoogle || []).push({});

    // Show the container.
    $('.ads.footer.leaderboard').show();
}

function bill_text_ad(container) {
    // Don't display on small screens or if the user has bought out of ads.
    if ($(window).width() < 992 || is_ad_free)
        return;

    // Add the Master A Responsive tag.
    container.find(".ad-container").html('<ins class="adsbygoogle" style="display:block" data-ad-client="ca-pub-3418906291605762" data-ad-slot="3758146349" data-ad-format="auto"></ins>');
    (adsbygoogle = window.adsbygoogle || []).push({});

    // Show the container.
    container.show();
}
