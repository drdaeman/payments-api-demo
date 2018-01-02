Payments API sample
===================

This is a demo project, not a full-fledged implementation that can
be used in production somewhere. See the "what's missing" section
below for some particular omissions.

It demonstrates use of Django and Django REST Framework to implement
a simple accounting-like API service.

There are three type of entities that the API manages:

- Owners. They're basically just labels, only having a name.
- Accounts. Account belongs to a single owner and holds funds
  in a single specific currency.
- Payments. Payments can be deposits, withdrawals and transfers
  between two accounts.

After the project is up and running, check the index page
for the documentation.

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

Dockerfile has a `DEBUG` build-time argument defined, that can be set
to either `true` (lowercase only) or `false`. The created image
defaults' depend on this.

For non-Docker, the default is `DEBUG=False`.

Configuration
-------------

The project uses [`django-environ`][django-environ] for settings, using
both environment variables and reading an `.env` file, if present.

With `DEBUG=True` if `SECRET_KEY` is not provided an ephemeral one
would be generated for the convenience.

Interacting with the API
------------------------

The API is RESTful and can be used with any HTTP client that can send
`GET`, `POST` and `PATCH` requests. There is CoreJSON/CoreAPI schema
support, so it can be also used with any tooling that understands this
standard.

The autogenerated documentation is interactive and allows to run test
queries right from the browser.

What's missing
--------------

This is a demo project and a lot of stuff is missing.
Here is a (incomplete) list:

- There is no authentication, authorization or access controls.
  Basically, any client can do just about anything.
- The project could benefit from a QuickCheck-style testing, generating
  lots of accounts and transactions and then ensuring the balances
  sum up correctly.
- The only documentation is auto-generated. Something like MkDocs and
  a good hand-written documentation would be a good idea.
- Unconfirmed payments do not expire. While it is not possible
  to overdraft funds, it would be cleanlier if uncommitted transactions
  would be garbage collected after a while.
- The code is currently incompatible with `BrowsableAPIRenderer` and
  it is disabled, with project relying on CoreAPI instead.
- There is no API versioning and "v1/" is just a hardcoded prefix.
- There is no logging at the moment.

There are also some "TODO" comments in the code.

Testing
-------

The code is formatted to conform to PEP8 and some other common rules,
like import ordering. To lint, you can use:

    docker run -it --rm -v $(pwd):/project drdaeman/flake8

This project uses [Django's standard approach to testing][testing].
With the Docker Compose setup described above, tests can be ran with:

    docker-compose exec web coverage run manage.py test

(Then run `docker-compose exec web coverage report -m` for the report)

Copyright
---------

This is free and unencumbered software released into the public domain.
For more information, see http://unlicense.org/ or the accompanying
`COPYING` file.


[testing]: https://docs.djangoproject.com/en/2.0/topics/testing/tools/
[django-environ]: https://django-environ.readthedocs.io/en/latest/