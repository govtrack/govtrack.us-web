# coding=utf-8

from __future__ import print_function

from boto import ec2
from fabric.api import cd, env, put, run, settings, sudo
import os


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Environments
#

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
    """
    Install necesary system packages. This is onen of the few commands whose
    commands actually has to be in the fabfile, since the govtrack code is not
    known to be in the latest state (or on the machine at all) when the command
    gets run.

    Here we install things like git and python, without which we can't proceed.
    """

    if update:
        sudo('apt update')

    sudo('apt install -y git python-virtualenv python-lxml python-openid'
            ' python-oauth2client python-iso8601 python-numpy python-scipy'
            ' python-prctl python-pip libssl-dev'

            # For Solr
            ' openjdk-8-jre jetty8'

            # For PostgreSQL & MySQLclient support
            ' libpq-dev'
            ' libmysqlclient-dev'

            # For the web server
            ' nginx')

    install_ssl_packages(update=update)


def install_ssl_packages(update=True):
    """
    Install the necessary packages for Let's Encrypt SSL certificates.
    """

    if update:
        sudo('add-apt-repository ppa:certbot/certbot --yes')
        sudo('apt-get update')

    sudo('apt-get install certbot --yes')


def configure_ssl():
    sudo('govtrack.us-web/build/configure_ssl.sh')


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
    with cd(folder):
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

        # We don't need psycopg2 in the normal requirements. If postgres isn't
        # installed, the library installation will fail. Leave it out of the
        # list to make development easier.
        sudo('pip install psycopg2')
        sudo('pip install mysqlclient')
        sudo('pip install paypalrestsdk') # installs 'cryptography' package which requires libssl-dev which we skip in local development

        # Similarly, we only need gunicorn if we're serving from a VM.
        sudo('pip install gunicorn')

        # We use honcho to manage the environment.
        sudo('pip install honcho jinja2')
        sudo('pip install honcho-export-systemd')

        # For backing up the data directory...
        sudo('pip install aws')

        # TODO: Create a pipreq.server.txt, and move
        # pipreq.txt to pipreq.app.txt. Then, install
        # pipreq.server.txt here instead of having the
        # requirements piece-meal.


def configure_solr():
    sudo('govtrack.us-web/build/configure_solr.sh')


def configure_postgres():
    sudo('apt install -y postgresql')
    sudo('createdb govtrack', user='postgres')


def setenv(envfile, restart=True):
    """ Upload environment variables to the target server(s). """
    with cd('govtrack.us-web'):
        put(envfile, '.env')

    if restart:
        restart_webserver()


def printenv():
    with cd('govtrack.us-web'):
        return run('cat .env')


def update_db():
    with cd('govtrack.us-web'):
        # NOTE: Will have to use `migrate` after Django upgrade.
        run('honcho run ./manage.py syncdb --noinput')


def update_assets():
    with cd('govtrack.us-web'):
        run('honcho run ./minify')


def bootstrap_data(congress=None):
    with cd('govtrack.us-web'):
        # This seems very chicken-or-egg. Is the purpose of this to bootstrap
        # the existing site with as much data as already exists? Won't the
        # scrapers have to be run anyway?
        run('wget http://www.govtrack.us/data/db/django-fixture-{people,usc_sections,billterms}.json')
        run('honcho run ./manage.py loaddata django-fixture-people.json')
        run('honcho run ./manage.py loaddata django-fixture-usc_sections.json')
        run('honcho run ./manage.py loaddata django-fixture-billterms.json')

        run('honcho run ./parse.py person')
        run('honcho run ./parse.py committee', warn_only=True)  # fails b/c meeting data not available

        run('honcho run build/rsync.sh')
        run('honcho run ./parse.py bill --congress={}'.format(congress))
        run('honcho run ./parse.py vote --congress={}'.format(congress))

        run('honcho run ./manage.py update_index')


def configure_webserver():
    sudo('govtrack.us-web/build/configure_webserver.sh')
    restart_webserver()


def configure_cron():
    sudo('govtrack.us-web/build/configure_cron.sh')


def restart_webserver():
    sudo('govtrack.us-web/build/restart_webserver.sh')


def deploy(envfile=None, branch='master', congress=None):
    pull_or_clone_repo(os.environ['GOVTRACK_WEB_GIT_URL'], 'govtrack.us-web', branch=branch)
    pull_or_clone_repo(os.environ['LEGISLATORS_GIT_URL'], 'congress-legislators')

    install_deps()
    configure_solr()

    if envfile:
        setenv(envfile, restart=False)

    update_db()
    update_assets()

    if congress:
        bootstrap_data(congress=congress)

    configure_cron()
    configure_nginx()
    restart_webserver()


def backup_data():
    sudo('govtrack.us-web/build/backup_data.sh')


def clean():
    run('rm -rf govtrack.us-web')
    run('rm -rf congress-legislators')

