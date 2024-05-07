from dagster import asset_check


@asset_check(asset="my_asset")
def my_asset_check(): ...
