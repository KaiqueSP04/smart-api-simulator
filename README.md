# Smart API Simulator

Plataforma para simulação inteligente de APIs REST a partir de contratos OpenAPI.

O **Smart API Simulator** interpreta contratos OpenAPI, identifica endpoints, parâmetros e schemas, e disponibiliza uma API simulada capaz de gerar respostas dinamicamente de acordo com o contrato recebido. O sistema também mantém estado entre requisições de uma mesma sessão, permitindo representar fluxos encadeados de forma coerente.

---

## Objetivo

O objetivo do projeto é simular APIs REST a partir de contratos OpenAPI, utilizando um modelo de linguagem para geração dinâmica de respostas.

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

## Arquitetura

O projeto segue uma **arquitetura hexagonal leve (Ports and Adapters)**. A aplicação de simulação depende de portas (contratos) e não instancia diretamente Gemini ou MongoDB. Os adaptadores concretos são montados no ponto de composição `app/main.py`, e podem ser substituídos por fakes nos testes.

O contrato OpenAPI fornece endpoints e schemas como configuração da simulação. Ele não é tratado como plugin: o projeto não possui carregamento ou registro de plugins.

Os contratos são declarados como `Protocol` em `app/application/ports.py`. `SimulationEngine` coordena o caso de uso; `ResponseGenerationService` aplica parsing, validação e retries; `SessionResources` concentra leitura e atualização do estado de recursos. `ContextBuilder` é síncrono e não acessa serviços externos. A composição destas classes e seus adaptadores fica em `app/main.py`.

O motor retorna `SimulationResult`, uma dataclass com o recurso gerado ou uma `SimulationFailure` categorizada por `FailureKind`. Ele não decide códigos HTTP para falhas. O contexto é descrito por `SimulationContext` (`TypedDict`), preservando o formato JSON utilizado pelo gerador. Essas estruturas ficam em `app/application/results.py`; as convenções de identificação e criação de recursos ficam centralizadas em `app/application/resource_rules.py`.

O adaptador `app/adapters/http_results.py` traduz os resultados da aplicação para códigos HTTP e para o envelope público (`codigo_status` e `dados`; ou `codigo_status` e `mensagem` para falhas). Com `X-Debug: true`, respostas de sucesso também incluem `diagnostico`, separado dos dados principais. O código de sucesso vem da chave de resposta do contrato OpenAPI. A porta `RequestLog` recebe o resultado tipado; o adaptador MongoDB traduz esse resultado para manter o formato do histórico. Mensagens da aplicação referem-se ao serviço de geração, permitindo trocar o fornecedor de IA.

Para consumidores Python do motor, use `result.data`, `result.failure` e `result.response_key`, em vez de acessar um dicionário HTTP. A versão 2.0 adota campos, situações e rotas em português: `/pedidos`, `/pagamentos`, `/confirmar` e `/cancelar`. Clientes da versão anterior precisam atualizar as chamadas. Comece com um novo `X-Session-ID`, pois recursos antigos não são convertidos para o novo contrato.

`OrderCalculation` implementa a porta `ResponseNormalizer` e é injetado no ponto de composição. Na criação de pedidos, preserva nome e itens enviados e calcula `total` com `Decimal` antes da validação e persistência. O modelo continua fornecendo o ID; o total não depende da IA. Outros contratos podem utilizar outro normalizador ou nenhum.

O fluxo principal do sistema é:

```text
Adaptador HTTP (FastAPI)
       ↓
Aplicação: SimulationEngine
       ├── ContextBuilder / PayloadValidator
       ├── porta ResponseGenerator ── adaptador Gemini
       ├── porta SessionStore ─────── adaptador MongoDB
       └── porta RequestLog ───────── adaptador MongoDB

Contrato OpenAPI ── adaptador/parser ── configuração de endpoints
```

OpenAPI Parser
Responsável por interpretar o contrato OpenAPI e extrair informações dos endpoints, incluindo: método HTTP, caminho, resumo, parâmetros, request body, respostas e schemas.

SimulationEngine
Coordena o fluxo de simulação, delegando as regras específicas aos serviços da aplicação. Ele:

identifica o endpoint correspondente à requisição;
solicita a construção do contexto;
verifica o request body quando aplicável;
consulta ou atualiza o estado por meio de SessionResources;
solicita uma resposta válida ao ResponseGenerationService;
registra a latência e o resultado pelo contrato RequestLog;
retorna a resposta simulada ou um erro apropriado.

ResponseGenerationService
Responsável por chamar a porta ResponseGenerator, interpretar o JSON, validar o schema da resposta, verificar a consistência do id e repetir a geração até três vezes quando necessário. Traduz timeout, limite de requisições e falhas de geração para falhas tipadas da aplicação, que os adaptadores convertem para HTTP.

SessionResources
Encapsula as operações e regras de acesso ao estado dos recursos de uma sessão. Usa a porta SessionStore, sem conhecer a implementação MongoDB.
ContextBuilder
Responsável por construir o contexto utilizado durante a simulação, que pode incluir: endpoint atual, parâmetros recebidos, request body, schema da requisição, schema da resposta e estado da sessão.

O sistema utiliza apenas o contexto relevante para a requisição atual, evitando o envio desnecessário de todo o contrato OpenAPI ao modelo de linguagem.

GeminiResponseGenerator
Adaptador que implementa a porta ResponseGenerator e isola a comunicação com o Google Gemini. O SimulationEngine trabalha com a porta, sem depender do SDK ou do cliente do Gemini.

O adapter constrói o prompt a partir do contexto, envia a solicitação ao Gemini, solicita respostas em JSON estruturado de acordo com o schema, retorna o conteúdo gerado e possui controle de timeout próprio e confiável.

Antes do envio, `app/adapters/gemini_schema.py` adapta uma cópia do schema: converte limites exclusivos booleanos do OpenAPI 3.0 para limites numéricos e omite `maxItems`, cujo valor 100 foi rejeitado pelo modelo configurado. O contrato, o Swagger e a validação local continuam usando as regras originais, inclusive o limite de 100 itens. A adaptação não reduz o limite de compras para 10 itens.

O prompt é montado de forma genérica a partir do contexto (sem qualquer dado fixo de domínio) e instrui o modelo a:

preencher os campos exigidos pelo response schema com valores plausíveis;
usar request_body e session_state para manter coerência entre requisições;
seguir a convenção dos schemas nos nomes de campos e valores técnicos (por exemplo, valores de status), tratando as descrições (summary) apenas como contexto, sem que elas definam o idioma dos valores.
PayloadValidator
Responsável por verificar se os payloads estão de acordo com os schemas definidos no contrato OpenAPI. São verificados os tipos: object, array, string, integer, number e boolean, além de campos obrigatórios e schemas de itens em arrays.

Quando uma resposta gerada não atende ao schema, o sistema realiza até três tentativas de geração.

Falha após esgotamento das tentativas
Quando as três tentativas de geração se esgotam sem uma resposta válida, o sistema retorna erro HTTP 503 controlado. Não existe fallback estático nem geração de resposta mínima a partir do schema. Falhas externas, como indisponibilidade e timeout, também são tratadas como erros; o limite de requisições do Gemini é tratado com HTTP 429.

SessionManager
Adaptador MongoDB que implementa a porta SessionStore. O estado é armazenado no MongoDB Atlas e recuperado por um identificador de sessão enviado na requisição. As sessões possuem expiração automática após 30 minutos por meio de um índice TTL do MongoDB.

RequestLogger
Adaptador que implementa a porta RequestLog e registra o histórico de requisições na coleção requests (endpoint, método, status, latência e timestamp). O registro é best-effort: uma falha ao gravar o log nunca interrompe a resposta ao cliente. Esses dados servem de base para os indicadores de avaliação do projeto.

Persistência de estado
O sistema utiliza o MongoDB Atlas para armazenar o estado das sessões.

Cada sessão é identificada pelo header:

X-Session-ID
Exemplo:

X-Session-ID: teste-001
Quando uma requisição utiliza um identificador de sessão existente, o estado correspondente é recuperado e incorporado ao contexto utilizado durante a simulação.

O estado é acumulado de forma genérica, indexado pelo tipo de recurso (derivado do caminho do endpoint) e pelo id retornado na resposta. Por exemplo, após criar um pedido, o estado passa a conter esse pedido; ao processar um pagamento na mesma sessão, o modelo tem acesso ao pedido criado e pode gerar uma resposta coerente (mantendo, por exemplo, o mesmo pedido_id).

Esse mecanismo é o que permite representar fluxos encadeados, como criação de pedido seguida de processamento e confirmação de pagamento.

Integração com Google Gemini
O Google Gemini é utilizado para gerar dinamicamente as respostas simuladas. A comunicação com o modelo ocorre exclusivamente por meio do adaptador Gemini, que implementa a porta ResponseGenerator.

As respostas são solicitadas em formato JSON estruturado com base no schema de resposta definido pelo contrato OpenAPI.

Configuração atual da integração:

Modelo: gemini-3.5-flash-lite;
Nível de raciocínio (thinking_level): high;
Timeout controlado pela aplicação (limite atual de 180 segundos).
O sistema também possui:

timeout próprio para chamadas ao Gemini, que conta o tempo total e garante que uma requisição nunca fique presa indefinidamente;
tratamento de limite de requisições (rate limit);
tratamento de indisponibilidade do serviço;
validação do payload gerado;
novas tentativas quando o payload gerado é inválido, com retorno HTTP 503 após o esgotamento das três tentativas, sem fallback.
Sobre a latência
Durante o desenvolvimento observou-se que o tempo de resposta do Gemini é variável e não é controlável pela aplicação. Testes de diagnóstico indicaram que, mesmo reduzindo ao máximo o "raciocínio" do modelo, o tempo total oscila de acordo com a disponibilidade do serviço. No Free Tier, as requisições têm prioridade menor e podem aguardar em fila ou ser recusadas em momentos de alta demanda.

Por esse motivo, o foco do projeto não é o tempo de resposta, e sim a correção e a coerência das respostas simuladas. O timeout da aplicação atua como rede de segurança para que o sistema não fique preso, e não como garantia de tempo. Em um cenário de uso profissional, um plano pago do Gemini elevaria a cota e daria maior prioridade de processamento, reduzindo essa variação.

Tecnologias utilizadas
Tecnologia	Utilização
Python 3.11	Linguagem principal
FastAPI	Framework da API REST
Pydantic	Modelagem e validação de dados
PyYAML	Leitura dos contratos OpenAPI em YAML
MongoDB Atlas	Persistência do estado das sessões
PyMongo	Comunicação com MongoDB
Google Gemini	Geração dinâmica de respostas
Google GenAI SDK	Integração com a API do Gemini
Swagger UI	Documentação e testes da API
Railway	Hospedagem em nuvem
Git / GitHub	Controle de versão
Estrutura do projeto
smart-api-simulator/
│
├── app/
│   ├── main.py                 # ponto de composição e configuração
│   ├── models.py               # modelos do contrato
│   ├── application/
│   │   ├── ports.py            # contratos consumidos pela aplicação
│   │   ├── results.py          # resultados tipados e contexto
│   │   ├── resource_rules.py   # convenções dos recursos
│   │   ├── order_calculation.py # cálculo determinístico do pedido
│   │   ├── simulation_engine.py
│   │   ├── response_generation.py
│   │   ├── session_resources.py
│   │   ├── context_builder.py
│   │   └── validator.py
│   └── adapters/
│       ├── http_api.py         # entrada FastAPI
│       ├── http_results.py     # respostas públicas e diagnóstico opcional
│       ├── swagger_docs.py     # instruções e schemas da documentação
│       ├── swagger_view.py     # apresentação visual do Swagger
│       ├── openapi_parser.py
│       ├── gemini.py
│       ├── mongodb_sessions.py
│       └── mongodb_request_logger.py
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
├── test_parser.py
├── test_simulation_engine.py
├── test_validator.py
│
├── .env
├── .gitignore
├── Procfile
├── requirements.txt
└── README.md
O arquivo .env não deve ser versionado, pois contém informações de configuração e credenciais.

Requisitos
Para executar o projeto localmente, é necessário ter:

Python 3.11 ou superior;
Git;
uma conta no MongoDB Atlas;
um cluster MongoDB;
um usuário de banco de dados configurado;
acesso de rede autorizado no MongoDB Atlas;
uma chave de API do Google Gemini.
Instalação
Clone o repositório:

git clone https://github.com/KaiqueSP04/smart-api-simulator.git
Entre no diretório:

cd smart-api-simulator
Crie um ambiente virtual:

python -m venv .venv
Ative o ambiente virtual no Windows:

.venv\Scripts\Activate.ps1
Instale as dependências:

pip install -r requirements.txt
Configuração
Crie um arquivo .env na raiz do projeto:

MONGODB_URI=mongodb+srv://USUARIO:SENHA@SEU_CLUSTER.mongodb.net/?appName=Cluster0
GEMINI_API_KEY=sua_chave
Substitua os valores pelos dados das suas respectivas configurações. O arquivo .env deve permanecer fora do controle de versão.

Observação sobre o MongoDB Atlas: o acesso depende de o IP atual estar autorizado na IP Access List do cluster. Caso o IP mude, pode ser necessário adicionar o novo IP no painel do Atlas. Para acesso a partir de ambientes de nuvem com IP variável (como o Railway), pode-se liberar o acesso de qualquer origem.

Executando a aplicação
Local
Com o ambiente virtual ativado:

uvicorn app.main:app --reload
A aplicação ficará disponível em http://127.0.0.1:8000 e a documentação interativa do Swagger em http://127.0.0.1:8000/docs.

### Usando o Swagger

A página `/docs` apresenta um cabeçalho visual, instruções de preenchimento e grupos de **Pedidos**, **Pagamentos** e **Sistema**, com filtro de operações e exibição do tempo da requisição. Os schemas de resposta documentam o envelope real: o recurso fica em `dados`, inclusive nas respostas de criação com código 201. Os erros da simulação incluem exemplos de `codigo_status` e `mensagem`; erros de parâmetros ou corpo detectados pelo FastAPI usam 422 e `detail`.

1. Abra `POST /pedidos`, clique em **Try it out** e use o exemplo preenchido. Envie a requisição com `X-Session-ID: checkout-demo-001`.
2. Confira `dados.total` e anote o `id` retornado em `dados.id`.
3. Use esse id em `GET /pedidos/{id}` ou em `POST /pagamentos`. Reutilize exatamente o mesmo `X-Session-ID` para compartilhar o estado da sessão.
4. Para processar o pagamento, preencha apenas `pedido_id` com o id do pedido criado e `metodo` com `cartao_credito`, `cartao_debito`, `pix` ou `boleto`. Repita o `X-Session-ID` da criação: o valor vem automaticamente do pedido armazenado. Em seguida, use o `id` retornado pelo pagamento nas operações de consulta, confirmação ou cancelamento.

Deixe `X-Debug` em `false` para uma resposta simples. Com `true`, a resposta de sucesso inclui `diagnostico.parametros`, `diagnostico.corpo_requisicao` e `diagnostico.contexto`. O contexto técnico mantém os nomes internos dos schemas e das portas. Esse modo mostra os detalhes da chamada atual; não é uma consulta posterior de logs.

Os exemplos exibidos nos campos do Swagger são definidos no contrato OpenAPI em `contracts/test-api.yaml`. Os resumos, descrições, exemplos do corpo, parâmetros de caminho e orientações do cabeçalho de sessão vêm desse contrato e do adaptador HTTP.

Para criar um pedido, use `nome_cliente` e `itens`. Cada item contém `nome_produto`, `quantidade` e `preco_unitario`. Não envie `total`: o sistema calcula a soma de quantidade × preço unitário. Quantidades devem ser inteiras e positivas, preços positivos com até duas casas decimais e a lista precisa conter pelo menos um item. Para processar um pagamento, informe apenas `pedido_id` e `metodo`, com o mesmo `X-Session-ID` do pedido. O campo `valor` aparece na resposta e é obtido do total armazenado, independentemente do que a IA gerar.

`CommerceRules`, em `app/application/payment_rules.py`, é injetado como política de requisição e normalizador de respostas. Antes da geração, verifica sessão, existência do pedido, situação `criado` e total válido. Sem sessão retorna 400; pedido ausente na sessão retorna 404; pedido cancelado retorna 400. O pagamento é integral e não inclui parcelamento. Essa política também delega o cálculo de pedidos a `OrderCalculation`.

Nuvem (Railway)
A aplicação também é publicada em nuvem na plataforma Railway, por meio de deploy automático a partir do repositório GitHub. O Procfile define o comando de inicialização, e as credenciais (GEMINI_API_KEY e MONGODB_URI) são configuradas como variáveis de ambiente na plataforma. Dessa forma, os endpoints simulados ficam acessíveis publicamente pela internet, sem necessidade de servidor local.

Testando a API
O contrato de teste atualmente utilizado está em contracts/test-api.yaml. A partir dele, o sistema registra automaticamente os endpoints definidos no contrato. O contrato de exemplo descreve um domínio de pedidos e pagamentos de e-commerce, com os endpoints:

POST /pedidos — cria um pedido;
GET /pedidos/{id} — consulta um pedido;
POST /pagamentos — processa um pagamento;
POST /pagamentos/{id}/confirmar — confirma um pagamento;
GET /pagamentos/{id} — consulta um pagamento.
Exemplo: criar um pedido
POST /pedidos
Com o corpo:

```json
{
  "nome_cliente": "João Silva",
  "itens": [
    {"nome_produto": "Mouse sem fio", "quantidade": 2, "preco_unitario": 124.95},
    {"nome_produto": "Teclado", "quantidade": 1, "preco_unitario": 150.00}
  ]
}
```

O total retornado será `399.90` (pode aparecer como `399.9`, que representa o mesmo número). O pedido retorna também `id`, `nome_cliente`, `itens` e `situacao: criado`.
Exemplo: processar um pagamento
POST /pagamentos
Com o corpo:

```json
{
  "pedido_id": 101,
  "metodo": "cartao_credito"
}
```
Testando sessões e fluxos encadeados
Uma requisição pode utilizar o identificador de sessão:

X-Session-ID: teste-001
Quando houver estado armazenado para a sessão, ele será recuperado pelo SessionManager e incorporado ao contexto utilizado pelo ContextBuilder.

Isso permite representar um fluxo encadeado dentro de uma mesma sessão, por exemplo:

POST /pedidos — cria um pedido e obtém o id retornado;
POST /pagamentos — processa o pagamento referenciando o pedido criado (o estado da sessão já contém o pedido);
POST /pagamentos/{id}/confirmar — confirma o pagamento.
O uso do mesmo X-Session-ID nas três chamadas faz com que o estado seja compartilhado e a coerência seja mantida ao longo do fluxo (por exemplo, o pedido_id do pagamento corresponde ao pedido criado anteriormente).

Testes automatizados e de diagnóstico
O projeto possui testes auxiliares para validar componentes específicos do sistema:

test_gemini.py — verifica a conexão com o Gemini;
test_llm_adapter.py — verifica a comunicação do adaptador Gemini com o modelo;
test_retry.py — verifica o comportamento de novas tentativas para respostas inválidas;
test_mongodb.py — verifica a conexão com o MongoDB;
test_session_manager.py — verifica o gerenciamento das sessões;
test_session_api.py — verifica o uso de sessões através da API;
test_parser.py — verifica a leitura e extração do contrato OpenAPI;
test_simulation_engine.py — verifica a orquestração da simulação;
test_validator.py — verifica a validação de payloads.
Estado atual do desenvolvimento
Implementado e validado
 Leitura de contratos OpenAPI em YAML
 Extração de endpoints, parâmetros, request bodies e response schemas
 Registro automático dos endpoints no FastAPI
 Documentação interativa com Swagger UI
 Validação de request bodies
 Validação de payloads de resposta
 Integração com MongoDB Atlas
 Gerenciamento de sessões e expiração automática (TTL de 30 minutos)
 Recuperação de estado pelo X-Session-ID
 Construção de contexto relevante por endpoint
 Integração do adaptador Gemini com o Google Gemini
 Geração dinâmica de respostas em JSON estruturado
 Validação das respostas geradas pelo Gemini
 Retry para payloads inválidos (até três tentativas)
 Retorno de erro HTTP 503 quando as três tentativas de geração são esgotadas (sem fallback)
 Timeout próprio e confiável para chamadas ao Gemini
 Tratamento de erros do serviço do Gemini (rate limit, indisponibilidade, timeout)
 Persistência genérica de estado, indexada por recurso e id
 Registro de histórico de requisições (coleção requests)
 Consistência dos valores gerados conforme os schemas
 Fluxo completo de pedidos e pagamentos validado em uma mesma sessão
 Deploy em nuvem na plataforma Railway
Possíveis melhorias futuras
 Upload de contratos em tempo de execução via interface
 Interface de uso mais acessível que o Swagger para o usuário final
 Configuração de regras de comportamento por endpoint
 Geração de identificadores única/incremental pelo próprio sistema
 Testar o simulador com uma maior variedade de contratos e domínios
 Considerar o envio apenas do estado relevante para cada requisição
Domínio experimental
O domínio utilizado para validação do simulador é o de e-commerce, com foco em: pedidos, pagamentos, processamento de pagamentos, fluxos encadeados entre endpoints e manutenção de estado entre requisições.

Os testes de fluxo confirmaram que o simulador utiliza o contexto da sessão para produzir respostas coerentes ao longo desses fluxos.

Para executar a suíte local sem chamadas ao Gemini ou MongoDB:

```bash
python -m pytest tests test_simulation_engine.py -q
```

Essa suíte verifica os fluxos com sessões, isolamento, retries, falhas do gerador, tradução dos resultados para HTTP e documentação OpenAPI. Os scripts de diagnóstico externos da raiz não fazem parte desse comando.

Observações
O contrato de teste atualmente utilizado possui escopo controlado e serve para validar o funcionamento do simulador. A separação entre aplicação e adaptadores permite substituir integrações externas e testar o motor com implementações falsas, sem exigir um servidor Gemini ou MongoDB nos testes de unidade.


**Principais atualizações:** arquitetura hexagonal leve, documentação interativa orientada ao uso, integração Gemini, registro de requisições e tratamento de respostas inválidas com até três tentativas e erro HTTP 503, sem fallback.
