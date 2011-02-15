#!.env/bin/python
"""
Sandbox for various tests.
"""
from common.system import setup_django
setup_django(__file__)
from person.video import get_sunlightlabs_video

def main():
    "All things happen here"

    get_sunlightlabs_video('H001032')


if __name__ == '__main__':
    main()
