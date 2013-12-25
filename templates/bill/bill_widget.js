var widgetIdPrefix = "govtrack:widget:bill:{{bill.congress}}:{{bill.bill_type_slug}}{{bill.number}}";

var widgetIframe = document.createElement("iframe");
widgetIframe.id = widgetIdPrefix + ":iframe";
widgetIframe.src = "{% if not debug %}{{SITE_ROOT_URL}}{% else %}//{{request.get_host}}{% endif %}{{bill.get_absolute_url}}/widget.html";
widgetIframe.width = "500";
widgetIframe.height = "200";
widgetIframe.frameBorder = "0";
widgetIframe.seamless = "seamless";

var thisScript = document.scripts.namedItem(widgetIdPrefix + ":script");
thisScript.parentNode.insertBefore(widgetIframe, thisScript);
