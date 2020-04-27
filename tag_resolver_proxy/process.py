import json
import logging
import os


logger = logging.getLogger(__name__)


def admission_response(uid, status, message) -> dict:
    return {
        'apiVersion': 'admission.k8s.io/v1beta1',
        'kind': 'AdmissionReview',
        'response': {
            'uid': uid,
            'allowed': status,
            'status': {
                'message': message
            }
        }
    }


async def process_spec(request_payload, callback):
    """Process given admission request specification.
       Check both spec containers and template spec containers.
       Invoke callback on each found container spec.
     """
    spec = request_payload['request']['object']['spec']

    for container_spec in spec.get('containers', []):
        await callback(container_spec)

    if 'template' in spec:
        for container_spec in spec['template']['spec'].get('containers', []):
            await callback(container_spec)


def response_deny(req_body, msg="Prohibited resource for this cluster") -> str:
    req = req_body['request']
    logger.warning("[pid={}] Denying admission for {} in proxy: {}".format(
        os.getpid(),
        req['userInfo']['username'], msg),
    )
    return json.dumps(admission_response(req['uid'], False, msg))


def response_allow(req_body, msg="Whitelisted resource") -> str:
    req = req_body['request']
    logger.warning("[pid={}] Allowing admission for {} in proxy: {}".format(
        os.getpid(),
        req['userInfo']['username'],
        msg,
    ))
    return json.dumps(admission_response(req['uid'], True, msg))


__all__ = ['process_spec', 'response_allow', 'response_deny']
