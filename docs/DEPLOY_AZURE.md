# Deploying to Azure

**Status: written, not yet deployed.** The commands below have not been run against a real Azure subscription. The
application image and the hosted-model setting are tested locally; the Azure steps are the standard route and should be
treated as a checklist to verify, not as a proven recipe. Anything that fails will be fixed here and noted in the CHANGELOG.

## Why a hosted model

Azure Container Apps and App Service cannot run a local Ollama model, so the deployment uses a hosted one. Set
`LLM_PROVIDER` to `anthropic`, `groq` or `openai` (see the README). **Questions and the passages sent to the model leave
Azure and go to that provider**, so check its data terms before loading real documents. The evaluation numbers in the
README were measured on the local model only; run `python -m scripts.evaluate` against the deployed URL before quoting
any number for the hosted one.

## What gets created

| Piece | Azure service | Notes |
|---|---|---|
| API image | Azure Container Registry | built from the repo `Dockerfile` (models are baked in) |
| API | Azure Container Apps | one replica only (the rate limiter and lockout are per process) |
| Database | Azure Database for PostgreSQL, Flexible Server, version 16 | needs the `vector` extension allow-listed |
| Secrets | Container Apps secrets | `JWT_SECRET`, `DATABASE_URL`, the model API key |
| Sign-in (optional) | Microsoft Entra ID app registration | see [SSO.md](SSO.md) |

## Steps

Replace the names in angle brackets. Use a new `JWT_SECRET` (`openssl rand -hex 32`), never the one from local `.env`.

```bash
# 0. Sign in and pick a region close to you
az login
az group create -n eka-rg -l centralindia

# 1. Container registry and image build (builds in Azure, no local Docker needed)
az acr create -g eka-rg -n <uniqueacrname> --sku Basic
az acr build -r <uniqueacrname> -t eka-api:1 .

# 2. PostgreSQL 16 with pgvector
az postgres flexible-server create -g eka-rg -n <uniquepgname> -l centralindia \
  --version 16 --tier Burstable --sku-name Standard_B1ms --storage-size 32 \
  --admin-user ekaadmin --admin-password '<strong password>' --public-access 0.0.0.0
az postgres flexible-server parameter set -g eka-rg --server-name <uniquepgname> \
  --name azure.extensions --value vector
az postgres flexible-server db create -g eka-rg --server-name <uniquepgname> -d knowledge

# 3. Create the tables once, from your own computer
#    (add your current IP to the server firewall first: az postgres flexible-server firewall-rule create ...)
export DATABASE_URL='postgresql://ekaadmin:<password>@<uniquepgname>.postgres.database.azure.com:5432/knowledge?sslmode=require'
python -m scripts.init_db
python -m scripts.migrate_auth && python -m scripts.migrate_audit && python -m scripts.migrate_chat   # only if init_db does not already cover them

# 4. Container Apps environment and the app
az containerapp env create -g eka-rg -n eka-env -l centralindia
az containerapp create -g eka-rg -n eka-api --environment eka-env \
  --image <uniqueacrname>.azurecr.io/eka-api:1 --registry-server <uniqueacrname>.azurecr.io \
  --target-port 8000 --ingress external --min-replicas 1 --max-replicas 1 --cpu 2 --memory 4Gi \
  --secrets jwt=<new-secret> db='<DATABASE_URL as above>' llmkey=<provider api key> \
  --env-vars JWT_SECRET=secretref:jwt DATABASE_URL=secretref:db \
             LLM_PROVIDER=groq GROQ_API_KEY=secretref:llmkey \
             LLM_MODEL=llama-3.3-70b-versatile ANSWERER_QUICK_MODEL=llama-3.1-8b-instant

# 5. Check it
az containerapp show -g eka-rg -n eka-api --query properties.configuration.ingress.fqdn -o tsv
curl https://<that address>/health
```

Typing real secrets on a command line leaves them in shell history; prefer the Azure portal's "Secrets" page or a
Key Vault reference for anything beyond a demo.

## Before anyone else uses it

- **Demo users.** `scripts.seed_demo` creates well-known demo accounts with known passwords. Fine for a clearly fictional
  public demo, not for real data. For real use create real users and set `PASSWORD_LOGIN_ENABLED=false` once SSO works.
- **Cost.** Burstable PostgreSQL and one Container Apps replica cost a few dollars a month at idle, plus the model
  provider's usage. Stop the database when idle, and delete the resource group (`az group delete -n eka-rg`) to end all charges.
- **Retention.** Schedule `python -m scripts.purge_retention` daily (a Container Apps job).
- **Tracing and metrics.** Leave `/metrics` off unless `METRICS_TOKEN` is set.
- **After deploying:** run `python -m scripts.smoke_test` and `python -m scripts.security_probe` against the public URL, then
  `python -m scripts.evaluate`, and record the results with the provider named.
