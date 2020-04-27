kritis-reverse-proxy
====================

## Why ?

Kritis currently (as of v.0.2.2) supports only digest-styled tags, formatted like quay.io/verygoodsecurity/software@sha256:sha256string
- https://github.com/grafeas/kritis/issues/351

FluxCD currently supports only "classic" tags, formatted like quay.io/verygoodsecurity/software:version
- https://github.com/fluxcd/flux/issues/885

A sidecar reverse proxy for Kritis, resolving tags through Docker Hub or Quay.

## Build

`docker build -t tag_resolver_proxy .`

## Run
`docker run -it tag_resolver_proxy --help`

## Test
`make test`

## Additional checks.

Before checking against Grafeas attestations API, 
this proxy verifies the following:

- latest tag is not used

