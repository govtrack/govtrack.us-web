var the_segment = "{% if remote_net_house %}House{% elif remote_net_senate %}Senate{% elif remote_net_eop %}EOP{% elif is_dc_local %}DC{% else %}Other{% endif %}";
var cong_dist = {% if congressional_district %}{{congressional_district|safe}}{% else %}null{% endif %};
var cong_dist_mocs = {% if congressional_district_mocs %}{{congressional_district_mocs|safe}}{% else %}null{% endif %};
var is_ad_free = {% if user.userprofile.paid_features.ad_free_life or user.userprofile.paid_features.ad_free_year %}true{% else %}false{% endif %};

