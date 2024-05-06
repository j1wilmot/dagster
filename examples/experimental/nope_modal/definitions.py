import json
import subprocess
from pathlib import Path
from typing import Iterable, List, Optional, Type

from dagster._core.execution.context.compute import AssetExecutionContext
from dagster._core.pipes.context import PipesExecutionResult
from dagster._core.pipes.subprocess import PipesSubprocessClient
from dagster._nope.project import (
    NopeInvocationTarget,
    NopeInvocationTargetManifest,
    NopeProject,
)


def get_current_branch() -> Optional[str]:
    return get_stripped_stdout(["git", "rev-parse", "--abbrev-ref", "HEAD"])


def get_stripped_stdout(cmds: List[str]) -> str:
    result = subprocess.run(
        cmds, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True
    )
    return result.stdout.strip()


def modal_has_env(env_name: str) -> bool:
    modal_list_output = json.loads(get_stripped_stdout(["modal", "environment", "list", "--json"]))
    for model_env in modal_list_output:
        if model_env["name"] == env_name:
            return True
    return False


def modal_create_env(env_name: str) -> None:
    subprocess.run(
        ["modal", "environment", "create", env_name],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


class ModalKicktestInvocationTarget(NopeInvocationTarget):
    @property
    def required_resource_keys(self) -> set:
        return {"subprocess_client"}

    class InvocationTargetManifest(NopeInvocationTargetManifest):
        @property
        def tags(self) -> dict:
            return {"kind": "modal"}

    def invoke(
        self, context: AssetExecutionContext, subprocess_client: PipesSubprocessClient
    ) -> Iterable[PipesExecutionResult]:
        branch_name = get_current_branch()

        if branch_name is None:
            raise Exception("Could not determine current branch")

        if not modal_has_env(env_name=branch_name):
            modal_create_env(env_name=branch_name)

        return subprocess_client.run(
            context=context,
            command=["modal", "run", "-e", branch_name, self.python_script_path],
        ).get_results()


class ModalKicktestProject(NopeProject):
    @classmethod
    def map_manifest_to_target_class(cls, target_type: str, full_manifest: dict) -> Type:
        if target_type == "modal":
            return ModalKicktestInvocationTarget
        raise Exception(f"Target type {target_type} not supported by {cls.__name__}")


defs = ModalKicktestProject.make_definitions(
    defs_path=Path(__file__).resolve().parent / Path("defs")
)

if __name__ == "__main__":
    defs.get_implicit_global_asset_job_def().execute_in_process()
