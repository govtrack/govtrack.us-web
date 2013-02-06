#!script

from bill.models import *
from bill.status import BillStatus

class Died:
	label = "Died"
	sort_order = 999
Died = Died()

T = { }
for b in Bill.objects.filter(congress__in=(110,111), bill_type=BillType.house_bill):
	s0 = BillStatus.introduced
	for d, s, t in b.major_actions:
		s = BillStatus.by_value(s)
		if s0:
			if s.key == "referred":
				# data error
				s = BillStatus.introduced # map to introduced next xycle
				pass
			elif s0.key == "pass_over_house" and s.key == "enacted_signed":
				# data error
				T[(s0, BillStatus.passed_bill)] = T.get((s0, BillStatus.passed_bill), 0) + 1
				T[(BillStatus.passed_bill, s)] = T.get((BillStatus.passed_bill, s), 0) + 1
			else:
				T[(s0, s)] = T.get((s0, s), 0) + 1
		s0 = s
	T[(s0, Died)] = T.get((s0, Died), 0) + 1

import pygraphviz as pgv
G = pgv.AGraph(directed=True, dpi=120, overlap=False, splines=True, bgcolor="transparent")
for (s0, s1), n in sorted(T.items(), key=lambda x : (x[0][0].sort_order, x[0][1].sort_order)):
	nn = sum([v[1] for v in T.items() if v[0][0] == s0])
	print s0.label, s1.label, float(n)/float(nn)
	if s1 == Died: continue # don't draw it
	G.add_node(s0.key, fontsize=8)
	G.add_node(s1.key, fontsize=8)
	G.add_edge(s0.key, s1.key, label="%d%%" % (100*float(n)/float(nn)), fontsize=10)
G.layout(prog='neato')
G.draw("static/markov_model.png")

