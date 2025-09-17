# 007-Hidraulico
Projeto Hidráulico + Válvula Solenóide 
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

