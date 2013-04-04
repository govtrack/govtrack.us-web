#!env/bin/python
import os, sys

try:
	import prctl
	prctl.set_name(os.environ["NAME"] + "-django")
except:
	pass

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
