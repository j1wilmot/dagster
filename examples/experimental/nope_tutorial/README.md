# Nope: Medium-code orchestration platform

Nope is a way to structure your Dagster projects to enable medium-code orchestration of external scripts and computations. 

### What is medium code why does it need a platform?

The term "low code" typically defines tools that have GUI interfaces for creating software programs. "Low code" implies the existence of "high code." We define high code as working in full-fledged development environment with formalized software best practices.

Neither of these terms is sufficient to describe a large swath of practitioners working in data. Is someone who periodically writes scripts, dbt models, or notebooks "high code" or "low code"? We submit that they are neither. 

They are "medium code" developers. They write software in turing-complete languages or transformation languages such as SQL. However they are also not traditional full-time software engineers or do not want to behave as one in the data context. Data scientists, data engineers, analytics engineers often want to work this way, as do some software engineers when operating within the data platform context.

Nope assumes that medium code engineers already have a python environment and toolchain for writing and deploying their business logic. This might be a notebooking platform, a compute environment like Ray, Modal, or Sagemaker, or a bespoke toolchain. It is a *non-goal* of Nope to improve that existing workflow.

Instead the goal of Nope is to allow those users to incorporate their code into the Dagster Asset Graph without learning another Python Environment (hence the name Nope: "NO Python Environment"). The success criteria for the practitioner is straightforward: They should be able to author a yaml file which plugs their existing script/computation into the data platform without installing or interacting with an additional Python environment.

Nope critically also offers a platform that a software engineer can manage for the medium code data practitioners they serve. A platform owner can customize the harness for their particular use case and technology.

## Hello world asset

To get started you'll need to create a `definitions.py` file and a `defs` folder. 

* `definitions.py` is the file that actually creates a `Definitions` object. 
* `defs` is the folder that contains all the business logic for your assets. The code in `definitions.py` introspects `defs` to build the asset graph.

`definitions.py`:
```python 
from dagster._nope import NopeProject

defs = NopeProject.make_definitions()
```

This is a vanilla Dagster `Definitions` object, build with a special factory function, `NopeProject.make_definitions`.

Next you need to make a `defs` folder. The first level of a `defs` folder defines group. They provide structure and organization to assets in Dagster. Assets are defined within groups.

So in this case we make a folder `defs` and then `group_a`. Finally we make a Python that contains the business logic for the asset at `defs/group_a/asset_one.py`. In this case we just print "hello."

```python
if __name__ == "__main__":
    print("hello")
```

Next you need a manifest file, which is a yaml file that tells Dagster how to invoke this script. In this case, we only need to know how to invoke the script, via a subprocess.  (The default `subprocess` target uses Dagster Pipes, but this is an implementation detail.)

```yaml
target: subprocess
```

With these two files in place we can load them in Dagster UI with `dagster dev -f definitions.py`.

![Screenshot 2024-05-04 at 2 23 04 PM](https://github.com/dagster-io/dagster/assets/28738937/6244402d-35ca-41fa-bcdc-a81dcac56876)

Note that the folder you made, `group_a`, corresponds to a group in the left nav. Similarly the file you created `asset_one.py`, creates an asset called `asset_one`. (Note: For dagster veterans the asset key of this asset is `group_a/asset_one` as well.) If you click on the asset, more information appears:

![Screenshot 2024-05-04 at 2 24 36 PM](https://github.com/dagster-io/dagster/assets/28738937/9a01adaf-df4d-4bcc-9c8f-0c07c24d3c06)

The entire contents of the python file are included in the description for your convenience. In addition, you'll note that there is a "Code Version." Dagster uses this to detect if your code has changed and requires recomputation to keep your assets up-to-date. It is just a hash computed from the contents of your pipes script. We'll come back to that later.

Next you can click on asset and materialize it. You are off to the races!

### Commentary on Hello World

During this README I'm going to interrrupt it with commentary to note decisions made for users.

* We are heavily opting the user into groups here. There a couple reasons here.
    * This make groups "heavier" here and make them a function of filesystem layout. The "default" group would have confused that mental model considerably, so I just made it impossible to create an asset without a group. We could find lighterweight solutions here, but I think the outcome is pretty reasonable.
    * Out of the box this system incorporates group name into the asset key. In general Nope 1) will never introduce the concept of asset prefix 2) will assume that groups are just incorporated into the asset key and 3) let the advanced user opt into explicit asset key management if they want to do so.
* Forcing a file-per-script gets us a bunch of a stuff for free. Two of them are right up front: rendering the python code in the UI and usage of the code versioning system.

## Building the graph

Now we want to build the asset graph and leverage it. For that we need dependencies. First let's create a second asset file `asset_two.py`:

Now we need to tell the system about this dependency. We do that via a manifest file which, in addition to kind, also informs the system that it has an upstream dependency on `asset_one`.

```yaml
target: subprocess
deps:
  - group_a/asset_one
```

Now reload your definitions and you should see a dependency graph:

![Screenshot 2024-05-04 at 2 48 13 PM](https://github.com/dagster-io/dagster/assets/28738937/371ea9d3-82a4-47e5-8192-f3ddad48af84)

We also want to add metadata about the underlying physical assets we are creating. For this we can use [Pipes](https://docs.dagster.io/guides/dagster-pipes) (which is the default harness for Nope out-the-box), which has lightweight APIs for reporting metadata events.

```python
from dagster_pipes import open_dagster_pipes


def main(pipes) -> None:
    pipes.log.info("Hello from asset two.")
    pipes.report_asset_materialization(metadata={"metadata": "value_one"})


if __name__ == "__main__":
    with open_dagster_pipes() as pipes:
        main(pipes)
```

Now we can materialize the asset and see the metadata events in the catalog.

![Screenshot 2024-05-05 at 2 33 27 PM](https://github.com/dagster-io/dagster/assets/28738937/c7009a56-23b0-4a82-856d-7f021d181622)

### Commentary on graph construction

Just a few things to note:

* A stakeholder can add themselves to the asset graph via a manifest without touching Python in the dagster environment.,
* This could easily plug into any tooling we create for the YAML DSL for typeaheads etc. DevRel/Yaml crew is already working on this so I did not replicate it.
* Dependencies must be fully qualified (no asset key prefixes or anything) and it parses forward slashes, which is much more convenient than arrays of strings. Requiring full qualification is an explicit tradeoff for obviousness/debuggability/clarity at the expense of some additional typing when writing manifest files.
* The asset key by default is `{group_name}/{asset_name}`

## Multiple assets in a invocation target 

Sometimes scripts/computations materialize more than a single asset in a particular invocation. Nope supports that through its concept of _invocation targets_. 

In this case we are going to simulate creating two assets, `asset_three` and `asset_four` in a single script `assets_three_and_four.py` and return metadata to Dagster using `dagster_pipes`.

```python
from dagster_pipes import open_dagster_pipes


def main(pipes) -> None:
    pipes.log.info("Hello from asset two.")
    pipes.report_asset_materialization(asset_key="group_a/asset_three", metadata= {"metadata": "value_one"})
    pipes.report_asset_materialization(asset_key="group_a/asset_four", metadata= {"metadata": "value_two"})

if __name__ == "__main__":
    with open_dagster_pipes() as pipes:
        main(pipes)
```

Now we need to inform the system that this script materializes two assets, and that they both depend on `asset_two`. We can do this via the manifest. By using the top-level key `assets` we inform the manifest system there are multiple assets encoded in the manifest:

`assets_three_and_four.yaml`:

```yaml
assets:
  asset_three:
    deps:
      - group_a/asset_two
  asset_four:
    deps:
      - group_a/asset_two
```

In the language of Nope, `asset_three_and_four` is single _invocation target_ that materializes two _assets_. 

### Commentary

* It would be straight forward to extend this with a top-level `checks` key to support asset checks.

## Customizing the platform metadata

As a platform owner you will want to customize this for your stakeholders. Nope provide pluggability points for customizing manifests as well as invocation behavior, allowing your stakeholders to write manifest files and code in invocation target environments (e.g. scripts, notebooks, code in hosted runtimes), but allowing you to programmaticaly control the create of asset definitions.

For example, let's imagine that we wanted to automatically set the "compute kind" tag to be Python for display in the asset graph and, for every asset, make the default owner "team:foobar" if manifest did not specify an owner. But we decided that an asset author is allowed to completely override the field, rather than merge. This is the platform owner making cross-cutting business logic decisions in the platform, that she wants to encode in code.

The first step is to create a custom subclass for your project.

```python
class TutorialProject(NopeProject):
    ...

defs = TutorialProject.make_definitions()
```

Nope has "invocations targets", which correspond to an invocation of some external runtime. Previously in the tutorial you specified `target: subprocess` in the manifest file, indicating the the invocation target was "subprocess". The yaml file is technically an _invocation target manifest_.

"Compute kinds" are attached to invocation targets so we have to customize the invocation target manifest. We have to create a new class that inherits from `NopeInvocationTargetManifest` and customize the tags behavior. Thie class must be named `InvocationTargetManifest` and be within your custom project class.

```python
class TutorialProject(NopeProject):
    class InvocationTargetManifest(NopeInvocationTargetManifest):
        @property
        def tags(self) -> dict:
            return {**{"kind": "python"}, **super().tags}
```

Next we want to do a similar thing at the asset level. For that we override a `NopeAssetManifest`, and in similar fashion, override a class method in our `TutorialProject` class.

```python
class TutorialProject(NopeProject):
    class AssetManifest(NopeAssetManifest):
        @property
        def owners(self) -> list:
            owners_from_manifest_file = super().owners
            return owners_from_manifest_file if owners_from_manifest_file else ["team:foobar"]
    ...
```

## Customizing Platform Execution

TODO

## Future work

* Asset checks: Straightforward to add asset check support to the script manifest. Just need to do so.
* Deployment and Branch Deployment Management: A structure like this is highly amenable to tooling support for deployment. Imagine the ability to have a command line utility that invokes user-defined functions that script deployment of code. That script could have the branch name in context. Imagine moving code into a well-known spot in databricks or another hosted runtime. We could invoke that function on startup in dagster dev, during branch deployment creation, or any number of scenarios. The idea here is that the we have just a little support for shipping the python code the stakeholder writes into an environment they can invoke via the pipes client.
* Partitioning support: Add partitioning support. My first proposal would be to have the `definitions.py` create a static set partition definitions avaiable for use by the stakeholders, which could be referenced by key in the manifest file.
* Declarative scheduling support: Supporting cron strings in the manifest is straightforward. For more complex scheduling rules, I think the mental model is that the platform owner "publishes" a set of rule expressions that stakeholders can key into. But complex scheduling conditions should be strictly confined to the native python APIs.
