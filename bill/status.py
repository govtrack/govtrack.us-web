"""
``BillStatus`` - list of possible Bill statuses.

Details: http://www.govtrack.us/developers/datadoc.xpd
"""
from common import enum

class BillStatus(enum.Enum):
    """
    List of bill statuses.
    """

    introduced = enum.Item(1, 'Introduced', xml_code='INTRODUCED')
    referred = enum.Item(2, 'Referred to Committee', xml_code='REFERRED')
    reported = enum.Item(3, 'Reported by Committee', xml_code='REPORTED')
    pass_over_house = enum.Item(4, 'Passed House', xml_code='PASS_OVER:HOUSE')
    pass_over_senate = enum.Item(5, 'Passed Senate', xml_code='PASS_OVER:SENATE')
    passed_simpleres = enum.Item(6, 'Resolution Passed', xml_code='PASSED:SIMPLERES')
    passed_constamend = enum.Item(7, 'Resolution Passed', xml_code='PASSED:CONSTAMEND')
    passed_concurrentres = enum.Item(8, 'Resolution Passed', xml_code='PASSED:CONCURRENTRES')
    passed_bill = enum.Item(9, 'Passed Congress', xml_code='PASSED:BILL')
    pass_back_house = enum.Item(10, 'Passed House with Changes', xml_code='PASS_BACK:HOUSE')
    pass_back_senate = enum.Item(11, 'Passed Senate with Changes', xml_code='PASS_BACK:SENATE')
    prov_kill_suspensionfailed = enum.Item(12, 'Failed Under Suspension', xml_code='PROV_KILL:SUSPENSIONFAILED')
    prov_kill_cloturefailed = enum.Item(13, 'Failed Cloture', xml_code='PROV_KILL:CLOTUREFAILED')
    prov_kill_pingpongfail = enum.Item(14, 'Failed to Resolve Differences', xml_code='PROV_KILL:PINGPONGFAIL')
    prov_kill_veto = enum.Item(15, 'Vetoed', xml_code='PROV_KILL:VETO')
    fail_originating_house = enum.Item(16, 'Failed House', xml_code='FAIL:ORIGINATING:HOUSE')
    fail_originating_senate = enum.Item(17, 'Failed Senate', xml_code='FAIL:ORIGINATING:SENATE')
    fail_second_house = enum.Item(19, 'Fail House', xml_code='FAIL:SECOND:HOUSE')
    fail_second_senate = enum.Item(20, 'Fail Senate', xml_code='FAIL:SECOND:SENATE')
    vetoed_override_pass_over_house = enum.Item(21, 'House Overrides Veto', xml_code='VETOED:OVERRIDE_PASS_OVER:HOUSE')
    vetoed_override_pass_over_senate = enum.Item(22, 'Senate Overrides Veto', xml_code='VETOED:OVERRIDE_PASS_OVER:SENATE')
    vetoed_pocket = enum.Item(23, 'Pocket Vetoed', xml_code='VETOED:POCKET')
    vetoed_override_fail_originating_house = enum.Item(24, 'Veto Override Failed in House', xml_code='VETOED:OVERRIDE_FAIL_ORIGINATING:HOUSE')
    vetoed_override_fail_originating_senate = enum.Item(25, 'Veto Override Failed in Senate', xml_code='VETOED:OVERRIDE_FAIL_ORIGINATING:SENATE')
    vetoed_override_fail_second_house = enum.Item(26, 'Veto Override Failed in House', xml_code='VETOED:OVERRIDE_FAIL_SECOND:HOUSE')
    vetoed_override_fail_second_senate = enum.Item(27, 'Veto Override Failed in Senate', xml_code='VETOED:OVERRIDE_FAIL_SECOND:SENATE')
    enacted_signed = enum.Item(28, 'Signed by the President', xml_code='ENACTED:SIGNED')
    enacted_veto_override = enum.Item(29, 'Veto Overridden', xml_code='ENACTED:VETO_OVERRIDE')


