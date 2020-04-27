import logging
import ssl
import os

import aiohttp.web

import tag_resolver_proxy.arguments
import tag_resolver_proxy.resolve_tags
import tag_resolver_proxy.webapp


NOSSL = os.environ.get('KRITIS_REVERSE_PROXY_NO_SSL', False)


def main():

    args = tag_resolver_proxy.arguments.arg_parser.parse_args()

    ssl_ctx = ssl.SSLContext()
    ssl_ctx.load_cert_chain(args.tls_cert_file, args.tls_key_file)

    tag_resolver_proxy.arguments.auth.update(
        {
            'docker.io': args.docker_auth_file,
            'quay.io': args.quay_token_file,
        }
    )
    tag_resolver_proxy.resolve_tags.init_registries()

    aiohttp.web.run_app(
        tag_resolver_proxy.webapp.app(args),
        port=args.port, ssl_context=ssl_ctx if not NOSSL else None
    )


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
