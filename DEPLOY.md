# Deploying Legal AI Hub to Azure App Service

This guide puts the app online at a permanent link (`https://<your-app-name>.azurewebsites.net`)
using the **Azure for Students** credit ($100, no credit card). Every step is written for a
first-time Azure user.

> **Cost safety in one line:** the *App Service plan* is what costs money, every hour it exists,
> even if the app is stopped. When you are done, **delete the resource group** (section 6).

---

## 0. What runs where

| Piece | Where it lives |
| --- | --- |
| Code (`app.py`, chatbot, knowledge base) | GitHub `main`, deployed automatically by GitHub Actions |
| Fine-tuned models (Module B / C, ~880 MB) | Hugging Face Hub: `vaishnavi1011/legal-case-outcome-predictor`. Downloaded on the first prediction, cached in `/home/hf_cache` (Azure's permanent disk), so only once |
| Database and sign-in | Supabase. URL and key are given to Azure as *App settings* (environment variables) |

## 1. Which plan size? (measured)

Measured on Linux, Python 3.12, both models loaded, a prediction, full-document mode and a SHAP
explanation:

| Stage | Memory (RSS) |
| --- | --- |
| App started, no models | ~0.1 GB |
| Both models loaded | ~0.86 GB |
| After a prediction | ~1.6 GB |
| **Peak, with SHAP decision drivers** | **~1.8 GB** |

(About 0.17 GB of that was GPU libraries that the CPU-only PyTorch build no longer loads, so
expect roughly 1.6–1.7 GB on Azure.)

| Tier | RAM | Verdict |
| --- | --- | --- |
| F1 (Free) | 1 GB, 60 CPU-min/day | Cannot run it |
| B1 | 1.75 GB | Too tight: the platform needs some of that RAM, so SHAP would crash it |
| **B2** | **3.5 GB** | **Smallest tier that works reliably. Use this.** |

Check the exact price on the plan-size screen in the portal before creating it. Roughly: B2 uses
about a quarter of the $100 credit per month, so it lasts a few months. Delete it when not needed.

## 2. One-time settings (summary)

| Setting | Value |
| --- | --- |
| Runtime | Python 3.12, Linux |
| Startup command | `python -m streamlit run app.py --server.port 8000 --server.address 0.0.0.0` |
| `WEBSITES_PORT` | `8000` |
| `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` (Azure installs `requirements.txt`) |
| `HF_HOME` | `/home/hf_cache` (keeps the model download between restarts) |
| `SUPABASE_URL`, `SUPABASE_KEY` | from Supabase → Project Settings → API. Use the **anon / publishable** key, never `service_role` |
| Always On | On (so the app does not sleep) |
| Web sockets | On (Streamlit needs them) |

## 3. Create everything in the Azure portal (click-by-click)

Sign in at https://portal.azure.com with the account that shows your *Azure for Students*
subscription.

**3.1 Resource group** (a folder that holds everything, so it is easy to delete later)
1. Search bar → **Resource groups** → **+ Create**.
2. Subscription: *Azure for Students*. Name: `rg-legal-ai-hub`. Region: **Central India**
   (if a later step says the region is not allowed for your subscription, use *South India* or *East US*).
3. **Review + create** → **Create**.

**3.2 Web app and plan**
1. Search bar → **App Services** → **+ Create** → **Web App**.
2. **Basics** tab:
   - Resource group: `rg-legal-ai-hub`
   - Name: `legal-ai-hub-vaishnavi` (must be unique worldwide; this becomes the link)
   - Publish: **Code**. Runtime stack: **Python 3.12**. Operating system: **Linux**. Region: same as above.
   - Linux plan: **Create new** → `plan-legal-ai-hub`.
   - Pricing plan: click **Explore pricing plans** → choose **Basic B2**. Read the monthly price shown.
3. **Deployment** tab: leave GitHub Actions **off** for now (we connect it in step 4).
4. **Monitoring** tab: Application Insights **No** (it adds cost; logs are still available).
5. **Review + create** → **Create**. Wait ~2 minutes → **Go to resource**.

**3.3 App settings**
1. In the web app: **Settings → Environment variables → App settings → + Add**, one at a time:
   `WEBSITES_PORT` = `8000`, `SCM_DO_BUILD_DURING_DEPLOYMENT` = `true`, `HF_HOME` = `/home/hf_cache`,
   `SUPABASE_URL` = *your URL*, `SUPABASE_KEY` = *your anon key*.
2. **Apply** → **Confirm** (the app restarts).

**3.4 Startup command, Always On, Web sockets**
1. **Settings → Configuration → General settings**.
2. Startup Command: `python -m streamlit run app.py --server.port 8000 --server.address 0.0.0.0`
3. Web sockets: **On**. Always on: **On**. HTTPS Only: **On**.
4. **Save** → **Continue**.

## 4. Deploy from `main` with GitHub Actions

1. In the web app: **Deployment → Deployment Center**.
2. Source: **GitHub** → **Authorize** → Organization `Bharambevaish`, Repository `AI-for-Legal-Case`, Branch `main`.
3. Authentication type: **User-assigned identity** (the safest choice; no password is stored).
4. **Save**. Azure adds a workflow file to `.github/workflows/` on `main` and starts the first run.
   Then on your laptop run `git pull` so you have that file too.
5. Watch it: GitHub → repository → **Actions** tab. The first build takes about 10–15 minutes
   (it installs PyTorch). Public repositories get free Actions minutes.

After that, **every push to `main` redeploys automatically**.

## 5. Check that it works

1. Open `https://legal-ai-hub-vaishnavi.azurewebsites.net`. The first load after a deploy takes 1–2 minutes.
2. Sign in, upload a judgment PDF in **Case Predictor**. The first prediction downloads the models
   (~1–2 minutes, only once). You should see a confidence percentage, not "rule-based estimate".
3. If something fails: web app → **Monitoring → Log stream** shows the live log.
4. In Supabase → **Authentication → URL Configuration**, set Site URL to the Azure link, so
   confirmation emails point to the live app.

| Problem | Fix |
| --- | --- |
| "Application Error" page | Log stream. Usually the startup command or `WEBSITES_PORT` is missing |
| Page loads but spins forever | Web sockets are off (3.4) |
| "Rule-based estimate" only | Log stream: model download failed or out of memory (use B2) |
| Database offline banner | `SUPABASE_URL` / `SUPABASE_KEY` missing or wrong, or the Supabase project is paused |

## 6. Costs: check, alert, and clean up

**Check spending:** portal search bar → **Education** → *Overview* shows credit left. Or
**Cost Management → Cost analysis**, scope = your subscription.

**Budget alert** (an email before the credit is used up):
1. **Cost Management → Budgets → + Add**.
2. Scope: *Azure for Students*. Name `student-budget`. Reset period: Monthly. Amount: `30`.
3. Alert conditions: Actual 50 %, 80 %, 100 % → your email. **Create**.

Azure for Students has a spending limit: when the credit runs out, resources stop. You are
never charged money, but the app goes offline.

**Pause vs. delete**
- *Stop* on the web app does **not** stop the plan's cost.
- To stop paying: delete the resource group. Resource groups → `rg-legal-ai-hub` → **Delete
  resource group** → type the name → **Delete**. This removes the plan and the app. Your code
  (GitHub), models (Hugging Face) and data (Supabase) are not affected, and you can recreate
  everything with this guide in about 15 minutes.

## 7. Same thing with the Azure CLI (optional)

Run in Azure **Cloud Shell** (the `>_` icon at the top of the portal). Put the Supabase values in
the portal (step 3.3), not on the command line, so they are not saved in shell history.

```bash
RG=rg-legal-ai-hub; PLAN=plan-legal-ai-hub; APP=legal-ai-hub-vaishnavi; LOC=centralindia
az group create -n $RG -l $LOC
az appservice plan create -g $RG -n $PLAN --is-linux --sku B2
az webapp create -g $RG -p $PLAN -n $APP --runtime "PYTHON:3.12"
az webapp config appsettings set -g $RG -n $APP --settings \
  WEBSITES_PORT=8000 SCM_DO_BUILD_DURING_DEPLOYMENT=true HF_HOME=/home/hf_cache
az webapp config set -g $RG -n $APP --always-on true --web-sockets-enabled true \
  --startup-file "python -m streamlit run app.py --server.port 8000 --server.address 0.0.0.0"
az webapp update -g $RG -n $APP --https-only true
# Clean up when done (stops all cost):
# az group delete -n $RG --yes
```

## 8. Optional extras from the GitHub Student Developer Pack

- **GitHub Codespaces:** a cloud VS Code to test changes without your laptop.
- **Sentry:** error reports from the live app (add later if you want monitoring).
- **Doppler:** a secrets manager. Not needed here; Azure App settings already keep secrets out of GitHub.
- **Custom domain:** a free `.me` domain (Namecheap offer) can point a subdomain such as
  `legal.yourname.me` at the app. Basic (B) plans support custom domains with a free certificate.
