"""Gerador deterministico para o experimento, sem modificar a aplicacao."""
import json
from copy import deepcopy
from decimal import Decimal


class MockTradicional:
    def __init__(self):
        self.proximo_pedido = 1
        self.proximo_pagamento = 1

    async def generate(self, context):
        endpoint = context['endpoint']
        path = endpoint['path']
        method = endpoint['method'].upper()
        body = context.get('request_body') or {}
        params = context.get('parameters') or {}
        state = context.get('session_state') or {}
        pedidos = state.get('pedidos') or {}
        pagamentos = state.get('pagamentos') or {}

        if method == 'POST' and path == '/pedidos':
            total = sum((Decimal(str(i['preco_unitario'])) * i['quantidade'] for i in body['itens']), Decimal('0'))
            resposta = {'id': self.proximo_pedido, 'nome_cliente': body['nome_cliente'],
                        'itens': deepcopy(body['itens']), 'total': float(total.quantize(Decimal('0.01'))),
                        'situacao': 'criado'}
            self.proximo_pedido += 1
        elif method == 'POST' and path == '/pagamentos':
            pedido = pedidos[str(body['pedido_id'])]
            resposta = {'id': self.proximo_pagamento, 'pedido_id': body['pedido_id'],
                        'valor': pedido['total'], 'metodo': body['metodo'], 'situacao': 'pendente'}
            self.proximo_pagamento += 1
        elif method == 'POST' and path == '/pedidos/{id}/cancelar':
            resposta = deepcopy(pedidos[str(params['id'])])
            resposta['situacao'] = 'cancelado'
        elif method == 'POST' and path in ('/pagamentos/{id}/confirmar', '/pagamentos/{id}/cancelar'):
            pagamento = pagamentos[str(params['id'])]
            resposta = {'id': int(params['id']), 'pedido_id': pagamento['pedido_id'],
                        'situacao': 'confirmado' if path.endswith('/confirmar') else 'cancelado'}
        elif method == 'GET' and path in ('/pedidos/{id}', '/pagamentos/{id}'):
            colecao = pedidos if path.startswith('/pedidos') else pagamentos
            resposta = deepcopy(colecao[str(params['id'])])
        else:
            raise NotImplementedError(f'Endpoint nao configurado: {method} {path}')
        return json.dumps(resposta, ensure_ascii=False)
