from app.parser import parse_openapi, get_endpoints
from app.simulation_engine import SimulationEngine


contract = parse_openapi("contracts/test-api.yaml")
endpoints = get_endpoints(contract)

engine = SimulationEngine(endpoints)

response = engine.simulate("/products", "GET")

print(response)