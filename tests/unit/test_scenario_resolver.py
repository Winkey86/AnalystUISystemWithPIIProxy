from orchestrator.planner.scenario_resolver import resolve_scenario_id


def test_resolver_prefers_file_analysis_when_attachment_present() -> None:
    scenario_id = resolve_scenario_id("что в файле", attachments=["report.csv"])
    assert scenario_id == "file_analysis"


def test_resolver_uses_artifact_first_for_chart_or_document_requests() -> None:
    assert resolve_scenario_id("Покажи график по данным") == "artifact_first_response"
    assert resolve_scenario_id("Собери документ по анализу") == "artifact_first_response"
    assert resolve_scenario_id("Добавь картинку с результатом") == "artifact_first_response"


def test_resolver_falls_back_to_factual_qa() -> None:
    assert resolve_scenario_id("Объясни метрику retention") == "factual_qa"
