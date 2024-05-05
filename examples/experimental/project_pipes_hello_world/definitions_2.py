from typing import Dict, Type

from dagster._core.pipes.project import (
    PipesAssetManifest,
    PipesProject,
    PipesScriptManifest,
    SubprocessPipesScript,
)


# TODO: rename script to "Execution type" or something 
class CustomPipesScript(SubprocessPipesScript):
    class AssetManifest(PipesAssetManifest):
        @property
        def owners(self) -> list:
            owners_from_file = super().owners
            if not owners_from_file:
                return ["team:foobar"]
            return owners_from_file

    class ScriptManifest(PipesScriptManifest):
        @property
        def tags(self) -> dict:
            return {**{"kind": "python"}, **super().tags}


class CustomProject(PipesProject):
    @classmethod
    def script_kind_map(cls) -> Dict[str, Type]:
        return {"subprocess": CustomPipesScript}


defs = CustomProject.make_defs()

if __name__ == "__main__":
    defs.get_implicit_global_asset_job_def().execute_in_process()
