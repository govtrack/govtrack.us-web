// Auto-size textareas as the user enters input.
jQuery.fn.input_autosize = function() {
  var resizer = function(elem, c) {
	var val = jQuery(elem).val();
	if (elem.nodeName.toUpperCase() == "TEXTAREA") {
		var numlines = 1;
		var nchars = 0;
		for (var i = 0; i < val.length; i++) {
			if (val.charAt(i) == '\n') { numlines++; nchars = 0; }
			if (nchars++ == 80) { numlines++; nchars = 0; } // approximate wrap?
		}
		if (c == 13) numlines++;
		if (numlines < 3) numlines = 3; // minimum size for a textarea that looks ok
		jQuery(elem).attr('rows', numlines);
	}
  }
  return this.each(function(){
	jQuery(this).keydown(function(c) { resizer(this, c.which); });
	jQuery(this).bind('paste', function(e) { resizer(this, 0); }); // IE only?
	jQuery(this).bind('cut', function(e) { resizer(this, 0); }); // IE only?
	jQuery(this).blur(function() { resizer(this, 0); }); // in case we missed a cut/paste
	resizer(this, 0); // resize it immediately
  });
};

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
	} else if (jQuery(this).val() == "") {
		// Otherwise, if the field is empty, replace it with the default.
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

function clear_default_fields(form) {
	for (var i = 0; i < form.elements.length; i++) {
		if ($(form.elements[i]).hasClass('default'))
			$(form.elements[i]).val('');
	}
}

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
}

jQuery.fn.keydown_enter = function(callback) {
  return this.each(function(){
	jQuery(this).keydown(function(ev) {
		if (ev.keyCode == '13')
			callback()
	});
  });
}

jQuery.fn.textchange = function(callback) {
  return this.each(function(){
	jQuery(this).keyup(callback);
	jQuery(this).bind("paste", callback);
	jQuery(this).bind("cut", callback);
  });
}

jQuery.fn.inline_edit = function(callback, createeditor) {
	return this.each(function(){
		var inline = jQuery(this);
		
		if (createeditor) {
			$('<div id="' + this.getAttribute("id") + '_editor" style="display: none">'
				+ ((createeditor == 'textarea' || createeditor == 'tinymce')
					? '<textarea '
					: '<input type="text" ' )
				+ 'id="' + this.getAttribute("id") + '_textarea"/>'
				+ '</div>').insertAfter(inline);
				
			var textarea = $("#" + this.getAttribute("id") + "_textarea");
			textarea.css('font-size', "inherit");
				
			if (createeditor == "input") {
				textarea.css('width', "100%");
				textarea.val(inline.text());
			} else if (createeditor == "textarea") {
				textarea.css('width', inline.css('width'));
				textarea.input_autosize();
				// textareas are normally used when there is some external HTMLizing going on
			} else if (createeditor == "tinymce") {
				textarea.css('width', inline.css('width'));
				tinyMCE.execCommand("mceAddControl", true, this.getAttribute("id") + "_textarea");
			}
		}
		
		var editor = $("#" + this.getAttribute("id") + "_editor");
		var textarea = $("#" + this.getAttribute("id") + "_textarea");
		var editbtn = $("#" + this.getAttribute("id") + "_editbtn");

		var blurfunc = function() {
			if (createeditor == "textarea")
				inline.height(textarea.height());
			editor.hide();
			inline.fadeIn();
			inline.removeClass("inlineedit_active");
			editbtn.fadeIn();
			
			if (createeditor == "input")
				inline.text(textarea.val());
			else if (createeditor == "tinymce")
				inline.html(textarea.val());
			
			if (callback)
				callback(textarea.val(), inline,
					function() {
						inline.height('auto');
					});
		};
		
		inline.addClass("inlineedit");
		inline.click(function() {
			if (inline.hasClass("inlineedit_active"))
				return;
			inline.addClass("inlineedit_active");
			inline.hide();
			editor.show();
			textarea.focus();
			editbtn.fadeOut();
			if (createeditor == "input") {
				textarea.val(inline.text());
			} else if (createeditor == "textarea") {
				// textareas are normally used when there is some external HTMLizing going on
			} else if (createeditor == "tinymce") {
				var mce = tinyMCE.getInstanceById(this.getAttribute("id") + "_textarea");
				mce.setContent(inline.html());
				mce.on_save = function() { blurfunc(); }
			}
		});
		
		if (createeditor != "tinymce")
			textarea.blur(blurfunc);
		if (createeditor == "input")
			textarea.keydown_enter(blurfunc);
	});
};

function enableWhenFormHasData(submitid, fields) {
	updater = function() {
		var hasdata = false;
		for (f in fields)
			if (!$(f).hasClass('default'))
				hasdata = true;
		$(submitid).attr('disabled', hasdata ? '' : '1');
	}
	for (f in fields)
		$(f).keyup(updater);
	updater();
}

function ajaxform(url, postdata, fields, actions) {
	// create copies of postdata and fields so we can modify them
	
	var c = { };
	for (var property in postdata)
		c[property] = postdata[property];
	
	var d = { };
	for (var property in actions)
		d[property] = actions[property];
	
	// add into postdata the resolved value of each field
	//    if fields have a class of default, then null out the value
	//    for checkbox fields, pass 0 or 1.
	
	for (var field in fields) {
		if (fields[field] == "") {
			// ignore
		} else if (typeof fields[field] == "function") {
			v = fields[field]();
			if (v == null) continue;
		} else {
			var n = jQuery(fields[field]);
			var v = n.val()
			if (n.hasClass("default")) continue;
			if (!n[0]) alert("Bad field name " + field);
			if (n[0].nodeName.toLowerCase() == "input" && n[0].getAttribute('type') && n[0].getAttribute('type').toLowerCase() == "checkbox") {
				if (n[0].checked)
					v = "1";
				else
					v = "0";
			}
		}
		c[field] = v;
	}
	
	ajax(url, c, d);
}

function ajax(url, postdata, actions) {
	if (actions == null) actions = {};
	
	// Disable the button while we're processing.
	if (actions.savebutton) {
		if ($('#' + actions.savebutton).attr('disabled')) return;
		$('#' + actions.savebutton).attr('disabled', '1');
	}
	
	// Let the user know we're starting in #statusfield with #statusstart if provided.
	// Normally this shouldn't be used because ajax calls should be fast enough that
	// there is no need to flash a message the user won't have time to read, especially
	// if it's in red and might scare the user.
	if (actions.statusfield && actions.statusstart) {
		$('#' + actions.statusfield).text(actions.statusstart);
		$('#' + actions.statusfield).fadeIn();
	}
	
	$.ajax({ 
		type:"POST",
		url: url,
		data: postdata,
		complete:
			function(res, status) {
				// If we have any per-field status spans, then hide them since we may have
				// put error messages in them from the last round.
				if (postdata && actions.statusfield)
					for (var f in postdata)
						$('#' + actions.statusfield + "_" + f).hide();
				
				// Reset the button so user can try again. Do this before any callbacks
				// in case the callback changes the state.
				if (actions.savebutton)
					$('#' + actions.savebutton).attr('disabled', '');
				if (status != "success" || res.responseText == "")
					res = { status: "generic-failure" };
				else
					res = eval('(' + res.responseText + ')');
				if (res && res.status == "success") {
					if (actions.statusfield) { // display message from server if given
						if (res && res.status != "generic-failure" && res.msg && res.msg != "") {
							$('#' + actions.statusfield).text(res.msg);
							$('#' + actions.statusfield).fadeIn();
						} else if (actions.statussuccess) { // clear status
							$('#' + actions.statusfield).text(actions.statussuccess);
							$('#' + actions.statusfield).fadeIn();
							$('#' + actions.statusfield).delay(1000).fadeOut();
						} else { // clear status
							$('#' + actions.statusfield).text("Finished.");
							$('#' + actions.statusfield).hide(); // don't fade out in case callback wants to show it again --- fade out will keep going
						}
					}
					if (actions.success) // user callback
						actions.success(res);
				} else {
					if (actions.statusfield) {
						if (res && res.byfield) {
							// An error message is given on a field by field basis. The form
							// must have corresponding field #statusfield_field spans for errors.
							for (var field in res.byfield) {
								var f2 = "#" + actions.statusfield + '_' + field;
								$(f2).fadeIn();
								$(f2).text(res.byfield[field]);
							}
							$('#' + actions.statusfield).fadeIn();
							$('#' + actions.statusfield).text("There were errors. Please see above.");
						} else if (res && res.status != "generic-failure" && res.msg && res.msg != "") {
							// If a message was specified, display it. If the message is tied
							// to a field and we have a span for #statusfield_fieldname
							// then put the error message there and display a generic
							// error in the main status field.
							var f2 = actions.statusfield + '_' + (res.field ? res.field : "");
							if (document.getElementById(f2)) { 
								$('#' + actions.statusfield).fadeIn();
								$('#' + actions.statusfield).text("There were errors. Please see above.");
								$('#' + f2).fadeIn();
								$('#' + f2).text(res.msg);
							} else {
								$('#' + actions.statusfield).fadeIn();
								$('#' + actions.statusfield).text(res.msg);
							}
						} else if (actions.statusfail) {
							// No message was provided so use our own message.
							$('#' + actions.statusfield).fadeIn();
							$('#' + actions.statusfield).text(actions.statusfail);
						} else {
							// No message was provided and the caller didn't give a
							// failure message, so display a generic message.
							$('#' + actions.statusfield).fadeIn();
							$('#' + actions.statusfield).text("Could not take action at this time.");
						}
					}
					
					if (actions.failure) // user callback
						actions.failure(res);
				}
			}
	});
}


