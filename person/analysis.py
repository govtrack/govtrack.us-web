import os, glob, io
import csv, json, rtyaml
from us import parse_govtrack_date
from .types import RoleType
from .models import Person

from settings import CURRENT_CONGRESS

def load_data(person):
    return {
        "sponsorship": load_sponsorship_analysis(person),
        "missedvotes": load_votes_analysis(person),
        #"influence": load_influence_analysis(person),
        "scorecards": load_scorecards_for(person),
    }
    
def load_sponsorship_analysis(person):
    role = person.get_most_recent_congress_role(excl_trivial=True)
    if not role: return None
    
    congressnumber = role.most_recent_congress_number()
    if not congressnumber: return None
    
    return load_sponsorship_analysis2(congressnumber, role.role_type, person)
    
def load_sponsorship_analysis2(congressnumber, role_type, person):
    data = { "congress": congressnumber, "current": congressnumber == CURRENT_CONGRESS }
    
    fname = 'data/us/%d/stats/sponsorshipanalysis' % congressnumber
    if role_type == RoleType.senator:
        fname += "_s.txt"
        data["chamber"] = "Senate"
    elif role_type == RoleType.representative:
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

        # Ignore members with low leadership scores because their ideology scores are inaccurate.
        if float(chunks[2]) < 0.1: continue

        pt = { }
        pt['id'] = int(chunks[0])
        pt['ideology'] = chunks[1]
        pt['leadership'] = chunks[2]
        pt['name'] = chunks[3]
        pt['party'] = chunks[4]
        pt['description'] = chunks[5]
        pt['introduced_bills'] = int(chunks[6])
        pt['cosponsored_bills'] = int(chunks[7])
        pt['unique_cosponsors'] = int(chunks[8])
        pt['total_cosponsors'] = int(chunks[9])
        
        if chunks[4] == "": continue # empty party means... not in office?
        
        if person and chunks[0] == str(person.pk):
            data.update(pt)
        else:
            all_points.append(pt)
            
    # sort, required by regroup tag
    all_points.sort(key = lambda item : item["party"])
            
    if person and not "ideology" in data: return None
    
    data.update(json.load(open(fname.replace(".txt", "_meta.txt"))))
    from parser.processor import Processor
    for field in ('start_date', 'end_date'):
        data[field] = Processor.parse_datetime(data[field])
    
    return data
    
def load_votes_analysis(person):
    role = person.get_most_recent_congress_role()
    if not role: return None
    
    congressnumber = role.most_recent_congress_number()
    if not congressnumber: return None
    
    fn = 'data/us/%d/stats/person/missedvotes/%d.csv' % (congressnumber, person.pk)
    if not os.path.exists(fn): return None
    
    lifetime_rec = None
    time_recs = []
    for rec in csv.DictReader(open(fn)):
        # normalize the string CSV fields as we need them for display
        rec = {
            "congress": rec["congress"],
            "session": rec["session"],
            "chamber": rec["chamber"],
            "period": rec["period"],
            "total": int(rec["total_votes"]),
            "missed": int(rec["missed_votes"]),
            "percent": round(float(rec["percent"]), 1),
            "percentile": int(round(float(rec["percentile"]))),
            "firstdate": parse_govtrack_date(rec["period_start"]),
            "lastdate": parse_govtrack_date(rec["period_end"]),
            "pctile25": float(rec["pctile25"]),
            "pctile50": float(rec["pctile50"]),
            "pctile75": float(rec["pctile75"]),
            "pctile90": float(rec["pctile90"]),
        }
        # for historical data, the year is out of range for strftime. but if we replace the year we also have to
        # replace the month because a day may be out of range in Feburary depending on the day.
        if rec["firstdate"].year != rec["lastdate"].year:
            rec["time"] = rec["firstdate"].replace(year=1900, day=1).strftime("%b") + " " + str(rec["firstdate"].year) + "-" + rec["lastdate"].replace(year=1900, day=1).strftime("%b") + " " + str(rec["lastdate"].year)
        else:
            rec["time"] = str(rec["firstdate"].year) + " " + rec["firstdate"].replace(year=1900, day=1).strftime("%b-") + rec["lastdate"].replace(year=1900, day=1).strftime("%b")
        
        if rec["congress"] == "lifetime":
            # Take the "lifetime" record with the most recent period_start, since there may be one
            # record for the House and one record for the Senate.
            if lifetime_rec == None or lifetime_rec["firstdate"] < rec["firstdate"]:
                lifetime_rec = rec
        else:
            time_recs.append(rec)
            
    if lifetime_rec == None: return None
            
    # It's confusing to take records from two chambers, so filter by chamber.
    time_recs = [rec for rec in time_recs if rec["chamber"] == lifetime_rec["chamber"]]
    
    lifetime_rec["data"] = time_recs
    return lifetime_rec

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

_scorecards = None
def load_scorecards():
    global _scorecards
    if _scorecards is None:
        _scorecards = []
        for fn in sorted(glob.glob("data/scorecards/*.yaml")):
            with open(fn) as f:
                # Split on "...", read the top as YAML and the
                # bottom as CSV.
                metadata, scores = f.read().split("\n...\n")
                metadata = rtyaml.load(metadata)
                scores = list(csv.reader(io.StringIO(scores)))

                # Store scores as a mapping from person IDs to score info.
                letter_grades = ("F", "D-", "D", "D+", "C-", "C", "C+", "B-", "B", "B+", "A-", "A", "A+")
                def format_score(score, info):
                    try:
                        if metadata.get("type") == "percent":
                            return {
                                "display": str(int(score)) + "%",
                                "sort": int(score),
                            }
                        if metadata.get("type") == "grade":
                            # for sorting, turn the grade into a number from 0 to 100
                            score = score.strip()
                            return {
                                "display": score,
                                "sort": letter_grades.index(score)/float(len(letter_grades)-1)*100,
                            }
                        raise ValueError()
                    except:
                        raise ValueError("Invalid scorecard entry for %s: %s %s." % (info, repr(metadata.get("type")), repr(score)))
                metadata["scores"] = {
                    int(row[0]): format_score(row[1].strip(), [fn, row[0]] + row[2:])
                    for row in scores
                    if row[0].strip() != ""
                }
                metadata["based_on"] = metadata["based-on"]
                _scorecards.append(metadata)
        _scorecards.sort(key = lambda scorecard : scorecard["abbrev"])
    return _scorecards

def load_scorecards_for(person):
    # Get the scorecards that apply to this person.
    ret = []
    for scorecard in load_scorecards():
        if person.id in scorecard["scores"]:
            ret.append( (scorecard, scorecard["scores"][person.id]) )

    # Sort from highest to lowest score. Put percentages before letter grades.
    ret.sort(key=lambda mr : mr[1]["sort"], reverse=True) # sort on score, best to worst

    # Return.
    return ret
