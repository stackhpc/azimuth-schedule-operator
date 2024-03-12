import asyncio
import datetime
import unittest
from unittest import mock

import kopf

from azimuth_schedule_operator.models.v1alpha1 import schedule as schedule_crd
from azimuth_schedule_operator import operator


class TestOperator(unittest.IsolatedAsyncioTestCase):
    def _generate_fake_crd(self, name):
        plural_name, api_group = name.split(".", maxsplit=1)
        return {
            "metadata": {
                "name": name,
            },
            "spec": {
                "group": api_group,
                "names": {
                    "plural": plural_name,
                },
                "versions": [
                    {
                        "name": "v1alpha1",
                        "storage": True,
                    },
                ],
            },
        }

    @mock.patch("azimuth_schedule_operator.utils.k8s.get_k8s_client")
    async def test_startup_register_crds(self, mock_get):
        mock_client = mock.AsyncMock()
        mock_get.return_value = mock_client
        mock_settings = mock.Mock()

        await operator.startup(mock_settings)

        # Test that the CRDs were applied
        mock_client.apply_object.assert_has_awaits([mock.call(mock.ANY, force=True)])
        # Test that the APIs were checked
        mock_client.get.assert_has_awaits(
            [
                mock.call("/apis/scheduling.azimuth.stackhpc.com/v1alpha1/schedules"),
            ]
        )

    @mock.patch.object(operator, "K8S_CLIENT", new_callable=mock.AsyncMock)
    async def test_cleanup_calls_aclose(self, mock_client):
        await operator.cleanup()
        mock_client.aclose.assert_awaited_once_with()

    @mock.patch.object(operator, "schedule_delete_task")
    @mock.patch.object(operator, "get_reference")
    async def test_schedule_changed(
        self, mock_get_reference, mock_schedule_delete_task
    ):
        memo = kopf.Memo()
        body = schedule_crd.get_fake_dict()
        fake = schedule_crd.get_fake()
        namespace = "ns1"

        await operator.schedule_changed(memo, body, namespace)

        # Assert the expected behavior
        mock_get_reference.assert_awaited_once_with(namespace, fake.spec.ref)
        mock_schedule_delete_task.assert_awaited_once_with(memo, namespace, mock.ANY)

    @mock.patch.object(asyncio, "create_task")
    @mock.patch.object(operator, "delete_after_delay", new_callable=mock.Mock)
    async def test_schedule_delete_task(
        self, mock_delete_after_delay, mock_create_task
    ):
        memo = kopf.Memo()
        namespace = "ns1"
        schedule = schedule_crd.get_fake()
        mock_create_task.return_value = "sentinel"

        await operator.schedule_delete_task(memo, namespace, schedule)

        # Assert the expected behavior
        mock_delete_after_delay.assert_called_once_with(0, namespace, schedule.spec.ref)
        self.assertEqual(
            memo["delete_scheduled_at"],
            schedule.spec.notBefore - datetime.timedelta(minutes=15),
        )
        self.assertEqual(memo["delete_scheduled_ref"], schedule.spec.ref)
        mock_create_task.assert_called_once_with(mock.ANY)
        self.assertEqual(memo["delete_task"], "sentinel")

    @mock.patch.object(asyncio, "sleep")
    @mock.patch.object(operator, "delete_reference")
    async def test_delete_after_delay(self, mock_delete_reference, mock_sleep):
        delay_seconds = 10
        namespace = "ns1"
        ref = schedule_crd.get_fake().spec.ref

        await operator.delete_after_delay(delay_seconds, namespace, ref)

        mock_delete_reference.assert_awaited_once_with(namespace, ref)
        mock_sleep.assert_awaited_once_with(delay_seconds)
