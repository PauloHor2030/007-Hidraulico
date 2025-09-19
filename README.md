# 007-Hidraulico
Projeto Hidráulico + Válvula Solenóide 
# Custos de Firebase
é f_ nos nomes dos campos, por favor.
penso que a opcao melhor é caminho B.

Mas eu queria que vc revisse os calculos de custos, pois agora que traçamos um pouco mais o cenário, acho que fica  mais plausível ter um custo mais real, pois estamos falando de banco operacional que serão guardados tambem. Lembre-se, estamos falando de 1 mes, mas quando vamos guardar os operacionais, acredito que os dados do ano devam estar a disposicao para consultas de relatorios.<br>
Penso que podemos fazer bancos mensais, por exemplo, se precisar das leituras de um determinado mes, baixamos para relatorios.<br>
como os dados estarao em sql format, penso que podemos condensar/agregar um pouco mais e tornar eles disponiveis em bigQuery (este tendo dados para relatorios anuais), estaria certo? e anualmente tambem fazer a baixa dos registros do ano anterior<br>
O ChatGPT disse:<br>
Pensou por 2m 33s<br>

Perfeito — vamos recalibrar os custos agora assumindo o Caminho B (streaming em tempo real), com 2000 medidores enviando a cada 5 minutos e retenção operacional + histórico anual (Firestore como operacional e BigQuery para relatórios). Vou separar em: premissas, componentes de custo (mês), impacto de retenção (30 dias vs 12 meses), custo de consultas/BI, e resumo com duas opções (Streaming x Lote Diário).<br>

Premissas (realistas e auditáveis)<br>

Volume: 2000 medidores × 12 leituras/h × 24 h × 30 dias ≈ 17,28 milhões de leituras/mês.<br>

Tamanho médio por leitura: ~0,5 KB (campos f_... essenciais: f_medidor_id, f_cliente_id, f_ts_utc, f_m3/f_pulso, flags).<br>

Preços de referência (USD):<br>

Firestore (Standard edition): writes US$0,09/100k, reads US$0,03/100k, deletes US$0,01/100k; storage cobrado por GiB-mês; tráfego intra-região gratuito. <br>
Google Cloud<br>

BigQuery (on-demand): storage ativo ~US$0,02/GB-mês (long-term ~US$0,01/GB-mês após 90 dias), consulta US$5/TB; ingestão por streaming: legacy $0,01/200 MB ou Storage Write API $0,025/GB com 2 TB/mês grátis. <br>
Google Cloud<br>
+2<br>
Weld<br>
+2<br>

Dataflow (streaming): cobrado por recursos (compute/Streaming Engine); varia conforme throughput (estimarei uma faixa). <br>
Google Cloud<br>

Functions (2ª geração): US$0,40/milhão invocações + vCPU/GiB-seg. <br>
Firebase<br>
+1<br>

Rede Firestore: tráfego dentro da mesma região é gratuito. <br>
Firebase<br>

Componentes de custo (mês) — “estado estável”<br>
1) Firestore (operacional: gravações + pequenas leituras + storage)<br>

Writes: 17,28M / 100k × $0,09 ≈ US$ 15,55/mês. <br>
Google Cloud<br>

Reads operacionais (dashboards rápidos, f_ultimo_valor, contadores etc.). Se planejarmos ~1,8M reads/mês (≈10% das writes): 1,8M/100k × $0,03 ≈ US$ 0,54. (Pode ser menos, se tudo vier de agregados.) <br>
Google Cloud<br>

Storage (retenção de 30 dias no operacional): ~17,28M × 0,5 KB ≈ 8,64 GB + índices/overhead ≈ ~10–12 GB. Firestore cobra por GiB-mês (≈US$ 0,15/GB-mês típico → ~US$ 1,5–1,8/mês). <br>
Google Cloud<br>
+1<br>

Deletes (se rotacionar com TTL): custo irrisório (US$0,01/100k). <br>
Google Cloud<br>

Subtotal Firestore (30 dias): ~ US$ 17–18/mês.<br>

2) Pipeline de streaming Firestore → BigQuery<br>

Extensão/Conector: cobra indiretamente (Dataflow/engine + ingestão BigQuery). <br>
Firebase Extensions Hub<br>

Ingestão BigQuery (Streaming)<br>

Se usar Storage Write API: até 2 TB/mês grátis → nosso volume (8,64 GB/mês) fica dentro do free tier → ~US$ 0. <br>
Airbyte<br>

Se usar legacy streaming ($0,01/200 MB): 8,64 GB ÷ 0,2 GB × $0,01 ≈ US$ 0,43/mês. <br>
CloudBolt<br>

Dataflow (streaming): trabalho leve, contínuo. Para esse throughput, é comum ver faixa ~US$ 20–80/mês (depende da configuração mínima e horas/uso do Streaming Engine). Recomendo validar no pricing calculator depois de definirmos o template e a região. <br>
Google Cloud<br>
+1<br>

Subtotal pipeline (com Storage Write API): ~ US$ 20–80/mês (dominante = Dataflow).<br>

3) Cloud Functions / Cloud Run (ingestão HTTP do ESP32)<br>

Invocações: 17,28M – 2M grátis = 15,28M cobradas → 15,28 × $0,40 ≈ US$ 6,11. <br>
Firebase<br>

Compute (ex.: 0,2 s, 256 MiB por chamada): custo baixo; ordem de US$ ~2–3/mês. <br>
Modal<br>

Subtotal ingest (Functions): ~ US$ 8–9/mês.<br>

4) BigQuery (armazenamento do histórico anual)<br>

Geração mensal: ~8,64 GB/mês. Em “estado estável” (12 meses):<br>

Ativo (últimos 90 dias): ≈ 3 × 8,64 = 25,9 GB × $0,02 ≈ US$ 0,52/mês.<br>

Long-term (9 meses anteriores): ≈ 9 × 8,64 = 77,8 GB × $0,01 ≈ US$ 0,78/mês.<br>
→ Total storage BigQuery ≈ US$ 1,30/mês (varia pouco com compressão/partição). <br>
Google Cloud<br>
+1<br>

5) Rede<br>

Intra-região (GCP): grátis (Firestore/BigQuery/Functions na mesma região). <br>
Firebase<br>

Total mensal (Caminho B – Streaming, 30 dias no operacional)<br>

Firestore (writes+reads+storage 30d): ~US$ 17–18<br>

Pipeline streaming (Dataflow + ingestão BigQuery): ~US$ 20–80<br>

Functions (ingestão ESP32): ~US$ 8–9<br>

BigQuery storage (12 meses): ~US$ 1,3<br>
≈ Faixa total: ~US$ 46 a 108 / mês (a variância concentra no Dataflow streaming).<br>

Obs.: Se optarmos por batch diário (sem Dataflow contínuo), o custo do pipeline cai para quase zero (Cloud Scheduler + Cloud Run job/dia), e o total mensal fica ~US$ 27–30 (muito próximo da nossa estimativa inicial), mantendo BigQuery atualizado 1x/dia. <br>
Google Cloud<br>

Retenção: 30 dias vs 12 meses no Firestore<br>

Seu pedido (correto): manter operacional no Firestore (rápido para o app), e histórico anual no BigQuery (SQL/relatórios).<br>

Se ampliar Firestore para 12 meses, o storage cresce (~100–130 GB considerando índices), custando ~US$ 15–20/mês só de storage Firestore, além dos mesmos writes/reads — não compensa frente ao BigQuery, que custa ~US$ 1–2/mês pelo ano inteiro. <br>
Airbyte<br>
+1<br>

Portanto, recomendo: Firestore = 30 dias (ou 60 no máximo) + TTL; BigQuery = 12 meses (ou mais), particionado por dia/mês.<br>

Consultas/BI no BigQuery (anual)<br>

Preço de consulta: US$ 5/TB processado (primeiro 1 TB/mês grátis). Se seus relatórios mensais varrerem, por exemplo, 100 GB no total, o custo é ~US$ 0,50/mês (ou zero se ficar dentro do free tier). <br>
Weld<br>

Boas práticas p/ baratear: tabelas particionadas por dia + cluster por f_medidor_id; evitar SELECT *, projetar só colunas usadas. <br>
Google Cloud<br>

Seu desenho de “bancos mensais”<br>

Em Firestore: subcoleções por mês nos medidores (ex.: t_medidor/{id}/t_leituras/2025_09/...).<br>

Em BigQuery: tabela única leituras particionada por dia (ou mês) com coluna f_dia_ref e clusterizada por f_medidor_id.<br>

Para “baixar” um mês específico (CSV/Parquet) para relatórios locais, é direto do BigQuery (export para GCS é gratuito; egress cobra se baixar para fora da nuvem). <br>
Google Cloud<br>

Resposta direta às suas perguntas de custo e estratégia<br>

Híbrido faz sentido? Sim: Firestore (30d) para operação + BigQuery (12m+) para BI anual/relatórios.<br>

Streaming copia toda alteração? Sim, se ligarmos no caminho t_medidor/*/t_leituras/* (create/update/delete). <br>
Firebase Extensions Hub<br>

5 min vs diário muda custo? Sim no pipeline: streaming mantém Dataflow 24/7 (US$ 20–80/mês); batch diário fica quase zero. Firestore/BigQuery não mudam (mesmo número de writes e GB). <br>
Google Cloud<br>

Relatórios anuais: BigQuery é o lugar certo (barato no storage e barato nas consultas se particionado). <br>
Google Cloud<br>

Quer o plano de ação (Caminho B) já com os nomes f_...?<br>

Eu já te mando:<br>

Esquema BigQuery (particionado/clusterizado) com colunas f_medidor_id, f_cliente_id, f_condominio_id, f_ts_utc, f_ano_mes_ref, f_dia_ref, f_m3, f_pulsos, f_flag_vazamento…<br>

Habilitar extensão “Stream Firestore to BigQuery” mirando t_medidor/*/t_leituras/*. <br>
Firebase Extensions Hub<br>

TTL Firestore (campo f_archived_at) para retenção de 30–60 dias.<br>

Consulta-modelo de BI (mensal/anual) já enxuta.<br>


# Firebase<br>
Programa de conversão: <br>
a) Streaming em tempo real <br>
   Firestore Change Stream-> Dataflow -> BigQuery<br>
   gravação em tempo real no BigQuery (particionado por data)<br>
   beneficios: baixa latência para BI, Zero manutenção de servidor, resiliente<br>
   Gravaçao no bigQuery será feita pelo Cloud Run Job / Cloud Function, qualquer um dos 2 será orquestrado pelo Cloud Scheduler.<br>

Recomendo uma arquitetura 100% Google Cloud, análoga ao ThermoSafe:<br>
### Ingestão
* Cloud Functions (HTTP) para receber os POSTs dos ESP32 (validação, idempotência, detecção de vazamento).<br>
* (Opcional) MQTT → Cloud Run consumer se quiser broker e buffering.<br>
### Banco operacional<br>
* Firestore (coleções t_condominio, t_cliente, t_medidor, subcoleção t_leituras por mês).<br>
* Regras fechando acesso direto; Admin SDK só no backend.<br>
### BI / Relatórios<br>
* BigQuery (tabelas particionadas por dia, cluster por medidor_id).<br>
* Pipeline Streaming (se quiser near real-time) ou Batch diário (mais econômico).<br>
### APIs e Painéis<br>
* Cloud Run (container) para sua API FastAPI (cadastros, autenticação, dashboards “operacionais”).<br>
* Streamlit ou Next.js/React para UI (pode subir em Cloud Run ou Firebase Hosting).<br>
* Grafana/Looker Studio para BI diretamente no BigQuery (barato e rápido).<br>
### Jobs/Rotinas<br>
* Cloud Scheduler para tarefas (ETL diário, limpeza/TTL, recomputar agregados).<br>
* Cloud Tasks/PubSub para filas de alertas.<br>
### Alertas<br>
* Na Function de ingestão, já marcar flag_vazamento e disparar WhatsApp/e-mail.<br>
* Opcional: Cloud Monitoring para métricas (leituras/min, falhas, latências).<br>

