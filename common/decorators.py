# Copied from https://bitbucket.org/lorien/django-common by @lorien.
# Django-common provides useful shortcuts for developing django projects

from django.shortcuts import render

def render_to(template):
    """
    Render view's output with ``template`` using ``RequestContext``.

    If decorated view returns dict object then render the template.

    If decorated view returns non dict object then just return this object.

    Args:
        :template: path to template
    
    Example::

        @render_to('blog/index.html')
        def post_list(request):
            posts = Post.objects.all()
            return {'posts': posts,
                    }
    """

    def decorator(func):
        def wrapper(request, *args, **kwargs):
            output = func(request, *args, **kwargs)
            if not isinstance(output, dict):
                return output
            else:
                return render(request, template, output)
        return wrapper
    return decorator

