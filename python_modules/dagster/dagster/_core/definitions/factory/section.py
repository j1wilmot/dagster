import inspect
from abc import ABC, abstractmethod
from functools import cached_property
from typing import (
    Iterable,
    Optional,
    Sequence,
    Set,
    Union,
)

from dagster._core.definitions.asset_check_result import AssetCheckResult
from dagster._core.definitions.asset_check_spec import AssetCheckSpec
from dagster._core.definitions.asset_spec import AssetSpec
from dagster._core.definitions.assets import AssetsDefinition
from dagster._core.definitions.base_asset_graph import AssetKeyOrCheckKey
from dagster._core.definitions.decorators.asset_decorator import multi_asset
from dagster._core.definitions.result import MaterializeResult, ObserveResult
from dagster._core.execution.context.compute import AssetExecutionContext
from dagster._utils.security import non_secure_md5_hash_str


def resources_without_io_manager(context: AssetExecutionContext):
    original_resources = context.resources.original_resource_dict
    return {k: v for k, v in original_resources.items() if k != "io_manager"}


def unique_id_from_key(keys: Sequence[AssetKeyOrCheckKey]) -> str:
    """Generate a unique ID from the provided keys.

    This is necessary to disambiguate between different ops underlying sections without
    forcing the user to provide a name for the underlying op.
    """
    sorted_keys = sorted(keys, key=lambda key: key.to_string())
    return non_secure_md5_hash_str(",".join([str(key) for key in sorted_keys]).encode())[:8]


SectionExecuteResult = Iterable[Union[MaterializeResult, AssetCheckResult, ObserveResult]]


class ExecutableAssetGraphSection(ABC):
    def __init__(
        self,
        specs: Sequence[Union[AssetSpec, AssetCheckSpec]],
        compute_kind: Optional[str] = None,
        subsettable: bool = False,
        tags: Optional[dict] = None,
    ):
        self.specs = specs
        self._compute_kind = compute_kind
        self._subsettable = subsettable
        self._tags = tags or {}

    @property
    def required_resource_keys(self) -> Set[str]:
        # calling inner property to cache property while
        # still allowing a user to override this
        return self._cached_required_resource_keys

    @cached_property
    def _cached_required_resource_keys(self) -> Set[str]:
        execute_method = getattr(self, "execute")
        parameters = inspect.signature(execute_method).parameters
        return {param for param in parameters if param != "context"}

    @property
    def asset_specs(self) -> Sequence[AssetSpec]:
        return [spec for spec in self.specs if isinstance(spec, AssetSpec)]

    @property
    def asset_check_specs(self) -> Sequence[AssetCheckSpec]:
        return [spec for spec in self.specs if isinstance(spec, AssetCheckSpec)]

    @property
    def op_name(self) -> str:
        return unique_id_from_key([spec.key for spec in self.specs])

    @property
    def tags(self) -> Optional[dict]:
        return self._tags

    @property
    def subsettable(self) -> bool:
        return self._subsettable

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
            can_subset=self.subsettable,
        )
        def _nope_multi_asset(context: AssetExecutionContext):
            return self.execute(context=context, **resources_without_io_manager(context))

        return _nope_multi_asset

    # Resources as kwargs. Must match set in required_resource_keys.
    # Can return anything that the multi_asset decorator can accept, hence typed as Any
    @abstractmethod
    def execute(self, context: AssetExecutionContext, **kwargs) -> SectionExecuteResult: ...


# class DefaultExecutableAssetGraphSection(ExecutableAssetGraphSection):
#     def __init__(
#         self,
#         specs: Sequence[AssetSpec],
#         check_specs: Sequence[AssetCheckSpec],
#         friendly_name: Optional[str] = None,
#         subsettable: bool = False,
#         tags: Optional[dict] = None,
#         compute_kind: Optional[str] = None,
#     ):
#         self._specs = specs
#         self._check_specs = check_specs
#         self._tags = tags
#         self._compute_kind = compute_kind
#         self._subsettable = subsettable
#         self._op_name = friendly_name or self.__class__.__name__

#     @property
#     def asset_specs(self) -> Sequence[AssetSpec]:
#         return self._specs

#     @property
#     def asset_check_specs(self) -> Sequence[AssetCheckSpec]:
#         return self._check_specs

#     @property
#     def op_name(self) -> str:
#         return self._op_name

#     @property
#     def tags(self) -> Optional[dict]:
#         return self._tags

#     @property
#     def compute_kind(self) -> Optional[str]:
#         return self._compute_kind
