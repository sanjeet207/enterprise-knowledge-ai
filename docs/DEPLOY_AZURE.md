# Deploying to Azure (free-trial runbook)

**Status: written, not yet deployed.** Nothing below has been run against a real subscription. Treat it as a checklist:
anything that fails gets fixed here and recorded in the CHANGELOG. The application image has been built and run locally
(non-root user, health check, production start guard), and the hosted-model setting is tested locally.

## Rules for a zero-spend run

- Use an **Azure free account (free trial)**: $200 credit for 30 days, with a **spending limit**. Never click *Upgrade* or
  *Remove spending limit*. When the credit or the 30 days run out, resources stop; nothing is charged.
- The 30-day clock starts at sign-up. Have everything below ready first, then do the whole run in one or two days.
- After every stage open **Cost Management** in the portal and look at the running cost. Stop if it is not what you expect.
- At the end, delete everything: `az group delete -n eka-rg --yes`.
- Free amounts and CLI flags change. Check the current Azure free-services page before the run; this file does not claim
  any price or free limit as verified.

## Why a hosted model

Container Apps cannot run a local Ollama model, so the deployment uses a hosted one (`LLM_PROVIDER=groq|anthropic|openai`).
**Questions and the passages sent to the model leave Azure and go to that provider.** Only fictional documents are loaded
in this run. The README numbers were measured on the local model; the hosted model has its own, smaller evaluation
(27-question set, see the README limitations). Groq's free tier allows 30 requests and 200,000 tokens per day per model,
so keep any public test to a handful of questions; when the limit is hit the app waits and retries, then returns an error.

## What gets created

| Piece | Azure service | Notes |
|---|---|---|
| Image | Azure Container Registry (Basic) | models are baked into the image |
| API | Container Apps, one replica | the per-person rate limiter is in memory, so never more than one (sign-in lockout is in the database) |
| Database | PostgreSQL 16 Flexible Server, Burstable B1ms | `vector` must be allow-listed before the app starts |
| Secrets | Container Apps secrets | `JWT_SECRET`, `DATABASE_URL`, model API key |
| Sign-in | Microsoft Entra app registration | see [SSO.md](SSO.md); tested after the app is up |

## Before starting the trial (on your computer)

1. `GROQ_API_KEY` is in your local `.env` (typed by you; never pasted into chat or a command line).
2. List the model names your key can use, and put two of them in the `LLM_MODEL` and `ANSWERER_QUICK_MODEL` lines below:
   `set -a; source .env; set +a; curl -s https://api.groq.com/openai/v1/models -H "Authorization: Bearer $GROQ_API_KEY" | python3 -c "import sys,json; print([m['id'] for m in json.load(sys.stdin)['data']])"`
3. Docker Desktop is running. `az --version` works (`brew install azure-cli`).
4. The tests pass and `main` is pushed.

## Steps

Names in angle brackets are yours to choose (lowercase letters and digits for the registry and server names).
Secrets are read into shell variables without echo, so they stay out of history and out of this chat.

```bash
# 0. Sign in, register the services a new subscription has not used yet, pick a region
az login
for p in Microsoft.App Microsoft.OperationalInsights Microsoft.ContainerRegistry Microsoft.DBforPostgreSQL; do az provider register -n $p; done
az extension add --name containerapp --upgrade
az group create -n eka-rg -l centralindia
# If a later step says the region has no capacity or the SKU is restricted, delete the group and retry in another region
# (for example southindia, uaenorth, or any region the error message offers). Use the same region everywhere.

# 1. Container registry
az acr create -g eka-rg -n <acrname> --sku Basic
```

**Image, path A (build in Azure).** Try this first:

```bash
az acr build -r <acrname> -t eka-api:1 .
```

**Image, path B (build on your Mac).** Free trials may block ACR build tasks. Your Mac is ARM, Azure runs amd64, so build for amd64
(slower, because it runs under emulation; allow 20 to 40 minutes):

```bash
az acr login -n <acrname>
docker buildx build --platform linux/amd64 -t <acrname>.azurecr.io/eka-api:1 --push .
```

```bash
# 2. PostgreSQL 16 with pgvector
read -s -p "New database admin password: " PGPASS; echo
az postgres flexible-server create -g eka-rg -n <pgname> -l <region> --version 16 \
  --tier Burstable --sku-name Standard_B1ms --storage-size 32 \
  --admin-user ekaadmin --admin-password "$PGPASS" --public-access 0.0.0.0
az postgres flexible-server parameter set -g eka-rg --server-name <pgname> --name azure.extensions --value vector
az postgres flexible-server db create -g eka-rg --server-name <pgname> -d knowledge
# let your computer reach it for the one-time setup (your current public IP):
MYIP=$(curl -s https://api.ipify.org)
az postgres flexible-server firewall-rule create -g eka-rg -n <pgname> --rule-name me --start-ip-address $MYIP --end-ip-address $MYIP

# 3. Create the tables once, from your computer (init_db covers every migration)
export DATABASE_URL="postgresql://ekaadmin:${PGPASS}@<pgname>.postgres.database.azure.com:5432/knowledge?sslmode=require"
python -m scripts.init_db
```

```bash
# 4. Container Apps environment and the app
az containerapp env create -g eka-rg -n eka-env -l <region>
read -s -p "Groq API key: " GKEY; echo
JWT=$(openssl rand -hex 32)
az containerapp create -g eka-rg -n eka-api --environment eka-env \
  --image <acrname>.azurecr.io/eka-api:1 --registry-server <acrname>.azurecr.io --registry-identity system \
  --target-port 8000 --ingress external --min-replicas 1 --max-replicas 1 --cpu 1 --memory 2Gi \
  --secrets jwt="$JWT" db="$DATABASE_URL" llmkey="$GKEY" \
  --env-vars JWT_SECRET=secretref:jwt DATABASE_URL=secretref:db \
             LLM_PROVIDER=groq GROQ_API_KEY=secretref:llmkey \
             LLM_MODEL=openai/gpt-oss-120b ANSWERER_QUICK_MODEL=openai/gpt-oss-20b \
             APP_ENV=production
# If the image pull is refused ("unauthorized"), grant the app's identity pull access:
#   az role assignment create --assignee <principalId from: az containerapp show ... --query identity.principalId -o tsv> \
#       --role AcrPull --scope $(az acr show -n <acrname> --query id -o tsv)
# If memory runs out while loading the models, raise to --cpu 2 --memory 4Gi.

# 5. Check it
FQDN=$(az containerapp show -g eka-rg -n eka-api --query properties.configuration.ingress.fqdn -o tsv)
curl -s https://$FQDN/health
```

### About the demo accounts

This run loads **fictional** companies only. Their accounts use `acme.test` and `northwind.test`, so the production start guard
refuses to start unless `ALLOW_DEMO_DATA=1` is set. For this fictional public demo that is a deliberate choice, made in two stages:

1. Start the app **without** `ALLOW_DEMO_DATA` while the database is empty. It starts, because there are no demo accounts yet.
2. From your computer (still pointing `DATABASE_URL` at Azure) run `python -m scripts.seed_demo`, then add the setting so the
   app can restart: `az containerapp update -g eka-rg -n eka-api --set-env-vars ALLOW_DEMO_DATA=1`.

Record in the README that the deployed demo runs with `ALLOW_DEMO_DATA=1` on purpose and holds only invented data.
Never set it on a deployment with real documents. Embeddings for the seeded documents are computed on your computer.

## After it is up (each result recorded with the date and the model named)

```bash
python -m scripts.smoke_test --base-url https://$FQDN
python -m scripts.security_probe --base-url https://$FQDN
python -m scripts.evaluate --base-url https://$FQDN --eval-set tests/eval_set.json --tag azure_groq_86
python -m scripts.evaluate --base-url https://$FQDN --eval-set evaluation/independent_set.json --tag azure_groq_27
```

Then the live Entra sign-in test (see SSO.md): sign-in with a mapped group, a person with no mapped group refused, a disabled
account refused. Set the app's `OIDC_*` settings and register `https://$FQDN/auth/sso/callback` as the redirect URI.
The hosted model's numbers go in a separate table from the local-model numbers.

## Cleanup

```bash
az group delete -n eka-rg --yes --no-wait
```

Also delete the Entra app registration and the test users, and revoke the Groq key if it was only for this run.

## Before real use (not part of this run)

- Use real users, set `PASSWORD_LOGIN_ENABLED=false` once SSO works, and never set `ALLOW_DEMO_DATA`.
- Move secrets to Key Vault references; schedule `python -m scripts.purge_retention` daily; keep `/metrics` off unless
  `METRICS_TOKEN` is set.
