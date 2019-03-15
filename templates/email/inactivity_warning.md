{% extends "email/template" %}
{% block content %}
Hello there,

On {{user.date_joined|date}} you created an account on [www.GovTrack.us](https://www.govtrack.us),
and we've been emailing you updates about legislation in the United States Congress (most recently on {{last_email|date}}).
But because you haven't logged in since {{user.last_login|date}}, we think you probably don't want to
hear from us anymore.

**We are deactivating your email updates.**

To restart your updates, just log in to your GovTrack account again at [https://www.govtrack.us/accounts/login](https://www.govtrack.us/accounts/login)
and your emails will resume.

Thanks for using GovTrack!
{% endblock %}
