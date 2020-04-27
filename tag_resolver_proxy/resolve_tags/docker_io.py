import base64
import logging
import urllib.parse

from tag_resolver_proxy.resolve_tags import base

logger = logging.getLogger(__name__)


class DockerIOTagResolver(base.TagResolver):

    registry_base_uri = 'docker.io'
    api_base_uri = f'https://index.{registry_base_uri}'
    auth_url = 'https://auth.docker.io'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.token:
            # --docker-auth-file must contain <username>:<password>
            self._auth_str = base64.b64encode(self.token).decode()

    def login_uri(self, image_props: base.ImageProperties) -> str:
        query = urllib.parse.urlencode(
            {
                'scope': f'repository:{image_props.org}/{image_props.software}:pull',
                'service': 'registry.docker.io',
            },
        )
        return f'{self.auth_url}/token?{query}'

    async def ensure_docker_io_temporary_token(self, image_props: base.ImageProperties) -> str:
        self.ensure_client()
        response = await self.client.get(
            url=self.login_uri(image_props),
            headers={
                'Content-Type': 'application/json',
            }
        )
        response_data = await response.json()
        temp_token = response_data.get('token')
        assert temp_token, 'Can not authenticate with Docker.io'
        return temp_token

    async def resolve_single_image(self, image_props: base.ImageProperties) -> str:
        """Resolve single image digest using Docker Hub API."""

        token = await self.ensure_docker_io_temporary_token(image_props)

        digest = (
            await self.client.get(
                f'{self.api_base_uri}'
                f'/v2/{image_props.org}/{image_props.software}/manifests/{image_props.tag}',
                headers={
                    'Accept': 'application/vnd.docker.distribution.manifest.v2+json',
                    'Authorization': f'Bearer {token}',
                }
            )
        ).headers.get('Docker-Content-Digest')

        assert digest, 'Can not retrieve docker image digest'

        return f'docker.io/{image_props.org}/{image_props.software}@{digest}'

    def get_client_headers(self):
        headers = super().get_client_headers()
        if self.token:
            headers.update({'Authorization': f'Basic {self._auth_str}'})
        return headers
