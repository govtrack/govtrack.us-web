from common.decorators import render_to

from committee.models import CommitteeMeeting

from datetime import datetime, timedelta

@render_to("event_calendar/calendar.html")
def calendar(request):
	now = datetime.now()
	today = datetime(now.year, now.month, now.day, 0, 0, 0, 0)
	committee_meetings = CommitteeMeeting.objects.order_by("occurs_at", "committee").filter(occurs_at__gte=today)

	print dir(committee_meetings[0].committee)

	return {
		"committee_meetings": committee_meetings,
	}
