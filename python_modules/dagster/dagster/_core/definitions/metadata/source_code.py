import inspect
import os
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Mapping,
    Optional,
    Sequence,
    Union,
)

import pydantic

import dagster._check as check
from dagster._annotations import experimental
from dagster._model import DagsterModel
from dagster._serdes import whitelist_for_serdes

from .metadata_set import (
    NamespacedMetadataSet as NamespacedMetadataSet,
    TableMetadataSet as TableMetadataSet,
)
from .metadata_value import MetadataValue

if TYPE_CHECKING:
    from dagster._core.definitions.assets import AssetsDefinition, SourceAsset
    from dagster._core.definitions.cacheable_assets import CacheableAssetsDefinition

DEFAULT_SOURCE_FILE_KEY = "asset_definition"


@experimental
@whitelist_for_serdes
class LocalFileSource(DagsterModel):
    """Represents a local file source location."""

    file_path: str
    line_number: int


@experimental
@whitelist_for_serdes
class SouceCodeLocationsMetadataValue(
    DagsterModel, MetadataValue["SouceCodeLocationsMetadataValue"]
):
    """Metadata value type which represents source locations (locally or otherwise)
    of the asset in question. For example, the file path and line number where the
    asset is defined.

    Attributes:
        sources (Dict[str, LocalFileSource]):
            A labeled dictionary of sources. The main source file should be keyed with
            the `DEFAULT_SOURCE_FILE_KEY` constant.
    """

    sources: Mapping[str, LocalFileSource] = {}

    @property
    def value(self) -> "SouceCodeLocationsMetadataValue":
        return self


def source_path_from_fn(fn: Callable[..., Any]) -> Optional[LocalFileSource]:
    cwd = os.getcwd()
    origin_file: Optional[str] = None
    origin_line = None
    try:
        origin_file = os.path.abspath(os.path.join(cwd, inspect.getsourcefile(fn)))  # type: ignore
        origin_file = check.not_none(origin_file)
        origin_line = inspect.getsourcelines(fn)[1]
    except TypeError:
        return None

    return LocalFileSource(
        file_path=origin_file,
        line_number=origin_line,
    )


class SourceCodeLocationsMetadataSet(NamespacedMetadataSet):
    """Metadata entries that apply to asset definitions and which specify the source code location
    for the asset.
    """

    source_code_locations: SouceCodeLocationsMetadataValue

    @classmethod
    def namespace(cls) -> str:
        return "dagster"


def _with_code_source_single_definition(
    assets_def: Union["AssetsDefinition", "SourceAsset", "CacheableAssetsDefinition"],
) -> Union["AssetsDefinition", "SourceAsset", "CacheableAssetsDefinition"]:
    from dagster._core.definitions.assets import AssetsDefinition

    # SourceAsset doesn't have an op definition to point to - cachable assets
    # will be supported eventually but are a bit trickier
    if not isinstance(assets_def, AssetsDefinition):
        return assets_def

    metadata_by_key = dict(assets_def.metadata_by_key) or {}

    from dagster._core.definitions.decorators.op_decorator import DecoratedOpFunction

    base_fn = (
        assets_def.op.compute_fn.decorated_fn
        if isinstance(assets_def.op.compute_fn, DecoratedOpFunction)
        else assets_def.op.compute_fn
    )
    source_path = source_path_from_fn(base_fn)

    if source_path:
        sources = {DEFAULT_SOURCE_FILE_KEY: source_path}

        for key in assets_def.keys:
            # defer to any existing metadata
            sources_for_asset = {**sources}
            try:
                existing_source_code_metadata = SourceCodeLocationsMetadataSet.extract(
                    metadata_by_key.get(key, {})
                )
                sources_for_asset = {
                    **sources,
                    **existing_source_code_metadata.source_code_locations.sources,
                }
            except pydantic.ValidationError:
                pass

            metadata_by_key[key] = {
                **metadata_by_key.get(key, {}),
                **SourceCodeLocationsMetadataSet(
                    source_code_locations=SouceCodeLocationsMetadataValue(sources=sources_for_asset)
                ),
            }

    return assets_def.with_attributes(metadata_by_key=metadata_by_key)


@experimental
def with_source_code_links(
    assets_defs: Sequence[Union["AssetsDefinition", "SourceAsset", "CacheableAssetsDefinition"]],
) -> Sequence[Union["AssetsDefinition", "SourceAsset", "CacheableAssetsDefinition"]]:
    """Wrapper function which attaches source code metadata to the provided asset definitions.

    Args:
        assets_defs (Sequence[Union[AssetsDefinition, SourceAsset, CacheableAssetsDefinition]]):
            The asset definitions to which source code metadata should be attached.

    Returns:
        Sequence[AssetsDefinition]: The asset definitions with source code metadata attached.
    """
    return [_with_code_source_single_definition(assets_def) for assets_def in assets_defs]
