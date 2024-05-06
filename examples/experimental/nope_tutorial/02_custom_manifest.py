from pathlib import Path
from typing import Type

from dagster._core.execution.context.compute import AssetExecutionContext
from dagster._core.pipes.subprocess import PipesSubprocessClient
from dagster._nope.project import (
    NopeInvocationTarget,
    NopeProject,
)
from dagster._nope.subprocess import NopeSubprocessInvocationTarget


class FancyRuntimeResource:
    def call(self, asset_keys) -> None:
        print(f"FancyRuntimeResource called on asset keys: {asset_keys}")  # noqa: T201


class FancyInvocationTarget(NopeInvocationTarget):
    def invoke(self, context: AssetExecutionContext, fancy_runtime_resource: FancyRuntimeResource):
        # platform owner has complete control here
        fancy_runtime_resource.call(context.selected_asset_keys)


class TutorialSubprocessInvocationTarget(NopeSubprocessInvocationTarget):
    class InvocationTargetManifest(NopeSubprocessInvocationTarget.InvocationTargetManifest):
        @property
        def tags(self) -> dict:
            return {**{"kind": "python"}, **super().tags}

    class AssetManifest(NopeSubprocessInvocationTarget.AssetManifest):
        @property
        def owners(self) -> list:
            owners_from_manifest_file = super().owners
            return owners_from_manifest_file if owners_from_manifest_file else ["team:foobar"]


class TutorialProject(NopeProject):
    @classmethod
    def map_manifest_to_target_class(cls, target_type: str, full_manifest: dict) -> Type:
        if target_type == "fancy":
            return FancyInvocationTarget
        elif target_type == "subprocess":
            return TutorialSubprocessInvocationTarget

        raise Exception(f"Target type {target_type} not supported by {cls.__name__}")


defs = TutorialProject.make_definitions(
    defs_path=Path(__file__).resolve().parent / Path("defs"),
    resources={
        "fancy_runtime_resource": FancyRuntimeResource(),
        "subprocess_client": PipesSubprocessClient(),
    },
)

if __name__ == "__main__":
    defs.get_implicit_global_asset_job_def().execute_in_process()
