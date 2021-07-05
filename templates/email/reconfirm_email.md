{% extends "email/template" %}
{% block content %}
Hello there,

It's been a while and we want to make sure that you're still there and interested in receiving emails from GovTrack.us.

Please click the link below to confirm that you're still willing and able to receive email from us:

[{{return_url}}]({{return_url}})

Thank you for your help. Your GovTrack account may be deactivated if you do not click the link soon.
{% endblock %}

