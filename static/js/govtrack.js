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

function init_ad_zone(ad_container) {
    // Track some ad impression statistics.
    var ad_cookie = $.cookie("ads");
    if (ad_cookie) ad_cookie = parse_qs(ad_cookie);
    if (!ad_cookie) ad_cookie = { };

    // put users in buckets: assign each user a random number in [0,1].
    if (!ad_cookie.segment) ad_cookie.segment = Math.random();

    // save cookie
    $.cookie("ad_exp", form_qs(ad_cookie), { expires: 21, path: '/' });

    // Defer ad zone scripts until the partner script is loaded.
    let deferred_scripts = [];
    window.deferred_ad_script ||= (func) => { deferred_scripts.push(func); };

    // Load ad partner script.
    if (!window.has_added_ads_script_tag && !is_ad_free) {
        //window.ad_provider = (ad_cookie.segment < .75) ? "adsense" : "publir";
        window.ad_provider = "publir";

        // https://stackoverflow.com/questions/8578617/inject-a-script-tag-with-remote-src-and-wait-for-it-to-execute

        const script = document.createElement('script');

        // Google AdSense
        if (window.ad_provider == "adsense")
        {
            script.src = "https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-3418906291605762";
            script.crossorigin = "anonymous";
        }
        else if (false)
        {
            // Always load the AdSense code for vignette ads, even if the display ads are coming from another provider.
            const script_adsense = document.createElement('script');
            script_adsense.src = "https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-3418906291605762";
            script_adsense.crossorigin = "anonymous";
            script_adsense.type = "text/javascript";
            document.getElementsByTagName('head')[0].appendChild(script_adsense);
        }

        // Publir
        if (window.ad_provider == "publir")
        {
            script.src = "//a.publir.com/platform/1591.js";
            script.id = "headerbidder";
        }

        script.type = "text/javascript";
        script.addEventListener('load', () => {
            deferred_scripts.forEach((func) => func()); // execute deferred scripts
            window.deferred_ad_script = (func) => { func(); }; // now execute immediately
        });
        document.getElementsByTagName('head')[0].appendChild(script);

        window.has_added_ads_script_tag = true;
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

    } else if (window.ad_provider == "adsense") {
        if (ad_container.attr('data-zone') == "sidebar" && $(window).width() >= 1170) {
            // Master A Google AdSense 336x280 unit.
            write_ad_code('<ins class="adsbygoogle" style="margin:0 -4px;display:inline-block;width:336px;height:280px" data-ad-client="ca-pub-3418906291605762" data-ad-slot="4342089141"></ins>');
            (adsbygoogle = window.adsbygoogle || []).push({});

        } else if (ad_container.attr('data-zone') == "sidebar" && $(window).width() >= 970) {
            // Master A Google AdSense 200x200 unit.
            write_ad_code('<ins class="adsbygoogle" style="display:inline-block;width:200px;height:200px" data-ad-client="ca-pub-3418906291605762" data-ad-slot="8659683806"></ins>');
            (adsbygoogle = window.adsbygoogle || []).push({});

        } else if (ad_container.attr('data-zone') == "sidebar") {
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
    } else if (window.ad_provider == "publir") {
        if (ad_container.attr('data-zone') == "sidebar") {
            // Sidebar Zone - Publir
            write_ad_code('<div id="div-hre-Govtrack-4171" class="publirAds">');
            window.deferred_ad_script(() => { googletag.cmd.push(function() {  googletag.pubads().addEventListener('slotRenderEnded', function(event) { if (event.slot.getSlotElementId() == "div-hre-Govtrack-4171") {googletag.display("div-hre-Govtrack-4171");} });}); });

        } else if (ad_container.attr('data-zone') == "header" || ad_container.attr('data-zone') == "footer") {
            // Header / Footer / In-Page Leaderboard Zone - Publir
            write_ad_code('<div id="div-hre-Govtrack-4169" class="publirAds">');
            window.deferred_ad_script(() => { googletag.cmd.push(function() {  googletag.pubads().addEventListener('slotRenderEnded', function(event) { if (event.slot.getSlotElementId() == "div-hre-Govtrack-4169") {googletag.display("div-hre-Govtrack-4169");} });}); });
        }
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

function redirect_to_district_page(state, district, lnglat, queryText)
{
  let path = "/congress/members/" + state;
  if (district != 0)
    path += "/" + district;
  if (queryText || lnglat)
    path += "#";
  if (queryText)
    path += "q=" + encodeURIComponent(queryText);
  if (queryText && lnglat)
    path += "&";
  if (lnglat)
    path += "marker_lng=" + lnglat[0] + "&marker_lat=" + lnglat[1];
  window.location = path;
}

function find_district_from_address_or_location(query, callback) {
  // Query is either { address: "12 Main Street..." }
  // or { lng: ..., lat: ... }. Callback is called with
  // callback(state, district, lnglat, queryText),
  // where queryText is the address if given, otherwise null.
  $.ajax({
    url: '/congress/members/lookup-district.json',
    data: query,
    method: 'POST',
    success: function(feature) {
      if (!feature) {
        alert("Could not find that address.");
        return;
      }

      // feature is a GeoJSON features dictionary from our pmtiles file,
      // plus a 'query' attribute with lng and lat properties if this
      // query was an address.
      let state = feature.state;
      let district = parseInt(feature.number);
      let lnglat = feature.query;
      let queryText = query.address; // may be null
      callback(state, district, lnglat, queryText);
    }
  });
}

function redirect_to_district_page_from_address(address)
{
  find_district_from_address_or_location({ address: address }, redirect_to_district_page);
}  

function redirect_to_district_page_from_geolocation() {
  if ("geolocation" in navigator)
  {
    navigator.geolocation.getCurrentPosition(function(position) {
      find_district_from_address_or_location(
        { lng: position.coords.longitude, lat: position.coords.latitude},
        redirect_to_district_page);
    });
    return;
  }
  alert("Location not available.");
}