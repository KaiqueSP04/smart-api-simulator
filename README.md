# Smart API Simulator

Protótipo de uma plataforma para simulação inteligente de APIs REST a partir de contratos OpenAPI.

O **Smart API Simulator** interpreta contratos OpenAPI, identifica endpoints, parâmetros e schemas, e disponibiliza uma API simulada capaz de gerar respostas de acordo com o contrato recebido. O projeto utiliza persistência de estado para permitir que diferentes requisições de uma mesma sessão mantenham contexto entre si.

O projeto é desenvolvido como parte de um Trabalho de Conclusão de Curso (TCC).

---

## Objetivo

O objetivo do projeto é desenvolver e validar um protótipo de simulador de APIs REST baseado em contratos OpenAPI, utilizando modelos de linguagem para geração dinâmica de respostas.

O sistema busca permitir simulações mais próximas do comportamento de uma API real, considerando:

* Contratos OpenAPI;
* Parâmetros das requisições;
* Schemas de entrada e saída;
* Estado persistente entre requisições;
* Validação das respostas geradas;
* Geração dinâmica de respostas por meio de um modelo de linguagem;
* Simulação de diferentes cenários de resposta.

O domínio experimental definido para o projeto é:

> **Simulação inteligente de APIs REST de pedidos e processamento de pagamentos para e-commerce, baseada em contratos OpenAPI.**

---

## Como o sistema funciona

O fluxo principal do sistema é:

```text
Contrato OpenAPI
       ↓
OpenAPI Parser
       ↓
SimulationEngine
       ↓
ContextBuilder
       ↓
LLMAdapter
       ↓
Modelo de linguagem
       ↓
PayloadValidator
       ↓
Resposta simulada
       ↓
Persistência de estado
```

### OpenAPI Parser

Responsável por interpretar o contrato OpenAPI e extrair informações dos endpoints, incluindo:

* método HTTP;
* caminho;
* resumo;
* parâmetros;
* request body;
* respostas;
* schemas.

### SimulationEngine

É responsável por orquestrar o processo de simulação.

Ele:

1. identifica o endpoint correspondente à requisição;
2. solicita a construção do contexto;
3. verifica o request body quando aplicável;
4. solicita a geração da resposta;
5. valida o payload gerado;
6. retorna a resposta simulada.

### ContextBuilder

Responsável por construir o contexto utilizado durante a simulação.

O contexto pode incluir:

* endpoint atual;
* parâmetros recebidos;
* request body;
* schema da requisição;
* schema da resposta;
* estado da sessão.

O sistema utiliza apenas o contexto relevante para a requisição atual, evitando o envio desnecessário de todo o contrato OpenAPI ao modelo de linguagem.

### SessionManager

Responsável pelo gerenciamento do estado das sessões.

O estado é armazenado no MongoDB e pode ser recuperado posteriormente utilizando um identificador de sessão enviado pela requisição.

Atualmente, as sessões possuem expiração automática após 30 minutos por meio de um índice TTL do MongoDB.

### PayloadValidator

Responsável por verificar se os payloads estão de acordo com os schemas definidos no contrato OpenAPI.

Atualmente são verificados tipos como:

* object;
* array;
* string;
* integer;
* number;
* boolean.

Também são verificados campos obrigatórios e schemas de itens em arrays.

### LLMAdapter

Camada responsável pela comunicação com o modelo de linguagem.

Essa camada será utilizada para isolar a integração do restante do sistema, permitindo que o `SimulationEngine` não dependa diretamente da implementação específica da API do modelo.

**Integração com Gemini: em desenvolvimento.**

---

## Persistência de estado

O sistema utiliza o MongoDB Atlas para armazenar o estado das sessões.

Cada sessão possui um identificador:

```text
X-Session-ID
```

Exemplo:

```http
X-Session-ID: teste-001
```

Quando uma requisição é realizada com um identificador de sessão existente, o estado correspondente pode ser recuperado e incorporado ao contexto da simulação.

Exemplo conceitual:

```text
POST /orders
       ↓
Sessão: teste-001
       ↓
Estado armazenado:
{
  "order_id": "ORD-001",
  "status": "created"
}
       ↓
Nova requisição
       ↓
ContextBuilder recupera o estado
```

Esse mecanismo será utilizado posteriormente para representar fluxos encadeados, como criação de pedido e processamento de pagamento.

---

## Tecnologias utilizadas

| Tecnologia    | Utilização                                       |
| ------------- | ------------------------------------------------ |
| Python 3.11   | Linguagem principal                              |
| FastAPI       | Framework da API REST                            |
| Pydantic      | Modelagem e validação de dados                   |
| PyYAML        | Leitura dos contratos OpenAPI em YAML            |
| MongoDB Atlas | Persistência do estado das sessões               |
| PyMongo       | Comunicação com MongoDB                          |
| Google Gemini | Geração dinâmica de respostas — em implementação |
| Swagger UI    | Documentação e testes da API                     |
| Railway       | Hospedagem planejada                             |
| Git / GitHub  | Controle de versão                               |

---

## Estrutura do projeto

```text
smart-api-simulator/
│
├── app/
│   ├── main.py
│   ├── models.py
│   ├── parser.py
│   ├── simulation_engine.py
│   ├── context_builder.py
│   ├── session_manager.py
│   └── validator.py
│
├── contracts/
│   └── test-api.yaml
│
├── test_mongodb.py
├── test_session_manager.py
├── test_session_api.py
│
├── .env
├── .gitignore
├── requirements.txt
└── README.md
```

> O arquivo `.env` não deve ser versionado, pois contém informações de configuração e credenciais.

---

## Requisitos

Para executar o projeto localmente, é necessário ter:

* Python 3.11 ou superior;
* Git;
* uma conta no MongoDB Atlas;
* um cluster MongoDB;
* um usuário de banco de dados configurado;
* acesso de rede autorizado no MongoDB Atlas.

A integração com o Gemini também exigirá uma chave de API quando essa etapa estiver configurada.

---

## Instalação

Clone o repositório:

```bash
git clone https://github.com/KaiqueSP04/smart-api-simulator.git
```

Entre no diretório:

```bash
cd smart-api-simulator
```

Crie um ambiente virtual:

```bash
python -m venv .venv
```

Ative o ambiente virtual no Windows:

```powershell
.venv\Scripts\Activate.ps1
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

---

## Configuração do MongoDB

Crie um arquivo `.env` na raiz do projeto:

```env
MONGODB_URI=mongodb+srv://USUARIO:SENHA@SEU_CLUSTER.mongodb.net/?appName=Cluster0
```

Substitua os valores pelos dados da sua conexão do MongoDB Atlas.

O arquivo `.env` deve permanecer fora do controle de versão.

---

## Executando a aplicação

Com o ambiente virtual ativado:

```powershell
uvicorn app.main:app --reload
```

A aplicação ficará disponível em:

```text
http://127.0.0.1:8000
```

A documentação interativa do Swagger pode ser acessada em:

```text
http://127.0.0.1:8000/docs
```

---

## Testando a API

O contrato de teste atualmente utilizado está em:

```text
contracts/test-api.yaml
```

A partir dele, o sistema registra os endpoints definidos no contrato.

### Exemplo: listar produtos

```http
GET /products
```

Também é possível enviar o parâmetro opcional:

```http
GET /products?category=electronics
```

### Exemplo de resposta

```json
{
  "status_code": 200,
  "data": [
    {
      "id": 1,
      "name": "exemplo",
      "price": 10.0
    }
  ],
  "parameters": {
    "category": "electronics"
  },
  "request_body": null,
  "context": {
    "endpoint": {
      "method": "GET",
      "path": "/products",
      "summary": "Lista produtos"
    },
    "parameters": {
      "category": "electronics"
    },
    "request_body": null,
    "request_schema": null,
    "response_schema": {},
    "session_state": null
  }
}
```

O conteúdo exato de `response_schema` depende do contrato OpenAPI utilizado.

---

## Testando sessões

Uma requisição pode utilizar o identificador de sessão:

```http
X-Session-ID: teste-001
```

Exemplo:

```powershell
curl.exe -X GET "http://127.0.0.1:8000/products?category=electronics" `
  -H "X-Session-ID: teste-001"
```

Quando houver estado armazenado para a sessão, ele será incluído no contexto utilizado durante a simulação.

---

## Estado atual do desenvolvimento

### Implementado

* [x] Leitura de contratos OpenAPI em YAML
* [x] Extração de endpoints
* [x] Extração de parâmetros
* [x] Identificação de request bodies
* [x] Identificação de response schemas
* [x] Registro automático dos endpoints no FastAPI
* [x] Documentação interativa com Swagger UI
* [x] Geração inicial de payloads baseada em schemas
* [x] Validação de request bodies
* [x] Validação de payloads de resposta
* [x] Integração com MongoDB Atlas
* [x] Gerenciamento de sessões
* [x] Expiração automática das sessões
* [x] Recuperação de estado pelo `X-Session-ID`
* [x] Construção de contexto por endpoint
* [x] Integração do contexto ao `SimulationEngine`

### Em desenvolvimento

* [ ] Integração com Google Gemini
* [ ] Implementação do `LLMAdapter`
* [ ] Geração dinâmica de respostas pelo modelo de linguagem
* [ ] Retry para payloads inválidos
* [ ] Tratamento de ti
