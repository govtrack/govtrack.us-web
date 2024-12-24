#!script

import os, glob, io
import csv, json, rtyaml
from collections import defaultdict

from numpy import median

from us import parse_govtrack_date
from person.types import RoleType
from person.models import Person

from django.conf import settings

def load_data(person):
    return {
        "sponsorship": load_sponsorship_analysis(person),
        "missedvotes": load_votes_analysis(person),
        "missing": is_legislator_missing(person),
        #"earmarks": load_earmarks_for(2024, person),
        #"influence": load_influence_analysis(person),
        #"scorecards": load_scorecards_for(person),
    }
    
def load_sponsorship_analysis(person):
    role = person.get_most_recent_congress_role(excl_trivial=True)
    if not role: return None
    
    congressnumber = role.most_recent_congress_number()
    if not congressnumber: return None

    # Harris served only a few days in 2021 but it kicks in
    # the next Congress. Report the previous Congress which
    # would be more reliable for her.
    if person.id == 412678: congressnumber = 116
    
    return load_sponsorship_analysis2(congressnumber, role.role_type, person)
    
def load_sponsorship_analysis2(congressnumber, role_type, person):
    data = { "congress": congressnumber, "current": congressnumber == settings.CURRENT_CONGRESS }
    
    fname = 'data/analysis/by-congress/%d/sponsorshipanalysis' % congressnumber
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

    # if the person was not found, return None            
    if person and not "ideology" in data: return None
    
    # add metadata
    data.update(json.load(open(fname.replace(".txt", "_meta.txt"))))
    from parser.processor import Processor
    for field in ('start_date', 'end_date'): # parse date fields to datetime's
        data[field] = Processor.parse_datetime(data[field])

    # add links to each person
    people = Person.objects.in_bulk({ pt["id"] for pt in all_points })
    for pt in all_points: pt["link"] = people[pt["id"]].get_absolute_url() if pt["id"] in people else None
    
    return data
    
def load_votes_analysis(person):
    role = person.get_most_recent_congress_role()
    if not role: return None
    
    congressnumber = role.most_recent_congress_number()
    if not congressnumber: return None

    # Get stats for the person's latest role but at the start of a new Congress
    # there might not be stats yet, so try the previous one.
    for c in (congressnumber, congressnumber-1):
      fn = 'data/analysis/by-congress/%d/person/missedvotes/%d.csv' % (c, person.pk)
      if os.path.exists(fn):
          congressnumber = c
          break
    else: # did not break
      return None
    
    lifetime_rec = None
    time_recs = []
    for rec in csv.DictReader(open(fn)):
        # normalize the string CSV fields as we need them for display
        rec = {
            "congress": rec["congress"],
            "session": rec["session"],
            "chamber": "House" if rec["chamber"] == "h" else "Senate",
            "period": int(rec["period"]) if rec["period"] != "" else None, # the lifetime record has no period
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
                if lifetime_rec: rec["firstdate"] = lifetime_rec["firstdate"]
                lifetime_rec = rec
        else:
            time_recs.append(rec)
            
    if lifetime_rec == None: return None

    # Set a flag if there are records from both chambers so the template can show the chamber
    # if so.
    lifetime_rec["multiple_chambers"] = len(set(rec["chamber"] for rec in time_recs)) > 1
    
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
    if _scorecards is None and hasattr(settings, 'SCORECARDS_DATABASE_PATH'):
        _scorecards = []
        for fn in sorted(glob.glob(settings.SCORECARDS_DATABASE_PATH + "/*.yaml")):
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
        _scorecards.sort(key = lambda scorecard : scorecard.get("abbrev") or scorecard["name"])
    return _scorecards

def load_scorecards_for(person):
    # Get the scorecards that apply to this person.
    ret = []
    for scorecard in load_scorecards() or []:
        if person.id in scorecard["scores"]:
            ret.append( (scorecard, scorecard["scores"][person.id]) )

    # Sort from highest to lowest score. Put percentages before letter grades.
    ret.sort(key=lambda mr : mr[1]["sort"], reverse=True) # sort on score, best to worst

    # Return.
    return ret

def load_earmarks_for(fiscalyear, person):
    fn = f'data/misc/earmarks_fy{fiscalyear}_house.csv'
    if not os.path.exists(fn): return None

    def format_dollar_amount(value):
        if value >= 4000000: # >=4 million, round to millions
            return f"${int(round(value / 1000000))} million"
        if value >= 1000000: # 1 million, round to 1/10th of a million
            return f"${round(value / 100000) / 10} million"
        if value >= 10000: # 10 thousand, round to thousands
            return f"${int(round(value / 1000) * 1000):,}"
        return f"${int(round(value / 1000))}"

    # legislators_by_bioguideid = {
    #     p.bioguideid: p
    #     for p in Person.objects.filter(roles__current=True).exclude(bioguideid=None).distinct() }
    total_requests_by_legislator = defaultdict(lambda : 0)
    this_legislators_requests = []
    with open(fn) as f:
        f.readline() # credit notice
        for rec in csv.DictReader(f):
            #p = legislators_by_bioguideid[rec['Member Bioguide ID']]
            #if rec['Party'] == 'D':
            amount = int(float(rec['Amount Requested'].replace("$", "").replace(",", "")))
            total_requests_by_legislator[rec['Member Bioguide ID']] += amount
            if rec['Member Bioguide ID']== person.bioguideid:
                this_legislators_requests.append({
                    'amount': amount,
                    'amount_display': format_dollar_amount(amount),
                    'recipient': rec['Recipient'],
                    'purpose': rec['Project Purpose'],
                    'link': rec['Member Website'],
                })

    this_legislators_requests.sort(key = lambda req : -req["amount"])

    # As of 4/30/2023, the total number of representatives in the
    # spreadsheet is 369 (85% of all 435 reps), 154 Republicans
    # (69% of 224 Republican reps including delegates) and 215
    # Democrats (of 216 Democratic reps including delegates).

    # Only return data for legislators for which we might have information,
    # which are legislators in the dataset and any legislators who
    # were serving in the House at the time the dataset was created.
    # print(
    #     set(Person.objects.filter(roles__current=True, roles__role_type=2).exclude(bioguideid=None).distinct().values_list("bioguideid", flat=True))
    #     - set(total_requests_by_legislator))
    legislators_without_earmarks = {'O000175', 'M001177', 'B001302', 'H001072', 'M001156', 'C001115', 'M001224', 'M001165', 'B000668', 'P000609', 'R000600', 'N000190', 'M001218', 'J000301', 'P000605', 'P000615', 'M000871', 'F000446', 'E000298', 'L000564', 'W000804', 'B001297', 'W000812', 'B001307', 'H001082', 'G000576', 'P000618', 'M001211', 'B001317', 'G000579', 'R000614', 'A000372', 'B001299', 'C001039', 'Y000067', 'S000929', 'S001195', 'B001311', 'C001116', 'A000379', 'S001189', 'L000589', 'B001314', 'S001213', 'C001132', 'A000377', 'B001248', 'F000478', 'M001195', 'W000816', 'J000289', 'T000480', 'H001093', 'W000795', 'S001183', 'D000615', 'F000469', 'R000103', 'B001316', 'S001199', 'D000626', 'T000165', 'G000590', 'G000565', 'H001058', 'F000450', 'G000595', 'B001275', 'M001212', 'M000194', 'F000246', 'M001184'}
    if person.bioguideid not in total_requests_by_legislator \
      and person.bioguideid not in legislators_without_earmarks:
        return None

    ret = {
        "fiscal_year": fiscalyear,
        "total_requested_display": format_dollar_amount(total_requests_by_legislator[person.bioguideid]),
        "requests": this_legislators_requests,
        "link": this_legislators_requests[0]['link'] if this_legislators_requests else None,
        "median_total_request_display": format_dollar_amount(median(list(total_requests_by_legislator.values()))),
        "total_reps_requesting": len(total_requests_by_legislator),
        "total_reps_serving": 441, # as of 4/30/2023 when database was pulled, including delegates
    }

    return ret


def load_missing_legislators(congress):
    fn = f'data/analysis/by-congress/{congress}/missinglegislators.csv'
    if not os.path.exists(fn): return None
    for row in csv.DictReader(open(fn)):
        row["person"] = Person.objects.get(id=int(row["person"]))
        row["missedvotes"] = int(row["missedvotes"])
        row["totalvotes"] = int(row["totalvotes"])
        row["missedvotespct"] = int(round(100 * row["missedvotes"] / row["totalvotes"]))
        row["firstmissedvote"] = parse_govtrack_date(row["firstmissedvote"])
        row["lastvote"] = parse_govtrack_date(row["lastvote"])

        if row["person"].id == 412677:
            row["explanation_html"] = "Rep. Evans had a stroke in early 2024."
        if row["person"].id == 412612:
            row["explanation_html"] = "Rep. Pelosi suffered a hip fracture from a fall during foreign travel."

        row["chart"] = load_votes_analysis(row["person"])

        yield row


def is_legislator_missing(person):
    role = person.get_most_recent_congress_role()
    if not role or not role.current: return None
    congressnumber = role.most_recent_congress_number()
    if not congressnumber: return None
    missing_legislators = load_missing_legislators(congressnumber)
    for row in missing_legislators:
        if row["person"] == person:
            return row
    return None


#if __name__ == "__main__":
#    print(is_legislator_missing(Person.objects.get(id=456933)))
