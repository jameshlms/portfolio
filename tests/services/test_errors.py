import inspect

import pytest

from app.services import errors

_ERRORS = [
    cls
    for _, cls in inspect.getmembers(errors, inspect.isclass)
    if issubclass(cls, Exception) and cls.__module__ == errors.__name__
]


@pytest.mark.parametrize("cls", _ERRORS, ids=lambda c: c.__name__)
def test_every_error_is_a_domain_error(cls: type[Exception]) -> None:
    assert issubclass(cls, errors.DomainError)


def test_field_errors_are_read_only_and_described() -> None:
    e = errors.InvalidPost("a-post", {"title": "Required.", "tags": "A list."})

    assert str(e) == "a-post: title: Required.; tags: A list."
    with pytest.raises(TypeError):
        e.errors["title"] = "changed"  # type: ignore[index]
