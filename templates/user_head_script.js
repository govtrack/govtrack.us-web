var the_segment = "{% if remote_net_house %}House{% elif remote_net_senate %}Senate{% elif remote_net_eop %}EOP{% elif is_dc_local %}DC{% else %}Other{% endif %}";
var is_ad_free = {% if user.userprofile.get_membership_subscription_info.active %}true{% else %}false{% endif %};

