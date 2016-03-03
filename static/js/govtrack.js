var map_controller = function() {
	var our_google_maps_style = [
	{
		"featureType": "water",
		"stylers": [	{ "visibility": "simplified" }	]
	},{
		"featureType": "transit.station.bus",
		"stylers": [	{ "visibility": "off" }	]
	},{
		"featureType": "poi.business",
		"stylers": [	{ "visibility": "off" }	]
	},{
		"featureType": "landscape.man_made",
		"stylers": [	{ "visibility": "off" }	]
	},{
		"featureType": "landscape.natural",
		"stylers": [	{ "lightness": 100 } ]
	},{
		"featureType": "administrative.province",
		"elementType": "geometry.stroke",
		"stylers": [	{ "invert_lightness": true } ]
	},{
		"featureType": "poi.park",
		"elementType": "geometry.fill",
		"stylers": [	{ "visibility": "off" } ]
	} ];

    var baseurl = "https://gis.govtrack.us";

	var map = null;

	var current_layer = null;
	function init(element, state, district, options) {
		// what layer?
		current_layer = "cd-2014";
		function zeropad(number, length) {
		    var ret = '' + number;
		    while (ret.length < length)
		        ret = '0' + ret;
		    return ret;
		}
		if (state && district) current_layer += "/" + state.toLowerCase() + "-" + zeropad(district, 2);

		// set additional map options
		options["mapTypeId"] = google.maps.MapTypeId.ROADMAP;
		options["styles"] = our_google_maps_style;
		options["panControl"] = false;
		options["zoomControl"] = true;
		options["mapTypeControl"] = false;
		options["scaleControl"] = true;
		options["streetViewControl"] = false;

		// initialize map
		map = new google.maps.Map(element, options);

		// controls
		map.controls[google.maps.ControlPosition.TOP_RIGHT].push($('#fullscreen')[0]);

		// show our overlay
		createDistrictsOverlay(current_layer);
	}
	
	/**************************************/
	var tilesizeshift = 1; // 0=256, 1=use 512px tiles instead of 256
	
	// Use PNG or GIF tiles? IE8 and earlier don't support transparent PNGs properly,
	// so use opaque GIF tiles but set the transparency on the map layer appropriately.
	var tileimgformat = 'png';
	if (navigator.appName == 'Microsoft Internet Explorer' && new RegExp("MSIE [678]").exec(navigator.userAgent)) tileimgformat = 'gif';
	
	function createDistrictsOverlay(layer) {
		var tileimgsize = 256 << tilesizeshift;
	
		// Apply the map layer.
		var overlay = new google.maps.ImageMapType({
		  getTileUrl: function(coord, zoom) {
			  return baseurl + "/map/tiles/" + layer + "/" + (zoom-tilesizeshift) + "/" + coord.x + "/" + coord.y + "." + tileimgformat + "?size=" + tileimgsize + (tileimgformat == "png" ? "" : "&features=outline,label");
		  },
		  tileSize: new google.maps.Size(tileimgsize, tileimgsize),
		  isPng: tileimgformat == "png",
		  minZoom: 3,
		  maxZoom: 28,
		  opacity: tileimgformat == "png" ? .85 : .65
		});
		
		map.overlayMapTypes.clear();
		map.overlayMapTypes.insertAt(0, overlay);
		
		// For IE8 and earlier, the layer above only applies outlines and labels --- at high opacity.
		// Apply a second layer for the boundary fill color --- at low opacity.
		if (tileimgformat != "png") {
			var overlay2 = new google.maps.ImageMapType({
			  getTileUrl: function(coord, zoom) {
				  return baseurl + "/map/tiles/" + layer + "/" + (zoom-tilesizeshift) + "/" + coord.x + "/" + coord.y + "." + tileimgformat + "?size=" + tileimgsize + (tileimgformat == "png" ? "" : "&features=fill");
			  },
			  tileSize: new google.maps.Size(tileimgsize, tileimgsize),
			  isPng: false,
			  minZoom: 3,
			  maxZoom: 28,
			  opacity: .15
			});
			
			map.overlayMapTypes.insertAt(0, overlay2);
		}
	}

	return {
		init: init,
		map: map,
		setCenter: function(latlng) { map.setCenter(latlng); },
		setZoom: function(zoom) { map.setZoom(zoom); },
		addControl: function(where, elem) { map.controls[where].push(elem); },
		addMarker: function(location) {
			var marker = new google.maps.Marker({
				map: map, 
				position: location
			});
			return marker;
		},
		onBoundsChanged: function(callback) {
			google.maps.event.addListener(map, "bounds_changed", function() {
				callback(map.getBounds());
			});
		},
		onMouseMoveHit: function(hit, loading) {
			if (typeof getTileCoordinate == "undefined") return; // local debugging

			google.maps.event.addListener(map, "mousemove", function(e) {
				loading();
				map_hit_test(
					getTileCoordinate(e.latLng, map),
					current_layer.split("/")[0], // when looking at a district, still do hit testing on whole country
					null,
					hit,
					baseurl);
			});	
		}
	};
};

function moc_record_matches_user(moc, cong_dist, cong_dist_mocs) {
	if (moc == null || moc === "" || cong_dist == null)
		return null;
	if (moc.id in cong_dist_mocs)
		return "Your " + moc.title + " " + moc.name + " ";
	if (moc.state == cong_dist.state && moc.district == null)
		return "Your former " + moc.title + " " + moc.name + " ";
	return null;
}

function submit_leg_services_teaser() {
	$.ajax({
		type: "POST",
		url: "/_ajax/leg-services-teaser",
		data: $('#leg-services-teaser form').serializeArray(),
		success: function(res) {
			alert(res.message);
			if (res.status == "ok")
				$('#leg-services-teaser').modal('hide');
		}
	})
}
