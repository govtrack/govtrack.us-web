// Some of my own utilities.

// Modernizing placeholder="...".
//
// Display a default value in text fields with a "default" class until
// user focuses the field, at which point the field is cleared and
// the "default" class is removed. If the user leaves the field and
// it's empty, the default text is replaced.
//
// If value is null then it works differently: the existing text in the
// field is taken to be its existing/default value. The "default" class
// is applied. When the field takes focus, the text is left unchanged
// so the user can edit the existing value but the default class is
// removed. When the user leaves the field, if it has the same value
// as its original value the default class is put back. So, the user
// can see if he has made a change.
jQuery.fn.input_default = function(value) {
  return this.each(function(){
	var default_value = value;
	var clear_on_focus = true;
	if (!default_value) {
		// If no value is specified, the default is whatever is currently
		// set in field but we don't do a clear-on-focus.
		default_value = jQuery(this).val();
		jQuery(this).addClass("default");
		clear_on_focus = false;
	} else if (jQuery(this).val() == "" || jQuery(this).val() == default_value) {
		// Otherwise, if the field is empty, replace it with the default.
		// If the field already has the default text (e.g. navigating back to
		// the page), make sure it has the default class.
		jQuery(this).val(default_value);
		jQuery(this).addClass("default");
	}
	jQuery(this).focus(function() {
		if (jQuery(this).val() == default_value && clear_on_focus)
			jQuery(this).val("");
		jQuery(this).removeClass("default");
	});
	jQuery(this).blur(function() {
		if (clear_on_focus) {
			if (jQuery(this).val() == "") {
				jQuery(this).val(default_value);
				jQuery(this).addClass("default");
			}
		} else {
			if (jQuery(this).val() == default_value) {
				jQuery(this).addClass("default");
			}
		}
	});
  });
};

// Apply the modernization.
if (!Modernizr.input.placeholder) {
	$(function() {
		$('input[placeholder]').each(function() {
			if (this.type == "password") return;
			$(this).input_default(this.getAttribute('placeholder'));
		});
	});
}


function clear_default_fields(form) {
	for (var i = 0; i < form.elements.length; i++) {
		if ($(form.elements[i]).hasClass('default'))
			$(form.elements[i]).val('');
	}
};

// This provides a delayed keyup event that fires once
// even if there are multiple keyup events between the
// first and the time the event handler is called.
jQuery.fn.keyup_delayed = function(callback, delay) {
  if (!delay) delay = 500;
  return this.each(function(){
	var last_press = null;
	jQuery(this).keyup(function() {
		last_press = (new Date()).getTime();
		jQuery(this).delay(delay);
		jQuery(this).queue(function(next) { if (last_press != null && ((new Date()).getTime() - last_press > delay*.75)) { callback(); last_press = null; } next(); } );
	});
  });
};

// This provides a callback for the enter keypress.
jQuery.fn.keydown_enter = function(callback) {
  return this.each(function(){
	jQuery(this).keydown(function(ev) {
		if (ev.keyCode == '13')
			callback()
	});
  });
};

// Tabs that work via the window hash. Call this method over a node set
// of <a href="#tabname"> elements, and have corresponding <div id="tabname">
// elements. Requires jquery.ba-bbq.min.js.
jQuery.fn.tabs = function(panes, subordinate_to, on_tab_activate) {
	function get_href(elem) {
		// In IE7, getAttribute('href') always returns an absolute URL
		// even if that's not what is specified in the HTML source. Doh.
		var href = elem.getAttribute('href');
		var h = href.indexOf('#');
		if (h >= 0) href = href.substring(h+1); // chop off the hash too
		return href;
	}
	
	var tabs = this;
	var default_tab = get_href(tabs[0]);
	
	panes = $(panes);
	
	// make a list of valid hrefs
	var tab_links = { };
	tabs.each(function() { tab_links[get_href(this)] = 1; });
	
	if (subordinate_to)
		subordinate_to += "/";
	else
		subordinate_to = "";
	
	var current_tab = null;
	
	// What happens when the page hash changes?
	function activate_tab(is_initial) {
		var p = location.hash.substring(1);
		
		// for top-level tabs, act on only the top part of the tab structure
		if (subordinate_to == "") p = p.replace(/\/.*/, "");
		
		if (!(p in tab_links)) p = default_tab;
		
		// the event fires twice?
		if (p == current_tab) return;
		current_tab = p;
		
		// get the height of the current tab
		var cur_height = panes.filter(":visible").height();
		
		// activate the new tab pane
		panes.each(function() {
			if (subordinate_to + this.getAttribute('id') == p || this.getAttribute('tab') == p) {
				// Show it immediately if this is on page load, otherwise fade it in fast.
				if (is_initial) $(this).show(); else $(this).fadeIn("fast");
				
				// Set a min-height so that the window height doesn't go down,
				// which can cause the page to scroll up and confuse the user.
				if (cur_height) $(this).css({ "min-height": cur_height + "px" });
				
				if (!is_initial) {
					// Scroll to the tab if we are far away.
					if ( (tabs.offset().top > $(window).scrollTop() + $(window).height()/3) 
						|| (tabs.offset().top < $(window).scrollTop())
						) {
						$("html, body").animate({ scrollTop: tabs.offset().top - $(window).height()/7 });
					}
				}
			}
		});

		// hide the old tab pane
		// Do this after showing the new pane to prevent the window
		// height from decreasing (because no tabs are shown) which
		// could cause the page to scroll up, which would confuse the user.
		panes.each(function() {
			if (!(subordinate_to + this.getAttribute('id') == p || this.getAttribute('tab') == p)) {
				$(this).hide();
			}
		});
		
		// set the link to .active
		tabs.removeClass('active');
		tabs.each(function() {
			if (get_href(this) == p)
				$(this).addClass('active');
		});
		
		// fire callback
		if (on_tab_activate)
			on_tab_activate(current_tab);
	}

	// On first load, load the tab corresponding to the page hash.
	activate_tab(true);
	
	// Register the hash change handler.
	$(window).on("hashchange", function() { activate_tab(false); });
};

// Smart ellipsis.
//
// Truncate text with an ellipsis so that it fits exactly within its
// max-width/max-height CSS properties. Only works on elements that
// contain only text and no child elements.
//
// Also, works well in Chrome but not quite right in FF/IE, although
// the result in presentable.
jQuery.fn.truncate_text = function(callback) {
	var elem = $(this);
	
	// elem's width/height are equal to its max-width/height. Wrap
	// elem in a new div with those dimensions, and remove the
	// max-width/height from elem.
	var w = elem.width();
	var h = elem.height();
	elem.css({ "max-width": "", "max-height": "", "overflow": "" });
	
	var remaining = elem.text();
	var chopped = null;
		
	function do_cut() {
		// Cut words from elem until it fits, or no text is left.
		while (elem.height() > h || elem.width() > w) {
			var idx = remaining.lastIndexOf(" ");
			if (idx <= 0) break;
			
			if (chopped == null) chopped = "";
			chopped = remaining.substring(idx) + chopped;
			remaining = remaining.substring(0, idx);
			elem.text(remaining + " ...");
		}
		
		if (callback)
			callback(remaining, chopped);
	}
	
	do_cut();

	// In FF and IE, the dimensions of the element may change. Perhaps
	// this is due to font loading. So we should repeat once the document
	// is loaded. We should do the ellipsis early to get things layed out
	// as early as possible.
	var w1 = elem.width();
	var h1 = elem.height();
	$(function() {
		// have the dimensions changed?
		if (elem.width() != w1 || elem.height() != h1) {
			// reset text
			elem.text(remaining + (chopped ? chopped : ""));
			
			// re-do ellipsis
			do_cut();
		}
	});
}

/**
 * jQuery.fn.sortElements based on:
 * --------------
 * @author James Padolsey (http://james.padolsey.com)
 * @version 0.11
 * @updated 18-MAR-2010
 * --------------
 * @param Function key_func:
 *   Returns a key, which can be an Array, for an element in the list, on which to sort.
 */
jQuery.fn.sortElements = (function(){
    
    var sort = [].sort;
    
    return function(key_func) {
        
        var placements = this.map(function(){
            
            var sortElement = this,
                parentNode = sortElement.parentNode,
                
                // Since the element itself will change position, we have
                // to have some way of storing it's original position in
                // the DOM. The easiest way is to have a 'flag' node:
                nextSibling = parentNode.insertBefore(
                    document.createTextNode(''),
                    sortElement.nextSibling
                );
            
            return function() {
                
                if (parentNode === this) {
                    throw new Error(
                        "You can't sort elements if any one is a descendant of another."
                    );
                }
                
                // Insert before flag:
                parentNode.insertBefore(this, nextSibling);
                // Remove flag:
                parentNode.removeChild(nextSibling);
                
            };
            
        });
       
       	function comparator(a, b) {
            a = key_func(a);
            b = key_func(b);
            return comparator2(a, b);
       	}
        function comparator2(a, b) {
            if (!$.isArray(a) || !$.isArray(b)) {
            	if (a < b) return -1;
            	if (a > b) return 1;
            	return 0;
            }

            for (var i = 0; i < a.length; i++) {
            	var c = comparator2(a[i], b[i]);
            	if (c != 0) return c;
            }
            return 0;
        }

        return sort.call(this, comparator).each(function(i){
            placements[i].call(this);
        });
        
    };
    
})();

jQuery.fn.moreLess = function() {
	var elem = $(this);
	var id = elem.attr('id');
	var more = $("#" + id + "_more");
	var less = $("#" + id + "_less");
	function show() {
		elem.fadeIn();
		more.hide();
		return false;
	}
	function hide() {
		elem.fadeOut();
		more.show();
		return false;
	}
	more.click(show);
	less.click(hide);
}
