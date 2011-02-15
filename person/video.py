import gdata.youtube.service
import gdata.service

from django.conf import settings

def get_youtube_channel(username):
    service = gdata.youtube.service.YouTubeService()
    service.client_id = 'govtrack.us-crawler'
    service.developer_key = settings.YOUTUBE_API_KEY
    uri = 'http://gdata.youtube.com/feeds/api/users/%s/uploads' % username
    try:
        feed = service.GetYouTubeVideoFeed(uri)
    except gdata.service.RequestError:
        return None
    else:
        response = {'latest_video': None}
        if len(feed.entry):
            entry = feed.entry[0]
            response['latest_video'] = {
                'title': entry.media.title.text,
                'published': entry.published.text,
                'url': entry.media.player.url,
                'thumbnail': entry.media.thumbnail[0].url,
            }
        return response
