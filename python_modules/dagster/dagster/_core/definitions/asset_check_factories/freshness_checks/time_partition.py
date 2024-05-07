from typing import Any, Dict, Sequence, Union

import pendulum

from dagster import _check as check
from dagster._annotations import experimental
from dagster._core.definitions.asset_check_result import AssetCheckResult
from dagster._core.definitions.asset_check_spec import AssetCheckSeverity, AssetCheckSpec
from dagster._core.definitions.asset_checks import AssetChecksDefinition
from dagster._core.definitions.asset_key import AssetKey
from dagster._core.definitions.assets import AssetsDefinition, SourceAsset
from dagster._core.definitions.events import CoercibleToAssetKey
from dagster._core.definitions.factory.entity_set import (
    EntitySetExecuteResult,
    ExecutableEntitySet,
)
from dagster._core.definitions.metadata import (
    JsonMetadataValue,
    MetadataValue,
    TimestampMetadataValue,
)
from dagster._core.definitions.time_window_partitions import (
    TimeWindowPartitionsDefinition,
)
from dagster._core.execution.context.compute import (
    AssetCheckExecutionContext,
)
from dagster._utils.schedules import (
    get_latest_completed_cron_tick,
    get_next_cron_tick,
    is_valid_cron_string,
)

from ..utils import (
    DEADLINE_CRON_PARAM_KEY,
    DEFAULT_FRESHNESS_SEVERITY,
    DEFAULT_FRESHNESS_TIMEZONE,
    FRESH_UNTIL_METADATA_KEY,
    FRESHNESS_PARAMS_METADATA_KEY,
    LAST_UPDATED_TIMESTAMP_METADATA_KEY,
    LATEST_CRON_TICK_METADATA_KEY,
    TIMEZONE_PARAM_KEY,
    assets_to_keys,
    ensure_no_duplicate_assets,
    freshness_section_friendly_name,
    get_last_updated_timestamp,
    retrieve_latest_record,
)


def create_freshness_check_specs(
    asset_keys: Sequence[AssetKey], params_metadata: Dict[str, Any]
) -> Sequence[AssetCheckSpec]:
    return [
        AssetCheckSpec(
            "freshness_check",
            asset=asset_key,
            metadata={FRESHNESS_PARAMS_METADATA_KEY: JsonMetadataValue(params_metadata)},
            description="Evaluates freshness for targeted asset.",
        )
        for asset_key in asset_keys
    ]


class TimePartitionFreshnessCheckSet(ExecutableEntitySet):
    def __init__(
        self,
        *,
        assets: Sequence[Union[SourceAsset, CoercibleToAssetKey, AssetsDefinition]],
        deadline_cron: str,
        timezone: str = DEFAULT_FRESHNESS_TIMEZONE,
        severity: AssetCheckSeverity = DEFAULT_FRESHNESS_SEVERITY,
    ):
        self._timezone = timezone
        self._deadline_cron = deadline_cron
        self._severity = severity
        self.params_metadata: dict[str, Any] = {
            TIMEZONE_PARAM_KEY: timezone,
            DEADLINE_CRON_PARAM_KEY: deadline_cron,
        }
        asset_keys = assets_to_keys(assets)
        super().__init__(
            specs=create_freshness_check_specs(asset_keys, self.params_metadata),
            subsettable=True,
            friendly_name=freshness_section_friendly_name(asset_keys),
        )

    def execute(self, context: AssetCheckExecutionContext) -> EntitySetExecuteResult:
        timezone = self._timezone
        deadline_cron = self._deadline_cron
        for check_key in context.selected_asset_check_keys:
            asset_key = check_key.asset_key
            current_timestamp = pendulum.now("UTC").timestamp()

            partitions_def = check.inst(
                context.job_def.asset_layer.asset_graph.get(asset_key).partitions_def,
                TimeWindowPartitionsDefinition,
            )
            current_time_in_freshness_tz = pendulum.from_timestamp(current_timestamp, tz=timezone)
            deadline = get_latest_completed_cron_tick(
                deadline_cron, current_time_in_freshness_tz, timezone
            )
            deadline_in_partitions_def_tz = pendulum.from_timestamp(
                deadline.timestamp(), tz=partitions_def.timezone
            )
            last_completed_time_window = check.not_none(
                partitions_def.get_prev_partition_window(deadline_in_partitions_def_tz)
            )
            expected_partition_key = partitions_def.get_partition_key_range_for_time_window(
                last_completed_time_window
            ).start
            latest_record = retrieve_latest_record(
                instance=context.instance, asset_key=asset_key, partition_key=expected_partition_key
            )
            passed = latest_record is not None

            metadata: Dict[str, MetadataValue] = {
                FRESHNESS_PARAMS_METADATA_KEY: JsonMetadataValue(self.params_metadata),
                LATEST_CRON_TICK_METADATA_KEY: TimestampMetadataValue(deadline.timestamp()),
            }

            # Allows us to distinguish between the case where the asset has never been
            # observed/materialized, and the case where this partition in particular is missing
            latest_record_any_partition = retrieve_latest_record(
                instance=context.instance, asset_key=asset_key, partition_key=None
            )

            if not passed and latest_record_any_partition is not None:
                # If this asset has been updated at all before, provide the time at which that
                # happened as additional metadata.
                metadata[LAST_UPDATED_TIMESTAMP_METADATA_KEY] = TimestampMetadataValue(
                    check.not_none(
                        get_last_updated_timestamp(latest_record_any_partition, context.log)
                    )
                )
            elif passed:
                metadata[FRESH_UNTIL_METADATA_KEY] = TimestampMetadataValue(
                    get_next_cron_tick(
                        deadline_cron, current_time_in_freshness_tz, timezone
                    ).timestamp()
                )

            yield AssetCheckResult(
                passed=passed,
                description=_construct_description(
                    partition_key=expected_partition_key,
                    passed=passed,
                    any_records_exist_for_asset=latest_record_any_partition is not None,
                ),
                severity=self._severity,
                asset_key=asset_key,
                metadata=metadata,
            )


@experimental
def build_time_partition_freshness_checks(
    *,
    assets: Sequence[Union[SourceAsset, CoercibleToAssetKey, AssetsDefinition]],
    deadline_cron: str,
    timezone: str = DEFAULT_FRESHNESS_TIMEZONE,
    severity: AssetCheckSeverity = DEFAULT_FRESHNESS_SEVERITY,
) -> AssetChecksDefinition:
    r"""Construct an `AssetChecksDefinition` that checks the freshness of the provided assets.

    This check passes if the asset is considered "fresh" by the time that execution begins. We
    consider an asset to be "fresh" if there exists a record for the most recent partition, once
    the deadline has passed.

    `deadline_cron` is a cron schedule that defines the deadline for when we should expect the most
    recent partition to arrive by. Once a tick of the cron schedule has passed, this check will fail
    if the most recent partition has not been observed/materialized.

    Let's say I have a daily-partitioned asset which runs every day at 8:00 AM UTC, and takes around
    45 minutes to complete. To account for operational delays, I would expect the asset to be done
    materializing every day by 9:00 AM UTC. I would set the `deadline_cron` to "0 9 \* \* \*". This
    means that starting at 9:00 AM, this check will expect a record to exist for the previous day's
    partition. Note that if the check runs at 8:59 AM, the deadline has not yet passed, and we'll
    instead be checking for the most recently passed deadline, which is yesterday (meaning the
    partition representing the day before yesterday).

    The timestamp of an observation record is the timestamp indicated by the
    "dagster/last_updated_timestamp" metadata key. The timestamp of a materialization record is the
    timestamp at which that record was created.

    The check will fail at runtime if a non-time-window partitioned asset is passed in.

    The check result will contain the following metadata:
    "dagster/freshness_params": A dictionary containing the parameters used to construct the
    check.
    "dagster/last_updated_time": (Only present if the asset has been observed/materialized before)
    The time of the most recent update to the asset.
    "dagster/overdue_seconds": (Only present if asset is overdue) The number of seconds that the
    asset is overdue by.
    "dagster/overdue_deadline_timestamp": The timestamp that we are expecting the asset to have
    arrived by. This is the timestamp of the most recent tick of the cron schedule.

    Examples:
        .. code-block:: python

            from dagster import build_time_partition_freshness_checks, AssetKey
            # A daily partitioned asset that is expected to be updated every day within 45 minutes
            # of 9:00 AM UTC
            from .somewhere import my_daily_scheduled_assets_def

            checks_def = build_time_partition_freshness_checks(
                [my_daily_scheduled_assets_def],
                deadline_cron="0 9 * * *",
            )


    Args:
        assets (Sequence[Union[CoercibleToAssetKey, AssetsDefinition, SourceAsset]): The assets to
            construct checks for. For each passed in asset, there will be a corresponding
            constructed `AssetChecksDefinition`.
        deadline_cron (str): The check will pass if the partition time window most recently
            completed by the time of the last cron tick has been observed/materialized.
        timezone (Optional[str]): The timezone to use when calculating freshness and deadline. If
            not provided, defaults to "UTC".

    Returns:
        AssetChecksDefinition: An `AssetChecksDefinition` object, which can execute a freshness
            check for each provided asset.
    """
    check.str_param(timezone, "timezone")
    check.opt_str_param(deadline_cron, "deadline_cron")
    check.invariant(
        deadline_cron is None or is_valid_cron_string(deadline_cron), "Invalid cron string."
    )
    check.inst_param(severity, "severity", AssetCheckSeverity)
    check.sequence_param(assets, "assets")
    ensure_no_duplicate_assets(assets)
    return TimePartitionFreshnessCheckSet(
        assets=assets, deadline_cron=deadline_cron, timezone=timezone, severity=severity
    ).to_asset_checks_def()


def _construct_description(
    partition_key: str,
    passed: bool,
    any_records_exist_for_asset: bool,
) -> str:
    if passed:
        return f"Asset is currently fresh, since partition {partition_key} has been observed/materialized."
    elif not any_records_exist_for_asset:
        return f"The asset has never been observed/materialized. We currently expect partition {partition_key} to have arrived."
    return (
        f"Asset is overdue. We expected partition {partition_key} to have arrived, and it has not."
    )
