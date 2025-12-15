from omanta_3rd.infra.jquants import JQuantsClient
c = JQuantsClient()
j = c.get('/listed/info', params={'date':'2025-12-12'})
row = j['info'][0]
print(sorted(row.keys()))
