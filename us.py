# TODO: move this module to some package

from datetime import datetime

# Current apportionment to the states, or "T" for territories sending a delegate
# or resident commissioner. This dict is used to filter out the historical territories
# from lists of the current states and territories.
stateapportionment = {'AL': 7, 'AK': 1, 'AS': 'T', 'AZ': 8, 'AR': 4, 'CA': 53, 'CO': 7, 'CT': 5, 'DE': 1, 'DC': 'T', 'FL': 25, 'GA': 13, 'GU': 'T', 'HI': 2, 'ID': 2, 'IL': 19, 'IN': 9, 'IA': 5, 'KS': 4, 'KY': 6, 'LA': 7, 'ME': 2, 'MD': 8, 'MA': 10, 'MI': 15, 'MN': 8, 'MS': 4, 'MO': 9, 'MT': 1, 'NE': 3, 'NV': 3, 'NH': 2, 'NJ': 13, 'NM': 3, 'NY': 29, 'NC': 13, 'ND':  1, 'MP': 'T', 'OH': 18, 'OK': 5, 'OR': 5, 'PA': 19, 'PR': 'T', 'RI': 2, 'SC': 6, 'SD': 1, 'TN': 9, 'TX': 32, 'UT': 3, 'VT': 1, 'VI': 'T', 'VA': 11, 'WA': 9, 'WV': 3, 'WI': 8, 'WY': 1}

# All state abbreviations, including historical territories.
stateabbrs = ["AL", "AK", "AS", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "GU", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "MP", "OH", "OK", "OR", "PA", "PR", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VI", "VA", "WA", "WV", "WI", "WY", "DK", "PI", "OL"]

# All state names, including historical territories.
statenames = {"AL":"Alabama", "AK":"Alaska", "AS":"American Samoa", "AZ":"Arizona", "AR":"Arkansas", "CA":"California", "CO":"Colorado", "CT":"Connecticut", "DE":"Delaware", "DC":"District of Columbia", "FL":"Florida", "GA":"Georgia", "GU":"Guam", "HI":"Hawaii", "ID":"Idaho", "IL":"Illinois", "IN":"Indiana", "IA":"Iowa", "KS":"Kansas", "KY":"Kentucky", "LA":"Louisiana", "ME":"Maine", "MD":"Maryland", "MA":"Massachusetts", "MI":"Michigan", "MN":"Minnesota", "MS":"Mississippi", "MO":"Missouri", "MT":"Montana", "NE":"Nebraska", "NV":"Nevada", "NH":"New Hampshire", "NJ":"New Jersey", "NM":"New Mexico", "NY":"New York", "NC":"North Carolina", "ND": "North Dakota", "MP":"Northern Mariana Islands", "OH":"Ohio", "OK":"Oklahoma", "OR":"Oregon", "PA":"Pennsylvania", "PR":"Puerto Rico", "RI":"Rhode Island", "SC":"South Carolina", "SD":"South Dakota", "TN":"Tennessee", "TX":"Texas", "UT":"Utah", "VT":"Vermont", "VI":"Virgin Islands", "VA":"Virginia", "WA":"Washington", "WV":"West Virginia", "WI":"Wisconsin", "WY":"Wyoming", "DK": "Dakota Territory", "PI": "Philippines Territory/Commonwealth", "OL": "Territory of Orleans"}

# Current states, a list of (abbr, name) tuples in sorted order.
statelist = [s for s in statenames.items() if s[0] in stateapportionment]
statelist.sort(key=lambda x : x[1])

CONGRESS_DATES = {}
SESSION_DATES = []

def parse_govtrack_date(d):
    try:
        return datetime.strptime(d, '%Y-%m-%dT%H:%M:%S-04:00')
    except ValueError:
        pass
    try:
        return datetime.strptime(d, '%Y-%m-%dT%H:%M:%S-05:00')
    except ValueError:
        pass
    return datetime.strptime(d, '%Y-%m-%d')


def get_congress_dates(congressnumber):
    global CONGRESS_DATES
    if CONGRESS_DATES == { }:
        cd = {}
        for line in open('data/us/sessions.tsv'):
            cn, sessionname, startdate, enddate = line.strip().split('\t')[0:4]
            if not '-' in startdate: # header
                continue
            cn = int(cn)
            if not cn in cd:
                cd[cn] = [parse_govtrack_date(startdate), None]
            cd[cn][1] = parse_govtrack_date(enddate)
        CONGRESS_DATES.update(cd)
    return CONGRESS_DATES[congressnumber]

def get_session_from_date(when):
    global SESSION_DATES
    if SESSION_DATES == [ ]:
        sd = []
        for line in open('data/us/sessions.tsv'):
            cn, sessionname, startdate, enddate = line.strip().split('\t')[0:4]
            if not '-' in startdate: # header
                continue
            sd.append((int(cn), sessionname, parse_govtrack_date(startdate), parse_govtrack_date(enddate)))
        SESSION_DATES = sd
    
    if when == None:
        return None
    
    for c, s, sd, ed in SESSION_DATES:
        if sd <= when and when <= ed:
            return (c, s)
            
    return None

def get_session_ordinal(congress, session):
    get_session_from_date(None) # load data
    
    ordinal = 0
    for c, s, sd, ed in SESSION_DATES:
        if c == congress:
            ordinal += 1
            if s == session: return ordinal
            
    raise ValueError("Congress or session not found.")
    

