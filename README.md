# Smart API Simulator

Protótipo de uma plataforma para simulação inteligente de APIs REST a partir de contratos OpenAPI.

O **Smart API Simulator** interpreta contratos OpenAPI, identifica endpoints, parâmetros e schemas, e disponibiliza uma API simulada capaz de gerar respostas dinamicamente de acordo com o contrato recebido. O sistema também mantém estado entre requisições de uma mesma sessão, permitindo representar fluxos encadeados.

O projeto é desenvolvido como parte de um Trabalho de Conclusão de Curso (TCC).

---

## Objetivo

O objetivo do projeto é desenvolver e validar um protótipo de simulador de APIs REST baseado em contratos OpenAPI, utilizando um modelo de linguagem para geração dinâmica de respostas.

O sistema considera:

* Contratos OpenAPI;
* Parâmetros das requisições;
* Schemas de entrada e saída;
* Estado persistente entre requisições;
* Validação das respostas geradas;
* Geração dinâmica de respostas por meio do Google Gemini;
* Tratamento de respostas inválidas e novas tentativas de geração.

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
Google Gemini
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
4. solicita a geração da resposta pelo modelo de linguagem;
5. valida o payload gerado;
6. realiza novas tentativas quando o payload é inválido;
7. retorna a resposta simulada ou um erro apropriado.

### ContextBuilder

Responsável por construir o contexto utilizado durante a simulação.

O contexto pode incluir:

* endpoint atual;
* parâmetros recebidos;
* request body;
* schema da requisição;
* schema da resposta;
* estado da sessão.

O sistema utiliza o contexto relevante para a requisição atual, evitando o envio desnecessário de todo o contrato OpenAPI ao modelo de linguagem.

### LLMAdapter

Camada responsável pela comunicação com o Google Gemini.

O `LLMAdapter` isola a integração do modelo de linguagem do restante do sistema. Dessa forma, o `SimulationEngine` não depende diretamente da implementação específica da API do Gemini.

O adapter:

* constrói o prompt a partir do contexto;
* envia a solicitação ao Gemini;
* solicita respostas em JSON estruturado de acordo com o schema;
* retorna o conteúdo gerado para o `SimulationEngine`;
* possui controle de timeout.

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

Quando uma resposta gerada não atende ao schema, o sistema pode realizar até três tentativas de geração.

### SessionManager

Responsável pelo gerenciamento do estado das sessões.

O estado é armazenado no MongoDB e pode ser recuperado posteriormente utilizando um identificador de sessão enviado pela requisição.

As sessões possuem expiração automática após 30 minutos por meio de um índice TTL do MongoDB.

---

## Persistência de estado

O sistema utiliza o MongoDB Atlas para armazenar o estado das sessões.

Cada sessão pode ser identificada pelo header:

```text
X-Session-ID
```

Exemplo:

```http
X-Session-ID: teste-001
```

Quando uma requisição utiliza um identificador de sessão existente, o estado correspondente é recuperado e incorporado ao contexto utilizado durante a simulação.

Esse mecanismo será utilizado para representar fluxos encadeados, como criação de pedido e processamento de pagamento.

---

## Integração com Google Gemini

O Google Gemini é utilizado para gerar dinamicamente as respostas simuladas.

A comunicação com o modelo ocorre exclusivamente por meio do `LLMAdapter`:

```text
SimulationEngine
       ↓
LLMAdapter
       ↓
Google Gemini
       ↓
LLMAdapter
       ↓
SimulationEngine
```

As respostas são solicitadas em formato JSON estruturado com base no schema de resposta definido pelo contrato OpenAPI.

O sistema também possui:

* timeout para chamadas ao Gemini;
* tratamento de limite de requisições;
* tratamento de indisponibilidade do serviço;
* validação do payload gerado;
* novas tentativas quando o payload gerado é inválido.

A integração com o Gemini está implementada e será validada posteriormente por meio de testes de fluxo completo envolvendo pedidos e pagamentos.

---

## Tecnologias utilizadas

| Tecnologia       | Utilização                            |
| ---------------- | ------------------------------------- |
| Python 3.11      | Linguagem principal                   |
| FastAPI          | Framework da API REST                 |
| Pydantic         | Modelagem e validação de dados        |
| PyYAML           | Leitura dos contratos OpenAPI em YAML |
| MongoDB Atlas    | Persistência do estado das sessões    |
| PyMongo          | Comunicação com MongoDB               |
| Google Gemini    | Geração dinâmica de respostas         |
| Google GenAI SDK | Integração com a API do Gemini        |
| Swagger UI       | Documentação e testes da API          |
| Railway          | Hospedagem planejada                  |
| Git / GitHub     | Controle de versão                    |

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
│   ├── validator.py
│   └── llm_adapter.py
│
├── contracts/
│   └── test-api.yaml
│
├── test_gemini.py
├── test_llm_adapter.py
├── test_retry.py
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
* acesso de rede autorizado no MongoDB Atlas;
* uma chave de API do Google Gemini.

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

```powershell
pip install -r requirements.txt
```

---

## Configuração

Crie um arquivo `.env` na raiz do projeto:

```env
MONGODB_URI=mongodb+srv://USUARIO:SENHA@SEU_CLUSTER.mongodb.net/?appName=Cluster0
GEMINI_API_KEY=sua_chave
```

Substitua os valores pelos dados das suas respectivas configurações.

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

A partir dele, o sistema registra automaticamente os endpoints definidos no contrato.

### Exemplo: listar produtos

```http
GET /products
```

Também é possível enviar o parâmetro opcional:

```http
GET /products?category=electronics
```

### Exemplo: criar produto

```http
POST /products
```

Com o corpo:

```json
{
  "name": "Mouse Gamer",
  "price": 150
}
```

O sistema valida o corpo da requisição de acordo com o schema definido no contrato e solicita ao Gemini a geração da resposta.

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

Quando houver estado armazenado para a sessão, ele será recuperado pelo `SessionManager` e incorporado ao contexto utilizado pelo `ContextBuilder`.

Esse mecanismo permite que diferentes requisições compartilhem informações dentro de uma mesma sessão.

---

## Testes automatizados e de integração

O projeto possui testes auxiliares para validar componentes específicos do sistema.

Entre eles:

* `test_gemini.py` — verifica a conexão com o Gemini;
* `test_llm_adapter.py` — verifica a comunicação do `LLMAdapter` com o modelo;
* `test_retry.py` — verifica o comportamento de novas tentativas para respostas inválidas;
* `test_mongodb.py` — verifica a conexão com o MongoDB;
* `test_session_manager.py` — verifica o gerenciamento das sessões;
* `test_session_api.py` — verifica o uso de sessões através da API.

Os testes de latência e de diferentes níveis de `thinking` utilizados durante o desenvolvimento são diagnósticos e não fazem parte do fluxo principal da aplicação.

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
* [x] Integração do `LLMAdapter` com o Google Gemini
* [x] Geração dinâmica de respostas
* [x] Respostas estruturadas em JSON
* [x] Validação das respostas geradas pelo Gemini
* [x] Retry para payloads inválidos
* [x] Timeout para chamadas ao Gemini
* [x] Tratamento básico de erros do serviço do Gemini

### Próxima etapa

* [ ] Testar o fluxo completo de pedidos e pagamentos utilizando uma mesma sessão
* [ ] Validar a coerência do estado entre requisições
* [ ] Corrigir eventuais problemas encontrados nos testes de integração
* [ ] Realizar melhorias finais no sistema

---

## Domínio experimental

O domínio utilizado para validação do protótipo é o de **e-commerce**, com foco em:

* pedidos;
* pagamentos;
* processamento de pagamentos;
* fluxos encadeados entre endpoints;
* manutenção de estado entre requisições.

O objetivo dos testes finais é verificar se o simulador consegue utilizar o contexto da sessão para produzir respostas coerentes ao longo desses fluxos.

---

## Observações

O projeto encontra-se em desenvolvimento no contexto de um Trabalho de Conclusão de Curso.

O contrato de teste atualmente utilizado possui escopo controlado e serve para validar o funcionamento do protótipo antes da realização dos testes finais com o domínio de pedidos e pagamentos.
