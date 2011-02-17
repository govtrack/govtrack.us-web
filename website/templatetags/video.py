from django import template

register = template.Library()

@register.inclusion_tag('website/video.html', takes_context=True)
def video(context, video):
    return {'MEDIA_URL': context['MEDIA_URL'],
            'box_id': 'video-%d' % id(video),
            'video': video,
            }
