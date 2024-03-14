import asyncio
import datetime
import logging
import os
import sys

import kopf

from azimuth_schedule_operator.models import registry
from azimuth_schedule_operator.models.v1alpha1 import schedule as schedule_crd
from azimuth_schedule_operator.utils import k8s

LOG = logging.getLogger(__name__)
K8S_CLIENT = None

CHECK_INTERVAL_SECONDS = int(os.environ.get("AZIMUTH_SCHEDULE_CHECK_INTERVAL", "120"))


@kopf.on.startup()
async def startup(settings, **kwargs):
    # Apply kopf setting to force watches to restart periodically
    settings.watching.client_timeout = int(os.environ.get("KOPF_WATCH_TIMEOUT", "600"))
    global K8S_CLIENT
    K8S_CLIENT = k8s.get_k8s_client()
    # Create or update the CRDs
    for crd in registry.get_crd_resources():
        try:
            await K8S_CLIENT.apply_object(crd, force=True)
        except Exception:
            LOG.exception("error applying CRD %s - exiting", crd["metadata"]["name"])
            sys.exit(1)
    LOG.info("All CRDs updated.")
    # Give Kubernetes a chance to create the APIs for the CRDs
    await asyncio.sleep(0.5)
    # Check to see if the APIs for the CRDs are up
    # If they are not, the kopf watches will not start properly
    for crd in registry.get_crd_resources():
        api_group = crd["spec"]["group"]
        preferred_version = next(
            v["name"] for v in crd["spec"]["versions"] if v["storage"]
        )
        api_version = f"{api_group}/{preferred_version}"
        plural_name = crd["spec"]["names"]["plural"]
        try:
            _ = await K8S_CLIENT.get(f"/apis/{api_version}/{plural_name}")
        except Exception:
            LOG.exception("api for %s not available - exiting", crd["metadata"]["name"])
            sys.exit(1)


@kopf.on.cleanup()
async def cleanup(**_):
    if K8S_CLIENT:
        await K8S_CLIENT.aclose()
    LOG.info("Cleanup complete.")


async def get_reference(namespace: str, ref: schedule_crd.ScheduleRef):
    resource = await K8S_CLIENT.api(ref.api_version).resource(ref.kind)
    object = await resource.fetch(ref.name, namespace=namespace)
    return object


async def delete_reference(namespace: str, ref: schedule_crd.ScheduleRef):
    resource = await K8S_CLIENT.api(ref.api_version).resource(ref.kind)
    await resource.delete(ref.name, namespace=namespace)


async def check_for_delete(namespace, schedule: schedule_crd.Schedule):
    # TODO(johngarbutt): add some config in helm to set this?
    max_delete_duration_int = int(
        os.environ.get("AZIMUTH_SCHEDULE_MAX_DELETE_DURATION_MINUTES", "15")
    ) + int(CHECK_INTERVAL_SECONDS / 60)
    max_delete_duration = datetime.timedelta(minutes=max_delete_duration_int)
    scheduled_at = schedule.spec.not_after - max_delete_duration
    now = datetime.datetime.now(datetime.timezone.utc)

    if now >= scheduled_at:
        LOG.info(f"Attempting delete for {namespace} and {schedule.metadata.name}.")
        await delete_reference(namespace, schedule.spec.ref)
        await update_schedule(schedule.metadata.name, namespace, delete_triggered=True)
    else:
        LOG.info(f"No delete for {namespace} and {schedule.metadata.name}.")


async def update_schedule(
    name: str,
    namespace: str,
    ref_found: bool = None,
    delete_triggered: bool = None,
):
    now = datetime.datetime.now(datetime.timezone.utc)
    now_string = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    status_updates = dict(updated_at=now_string)

    if ref_found is not None:
        status_updates["refFound"] = ref_found
    if delete_triggered is not None:
        status_updates["deleteTriggered"] = delete_triggered

    status_resource = await K8S_CLIENT.api(registry.API_VERSION).resource(
        "schedules/status"
    )
    LOG.info(f"Updating status for {name} in {namespace} with: {status_updates}")
    await status_resource.patch(
        name,
        dict(status=status_updates),
        namespace=namespace,
    )


# check every two minutes
@kopf.timer(registry.API_GROUP, "schedule", interval=CHECK_INTERVAL_SECONDS)
async def schedule_check(body, namespace, **_):
    schedule = schedule_crd.Schedule(**body)

    if not schedule.status.ref_found:
        await get_reference(namespace, schedule.spec.ref)
        await update_schedule(schedule.metadata.name, namespace, ref_found=True)

    await check_for_delete(namespace, schedule)
