from dagster._nope.project import (
    NopeAssetManifest,
    NopeInvocationTargetManifest,
    NopeProject,
)


class TutorialProject(NopeProject):
    class InvocationTargetManifest(NopeInvocationTargetManifest):
        @property
        def tags(self) -> dict:
            return {**{"kind": "python"}, **super().tags}

    class AssetManifest(NopeAssetManifest):
        @property
        def owners(self) -> list:
            owners_from_manifest_file = super().owners
            return owners_from_manifest_file if owners_from_manifest_file else ["team:foobar"]


defs = TutorialProject.make_definitions()

if __name__ == "__main__":
    defs.get_implicit_global_asset_job_def().execute_in_process()
