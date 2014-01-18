from models import Req
from django.core.cache import cache
from django.conf import settings
 
import urllib, json, datetime, base64

from emailverification.models import BouncedEmail

if settings.GEOIP_DB_PATH:
    from django.contrib.gis.geoip import GeoIP
    from django.contrib.gis.geos import Point
    geo_ip_db = GeoIP(settings.GEOIP_DB_PATH)
    washington_dc = Point(-77.0300, 38.8900)

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

trending_feeds = None

def template_context_processor(request):
    # These are good to have in a context processor and not middleware
    # because they won't be evaluated until template evaluation, which
    # might have user-info blocked already for caching (a good thing).
    
    context = {
        "SITE_ROOT_URL": settings.SITE_ROOT_URL,
        "GOOGLE_ANALYTICS_KEY": settings.GOOGLE_ANALYTICS_KEY
    }
    
    if request.user.is_authenticated() and BouncedEmail.objects.filter(user=request.user).exists(): context["user_has_bounced_mail"] = True
    
    # Add top-tracked feeds.
    global trending_feeds
    if not trending_feeds or trending_feeds[0] < datetime.datetime.now()-datetime.timedelta(hours=2):
        from events.models import Feed
        trf = cache.get("trending_feeds")
        if not trf:
            trf = Feed.get_trending_feeds()
            cache.set("trending_feeds", trf, 60*60*2)
        trending_feeds = (datetime.datetime.now(), [Feed.objects.get(id=f) for f in trf])
    context["trending_feeds"] = trending_feeds[1]
    
    # Add context variables for whether the user is in the
    # House or Senate netblocks.
    
    def ip_to_quad(ip):
        return [int(s) for s in ip.split(".")]
    def compare_ips(ip1, ip2):
        return cmp(ip_to_quad(ip1), ip_to_quad(ip2))
    def is_ip_in_range(ip, block):
       return compare_ips(ip, block[0]) >= 0 and compare_ips(ip, block[1]) <= 0
    def is_ip_in_any_range(ip, blocks):
       for block in blocks:
           if is_ip_in_range(ip, block):
               return True
       return False
    
    try:
        ip = request.META["REMOTE_ADDR"]
        ip = ip.replace("::ffff:", "") # ipv6 wrapping ipv4
        
        if is_ip_in_any_range(ip, HOUSE_NET_RANGES):
            context["remote_net_house"] = True
            request._track_this_user = True
        if is_ip_in_any_range(ip, SENATE_NET_RANGES):
            context["remote_net_senate"] = True
            request._track_this_user = True
        if is_ip_in_any_range(ip, EOP_NET_RANGES):
            context["remote_net_eop"] = True
            request._track_this_user = True
        
        try:
            cong_dist = json.loads(request.COOKIES["cong_dist"])
        except:
            cong_dist = None
        
        if settings.GEOIP_DB_PATH:
            user_loc = geo_ip_db.geos(ip)
            context["is_dc_local"] = user_loc.distance(washington_dc) < .5
            
            # geolocate to a congressional district if not known
            if not cong_dist and False:
                from person.views import do_district_lookup
                cong_dist = do_district_lookup(*user_loc.coords)
                cong_dist["queried"] = True

        if cong_dist and "error" not in cong_dist:
            from person.models import PersonRole, RoleType, Gender
            import random
            def get_key_vote(p):
                from vote.models import Vote
                
                v = 113340
                descr = "CISPA"
                
                v = Vote.objects.get(id=v)
                try:
                    return {
                        "link": v.get_absolute_url(),
                        "description": descr,
                        "option": p.votes.get(vote=v).option.key,
                    }
                except:
                    return None
            def fmt_role(r):
                return {
                    "id": r.person.id,
                    "name": r.person.name_and_title(),
                    "link": r.person.get_absolute_url(),
                    "type": RoleType.by_value(r.role_type).key,
                    "pronoun": Gender.by_value(r.person.gender).pronoun,
                    "key_vote": get_key_vote(r.person),
                }
            qs = PersonRole.objects.filter(current=True).select_related("person")    
            cong_dist["reps"] = [fmt_role(r) for r in 
                qs.filter(role_type=RoleType.representative, state=cong_dist["state"], district=cong_dist["district"])
                | qs.filter(role_type=RoleType.senator, state=cong_dist["state"])]
                
            if settings.DEBUG:
                # I need to test with more than my rep (just our DC delegate).
                cong_dist["reps"] = [fmt_role(r) for r in random.sample(PersonRole.objects.filter(current=True), 3)]
            
            random.shuffle(cong_dist["reps"]) # for varied output
            
            context["geolocation"] = json.dumps(cong_dist)
        if cong_dist: # whether or not error
            request.cong_dist_info = cong_dist
                
    except:
        pass
    
    return context
  
class GovTrackMiddleware:
    def process_response(self, request, response):
        # Save the geolocation info in a cookie so we don't have to
        # query GIS info on each request.
        if hasattr(request, "cong_dist_info"):
            cong_dist_info = request.cong_dist_info
            for k in ("queried", "reps"):
                if k in cong_dist_info: del cong_dist_info[k]
            response.set_cookie("cong_dist", json.dumps(cong_dist_info), max_age=60*60*24*21)

		# log some requets for processing later
        if hasattr(request, "_track_this_user"):
            uid = request.COOKIES.get("uuid")
            if not uid:
                import uuid
                uid = base64.urlsafe_b64encode(uuid.uuid4().bytes).replace('=', '')
            response.set_cookie("uuid", uid, max_age=60*60*24*365*10)
            print "TRACK", uid, datetime.datetime.now().isoformat(), base64.b64encode(repr(request))

        return response


class DebugMiddleware:
    def process_request(self, request):
        r = Req(request=repr(request))
        r.save()
        request._debug_req = r
        return None
    def process_response(self, request, response):
        if getattr(request, "_debug_req", None) != None:
            request._debug_req.delete()
            request._debug_req = None
        return response
    def process_exception(self, request, exception):
        if getattr(request, "_debug_req", None) != None:
            request._debug_req.delete()
            request._debug_req = None
        return None
        
