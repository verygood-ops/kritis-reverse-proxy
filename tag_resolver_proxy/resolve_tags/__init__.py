from .base import ResolverMeta


async def resolve_tags(container_spec):
    image = container_spec["image"]

    properties = ResolverMeta.for_image_url(image)

    container_spec['image'] = await properties.resolver.resolve_tags(properties)


def init_registries():
    # Import all known resolver implementations after auth is available
    from tag_resolver_proxy.resolve_tags.docker_io import DockerIOTagResolver
    from tag_resolver_proxy.resolve_tags.quay_io import QuayIOTagResolver


__all__ = ['resolve_tags', 'init_registries']
