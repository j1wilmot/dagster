from typing import Type

from dagster import AssetExecutionContext, Definitions, PipesSubprocessClient
from dagster._nope.project import (
    NopeAssetManifest,
    NopeExecutionTarget,
    NopeInvocationTargetManifest,
    NopeProject,
)


class HelloWorldProjectExecutionTargetManifest(NopeInvocationTargetManifest):
    @property
    def tags(self) -> dict:
        return {**{"kind": "python"}, **super().tags}


class HelloWorldProjectAssetManifest(NopeAssetManifest):
    @property
    def owners(self) -> list:
        owners_from_file = super().owners
        if not owners_from_file:
            return ["team:foobar"]
        return owners_from_file


class HelloWorldProjectScript(NopeExecutionTarget):
    @classmethod
    def asset_manifest_class(cls) -> Type:
        return HelloWorldProjectAssetManifest

    @classmethod
    def script_manifest_class(cls) -> Type:
        return HelloWorldProjectExecutionTargetManifest

    def invoke(self, context: AssetExecutionContext, subprocess_client: PipesSubprocessClient):
        command = [self.python_executable_path, self.python_script_path]
        return subprocess_client.run(context=context, command=command).get_results()


defs = Definitions(
    assets=NopeProject.make_assets_defs(),
    resources={"subprocess_client": PipesSubprocessClient()},
)


if __name__ == "__main__":
    defs.get_implicit_global_asset_job_def().execute_in_process()
