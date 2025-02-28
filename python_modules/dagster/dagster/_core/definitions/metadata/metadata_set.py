from abc import ABC, abstractmethod
from functools import lru_cache
from typing import AbstractSet, Any, Mapping, Optional, Type

from typing_extensions import TypeVar

from dagster import _check as check
from dagster._model import DagsterModel
from dagster._model.pydantic_compat_layer import model_fields
from dagster._utils.typing_api import flatten_unions

from .metadata_value import MetadataValue, TableColumnLineage, TableSchema

T_NamespacedMetadataSet = TypeVar("T_NamespacedMetadataSet", bound="NamespacedMetadataSet")


# Python types that have a MetadataValue types that directly wraps them
DIRECTLY_WRAPPED_METADATA_TYPES = {
    str,
    float,
    int,
    bool,
    TableSchema,
    TableColumnLineage,
    type(None),
}

T_NamespacedMetadataSet = TypeVar("T_NamespacedMetadataSet", bound="NamespacedMetadataSet")


def is_raw_metadata_type(t: Type) -> bool:
    return issubclass(t, MetadataValue) or t in DIRECTLY_WRAPPED_METADATA_TYPES


class NamespacedMetadataSet(ABC, DagsterModel):
    """Extend this class to define a set of metadata fields in the same namespace.

    Supports splatting to a dictionary that can be placed inside a metadata argument along with
    other dictionary-structured metadata.

    .. code-block:: python

        my_metadata: NamespacedMetadataSet = ...
        return MaterializeResult(metadata={**my_metadata, ...})
    """

    def __init__(self, *args, **kwargs):
        for field_name in model_fields(self).keys():
            annotation_types = self._get_accepted_types_for_field(field_name)
            invalid_annotation_types = {
                annotation_type
                for annotation_type in annotation_types
                if not is_raw_metadata_type(annotation_type)
            }
            if invalid_annotation_types:
                check.failed(
                    f"Type annotation for field '{field_name}' includes invalid metadata type(s): {invalid_annotation_types}"
                )
        super().__init__(*args, **kwargs)

    @classmethod
    @abstractmethod
    def namespace(cls) -> str:
        raise NotImplementedError()

    @classmethod
    def _namespaced_key(cls, key: str) -> str:
        return f"{cls.namespace()}/{key}"

    @staticmethod
    def _strip_namespace_from_key(key: str) -> str:
        return key.split("/", 1)[1]

    def keys(self) -> AbstractSet[str]:
        return {
            self._namespaced_key(key)
            for key in model_fields(self).keys()
            # getattr returns the pydantic property on the subclass
            if getattr(self, key) is not None
        }

    def __getitem__(self, key: str) -> Any:
        # getattr returns the pydantic property on the subclass
        return getattr(self, self._strip_namespace_from_key(key))

    @classmethod
    def extract(
        cls: Type[T_NamespacedMetadataSet], metadata: Mapping[str, Any]
    ) -> T_NamespacedMetadataSet:
        """Extracts entries from the provided metadata dictionary into an instance of this class.

        Ignores any entries in the metadata dictionary whose keys don't correspond to fields on this
        class.

        In general, the following should always pass:

        .. code-block:: python

            class MyMetadataSet(NamedspacedMetadataSet):
                ...

            metadata: MyMetadataSet  = ...
            assert MyMetadataSet.extract(dict(metadata)) == metadata

        Args:
            metadata (Mapping[str, Any]): A dictionary of metadata entries.
        """
        kwargs = {}
        for namespaced_key, value in metadata.items():
            splits = namespaced_key.split("/")
            if len(splits) == 2:
                namespace, key = splits
                if namespace == cls.namespace() and key in model_fields(cls):
                    kwargs[key] = cls._extract_value(field_name=key, value=value)

        return cls(**kwargs)

    @classmethod
    def _extract_value(cls, field_name: str, value: Any) -> Any:
        """Based on type annotation, potentially coerce the metadata value to its inner value.

        E.g. if the annotation is Optional[float] and the value is FloatMetadataValue, construct
        the MetadataSet using the inner float.
        """
        if isinstance(value, MetadataValue):
            annotation = model_fields(cls)[field_name].annotation
            annotation_acceptable_types = flatten_unions(annotation)
            if (
                type(value) not in annotation_acceptable_types
                and type(value.value) in annotation_acceptable_types
            ):
                check.invariant(type(value.value) in DIRECTLY_WRAPPED_METADATA_TYPES)
                return value.value

        return value

    @classmethod
    @lru_cache(maxsize=None)  # this avoids wastefully recomputing this once per instance
    def _get_accepted_types_for_field(cls, field_name: str) -> AbstractSet[Type]:
        annotation = model_fields(cls)[field_name].annotation
        return flatten_unions(annotation)


class TableMetadataSet(NamespacedMetadataSet):
    """Metadata entries that apply to definitions, observations, or materializations of assets that
    are tables.

    Args:
        column_schema (Optional[TableSchema]): The schema of the columns in the table.
        column_lineage (Optional[TableColumnLineage]): The lineage of column inputs to column
            outputs for the table.
    """

    column_schema: Optional[TableSchema] = None
    column_lineage: Optional[TableColumnLineage] = None

    @classmethod
    def namespace(cls) -> str:
        return "dagster"
