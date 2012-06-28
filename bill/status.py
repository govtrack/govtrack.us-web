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
    passed_simpleres = enum.Item(6, 'Passed (Simple Resolution)', xml_code='PASSED:SIMPLERES', search_help_text="The simple resolution was passed (its final status).", sort_order=(1,2))
    passed_constamend = enum.Item(7, 'Passed (Constitutional Amendment)', xml_code='PASSED:CONSTAMEND', search_help_text="The resolution proposing a constitutional amendment passed both chambers of Congress and goes on to the states.", sort_order=(3,0))
    passed_concurrentres = enum.Item(8, 'Passed (Concurrent Resolution)', xml_code='PASSED:CONCURRENTRES', search_help_text="The concurrent resolution passed both chambers of Congress (its final status).", sort_order=(3,1))
    passed_bill = enum.Item(9, 'At President', xml_code='PASSED:BILL', search_help_text="The bill passed both chambers of Congress in identical form and goes on to the President for signing next.", sort_order=(3,2))
    pass_back_house = enum.Item(10, 'Passed House with Changes', xml_code='PASS_BACK:HOUSE', search_help_text="The House passed the bill with changes and sent it back to the Senate.", sort_order=(2,0))
    pass_back_senate = enum.Item(11, 'Passed Senate with Changes', xml_code='PASS_BACK:SENATE', search_help_text="The Senate passed the bill with changes and sent it back to the House.", sort_order=(2,1))
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
    final_status_obvious = (passed_simpleres, passed_constamend, passed_concurrentres, prov_kill_veto, fail_originating_house, fail_originating_senate, fail_second_house, fail_second_senate, vetoed_pocket, enacted_signed, enacted_veto_override, vetoed_override_fail_originating_house, vetoed_override_fail_originating_senate, vetoed_override_fail_second_house, vetoed_override_fail_second_senate)

    # indicates a bill at the end of its life cycle and passed
    final_status_passed_bill = (enacted_signed, enacted_veto_override)
    final_status_passed_resolution = (passed_simpleres, passed_constamend, passed_concurrentres)
    final_status_passed = tuple(list(final_status_passed_bill) + list(final_status_passed_resolution))
    
    # indicates a bill at the end of its life cycle and failed
    final_status_failed = (fail_originating_house, fail_originating_senate, fail_second_house, fail_second_senate, vetoed_pocket, vetoed_override_fail_originating_house, vetoed_override_fail_originating_senate, vetoed_override_fail_second_house, vetoed_override_fail_second_senate)

    # all final statuses
    final_status = tuple(list(final_status_passed_bill) + list(final_status_passed_resolution) + list(final_status_failed))

