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
jQuery.fn.tabs = function(panes, subordinate_to) {
	var tabs = this;
	var default_tab = tabs[0].getAttribute('href');
	
	panes = $(panes);
	
	// make a list of valid hrefs
	var tab_links = { };
	tabs.each(function() { tab_links[this.getAttribute('href')] = 1; });
	
	if (subordinate_to)
		subordinate_to += "/";
	else
		subordinate_to = "";
	
	var current_tab = null;
	
	// What happens when the page hash changes?
	function activate_tab(is_initial) {
		var p = location.hash;
		
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
			if ("#" + subordinate_to + this.getAttribute('id') == p) {
				// Show it immediately if this is on page load, otherwise fade it in fast.
				if (is_initial) $(this).show(); else $(this).fadeIn("fast");
				
				// Set a min-height so that the window height doesn't go down,
				// which can cause the page to scroll up and confuse the user.
				if (cur_height) $(this).css({ "min-height": cur_height + "px" });
			}
		});

		// hide the old tab pane
		// Do this after showing the new pane to prevent the window
		// height from decreasing (because no tabs are shown) which
		// could cause the page to scroll up, which would confuse the user.
		panes.each(function() {
			if ("#" + subordinate_to + this.getAttribute('id') != p) {
				$(this).hide();
			}
		});
		
		// set the link to .active
		tabs.removeClass('active');
		tabs.each(function() {
			if (this.getAttribute('href') == p)
				$(this).addClass('active');
		});
	}

	// On first load, load the tab corresponding to the page hash.
	activate_tab(true);
	
	// Register the hash change handler.
	$(window).on("hashchange", function() { activate_tab(false); });
};


