#!script

# When was Congress in session?
#
# Forgive me for generating SVG without a proper library.

from datetime import date
from us import get_all_sessions

bar_width = 3.5
height = 20.0

print("""<svg xmlns="http://www.w3.org/2000/svg" version="1.1">""")

def break_session(s1, s2):
	for y in range(s1.year, s2.year+1):
		yield (s1 if y == s1.year else date(y, 1, 1)), (s2 if y == s2.year else date(y, 12, 31))

for cong, sess, s1, s2 in get_all_sessions():
	clr = "rgb(200,200,200)"
	if (cong % 2) == 0: clr = "rgb(100,100,100)"
	
	for startdate, enddate in break_session(s1, s2):
		print("""<rect x="%f" y="%f" width="%f" height="%f" style="fill:%s; stroke-width:%f; stroke:rgb(0,0,0)" />""" % (
			(startdate.year - 1789) * bar_width,
			(startdate - date(startdate.year, 1, 1)).days/365.0 * height,
			.5 * bar_width,
			(enddate - startdate).days/365.0*5.0 * height,
			clr,
			bar_width * .05,
			))

print("""</svg>""")

