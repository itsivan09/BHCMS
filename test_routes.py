from app import app

routes = {}
for rule in app.url_map.iter_rules():
    if rule.endpoint not in routes:
        routes[rule.endpoint] = []
    routes[rule.endpoint].append(rule.rule)

critical = ['dashboard', 'patients', 'inventory', 'bhw_dashboard', 'community_events']
print("\n✓ ROUTE AVAILABILITY CHECK:")
for route in critical:
    if route in routes:
        print(f"  ✓ {route}: {routes[route][0]}")
    else:
        print(f"  ✗ {route}: NOT FOUND")