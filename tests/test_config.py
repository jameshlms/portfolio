"""Settings: errors never echo values, and the dotenv file can be switched off."""

from pathlib import Path

import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsConfigDict

from app.config import Settings, settings

_SECRET = "github_pat_FAKE0123456789abcdefghijklmnop"


def _from_file(env: Path | None) -> Settings:
    """Settings read from `env` (None: no dotenv file), keeping every other option."""

    class FromFile(Settings):
        model_config = SettingsConfigDict(env_file=env)

    return FromFile()


def test_unknown_dotenv_key_fails_by_name_without_its_value(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(f"STALE_TOKEN={_SECRET}\n")

    with pytest.raises(ValidationError) as raised:
        _from_file(env)

    assert "stale_token" in str(raised.value)
    assert _SECRET not in str(raised.value)
    assert _SECRET[:12] not in str(raised.value)  # not even Pydantic's truncated echo


def test_invalid_value_is_reported_without_it(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(f"DEBUG={_SECRET}\n")  # not a boolean

    with pytest.raises(ValidationError) as raised:
        _from_file(env)

    assert "debug" in str(raised.value)
    assert _SECRET[:12] not in str(raised.value)


def test_dotenv_file_is_read_when_given(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("SITE_NAME=From the file\n")

    assert _from_file(env).site_name == "From the file"


def test_the_test_run_reads_no_dotenv_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # conftest sets PORTFOLIO_ENV_FILE="" before app.config is imported, so the app's
    # settings read no dotenv file; a .env in the working directory changes nothing.
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("SITE_NAME=Should not be read\n")

    assert Settings.model_config.get("env_file") is None
    assert Settings().site_name != "Should not be read"
    assert settings.site_name != "Should not be read"
