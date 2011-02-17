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
                item = {
                    'title': entry.media.title.text,
                    'published': parse_time(entry.published.text),
                    'url': entry.media.player.url,
                    'thumbnail': entry.media.thumbnail[0].url,
                }
                response['videos'].append(item)
    return response


@cached(60 * 30)
def get_sunlightlabs_videos(bioguideid):
    """
    Fetch latest video about person from api.realtimecongress.com.

    Documentation:
     * http://services.sunlightlabs.com/docs/Real_Time_Congress_API/
     * http://services.sunlightlabs.com/docs/Real_Time_Congress_API/videos/
    """

    # Fetch 5 latest videos
    response = {'videos': []}

    url = 'http://api.realtimecongress.org/api/v1/videos.xml?apikey=%s&bioguide_ids=%s&per_page=5' % (
        settings.SUNLIGHTLABS_API_KEY, bioguideid)

    @cached(60 * 30)
    def fetch(url):
        return urllib.urlopen(url).read()

    try:
        data = fetch(url)
    except IOError, ex:
        pass
    else:
        open('log', 'w').write(data)
        tree = etree.fromstring(data)
        for video in tree.xpath('//video'):
            # Find mp4 file. Also there could be mp3 and mms - ignore them.
            # MMS - is sort of playlist and JWPlayer raise an error when
            # tries to play it.
            try:
                url = video.xpath('.//mp4')[0].text
            except IndexError:
                pass
            else:
                # Video node could be split on several clips. Try to find the clip
                # with required bioguidedid. If it found then provide in the response
                # the time offset of this clip
                video_start = parse_time(video.xpath('./pubdate')[0].text)
                try:
                    clip = video.xpath('.//clip//bioguide_id[text()="%s"]/../..' % bioguideid)[0]
                except IndexError, ex:
                    offset = 0
                else:
                    clip_start = parse_time(clip.xpath('./time')[0].text)
                    offset = (clip_start - video_start).seconds
                item = {
                    'published': video_start,
                    'url': url,
                    'offset': offset,
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
