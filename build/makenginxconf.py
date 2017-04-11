#!/usr/bin/env python

import jinja2, os

with open('conf/nginx.conf.template') as infile:
    template = jinja2.Template(infile.read());

conf = template.render(**os.environ)

print(conf)
