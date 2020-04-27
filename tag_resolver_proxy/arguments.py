import argparse


arg_parser = argparse.ArgumentParser()
arg_parser.add_argument('--tls-key-file', help='TLS cert file to run server with')
arg_parser.add_argument('--tls-cert-file', help='TLS cert file to run server with')
arg_parser.add_argument('--client-key-file', help='A client key file to use for auth')
arg_parser.add_argument('--client-cert-file', help='A client cert file to use for auth')
arg_parser.add_argument('--client-ca-cert-file', help='A client cert file to use for auth')

arg_parser.add_argument('--docker-auth-file', help='A path file containing '
                                                   'Docker username and access token/password')
arg_parser.add_argument('--quay-token-file', help='A file containing Quay access token')

arg_parser.add_argument('--port', help='A port to listen TLS', type=int, default=9443)

arg_parser.add_argument('--upstream-uri', help='Upstream admission webhook server URL',
                        type=str, default='localhost')
arg_parser.add_argument('--whitelist-registry',
                        help='Whitelist given registry, bypassing all checks',
                        action='append', default=[])

auth = {}


__all__ = ['arg_parser', 'auth']
