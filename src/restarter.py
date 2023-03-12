import sys
from kubernetes import config, client
import datetime
import pytz
import time
import logging
import re

LOOP_INTERVAL_SEC = 30
RESTARTER_ANNOTATION = 'restarter/after'
NAMESPACE = 'default'
FORMATTER = logging.Formatter(
    "%(asctime)s — %(name)s — %(levelname)s — %(message)s")


def get_console_handler():
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(FORMATTER)
    return console_handler


log = logging.getLogger('restarter')
log.setLevel(logging.DEBUG)
log.addHandler(get_console_handler())


def parse_duration(duration_str):
    match = re.match(r'(\d+)([a-z]+)', duration_str, re.IGNORECASE)
    if not match:
        raise ValueError('Invalid duration string: {}'.format(duration_str))
    value, unit = match.groups()
    unit = unit.lower()
    if unit == 'h':
        value = int(value) * 3600
    elif unit == 'm':
        value = int(value) * 60
    elif unit == 'd':
        value = int(value) * 3600 * 24
    else:
        raise ValueError('Invalid duration unit: {}'.format(unit))
    return value


def get_all_deployments_in_namespace(api: client.AppsV1Api, namespace: str):
    resp = api.list_namespaced_deployment(namespace)

    if len(resp.items) == 0:
        log.debug('no deployments found in namespace')
    else:
        log.debug('found %d deployments:' % len(resp.items))

        for i in resp.items:
            log.debug('  - %s', i.metadata.name)

    return resp.items


def filter_deployments_for_annotation(deployments: list, annotation: str) -> list:
    deployments = list(filter(
        lambda d: annotation in d.metadata.annotations, deployments))

    if len(deployments) == 0:
        log.debug('no deployments has %s annotation' % RESTARTER_ANNOTATION)
    else:
        log.debug('found %d deployments with matching annotation:' %
                  len(deployments))
        for d in deployments:
            log.debug('  - %s', d.metadata.name)


def get_deployments(deployments: list, annotation: str) -> list:
    deployments = list(filter(
        lambda d: annotation in d.metadata.annotations, deployments))

    if len(deployments) == 0:
        log.debug('no deployments has %s annotation' % RESTARTER_ANNOTATION)
    else:
        log.debug('found %d deployments with matching annotation:' %
                  len(deployments))
        for d in deployments:
            log.debug('  - %s', d.metadata.name)


def get_replicaset_for_label(api: client.AppsV1Api, label: str):
    api.read_namespaced_replica_set()


def restart_deployment(api: client.AppsV1Api, deployment):
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


def get_last_replicaset_with_selectors(api: client.AppsV1Api, selectors: list):
    replicaset_list = api.list_namespaced_replica_set(
        NAMESPACE, label_selector=','.join(selectors))

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


def handle_deployment_restart(api: client.AppsV1Api, deployment):
    try:
        name = deployment.metadata.name
        if RESTARTER_ANNOTATION in deployment.metadata.annotations:
            restart_after = parse_duration(
                deployment.metadata.annotations[RESTARTER_ANNOTATION])
            log.debug('deployment "%s" has to be restarted after: %s (%ds)',
                      name, deployment.metadata.annotations[RESTARTER_ANNOTATION], restart_after)

            selectors = [f"{key}={value}" for key,
                         value in deployment.spec.selector.match_labels.items()]

            replica_set = get_last_replicaset_with_selectors(
                api, selectors)

            now = datetime.datetime.now().timestamp()
            current_age = now - replica_set.metadata.creation_timestamp.timestamp()
            if current_age > restart_after:
                log.info('\tdeployment need to be restarted')
                restart_deployment(api, deployment)
            else:
                log.debug(
                    '\tno need to restart (current uptime is %ds, target is: %ds)' % (current_age, restart_after))
        else:
            log.debug('deployment "%s" has no "%s" annotation, skipping...',
                      name, RESTARTER_ANNOTATION)
    except:
        log.exception("failed processing deployment: %s" %
                      name)


def load_config():
    try:
        log.debug("try to load in-cluster configuration")
        config.load_incluster_config()
    except:
        log.warn('in-cluster configuration not found, checking .kube/config')
        config.load_kube_config()


def main():
    load_config()
    apps_v1 = client.AppsV1Api()

    while True:
        try:
            deployments = get_all_deployments_in_namespace(apps_v1, NAMESPACE)
            for d in deployments:
                handle_deployment_restart(apps_v1, d)
        except:
            log.exception("failed to retrieve deployment list")

        time.sleep(LOOP_INTERVAL_SEC)


if __name__ == "__main__":
    main()
