FROM python:3.6-alpine
LABEL maintainer="Aleksei Zhukov <me@zhukov.al>"

ENV DJANGO_SETTINGS_MODULE=api_demo.settings \
    STATIC_ROOT=/srv/static \
    PYTHONPATH=/srv/app \
    PYTHONUNBUFFERED=1

RUN mkdir -p /srv/app "$STATIC_ROOT" \
 && addgroup -S app \
 && adduser -u 1000 -D -H -h /srv/app -G app -s /sbin/nologin app \
 && chown app:app /srv/app "$STATIC_ROOT" \
 && chmod 0755 /srv/app \
 && chmod 02775 "$STATIC_ROOT" \
 && apk add --no-cache ca-certificates libpq \
 && update-ca-certificates
WORKDIR /srv/app

COPY requirements*.txt /srv/app/
ARG DEBUG=false
ENV DEBUG ${DEBUG}
RUN apk add --no-cache --virtual .build-deps gcc musl-dev postgresql-dev \
 && pip install --no-cache-dir gunicorn \
   -r /srv/app/requirements$([ "$DEBUG" = "true" ] && echo -n ".dev").txt \
 && apk del .build-deps

ARG PROJECT_GIT_VERSION
ENV PROJECT_GIT_VERSION ${PROJECT_GIT_VERSION}
COPY . /srv/app/
RUN touch .env
USER app
RUN SECRET_KEY=static python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["gunicorn", "api_demo.wsgi:application"]
