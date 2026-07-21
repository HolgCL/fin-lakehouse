from fin_lakehouse.config import Settings


def test_settings_have_defaults() -> None:
    settings = Settings(_env_file=None)
    assert settings.dbt_target == "dev"
    assert "fin-lakehouse" in settings.sec_user_agent
