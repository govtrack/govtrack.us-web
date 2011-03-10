from datetime import datetime

from django.test import TestCase

from vote.models import Vote, CongressChamber, VoteSource

class VoteTestCase(TestCase):
    def test_category(self):
        # Check that <category> value which is not
        # listed in VoteCategory enum
        # does not confuse Django ORM

        vote = Vote(congress=2011, session='2011',
                    chamber=CongressChamber.senate,
                    number=10,
                    source=VoteSource.random_value(),
                    created=datetime.now(),
                    vote_type='asdf',
                    category='zzz',
                    question='asdf',
                    required='asdf',
                    result='asdf')
        vote.save()

        self.assertEqual(vote.category, u'zzz')
        self.assertEqual(vote.get_category_display(), u'zzz')
