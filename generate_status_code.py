#!.env/bin/python
from common.system import setup_django
setup_django(__file__)

data = """
INTRODUCED. The bill or resolution was introduced but not yet referred to committee.
REFERRED. The bill or resolution has been referred to committee in the originating chamber and needs committee action to continue.
REPORTED. The bill or resolution was reported by committee in the originating chamber and can now continue with floor debate in the originating chamber.
PASS_OVER:. These are a family of status codes indicating the bill or joint or concurrent resolution has passed favorably in its originating chamber and now goes on to the other chamber. If it failed, the status would be the corresponding FAIL:ORIGINATING:.
PASS_OVER:HOUSE. The bill or resolution passed the House (Senate next).
PASS_OVER:SENATE. The bill or resolution passed the Senate (House next).
PASSED:. These are a family of status codes indicating the bill has passed favorably out of Congress. It is a final status code for resolutions but not for bills. If the vote that PASSED it had gone the other way, the status would be the corresponding FAIL:ORIGINATING: for PASSED:SIMPLERES or FAIL:SECOND: for the others.
PASSED:SIMPLERES. A simple resolution has been passed in its originating chamber. This is the end of the life for a simple resolution.
PASSED:CONSTAMEND. A joint resolution which is proposing an amendment to the Constitution has passed both chambers. This is the end of the life for the resolution in the legislative branch. It goes on subsequently to the states.
PASSED:CONCURRENTRES. A concurrent resolution has been passed by both chambers. This is the end of the life for concurrent resolutions.
PASSED:BILL. A bill or a joint resolution not proposing an amendment to the constitution has been passed by both chambers. It may require a conference committee first, but will eventually go on to the President.
PASS_BACK:. These are a family of status codes that occur when a bill is passed in both chambers, but the second chamber made changes that the first chamber now has to agree to. The bill goes to conference or "ping pong" ensues where the chambers go back and forth between passing the bill until no one makes any more changes. When that finishes, the bill goes into the state PASSED:BILL.
PASS_BACK:HOUSE. The House voted on a Senate bill, making changes and sending it back to the Senate.
PASS_BACK:SENATE. The Senate voted on a House bill, making changes and sending it back to the House.
PROV_KILL:. These are a family of status codes indicating the bill or resolution is provisionally killed, meaning Congress took some action that would often mean the end of life for it (often enough to warrant a status code) but that it could still recover.
PROV_KILL:SUSPENSIONFAILED. The bill or resolution was brought up "under suspension of the rules" and failed that vote. It could be voted on again. If the vote had passed, the status would be one of PASSED, PASS_OVER, etc.
PROV_KILL:CLOTUREFAILED. A cloture vote was taken on the bill or resolution and the vote failed, meaning it was successfully filibustered. If the vote had succeeded, no status would be noted.
PROV_KILL:PINGPONGFAIL. After both chambers have passed a bill or joint/concurrent resolution, if the second chamber made a change the chambers have to resolve their differences. When the second chamber's changes go back to the first chamber for a vote, if the vote fails it's a provisional failure since I think they can try again.
PROV_KILL:VETO. The bill "PASSED:BILL" out of Congress but was vetoed by the President. A veto can be overridden. This status applies until an override attempt is made. If the bill was signed instead, the ENACTED status would follow (but not immediately). A pocket veto is indicated separately with VETOED:POCKET.
FAIL:. These are a family of status codes indicating the end of life of a bill or resolution. (Unlike PROVKILL, these are always final.)
FAIL:ORIGINATING:. This is a subgroup for when a bill or resolution fails in its originating chamber.
FAIL:ORIGINATING:HOUSE. The bill or resolution failed in its originating chamber, the House.
FAIL:ORIGINATING:SENATE. The bill or resolution failed in its originating chamber, the Senate.
FAIL:SECOND. This is a subgroup for when a bill or joint or concurrent resolution fails in the second chamber. It must have passed in the originating chamber to get this far.
FAIL:SECOND:HOUSE. The bill or resolution passed in the Senate but failed in the House.
FAIL:SECOND:SENATE. The bill or resolution passed in the House but failed in the Senate.
OVERRIDE_PASS_OVER:. This is a family of status codes indicating a veto override attempt was successful in the originating chamber, and that it is now up to the second chamber to attempt the override. If the override failed, the status would be one of VETOED:OVERRIDE_FAIL_ORIGINATING:.
OVERRIDE_PASS_OVER:HOUSE. The House (the originating chamber) succeeded at the veto override. It goes on to the Senate next.
OVERRIDE_PASS_OVER:SENATE. The Senate (the originating chamber) succeeded at the veto override. It goes on to the House next.
VETOED:. These are a family of status codes indicating the end of life for a bill that has been vetoed. It is a final status code for a bill.
VETOED:POCKET. This status code is for bills that were pocket-vetoed, meaning the President does not sign the bill and Congress adjourns. The bill does not become law and Congress has no opportunity to override.
VETOED:OVERRIDE_FAIL_ORIGINATING:. This is a subgroup for bills who failed in the veto-override attempt of its originating chamber, which comes first.
VETOED:OVERRIDE_FAIL_ORIGINATING:HOUSE. Veto override failed in the House, the bill's originating chamber. It had not gotten to the Senate yet for an override.
VETOED:OVERRIDE_FAIL_ORIGINATING:SENATE. Veto override failed in the Senate, the bill's originating chamber. It had not gotten to the House yet for an override.
VETOED:OVERRIDE_FAIL_SECOND::. This is a subgroup for bills whose veto was successfully overridden in its originating chamber but failed in the veto-override attempt of the other chamber, which comes second. If the override had passed, the status would shortly be ENACTED:VETO_OVERRIDE.
VETOED:OVERRIDE_FAIL_SECOND:HOUSE. Veto override passed in the Senate (the originating chamber) but failed in the House.
VETOED:OVERRIDE_FAIL_SECOND:SENATE. Veto override passed in the House (the originating chamber) but failed in the Senate.
ENACTED:. These are a family of status codes for bills and joint resolutions not proposing an amendment to the constitution that have been enacted as law. It comes after a short delay between the signature or override and the administrative action to actually make the bill law.
ENACTED:SIGNED. The president signed the bill.
ENACTED:VETO_OVERRIDE. The bill was vetoed but the veto was overridden in both chambers.
"""

def main():
    count = 1
    for line in data.strip().splitlines():
        # Put status slug in first variable, description in second
        slug, description = line.split('.', 1)
        # Ignore subgroups
        if slug.endswith(':'):
            continue
        key = slug.lower().replace(':', '_')
        title = slug.lower().replace(':', ' ').replace('_', ' ').title()
        description = description.strip()
        print "%s = enum.Item(%d, '%s', xml_code='%s')" % (key, count, title, slug)
        count += 1



if __name__ == '__main__':
    main()
