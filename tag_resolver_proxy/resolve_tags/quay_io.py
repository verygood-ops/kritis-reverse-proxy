from tag_resolver_proxy.resolve_tags import base
from tag_resolver_proxy.resolve_tags.base import ImageProperties


def quay_repository_url(organization: str, software: str) -> str:
    return f'https://quay.io/api/v1/repository/{organization}/{software}'


class QuayIOTagResolver(base.TagResolver):

    registry_base_uri = 'quay.io'

    async def resolve_single_image(self, image_props: ImageProperties) -> str:
        """Resolve single image digest using Quay API."""

        tags = (
            await (
                await self.client.get(quay_repository_url(image_props.org, image_props.software))
            ).json()
        ).get('tags', {})

        tag_metadata = tags.get(image_props.tag)

        assert tag_metadata, f'Unknown image {image_props.url}'
        assert tag_metadata['manifest_digest'], 'Unknown Quay response format'

        return f'quay.io/{image_props.org}/{image_props.software}@{tag_metadata["manifest_digest"]}'

    def get_client_headers(self):
        headers = super().get_client_headers()
        if self.token:
            headers.update({'Authorization': f'Bearer {self.token}'})
        return headers
