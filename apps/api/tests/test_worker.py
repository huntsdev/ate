def test_synthetic_task_uses_json_and_returns_no_business_data(settings):
    from worker import celery_app, noop

    assert celery_app.conf.accept_content == ["json"]
    assert celery_app.conf.task_serializer == "json"
    assert noop.run() == {"status": "ok"}
    assert celery_app.conf.result_expires == 300
