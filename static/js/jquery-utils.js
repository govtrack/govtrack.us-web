// Some of my own utilities.

// This provides a callback for the enter keypress.
jQuery.fn.keydown_enter = function(callback) {
  return this.each(function(){
	jQuery(this).keydown(function(ev) {
		if (ev.keyCode == '13')
			callback()
	});
  });
};

// Smart ellipsis.
//
// Truncate text with an ellipsis so that it fits exactly within its
// max-width/max-height CSS properties. Only works on elements that
// contain only text and no child elements.
//
// Also, works well in Chrome but not quite right in FF/IE, although
// the result in presentable.
jQuery.fn.truncate_text = function(callback, before_first_cut) {
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
			
			if (chopped == null) {
				chopped = "";
				if (before_first_cut) {
					before_first_cut();
					if (!(elem.height() > h || elem.width() > w)) break; // that fixed it
				}
			}
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

function parse_qs(qs) {
	// Parse something that looks like a query string into a Javascript
	// object. Based on http://stackoverflow.com/a/2880929/125992.
	var match,
	pl     = /\+/g,  // Regex for replacing addition symbol with a space
	search = /([^&=]+)=?([^&]*)/g,
	decode = function (s) { return decodeURIComponent(s.replace(pl, " ")); },
	ret = {};
	while (match = search.exec(qs)) {
		var key = decode(match[1]);
		var value = decode(match[2]);
		if (key.substring(key.length-2) == '[]') {
			// Special handling for arrays.
			key = key.substring(0, key.length-2);
			value = $.map(value.split(','), decode);
		}
		ret[key] = value;
	}
	return ret;
}
parse_qs.fragment = function() {
	// Helper that parses the window.location.fragment.
	return parse_qs(window.location.hash.substring(1));
}

function form_qs(obj) {
	// Forms a query-string-like string from a Javascript object's keys and values.
	var encode = function (s) { return encodeURIComponent(s).replace(/\%20/g, "+"); };
	var serialize = function(val) {
		// Special handling for arrays.
		if (val instanceof Array) return val.map(encode).join(",")
		return encode(val); // default string conversion
	};
	var format_marker = function(val) {
		if (val instanceof Array) return "[]"
		return "";
	};
	return $.map(obj, function(value, key) { return encode(key)+format_marker(value) + "=" + serialize(value); }).join("&");
}
