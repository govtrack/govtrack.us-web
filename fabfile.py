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

def local_web_vm():
    env.user = os.environ['FAB_WEB_USER']
    env.hosts = os.environ['FAB_WEB_HOST'].split(',')


def ec2_web_cluster():
    """Borrowed with ♥ from http://joet3ch.com/blog/2012/01/18/fabric-ec2/"""

    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')

    env.user = os.environ['FAB_WEB_USER']
    env.key_filename = os.environ['FAB_WEB_KEY_FILENAME']
    env.conftype = os.environ['FAB_WEB_CONFTYPE']
    env.project = os.environ['FAB_WEB_PROJECT']

    ec2conn = ec2.connection.EC2Connection(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    web_group = ec2conn.get_all_security_groups(groupnames=['web'])
    for i in web_group[0].instances():
        hostname = i.__dict__['public_dns_name']
        if hostname is not '':
            env.hosts.append(hostname)


def local_solr_vm():
    pass


def ec2_solr_cluster():
    pass


def local_worker_vm():
    pass


def ec2_worker_cluster():
    pass


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Set-up commands
#

def install_packages(update=True):
    if update:
        sudo('apt update')

    sudo('apt install git python-virtualenv python-lxml python-openid \
              python-oauth2client python-iso8601 python-numpy python-scipy \
              python-prctl libssl-dev')


def pull_source():
    with cd('govtrack.us-web'):
        return run('git pull')


def clone_source():
    return run('git clone --recursive {url}'.format(url=os.environ['PROJECT_GIT_URL']))


def pull_or_clone_source():
    # Try pulling as if the repo already exists
    with settings(warn_only=True):
        result = pull_source()
    # If it doesn't, clone from github
    if result.failed:
        clone_source()


def deploy_web():
    pull_or_clone_source()


def clean_web():
    run('rm -rf govtrack.us-web')
