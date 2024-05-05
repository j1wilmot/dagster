from dagster._core.pipes.project import (
    PipesProject,
)

defs = PipesProject.make_defs()

if __name__ == "__main__":
    defs.get_implicit_global_asset_job_def().execute_in_process()
