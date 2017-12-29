Payments API sample
===================

This demo project is a work in progress.

At the moment, it doesn't do anything useful.

Setting up
----------

Project uses Django 2.0 and requires Python 3.6.
A full list of dependencies can be found in `requirements.txt`

The project is a pretty standard Django project, so any common approach
to set up development environment should work. The recommended setup
is using Docker and Docker Compose, but it is not a strict requirement,
and any other approach (e.g. virtualenv) should work.

To spin up everything with Compose, run:

    docker-compose up -d
    docker-compose exec web python manage.py migrate

After those two commands, the API will be up and running, available
at http://localhost:8000/

Note, the Compose file is designed for development. The source tree
is be mounted into the container (under `/srv/app`) and gunicorn
is instructed to watch for changes, so code updates would be reflected
immediately. The configuration is *not* suitable for production.

**TODO:** Document image build-time arguments

Interacting with the API
------------------------

**TODO:** TBD

Testing
-------

**TODO:** TBD

    docker run -it --rm -v $(pwd):/project drdaeman/flake8
    docker-compose exec web coverage run manage.py test

Copyright
---------

This is free and unencumbered software released into the public domain.
For more information, see http://unlicense.org/ or the accompanying
`COPYING` file.
