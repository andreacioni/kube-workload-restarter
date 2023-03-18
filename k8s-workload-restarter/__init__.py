import signal
import time
from kubernetes import config, client

from .restarter import get_all_deployments_in_namespace, handle_deployment
from .log import log

LOOP_INTERVAL_SEC = 30
NAMESPACE = 'default'

_exit_gracefully = False


def _load_config():
    try:
        log.debug("try to load in-cluster configuration")
        config.load_incluster_config()
    except:
        try:
            log.info(
                'in-cluster configuration not found, checking .kube/config')
            config.load_kube_config()
        except:
            log.exception("failed to load config")


def _app_main_loop(api: client.AppsV1Api):
    global _exit_gracefully

    timeout_counter = 0
    while not _exit_gracefully:
        if (timeout_counter <= 0):
            try:
                deployments = get_all_deployments_in_namespace(
                    api, NAMESPACE)
                for d in deployments:
                    handle_deployment(api, NAMESPACE, d)
            except:
                log.exception("failed to retrieve deployment list")

            timeout_counter = LOOP_INTERVAL_SEC
        time.sleep(1)
        timeout_counter = timeout_counter - 1


def main():
    def set_exit_gracefully(*kargs):
        global _exit_gracefully
        log.info("exiting...")
        _exit_gracefully = True

    signal.signal(signal.SIGINT, set_exit_gracefully)
    signal.signal(signal.SIGTERM, set_exit_gracefully)

    _load_config()
    api = client.AppsV1Api()

    _app_main_loop(api)


if __name__ == "__main__":
    main()
