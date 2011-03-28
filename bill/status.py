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
    referred = enum.Item(2, 'Referred', xml_code='REFERRED')
    reported = enum.Item(3, 'Reported', xml_code='REPORTED')
    pass_over_house = enum.Item(4, 'Pass Over House', xml_code='PASS_OVER:HOUSE')
    pass_over_senate = enum.Item(5, 'Pass Over Senate', xml_code='PASS_OVER:SENATE')
    passed_simpleres = enum.Item(6, 'Passed Simpleres', xml_code='PASSED:SIMPLERES')
    passed_constamend = enum.Item(7, 'Passed Constamend', xml_code='PASSED:CONSTAMEND')
    passed_concurrentres = enum.Item(8, 'Passed Concurrentres', xml_code='PASSED:CONCURRENTRES')
    passed_bill = enum.Item(9, 'Passed Bill', xml_code='PASSED:BILL')
    pass_back_house = enum.Item(10, 'Pass Back House', xml_code='PASS_BACK:HOUSE')
    pass_back_senate = enum.Item(11, 'Pass Back Senate', xml_code='PASS_BACK:SENATE')
    prov_kill_suspensionfailed = enum.Item(12, 'Prov Kill Suspensionfailed', xml_code='PROV_KILL:SUSPENSIONFAILED')
    prov_kill_cloturefailed = enum.Item(13, 'Prov Kill Cloturefailed', xml_code='PROV_KILL:CLOTUREFAILED')
    prov_kill_pingpongfail = enum.Item(14, 'Prov Kill Pingpongfail', xml_code='PROV_KILL:PINGPONGFAIL')
    prov_kill_veto = enum.Item(15, 'Prov Kill Veto', xml_code='PROV_KILL:VETO')
    fail_originating_house = enum.Item(16, 'Fail Originating House', xml_code='FAIL:ORIGINATING:HOUSE')
    fail_originating_senate = enum.Item(17, 'Fail Originating Senate', xml_code='FAIL:ORIGINATING:SENATE')
    fail_second = enum.Item(18, 'Fail Second', xml_code='FAIL:SECOND')
    fail_second_house = enum.Item(19, 'Fail Second House', xml_code='FAIL:SECOND:HOUSE')
    fail_second_senate = enum.Item(20, 'Fail Second Senate', xml_code='FAIL:SECOND:SENATE')
    override_pass_over_house = enum.Item(21, 'Override Pass Over House', xml_code='OVERRIDE_PASS_OVER:HOUSE')
    override_pass_over_senate = enum.Item(22, 'Override Pass Over Senate', xml_code='OVERRIDE_PASS_OVER:SENATE')
    vetoed_pocket = enum.Item(23, 'Vetoed Pocket', xml_code='VETOED:POCKET')
    vetoed_override_fail_originating_house = enum.Item(24, 'Vetoed Override Fail Originating House', xml_code='VETOED:OVERRIDE_FAIL_ORIGINATING:HOUSE')
    vetoed_override_fail_originating_senate = enum.Item(25, 'Vetoed Override Fail Originating Senate', xml_code='VETOED:OVERRIDE_FAIL_ORIGINATING:SENATE')
    vetoed_override_fail_second_house = enum.Item(26, 'Vetoed Override Fail Second House', xml_code='VETOED:OVERRIDE_FAIL_SECOND:HOUSE')
    vetoed_override_fail_second_senate = enum.Item(27, 'Vetoed Override Fail Second Senate', xml_code='VETOED:OVERRIDE_FAIL_SECOND:SENATE')
    enacted_signed = enum.Item(28, 'Enacted Signed', xml_code='ENACTED:SIGNED')
    enacted_veto_override = enum.Item(29, 'Enacted Veto Override', xml_code='ENACTED:VETO_OVERRIDE')
