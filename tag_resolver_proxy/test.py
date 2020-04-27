import contextlib
import copy
import json
import os
import time

import asynctest
from asynctest import mock
from aiohttp import client
import yaml

from tag_resolver_proxy.resolve_tags import base, resolve_tags, init_registries
from tag_resolver_proxy.process import response_allow
from tag_resolver_proxy.webapp import app


test_dir = os.path.join(os.path.dirname(__file__), 'test/')
init_registries()


class KritisTest(asynctest.TestCase):

    @contextlib.contextmanager
    def _replace_resolvermeta_resolvers(self, new_resolvers):
        old_resolvers = copy.copy(base.ResolverMeta.resolvers)
        try:
            base.ResolverMeta.resolvers = new_resolvers
            yield
        finally:
            base.ResolverMeta.resolvers = old_resolvers

    def _testfile(self, path):
        """Return location of text fixture file."""
        return os.path.join(test_dir, path)

    def _deployment(self, name):
        """Returns dictionary data sourced from deployment YAML."""
        with open(self._testfile('deployments/{}.yaml'.format(name))) as fl:
            return yaml.load(fl, Loader=yaml.SafeLoader)

    def _admission(self, **deployment_data):
        return {'request': {'uid': self.REQ_UID,
                            'object': deployment_data,
                            'userInfo': {'username': 'test'}},
                'kind': 'AdmissionReview'}


class KritisReverseProxyTest(KritisTest):

    PORT = 8889
    REQ_UID = 'test'
    WHITELIST_REGISTRY = []

    async def _admission_request(self, **deployment_data):
        """Performs an admission request to a backend."""
        resp = await self._client.post('http://127.0.0.1:{}/'.format(self.PORT),
                                       json=self._admission(**deployment_data))
        resp_body = await resp.json()
        resp.close()
        return resp.status, resp_body

    def _assert_admission_response_equal(self, status, msg, response):
        self.assertDictEqual(
            {
                'apiVersion': 'admission.k8s.io/v1beta1',
                'kind': 'AdmissionReview',
                'response': {
                    'uid': self.REQ_UID,
                    'allowed': status,
                    'status': {'message': msg}}}, response)

    async def setUp(self):

        args = mock.Mock()
        args.client_cert_file = self._testfile('kritis.crt')
        args.client_key_file = self._testfile('kritis.key')
        args.client_ca_cert_file = self._testfile('ca.crt')
        args.quay_token_file = self._testfile('quay.token')
        args.upstream_uri = 'https://127.0.0.1/test'
        args.quay_io_organization = ['test', ]
        args.whitelist_registry = self.WHITELIST_REGISTRY

        self._app = app(args)
        self._server = await self.loop.create_server(self._app.make_handler(),
                                                     '127.0.0.1', self.PORT)
        self._client = client.ClientSession()

    async def tearDown(self):
        self._server.close()
        await self._server.wait_closed()


class KritisReverseProxyAdmissionTest(KritisReverseProxyTest):

    async def test_deploy_latest(self):
        status, response = await self._admission_request(**self._deployment('latest'))
        self.assertEqual(200, status)
        self._assert_admission_response_equal(
            False,
            'Can not use latest tag',
            response,
        )

    async def test_deploy_kritis_pass(self):

        with mock.patch('tag_resolver_proxy.resolve_tags.quay_io.QuayIOTagResolver.resolve_tags') as resolve_tags, \
         mock.patch.object(self._app['client'], 'post') as upstream_post:
            resolve_tags.return_value = \
                'quay.io/test/curl@sha256:8bb9ec6e86c87e436402a2952eba54ed636754ba61ddf84d1b6e4844396383c9'
            deployment = self._deployment('kritis_pass')

            upstream_response = response_allow(self._admission(**deployment))
            upstream_response_data = json.loads(upstream_response)
            msg_mock = 'This message is generated during test at {}'.format(str(time.time()))

            upstream_response_data['response']['status']['message'] = msg_mock

            response_mock = mock.CoroutineMock(client.ClientResponse)
            response_mock.status = 200
            response_mock.text = mock.CoroutineMock(return_value=json.dumps(upstream_response_data))

            async def kritis_fake_response(*args, **kwargs):
                etalon_dep = copy.copy(deployment)
                etalon_dep['spec']['template']['spec']['containers'][0]['image'] = \
                    'quay.io/test/curl@sha256:8bb9ec6e86c87e436402a2952eba54ed636754ba61ddf84d1b6e4844396383c9'
                self.assertDictEqual(
                    {'json': {'request':{
                        'uid': 'test',
                        'object': etalon_dep,
                        'userInfo': {'username': 'test'}}, 'kind': 'AdmissionReview'}},
                    kwargs,
                )
                self.assertTupleEqual(('https://https://127.0.0.1/test/',), args)
                return response_mock

            upstream_post.side_effect = kritis_fake_response

            status, response = await self._admission_request(**deployment)

        self.assertEqual(200, status)
        self._assert_admission_response_equal(
            True,
            msg_mock,
            response,
        )


class KritisReverseProxyWhiteListTest(KritisReverseProxyTest):

    WHITELIST_REGISTRY = ['docker.io/whitelisted']

    async def test_deploy_white_list(self):
        with mock.patch('tag_resolver_proxy.resolve_tags.docker_io.DockerIOTagResolver.resolve_tags') as resolve_tags, \
                mock.patch.object(self._app['client'], 'post') as upstream_post:
            resolve_tags.return_value = \
                'docker.io/test/curl@sha256:8bb9ec6e86c87e436402a2952eba54ed636754ba61ddf84d1b6e4844396383c9'
            deployment = self._deployment('white_list')

            status, response = await self._admission_request(**deployment)

        self.assertEqual(200, status)

        self._assert_admission_response_equal(
            True,
            'All images whitelisted',
            response,
        )
        self.assertFalse(resolve_tags.called)
        self.assertFalse(upstream_post.called)


class TagResolverBaseTest(KritisTest):
    container_spec = {'name': 'sleep', 'image': 'curl:3.2.1', 'command': ['/bin/sleep', 'infinity'],
                      'resources': {'requests': {'cpu': '0m', 'memory': '0M'}, 'limits': {'cpu': '0m', 'memory': '0M'}}}

    class NoopTagResolver(base.TagResolver):

        registry_base_uri = 'localhost:5000'

        async def resolve_single_image(self, image_properties: base.ImageProperties) -> str:
            return image_properties.url

    async def test_noop_resolver(self):

        with self._replace_resolvermeta_resolvers({'docker.io': TagResolverBaseTest.NoopTagResolver(None)}):
            spec = copy.copy(self.container_spec)
            await resolve_tags(spec)
            self.assertDictEqual(spec, spec)


class QuayTagResolverTest(KritisTest):
    container_spec = {'name': 'sleep', 'image': 'quay.io/calico/node:v3.14.0-0.dev-55-g785f8b2',
                      'command': ['/bin/sleep', 'infinity'],
                      'resources': {'requests': {'cpu': '0m', 'memory': '0M'}, 'limits': {'cpu': '0m', 'memory': '0M'}}}

    async def test_quay_resolver(self):
        await resolve_tags(self.container_spec)

        # whoa, in-place replace
        self.assertEqual(
            {'name': 'sleep',
             'image': 'quay.io/calico/node@sha256:e8f497444c8d663da3c8a7e4ea58d16f1b130c1122c098b9946cd23dca0f9aab',
             'command': ['/bin/sleep', 'infinity'],
             'resources': {'requests': {'cpu': '0m', 'memory': '0M'}, 'limits': {'cpu': '0m', 'memory': '0M'}}},
            self.container_spec,
        )


class DockerTagResolverTest(KritisTest):
    container_spec = {'name': 'sleep', 'image': 'docker.io/calico/node:v3.14.0-0.dev-55-g785f8b2',
                      'command': ['/bin/sleep', 'infinity'],
                      'resources': {'requests': {'cpu': '0m', 'memory': '0M'}, 'limits': {'cpu': '0m', 'memory': '0M'}}}

    async def test_docker_resolver(self):
        await resolve_tags(self.container_spec)

        # whoa, in-place replace
        self.assertEqual(
            {'name': 'sleep',
             'image': 'docker.io/calico/node@sha256:e8f497444c8d663da3c8a7e4ea58d16f1b130c1122c098b9946cd23dca0f9aab',
             'command': ['/bin/sleep', 'infinity'],
             'resources': {'requests': {'cpu': '0m', 'memory': '0M'}, 'limits': {'cpu': '0m', 'memory': '0M'}}},
            self.container_spec,
        )
