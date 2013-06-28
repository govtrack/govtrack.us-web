var the_segment = "{% if remote_net_house %}House{% elif remote_net_senate %}Senate{% elif is_dc_local %}DC{% else %}Other{% endif %}";
var cong_dist = {% if geolocation %}{{geolocation|safe}}{% else %}null{% endif %};
var is_ad_free = {% if user.userprofile.paid_features.ad_free_life or user.userprofile.paid_features.ad_free_year %}true{% else %}false{% endif %};

