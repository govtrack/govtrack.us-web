# -*- coding: utf-8 -*-
from django.http import Http404, HttpResponse, HttpResponseRedirect, HttpResponseBadRequest
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from django.contrib.auth.decorators import login_required
from django.conf import settings

from common.decorators import render_to

from twostream.decorators import anonymous_view
from registration.helpers import json_response

from website.models import UserProfile, MediumPost
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

    # Fetch our Medium posts for summaries and features.
    from website.models import MediumPost
    post_groups.append({
        "title": "What We're Watching",
        "posts": MediumPost.objects.order_by('-published')[0:3],
        "link": "/events/govtrack-insider",
        "link_text": "Subscribe to all GovTrack Insider articles",
    })

    # legislation coming up
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
            } for bill in coming_up[0:3]],
            "link": "/congress/bills",
            "link_text": "View All",
        })

    # trending feeds
    trending_feeds = [Feed.objects.get(id=f) for f in Feed.get_trending_feeds()[0:6]]
    if len(trending_feeds) > 0:
        post_groups.append({
            "title": "Trending",
            "posts": [{
                "title": feed.title,
                "url": feed.link,
            } for feed in trending_feeds
        ]})


    from person.models import Person
    from vote.models import Vote
    return {
        # for the action area below the splash
        'bill_subject_areas': bill_subject_areas,

        # for the highlights blocks
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

def do_site_search(q, allow_redirect=False, request=None):
    if q.strip() == "":
        return []
    
    results = []
    
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
    bill = parse_bill_citation(q)
    congress = "__ALL__"
    if not bill or not allow_redirect:
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

        bills = [\
            {"href": b.object.get_absolute_url(),
             "label": b.object.title,
             "obj": b.object,
             "feed": b.object.get_feed() if b.object.is_alive else None,
             "secondary": b.object.congress != CURRENT_CONGRESS }
            for b in q[0:9]]
    else:
        url = bill.get_absolute_url()
        if request.GET.get("track"): url += "#track"
        return HttpResponseRedirect(url)
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
            for p in BillTerm.objects.filter(name__icontains=q, term_type=TermType.new).exclude(name__contains=" Committee on ")[0:9]]
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
    r = do_site_search(request.GET.get("q", request.POST.get("q", "")), allow_redirect=True, request=request)
    if not isinstance(r, list): return r
    return { "results": r }

def push_to_social_media_rss(request):
    import django.contrib.syndication.views
    from events.models import Feed
    from events.templatetags.events_utils import render_event
    import re
    
    feedlist = [Feed.from_name("misc:comingup"), Feed.from_name('misc:enactedbills')]
    
    class DjangoFeed(django.contrib.syndication.views.Feed):
        title = "GovTrack.us Is Tracking Congress"
        link = "/"
        description = "GovTrack tracks the activities of the United States Congress. We push this feed to our Twitter and Facebook accounts."
        
        def items(self):
            events = [render_event(item, feedlist) for item in Feed.get_events_for(feedlist, 25)]
            return [e for e in events if e != None]
            
        def item_title(self, item):
            return re.sub(r"^Legislation ", "", item["type"]) + ": " + item["title"]
        def item_description(self, item):
            return item["body_text"]
        def item_link(self, item):
            return settings.SITE_ROOT_URL + item["url"]# + "?utm_campaign=govtrack_push&utm_source=govtrack_push" 
        def item_guid(self, item):
            return "http://www.govtrack.us/events/guid/" + item["guid"] 
        def item_pubdate(self, item):
            return item["date"] if isinstance(item["date"], datetime) or item["date"] is None else datetime.combine(item["date"], time.min)
            
    return DjangoFeed()(request)


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
        
    if request.POST.get("action") == "massemail":
		# Toggle.
        p = request.user.userprofile()
        p.massemail = not p.massemail
        p.save()
            
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
    # just show the go-ad-free page.
    
    # does the user have an ad-free payment already?
    msi = { }
    if not request.user.is_anonymous:
        msi = request.user.userprofile().get_membership_subscription_info()

    # or did the user make an anonymous payment?
    from website.models import PayPalPayment
    p = None
    try:
        p = PayPalPayment.objects.get(paypal_id=request.session["go-ad-free-payment"])
    except:
        pass
    return { "msi": msi, "anonymous_payment": p }
    
def go_ad_free_redirect(request):
    # create a Payment and redirect to the approval step, and track this
    try:
        amount = float(request.POST["amount"])
    except:
        return HttpResponseRedirect(reverse(go_ad_free_start))


    import paypalrestsdk

    sandbox = ""
    if paypalrestsdk.api.default().mode == "sandbox":
        sandbox = "-sandbox"

    # slightly different SKU if the user is/isn't logged in
    if request.user.is_anonymous:
        item = {
            "name": "Support GovTrack.us (%.02d)" % amount,
            "sku": "govtrack-tip" + sandbox,
        }
        description = "Thank you for supporting GovTrack.us%s!" % sandbox
    else:
        item = {
            "name": "Ad-Free GovTrack.us for 1 Year (%.02d)" % amount,
            "sku": "govtrack-ad-free-for-year" + sandbox,
        }
        description = "Ad-Free%s: GovTrack.us is ad-free for a year while you're logged in." % sandbox

    item.update({
        "price": "%.02f" % amount,
        "currency": "USD",
        "quantity": 1,
    })
    
    payment = paypalrestsdk.Payment({
      "intent": "sale",
      "payer": { "payment_method": "paypal" },
      "transactions": [{
        "item_list": {
          "items": [item]
            },
          "amount": {
            "total": item["price"],
            "currency": item["currency"],
          },
          "description": description }],
      "redirect_urls": {
        "return_url": request.build_absolute_uri(reverse(go_ad_free_finish)),
        "cancel_url": request.build_absolute_uri(reverse(go_ad_free_start)),
      },
    })
    
    if not payment.create():
      raise ValueError("Error creating PayPal.Payment: " + repr(payment.error))
      
    request.session["paypal-payment-to-execute"] = payment.id

    from website.models import PayPalPayment
    rec = PayPalPayment(
        paypal_id=payment.id,
        user=request.user if not request.user.is_anonymous else None,
        response_data=payment.to_dict(),
        notes=item["name"])
    rec.save()
  
    for link in payment.links:
        if link.method == "REDIRECT":
            return HttpResponseRedirect(link.href)
    else:
        raise ValueError("No redirect in PayPal.Payment: " + payment.id)
    
def go_ad_free_finish(request):
    from website.models import PayPalPayment
    (payment, rec) = PayPalPayment.execute(request)

    if rec.user:
        prof = rec.user.userprofile()

        try:
            # Update the user profile.
            if prof.paid_features == None: prof.paid_features = { }
            prof.paid_features["ad_free_year"] = (payment.id, None)
            prof.save()
          
        except Exception as e:
            raise ValueError(str(e) + " while processing " + payment.id)

    # Send user back to the start.
    request.session["go-ad-free-payment"] = payment.id
    return HttpResponseRedirect(reverse(go_ad_free_start))
 

@anonymous_view
def videos(request, video_id=None):
    return render(request, 'website/videos.html', { "video_id": video_id })


def set_district(request):
    try:
        state = request.POST["state"]
        if state != "XX" and state not in us.statenames: raise Exception()
        district = int(request.POST["district"])
    except:
        return HttpResponseBadRequest()

    # Who represents?
    from person.models import Person
    mocs = None
    if state != "XX":
        mocs = [p.id for p in Person.from_state_and_district(state, district)]

    # Form response.
    response = HttpResponse(
        json.dumps({ "status": "ok", "mocs": mocs }),
        content_type="application/json")

    if request.user.is_authenticated:
        # Save to database.
        prof = request.user.userprofile()
        prof.congressionaldistrict = "%s%02d" % (state, district)
        prof.save()
    else:
        # Save in cookie.
        response.set_cookie("cong_dist", json.dumps({ "state": state, "district": district }),
            max_age=60*60*24*21)

    return response

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

@anonymous_view
def medium_post_redirector(request, id):
    post = get_object_or_404(MediumPost, id=id)
    return HttpResponseRedirect(post.url)

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
            subject=request.POST["subject"],
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

def dump_sousveillance(request):
    from datetime import datetime, timedelta
    from website.models import Sousveillance
    from website.middleware import is_ip_in_any_range, HOUSE_NET_RANGES, SENATE_NET_RANGES, EOP_NET_RANGES
    import re
    import urllib.request, urllib.parse, urllib.error
    import user_agents

    def get_netblock_label(ip):
        if is_ip_in_any_range(ip, HOUSE_NET_RANGES): return "House"
        if is_ip_in_any_range(ip, SENATE_NET_RANGES): return "Senate"
        if is_ip_in_any_range(ip, EOP_NET_RANGES): return "WH"
    
    # get hits in the time period
    records = Sousveillance.objects\
      .order_by('-when')\
      [0:60]
    def format_record(r, recursive):
      path = r.req["path"]
      if "twostream" in path:
        try:
            path = r.req["referrer"].replace("https://www.govtrack.us", "")
        except:
            pass
      if "?" in path: path = path[:path.index("?")] # ensure no qsargs
      if r.req.get("query"): path += "?" + urllib.parse.urlencode({ k.encode("utf8"): v.encode("utf8") for k,v in list(r.req["query"].items()) })

      if r.req['agent']:
          ua = str(user_agents.parse(r.req['agent']))
          if ua == "Other / Other / Other": ua = "bot"
          ua = re.sub(r"(\d+)(\.[\d\.]+)", r"\1", ua) # remove minor version numbers
      else:
          ua = "unknown"

      ret = {
        "reqid": r.id,
        "when": r.when.strftime("%b %-d, %Y %-I:%M:%S %p"),
        "netblock": get_netblock_label(r.req['ip']) if r.req['ip'] else None,
        "path": path,
        "query": r.req.get('query', {}),
        "ua": ua,
      }
      if recursive:
          ret["netblock"] = ", ".join(sorted(set( get_netblock_label(rr.req["ip"]) for rr in Sousveillance.objects.filter(subject=r.subject) if rr.req["ip"] )))
          ret["recent"] = [format_record(rr, False) for rr in Sousveillance.objects.filter(subject=r.subject, id__lt=r.id).order_by('-when')[0:15]]
      return ret
    records = [
      format_record(r, True)
      for r in records
    ]
    return HttpResponse(json.dumps(records, indent=2), content_type="application/json")
dump_sousveillance.max_age = 30
dump_sousveillance = anonymous_view(dump_sousveillance)

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
  ("reprimand", "reprimand"),
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

misconduct_tags_guilty = set(["expulsion", "censure", "reprimand", "exclusion", "conviction", "plea"])

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
    from person.analysis import load_scorecards_for
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
        if not load_scorecards_for(p):
            # new legislators won't have scorecards for a while
            add_person(p).update({ "scorecards": "✘" })
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
            m = re.search(r"<td>(\d/\d+/\d+)</td>.*href=\"https://www.govtrack.us/congress/members/\S+/(\d+)", line)
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
            raise Exception("Row with unmatched role: " + repr(line))

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

