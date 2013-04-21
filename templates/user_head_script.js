var the_segment = "{% if remote_net_house %}House{% elif remote_net_senate %}Senate{% elif is_dc_local %}DC{% else %}Other{% endif %}";
var near_phoenix = {% if near_phoenix %}true{% else %}false{% endif %};

