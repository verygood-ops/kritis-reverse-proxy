import abc
import asyncio
import collections
import contextlib
import logging
import os

import aiohttp

import tag_resolver_proxy.arguments

logger = logging.getLogger(__name__)
ImageProperties = collections.namedtuple('ImageProperties',
                                         ['url', 'domain', 'org', 'software', 'tag', 'resolver'])


class ResolverMeta(type):

    resolvers = {}

    def __new__(mcs, *args, **kwargs):
        cls = super(ResolverMeta, mcs).__new__(mcs, *args, **kwargs)
        base_uri = getattr(cls, 'registry_base_uri', None)
        if base_uri and not isinstance(base_uri, property):
            mcs.resolvers[base_uri] = cls(tag_resolver_proxy.arguments.auth.get(base_uri))
        return cls

    @classmethod
    def for_image_url(mcs, image_url) -> ImageProperties:
        """Finds a suitable resolver for given image URL.

        Parses necessary metadata from URL. Picks right resolves.

        Bundles metadata with URL into ImageProperties object.

        Performs initial validation for image URL.
        """
        if ':' in image_url:
            repo, tag = image_url.split(':')
        else:
            tag = 'latest'
            repo = None

        assert tag != 'latest', 'Can not use latest tag'

        parts = repo.split('/')

        if len(parts) == 1:
            # docker.io/library
            domain, org = 'docker.io', 'library'
            software = parts[0]
        elif len(parts) == 2:
            # docker.io/{org}
            domain = 'docker.io'
            software, org = parts
        elif len(parts) == 3:
            domain, org, software = parts
        else:
            raise AssertionError(f'An image URL must have '
                                 f'format hub/org/software')

        assert domain in mcs.resolvers, f'Unknown Docker registry: {domain}'

        return ImageProperties(
            image_url,
            domain=domain,
            org=org,
            software=software,
            tag=tag,
            resolver=mcs.resolvers[domain],
        )


class TagResolver(metaclass=ResolverMeta):
    """Resolves tags against remote Quay or Docker repository."""

    def __init__(self, token_file):
        self.client = None
        self.tag_digest_cache = {}
        self.tags_inflight = {}

        if token_file and os.path.exists(token_file):
            with open(token_file, 'r') as tkn:
                self.token = tkn.read().strip()
                logger.info('Loaded token file')
        else:
            self.token = None

    @property
    @abc.abstractmethod
    def registry_base_uri(self) -> str:
        """A registry base URI."""
        raise NotImplementedError()

    @abc.abstractmethod
    async def resolve_single_image(self, image_properties: ImageProperties) -> str:
        """Get an image URL for given dictionary."""
        raise NotImplementedError()

    def ensure_client(self):
        """Create HTTP client for interacting with Docker registry."""
        if self.client is None:
            self.client = aiohttp.client.ClientSession(
                headers=self.get_client_headers(),
            )

    def get_client_headers(self):
        """Retrieve headers for HTTP client authentication."""
        return {
            'User-Agent': 'kritis-reverse-proxy',
        }

    @contextlib.asynccontextmanager
    async def guard_event(self, image_url):
        """Guard event for image URL, protecting tag cache of simultaneous access."""

        self.tags_inflight[image_url] = asyncio.Event()
        try:
            yield
        finally:
            self.tags_inflight.pop(image_url).set()

    async def resolve_tags(self, image_props: ImageProperties):
        """Resolve tags for given k8s container spec.

        Cache the value for further usage.
        kritis-reverse-proxy assumes you don't use latest, and tags are immutable.

        :param image_props: Image IRL metadata properties, extracted into named tuple.
        """
        image = image_props.url

        if '@sha256' in image:
            logger.warning('Tag already resolved for %s', image)
            resolved = image
        else:

            if image not in self.tag_digest_cache:

                if image in self.tags_inflight:
                    await self.tags_inflight[image].wait()
                    resolved = self.tag_digest_cache[image]
                else:
                    async with self.guard_event(image):
                        self.ensure_client()
                        resolved = await self.resolve_single_image(image_props)

                self.tag_digest_cache[image] = resolved
            else:
                resolved = self.tag_digest_cache[image]

        return resolved
