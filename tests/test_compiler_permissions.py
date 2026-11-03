from conftest import new_project


def test_untrusted_frontend_graph_is_rejected(system):
    c, db, h = system
    p = new_project(c, h)
    path = '/api/v2/projects/'+p['id']+'/workflow/compile'
    malicious = {'nodes':[{'id':'a'}], 'connections':[{'from':'a','to':'a'}]}
    assert c.post(path, headers=h['alice'], json=malicious).status_code == 422
    assert c.post(path, headers=h['alice'], json={'expected_version':999}).status_code == 409
    assert c.post(path, headers=h['alice']).status_code == 200
    for _ in range(3):
        assert c.post('/api/v2/projects/'+p['id']+'/agent-runs',headers=h['alice'],json={'expected_version':1}).status_code == 200
    assert c.post('/api/v2/projects/'+p['id']+'/agent-runs',headers=h['alice'],json={'expected_version':1}).status_code == 429
