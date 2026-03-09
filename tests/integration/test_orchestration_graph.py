from orchestrator.core.runtime import ResponsePackage, run_once


def test_user_message_to_evidence_and_response() -> None:
    result = run_once("analyze this dataset")

    evidence = result.get("validated_evidence", [])
    assert len(evidence) >= 1
    assert evidence[0]["validated"] is True

    response = result.get("response_package")
    assert isinstance(response, ResponsePackage)
    assert response.evidence_count >= 1
    assert response.scenario == "factual_qa"
    assert "validated evidence" in response.text

    assert result.get("persist_status") == "stored"
