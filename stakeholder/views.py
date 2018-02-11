# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.forms import Form, CharField, URLField
from django.http import Http404, HttpResponseRedirect

from .models import Stakeholder

@login_required
def new_stakeholder(request):
    class NewStakehoderForm(Form):
      organization_name = CharField()
      website = URLField(initial="http://")
      twitter_name = CharField(initial="@", required=False)

    if request.method == "GET":
      return render(request, "stakeholder/new.html", {
        "form": NewStakehoderForm()
      })
    else:
        form = NewStakehoderForm(request.POST)
        if form.is_valid():
            # Create a new un-verified Stakeholder object.
            stk = Stakeholder()
            stk.name = form.cleaned_data['organization_name']
            stk.website = form.cleaned_data['website'] or None
            stk.twitter_handle = form.cleaned_data['twitter_name'].lstrip("@") or None
            stk.save()

            # Make this user an admin.
            stk.admins.add(request.user)

            # Go view it.
            return HttpResponseRedirect(stk.get_absolute_url())
        return render(request,
            "stakeholder/new.html", {
            "form": form,
        })


def view_stakeholder(request, id):
    # Get the stakeholder.
    stakeholder = get_object_or_404(Stakeholder, id=id)

    # Redirect to canonical URL.
    if request.path != stakeholder.get_absolute_url():
      return HttpResponseRedirect(stakeholder.get_absolute_url)

    # If not verified, then require the user to be an admin.
    is_admin = request.user in stakeholder.admins.all()
    if not stakeholder.verified and not is_admin:
      return HttpResponseRedirect("/accounts/login?next=" + request.path)

    # Check instant verification status.
    instant_verification_status = None
    if "registration_external_verify" in request.session:
      verif = request.session["registration_external_verify"]
      if verif is None:
        instant_verification_status = "Login failed."
      elif verif["provider"] == "twitter" and stakeholder.twitter_handle and verif["profile"].get("screen_name", "").lower() == stakeholder.twitter_handle.lower():
        if not verif["profile"]["verified"]:
          instant_verification_status = "The Twitter account isn't a verified Twitter account. Instant confirmation only works for verified Twitter accounts."
        else:
          stakeholder.name = verif["profile"]["name"]
          try:
            stakeholder.description = verif["profile"]["description"]
            for entity in verif["profile"]["entities"]["url"]["urls"]:
              if entity["url"] == verif["profile"]["url"]:
                stakeholder.website = entity["expanded_url"]
                break
            stakeholder.twitter_handle = verif["profile"]["screen_name"] # normalize casing
          except:
            # Meh.
            pass
          stakeholder.extra.setdefault("verification_login", {})
          stakeholder.extra["verification_login"][verif["provider"]] = verif
          stakeholder.verified = True
          stakeholder.save()
      else:
        instant_verification_status = "It looks like you logged into a different account. You may need to go to Twitter.com and log out manually first so you can log into a different account. You must log in as @" + stakeholder.twitter_handle + "."
      del request.session["registration_external_verify"]

    # Render.
    return render(request,
        "stakeholder/view.html", {
        "stakeholder": stakeholder,
        "is_admin": is_admin,
        "instant_verification_status": instant_verification_status,
    })
