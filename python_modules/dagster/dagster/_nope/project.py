import hashlib
import shutil
from abc import abstractmethod
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterable, List, Mapping, Optional, Sequence, Type

import yaml

from dagster import AssetSpec, file_relative_path, multi_asset
from dagster._core.definitions.asset_dep import CoercibleToAssetDep
from dagster._core.definitions.asset_key import AssetKey, CoercibleToAssetKey
from dagster._core.definitions.assets import AssetsDefinition
from dagster._core.execution.context.compute import AssetExecutionContext
from dagster._core.pipes.context import PipesExecutionResult
from dagster._core.pipes.subprocess import PipesSubprocessClient

try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

if TYPE_CHECKING:
    from dagster._core.definitions.definitions_class import Definitions

# Directory path
directory = Path(file_relative_path(__file__, "assets"))


def compute_file_hash(file_path, hash_algorithm="sha256") -> Any:
    # Initialize the hash object
    hash_object = hashlib.new(hash_algorithm)

    # Open the file in binary mode and read its contents
    with open(file_path, "rb") as file:
        # Update the hash object with the file contents
        while chunk := file.read(4096):  # Read the file in chunks to conserve memory
            hash_object.update(chunk)

    # Get the hexadecimal digest of the hash
    file_hash = hash_object.hexdigest()
    return file_hash


def deps_from_metadata_cls(raw_manifest_obj: dict) -> Sequence[CoercibleToAssetDep]:
    if not raw_manifest_obj or "deps" not in raw_manifest_obj:
        return []

    return [
        AssetKey.from_user_string(dep) if isinstance(dep, str) else dep
        for dep in raw_manifest_obj["deps"]
    ]


def build_description_from_python_file(file_path: Path) -> str:
    return (
        f"""Python file "{file_path.name}":
"""
        + "```\n"
        + file_path.read_text()
        + "\n```"
    )


class NopeAssetManifest:
    def __init__(
        self,
        manifest_obj,
        full_python_path: Path,
        group_folder: Path,
        asset_key_parts: List[str],
    ) -> None:
        self.manifest_obj = manifest_obj or {}
        self.full_python_path = full_python_path
        self.group_folder = group_folder
        self.asset_key_parts = asset_key_parts

    @property
    def code_version(self) -> str:
        return compute_file_hash(self.full_python_path)

    @property
    def deps(self) -> Sequence[CoercibleToAssetDep]:
        return deps_from_metadata_cls(self.manifest_obj)

    @property
    def description(self) -> str:
        return build_description_from_python_file(self.full_python_path)

    @property
    def asset_key(self) -> CoercibleToAssetKey:
        return AssetKey([self.group_name] + self.asset_key_parts)

    @property
    def file_name_parts(self) -> List[str]:
        return self.full_python_path.stem.split(".")

    @property
    def group_name(self) -> str:
        return self.group_folder.name

    @property
    def tags(self) -> dict:
        return self.manifest_obj.get("tags", {})

    @property
    def metadata(self) -> dict:
        return self.manifest_obj.get("metadata", {})

    @property
    def owners(self) -> List[str]:
        return self.manifest_obj.get("owners", [])

    @property
    def asset_spec(self) -> AssetSpec:
        return AssetSpec(
            key=self.asset_key,
            deps=self.deps,
            description=self.description,
            group_name=self.group_name,
            tags=self.tags,
            metadata=self.metadata,
            owners=self.owners,
            code_version=self.code_version,
        )


class NopeExecutionTargetManifest:
    file_path: Path
    asset_spec: AssetSpec

    def __init__(
        self,
        *,
        group_folder: Path,
        full_python_path: Path,
        full_manifest_path: Optional[Path],
        asset_manifest_class: Type,
    ) -> None:
        self.group_folder = group_folder
        self.full_python_path = full_python_path
        self.manifest_object = (
            yaml.load(full_manifest_path.read_text(), Loader=Loader) if full_manifest_path else {}
        )
        self.asset_manifest_class = asset_manifest_class

    @property
    def kind(self) -> str:
        return self.manifest_object["kind"]

    @property
    def asset_manifests(self) -> Sequence[NopeAssetManifest]:
        if self.manifest_object and "assets" in self.manifest_object:
            raw_asset_manifests = self.manifest_object["assets"]
            asset_manifests = []
            for asset_name, raw_asset_manifest in raw_asset_manifests.items():
                asset_manifests.append(
                    self.asset_manifest_class(
                        manifest_obj=raw_asset_manifest,
                        full_python_path=self.full_python_path,
                        group_folder=self.group_folder,
                        asset_key_parts=asset_name.split("."),
                    )
                )
            return asset_manifests
        else:
            return [
                self.asset_manifest_class(
                    self.manifest_object,
                    self.full_python_path,
                    self.group_folder,
                    asset_key_parts=self.full_python_path.stem.split("."),
                )
            ]

    @property
    def file_name_parts(self) -> List[str]:
        return self.full_python_path.stem.split(".")

    @property
    def op_name(self) -> str:
        return self.file_name_parts[-1]

    @property
    def tags(self) -> dict:
        return {}

    @property
    def asset_specs(self) -> Sequence[AssetSpec]:
        return [asset_manifest.asset_spec for asset_manifest in self.asset_manifests]

    @property
    def metadata(self) -> dict:
        return {}


class NopeExecutionTarget:
    def __init__(self, script_manifest: NopeExecutionTargetManifest):
        self._script_manifest = script_manifest

    @property
    @abstractmethod
    def required_resource_keys(self) -> set: ...

    @property
    def script_manifest(self) -> NopeExecutionTargetManifest:
        return self._script_manifest

    def to_assets_def(self) -> AssetsDefinition:
        @multi_asset(
            specs=self.script_manifest.asset_specs,
            name=self.script_manifest.op_name,
            op_tags=self.script_manifest.tags,
            required_resource_keys=self.required_resource_keys,
        )
        def _nope_multi_asset(context: AssetExecutionContext):
            import copy

            resource_dict = copy.copy(context.resources.original_resource_dict)
            del resource_dict["io_manager"]
            return self.execute(context=context, **resource_dict)

        return _nope_multi_asset

    @cached_property
    def python_executable_path(self) -> str:
        python_executable = shutil.which("python")
        if not python_executable:
            raise ValueError("Python executable not found.")
        return python_executable

    @property
    def python_script_path(self) -> str:
        return str(self.script_manifest.full_python_path.resolve())

    @abstractmethod
    def execute(self, context: AssetExecutionContext, **kwargs) -> Any: ...


class NopeSubprocessExecutionTarget(NopeExecutionTarget):
    @property
    def required_resource_keys(self) -> set:
        return {"subprocess_client"}

    def execute(
        self, context: AssetExecutionContext, subprocess_client: PipesSubprocessClient
    ) -> Iterable[PipesExecutionResult]:
        command = [self.python_executable_path, self.python_script_path]
        return subprocess_client.run(context=context, command=command).get_results()


class NopeProject:
    @classmethod
    def create_execution_target(
        cls, script_manifest: NopeExecutionTargetManifest
    ) -> NopeExecutionTarget:
        return NopeSubprocessExecutionTarget(script_manifest)

    @classmethod
    def asset_manifest_class(cls) -> Type:
        if hasattr(cls, "AssetManifest"):
            return getattr(cls, "AssetManifest")
        return NopeAssetManifest

    @classmethod
    def script_manifest_class(cls) -> Type:
        if hasattr(cls, "ExecutionTargetManifest"):
            return getattr(cls, "ExecutionTargetManifest")
        return NopeExecutionTargetManifest

    @classmethod
    def make_assets_defs(
        cls, cwd: Optional[Path] = None, root_folder: Optional[Path] = None
    ) -> Sequence[AssetsDefinition]:
        cwd = cwd or Path.cwd()
        root_folder = root_folder or Path("defs")
        assets_defs = []
        for group_folder in (cwd / root_folder).iterdir():
            if not group_folder.is_dir():
                continue

            yaml_files = {}
            python_files = {}
            for full_path in (cwd / group_folder).iterdir():
                if full_path.suffix == ".yaml":
                    yaml_files[full_path.stem] = full_path
                elif full_path.suffix == ".py":
                    python_files[full_path.stem] = full_path

            for stem_name in set(python_files) & set(yaml_files):
                assets_defs.append(
                    cls.make_assets_def(
                        group_folder=group_folder,
                        full_python_path=python_files[stem_name],
                        full_yaml_path=yaml_files[stem_name],
                    )
                )

        return assets_defs

    @classmethod
    def make_definitions(cls, resources: Optional[Mapping[str, Any]] = None) -> "Definitions":
        from dagster._core.definitions.definitions_class import Definitions

        return Definitions(
            assets=NopeProject.make_assets_defs(),
            resources=resources if resources else {"subprocess_client": PipesSubprocessClient()},
        )

    @classmethod
    def make_assets_def(
        cls, group_folder: Path, full_python_path: Path, full_yaml_path: Path
    ) -> AssetsDefinition:
        script_instance = cls.create_execution_target(
            cls.script_manifest_class()(
                group_folder=group_folder,
                full_python_path=full_python_path,
                full_manifest_path=full_yaml_path,
                asset_manifest_class=cls.asset_manifest_class(),
            )
        )
        return script_instance.to_assets_def()
