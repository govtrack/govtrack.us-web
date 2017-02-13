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

    sudo('apt install -y git python-virtualenv python-lxml python-openid \
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


def setenv(vars):
    """
    Read environment variables from string and update on remote machine. Restart
    the services on the machine afterward.
    """
    pass
