import os
from lxml import etree
from us import parse_govtrack_date
from types import RoleType
from models import Person

def load_data(person):
    return {
        "sponsorship": load_sponsorship_analysis(person),
        "missedvotes": load_votes_analysis(person),
        "influence": load_influence_analysis(person),
    }
    
def load_sponsorship_analysis(person):
    role = person.get_most_recent_role()
    if not role: return None
    
    congressnumber = role.most_recent_congress_number()
    if not congressnumber: return None
    
    data = { }
    
    fname = 'data/us/%d/stats/sponsorshipanalysis' % congressnumber
    if role.role_type == RoleType.senator:
        fname += "_s.txt"
        data["chamber"] = "Senate"
    elif role.role_type == RoleType.representative:
        fname += "_h.txt"
        data["chamber"] = "House of Representatives"
    else:
        return None
    if not os.path.exists(fname): return None
    
    all_points = []
    data["all"] = all_points
    
    for line in open(fname).read().splitlines():
        chunks = [x.strip() for x in line.strip().split(',')]
        if chunks[0] == "ID": continue
        
        pt = { }
        pt['id'] = int(chunks[0])
        pt['ideology'] = chunks[1]
        pt['leadership'] = chunks[2]
        pt['name'] = chunks[3]
        pt['party'] = chunks[4]
        pt['description'] = chunks[5]
        
        if chunks[4] == "": continue # empty party means... not in office?
        
        if chunks[0] == str(person.pk):
            data.update(pt)
        else:
            all_points.append(pt)
            
    # sort, required by regroup tag
    all_points.sort(key = lambda item : item["party"])
            
    if not "ideology" in data: return None
    return data
    
def load_votes_analysis(person):
    role = person.get_most_recent_role()
    if not role: return None
    
    congressnumber = role.most_recent_congress_number()
    if not congressnumber: return None
    
    fn = 'data/us/%d/repstats.person/%d.xml' % (congressnumber, person.pk)
    if not os.path.exists(fn): return None
    
    dom = etree.parse(fn)
    
    return {
        "total": dom.xpath("novote")[0].get("NumVote"),
        "missed": dom.xpath("novote")[0].get("NoVote"),
        "percent": round(100*float(dom.xpath("novote")[0].get("NoVotePct"))),
        "firstdate": parse_govtrack_date(dom.xpath("novote")[0].get("FirstVoteDate")),
        "lastdate": parse_govtrack_date(dom.xpath("novote")[0].get("LastVoteDate")),
        "data": [(node.get("time"), round(100.0*float(node.get("NoVotePct")), 1), node.get("NoVote"), node.get("NumVote")) for node in dom.xpath("novote/hist-stat") ] }

def load_influence_analysis(person):
    influencers = []
    influencees = []
    
    # only the first 100 entries seemed to be helpful
    for line in open("/home/govtrack/scripts/analysis/influence_network_full.csv").readlines()[0:100]:
        influencer, influencee = line.strip().split(",")
        influencer = int(influencer)
        influencee = int(influencee)
        if person.id == influencer: influencees.append(influencee)
        if person.id == influencee: influencers.append(influencer)
    
    return { "influencers": Person.objects.in_bulk(influencers), "influencees": Person.objects.in_bulk(influencees) }
    
