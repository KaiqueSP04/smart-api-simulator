from app.parser import parse_openapi, get_endpoints


contract = parse_openapi("contracts/test-api.yaml")

endpoints = get_endpoints(contract)

for endpoint in endpoints:
    print(endpoint)