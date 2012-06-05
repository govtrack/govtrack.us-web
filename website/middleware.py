from models import Req
from settings import WMATA_API_KEY
from django.core.cache import cache
 
import urllib, json, datetime

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

bulk_data_users_took_action = set(line.strip().lower() for line in open('campaign_bulk_data_emails') if line.strip() != "")

def template_context_processor(request):
    context = { }
    
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
        if is_ip_in_any_range(request.META["REMOTE_ADDR"], HOUSE_NET_RANGES):
            context["remote_net_house"] = True
        if is_ip_in_any_range(request.META["REMOTE_ADDR"], SENATE_NET_RANGES):
            context["remote_net_senate"] = True
    except:
        pass
    
    # Get WMATA train status at Capitol South and Union Station.
    def wmata_info():
        if datetime.datetime.now().hour < 16: return { }
        ret = cache.get("hill_wmata_info")
        if ret: return ret
        ret = { }
        try:
            ret.update( json.loads(urllib.urlopen("http://api.wmata.com/StationPrediction.svc/json/GetPrediction/B03,D05?api_key=" + WMATA_API_KEY).read()) )
            ret.update( json.loads(urllib.urlopen("http://api.wmata.com/Incidents.svc/json/Incidents?api_key=" + WMATA_API_KEY).read()) )
            ret["Trains"] = [t for t in ret["Trains"] if t["Line"] in ("RD", "BL", "OR")] # exclude no passengers
            for inc in ret["Incidents"]:
                inc["LinesAffected"] = [t for t in inc.get("LinesAffected", "").split(";") if t != ""]
        except:
            pass
        cache.set("hill_wmata_info", ret, 15) # 15 seconds
        return ret
    context["wmata_info"] = wmata_info
    
    # Has the user participated in the bulk data campaign?
    context["bulk_data_took_action"] = request.user.is_authenticated() and request.user.email.lower() in bulk_data_users_took_action
    
    return context
    
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
        
