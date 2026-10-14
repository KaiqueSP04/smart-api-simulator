"""Visual presentation of the interactive API documentation."""

from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse


STYLES = """
<style>
:root { color-scheme: light; }
body { margin:0; background:#f4f7fb; }
#swagger-ui { padding-bottom:80px; }
.docs-banner { background:#10273b; color:#fff; padding:40px max(24px,calc((100vw - 1200px)/2));
 font-family:system-ui,sans-serif; border-bottom:5px solid #41d6ac; }
.docs-banner .eyebrow { color:#80e4c7; text-transform:uppercase; letter-spacing:.14em; font-size:12px; font-weight:700; }
.docs-banner h1 { font-size:clamp(26px,4vw,42px); margin:12px 0; letter-spacing:-.03em; }
.docs-banner p { max-width:700px; color:#d0deea; line-height:1.7; margin:0 0 22px; }
.docs-banner nav { display:flex; flex-wrap:wrap; gap:12px; }
.docs-banner a { color:#10273b; background:#80e4c7; border-radius:8px; padding:10px 16px;
 text-decoration:none; font-size:14px; font-weight:650; }
.docs-banner a.secondary { background:transparent; color:white; border:1px solid #647b8e; }
.swagger-ui .topbar { display:none; }
.swagger-ui .wrapper { max-width:1200px; padding:0 24px; }
.swagger-ui .info { margin:30px 0; padding:26px; background:white; border:1px solid #dce5ee; border-radius:14px; }
.swagger-ui .info .title { color:#10273b; font-size:26px; }
.swagger-ui .info p, .swagger-ui .info li { line-height:1.7; }
.swagger-ui .info table { width:100%; border-collapse:collapse; margin:18px 0; }
.swagger-ui .info th, .swagger-ui .info td { padding:12px; border-bottom:1px solid #e1e8ef; text-align:left; }
.swagger-ui .info th { background:#eef5fa; }
.swagger-ui .scheme-container { background:white; box-shadow:none; border-block:1px solid #dce5ee; }
.swagger-ui .opblock { border-radius:10px; box-shadow:none; margin-bottom:14px; }
.swagger-ui .opblock-tag { color:#10273b; border-bottom:1px solid #dce5ee; }
.swagger-ui .opblock .opblock-summary { padding:10px; }
.swagger-ui .btn { border-radius:7px; }
.swagger-ui textarea { border-radius:8px; line-height:1.5; }
@media(max-width:600px) {
 #swagger-ui { padding-bottom:48px; }
 .docs-banner { padding:28px 20px; }
 .swagger-ui .wrapper { padding:0 12px; }
 .swagger-ui .info { padding:16px; }
 .swagger-ui .opblock .opblock-summary-path { font-size:13px; }
}
</style>
"""

BANNER = """
<header class="docs-banner">
  <span class="eyebrow">Smart API Simulator</span>
  <h1>Uma compra, do pedido ao pagamento.</h1>
  <p>Preencha os produtos, confira o total e acompanhe cada etapa.
  Use a mesma sessão para conectar suas chamadas.</p>
  <nav aria-label="Atalhos da documentação">
    <a href="#swagger-ui">Explorar e testar a API</a>
    <a class="secondary" href="/redoc" target="_blank" rel="noopener noreferrer">Documentação de referência</a>
  </nav>
</header>
"""


def swagger_page(openapi_url: str) -> HTMLResponse:
    page = get_swagger_ui_html(
        openapi_url=openapi_url,
        title="Pedidos e pagamentos · Smart API Simulator",
        swagger_ui_parameters={
            "docExpansion": "none", "filter": True,
            "displayRequestDuration": True, "defaultModelsExpandDepth": -1,
            "tryItOutEnabled": True,
        },
    ).body.decode("utf-8")
    page = page.replace("<html>", '<html lang="pt-BR">')
    page = page.replace("</head>", STYLES + "</head>")
    page = page.replace("<body>", "<body>" + BANNER)
    return HTMLResponse(page)
