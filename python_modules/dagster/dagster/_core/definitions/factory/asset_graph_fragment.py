import inspect
from abc import abstractmethod
from functools import cached_property
from typing import (
    Iterable,
    Optional,
    Sequence,
    Set,
    Union,
)

from dagster import (
    AssetSpec,
    multi_asset,
)
from dagster._core.definitions.asset_check_result import AssetCheckResult
from dagster._core.definitions.asset_check_spec import AssetCheckSpec
from dagster._core.definitions.assets import AssetsDefinition
from dagster._core.definitions.result import MaterializeResult, ObserveResult
from dagster._core.execution.context.compute import AssetExecutionContext


def resources_without_io_manager(context: AssetExecutionContext):
    original_resources = context.resources.original_resource_dict
    return {k: v for k, v in original_resources.items() if k != "io_manager"}


class ExecutableAssetGraphSection:
    def __init__(
        self,
        specs: Sequence[AssetSpec],
        check_specs: Sequence[AssetCheckSpec],
        friendly_name: Optional[str] = None,
        subsettable: bool = False,
        tags: Optional[dict] = None,
        compute_kind: Optional[str] = None,
    ):
        self._specs = specs
        self._check_specs = check_specs
        self._tags = tags
        self._compute_kind = compute_kind
        self._subsettable = subsettable
        self._op_name = friendly_name or self.__class__.__name__

    @property
    def required_resource_keys(self) -> Set[str]:
        # calling inner property to cache property while
        # still allowing a user to override this
        return self._cached_required_resource_keys

    @cached_property
    def _cached_required_resource_keys(self) -> Set[str]:
        invoke_method = getattr(self, "invoke")
        parameters = inspect.signature(invoke_method).parameters
        return {param for param in parameters if param != "context"}

    @property
    def asset_specs(self) -> Sequence[AssetSpec]:
        return self._specs

    @property
    def asset_check_specs(self) -> Sequence[AssetCheckSpec]:
        return self._check_specs

    @property
    def op_name(self) -> str:
        return self._op_name

    @property
    def tags(self) -> Optional[dict]:
        return self._tags

    @property
    def compute_kind(self) -> Optional[str]:
        return self._compute_kind

    def to_assets_def(self) -> AssetsDefinition:
        @multi_asset(
            specs=self.asset_specs,
            check_specs=self.asset_check_specs,
            name=self.op_name,
            op_tags=self.tags,
            required_resource_keys=self.required_resource_keys,
            compute_kind=self.compute_kind,
            can_subset=self._subsettable,
        )
        def _nope_multi_asset(context: AssetExecutionContext):
            return self.execute(context=context, **resources_without_io_manager(context))

        return _nope_multi_asset

    # Resources as kwargs. Must match set in required_resource_keys.
    # Can return anything that the multi_asset decorator can accept, hence typed as Any
    @abstractmethod
    def execute(
        self, context: AssetExecutionContext, **kwargs
    ) -> Iterable[Union[MaterializeResult, AssetCheckResult, ObserveResult]]: ...
