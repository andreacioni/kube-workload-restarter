import sys
from kubernetes import client
import datetime
import pytz
import time
import logging
import re
import signal

from .util import parse_duration
from .log import log


RESTARTER_ANNOTATION = 'restarter/after'


def _restart_deployment(api: client.AppsV1Api, deployment):
    # update `spec.template.metadata` section
    # to add `kubectl.kubernetes.io/restartedAt` annotation
    deployment.spec.template.metadata.annotations = {
        "kubectl.kubernetes.io/restartedAt": datetime.datetime.utcnow()
        .replace(tzinfo=pytz.UTC)
        .isoformat()
    }

    # patch the deployment
    api.patch_namespaced_deployment(
        name=deployment.metadata.name, namespace="default", body=deployment
    )

    log.info("\tdeployment '%s' restarted.\n" %
             deployment.metadata.name)


def _get_last_replicaset_with_selectors(api: client.AppsV1Api, namespace: str, selectors: list):
    replicaset_list = api.list_namespaced_replica_set(
        namespace, label_selector=','.join(selectors))

    log.debug('\tfound %d replica/s' %
              (len(replicaset_list.items)))

    if len(replicaset_list.items) == 0:
        return None

    sorted_list = sorted(replicaset_list.items, key=lambda rs:
                         rs.metadata.creation_timestamp)
    recent_replicaset = sorted_list[len(sorted_list)-1]

    log.debug('\tmost recent replicaset is: %s (rev: %s, created at: %s)' %
              (recent_replicaset.metadata.name, recent_replicaset.metadata.annotations['deployment.kubernetes.io/revision'], recent_replicaset.metadata.creation_timestamp))

    return recent_replicaset


def handle_deployment(api: client.AppsV1Api, namespace: str, deployment):
    try:
        name = deployment.metadata.name
        if RESTARTER_ANNOTATION in deployment.metadata.annotations:
            restart_after = parse_duration(
                deployment.metadata.annotations[RESTARTER_ANNOTATION])
            log.debug('deployment "%s" has to be restarted after: %s (%ds)',
                      name, deployment.metadata.annotations[RESTARTER_ANNOTATION], restart_after)

            selectors = [f"{key}={value}" for key,
                         value in deployment.spec.selector.match_labels.items()]

            replica_set = _get_last_replicaset_with_selectors(
                api, namespace, selectors)

            now = datetime.datetime.now().timestamp()
            current_age = now - replica_set.metadata.creation_timestamp.timestamp()
            if current_age > restart_after:
                log.info('\tdeployment need to be restarted')
                _restart_deployment(api, deployment)
            else:
                log.debug(
                    '\tno need to restart (current uptime is %ds, target is: %ds)' % (current_age, restart_after))
        else:
            log.debug('deployment "%s" has no "%s" annotation, skipping...',
                      name, RESTARTER_ANNOTATION)
    except:
        log.exception("failed processing deployment: %s" %
                      name)


def get_all_deployments_in_namespace(api: client.AppsV1Api, namespace: str):
    resp = api.list_namespaced_deployment(namespace)

    if len(resp.items) == 0:
        log.debug('no deployments found in namespace')
    else:
        log.debug('found %d deployments:' % len(resp.items))

        for i in resp.items:
            log.debug('  - %s', i.metadata.name)

    return resp.items
