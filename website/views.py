# -*- coding: utf-8 -*-
from django.http import Http404, HttpResponse, HttpResponseRedirect, HttpResponseBadRequest
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.conf import settings

from common.decorators import render_to

from twostream.decorators import anonymous_view
from registration.helpers import json_response

from website.models import UserProfile, BlogPost
from events.models import Feed
import us

import re, json
from datetime import datetime, timedelta, time, date

@anonymous_view
@render_to('website/index.html')
def index(request):
    # Fetch subject areas for drop-down.
    from bill.views import subject_choices
    bill_subject_areas = subject_choices()

    post_groups = []
    MAX_PER_GROUP = 3

    # Get our latest blog post.
    from .models import BlogPost
    latest_blog_post = BlogPost.objects\
        .filter(published=True)\
        .exclude(id=434)\
        .order_by('-created')\
        .first()

    # Recent votes.
    from vote.models import Vote
    recent_votes = Vote.objects\
        .filter(created__gt=datetime.now() - timedelta(days = 7))\
        .filter(category__in=Vote.MAJOR_CATEGORIES)\
        .order_by('-created')\
        [0:5]
    if len(recent_votes) > 0:
        post_groups.append({
            "title": "Recent Major Votes",
            "posts": [{
                "image_url": vote.get_thumbnail_url(),
                "title": vote.question,
                "url": vote.get_absolute_url(),
                "published": vote.created.strftime("%x"),
            } for vote in recent_votes],
            "links": [("/congress/votes", "All Votes")],
        })

    # Legislation coming up. Sadly this is usually the least interesting.
    from django.db.models import F
    from django.conf import settings
    from bill.models import Bill
    dhg_bills = Bill.objects.filter(congress=settings.CURRENT_CONGRESS, docs_house_gov_postdate__gt=datetime.now() - timedelta(days=10)).filter(docs_house_gov_postdate__gt=F('current_status_date'))
    sfs_bills = Bill.objects.filter(congress=settings.CURRENT_CONGRESS, senate_floor_schedule_postdate__gt=datetime.now() - timedelta(days=5)).filter(senate_floor_schedule_postdate__gt=F('current_status_date'))
    coming_up = list((dhg_bills | sfs_bills))
    coming_up.sort(key = lambda bill : -bill.proscore())
    if len(coming_up) > 0:
        post_groups.append({
            "title": "Legislation Coming Up",
            "posts": [{
                "image_url": bill.get_thumbnail_url_ex(),
                "title": bill.title,
                "url": bill.get_absolute_url(),
                "published": "week of " + bill.scheduled_consideration_date.strftime("%x"),
            } for bill in coming_up[0:6]],
            "links": [("/congress/bills", "Search and Track Legislation")],
        })

    # Trending feeds.
    trending_feeds = [Feed.objects.get(id=f) for f in Feed.get_trending_feeds()[0:6]]
    if len(trending_feeds) > 0:
        post_groups.append({
            "title": "Trending",
            "posts": [{
                "title": feed.title,
                "url": feed.link,
            } for feed in trending_feeds ],
            "compact": True
        })

    return {
        'bill_subject_areas': bill_subject_areas, # for the action area below the splash
        'latest_blog_post': latest_blog_post,
        'post_groups': post_groups,
        }

@anonymous_view
def staticpage(request, pagename):
    if pagename == "developers": pagename = "developers/index"
    
    ctx = { 'pagename': pagename }
    
    return render(request, 'website/' + pagename + '.html', ctx)

def get_blog_items():
    # c/o http://stackoverflow.com/questions/1208916/decoding-html-entities-with-python
    import re
    def _callback(matches):
        id = matches.group(1)
        try:
           return chr(int(id))
        except:
           return id
    def decode_unicode_references(data):
        return re.sub("&#(\d+)(;|(?=\s))", _callback, data)

    # Fetch from Atom feed.
    import feedparser
    feed = feedparser.parse("https://govtracknews.wordpress.com/feed/atom/")

    from django.template.defaultfilters import truncatewords, striptags

    # Yield dicts.
    for i, entry in enumerate(feed["entries"]):
        if i >= 2: return
        yield {
            "url": entry.link,
            "title": decode_unicode_references(entry.title),
            "published": datetime(*entry.updated_parsed[0:6]),
            "snippet": truncatewords(striptags(decode_unicode_references(entry.content[0].value)), 30)
        }

def congress_home(request):
    return HttpResponseRedirect("/start")

def do_site_search(q, bill_match_mode=None, request=None):
    if q.strip() == "":
        return []
    
    results = []
    
    # Search bills
    from bill.models import Bill
    from vote.models import Vote
    if "pass" in q or "fail" in q or "vote" in q:
        results.append({
            "title": "Tracking Federal Legislation",
            "href": "/start",
            "noun": "feeds",
            "results": [
                {"href": f.link,
                 "label": f.title,
                 "obj": f,
                 "feed": f,
                 "secondary": False }
                for f in (
                    Bill.EnactedBillsFeed(), Bill.ActiveBillsExceptIntroductionsFeed(), Bill.ComingUpFeed(), Vote.AllVotesFeed(),
                    )
                ]
            })
    
    from haystack.query import SearchQuerySet
    from events.models import Feed

    # Search legislators
    from person.models import RoleType
    sqs = SearchQuerySet().using("person")\
        .filter(
            indexed_model_name__in=["Person"],
            all_role_types__in=(RoleType.representative, RoleType.senator),
            content=q)
    if 'XapianEngine' not in settings.HAYSTACK_CONNECTIONS['person']['ENGINE']:
        # Xapian doesn't provide a 'score' so we can't do this when debugging.
        sqs = sqs.order_by('-is_currently_serving', '-score')
    results.append({
        "title": "Members of Congress",
        "href": "/congress/members/all",
        "qsarg": "name",
        "noun": "Members of Congress",
        "results": [
            {"href": p.object.get_absolute_url(),
             "label": p.object.name,
             "obj": p.object,
             "feed": p.object.get_feed(),
             "secondary": p.object.get_current_role() == None }
            for p in sqs[0:9]]
        })

    # Search non-legislator presidents and vice presidents
    sqs = SearchQuerySet().using("person")\
        .filter(
            indexed_model_name__in=["Person"],
            content=q)\
        .exclude(all_role_types__in=(RoleType.representative, RoleType.senator))
    if 'XapianEngine' not in settings.HAYSTACK_CONNECTIONS['person']['ENGINE']:
        # Xapian doesn't provide a 'score' so we can't do this when debugging.
        sqs = sqs.order_by('-is_currently_serving', '-score')
    results.append({
        "title": "Other Presidents and Vice Presidents",
        #"href": "/congress/members/all",
        #"qsarg": "name",
        "noun": "Presidents and Vice Presidents",
        "results": [
            {"href": p.object.get_absolute_url(),
             "label": p.object.name,
             "obj": p.object,
             "feed": p.object.get_feed(),
             "secondary": p.object.get_current_role() == None }
            for p in sqs[0:9]]
        })

    import us
    results.append({
        "title": "States",
        "href": "/congress/members",
        "noun": "states",
        "results": sorted([{"href": "/congress/members/%s" % s, "label": us.statenames[s] }
            for s in us.statenames
            if us.statenames[s].lower().startswith(q.lower())
            ], key=lambda p : p["label"])})
    
    # search committees -- name must contain all of the words in the
    # search query (e.g. "rules committee" should match "committee on rules")
    from committee.models import Committee
    committees_qs = Committee.objects.filter(obsolete=False)
    for word in q.split(" "):
        committees_qs = committees_qs.filter(name__icontains=word)
    results.append({
        "title": "Congressional Committees",
        "href": "/congress/committees",
        "noun": "committees in Congress",
        "results": sorted([
            {"href": c.get_absolute_url(),
             "label": c.fullname,
             "feed": c.get_feed(),
             "obj": c,
             "secondary": c.committee != None}
            for c in committees_qs
            ], key=lambda c : c["label"])
        })
       
    from settings import CURRENT_CONGRESS
    from bill.search import parse_bill_citation
    bill = parse_bill_citation(q, not_exist_ok=True)
    congress = "__ALL__"
    if bill and not bill._state.adding and bill_match_mode == "redirect":
        url = bill.get_absolute_url()
        if request.GET.get("track"): url += "#track"
        return HttpResponseRedirect(url)
    if bill and bill_match_mode == "single":
        # When a bill number matches, just return that bill.
        # Unless we guessed the Congress number, then show recent
        # bills with the same type and number.
        if bill.search_type_flag == "bill-guessed-congress" or bill._state.adding:
            bills = [ { "obj": b }
                      for b in Bill.objects.filter(bill_type=bill.bill_type, number=bill.number)
                                           .order_by('-congress')
                                           [0:5] ]
        else:
            bills = [ { "obj": bill } ]
    else:
        # query Solr w/ the boosted field
        from haystack.inputs import AutoQuery
        from haystack.query import SQ
        q = SearchQuerySet().using("bill").filter(indexed_model_name__in=["Bill"])\
            .filter( SQ(text=AutoQuery(q)) | SQ(text_boosted=AutoQuery(q)) )

        # restrict to current bills if any (at least 10) bills match
        q1 = q.filter(congress=CURRENT_CONGRESS)
        if q1.count() >= 10:
            q = q1
            congress = str(CURRENT_CONGRESS)

        bills = [{ "obj": b.object } for b in q[0:9]]
    for item in bills:
       item.update({"href": item["obj"].get_absolute_url(),
             "label": item["obj"].title,
             "feed": item["obj"].get_feed() if item["obj"].is_alive else None,
             "secondary": item["obj"].congress != CURRENT_CONGRESS })
    results.append({
        "title": "Bills and Resolutions",
        "href": "/congress/bills/browse",
        "qsarg": "congress=%s&text" % congress,
        "noun": "federal bills or resolutions",
        "results": bills})

    # subject terms, but exclude subject terms that look like committee names because
    # that is confusing to also see with committee results
    from bill.models import BillTerm, TermType
    results.append({
        "title": "Subject Areas",
        "href": "/congress/bills",
        "noun": "subject areas",
        "results": [
            {"href": p.get_absolute_url(),
             "label": p.name,
             "obj": p,
             "feed": p.get_feed(),
             "secondary": not p.is_top_term() }
            for p in BillTerm.objects.filter(name__icontains=q, term_type=TermType.new)[0:9]]
        })
    
    # in each group, make sure the secondary results are placed last, but otherwise preserve order
    for grp in results:
        for i, obj in enumerate(grp["results"]):
           obj["index"] = i
        grp["results"].sort(key = lambda o : (o.get("secondary", False), o["index"]))
    
    # sort categories first by whether all results are secondary results, then by number of matches (fewest first, if greater than zero)
    results.sort(key = lambda c : (
        len([d for d in c["results"] if d.get("secondary", False) == False]) == 0,
        len(c["results"]) == 0,
        len(c["results"])))
        
    return results

@render_to('website/search.html')
def search(request):
    r = do_site_search(request.GET.get("q", request.POST.get("q", "")), bill_match_mode="redirect", request=request)
    if not isinstance(r, list): return r
    return { "results": r }

@json_response
def search_autocomplete(request):
    # Although this is POST-y, we want results cached so use GET.

    # Do the search.
    r = do_site_search(request.GET.get("q", ""), bill_match_mode="single")

    # Limit the number of results for each group.
    limit_per_group = 6
    for i, grp in enumerate(r):
       grp["results"] = grp["results"][:limit_per_group]
       limit_per_group = max(int(len(grp["results"]) / 1.5), 1)

    # Remove groups without results.
    r = [g for g in r if g["results"]]

    # Remove non-JSON-able fields.
    for grp in r:
      for item in grp["results"]:
        if "obj" in item: del item["obj"]
        if "feed" in item: del item["feed"]

    return { "result_groups": r }

@render_to('website/your_docket.html')
def your_docket(request):
    from bill.models import Bill
    # Pre-load the user's subscription lists and for each list
    # pre-load the list of bills entered into the list.
    lists = []
    if request.user.is_authenticated:
        lists = request.user.subscription_lists.all()
        for lst in lists:
            lst.bills = []
            for trk in lst.trackers.all():
                try:
                    lst.bills.append( Bill.from_feed(trk) )
                except ValueError:
                    pass
    return { "lists": lists }

@login_required
def update_account_settings(request):
    if request.POST.get("action") == "unsubscribe":
        # Turn off all emails.
        for x in request.user.userprofile().lists_with_email():
            x.email = 0
            x.save()
        p = request.user.userprofile()
        p.massemail = False
        p.save()
        
    if request.POST.get("action") == "posts":
        # Record the unsubscribed categories in userprofile.massemail_options,
        # unless they are all unsubscribed, in which case set userprofile.massemail
        # to False.
        p = request.user.userprofile()
        catsub = request.POST.getlist('postcatsub', '')
        if len(catsub) == 0:
            p.massemail = False
            p.massemail_options = ""
        else:
            # Record the categories not selected.
            p.massemail = True
            massemail_options = [
                "unsubcat:" + cat["key"]
                for cat in p.get_blogpost_categories()
                if cat["key"] not in catsub
            ]
            if request.POST.get("postfreq", "") == "weekly":
                massemail_options.append("postfreq:weekly")
            p.massemail_options = ",".join(massemail_options)
            assert len(p.massemail_options) <= UserProfile._meta.get_field("massemail_options").max_length
        p.save()
        return HttpResponseRedirect("/accounts/lists")
            
    return HttpResponseRedirect("/accounts/profile")

# import function but put here because it's refernced here in urls.py I guess
from website.api import api_overview

@render_to('website/analysis.html')
def analysis_methodology(request):
    from settings import CURRENT_CONGRESS
    from person.models import RoleType
    from bill.models import BillType
    from us import get_congress_dates
    import json
    
    from person.analysis import load_sponsorship_analysis2
    def make_chart_series(role_type):
        data = load_sponsorship_analysis2(CURRENT_CONGRESS, role_type, None)
        if not data: return None
        
        ret = { }
        for p in data["all"]:
            ret.setdefault(p["party"], {
                "type": "party",
                "party": p["party"],
                "data": [],
            })["data"].append({
                "x": float(p["ideology"]),
                "y": float(p["leadership"]),
                "name": p["name"],
            })
        ret = list(ret.values())
        ret.sort(key = lambda s : len(s["data"]), reverse=True)
        
        data = dict(data) # clone before modifying, just in case
        data["series"] = json.dumps(ret)
        
        return data
        
    import bill.prognosis
    import bill.prognosis_model
    import bill.prognosis_model_test
    prognosis_factors = sorted([dict(v) for v in bill.prognosis_model.factors.values()],
        key = lambda m : m["count"], reverse=True)
    for v in prognosis_factors:
        v["factors"] = sorted(v["factors"].values(), key = lambda f : f["regression_beta"], reverse=True)
    prognosis_test = sorted(bill.prognosis_model_test.model_test_results.values(),
        key = lambda v : v["count"], reverse=True)
    
    return {
        "ideology": lambda : { # defer until cache miss
            "house": make_chart_series(RoleType.representative), 
            "senate": make_chart_series(RoleType.senator),
        },
        "current_congress": CURRENT_CONGRESS,
        "prognosis_training_congress": bill.prognosis_model.congress,
        "prognosis_training_congress_dates": get_congress_dates(bill.prognosis_model.congress),
        "prognosis_factors": prognosis_factors,
        "prognosis_test": prognosis_test,
        "prognosis_testing_traincongress": bill.prognosis_model_test.train_congress,
        "prognosis_testing_testcongress": bill.prognosis_model_test.test_congress,
    }

@anonymous_view
@cache_page(60*60 * 1)
@render_to('website/financial_report.html')
def financial_report(request):
    categories = {
        "AD": ("Advertising", "Revenue from advertisements displayed on GovTrack.us."),
        "DATALIC": ("Data Licensing", "Revenue from data licensing agreements."),
        "PRIZE": ("Prize Winnings", "Income from prizes."),
        "INFR": ("IT Infrastruture", "IT systems infrastructure including the web server."),
        "LABOR": ("Contract Labor", "Contract labor, such as developers, designers, and    other staff. (Does not count Josh.)"),
        "OFFICE": ("Office Expenses", "Josh's home office."),
        "TRAVEL": ("Conferences and Travel", "Expenses for conferences and other similar travel."),
        "MARKETING": ("Marketing", "Marketing expenses."),
        "PROF": ("Professional Membership", "Membership in the ACM and other professional organizations."),
        "HEALTHINS": ("Health Insurance", "Josh's health insurance."),
        "LEGAL": ("Legal Fees", "Fees related to business filings and legal advice."),
        "MISC": ("Miscellaneous", "Other expenses."),
        "TAX": ("Taxes", "Federal/state/local taxes (see note below)."),
    }
    
    import csv
    rows = []
    for row in csv.DictReader(open("/home/govtrack/extdata/civic_impulse/financial_report.tsv"), delimiter="\t"):
        year = { "year": row["Year"], "items": [] }
        net = 0.0
        for k, v in row.items():
            if k in categories and v.strip() != "":
                amt = float(v.replace("$", "").replace(",", ""))
                net += amt
                amt = int(round(amt))
                year["items"].append({
                    "category": categories[k][0],
                    "description": categories[k][1],
                    "amount": amt,
                    "unsigned_amount": abs(amt)
                })
        year["items"].sort(key = lambda x : (x["amount"] >= 0, abs(x["amount"])), reverse=True)
        rows.append(year)
        year["net"] = int(round(net))
        year["unsigned_net"] = abs(year["net"])
        
    return { "years": reversed(rows) }
    
@render_to('website/ad_free_start.html')
def go_ad_free_start(request):
    # if there is a checkout session ID in the request session,
    # try to process it in case the webhook failed and get it
    # so we can display a checkout session in progress
    cs = None
    try:
        cs = go_ad_free_complete_checkout_session(request.session["go-ad-free-payment"])
        cs = ("%0.2f" % (cs.amount_total / 100),
              datetime.utcfromtimestamp(cs.created),
              cs.payment_status == "paid")
    except:
        pass
    
    # does the user have an ad-free payment already?
    msi = { }
    if not request.user.is_anonymous:
        msi = request.user.userprofile().get_membership_subscription_info()

    return { "msi": msi, "checkout_session": cs }
    
def go_ad_free_checkout(request):
    try:
        amount = float(request.POST["amount"])
    except:
        return HttpResponseRedirect(reverse(go_ad_free_start))

    # We have different SKUs if the user is/isn't logged in, to avoid confusion,
    # and these SKUs are different in the Stripe test environment.
    if settings.STRIPE_SECRET_KEY.startswith("sk_test_"):
        # Test environment.
        skus = ["prod_RwVgM4oUqy1dGk", "prod_RwVfbypzdrpSuE"] # logged out, logged in
    else:
        # Live environment
        skus = ["prod_RwVghshnIhc4gG", "prod_RwVgXw4hgeen4n"] # logged out, logged in
    descriptions = ["GovTrack.us Tip", "GovTrack.us Ad-Free for One Year"] # logged out, logged in

    if request.user.is_anonymous:
        productid = skus[0]
        description = descriptions[0]
    else:
        productid = skus[1]
        description = descriptions[1]

    import stripe
    try:
      checkout_session = stripe.checkout.Session.create(
        success_url=request.build_absolute_uri(reverse(go_ad_free_start)),
        cancel_url=request.build_absolute_uri(reverse(go_ad_free_start)),
        client_reference_id=("user=" + str(request.user.id)) if not request.user.is_anonymous else None,
        payment_intent_data={ "description": description },
        line_items=[{
          "price_data": { "currency": "USD",
                         "product": productid,
                         "unit_amount": int(amount * 100), # it's in cents
                       },
          "quantity": 1
        }],
        mode="payment",
        customer_email=request.user.email if not request.user.is_anonymous else None,
      )
    except Exception as e:
      raise ValueError("Error creating payment session: " + str(e))

    request.session["go-ad-free-payment"] = checkout_session.id
      
    return HttpResponseRedirect(checkout_session.url)
    
@csrf_exempt
def go_ad_free_webhook(request):
  import stripe

  payload = request.body
  sig_header = request.META['HTTP_STRIPE_SIGNATURE']
  event = None

  try:
    event = stripe.Webhook.construct_event(
      payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
    )
  except ValueError as e:
    return HttpResponse(status=400)
  except stripe.error.SignatureVerificationError as e:
    return HttpResponse(status=400)

  if (
    event['type'] == 'checkout.session.completed'
    or event['type'] == 'checkout.session.async_payment_succeeded'
  ):
    go_ad_free_complete_checkout_session(event['data']['object']['id'])

  return HttpResponse(status=200)

def go_ad_free_complete_checkout_session(session_id):
    import stripe
    checkout_session = stripe.checkout.Session.retrieve(session_id,
        expand=['line_items'])
    if checkout_session.payment_status != 'unpaid' \
      and checkout_session.client_reference_id:

        # Save to user's profile
        from django.contrib.auth.models import User
        user = User.objects.get(id=int(checkout_session.client_reference_id.split("=")[1]))
        prof = user.userprofile()

        from dateutil.relativedelta import relativedelta
        now = datetime.now()
        pfrec = { }
        pfrec["stripe_checkout_session_id"] = checkout_session.id
        pfrec["date"] = now.isoformat()
        expires = now + relativedelta(years=1)
        pfrec["expires"] = expires.isoformat()

        if prof.paid_features == None: prof.paid_features = { }
        prof.paid_features["ad_free"] = pfrec
        prof.save()
    return checkout_session

@anonymous_view
def videos(request, video_id=None):
    return render(request, 'website/videos.html', { "video_id": video_id })


@anonymous_view
def dumprequest(request):
	return HttpResponse(
		"secure=" + repr(request.is_secure()) + "\n"
		+ repr(request),
		content_type="text/plain")

@render_to('website/one_click_unsubscribe.html')
def account_one_click_unsubscribe(request, key):
    ok = UserProfile.one_click_unsubscribe(key)
    return { "ok": ok }

@login_required
@render_to('website/list_positions.html')
def get_user_position_list(request):
    from website.models import UserPosition
    return {
        "positions": UserPosition.objects.filter(user=request.user).order_by('-created'),
    }

@login_required
def update_userposition(request):
    from website.models import UserPosition
    if request.method != "POST": raise HttpResponseBadRequest()

    # just validate
    f = Feed.from_name(request.POST.get("subject", ""))
    f.title

    qs = UserPosition.objects.filter(user=request.user, subject=request.POST["subject"])
    if not request.POST.get("likert") and not request.POST.get("reason"):
        # Nothing to save - delete any existing.
        qs.delete()
    else:
        # Update.
        upos, _ = qs.get_or_create(user=request.user, subject=request.POST["subject"])
        upos.likert = int(request.POST["likert"]) if request.POST.get("likert") else None
        upos.reason = request.POST["reason"]
        upos.save()

    return HttpResponse(json.dumps({ "status": "ok" }), content_type="application/json")

def add_remove_reaction(request):
    from website.models import Reaction
    res = { "status": "error" }
    if request.method == "POST" \
        and request.POST.get("subject") \
        and request.POST.get("mode") in ("-1", "1") \
        and request.POST.get("emoji") in Reaction.EMOJI_CHOICES:

        r, isnew = Reaction.objects.get_or_create(
            subject=request.POST["subject"][:20],
            user=request.user if request.user.is_authenticated else None,
            anon_session_key=Reaction.get_session_key(request) if not request.user.is_authenticated else None,
        )

        if isnew:
            r.extra = {
                "ip": request.META['REMOTE_ADDR'],
            }

        if not isinstance(r.reaction, dict):
            r.reaction = { }
        emojis = set(r.reaction.get("emojis", []))
        if request.POST["mode"] == "1":
            emojis.add(request.POST["emoji"])
        elif request.POST["mode"] == "-1" and request.POST["emoji"] in emojis:
            emojis.remove(request.POST["emoji"])
        r.reaction["emojis"] = sorted(emojis)
        if len(r.reaction["emojis"]) == 0:
            del r.reaction["emojis"]
        if not r.reaction:
            # no data, delete record
            r.delete()
        else:
            # save
            r.save()

    return HttpResponse(json.dumps(res), content_type="application/json")

def dump_reactions(request):
    from django.db.models import Count
    from website.models import Reaction
    from collections import defaultdict, OrderedDict
    from website.models import Bill

    # Get subjects with the most users reacting.
    reactions = Reaction.objects.values_list("subject").annotate(count=Count('subject')).order_by('-count')[0:100]

    # Build ouptut.
    def emojis(subject):
        counts = defaultdict(lambda : 0)
        for r in Reaction.objects.filter(subject=subject):
            for e in (r.reaction or {}).get("emojis", []):
                counts[e] += 1
        return OrderedDict(sorted(counts.items(), key = lambda kv : -kv[1]))
    
    ret = [
        OrderedDict([
            ("subject", r[0]),
            ("title", Bill.from_congressproject_id(r[0][5:]).title),
            ("unique_users", r[1]),
            ("emojis", emojis(r[0])),
        ])
        for r in reactions
    ]
    return HttpResponse(json.dumps(ret, indent=2), content_type="application/json")

misconduct_data = None
def load_misconduct_data():
    global misconduct_data
    if not misconduct_data:
        # Load data.
        import os.path, rtyaml
        if not hasattr(settings, 'MISCONDUCT_DATABASE_PATH'):
            # debugging
            misconduct_data = []
        else:
            misconduct_data = rtyaml.load(open(settings.MISCONDUCT_DATABASE_PATH))

        # Pre-fetch all members then add references to Person instances from numeric IDs.
        from person.models import Person
        people_map = Person.objects.in_bulk(set(entry["person"] for entry in misconduct_data))
        for entry in misconduct_data:
            entry["person"] = people_map[int(entry["person"])]

        for entry in misconduct_data:
            for consequence in entry.get("consequences", []):
                # Pre-render consequence dates.
                if isinstance(consequence.get("date"), (int, str)):
                    if len(str(consequence["date"])) == 4: # year alone
                        consequence["date_rendered"] = str(consequence["date"])
                        consequence["date_year"] = int(consequence["date"])
                    elif len(consequence["date"]) == 7: # YYYY-MM, but it's historical so we can't use strftime directly
                        consequence["date_rendered"] = date(2000, int(consequence["date"][5:7]), 1).strftime("%B") + " " + str(int(consequence["date"][0:4]))
                        consequence["date_year"] = int(consequence["date"][0:4])
                    else:
                        raise ValueError(consequence["date"])
                elif isinstance(consequence.get("date"), date):
                    consequence["date_rendered"] = date(2000, consequence["date"].month, consequence["date"].day).strftime("%b. %d").replace(" 0", " ") + ", " + str(consequence["date"].year)
                    consequence["date_year"] = consequence["date"].year
                else:
                    raise ValueError(consequence["date"])

                # Normalize links to list.
                if isinstance(consequence.get("link"), str):
                    consequence["links"] = [consequence["link"]]
                else:
                    consequence["links"] = consequence.get("link", [])
                consequence["wrap_link"] = (len(consequence["links"]) == 1) and (len(consequence.get("action", "") + consequence.get("text", "")) < 100)

                # Parse tags.
                if "tags" in consequence:
                    consequence["tags"] = set(consequence["tags"].split(" "))
                else:
                    consequence["tags"] = set()

                # Map consequence back to main entry. When plotting by consequence,
                # we may want to know what entry it was for.
                consequence["entry"] = entry


            # Split all tags and percolate consequence tags to the top level.
            if "tags" in entry:
                entry["tags"] = set(entry["tags"].split(" "))
            else:
                entry["tags"] = set()
            for cons in entry["consequences"]:
                entry["tags"] |= cons["tags"]

            # Mark the entry as 'alleged' if no guilty consequence tag (which we've percolated to the top) is present.
            entry["alleged"] = (len(entry["tags"] & misconduct_tags_guilty) == 0)

    return misconduct_data

misconduct_type_tags = [
  ("corruption", "bribery & corruption"),
  ("crime", "other crimes"),
  ("ethics", "ethics violation"),
  ("sexual-harassment-abuse", "sexual harassment & abuse"),
  ("elections", "campaign & elections"),
]
misconduct_consequence_tags = [
  ("expulsion", "expulsion"),
  ("censure", "censure"),
  ("contempt", "contempt of Congress"),
  ("reprimand", "reprimand"),
  ("fined", "fined by House/Senate"),
  ("resignation", "resignation"),
  ("exclusion", "exclusion"),
  ("settlement", "settlement"),
  ("conviction", "conviction in court"),
  ("plea", "pleaded in court"),
]
misconduct_status_tags = [
  ("resolved", "resolved"),
  ("unresolved", "unresolved"),
]
misconduct_tag_filters = misconduct_type_tags + misconduct_consequence_tags + misconduct_status_tags

misconduct_tags_guilty = set(["expulsion", "censure", "contempt", "reprimand", "fined", "exclusion", "conviction", "plea", "confirmation"])

@anonymous_view
@render_to('website/misconduct.html')
def misconduct(request):
    entries = load_misconduct_data()

    import plotly.graph_objs as go
    import plotly.graph_objs.layout as go_layout
    from plotly.offline import plot

    # Break out consequences into their own list.
    consequences = sum((entry['consequences'] for entry in entries), [])
    last_consequence_year = max(cons['date_year'] for cons in consequences)

    # Make a common x-axis of decades starting with the first full year of the Congress,
    # which happens to be an even decade.
    x = [(1790 + 10*x) for x in range(0, (last_consequence_year-1790)//10+1)]
    xlab = [str(year)+'s' for year in x]

    bar_chart_layout = go.Layout(
        barmode='stack',
        margin=go_layout.Margin(l=25,r=20,b=10,t=0,pad=0),
        legend={ "orientation": "h" })

    def make_chart(title, universe, bars, year_of):
        stacks = []
        def decade_of(entry): return year_of(entry) - (year_of(entry) % 10)
        for tag, label in bars:
            y = [
                sum(1
                    for entry in universe
                    if  decade_of(entry) == decade
                    and tag in entry['tags'])
                for decade in x
            ]
            stacks.append(go.Bar(x=xlab, y=y, name=label))
        return {
            "title": title,
            "figure": plot(
                go.Figure(
                    data=stacks,
                    layout=bar_chart_layout),
                output_type="div",
                include_plotlyjs=False,
                show_link=False)
            }

    charts = [
        make_chart(
            title="Types of misconduct and alleged misconduct over time",
            universe=entries,
            bars=misconduct_type_tags,
            year_of=lambda entry : entry['consequences'][0]['date_year'],
        ),
        make_chart(
            title="Consequences of misconduct and alleged misconduct over time",
            universe=consequences,
            bars=misconduct_consequence_tags,
            year_of=lambda entry : entry['date_year'],
        ),
    ]


    return {
        "entries": entries,
        "tags": misconduct_tag_filters,
        "charts": charts,
    }

def user_group_signup(request):
    if request.method != "POST":
        return HttpResponseBadRequest()

    from website.models import UserGroupSignup
    UserGroupSignup.objects.create(
        user=request.user if request.user.is_authenticated() else None,
        email=request.POST.get("email", ""),
        groups=request.POST.get("groups", "")
        )

    return HttpResponse(
        json.dumps({ "status": "ok" }),
        content_type="application/json")

@login_required
def discourse_sso(request):
  # Identity provider for the Discourse.org SSO protocol
  # for our forum at community.govtrack.us. @login_required
  # takes care of redirecting users to the login path. Only
  # after logging in do they end up at this view.
  
  # Validate the signature in the request.
  import hmac
  sig = hmac.new(getattr(settings, 'COMMUNITY_FORUM_SSO_KEY').encode("ascii"),
                 msg=request.GET.get("sso", "").encode("ascii"),
                 digestmod="SHA256")\
                 .hexdigest()
  if sig != request.GET.get("sig"):
    return HttpResponseBadRequest()

  # Decode the payload.
  import base64
  import urllib.parse
  payload = urllib.parse.parse_qs(base64.b64decode(request.GET.get("sso", "").encode("ascii")).decode("ascii"))

  # Add user attributes.
  payload['external_id'] = request.user.id
  payload['email'] = request.user.email

  # Encode the payload to send a redirect back to the forum.
  payload = base64.b64encode(urllib.parse.urlencode(payload, doseq=True).encode("ascii")).decode("ascii")

  # Redirect back to the forum.  
  return HttpResponseRedirect(
    settings.COMMUNITY_FORUM_URL
    + "/session/sso_login?"
    + urllib.parse.urlencode({
        "sso": payload,
        "sig": hmac.new(getattr(settings, 'COMMUNITY_FORUM_SSO_KEY').encode("ascii"),
                        msg=payload.encode("ascii"),
                        digestmod="SHA256")\
                       .hexdigest()
      })
  )

@anonymous_view
@render_to('website/missing_data.html')
def missing_data(request):
    # What data are we missing?

    # What data are we missing about current legislators?

    # Load the pronunciation guide.
    import os.path
    if not hasattr(settings, 'PRONUNCIATION_DATABASE_PATH'):
        pronunciation_guide = None
    else:
        import rtyaml
        pronunciation_guide = { p["id"]["govtrack"]: p for p in rtyaml.load(open(settings.PRONUNCIATION_DATABASE_PATH)) }

    from person.models import Person
    people = { }
    def add_person(p):
        return people.setdefault(p.id, {
            "id": p.id,
            "name": p.sortname,
            "link": p.get_absolute_url(),
        })
    for p in Person.objects.filter(roles__current=True):
        if not p.has_photo():
            add_person(p).update({ "photo": "✘" })
        if not p.birthday:
            add_person(p).update({ "birthday": "✘" })
        if not p.twitterid:
            add_person(p).update({ "twitter": "✘" })
        if pronunciation_guide:
            if p.id not in pronunciation_guide:
                add_person(p).update({ "pronunciation": "✘" })
            # Check that the name in the guide matches the name we display.
            elif pronunciation_guide[p.id]['name'] != p.firstname + " // " + p.lastname:
                add_person(p).update({ "pronunciation": "mismatch" })
    people = sorted(people.values(), key=lambda p : p['name'])

    return {
        "people": people,
    }

@anonymous_view
@render_to('website/covid19.html')
def covid19(request):
    # In order to split the chart by chamber and to track party totals,
    # we need to pass some additional information into the template.
    # Hopefully it remains more efficient to pass only info for legislators
    # listed in the HTML table than for all currently serving members,
    # but we'll also pass current member totals so we can compute the
    # current working membership of each chamber.
    import datetime
    from person.models import PersonRole, RoleType

    # Scan the template for the <table>s that hold information about
    # legislators.
    legislator_data = { }
    with open('templates/website/covid19.html') as f:
        for line in f:
            m = re.search(r"<td>(\d+/\d+/\d+)</td>.*href=\"https://www.govtrack.us/congress/members/\S+/(\d+)", line)
            if m:
                # For each table line with a date and legislator id, record
                # in legislator_data.
                datestr, id = m.groups()
                id = int(id)
                date = datetime.date(int("20"+datestr.split("/")[2]), int(datestr.split("/")[0]), int(datestr.split("/")[1]))
                legislator_data[str(id) + "__" + datestr] = { # key must match how client-side script does a lookup
                    "id": id,
                    "date": date,
                }

    # Fetch all of the PersonRoles that cover the date range of the records.
    current_members = list(PersonRole.objects.filter(
        enddate__gte=min(d['date'] for d in legislator_data.values()),
        startdate__lte=max(d['date'] for d in legislator_data.values()),
    ).select_related("person"))

    # Find the PersonRole for each record.
    for data in legislator_data.values():
        for pr in current_members: # hard to make more efficient because of date check
            if pr.person.id == data['id'] and pr.startdate <= data['date'] <= pr.enddate:
                break
        else:
            raise Exception("Row with unmatched role: " + repr(data))

        # Store data to pass to the template.
        data.update({
            "chamber": "senate" if pr.role_type == RoleType.senator else "house",
            "is_voting": not pr.is_territory, # doesn't affect total for quorum
            "party": pr.get_party_on_date(data['date']),
        })

    # Remove date because it is not JSON serializable.
    for data in legislator_data.values():
        del data['date']

    # To show the current party breakdown of each chamber, count up the total membership.
    # We'll subtract quanrantined members on the client side.
    current_party_totals = { }
    for pr in current_members:
        if pr.is_territory: continue
        chamber = "senate" if pr.role_type == RoleType.senator else "house"
        party = pr.caucus or pr.party
        current_party_totals.setdefault(chamber, {})
        current_party_totals[chamber].setdefault(party, {})
        current_party_totals[chamber][party]["count"] = current_party_totals[chamber][party].get("count", 0) + 1
        if pr.caucus: current_party_totals[chamber][party]["has_independent"] = True
    for chamber in current_party_totals: # list the majority party first
        current_party_totals[chamber] = sorted(current_party_totals[chamber].items(), key=lambda p : -p[1]["count"])

    return {
        "legislator_data": legislator_data,
        "current_party_totals": current_party_totals,
    }


# https://stackoverflow.com/a/44871104
def get_youtube_videos(channel_id, limit=None):
    # See https://stackoverflow.com/questions/14366648/how-can-i-get-a-channel-id-from-youtube
    # for how to get a channel_id. This function returns a list of dicts. The ID of each video
    # can be found in the videoId key. Because the Google API has request limits, the result is
    # cached.

    cache_key = "youtube_{}_{}".format(channel_id, limit)
    cache_hit = cache.get(cache_key)
    if cache_hit is not None:
        if isinstance(cache_hit, str): raise Exception(cache_hit)
        return cache_hit

    import urllib.request
    import urllib.error
    import json
    if not hasattr(settings, 'GOOGLE_API_KEY'): return []
    base_search_url = 'https://www.googleapis.com/youtube/v3/search?'
    first_url = base_search_url + 'channelId={}&key={}&type=video&part=id,snippet&order=date&maxResults=25'.format(channel_id, settings.GOOGLE_API_KEY)
    videos = []
    exception = None
    url = first_url
    while True:
        try:
            inp = urllib.request.urlopen(url)
        except urllib.error.HTTPError as ex:
            exception = ex
            break
        resp = json.load(inp)
        for i in resp['items']:
            v = i['snippet']
            v.update(i['id'])
            videos.append(v)
        try:
            next_page_token = resp['nextPageToken']
            url = first_url + '&pageToken={}'.format(next_page_token)
        except:
            break
        if limit is not None and len(videos) >= limit:
            break

    if exception and not videos:
        # Cache the fact that we got an exception.
        cache.set(cache_key, str(exception), 60*5) # 5 minutes
        raise exception

    cache.set(cache_key, videos, 60*15) # 15 minutes

    return videos

def is_congress_in_session_live():
    # Is Congress in session right now? Cache for 10 minutes
    # because we don't want to hammer servers.
    cache_key = "congress_in_session_live"
    ret = cache.get(cache_key)
    if ret is not None:
        return ret

    import urllib.request
    import urllib.error

    ret = { "house": "unknown", "senate": "unknown", "as_of": datetime.now().isoformat() }

    try:
        r = urllib.request.urlopen("https://in-session.house.gov/").read()
        ret["house"] = "no" if r == b'0' else "yes"
    except:
        ret["house"] = "error"

    try:
        r = urllib.request.urlopen("https://senate.granicus.com/ViewPublisher.php?view_id=20").read()
        ret["senate"] = "no" if b'OFF' in r else "yes"
    except:
        ret["senate"] = "error"

    cache.set(cache_key, ret, 60*10) # 10 minutes
    return ret

def get_user_communities(user, request):
    # A user is granted access to communities according to their
    # email address and connecting IP address.
    from website.models import Community
    communities = set()

    if user:
        if user.is_staff:
            communities.add("capitol-hill")

        if user.email.endswith("@mail.house.gov") or user.email.endswith(".senate.gov"):
            communities.add("capitol-hill")

    if request:
        if getattr(request, "_special_netblock", None)  in ["house", "senate"]:
            communities.add("capitol-hill")

    # Return Community objects.
    communities = set(Community.objects.filter(slug__in=communities))

    return communities

def community_forum_userdata(request, subject):
    communities = get_user_communities(request.user if request.user.is_authenticated else None, request)
    return {
        "html": render_community_forum(request, subject, communities)
    }

def render_community_forum(request, subject, communities):
    # Return all of the messages on boards for the given subject
    # in communities that the user is a member of.

    if not communities:
        return ""

    # Load all of the messages on all of the boards.
    from website.models import CommunityMessageBoard, CommunityMessage
    messages = [
        {
            "community": board.community,
            "messages": list(CommunityMessage.objects.filter(board=board).order_by("-created")),
        }
        for board in CommunityMessageBoard.objects.filter(subject=subject, community__in=communities)
    ]

    # Drop boards without messages (we'll add them back at the end).
    messages = [mm for mm in messages if len(mm["messages"]) > 0]

    # Sort boards by most recent message.
    messages.sort(key = lambda board : board["messages"][0].created, reverse=True)

    # Add communities without messages at the end.
    for community in communities - set(mm["community"] for mm in messages):
        messages.append({ "community": community, "messages": [] })

    # Render.
    from django.template.loader import get_template
    return get_template('website/community_messages.html').render({
        "subject": subject,
        "messages": messages,
        "most_recent_message": CommunityMessage.objects.filter(author=request.user).order_by('-created').first()
          if request.user.is_authenticated else None,
        "request": request,
    })

@login_required
@json_response
def community_forum_post_message(request):
    from website.models import CommunityMessageBoard, CommunityMessage
    from events.models import Feed

    if request.method != "POST": return HttpResponseBadRequest()
    try:
        if "update_message_id" not in request.POST:
            community = int(request.POST["community"])
            subject = request.POST["subject"]

            community = [c for c in get_user_communities(request.user, None)
              if c.id == community][0] # ensure user has / still has access to this community
            #Feed.from_name(subject, must_exist=True) # throws if feed does not exist, in testing we don't have feeds

            update_message = None
        else:
            # Get the message to update (and ensure the ID corresponds to a message the user owns).
            update_message = CommunityMessage.objects.get(id=request.POST["update_message_id"], author=request.user)

            # Check that the user still have access to the board the message is on.
            if update_message.board.community not in get_user_communities(request.user, None): return HttpResponseBadRequest()

        author = request.POST["author"]
        body = request.POST["body"]
    except:
        return HttpResponseBadRequest()

    if not author.strip() or not body.strip():
        return {
            "status": "error",
            "message": "Author and body cannot be empty."
        }

    if update_message is None:
        # Create a new message.
        board, _ = CommunityMessageBoard.objects.get_or_create(community=community, subject=subject)
        try:
            m = CommunityMessage(
                board=board,
                author=request.user,
                author_display=author,
                message=body,
            )
            m.save()
        except:
            # Message is too long?
            return HttpResponseBadRequest()

    elif request.POST.get("delete") == "delete":
        update_message.delete()
        return {
            "status": "ok",
        }

    else:
        # Edit an existing message.
        m = update_message
        m.push_message_state()
        m.author_display = author
        m.message = body
        m.save()

    from django.template.loader import get_template
    return {
        "status": "ok",
        "message": get_template("website/community_messages_message.html").render({ "message": m, "request": request })
    }


@anonymous_view
def posts(request, category=None, id=None, slug=None):
    if not id:
        posts = BlogPost.objects.filter(published=True).order_by('-created')
        if category == None:
            pass
        elif category == "news":
            posts = posts.filter(category="sitenews")
        else:
            raise Http404()
        return render(request, 'website/posts.html', {
            "category": category,
            "posts": posts,
            "categories": BlogPost.get_categories_with_freq() })

    post = get_object_or_404(BlogPost, published=True, id=id)

    if request.path != post.get_absolute_url():
        return redirect(post.get_absolute_url())

    return render(request, 'website/post.html', {
        "post": post,
        "categories": BlogPost.get_categories_with_freq() })

import django.contrib.syndication.views
class BlogPostsFeed(django.contrib.syndication.views.Feed):
    title = "GovTrack.us Posts"
    link = "/posts"
    description = "Upcoming legislation in Congress, recaps, analysis, and site news from GovTrack.us."
    def items(self):
        return BlogPost.objects.order_by('-created')[:15]
    def item_title(self, item):
        return item.title
    def item_description(self, item):
        from django.template.defaultfilters import truncatewords
        return truncatewords(item.body_text(), 150)
    def item_pubdate(self, item):
        return item.created
    def item_updateddate(self, item):
        return item.updated
