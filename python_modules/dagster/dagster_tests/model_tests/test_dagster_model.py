import pytest
from dagster._model import DagsterModel
from dagster._utils.cached_method import CACHED_METHOD_CACHE_FIELD, cached_method
from pydantic import ValidationError


def test_override_constructor_in_subclass():
    class MyClass(DagsterModel):
        foo: str
        bar: int

        def __init__(self, foo: str, bar: int):
            super().__init__(foo=foo, bar=bar)

    MyClass(foo="fdsjk", bar=4)


def test_override_constructor_in_subclass_different_arg_names():
    class MyClass(DagsterModel):
        foo: str
        bar: int

        def __init__(self, fooarg: str, bararg: int):
            super().__init__(foo=fooarg, bar=bararg)

    MyClass(fooarg="fdsjk", bararg=4)


def test_override_constructor_in_subclass_wrong_type():
    class MyClass(DagsterModel):
        foo: str
        bar: int

        def __init__(self, foo: str, bar: str):
            super().__init__(foo=foo, bar=bar)

    with pytest.raises(ValidationError):
        MyClass(foo="fdsjk", bar="fdslk")


def test_model_copy():
    class MyClass(DagsterModel):
        foo: str
        bar: int

    obj = MyClass(foo="abc", bar=5)
    assert obj.model_copy(update=dict(foo="xyz")) == MyClass(foo="xyz", bar=5)
    assert obj.model_copy(update=dict(bar=6)) == MyClass(foo="abc", bar=6)
    assert obj.model_copy(update=dict(foo="xyz", bar=6)) == MyClass(foo="xyz", bar=6)


def test_non_model_param():
    class SomeClass: ...

    class OtherClass: ...

    class MyModel(DagsterModel):
        some_class: SomeClass

    MyModel(some_class=SomeClass())

    with pytest.raises(ValidationError):
        MyModel(some_class=OtherClass())  # wrong class

    with pytest.raises(ValidationError):
        MyModel(some_class=SomeClass)  # forgot ()


def test_cached_method() -> None:
    class CoolModel(DagsterModel):
        name: str

        @cached_method
        def calculate(self, n: int):
            return {self.name: n}

        @cached_method
        def reticulate(self, n: int):
            return {self.name: n}

    m = CoolModel(name="bob")
    assert m.calculate(4) is m.calculate(4)
    assert m.calculate(4) is not m.reticulate(4)

    assert CACHED_METHOD_CACHE_FIELD not in m.dict()
