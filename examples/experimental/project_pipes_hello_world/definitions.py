from typing import Type

from dagster import AssetExecutionContext, Definitions, PipesSubprocessClient
from dagster._core.pipes.project import (
    PipesAssetManifest,
    PipesProject,
    PipesScript,
    PipesScriptManifest,
)


class HelloWorldProjectScriptManifest(PipesScriptManifest):
    @property
    def tags(self) -> dict:
        return {**{"kind": "python"}, **super().tags}


class HelloWorldProjectAssetManifest(PipesAssetManifest):
    @property
    def owners(self) -> list:
        owners_from_file = super().owners
        if not owners_from_file:
            return ["team:foobar"]
        return owners_from_file


class HelloWorldProjectScript(PipesScript):
    @classmethod
    def asset_manifest_class(cls) -> Type:
        return HelloWorldProjectAssetManifest

    @classmethod
    def script_manifest_class(cls) -> Type:
        return HelloWorldProjectScriptManifest

    def execute(self, context: AssetExecutionContext, subprocess_client: PipesSubprocessClient):
        command = [self.python_executable_path, self.python_script_path]
        return subprocess_client.run(context=context, command=command).get_results()


defs = Definitions(
    assets=PipesProject.make_assets_defs(),
    resources={"subprocess_client": PipesSubprocessClient()},
)


if __name__ == "__main__":
    defs.get_implicit_global_asset_job_def().execute_in_process()
