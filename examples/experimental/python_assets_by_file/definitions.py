from typing import List

from dagster._nope.project import NopeAssetManifest, NopeInvocationTargetManifest, NopeProject


class ProjectFooBarProject(NopeProject):
    class AssetManifest(NopeAssetManifest):
        @property
        def tags(self) -> dict:
            return {**{"some_default_tags": "default_value"}, **super().tags}

        @property
        def metadata(self) -> dict:
            return {**{"a_metadata_key": "a_metadata_value"}, **super().metadata}

        @property
        def owners(self) -> List[str]:
            owners_from_file = super().owners
            if not owners_from_file:
                return ["team:foobar"]
            return owners_from_file

    class ExecutionTargetManifest(NopeInvocationTargetManifest):
        @property
        def tags(self) -> dict:
            return {**{"kind": "python"}, **super().tags}


defs = ProjectFooBarProject.make_definitions()

if __name__ == "__main__":
    ...
    defs.get_implicit_global_asset_job_def().execute_in_process()
