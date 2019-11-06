# -*- coding: utf-8 -*-


from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.forms import Form, CharField, URLField, ChoiceField, Textarea
from django.http import Http404, HttpResponseRedirect

from .models import Stakeholder, Post, BillPosition

@login_required
def list_my_stakeholders(request):
    return render(request, "stakeholder/index.html", {
      "stakeholders": Stakeholder.objects.filter(admins=request.user).order_by('name', 'created'),
    })

@login_required
def new_stakeholder_post(request):
    from bill.models import Bill
    related_bill = None
    if request.GET.get('bill'):
      related_bill = Bill.from_congressproject_id(request.GET['bill'])

    user_admin_of_stakeholders = request.user.stakeholder_set.all()

    class NewStakehoderForm(Form):
      if not user_admin_of_stakeholders:
        organization_name = CharField()
        organization_website = URLField(initial="http://")
        twitter_account = CharField(initial="@", required=False)
      else:
        organization = ChoiceField(choices=[(s.id, s.name) for s in user_admin_of_stakeholders],
          label="Your organization")
      if related_bill:
        position = ChoiceField(choices=[(None, '(choose)'), (1, "Support"), (0, "Neutral"), (-1, "Oppose")], required=True,
          label="Your organization's position on " + related_bill.display_number)
        position_statement_link = URLField(required=True,
          label="Link to webpage or PDF containing a position statement about " + related_bill.display_number)
        position_statement_content = CharField(required=True, widget=Textarea,
          label="Paste the text of your position statement about " + related_bill.display_number)

    if request.method == "GET":
        form = NewStakehoderForm()
    else: # POST
        form = NewStakehoderForm(request.POST)
        if form.is_valid():
            if not user_admin_of_stakeholders:
              # Create a new un-verified Stakeholder object.
              stk = Stakeholder()
              stk.name = form.cleaned_data['organization_name']
              stk.website = form.cleaned_data['organization_website'] or None
              stk.twitter_handle = form.cleaned_data['twitter_account'].lstrip("@") or None
              stk.save()

              # Make this user an admin.
              stk.admins.add(request.user)
            else:
              # Get an existing Stakeholder that they are the admin of.
              stk = get_object_or_404(Stakeholder, id=form.cleaned_data['organization'])
              if request.user not in stk.admins.all():
                # Invalid. Get out of here.
                return HttpResponseRedirect(stk.get_absolute_url())

            # Create a new post if this page is for a related bill and a position,
            # link, or statement are provided.
            if related_bill and (form.cleaned_data['position'] != '' or form.cleaned_data['position_statement_link'] or form.cleaned_data['position_statement_content']):
              # Create a new Post object.
              post = Post()
              post.stakeholder = stk
              if form.cleaned_data['position_statement_link'] or form.cleaned_data['position_statement_content']:
                post.post_type = 1 # summary
                post.link = (form.cleaned_data['position_statement_link'] or None)
                post.content = (form.cleaned_data['position_statement_content'] or None)
              else:
                post.post_type = 0 # positions only
              post.save()

              # Attach a BillPosition to the Post.
              bp = BillPosition()
              bp.post = post
              bp.bill = related_bill
              if form.cleaned_data['position'] != '':
                bp.position = int(form.cleaned_data['position'])
              bp.save()

            # Go view it.
            return HttpResponseRedirect(stk.get_absolute_url())

    return render(request, "stakeholder/new.html", {
      "form": form,
      "related_bill": related_bill,
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

    # Get the Posts. Return one Post for non-positions-only posts,
    # and explode positions-only posts into a cloned Post per position.
    posts = []
    posts.extend(Post.objects.filter(stakeholder=stakeholder).exclude(post_type=0))
    for p in Post.objects.filter(stakeholder=stakeholder, post_type=0):
      for bp in p.bill_positions.all():
        p = Post(
          id=p.id,
          created=bp.created,
        )
        posts.append(p)
    posts.sort(key = lambda p : p.created)

    # Render.
    return render(request,
        "stakeholder/view.html", {
        "stakeholder": stakeholder,
        "is_admin": is_admin,
        "instant_verification_status": instant_verification_status,
        "posts": posts,
    })
