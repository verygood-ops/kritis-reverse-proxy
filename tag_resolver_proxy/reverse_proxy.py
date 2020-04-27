import logging

import aiohttp.web

from tag_resolver_proxy import process
from tag_resolver_proxy import resolve_tags


logger = logging.getLogger(__name__)


async def webhook_handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
    request_payload = await request.json()
    logger.warning('REQUEST ::::::: %s', request_payload)
    assert request_payload.get('kind') == 'AdmissionReview'

    await process.process_spec(request_payload, resolve_tags.resolve_tags)

    response = await request.app['client'].post(
        f'https://{request.app["upstream_uri"]}{request.path}',
        json=request_payload,
    )
    response_text = (await response.text())
    logger.warning('RESPONSE ::::::: %s', response_text)
    response_webhook = aiohttp.web.Response(text=response_text)
    response_webhook.headers.update(response.headers.copy())
    response_webhook.set_status(response.status)
    return response_webhook


@aiohttp.web.middleware
async def webhook_middleware(request: aiohttp.web.Request, handler) -> aiohttp.web.Response:
    try:
        response = await handler(request)
    except aiohttp.web.HTTPException as exc:
        raise exc
    except AssertionError as exc:
        logger.exception('Processing assertion failed.')
        req = await request.json()
        response = aiohttp.web.json_response(text=process.response_deny(req, msg=str(exc.args[0])))
    if not response.prepared:
        response.headers['SERVER'] = 'vgs-kritis-resolve-tags'
        response.headers['CONTENT-TYPE'] = 'application/json'
    return response

webhook_middleware.__middleware_version__ = 1
