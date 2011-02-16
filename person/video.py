import gdata.youtube.service
import gdata.service
from lxml import etree
import urllib

from django.conf import settings

def get_youtube_channel(username):
    """
    Fetch latest video from person's youtube channel.

    Documentation:  http://code.google.com/intl/ru/apis/youtube/1.0/developers_guide_python.html
    """

    service = gdata.youtube.service.YouTubeService()
    service.client_id = 'govtrack.us-crawler'
    service.developer_key = settings.YOUTUBE_API_KEY
    uri = 'http://gdata.youtube.com/feeds/api/users/%s/uploads' % username
    try:
        feed = service.GetYouTubeVideoFeed(uri)
    except gdata.service.RequestError:
        return None
    else:
        response = {
            'url': 'http://www.youtube.com/user/%s' % username,
            'latest_video': None,
        }
        if len(feed.entry):
            entry = feed.entry[0]
            response['latest_video'] = {
                'title': entry.media.title.text,
                'published': entry.published.text,
                'url': entry.media.player.url,
                'thumbnail': entry.media.thumbnail[0].url,
            }
        return response


def get_sunlightlabs_video(bioguideid):
    """
    Fetch latest video about person from api.realtimecongress.com.

    Documentation: http://services.sunlightlabs.com/docs/Real_Time_Congress_API/
    """

    url = 'http://api.realtimecongress.org/api/v1/videos.xml?apikey=%s&bioguide_ids=%s' % (
        settings.SUNLIGHTLABS_API_KEY, bioguideid)
    try:
        data = urllib.urlopen(url).read()
    except IOError, ex:
        logging.error(ex)
        return None
    else:
        tree = etree.fromstring(data)
