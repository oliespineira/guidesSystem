#!/usr/bin/env bash
# Initial Azure setup for guidesSystem, run once, step by step, in bash (not zsh: see the A2 deployment guide).
# Steps follow the guide. Passwords are never written here: set them in the shell first
# (read -s SQL_ADMIN_PASSWORD; read -s KRAAL_DB_PASSWORD; read -s ACTAS_DB_PASSWORD).
set -euo pipefail

PREFIX=oespineira-ieu2024
RG=rg-$PREFIX
LOCATION=swedencentral          # one of the 5 regions allowed by my Azure for Students policy
SQL_LOCATION=swedencentral      # the SQL free offer must be available here (it is not in spaincentral)
STORAGE=oespineiraieu2024ui     # 3-24 lowercase letters/digits, unique in Azure
GH_REPO=oliespineira/guidesSystem

# Step 2: providers and resource group
for ns in Microsoft.App Microsoft.OperationalInsights Microsoft.Sql Microsoft.Storage Microsoft.ManagedIdentity; do
  az provider register --namespace "$ns"
done
az group create --name "$RG" --location "$LOCATION"

# Step 3: the UI as a Storage static website (its web endpoint is the public URL and the CORS origin)
az storage account create --name "$STORAGE" --resource-group "$RG" --location "$LOCATION" \
  --sku Standard_LRS --kind StorageV2 --min-tls-version TLS1_2
az storage blob service-properties update --account-name "$STORAGE" --static-website --index-document index.html
UI_URL=$(az storage account show --name "$STORAGE" --resource-group "$RG" --query primaryEndpoints.web -o tsv)
UI_ORIGIN=${UI_URL%/}           # a browser's Origin header has no trailing slash

# Step 4: SQL server, "allow Azure services", two serverless databases on the free offer
az sql server create --name "$PREFIX-sql" --resource-group "$RG" --location "$SQL_LOCATION" \
  --admin-user sqladmin --admin-password "$SQL_ADMIN_PASSWORD"
az sql server firewall-rule create --resource-group "$RG" --server "$PREFIX-sql" --name AllowAzureServices \
  --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0
for svc in kraal actas; do
  az sql db create --resource-group "$RG" --server "$PREFIX-sql" --name "$PREFIX-$svc-db" \
    --edition GeneralPurpose --compute-model Serverless --family Gen5 --min-capacity 0.5 --capacity 1 \
    --backup-storage-redundancy Local --use-free-limit true --free-limit-exhaustion-behavior AutoPause
done
# Step 4 (continued): one contained user per database, with db_ddladmin, db_datareader and db_datawriter.
# Open the firewall to my IP only while running this, then close it again.
# My network sent traffic from more than one public IP (.34 and .35 in the same block), so the rule covers the /24 block.
MY_IP=$(curl -s https://api.ipify.org)
MY_BLOCK=${MY_IP%.*}
az sql server firewall-rule create --resource-group "$RG" --server "$PREFIX-sql" --name MyLaptop \
  --start-ip-address "$MY_BLOCK.0" --end-ip-address "$MY_BLOCK.255"
# The repo path contains spaces, which break docker's -v option, so mount it through a space-free link.
ln -sfn "$PWD/infra" /tmp/guides-infra
SQLCMD="docker run --rm --platform linux/amd64 -v /tmp/guides-infra:/infra:ro mcr.microsoft.com/mssql/server:2022-latest /opt/mssql-tools18/bin/sqlcmd"
# If this fails with error 40613, the paused database is waking up: wait a minute and run the same line again.
$SQLCMD -S "$PREFIX-sql.database.windows.net" -d "$PREFIX-kraal-db" -U sqladmin -P "$SQL_ADMIN_PASSWORD" -l 60 -b \
  -i /infra/create-user.sql -v APP_USER=kraal_app APP_PASSWORD="$KRAAL_DB_PASSWORD"
$SQLCMD -S "$PREFIX-sql.database.windows.net" -d "$PREFIX-actas-db" -U sqladmin -P "$SQL_ADMIN_PASSWORD" -l 60 -b \
  -i /infra/create-user.sql -v APP_USER=actas_app APP_PASSWORD="$ACTAS_DB_PASSWORD"
az sql server firewall-rule delete --resource-group "$RG" --server "$PREFIX-sql" --name MyLaptop

# Step 5: Container Apps environment, with a Log Analytics workspace for the containers' logs
# (part of the allowance; capped at 0.15 GB a day, under the free 5 GB a month), then one Container App per service.
# Placeholder image until the first deploy; scale 0..1; the connection string is a secret, passed by secretref.
az monitor log-analytics workspace create -g "$RG" -n "$PREFIX-logs" -l "$LOCATION" --sku PerGB2018 \
  --retention-time 30 --quota 0.15
WS_ID=$(az monitor log-analytics workspace show -g "$RG" -n "$PREFIX-logs" --query customerId -o tsv)
WS_KEY=$(az monitor log-analytics workspace get-shared-keys -g "$RG" -n "$PREFIX-logs" --query primarySharedKey -o tsv)
az containerapp env create --name "$PREFIX-env" --resource-group "$RG" --location "$LOCATION" \
  --logs-destination log-analytics --logs-workspace-id "$WS_ID" --logs-workspace-key "$WS_KEY"
az containerapp create --name "$PREFIX-kraal" --resource-group "$RG" --environment "$PREFIX-env" \
  --image mcr.microsoft.com/k8se/quickstart:latest --ingress external --target-port 8000 \
  --min-replicas 0 --max-replicas 1 --cpu 0.25 --memory 0.5Gi \
  --secrets "database-url=mssql://kraal_app:${KRAAL_DB_PASSWORD}@${PREFIX}-sql.database.windows.net:1433/${PREFIX}-kraal-db?encrypt=require" \
  --env-vars DATABASE_URL=secretref:database-url UI_ORIGIN="$UI_ORIGIN"
KRAAL_FQDN=$(az containerapp show --name "$PREFIX-kraal" --resource-group "$RG" --query properties.configuration.ingress.fqdn -o tsv)
az containerapp create --name "$PREFIX-actas" --resource-group "$RG" --environment "$PREFIX-env" \
  --image mcr.microsoft.com/k8se/quickstart:latest --ingress external --target-port 8000 \
  --min-replicas 0 --max-replicas 1 --cpu 0.25 --memory 0.5Gi \
  --secrets "database-url=mssql://actas_app:${ACTAS_DB_PASSWORD}@${PREFIX}-sql.database.windows.net:1433/${PREFIX}-actas-db?encrypt=require" \
  --env-vars DATABASE_URL=secretref:database-url UI_ORIGIN="$UI_ORIGIN" KRAAL_URL="https://$KRAAL_FQDN"
# Step 6: the pipeline's identity: a user-assigned managed identity with Contributor on this resource group only,
# trusted through OIDC for pushes to main (both subject formats GitHub may send). Run in bash, not zsh.
az identity create --name "$PREFIX-github" --resource-group "$RG" --location "$LOCATION"
CLIENT_ID=$(az identity show --name "$PREFIX-github" --resource-group "$RG" --query clientId -o tsv)
PRINCIPAL_ID=$(az identity show --name "$PREFIX-github" --resource-group "$RG" --query principalId -o tsv)
RG_ID=$(az group show --name "$RG" --query id -o tsv)
az role assignment create --assignee-object-id "$PRINCIPAL_ID" --assignee-principal-type ServicePrincipal \
  --role Contributor --scope "$RG_ID"
az identity federated-credential create --name github-main --identity-name "$PREFIX-github" --resource-group "$RG" \
  --issuer https://token.actions.githubusercontent.com --subject "repo:${GH_REPO}:ref:refs/heads/main" \
  --audiences api://AzureADTokenExchange
OWNER_ID=$(gh api "repos/${GH_REPO}" --jq .owner.id)
REPO_ID=$(gh api "repos/${GH_REPO}" --jq .id)
az identity federated-credential create --name github-main-ids --identity-name "$PREFIX-github" --resource-group "$RG" \
  --issuer https://token.actions.githubusercontent.com \
  --subject "repo:${GH_REPO%/*}@${OWNER_ID}/${GH_REPO#*/}@${REPO_ID}:ref:refs/heads/main" \
  --audiences api://AzureADTokenExchange

# Step 7: GitHub secrets and variables (values go straight to GitHub, never into a file)
gh secret set AZURE_CLIENT_ID --repo "$GH_REPO" --body "$CLIENT_ID"
gh secret set AZURE_TENANT_ID --repo "$GH_REPO" --body "$(az account show --query tenantId -o tsv)"
gh secret set AZURE_SUBSCRIPTION_ID --repo "$GH_REPO" --body "$(az account show --query id -o tsv)"
gh secret set KRAAL_DB_PASSWORD --repo "$GH_REPO" --body "$KRAAL_DB_PASSWORD"
gh secret set ACTAS_DB_PASSWORD --repo "$GH_REPO" --body "$ACTAS_DB_PASSWORD"
gh variable set PREFIX --repo "$GH_REPO" --body "$PREFIX"
gh variable set RESOURCE_GROUP --repo "$GH_REPO" --body "$RG"
gh variable set UI_STORAGE --repo "$GH_REPO" --body "$STORAGE"

# Step 9: Reader on the resource group for the professors, so they can check the deployment
for p in amartini@faculty.ie.edu bserra@faculty.ie.edu; do
  az role assignment create --assignee "$p" --role Reader --scope "$RG_ID"
done