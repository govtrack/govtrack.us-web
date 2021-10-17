from .models import Req
from django.core.cache import cache
from django.conf import settings
 
import json, datetime, base64, urllib.request, urllib.error, urllib.parse

from emailverification.models import BouncedEmail

from website.views import is_congress_in_session_live

import us

# http://whois.arin.net/rest/org/ISUHR/nets
HOUSE_NET_RANGES = (
    ("143.231.0.0", "143.231.255.255"),
    ("137.18.0.0", "137.18.255.255"),
    ("143.228.0.0", "143.228.255.255"),
    ("12.185.56.0", "12.185.56.7"),
    ("12.147.170.144", "12.147.170.159"),
    ("74.119.128.0", "74.119.131.255"),
    )
# http://whois.arin.net/rest/org/USSAA/nets
SENATE_NET_RANGES = (
    ("156.33.0.0", "156.33.255.255"),
    )
# http://whois.arin.net/rest/org/EXOP/nets
EOP_NET_RANGES = (
    ("165.119.0.0", "165.119.255.255"),
    ("198.137.240.0", "198.137.241.255"),
    ("204.68.207.0", "204.68.207.255"),
	)
def ip_to_quad(ip):
    return tuple([int(s) for s in ip.split(".")])
def is_ip_in_range(ip, block):
   return block[0] <= ip <= block[1]
def is_ip_in_any_range(ip, blocks):
   for block in blocks:
       if is_ip_in_range(ip, block):
           return True
   return False
    

trending_feeds = None

base_context = {
    "SITE_ROOT_URL": settings.SITE_ROOT_URL,
    "GOOGLE_ANALYTICS_KEY": getattr(settings, 'GOOGLE_ANALYTICS_KEY', ''),
    "DID_AN_ELECTION_JUST_HAPPEN": settings.CURRENT_ELECTION_DATE and settings.CURRENT_ELECTION_DATE <= datetime.datetime.now().date(),

    # district maps
    "MAPBOX_ACCESS_TOKEN": getattr(settings, 'MAPBOX_ACCESS_TOKEN'),
    "MAPBOX_MAP_STYLE": getattr(settings, 'MAPBOX_MAP_STYLE'),
    "MAPBOX_MAP_ID": getattr(settings, 'MAPBOX_MAP_ID'),
    "DISTRICT_BBOXES_FILE": getattr(settings, 'DISTRICT_BBOXES_FILE'),
}

def template_context_processor(request):
    # These are good to have in a context processor and not middleware
    # because they won't be evaluated until template evaluation, which
    # might have user-info blocked already for caching (a good thing).
    
    context = dict(base_context) # clone
    
    # Get our latest Medium posts.
    medium_posts = cache.get("medium_posts")
    if not medium_posts:
        from website.models import MediumPost
        medium_posts = MediumPost.objects.order_by('-published')[0:6]
        cache.set("medium_posts", medium_posts, 60*15) # 15 minutes
    context["medium_posts"] = medium_posts

    # Add context variables for whether the user is in the
    # House or Senate netblocks.
    try:
        context["remote_net_" + request._special_netblock] = True
    except:
        pass

    context["IS_CONGRESS_IN_SESSION_LIVE"] = is_congress_in_session_live

    return context
  
class GovTrackMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Some features require knowing if a user is a member of any panels.
        from userpanels.models import PanelMembership
        request.user.twostream_data = {
            "is_on_userpanel": PanelMembership.objects.filter(user=request.user).count()
              if request.user.is_authenticated else 0
        }

        # Is the user in one of the special netblocks?
        try:
            ip = request.META["REMOTE_ADDR"]
            ip = ip.replace("::ffff:", "") # ipv6 wrapping ipv4
            if is_ip_in_any_range(ip, HOUSE_NET_RANGES):
                request._special_netblock = "house"
            if is_ip_in_any_range(ip, SENATE_NET_RANGES):
                request._special_netblock = "senate"
            if is_ip_in_any_range(ip, EOP_NET_RANGES):
                request._special_netblock = "eop"
        except:
            pass

        return self.get_response(request)

