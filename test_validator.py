from app.application.validator import PayloadValidator


validator = PayloadValidator()

schema = {
    "type": "object",
    "required": ["name", "price"],
    "properties": {
        "name": {
            "type": "string"
        },
        "price": {
            "type": "number"
        }
    }
}

valid_payload = {
    "name": "Notebook",
    "price": 2500
}

invalid_payload = {
    "name": "Notebook",
    "price": "2500"
}

print("Payload válido:", validator.validate(valid_payload, schema))
print("Payload inválido:", validator.validate(invalid_payload, schema))