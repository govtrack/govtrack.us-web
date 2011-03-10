from GChartWrapper import Pie

from django import template

register = template.Library()

@register.simple_tag
def vote_totals_pie(vote):
    totals = vote.totals()
    counts = (totals[0]['count'], totals[1]['count'], sum(x['count'] for x in totals[2:]))
    g = Pie(counts)
    g.type('pie')
    g.title('All votes')
    g.legend('Yes', 'No', 'No Vote')
    g.size(200, 200)
    g.color('0000CC','CC0000', '00AAAA')
    return g.img()
