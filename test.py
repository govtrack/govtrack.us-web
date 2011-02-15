#!.env/bin/python
import gdata.youtube.service
import gdata.service
from common.system import setup_django
setup_django(__file__)
from django.conf import settings

try:
    username = 'SenatorOrrinHatch2'
    service = gdata.youtube.service.YouTubeService()
    service.client_id = 'govtrack.us-crawler'
    service.developer_key = settings.YOUTUBE_API_KEY
    uri = 'http://gdata.youtube.com/feeds/api/users/%s/uploads' % username
    feed = service.GetYouTubeVideoFeed(uri)
    print len(feed.entry)
except gdata.service.RequestError, ex:
    print 'Error', ex
