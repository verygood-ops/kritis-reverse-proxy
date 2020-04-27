import ssl

import aiohttp
import aiohttp.client
import aiohttp.web

import tag_resolver_proxy.resolve_tags
import tag_resolver_proxy.reverse_proxy
import tag_resolver_proxy.white_list


def app(args) -> aiohttp.web.Application:
    """Construct reverse proxy web application."""

    ssl_ctx_client = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH, cafile=args.client_ca_cert_file)
    ssl_ctx_client.load_cert_chain(args.client_cert_file, args.client_key_file)

    connector = aiohttp.TCPConnector(ssl_context=ssl_ctx_client)

    kritis_client = aiohttp.client.ClientSession(connector=connector)
    kritis_client.verify = ssl_ctx_client

    application = aiohttp.web.Application(
        middlewares=[
            tag_resolver_proxy.reverse_proxy.webhook_middleware,
            tag_resolver_proxy.white_list.create_middleware_from_white_list(args.whitelist_registry),
        ])

    # Application state singletons
    application['client'] = kritis_client
    application['upstream_uri'] = args.upstream_uri

    application.router.add_post('/', tag_resolver_proxy.reverse_proxy.webhook_handler)
    return application
