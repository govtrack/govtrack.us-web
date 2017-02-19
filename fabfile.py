# coding=utf-8

from __future__ import print_function

from boto import ec2
from fabric.api import cd, env, run, settings, sudo
import os


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Environments for web, worker, and solr in local VM, and EC2 clusters
#
#                |  Local VM  |  EC2 Cluster  |
#                |------------+---------------|
#           web  |            |               |
#                |------------+---------------|
#        worker  |            |               |
#                |------------+---------------|
#          solr  |            |               |
#                +------------+---------------+

def local_vm():
    env.user = os.environ['VM_USER']
    env.hosts = os.environ['VM_HOST'].split(',')


def ec2_vm():
    """
    Target a single ec2 machine, or a cluster of machines, all with the group
    name "govtrack-vm", for deployment.

    Borrowed with ♥ from http://joet3ch.com/blog/2012/01/18/fabric-ec2/
    """

    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')

    env.user = os.environ['VM_USER']
    env.key_filename = os.environ['VM_KEY_FILENAME']

    ec2conn = ec2.connection.EC2Connection(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    web_group = ec2conn.get_all_security_groups(groupnames=['govtrack-vm'])
    for i in web_group[0].instances():
        hostname = i.__dict__['public_dns_name']
        if hostname is not '':
            env.hosts.append(hostname)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Set-up commands
#

def install_packages(update=True):
    if update:
        sudo('apt update')

    sudo('apt install -y git python-virtualenv python-lxml python-openid'
            ' python-oauth2client python-iso8601 python-numpy python-scipy'
            ' python-prctl python-pip libssl-dev'

            # For Solr
            ' openjdk-8-jre jetty8')


def pull_repo(folder, branch='master'):
    with cd(folder):
        result = run('git fetch --all')

        if result.failed:
            return result

        run('git checkout {branch}'.format(branch=branch))
        run('git reset --hard origin/{branch}'.format(branch=branch))
        return result


def clone_repo(repo_url, folder, branch='master'):
    result = run('git clone --recursive {url} {folder}'.format(url=repo_url, folder=folder))
    run('git checkout {branch}'.format(branch=branch))
    return result


def pull_or_clone_repo(repo_url, folder, branch='master'):
    # Try pulling as if the repo already exists
    with settings(warn_only=True):
        result = pull_repo(folder, branch=branch)
    # If it doesn't, clone from github
    if result.failed:
        clone_repo(repo_url, folder, branch=branch)


def install_deps():
    with cd('govtrack.us-web'):
        sudo('pip install --upgrade -r ./build/pipreq.txt')


def configure_solr():
    with cd('govtrack.us-web'):
        return run('./build/buildsolr.sh')


def upload_settings():
    pass


def update_db():
    with cd('govtrack.us-web'):
        run('./manage.py syncdb --noinput')


def update_assets():
    with cd('govtrack.us-web'):
        run('./minify')


def bootstrap_data():
    with cd('govtrack.us-web'):
        # This seems very chicken-or-egg. Is the purpose of this to bootstrap
        # the existing site with as much data as already exists? Won't the
        # scrapers have to be run anyway?
        run('wget http://www.govtrack.us/data/db/django-fixture-{people,usc_sections,billterms}.json')
        run('./manage.py loaddata django-fixture-people.json')
        run('./manage.py loaddata django-fixture-usc_sections.json')
        run('./manage.py loaddata django-fixture-billterms.json')

        run('./parse.py committee')

        run('build/rsync.sh')
        run('./parse.py bill --congress=113 --disable-index --disable-events')
        run('./parse.py vote --congress=113 --disable-index --disable-events')


def deploy(settings=None):
    pull_or_clone_repo(os.environ['GOVTRACK_WEB_GIT_URL'], 'govtrack.us-web', branch='vm-deployment')
    pull_or_clone_repo(os.environ['LEGISLATORS_GIT_URL'], 'congress-legislators')

    install_deps()
    configure_solr()

    if settings:
        upload_settings()

    update_db()
    update_assets()
    bootstrap_data()


def clean():
    run('rm -rf govtrack.us-web')
    run('rm -rf congress-legislators')


def setenv(vars):
    """
    Read environment variables from string and update on remote machine. Restart
    the services on the machine afterward.
    """
    pass
