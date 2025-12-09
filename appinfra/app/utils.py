def disable_urllib_warnings() -> None:
    import urllib3

    urllib3.disable_warnings()
