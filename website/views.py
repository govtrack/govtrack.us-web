# -*- coding: utf-8 -*-
from django.http import Http404, HttpResponse, HttpResponseRedirect, HttpResponseBadRequest
from django.shortcuts import redirect, get_object_or_404, render_to_response
from django.template import RequestContext
from django.core.urlresolvers import reverse
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from django.contrib.auth.decorators import login_required
from django.conf import settings

from common.decorators import render_to
from common.pagination import paginate

from cache_utils.decorators import cached

from twostream.decorators import anonymous_view
from registration.helpers import json_response

from website.models import UserProfile, MediumPost
from events.models import Feed
import us

import re, json
from datetime import datetime, timedelta, time

@anonymous_view
@render_to('website/index.html')
def index(request):
    blog_feed = cache.get("our_blog_feed")
    if not blog_feed:
        blog_feed = get_blog_items()[0:4]
        cache.set("our_blog_feed", blog_feed, 60*30) # 30 min
    
    events_feed = cache.get("frontpage_events_feed")
    if not events_feed:
        events_feed = Feed.get_events_for([fn for fn in ("misc:activebills2", "misc:billsummaries", "misc:allvotes") if Feed.objects.filter(feedname=fn).exists()], 6)
        cache.set("frontpage_events_feed", events_feed, 60*15) # 15 minutes

    from bill.views import subject_choices
    bill_subject_areas = subject_choices()

    return {
        'events': events_feed,
        'blog': blog_feed,
        'bill_subject_areas': bill_subject_areas,
        }
      
@anonymous_view
def staticpage(request, pagename):
    if pagename == "developers": pagename = "developers/index"
    
    ctx = { 'pagename': pagename }
    
    return render_to_response('website/' + pagename + '.html', ctx, RequestContext(request))

def get_blog_items():
    # c/o http://stackoverflow.com/questions/1208916/decoding-html-entities-with-python
    import re
    def _callback(matches):
        id = matches.group(1)
        try:
           return unichr(int(id))
        except:
           return id
    def decode_unicode_references(data):
        return re.sub("&#(\d+)(;|(?=\s))", _callback, data)

    import feedparser
    feed = feedparser.parse(settings.SITE_ROOT_URL + "/blog/atom")

    return [{"link":entry.link, "title":decode_unicode_references(entry.title), "date":datetime(*entry.updated_parsed[0:6]), "content":decode_unicode_references(entry.content[0].value)} for entry in feed["entries"][0:4]]

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
    
    results.append({
        "title": "Members of Congress, Presidents, and Vice Presidents",
        "href": "/congress/members/all",
        "qsarg": "name",
        "noun": "Members of Congress, Presidents, or Vice Presidents",
        "results": [
            {"href": p.object.get_absolute_url(),
             "label": p.object.name,
             "obj": p.object,
             "feed": p.object.get_feed(),
             "secondary": p.object.get_current_role() == None }
            for p in SearchQuerySet().using("person").filter(indexed_model_name__in=["Person"], content=q).order_by('-is_currently_serving', '-score')[0:9]]
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
        "title": "Subject Areas (Federal Legislation)",
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
    r = do_site_search(request.REQUEST.get("q", ""), allow_redirect=True, request=request)
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
    if request.user.is_authenticated():
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
    if not request.user.is_anonymous():
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
    if request.user.is_anonymous():
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
        user=request.user if not request.user.is_anonymous() else None,
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
    return render_to_response('website/videos.html', { "video_id": video_id }, RequestContext(request))


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

    if request.user.is_authenticated():
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

def add_remove_reaction(request):
    from website.models import Reaction
    res = { "status": "error" }
    if request.method == "POST" \
        and request.POST.get("subject") \
        and request.POST.get("mode") in ("-1", "1") \
        and request.POST.get("emoji") in Reaction.EMOJI_CHOICES:

        r, isnew = Reaction.objects.get_or_create(
            subject=request.POST["subject"],
            user=request.user if request.user.is_authenticated() else None,
            anon_session_key=Reaction.get_session_key(request) if not request.user.is_authenticated() else None,
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
    import urllib
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
      if r.req.get("query"): path += "?" + urllib.urlencode({ k.encode("utf8"): v.encode("utf8") for k,v in r.req["query"].items() })

      ua = str(user_agents.parse(r.req['agent']))
      if ua == "Other / Other / Other": ua = "bot"
      ua = re.sub(r"(\d+)(\.[\d\.]+)", r"\1", ua) # remove minor version numbers

      ret = {
        "reqid": r.id,
        "when": r.when.strftime("%b %-d, %Y %-I:%M:%S %p"),
        "netblock": get_netblock_label(r.req['ip']),
        "path": path,
        "query": r.req.get('query', {}),
        "ua": ua,
      }
      if recursive:
          ret["netblock"] = ", ".join(sorted(set( get_netblock_label(rr.req["ip"]) for rr in Sousveillance.objects.filter(subject=r.subject) )))
          ret["recent"] = [format_record(rr, False) for rr in Sousveillance.objects.filter(subject=r.subject, id__lt=r.id).order_by('-when')[0:15]]
      return ret
    records = [
      format_record(r, True)
      for r in records
    ]
    return HttpResponse(json.dumps(records, indent=2), content_type="application/json")
dump_sousveillance.max_age = 30
dump_sousveillance = anonymous_view(dump_sousveillance)
