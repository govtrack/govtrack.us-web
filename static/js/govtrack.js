$(function() {
    // Activate tab state from URL fragment.
    // TODO This doesn't work when activating a tab within a tab
    // if a parent tab also needs to be activated.
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

    // Autocomplete for the site search box.
    init_site_search_for_control($('#master_search_q'), {
        tips: "Enter a bill number like <nobr>H.R. 123</nobr> or <nobr>H.R. 123/110</nobr> (for previous Congresses), law number (e.g. P.L. 110-64), or keywords. Or search legislators, committees, and subject areas."
    });

    // Activate Senate/House in session in the nav bar.
    if (is_congress_in_session_live.house == "yes") $('#nav-in-session-house').show();
    if (is_congress_in_session_live.senate == "yes") $('#nav-in-session-senate').show();
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

function addLazyScriptTag(src, onload) {
    // https://stackoverflow.com/questions/8578617/inject-a-script-tag-with-remote-src-and-wait-for-it-to-execute
    const script = document.createElement('script');
    script.src = src;
    script.crossorigin = "anonymous";
    if (onload) script.addEventListener('load', onload);
    if (onerror) script.addEventListener('error', onerror);
    document.getElementsByTagName('head')[0].appendChild(script);
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

    // Load AdSense.
    if (!window.has_added_adsense_script_tag && !is_ad_free) {
        addLazyScriptTag("https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-3418906291605762");
        window.has_added_adsense_script_tag = true;
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

    } else if (ad_container.attr('data-zone') == "footer" && $(window).width() >= 1200) { // container width is 960
        // Master A Google AdSense Responsive unit
        write_ad_code('<ins class="adsbygoogle" style="display:block" data-ad-client="ca-pub-3418906291605762" data-ad-slot="3758146349" data-ad-format="auto"></ins>');
        (adsbygoogle = window.adsbygoogle || []).push({});
    } else if (ad_container.attr('data-zone') == "footer" && $(window).width() >= 992) { // container width is 960
        // Footer leaderboard Google AdSense unit (728x90)
        write_ad_code('<ins class="adsbygoogle" style="display:inline-block;width:728px;height:90px" data-ad-client="ca-pub-3418906291605762" data-ad-slot="5620102176"></ins>');
        (adsbygoogle = window.adsbygoogle || []).push({});
    } else if (ad_container.attr('data-zone') == "footer" && $(window).width() >= 330) {
        // Smartphone Banner Google AdSense unit (320x50)
        write_ad_code('<ins class="adsbygoogle" style="display:inline-block;width:320px;height:50px" data-ad-client="ca-pub-3418906291605762" data-ad-slot="8745863219"></ins>');
        (adsbygoogle = window.adsbygoogle || []).push({});

    } else if (ad_container.attr('data-zone') == "header" && $(window).width() >= 1200) { // container width is 960
	// Top Billboard Google AdSense unit (970x250)
	write_ad_code('<ins class="adsbygoogle" style="display:inline-block;width:970px;height:250px" data-ad-client="ca-pub-3418906291605762" data-ad-slot="9787482143"></ins>');
        (adsbygoogle = window.adsbygoogle || []).push({});
    } else if (ad_container.attr('data-zone') == "header" && $(window).width() >= 992) { // container width is 960
	// Top Leaderboard Google AdSense unit (728x90)
	write_ad_code('<ins class="adsbygoogle" style="display:inline-block;width:728px;height:90px" data-ad-client="ca-pub-3418906291605762" data-ad-slot="3192837063"></ins>');
        (adsbygoogle = window.adsbygoogle || []).push({});
    } else if (ad_container.attr('data-zone') == "header" && $(window).width() >= 330) {
        // Smartphone Banner Google AdSense unit (320x50)
	write_ad_code('<ins class="adsbygoogle" style="display:inline-block;width:320px;height:50px" data-ad-client="ca-pub-3418906291605762" data-ad-slot="8745863219"></ins>');
        (adsbygoogle = window.adsbygoogle || []).push({});
    }
}

function smooth_scroll_to(elem) {
    $("html, body").animate({ scrollTop: elem.offset().top - $(window).height()/10 });
    return false;
}

function ordinal(n) {
    var t = ['th', 'st', 'nd', 'rd', 'th', 'th', 'th', 'th', 'th', 'th'];
    var m;
    if (n % 100 >= 11 && n % 100 <= 13)
        m = 0;
    else
        m = n % 10;
    return n + "<sup>" + t[m] + "</sup>";
}

function init_site_search_for_control(elem, options) {
    var closure = {
        last_input: 0,
        working: false,
        hover: false,
        blurred: false
    };

    // Initialize events.
    elem.on("input", run_search_on_delay);
    elem.on("blur", function() {
        closure["blurred"] = true;
        if (closure["hover"]) return;
        $("#site_search_autocomplete_results").hide();
    })
    elem.on("focus", function() {
        // If we lost focus to the results but get back
        // while the results are still open, don't re-start
        // the search. The user may have pressed ESC, which
        // closes the results and returns to the input element
        // but should not re-open results.
        if (closure["hover"]) return;
        run_search();
    });
    elem.on("keydown", function(event) {
      if (event.which == 40) { // down arrow
        // If results are shown, shift focus to first result.
        var container = $("#site_search_autocomplete_results");
        if (container.is(":visible")) {
          var items = container.find('.result-item');
          if (items) {
              closure["hover"] = true;
              event.stopPropagation();
              setTimeout(function() {
                $(items[0]).focus();
              }, 1);
          }
        }
      }
      if (event.which == 27) { // escape
        var container = $("#site_search_autocomplete_results");
        container.hide();
      }
    });

    function run_search_on_delay() {
        // The user made a change to the text. But don't
        // start the search until a delay in which there
        // are no more inputs. Increment a sentinel on
        // each input event. Then delay. After the delay,
        // if the sentinel has not changed, fire the next
        // step.
        closure['last_input']++;
        var current_input = closure['last_input'];
        setTimeout(function() {
            // If we have an AJAX request in progress,
            // then delay until it's done.
            if (closure["working"]) {
                run_search_on_delay();
                return;
            }

            // Have any more inputs come in?
            if (current_input == closure['last_input'])
                run_search();
        }, 150);
    }

    // Run search query and show matches.
    function run_search() {
        var q = $(elem).val();
        if (!/\S/.test(q)) {
            // Empty / all whitespace.
            show_results({ result_groups: [] });
        } else {
            // Run AJAX query.
            closure["working"] = true;
            $.ajax({
                url: "/search/_autocomplete",
                data: {
                    q: q
                },
                success: function(res) {
                    closure["working"] = false;
                    show_results(res);
                }, error: function() {
                    closure["working"] = false;
                }
            })
        }
    }

    // Results UI.
    function show_results(results) {
        // Construct a div to hold results.
        closure["blurred"] = false;
        closure["hover"] = false;
        var container = $("#site_search_autocomplete_results");
        if (container.length == 0) {
            container = $("<div id=site_search_autocomplete_results></div>");
            $('body').append(container);
            container.on("mouseenter", function() {
                closure["hover"] = true;
            })
            container.on("mouseleave", function() {
                closure["hover"] = false;
                if (closure["blurred"]) container.hide();
            })
        }

        // Clear results.
        container.text('');

        // Hide if no results and no tips.
        if (results.result_groups.length == 0 && !(options && options.tips)) {
            container.hide();
            return;
        }

        // Construct results - first by group.
        results.result_groups.forEach(function(group) {
            // Make a group header.
            var group_container = $("<div class='search-result-group'></div>");
            container.append(group_container);
            group_container.text(group.title);

            // Add the items.
            group.results.forEach(function(item) {
                var item_container = $("<a class='result-item'></a>")
                container.append(item_container);
                item_container.text(item.label);
                item_container.attr('href', item.href);

                // Attach keyboard navigation.
                item_container.on("keydown", function(event) {
                  if (event.which == 38) { // up arrow
                    event.preventDefault();
                    // prevAll instead of prev so that it can skip result group headings
                    var prev_item = item_container.prevAll('.result-item:first');
                    if (!prev_item.length) prev_item = $(elem);
                    setTimeout(function() {
                      prev_item.focus();
                    }, 1);
                  }
                  if (event.which == 40) { // down arrow
                    event.preventDefault();
                    var next_item = item_container.nextAll('.result-item:first');
                    if (!next_item.length) return;
                    setTimeout(function() {
                      next_item.focus();
                    }, 1);
                  }
                  if (event.which == 27) { // escape
                    container.hide();
                    $(elem).focus();
                  }
                });
            });
        });



        // Add tips.
        if (options && options.tips) {
            var group_container = $("<div class='search-result-group search-tips'></div>");
            container.append(group_container);
            group_container.html(options.tips);
        }

        // Show results.
        container.css({
            display: 'block',
            position: 'absolute',
            top: $(elem).offset().top + $(elem).outerHeight(),
        });
        var w = $(elem).outerWidth();
        if (w > 300) {
            container.css({
                left: $(elem).offset().left,
                width: $(elem).outerWidth()
            });
        } else if ($(window).innerWidth() - $(elem).offset().left > 300) {
            container.css({
                left: $(elem).offset().left,
                width: $(window).innerWidth() - $(elem).offset().left - 5 /* our padding */
            });
        } else {
            container.css({
                left: 5,
                width: $(window).innerWidth() - 15
            });
        }
    }
}
