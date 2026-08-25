def test_package_exposes_version() -> None:
    import werewolf_arena

    assert werewolf_arena.__version__ == "0.1.0"
