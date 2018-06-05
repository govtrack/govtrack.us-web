from django import forms

from vote.models import Vote, CongressChamber, VoteCategory

YEARS = [('', 'Any')] + [(x, str(x)) for x in range(2011, 1788, -1)]
CHAMBERS = [('', 'Any')] + CongressChamber.choices()
CATEGORIES = [('', 'Any')] + VoteCategory.choices()

YEAR_FIELD = forms.ChoiceField(choices=YEARS, required=False)

class VoteFilterForm(forms.Form):
    year = forms.ChoiceField(choices=YEARS, required=False)
    chamber = forms.ChoiceField(choices=CHAMBERS, required=False)
    category = forms.ChoiceField(choices=CATEGORIES, required=False)

    def filter(self, qs):
        data = self.cleaned_data
        if data['year']:
            qs = qs.filter(created__year=data['year'])
        if data['chamber']:
            qs = qs.filter(chamber=data['chamber'])
        if data['category']:
            qs = qs.filter(category=data['category'])
        return qs
