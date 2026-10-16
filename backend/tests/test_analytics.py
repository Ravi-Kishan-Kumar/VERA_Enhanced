"""Tests for analytics endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_analytics_performance(client: TestClient) -> None:
    res = client.get("/api/analytics/performance")
    assert res.status_code == 200
    data = res.json()
    assert "overall_mae" in data
    assert "rating_inflation_index" in data
    assert "total_reviews" in data
    assert "completed_reviews" in data


def test_analytics_agents(client: TestClient) -> None:
    res = client.get("/api/analytics/agents")
    assert res.status_code == 200
    data = res.json()
    assert "agent_1_preprocessor" in data
    assert "agent_2_experience_extractor" in data
    assert "agent_3_absa" in data
    assert "agent_7_fusion_ensemble" in data


def test_analytics_aspects(client: TestClient) -> None:
    res = client.get("/api/analytics/aspects")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) == 10
    aspect_names = [a["aspect"] for a in data]
    assert "sound_quality" in aspect_names
    assert "comfort" in aspect_names


def test_analytics_model_info(client: TestClient) -> None:
    res = client.get("/api/analytics/model-info")
    assert res.status_code == 200
    data = res.json()
    assert "earbuds_pipeline" in data
    assert "headphones_pipeline" in data
    assert "gates" in data
