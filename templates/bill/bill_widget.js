var widgetIdPrefix = "govtrack:widget:{{bill.noun}}:{{bill.congress}}:{{bill.bill_type_slug}}{{bill.number}}";

var widgetIframe = document.createElement("iframe");
widgetIframe.id = widgetIdPrefix + ":iframe";
widgetIframe.src = "{{bill.get_absolute_url}}/widget.html";
widgetIframe.width = "500";
widgetIframe.height = "300";

var thisScript = document.scripts.namedItem(widgetIdPrefix + ":script");
thisScript.parentNode.insertBefore(widgetIframe, thisScript);
