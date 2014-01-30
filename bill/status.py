"""
``BillStatus`` - list of possible Bill statuses.

Details: http://www.govtrack.us/developers/datadoc.xpd
"""
from common import enum

class BillStatus(enum.Enum):
    """
    List of bill statuses.
    """

    introduced = enum.Item(1, 'Introduced', xml_code='INTRODUCED', search_help_text="Introduced but not yet referred to a committee.", sort_order=(0,0))
    referred = enum.Item(2, 'Referred to Committee', xml_code='REFERRED', search_help_text="Referred to a committee in the originating chamber.", sort_order=(0,1))
    reported = enum.Item(3, 'Reported by Committee', xml_code='REPORTED', search_help_text="Reported by a committee in the originating chamber.", sort_order=(0,2))
    pass_over_house = enum.Item(4, 'Passed House', xml_code='PASS_OVER:HOUSE', search_help_text="Passed the House, waiting for a Senate vote next.", sort_order=(1,0))
    pass_over_senate = enum.Item(5, 'Passed Senate', xml_code='PASS_OVER:SENATE', search_help_text="Passed the Senate, waiting for a House vote next.", sort_order=(1,1))
    passed_simpleres = enum.Item(6, 'Agreed To (Simple Resolution)', xml_code='PASSED:SIMPLERES', search_help_text="The simple resolution was agreed to in the chamber in which it was introduced. This is a simple resolution's final status.", sort_order=(1,2))
    passed_constamend = enum.Item(7, 'Agreed To (Constitutional Amendment Proposal)', xml_code='PASSED:CONSTAMEND', search_help_text="The resolution proposing a constitutional amendment was agreed to by both chambers of Congress and goes on to the states.", sort_order=(3,0))
    passed_concurrentres = enum.Item(8, 'Agreed To (Concurrent Resolution)', xml_code='PASSED:CONCURRENTRES', search_help_text="The concurrent resolution was agreed to by both chambers of Congress. This is the final status for concurrent resolutions.", sort_order=(3,1))
    passed_bill = enum.Item(9, 'Enrolled Bill', xml_code='PASSED:BILL', search_help_text="The bill passed both chambers of Congress in identical form and goes on to the President for signing next.", sort_order=(3,2))
    pass_back_house = enum.Item(10, 'Passed House with Changes', xml_code='PASS_BACK:HOUSE', search_help_text="The House passed the bill with changes and sent it back to the Senate.", sort_order=(2,0))
    pass_back_senate = enum.Item(11, 'Passed Senate with Changes', xml_code='PASS_BACK:SENATE', search_help_text="The Senate passed the bill with changes and sent it back to the House.", sort_order=(2,1))
    conference_passed_house = enum.Item(30, 'Conference Report Agreed to by House', xml_code='CONFERENCE:PASSED:HOUSE', search_help_text="The House approved a conference committee report to resolve differences. The Senate must also approve it.", sort_order=(2,2))
    conference_passed_senate = enum.Item(31, 'Conference Report Agreed to by Senate', xml_code='CONFERENCE:PASSED:SENATE', search_help_text="The Senate approved a conference committee report to resolve differences. The House must also approve it.", sort_order=(2,3))
    prov_kill_suspensionfailed = enum.Item(12, 'Failed Under Suspension', xml_code='PROV_KILL:SUSPENSIONFAILED', search_help_text="Passage failed under \"suspension of the rules\" but can be voted on again.", sort_order=(4,0))
    prov_kill_cloturefailed = enum.Item(13, 'Failed Cloture', xml_code='PROV_KILL:CLOTUREFAILED', search_help_text="Cloture (ending a filibuster) failed but can be tried again.", sort_order=(4,1))
    prov_kill_pingpongfail = enum.Item(14, 'Failed to Resolve Differences', xml_code='PROV_KILL:PINGPONGFAIL', search_help_text="The House or Senate failed to resolve differences with the other chamber but can try again.", sort_order=(4,2))
    prov_kill_veto = enum.Item(15, 'Vetoed (No Override Attempt)', xml_code='PROV_KILL:VETO', search_help_text="Vetoed by the President but the veto can be overridden.", sort_order=(5,4))
    fail_originating_house = enum.Item(16, 'Failed House', xml_code='FAIL:ORIGINATING:HOUSE', search_help_text="Failed in the House, its originating chamber", sort_order=(5,0))
    fail_originating_senate = enum.Item(17, 'Failed Senate', xml_code='FAIL:ORIGINATING:SENATE', search_help_text="Failed in the Senate, its originating chamber", sort_order=(5,1))
    fail_second_house = enum.Item(19, 'Passed Senate, Failed House', xml_code='FAIL:SECOND:HOUSE', search_help_text="Passed the Senate but failed in the House.", sort_order=(5,2))
    fail_second_senate = enum.Item(20, 'Passed House, Failed Senate', xml_code='FAIL:SECOND:SENATE', search_help_text="Passed the House but failed in the Senate.", sort_order=(5,3))
    override_pass_over_house = enum.Item(21, 'Vetoed & House Overrides (Senate Next)', xml_code='OVERRIDE_PASS_OVER:HOUSE', search_help_text="The House passed a veto override, sending it to the Senate.", sort_order=(6,0))
    override_pass_over_senate = enum.Item(22, 'Vetoed & Senate Overridess (House Next)', xml_code='OVERRIDE_PASS_OVER:SENATE', search_help_text="The Senate passed a veto override, sending it to the House.", sort_order=(6,1))
    vetoed_pocket = enum.Item(23, 'Pocket Vetoed', xml_code='VETOED:POCKET', search_help_text="Pocket vetoed by the President.", sort_order=(5,5))
    vetoed_override_fail_originating_house = enum.Item(24, 'Vetoed & Override Failed in House', xml_code='VETOED:OVERRIDE_FAIL_ORIGINATING:HOUSE', search_help_text="The House's attempt to override a veto failed.", sort_order=(5,6))
    vetoed_override_fail_originating_senate = enum.Item(25, 'Vetoed & Override Failed in Senate', xml_code='VETOED:OVERRIDE_FAIL_ORIGINATING:SENATE', search_help_text="The Senate's attempt to override a veto failed.", sort_order=(5,7))
    vetoed_override_fail_second_house = enum.Item(26, 'Vetoed & Override Passed Senate, Failed in House', xml_code='VETOED:OVERRIDE_FAIL_SECOND:HOUSE', search_help_text="The Senate overrode the veto but the House's attempt to override the veto failed.", sort_order=(5,8))
    vetoed_override_fail_second_senate = enum.Item(27, 'Vetoed & Override Passed House, Failed in Senate', xml_code='VETOED:OVERRIDE_FAIL_SECOND:SENATE', search_help_text="The House overrode the veto but the Senate's attempt to override the veto failed.", sort_order=(5,9))
    enacted_signed = enum.Item(28, 'Signed by the President', xml_code='ENACTED:SIGNED', search_help_text="Enacted by a signature of the President.", sort_order=(3,3))
    enacted_veto_override = enum.Item(29, 'Veto Overridden', xml_code='ENACTED:VETO_OVERRIDE', search_help_text="Enacted by a veto override.", sort_order=(3,4))

    # indicates statuses whose descriptions are clear that the bill is no longer active,
    # other statuses are displayed as "Died: " for bills from previous congresses.
    final_status_obvious = (passed_simpleres, passed_constamend, passed_concurrentres, prov_kill_veto, fail_originating_house, fail_originating_senate, fail_second_house, fail_second_senate, vetoed_pocket, enacted_signed, enacted_veto_override, vetoed_override_fail_originating_house, vetoed_override_fail_originating_senate, vetoed_override_fail_second_house, vetoed_override_fail_second_senate, passed_bill)

    # indicates a bill at the end of its life cycle and passed
    final_status_passed_bill = (enacted_signed, enacted_veto_override)
    final_status_passed_resolution = (passed_simpleres, passed_constamend, passed_concurrentres)
    final_status_passed = tuple(list(final_status_passed_bill) + list(final_status_passed_resolution))
    
    # indicates a bill at the end of its life cycle and failed
    final_status_failed = (fail_originating_house, fail_originating_senate, fail_second_house, fail_second_senate, vetoed_pocket, vetoed_override_fail_originating_house, vetoed_override_fail_originating_senate, vetoed_override_fail_second_house, vetoed_override_fail_second_senate)

    # all final statuses
    final_status = tuple(list(final_status_passed_bill) + list(final_status_passed_resolution) + list(final_status_failed))

	# the statuses that are basically just introduction
    introduced_statuses = (introduced, referred)

def get_bill_status_string(is_current, status):
    # Returns a string with two %'s in it, one for the bill noun ("bill"/"resolution")
    # and one for the status date.
    
    # Some status messages depend on whether the bill is current:
    if is_current:
        if status == "INTRODUCED":
            status = "This %s is in the first stage of the legislative process. It was introduced into Congress on %s. It will typically be considered by committee next."
        elif status == "REFERRED":
            status = "This %s was assigned to a congressional committee on %s, which will consider it before possibly sending it on to the House or Senate as a whole."
        elif status == "REPORTED":
            status = "The committees assigned to this %s sent it to the House or Senate as a whole for consideration on %s."
        elif status == "PASS_OVER:HOUSE":
            status = "This %s passed in the House on %s and goes to the Senate next for consideration."
        elif status == "PASS_OVER:SENATE":
            status = "This %s passed in the Senate on %s and goes to the House next for consideration."
        elif status == "PASSED:BILL":
            status = "This %s was passed by Congress on %s and goes to the President next."
        elif status == "PASS_BACK:HOUSE":
            status = "This %s passed in the Senate and the House, but the House made changes and sent it back to the Senate on %s."
        elif status == "PASS_BACK:SENATE":
            status = "This %s has been passed in the House and the Senate, but the Senate made changes and sent it back to the House on %s."
        elif status == "CONFERENCE:PASSED:HOUSE":
            status = "The conference report for this %s was agreed to in the House on %s. The Senate must also approve it. A conference report resolves the differences in the bill in each chamber."
        elif status == "CONFERENCE:PASSED:SENATE":
            status = "The conference report for this %s was agreed to in the Senate on %s. The House must also approve it. A conference report resolves the differences in the bill in each chamber."
        elif status == "PROV_KILL:SUSPENSIONFAILED":
            status = "This %s is provisionally dead due to a failed vote on %s under a fast-track procedure called \"suspension.\" It may or may not get another vote."
        elif status == "PROV_KILL:CLOTUREFAILED":
            status = "This %s is provisionally dead due to a failed vote for cloture on %s. Cloture is required to move past a Senate filibuster or the threat of a filibuster and takes a 3/5ths vote. In practice, most bills must pass cloture to move forward in the Senate."
        elif status == "PROV_KILL:PINGPONGFAIL":
            status = "This %s is provisionally dead due to a failed attempt to resolve differences between the House and Senate versions, on %s."
        elif status == "PROV_KILL:VETO":
            status = "This %s was vetoed by the President on %s. The bill is dead unless Congress can override it."
        elif status == "OVERRIDE_PASS_OVER:HOUSE":
            status = "After a presidential veto of the %s, the House succeeeded in an override on %s. It goes to the Senate next."
        elif status == "OVERRIDE_PASS_OVER:SENATE":
            status = "After a presidential veto of the %s, the Senate succeeded in an override on %s. It goes to the House next."
    
    else: # Bill is not current.
        if status == "INTRODUCED" or status == "REFERRED" or status == "REPORTED":
            status = "This %s was introduced on %s, in a previous session of Congress, but was not enacted."
        elif status == "PASS_OVER:HOUSE":
            status = "This %s was introduced in a previous session of Congress and was passed by the House on %s but was never passed by the Senate."
        elif status == "PASS_OVER:SENATE":
            status = "This %s was introduced in a previous session of Congress and was passed by the Senate on %s but was never passed by the House."
        elif status == "PASSED:BILL":
            status = "This %s was passed by Congress on %s but was not enacted before the end of its Congressional session. (It is possible this bill is waiting for the signature of the President.)"
        elif status in ("PASS_BACK:HOUSE", "PASS_BACK:SENATE"):
            status = "This %s was introduced in a previous session of Congress and though it was passed by both chambers on %s it was passed in non-identical forms and the differences were never resolved."
        elif status in ("CONFERENCE:PASSED:HOUSE", "CONFERENCE:PASSED:SENATE"):
            status = "This %s was introduced in a previous session of Congress and though it was passed by both chambers, it was passed in non-identical form and only one chamber approved a conference report to resolve the differences."
        elif status == "PROV_KILL:SUSPENSIONFAILED" or status == "PROV_KILL:CLOTUREFAILED" or status == "PROV_KILL:PINGPONGFAIL":
            status = "This %s was introduced in a previous session of Congress but was killed due to a failed vote for cloture, under a fast-track vote called \"suspension\", or while resolving differences on %s."
        elif status == "PROV_KILL:VETO":
            status = "This %s was vetoed by the President on %s and Congress did not attempt an override before the end of the Congressional session."
        elif status == "OVERRIDE_PASS_OVER:HOUSE" or status == "OVERRIDE_PASS_OVER:SENATE":
            status = "This %s was vetoed by the President and Congress did not finish an override begun on %s before the end of the Congressional session."
        
    # Some status messages do not depend on whether the bill is current.
    
    if status == "PASSED:SIMPLERES":
        status = "This simple %s was agreed to on %s. That is the end of the legislative process for a simple resolution."
    elif status == "PASSED:CONSTAMEND":
        status = "This %s proposing a constitutional amendment was agreed to by both chambers of Congress on %s and goes to the states for consideration next."
    elif status == "PASSED:CONCURRENTRES":
        status = "This concurrent %s was agreed to by both chambers of Congress on %s. That is the end of the legislative process for concurrent resolutions. They do not have the force of law."
    elif status == "FAIL:ORIGINATING:HOUSE":
        status = "This %s failed in the House on %s."
    elif status == "FAIL:ORIGINATING:SENATE":
        status = "This %s failed in the Senate on %s."
    elif status == "FAIL:SECOND:HOUSE":
        status = "After passing in the Senate, this %s failed in the House on %s."
    elif status == "FAIL:SECOND:SENATE":
        status = "After passing in the House, this %s failed in the Senate on %s."
    elif status == "VETOED:OVERRIDE_FAIL_ORIGINATING:HOUSE" or status == "VETOED:OVERRIDE_FAIL_SECOND:HOUSE":
        status = "This %s was vetoed. The House attempted to override the veto on %s but failed."
    elif status == "VETOED:OVERRIDE_FAIL_ORIGINATING:SENATE" or status == "VETOED:OVERRIDE_FAIL_SECOND:SENATE":
        status = "This %s was vetoed. The Senate attempted to override the veto on %s but failed."
    elif status == "VETOED:POCKET":
        status = "This %s was pocket vetoed on %s."
    elif status == "ENACTED:SIGNED":
        status = "This %s was enacted after being signed by the President on %s."
    elif status == "ENACTED:VETO_OVERRIDE":
        status = "This %s was enacted after a congressional override of the President's veto on %s."
    
    return status   

