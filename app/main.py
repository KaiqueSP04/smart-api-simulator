from fastapi import FastAPI

from .parser import parse_openapi, get_endpoints
from .simulation_engine import SimulationEngine


app = FastAPI(
    title="Smart API Simulator",
    version="0.1.0"
)


contract = parse_openapi("contracts/test-api.yaml")
endpoints = get_endpoints(contract)

engine = SimulationEngine(endpoints)


@app.get("/")
def root():
    return {
        "message": "Smart API Simulator funcionando!"
    }


@app.get("/products")
def get_products():
    return engine.simulate("/products", "GET")