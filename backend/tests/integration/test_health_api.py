def test_health_endpoint_returns_healthy_status(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

