# Smart API Simulator

Protótipo de uma plataforma para simulação inteligente de APIs REST a partir de contratos OpenAPI.

O **Smart API Simulator** interpreta contratos OpenAPI, identifica endpoints, parâmetros e schemas, e disponibiliza uma API simulada capaz de gerar respostas dinamicamente de acordo com o contrato recebido. O sistema também mantém estado entre requisições de uma mesma sessão, permitindo representar fluxos encadeados de forma coerente.

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

## Arquitetura

O projeto segue o padrão **Microkernel**: o motor de simulação é genérico e não conhece nenhum domínio específico. Todo o domínio (endpoints, campos, schemas, idioma dos textos) vem do contrato OpenAPI. Isso permite que o mesmo motor simule qualquer API REST válida, sem alteração de código.

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
OpenAPI Parser
Responsável por interpretar o contrato OpenAPI e extrair informações dos endpoints, incluindo: método HTTP, caminho, resumo, parâmetros, request body, respostas e schemas.

SimulationEngine
É responsável por orquestrar o processo de simulação. Ele:

identifica o endpoint correspondente à requisição;
solicita a construção do contexto;
verifica o request body quando aplicável;
solicita a geração da resposta pelo modelo de linguagem;
valida o payload gerado;
realiza novas tentativas quando o payload é inválido;
aciona o fallback quando as tentativas se esgotam;
persiste o estado da sessão a partir da resposta gerada;
registra a requisição no histórico;
retorna a resposta simulada ou um erro apropriado.
ContextBuilder
Responsável por construir o contexto utilizado durante a simulação, que pode incluir: endpoint atual, parâmetros recebidos, request body, schema da requisição, schema da resposta e estado da sessão.

O sistema utiliza apenas o contexto relevante para a requisição atual, evitando o envio desnecessário de todo o contrato OpenAPI ao modelo de linguagem.

LLMAdapter
Camada responsável pela comunicação com o Google Gemini. O LLMAdapter isola a integração do modelo de linguagem do restante do sistema, de modo que o SimulationEngine não dependa diretamente da implementação específica da API do Gemini.

O adapter constrói o prompt a partir do contexto, envia a solicitação ao Gemini, solicita respostas em JSON estruturado de acordo com o schema, retorna o conteúdo gerado e possui controle de timeout próprio e confiável.

O prompt é montado de forma genérica a partir do contexto (sem qualquer dado fixo de domínio) e instrui o modelo a:

preencher os campos exigidos pelo response schema com valores plausíveis;
usar request_body e session_state para manter coerência entre requisições;
seguir a convenção dos schemas nos nomes de campos e valores técnicos (por exemplo, valores de status), tratando as descrições (summary) apenas como contexto, sem que elas definam o idioma dos valores.
PayloadValidator
Responsável por verificar se os payloads estão de acordo com os schemas definidos no contrato OpenAPI. São verificados os tipos: object, array, string, integer, number e boolean, além de campos obrigatórios e schemas de itens em arrays.

Quando uma resposta gerada não atende ao schema, o sistema realiza até três tentativas de geração.

Fallback
Quando as três tentativas de geração se esgotam sem uma resposta válida, o sistema aciona um fallback: monta uma resposta mínima a partir do próprio schema do contrato (preenchendo cada campo com um valor padrão do seu tipo) e a retorna marcada com "fallback": true. Isso evita que uma falha de geração do modelo interrompa o fluxo. O fallback cobre apenas o caso de resposta inválida; falhas externas (indisponibilidade, timeout, rate limit) retornam o erro real, sem mascaramento.

SessionManager
Responsável pelo gerenciamento do estado das sessões. O estado é armazenado no MongoDB Atlas e recuperado por um identificador de sessão enviado na requisição. As sessões possuem expiração automática após 30 minutos por meio de um índice TTL do MongoDB.

RequestLogger
Registra o histórico de requisições na coleção requests (endpoint, método, status, latência, uso de fallback e timestamp). O registro é best-effort: uma falha ao gravar o log nunca interrompe a resposta ao cliente. Esses dados servem de base para os indicadores de avaliação do projeto.

Persistência de estado
O sistema utiliza o MongoDB Atlas para armazenar o estado das sessões.

Cada sessão é identificada pelo header:

X-Session-ID
Exemplo:

X-Session-ID: teste-001
Quando uma requisição utiliza um identificador de sessão existente, o estado correspondente é recuperado e incorporado ao contexto utilizado durante a simulação.

O estado é acumulado de forma genérica, indexado pelo tipo de recurso (derivado do caminho do endpoint) e pelo id retornado na resposta. Por exemplo, após criar um pedido, o estado passa a conter esse pedido; ao processar um pagamento na mesma sessão, o modelo tem acesso ao pedido criado e pode gerar uma resposta coerente (mantendo, por exemplo, o mesmo order_id).

Esse mecanismo é o que permite representar fluxos encadeados, como criação de pedido seguida de processamento e confirmação de pagamento.

Integração com Google Gemini
O Google Gemini é utilizado para gerar dinamicamente as respostas simuladas. A comunicação com o modelo ocorre exclusivamente por meio do LLMAdapter.

As respostas são solicitadas em formato JSON estruturado com base no schema de resposta definido pelo contrato OpenAPI.

Configuração atual da integração:

Modelo: gemini-3.5-flash-lite;
Nível de raciocínio (thinking_level): low;
Timeout controlado pela aplicação (limite atual de 180 segundos).
O sistema também possui:

timeout próprio para chamadas ao Gemini, que conta o tempo total e garante que uma requisição nunca fique presa indefinidamente;
tratamento de limite de requisições (rate limit);
tratamento de indisponibilidade do serviço;
validação do payload gerado;
novas tentativas quando o payload gerado é inválido, com fallback a partir do schema.
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
│   ├── main.py
│   ├── models.py
│   ├── parser.py
│   ├── simulation_engine.py
│   ├── context_builder.py
│   ├── session_manager.py
│   ├── request_logger.py
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

Nuvem (Railway)
A aplicação também é publicada em nuvem na plataforma Railway, por meio de deploy automático a partir do repositório GitHub. O Procfile define o comando de inicialização, e as credenciais (GEMINI_API_KEY e MONGODB_URI) são configuradas como variáveis de ambiente na plataforma. Dessa forma, os endpoints simulados ficam acessíveis publicamente pela internet, sem necessidade de servidor local.

Testando a API
O contrato de teste atualmente utilizado está em contracts/test-api.yaml. A partir dele, o sistema registra automaticamente os endpoints definidos no contrato. O contrato de exemplo descreve um domínio de pedidos e pagamentos de e-commerce, com os endpoints:

POST /orders — cria um pedido;
GET /orders/{id} — consulta um pedido;
POST /payments — processa um pagamento;
POST /payments/{id}/confirm — confirma um pagamento;
GET /payments/{id} — consulta um pagamento.
Exemplo: criar um pedido
POST /orders
Com o corpo:

{
  "customer_name": "João Silva",
  "total": 3500
}
Exemplo: processar um pagamento
POST /payments
Com o corpo:

{
  "order_id": 101,
  "amount": 3500,
  "method": "credit_card"
}
Testando sessões e fluxos encadeados
Uma requisição pode utilizar o identificador de sessão:

X-Session-ID: teste-001
Quando houver estado armazenado para a sessão, ele será recuperado pelo SessionManager e incorporado ao contexto utilizado pelo ContextBuilder.

Isso permite representar um fluxo encadeado dentro de uma mesma sessão, por exemplo:

POST /orders — cria um pedido e obtém o id retornado;
POST /payments — processa o pagamento referenciando o pedido criado (o estado da sessão já contém o pedido);
POST /payments/{id}/confirm — confirma o pagamento.
O uso do mesmo X-Session-ID nas três chamadas faz com que o estado seja compartilhado e a coerência seja mantida ao longo do fluxo (por exemplo, o order_id do pagamento corresponde ao pedido criado anteriormente).

Testes automatizados e de diagnóstico
O projeto possui testes auxiliares para validar componentes específicos do sistema:

test_gemini.py — verifica a conexão com o Gemini;
test_llm_adapter.py — verifica a comunicação do LLMAdapter com o modelo;
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
 Integração do LLMAdapter com o Google Gemini
 Geração dinâmica de respostas em JSON estruturado
 Validação das respostas geradas pelo Gemini
 Retry para payloads inválidos (até três tentativas)
 Fallback a partir do schema quando as tentativas se esgotam
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
O domínio utilizado para validação do protótipo é o de e-commerce, com foco em: pedidos, pagamentos, processamento de pagamentos, fluxos encadeados entre endpoints e manutenção de estado entre requisições.

Os testes de fluxo confirmaram que o simulador utiliza o contexto da sessão para produzir respostas coerentes ao longo desses fluxos.

Observações
O projeto encontra-se em fase de finalização no contexto de um Trabalho de Conclusão de Curso.

O contrato de teste atualmente utilizado possui escopo controlado e serve para validar o funcionamento do protótipo. Por respeitar o padrão Microkernel, o mesmo motor de simulação pode ser utilizado com outros contratos OpenAPI válidos, sem necessidade de alteração de código.


**Principais atualizações:** modelo lite, fallback (nova seção), RequestLogger (nova seção), Railway como implementado, `request_logger.py` e `Procfile` na estrutura, melhorias futuras atualizadas (upload, rules e ids viraram "futuro").

Cola no `README.md`, salva, e aí commita tudo junto. Agora são **6 arquivos**:
git add app/simulation_engine.py app/request_logger.py app/main.py app/llm_adapter.py Procfile README.md


Confirma e commita. Me avisa quando o push terminar.