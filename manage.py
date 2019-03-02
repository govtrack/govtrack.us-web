#!python_rand_hash
import os, sys

if "runserver" in sys.argv:
	# Always do this in debug mode.
	os.environ["DEBUG"] = "1"
else:
	# Put the managment command name into the process name.
	try:
		import prctl
		prctl.set_name(sys.argv[1])
	except:
		pass

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
