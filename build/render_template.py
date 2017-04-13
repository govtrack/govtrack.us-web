#!/usr/bin/env python

"""
Render a template with the current set of enviironment variables as the template
context. Send output to standard out.

Usage:
    render_template [INFILE]

INFILE is the name of the input template file. If no infile is provided, stdin
will be used.
"""

import jinja2, os, sys

if __name__ == '__main__':
    # If there is at least one argument, use the first one as the file name
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as infile:
            template = jinja2.Template(infile.read())

    # Otherwise, just use stdin
    else:
        template = jinja2.Template(sys.stdin.read())

    # Render the template
    conf = template.render(**os.environ)

    # Send the output to stdout
    print(conf)
