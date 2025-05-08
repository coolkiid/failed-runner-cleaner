import argparse
import datetime
from kubernetes import client, config


RUNNER_SETS_PLURAL = "autoscalingrunnersets"
EPHEMERAL_RUNNERS_PLURAL = "ephemeralrunners"


def _print(message: str, warning: bool = False):
    if warning:
        message = f"\033[93m{message}\033[0m"

    print(f"[{datetime.datetime.now()}] {message}")


def list_failed_runners(
    api: client.CustomObjectsApi,
    namespace: str,
) -> list:
    r = api.list_namespaced_custom_object(
        "actions.github.com", "v1alpha1", namespace, EPHEMERAL_RUNNERS_PLURAL
    )

    failed_runners = []

    for runner in r["items"]:
        status = runner["status"]
        if (
            status["phase"] == "Failed"
            and not status["ready"]
            and status["reason"] == "TooManyPodFailures"
        ):
            failed_runner = status["runnerName"]
            failed_runners.append(failed_runner)

    _print(f"all failed ephemeral runners: {failed_runners}", warning=True)
    return failed_runners


def delete_failed_runners(
    api: client.CustomObjectsApi, namespace: str, failed_runners: list
):
    for runner in failed_runners:
        _print(f"about to delete {runner}")
        api.delete_namespaced_custom_object(
            "actions.github.com",
            "v1alpha1",
            namespace,
            EPHEMERAL_RUNNERS_PLURAL,
            runner,
        )


def failed_runner_count(api: client.CustomObjectsApi, namespace: str) -> int:
    r = api.list_namespaced_custom_object(
        "actions.github.com", "v1alpha1", namespace, RUNNER_SETS_PLURAL
    )

    status = r["items"][0].get("status", None)
    if status is None:
        _print(f"no status field found in the response for {namespace}", warning=True)
        return None

    return r["items"][0]["status"].get("failedEphemeralRunners", None)


def read_namespaces_from_file(file_path: str) -> list:
    with open(file_path, "r") as f:
        lines = f.readlines()
        namespaces = [line.strip() for line in lines if line.strip()]

    return list(set(namespaces))


def check_runners(api: client.CustomObjectsApi, namespace: str, dry_run: bool = True):
    num: int = failed_runner_count(api, namespace) or 0
    _print(f"{num} failed runner(s) found in {namespace}.")

    if num == 0:
        return

    list_failed_runners(api, namespace, EPHEMERAL_RUNNERS_PLURAL)

    if dry_run:
        return

    delete_failed_runners(api, namespace, EPHEMERAL_RUNNERS_PLURAL)


def main():
    parser = argparse.ArgumentParser(
        description="This tools is for cleaning failed ephemeral runners"
    )
    parser.add_argument(
        "--namespace-list",
        required=True,
        help="the absolute file path that records the watched runners' namespaces",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="print the failed runners' name only"
    )
    args = parser.parse_args()

    config.load_kube_config()
    api = client.CustomObjectsApi()

    namespaces: list = read_namespaces_from_file(args.namespace_list)
    _print(f"check failed runners in {namespaces}")

    for namespace in namespaces:
        check_runners(api, namespace, args.dry_run)


main()
