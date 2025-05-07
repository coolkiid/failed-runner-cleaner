import argparse
import datetime
from kubernetes import client, config


RUNNER_SETS_PLURAL = "autoscalingrunnersets"
EPHEMERAL_RUNNERS_PLURAL = "ephemeralrunners"


def _print(message: str):
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

    _print(f"all failed ephemeral runners: {failed_runners}")
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
    return r["items"][0]["status"]["failedEphemeralRunners"]


def main():
    parser = argparse.ArgumentParser(
        description="This tools is for cleaning failed ephemeral runners"
    )
    parser.add_argument(
        "-n", "--namespace", required=True, help="the runner's namespace"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="print the failed runners' name only"
    )
    args = parser.parse_args()

    config.load_kube_config()
    api = client.CustomObjectsApi()

    namespace: str = args.namespace
    _print(f"check failed runners in {namespace}")

    num: int = failed_runner_count(api, namespace)
    _print(f"{num} failed runner(s) found.")

    if num == 0:
        return

    list_failed_runners(api, namespace, EPHEMERAL_RUNNERS_PLURAL)

    if args.dry_run:
        return

    delete_failed_runners(api, namespace, EPHEMERAL_RUNNERS_PLURAL)


main()
