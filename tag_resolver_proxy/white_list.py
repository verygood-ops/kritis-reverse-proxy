"""Image whitelist helper."""
import logging

import aiohttp.web

from tag_resolver_proxy import process


logger = logging.getLogger(__name__)


class ImageWhitelistResolver:
    """Checks all images in deployment/pod spec.

    If all images belong to whitelisted repository, allows deployment.
    """

    def __init__(self, white_list):
        self._white_list = white_list
        self._all_whitelisted = None

    async def is_whitelisted(self, container_spec):
        """Finds out if all the images in request payload are whitelisted."""

        image = container_spec["image"]

        for repository in self._white_list:
            if image.startswith(repository):
                logger.warning('Image {} belongs to whitelisted '
                               'repository {}'.format(image, repository))
                whitelisted = True
                break
        else:
            whitelisted = False

        self._all_whitelisted = (self._all_whitelisted in (None, True)) and whitelisted

    @property
    def all_images_whitelisted(self) -> bool:
        return bool(self._all_whitelisted)


def create_middleware_from_white_list(white_list):
    """Construct a middleware to check for white listed images."""

    white_list_resolver = ImageWhitelistResolver(white_list or [])

    @aiohttp.web.middleware
    async def whitelist_middleware(request: aiohttp.web.Request, handler) -> aiohttp.web.Response:
        request_payload = await request.json()
        await process.process_spec(request_payload, white_list_resolver.is_whitelisted)
        if white_list_resolver.all_images_whitelisted:
            response = aiohttp.web.json_response(text=process.response_allow(
                request_payload, msg='All images whitelisted'))
        else:
            response = await handler(request)
        return response

    whitelist_middleware.__middleware_version__ = 1

    return whitelist_middleware
