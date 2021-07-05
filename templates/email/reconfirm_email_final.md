{% extends "email/template" %}
{% block content %}
Hello there,

We recently sent you an email asking you to confirm that you're still able to receive mail from GovTrack.us. This email is to let you know that your GovTrack account has been deactivated since you did not click the link in the email.

But don't fret. If you just misssed the email, you can re-activate your account by clicking the link below:

[{{return_url}}]({{return_url}})

Thank you for your help keeping our lists up to date.
{% endblock %}

