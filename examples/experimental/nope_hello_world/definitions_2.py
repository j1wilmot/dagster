from dagster._nope.project import (
    NopeAssetManifest,
    NopeInvocationTarget,
    NopeInvocationTargetManifest,
    NopeProject,
    NopeSubprocessInvocationTarget,
)


# TODO: rename script to "Execution type" or something
class TutorialInvocationTarget(NopeSubprocessInvocationTarget):
    class AssetManifest(NopeAssetManifest):
        @property
        def owners(self) -> list:
            owners_from_file = super().owners
            if not owners_from_file:
                return ["team:foobar"]
            return owners_from_file

    class InvocationTargetManifest(NopeInvocationTargetManifest):
        @property
        def tags(self) -> dict:
            return {**{"kind": "python"}, **super().tags}


class TutorialProject(NopeProject):
    @classmethod
    def create_invocation_target(cls, invocation_target_manifest: NopeInvocationTargetManifest) -> NopeInvocationTarget:
        return TutorialInvocationTarget(invocation_target_manifest)

defs = TutorialProject.make_definitions()

if __name__ == "__main__":
    defs.get_implicit_global_asset_job_def().execute_in_process()
