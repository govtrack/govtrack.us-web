# -*- coding: utf-8 -*-
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import redirect, get_object_or_404, render_to_response
from django.template import RequestContext
from django.core.urlresolvers import reverse
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from django.contrib.auth.decorators import login_required

from common.decorators import render_to
from common.pagination import paginate

from cache_utils.decorators import cached

from twostream.decorators import anonymous_view

from events.models import Feed
import us

import re
from datetime import datetime, timedelta

@anonymous_view
@render_to('website/index.html')
def index(request):
    twitter_feed = cache.get("our_twitter_feed")
    if twitter_feed == None:
        try:
            import twitter
            twitter_api = twitter.Api()
            twitter_feed = twitter_api.GetUserTimeline("govtrack", since_id=0, count=3)
        
            # replace links
            from django.utils.html import conditional_escape
            from django.utils.safestring import mark_safe
            re_url = re.compile(r"(?i)\b((?:[a-z][\w-]+:(?:/{1,3}|[a-z0-9%])|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))")
            for item in twitter_feed:
                item.text = re_url.sub(lambda m : "<a target=\"_blank\" href=\"" + m.group(0) + "\">" + m.group(0) + "</a>", conditional_escape(item.text))
            cache.set("our_twitter_feed", twitter_feed, 60*30) # 30 minutes
        except:
            twitter_feed = []
            cache.set("our_twitter_feed", twitter_feed, 60*2) # 2 minutes
            
        
    blog_feed = cache.get("our_blog_feed")
    if not blog_feed:
        blog_feed = get_blog_items()[0:2]
        cache.set("our_blog_feed", blog_feed, 60*30) # 30 min
    
    events_feed = cache.get("frontpage_events_feed")
    if not events_feed:
        events_feed = Feed.get_events_for([fn for fn in ("misc:activebills2", "misc:billsummaries", "misc:allvotes") if Feed.objects.filter(feedname=fn).exists()], 6)
        cache.set("frontpage_events_feed", events_feed, 60*15) # 15 minutes

    return {
        'events': events_feed,
        'tweets': twitter_feed,
        'blog': blog_feed,
        }
      
@anonymous_view
def staticpage(request, pagename):
    if pagename == "developers": pagename = "developers/index"
    
    ctx = { 'pagename': pagename }
    
    if pagename == "overview":
        from us import statenames
        from states.views import states_with_data
        ctx['states'] = ((s, statenames[s]) for s in states_with_data())
    
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
    feed = feedparser.parse("http://www.govtrack.us/blog/atom")

    return [{"link":entry.link, "title":decode_unicode_references(entry.title), "date":datetime(*entry.updated_parsed[0:6]), "content":decode_unicode_references(entry.content[0].value)} for entry in feed["entries"][0:4]]

def congress_home(request):
    return HttpResponseRedirect("/overview")

def do_site_search(q, allow_redirect=False):
    if q.strip() == "":
        return []
    
    results = []
    
    from events.models import Feed
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
                    Feed.EnactedBillsFeed(), Feed.ActiveBillsExceptIntroductionsFeed(), Feed.ComingUpFeed(), Feed.AllVotesFeed(),
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
             "feed": Feed.PersonFeed(p.object),
             "secondary": p.object.get_current_role() == None }
            for p in SearchQuerySet().using("person").filter(indexed_model_name__in=["Person"], content=q)[0:9]]
        })
       
    # Skipping states for now because we might want to go to the district maps or to
    # the state's main page for state legislative information.
    #import us
    #results.append(("States", "/congress/members", "most_recent_role_state", "states",
    #    sorted([{"href": "/congress/members/%s" % s, "label": us.statenames[s] }
    #        for s in us.statenames
    #        if us.statenames[s].lower().startswith(q.lower())
    #        ], key=lambda p : p["label"])))
    
    from committee.models import Committee
    results.append({
        "title": "Congressional Committees",
        "href": "/congress/committees",
        "noun": "committees in Congress",
        "results": sorted([
            {"href": c.get_absolute_url(),
             "label": c.fullname,
             "feed": Feed.CommitteeFeed(c),
             "obj": c,
             "secondary": c.committee != None}
            for c in Committee.objects.filter(name__icontains=q, obsolete=False)
            ], key=lambda c : c["label"])
        })
       
    from settings import CURRENT_CONGRESS
    from bill.search import parse_bill_citation
    bill = parse_bill_citation(q)
    if not bill or not allow_redirect:
        bills = [\
            {"href": b.object.get_absolute_url(),
             "label": b.object.title,
             "obj": b.object,
             "feed": Feed.BillFeed(b.object) if b.object.is_alive else None,
             "secondary": b.object.congress != CURRENT_CONGRESS }
            for b in SearchQuerySet().using("bill").filter(indexed_model_name__in=["Bill"], content=q).order_by('-current_status_date')[0:9]]
    else:
        #bills = [{"href": bill.get_absolute_url(), "label": bill.title, "obj": bill, "secondary": bill.congress != CURRENT_CONGRESS }]
        return HttpResponseRedirect(bill.get_absolute_url())
    results.append({
        "title": "Bills and Resolutions (Federal)",
        "href": "/congress/bills/browse",
        "qsarg": "text",
        "noun": "federal bills or resolutions",
        "results": bills})

    
    results.append({
        "title": "State Legislation",
        "href": "/states/bills/browse",
        "qsarg": "text",
        "noun": "state legislation",
        "results": [
            {"href": p.object.get_absolute_url(),
             "label": p.object.short_display_title,
             "obj": p.object,
             "feed": Feed(feedname="states_bill:%d" % p.object.id),
             "secondary": True }
            for p in SearchQuerySet().using('states').filter(indexed_model_name__in=["StateBill"], content=q)[0:9]]
            })

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
             "feed": Feed.IssueFeed(p),
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
    r = do_site_search(request.REQUEST.get("q", ""), allow_redirect=True)
    if not isinstance(r, list): return r
    return { "results": r }

@cache_page(60 * 15)
@render_to('website/campaigns/bulkdata2.html')
def campaign_bulk_data(request):
    return { }

@render_to('website/campaigns/bulkdata.html')
def campaign_bulk_data_old(request):
    prefixes = ("Mr.", "Ms.", "Mrs.", "Dr.")
    
    # Validate.
    if request.method == 'POST':
        from models import CampaignSupporter

        s = CampaignSupporter()
        
        if "sid" in request.POST:
            try:
                s = CampaignSupporter.objects.get(id=request.POST.get("sid"), email=request.POST.get("email", ""))
            except:
                pass
        
        s.campaign = "2012_03_buldata"
        for field in ('prefix', 'firstname', 'lastname', 'address', 'city', 'state', 'zipcode', 'email'):
            if request.POST.get(field, '').strip() == "":
                return { "stage": 1, "error": "All fields are required!", "prefixes": prefixes }
            setattr(s, field, request.POST.get(field, ""))
        s.message = request.POST.get('message', '')
        s.save()

        if "message" not in request.POST:
            return { "stage": 2, "sid": s.id }
        else:
            return { "stage": 3 }
    return { "stage": 1, "prefixes": prefixes }

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
            return "http://www.govtrack.us" + item["url"]# + "?utm_campaign=govtrack_push&utm_source=govtrack_push" 
        def item_guid(self, item):
            return "http://www.govtrack.us/events/guid/" + item["guid"] 
        def item_pubdate(self, item):
            return item["date"] if isinstance(item["date"], datetime) else datetime.combine(item["date"], time.min)
            
    return DjangoFeed()(request)


@render_to('website/your_docket.html')
def your_docket(request):
    # Pre-load the user's subscription lists and for each list
    # pre-load the list of bills entered into the list.
    lists = []
    if request.user.is_authenticated():
        lists = request.user.subscription_lists.all()
        for lst in lists:
            lst.bills = [tr.bill() for tr in lst.trackers.all() if tr.bill() != None]
            
    return { "lists": lists }

@login_required
def update_account_settings(request):
    if request.POST.get("action") == "unsubscribe":
        # Turn off all email updates.
        for x in request.user.userprofile().lists_with_email():
            x.email = 0
            x.save()
        
    if request.POST.get("action") == "massemail":
        p = request.user.userprofile()
        p.massemail = True if request.POST.get("massemail", False) else False
        p.save()
            
    return HttpResponseRedirect("/accounts/profile")

from website.api import api_overview

@render_to('website/congress_live.html')
def congress_live(request):

    from cache_utils.decorators import cached
    @cached(60*5)
    def get_loc_streams():
        # Scrape the LoC for live House committee hearings.
        
        import urllib
        cmtelist = urllib.urlopen("http://thomas.loc.gov/video/house-committee").read()
        
        feeds = []
        for m in re.findall(r'<a href="(/video/house-committee/\S*)" class="committee-links"', cmtelist):
            cmtepage = urllib.urlopen("http://thomas.loc.gov" + m).read()
            n = re.search(r'<h3>Live Stream: ([^<]+)</h3><iframe [^>]+src="(http://www.ustream.tv/embed/\d+)"', cmtepage)
            if n:
                feeds.append( { "title": n.group(1), "url": "http://thomas.loc.gov" + m } )
            
        return feeds

    return {
        "housecommittees": get_loc_streams,
    }
    
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
        
    import bill.prognosis_model
    import bill.prognosis_model_test
    prognosis_factors = list((k, dict(v)) for k, v in bill.prognosis_model.factors.items()) # clone
    for k, v in prognosis_factors:
        v["bill_type"] = BillType.by_value(k[0])
        v["is_introduced_model"] = k[1]
        v["factors"] = sorted(v["factors"].values(), key = lambda f : f["regression_beta"], reverse=True)
    prognosis_factors = [kv[1] for kv in prognosis_factors]
    prognosis_factors.sort(key = lambda m : (m["bill_type"] in (BillType.house_bill, BillType.senate_bill), m["count"]), reverse=True)
    prognosis_test = list(bill.prognosis_model_test.model_test_results.items()) # clone
    for k, v in prognosis_test:
        v["bill_type"] = BillType.by_value(k[0])
        v["is_introduced_model"] = (k[1] == 0)
        v["success_name"] = bill.prognosis_model.factors[(k[0], (k[1] == 0))]["success_name"]
    prognosis_test.sort(key = lambda kv : (kv[0][0] in (BillType.house_bill, BillType.senate_bill), kv[1]["count"]), reverse=True)
    prognosis_test = [kv[1] for kv in prognosis_test]
    
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
    
    is_ad_free = False
    
    if not request.user.is_anonymous():
        is_ad_free = request.user.userprofile().get_ad_free_message()
        
    return { "is_ad_free": is_ad_free }
    
def go_ad_free_redirect(request):
    # create a Payment and redirect to the approval step, and track this
    
    if request.user.is_anonymous():
        return HttpResponseRedirect(reverse(go_ad_free_start))
        
    if request.user.get_profile().get_ad_free_message():
        raise ValueError("User already has this feature.")
    
    import paypalrestsdk

    sandbox = ""
    if paypalrestsdk.api.default().mode == "sandbox":
        sandbox = "-sandbox"
    
    payment = paypalrestsdk.Payment({
      "intent": "sale",
      "payer": { "payment_method": "paypal" },
      "transactions": [{
        "item_list": {
          "items": [{
            "name": "Ad-Free GovTrack.us for 1 Year",
            "sku": "govtrack-ad-free-for-year" + sandbox,
            "price": "2.00",
            "currency": "USD",
            "quantity": 1 }]
            },
          "amount": {
            "total": "2.00",
            "currency": "USD"
          },
          "description": "Ad-Free%s: GovTrack.us is ad-free for a year while you're logged in." % sandbox }],
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
        paypal_id = payment.id,
        user = request.user,
        response_data = payment.to_dict(),
        notes = "ad-free-year $2")
    rec.save()
  
    for link in payment.links:
        if link.method == "REDIRECT":
            return HttpResponseRedirect(link.href)
    else:
        raise ValueError("No redirect in PayPal.Payment: " + payment.id)
    
def go_ad_free_finish(request):
    if request.user.is_anonymous():
        raise ValueError("User got logged out!")

    # Do as much before we destroy state.
    prof = request.user.get_profile()

    from website.models import PayPalPayment
    (payment, rec) = PayPalPayment.execute(request, "ad-free-year $2")
    
    try:
        # Update the user profile.
        if prof.paid_features == None: prof.paid_features = { }
        prof.paid_features["ad_free_year"] = (payment.id, None)
        prof.save()
      
        # Send user back to the start.
        return HttpResponseRedirect(reverse(go_ad_free_start))
     
    except Exception as e:
        raise ValueError(str(e) + " while processing " + payment.id)

