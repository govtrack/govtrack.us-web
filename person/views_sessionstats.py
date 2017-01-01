from us import statenames

stat_titles = {
    "missed-votes":  { "title": "Missed Votes", "icon": "voting-records", "superlatives": ("most absent", "most voting") },
    "bills-introduced":  { "title": "Bills Introduced", "icon": "bills-resolutions", "superlatives": ("most bills", "fewest bills") },
    "bills-enacted":  { "title": "Laws Enacted", "icon": "bills-resolutions", "superlatives": ("most bills", "fewest bills") },
    "bills-enacted-ti":  { "title": "Laws Enacted", "icon": "bills-resolutions", "superlatives": ("most bills", "fewest bills") },
    "bills-reported":  { "title": "Bills Out of Committee", "icon": "committees", "superlatives": ("most bills", "fewest bills") },
    "bills-with-committee-leaders":  { "title": "Powerful Cosponsors", "icon": "committees", "superlatives": ("most bills", "fewest bills") },
    "bills-with-cosponsors-both-parties":  { "title": "Writing Bipartisan Bills", "icon": "handshake", "superlatives": ("highest % of bills", "lowest % of bills") },
    "bills-with-cosponsors-both-parties-count":  { "title": "Writing Bipartisan Bills", "icon": "handshake", "superlatives": ("most bills", "fewest bills") },
    "bills-with-companion":  { "title": "Working with the {{other_chamber}}", "icon": "handshake", "superlatives": ("most bills", "fewest bills") },
    "cosponsors":  { "title": "Cosponsors", "icon": "congress-members", "superlatives": ("most cosponsors", "fewest cosponsors") },
    "cosponsored":  { "title": "Bills Cosponsored", "icon": "bills-resolutions", "superlatives": ("most bills", "fewest bills") },
    "cosponsored-other-party":  { "title": "Joining Bipartisan Bills", "icon": "handshake", "superlatives": ("most bipartisan", "least bipartisan") },
    "ideology": { "title": "Ideology Score", "icon": "congress-members", "superlatives": ("most conservative", "most liberal") },
    "leadership":  { "title": "Leadership Score", "icon": "congress-members", "superlatives": ("best score", "worst score") },
    "committee-positions":  { "title": "Committee Positions", "icon": "committees", "superlatives": ("highest score", "lowest score") },
    "transparency-bills":  { "title": "Government Transparency", "icon": "open-government", "superlatives": ("most supportive", "least supportive") },
}

def get_cohort_name(key, longform=False):
    if key == "house": return "All Representatives"
    if key == "senate": return "All Senators"
    if key == "party-house-democrat": return "House Democrats"
    if key == "party-house-republican": return "House Republicans"
    if key == "party-house-independent": return "House Independents"
    if key == "party-senate-democrat": return "Senate Democrats"
    if key == "party-senate-republican": return "Senate Republicans"
    if key == "party-senate-independent": return "Senate Independents"
    if key.startswith("house-state-delegation-"): return statenames[key[23:25].upper()] + " Delegation"
    if key == "house-leadership": return "House Party Leaders"
    if key == "senate-leadership": return "Senate Party Leaders"
    if key == "house-freshmen": return "House Freshmen"
    if key == "senate-freshmen": return "Senate Freshmen"
    if key == "house-sophomores": return "House Sophomores"
    if key == "senate-sophomores": return "Senate Sophomores"
    if key == "house-tenyears": return "Serving 10+ Years" + ("" if not longform else " (House)")
    if key == "senate-tenyears": return "Serving 10+ Years" + ("" if not longform else " (Senate)")
    if key == "house-committee-leaders": return "House Cmte. Chairs/RkMembs"
    if key == "senate-committee-leaders": return "Senate Cmte. Chairs/RkMembs"
    if key == "house-competitive-seat": return "Competitive House Seats"
    if key == "house-safe-seat": return "Safe House Seats"
    raise ValueError(key)

def clean_person_stats(stats):
    # Remove ideology if the person has a low leadership score because it indicates bad data.
    # Remove it and leadership if the introduced fewer than ten bills.
    if stats["stats"]["bills-introduced"]["value"] < 10 or stats["stats"]["leadership"]["value"] < .25: del stats["stats"]["ideology"]
    if stats["stats"]["bills-introduced"]["value"] < 10: del stats["stats"]["leadership"]
    for s in list(stats["stats"].keys()):
        if stats["stats"][s]["value"] is None:
            del stats["stats"][s]

    # Delete some dumb other contexts.
    delete = [
        ("committee-positions", "senate-committee-leaders"),
        ("committee-positions", "house-committee-leaders"),
        ("missed-votes", "party-house-democrat"),
        ("missed-votes", "party-house-republican"),
        ("missed-votes", "party-house-independent"),
        ("missed-votes", "party-senate-democrat"),
        ("missed-votes", "party-senate-republican"),
        ("missed-votes", "party-senate-independent"),
        ]
    for statname, stat in stats["stats"].items():
        if "context" not in stat: continue
        for s, c in delete:
            if statname == s and c in stat["context"]:
                del stat["context"][c]

    # put nice names in the context cohorts
    for statname, stat in stats["stats"].items():
        stat["key"] = statname
        stat.update(stat_titles.get(statname, { "title": statname, "icon": "" }))
        stat["title"] = stat["title"].replace("{{other_chamber}}", stat.get("other_chamber",""))

        stat["show_values"] = statname not in ("leadership", "ideology")
        if "superlatives" not in stat: stat["superlatives"] = ("highest", "lowest")

        for cohort, context in stat.get("context", {}).items():
            context["key"] = cohort
            context["name"] = get_cohort_name(cohort)

            # If the person's rank is less than the number of ties, don't use this context
            # for the headline.
            if min(context["rank_ascending"], context["rank_descending"]) < context["rank_ties"]:
                context["use_in_headline"] = False

            # These are never interesting.
            if cohort == "house-safe-seat":
                context["use_in_headline"] = False

            # The percentile we computed off-line is the normal percentile, but it's not good for
            # "Top 20%"-style measures because of ties. Re-do it.
            context["percentile2"] = (min(context["rank_ascending"], context["rank_descending"]) + context["rank_ties"])/float(context["N"])

            if context["rank_ties"] > .25 * context["N"]:
                context["large_tie"] = True

    stats["stats"] = list(stats["stats"].values())

    # Within each statistic, put the context cohorts into the most interesting
    # order for display, which is cohorts from smallest size to largest size.
    #
    # Also choose the context cohort that is best for the statistic's headline,
    # which is the cohort with the most extreme percentile, with ties favoring
    # the larger group.
    def cohort_comparer_for_display(cohort):
        return cohort["N"]
    def cohort_comparer_for_headline(cohort):
        return (min(cohort["percentile"], 100-cohort["percentile"]), -cohort["N"])
    for stat in stats["stats"]:
        if len(stat.get("context", {})) == 0: continue
        stat["context_for_display"] = sorted(stat["context"].values(), key = cohort_comparer_for_display)

        contexts_for_headline = [c for c in stat["context"].values() if c.get("use_in_headline", True)]
        if len(contexts_for_headline) > 0:
            stat["context_for_headline"] = sorted(contexts_for_headline, key = cohort_comparer_for_headline)[0]

    # put the statistics in the most interesting order, which is statistics
    # for which the member has the most extreme values to display.
    def stat_comparer(stat):
        if len(stat.get("context_for_headline", [])) == 0: return (999999, 0) # no contextual info, put last
        c = stat["context_for_headline"]
        return (min(c["rank_ascending"], c["rank_descending"]) + c["rank_ties"]/2.0, -c["N"])
    stats["stats"].sort(key = stat_comparer)
