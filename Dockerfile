FROM python:3.8.2-alpine3.11 AS build

RUN apk add py3-pip python3-dev musl-dev gcc make openssl openssl-dev libffi libffi-dev

WORKDIR /app
RUN python3 -m venv venv
COPY requirements.txt /app/requirements.txt
RUN venv/bin/python3 -m pip install -r /app/requirements.txt
RUN apk del gcc make python3-dev musl-dev libffi-dev openssl-dev

COPY tag_resolver_proxy /app/tag_resolver_proxy

FROM python:3.8.2-alpine3.11

RUN apk add openssl libffi

COPY --from=build /app /app
WORKDIR /app
ENV PYTHONPATH=/app

ENTRYPOINT ["/app/venv/bin/python3", "-m", "tag_resolver_proxy"]
