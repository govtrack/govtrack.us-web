from GChartWrapper import Pie

from django import template

register = template.Library()

@register.simple_tag
def vote_totals_pie(vote):
    """
    Prepare data to display the Total Vote Couns Pie.
    """

    items = vote.totals()['options']
    yes_count = sum(x['count'] for x in items if x.get('yes') == True)
    no_count = sum(x['count'] for x in items if x.get('no') == True)
    other_count = sum(x['count'] for x in items if\
                      x.get('no') == None and x.get('yes') == None)
    g = Pie([yes_count, no_count, other_count])
    g.type('pie')
    g.title('All votes')
    g.legend('Yes', 'No', 'No Vote')
    g.size(200, 200)
    g.color('0000CC','CC0000', '00AAAA')
    return g.img()


@register.simple_tag
def vote_pie(yes_count, no_count, other_count):
    """
    Prepare data to display the Party Votes Pie.
    """
    
    g = Pie([yes_count, no_count, other_count])
    g.type('pie')
    g.size(50, 50)
    g.color('0000CC','CC0000', '00AAAA')
    return g.img()
