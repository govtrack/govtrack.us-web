from datetime import datetime, timedelta
import gdata.youtube.service
import gdata.service
from lxml import etree
import urllib

from cache_utils.decorators import cached
from django.conf import settings

@cached(60 * 30)
def get_youtube_videos(username):
    """
    Fetch latest video from person's youtube channel.

    Documentation:  http://code.google.com/intl/ru/apis/youtube/1.0/developers_guide_python.html
    """

    service = gdata.youtube.service.YouTubeService()
    service.client_id = 'govtrack.us-crawler'
    service.developer_key = settings.YOUTUBE_API_KEY
    uri = 'http://gdata.youtube.com/feeds/api/users/%s/uploads' % username

    response = {
        'url': 'http://www.youtube.com/user/%s' % username,
        'videos': []
    }
    try:
        feed = service.GetYouTubeVideoFeed(uri)
    except gdata.service.RequestError:
        pass
    else:
        if len(feed.entry):
            for entry in feed.entry[:5]:
                thumb = None
                for node in entry.media.thumbnail:
                    if int(node.width) == 120:
                        thumb = node.url
                item = {
                    'title': entry.media.title.text,
                    'published': parse_time(entry.published.text),
                    'url': entry.media.player.url,
                    'thumbnail': thumb,
                }
                response['videos'].append(item)
    return response


def parse_time(timestr):
    timestr = timestr.lower()
    try:
        return datetime.strptime(timestr, '%Y-%m-%dt%H:%M:%S:00z') - timedelta(hours=5)
    except ValueError:
        try:
            return datetime.strptime(timestr, '%Y-%m-%dt%H:%Mz') - timedelta(hours=5)
        except ValueError:
            try:
                return datetime.strptime(timestr, '%Y-%m-%dt%H:%M:00z') - timedelta(hours=5)
            except ValueError:
                return datetime.strptime(timestr, '%Y-%m-%dt%H:%M:%S.000z') - timedelta(hours=5)
