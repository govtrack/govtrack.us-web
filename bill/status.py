"""
``BillStatus`` - list of possible Bill statuses.

Details: http://www.govtrack.us/developers/datadoc.xpd
"""
from common import enum

class BillStatus(enum.Enum):
    """
    List of bill statuses.
    """

    introduced = enum.Item(1, 'Introduced', xml_code='INTRODUCED', search_help_text="Introduced but not yet referred to a committee.")
    referred = enum.Item(2, 'Referred to Committee', xml_code='REFERRED', search_help_text="Referred to a committee in the originating chamber.")
    reported = enum.Item(3, 'Reported by Committee', xml_code='REPORTED', search_help_text="Reported by a committee in the originating chamber.")
    pass_over_house = enum.Item(4, 'Passed House', xml_code='PASS_OVER:HOUSE', search_help_text="Passed the House, waiting for a Senate vote next.")
    pass_over_senate = enum.Item(5, 'Passed Senate', xml_code='PASS_OVER:SENATE', search_help_text="Passed the Senate, waiting for a House vote next.")
    passed_simpleres = enum.Item(6, 'Passed (Simple Resolution)', xml_code='PASSED:SIMPLERES', search_help_text="The simple resolution was passed (its final status).")
    passed_constamend = enum.Item(7, 'Passed (Constitutional Amendment)', xml_code='PASSED:CONSTAMEND', search_help_text="The resolution proposing a constitutional amendment passed both chambers of Congress and goes on to the states.")
    passed_concurrentres = enum.Item(8, 'Passed (Concurrent Resolution)', xml_code='PASSED:CONCURRENTRES', search_help_text="The concurrent resolution passed both chambers of Congress (its final status).")
    passed_bill = enum.Item(9, 'Passed Congress', xml_code='PASSED:BILL', search_help_text="The bill passed both chambers of Congress in identical form and goes on to the President for signing next.")
    pass_back_house = enum.Item(10, 'Passed House with Changes', xml_code='PASS_BACK:HOUSE', search_help_text="The House passed the bill with changes and sent it back to the Senate.")
    pass_back_senate = enum.Item(11, 'Passed Senate with Changes', xml_code='PASS_BACK:SENATE', search_help_text="The Senate passed the bill with changes and sent it back to the House.")
    prov_kill_suspensionfailed = enum.Item(12, 'Failed Under Suspension', xml_code='PROV_KILL:SUSPENSIONFAILED', search_help_text="Passage failed under \"suspension of the rules\" but can be voted on again.")
    prov_kill_cloturefailed = enum.Item(13, 'Failed Cloture', xml_code='PROV_KILL:CLOTUREFAILED', search_help_text="Cloture (ending a filibuster) failed but can be tried again.")
    prov_kill_pingpongfail = enum.Item(14, 'Failed to Resolve Differences', xml_code='PROV_KILL:PINGPONGFAIL', search_help_text="The House or Senate failed to resolve differences with the other chamber but can try again.")
    prov_kill_veto = enum.Item(15, 'Vetoed', xml_code='PROV_KILL:VETO', search_help_text="Vetoed by the President but the veto can be overridden.")
    fail_originating_house = enum.Item(16, 'Failed House', xml_code='FAIL:ORIGINATING:HOUSE', search_help_text="Failed in the House, its originating chamber")
    fail_originating_senate = enum.Item(17, 'Failed Senate', xml_code='FAIL:ORIGINATING:SENATE', search_help_text="Failed in the Senate, its originating chamber")
    fail_second_house = enum.Item(19, 'Passed Senate, Failed House', xml_code='FAIL:SECOND:HOUSE', search_help_text="Passed the Senate but failed in the House.")
    fail_second_senate = enum.Item(20, 'Passed House, Failed Senate', xml_code='FAIL:SECOND:SENATE', search_help_text="Passed the House but failed in the Senate.")
    override_pass_over_house = enum.Item(21, 'House Overrides Veto', xml_code='OVERRIDE_PASS_OVER:HOUSE', search_help_text="The House passed a veto override, sending it to the Senate.")
    override_pass_over_senate = enum.Item(22, 'Senate Overrides Veto', xml_code='OVERRIDE_PASS_OVER:SENATE', search_help_text="The Senate passed a veto override, sending it to the House.")
    vetoed_pocket = enum.Item(23, 'Pocket Vetoed', xml_code='VETOED:POCKET', search_help_text="Pocket vetoed by the President.")
    vetoed_override_fail_originating_house = enum.Item(24, 'Veto Override Failed in House', xml_code='VETOED:OVERRIDE_FAIL_ORIGINATING:HOUSE', search_help_text="The House's attempt to override a veto failed.")
    vetoed_override_fail_originating_senate = enum.Item(25, 'Veto Override Failed in Senate', xml_code='VETOED:OVERRIDE_FAIL_ORIGINATING:SENATE', search_help_text="The Senate's attempt to override a veto failed.")
    vetoed_override_fail_second_house = enum.Item(26, 'Veto Override Passed House, Failed in House', xml_code='VETOED:OVERRIDE_FAIL_SECOND:HOUSE', search_help_text="The Senate overrode the veto but the House's attempt to override the veto failed.")
    vetoed_override_fail_second_senate = enum.Item(27, 'Veto Override Passed Senate, Failed in Senate', xml_code='VETOED:OVERRIDE_FAIL_SECOND:SENATE', search_help_text="The House overrode the veto but the Senate's attempt to override the veto failed.")
    enacted_signed = enum.Item(28, 'Signed by the President', xml_code='ENACTED:SIGNED', search_help_text="Enacted by a signature of the President.")
    enacted_veto_override = enum.Item(29, 'Veto Overridden', xml_code='ENACTED:VETO_OVERRIDE', search_help_text="Enacted by a veto override.")

    final_status = (passed_simpleres, passed_constamend, passed_concurrentres, prov_kill_veto, fail_originating_house, fail_originating_senate, fail_second_house, fail_second_senate, vetoed_pocket, enacted_signed, enacted_veto_override)
