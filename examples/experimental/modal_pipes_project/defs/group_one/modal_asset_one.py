import modal

app = modal.App("schrockn-project-pipes-kicktest")


@app.function()
def asset_one_on_modal() -> None:
    print("This print statement is running on modal's cloud.")


@app.local_entrypoint()
def main() -> None:
    asset_one_on_modal.remote()
