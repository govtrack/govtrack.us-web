Deployment Instructions
=======================

## Initial installation

Before beginning, you should have the appropriate infrastructure set up on AWS.
You'll want to create your database of choice on RDS (packages will be installed
to support MySQL and PostgreSQL), and one or more EC2 machines. Create these
machines in a security group named "govtrack-vm".

Copy `.env.deploy.template` to `.env`, and uncomment the `AWS_...` variables and
fill in appropriate values to access your EC2 server(s).

The project uses Fabric to transfer files and run commands on remote servers. To
install the initial set of packages on the EC2 server(s), run:

    honcho run fab ec2_vm install_packages

In case it is ever needed for reference, the following article was helpful in
getting Solr 4.x set up with Jetty. There were some adjustments because of
package changes in Ubuntu 16.04:
https://www.digitalocean.com/community/tutorials/how-to-install-solr-on-ubuntu-14-04


## Management/Deployment commands

The primary command for deploying the application is:

    honcho run [-e .env.deploy...] \
      fab [ec2_vm | local_vm] \
        deploy[:envfile=...,congress=...,branch=...]

To break this down:

* `honcho` is a process environment manager. It uses files `.env` files to set
  up the environment, much like `foreman`. If a `.env` file exists in the
  current directory, the default environment will be read from it. This file
  should contain key/value pairs, separated by =, with one key/value pair per
  line. See more about `.env` files [below](Environment variables).

  There are two `.env` templates in the project folder:

  * `.env.deploy.template` -- for environment variables necessary to deploy
    from a local machine.
  * `.env.server.template` -- for environment variables that a remote machine
    needs to know about.

  You should copy each of these and fill in the appropriate values. Though
  `honcho` will use the file named `.env` in the working directory by default,
  you can specify a different file by using the `-e` flag.

* `fab` is the Fabric command runner. It is used to orchestrate the running of
  commands on local and remote machines. The first argument specifies the
  remote target. There are two targets specified in the `fabfile.py` for this
  project:

  * `ec2_vm` -- One or more EC2 VMs that live in the security group `govtrack-vm`
  * `local_vm` -- A virtual machine set up through, e.g., virtual box that is
    accessible by IP address.

  The next argument is the Fabric command to run. All of the commands are
  defined in `fabfile.py`. In this case, the `deploy` command relies on a number
  of others.

  The deploy command accepts three optional arguments:

  * `envfile` -- if you want to update the environment variables used on the
    server
  * `branch` -- if you want to deploy from a branch besides `master`
  * `congress` -- if you want to download the members and bills pertaining to
    a congressional session

For example, to update the environment variables on a machine, and load data for
the 115th congress, you could run:

    honcho run -e .env.deploy.prod \
      fab ec2_vm deploy:envfile=.env.server.prod,congress=115

In the fabric file there are a number of commands that are executed as part of
the deploy. Any of these can be run as standalone commands themselves:

* `install_deps`
* `configure_solr`
* `upload_settings:envfile=...`
* `update_db`
* `update_assets`
* `bootstrap_data:congress=...`


## Environment variables

The application is configured through environment variables. There are a number
of different ways to set environment variables, but the easiest is as part of
the deployment process.

To use fabric to set your environment variables, first copy the
*.env.server.template* file in the root folder to a new file (you can name the
new file anything, but for the purposes of these instructions it will be called
*.env.server.prod*):

    cp .env.server.template .env.server.prod

Edit the *.env.server.prod* file, replacing all of the variables with the
appropriate production values. You should back this file up somewhere; you will
need it if you want to update variable values later.

Next, deploy the variables to the server using fabric:

    honcho run fab ec2_vm upload_settings:envfile=.env.server.prod

If there is a webserver server running, this will restart it as well.


## Infrastructure

For deploying to AWS, the following setup is recommended:

* A t2.large EC2 machine with a 100GB+ attached volume.
* A security-group for the EC2 machine named `govtrack-vm`, with inbound ports
  open for HTTP, HTTPS, and SSH. If you want to explore the Solr admin, you will
  also need to create a custom inbound rule for TCP over port 8983.
* An RDS database with PostgreSQL or MySQL. In your `.env.server` file, set the
  `DATABASE_URL` variable to the connection string for this server, according to
  the guidelines at https://github.com/kennethreitz/dj-database-url#url-schema.
* An S3 bucket for storing backups of the `data/` directory. The name of this
  bucket should be entered in the `S3_BACKUPS_BUCKET` environment variable.