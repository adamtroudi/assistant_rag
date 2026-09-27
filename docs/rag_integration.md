# Intégration de l'assistant RAG EPI

## Périmètre et architecture

Le dossier remis ne contenait aucune application existante, migration ou service LLM à réutiliser. Cette livraison constitue donc un module FastAPI autonome et transplantable. Elle n'indexe que les 20 lignes fournies dans `data/rag_epi_3_machines/rag_chunks.jsonl`. Les machines autorisées sont strictement :

- `EPI_PumpStation1`
- `EPI_PumpStation2`
- `EPI_PickAndPlace`

Les passages généraux ont `machine_id = null`. TEC, photovoltaïque, compteur global et toute autre machine EPI sont rejetés. Les prévisions restent séparées du corpus documentaire.

## Installation et démarrage

Prérequis : Python 3.11+, PostgreSQL 14+ et, de préférence, l'extension serveur [pgvector](https://github.com/pgvector/pgvector). Installer le paquet `vector` sur le serveur PostgreSQL nécessite souvent des droits administrateur. L'image Docker fournie l'inclut déjà.

```bash
python -m venv .venv
# PowerShell
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
docker compose up -d db
alembic upgrade head
python -m app.cli ingest
uvicorn app.main:app --reload
```

Le premier lancement de l'ingestion télécharge `intfloat/multilingual-e5-small`. Les textes sont encodés avec le préfixe `passage:`, les questions avec `query:`, puis normalisés en 384 dimensions. La recherche native utilise la distance cosine exacte pgvector, sans index approximatif. Si `CREATE EXTENSION vector` n'est pas autorisé, la migration conserve les embeddings dans PostgreSQL en JSONB et le repository effectue un calcul cosine exact en Python sur les lignes déjà filtrées (20 au maximum). La présence de la colonne `embedding_vector` permet de savoir quel mode est actif.

L'ingestion valide tous les `source_id`, fait un upsert par `chunk_id`, puis supprime uniquement les fragments obsolètes dont `corpus_name = rag_epi_3_machines`. Elle ne modifie aucune autre table ni aucun autre corpus. Aucun endpoint HTTP de réindexation n'est exposé.

## Configuration LLM

Renseigner `LLM_BASE_URL`, `LLM_MODEL` et, si le fournisseur l'exige, `LLM_API_KEY`. Le client appelle `POST {LLM_BASE_URL}/chat/completions` au format compatible OpenAI. Avec Ollama, une valeur typique est `LLM_BASE_URL=http://localhost:11434/v1`. Sans URL ou modèle, l'API renvoie explicitement HTTP 503 et ne fabrique aucune réponse.

Le prompt système vient du corpus. Le fournisseur reçoit seulement ce prompt, la question, les passages retrouvés et les éventuels résumés de prévision calculés en Python. Les citations structurées de la réponse HTTP sont construites depuis les métadonnées du corpus, indépendamment du texte généré.

## Contrat des prévisions

Le format principal est la sortie XGBoost transmise directement par la plateforme dans chaque requête, comme décrit ci-dessous. Un chargeur de fichier utilisant le contrat interne suivant reste disponible uniquement comme solution de repli pour les exécutions autonomes :

```json
{
  "forecasts": [
    {
      "forecast_id": "calculation-id",
      "forecast_version": "model-version",
      "machine_id": "EPI_PumpStation1",
      "horizon_days": 7,
      "start_utc": "2026-10-01T00:00:00Z",
      "end_utc": "2026-10-08T00:00:00Z",
      "quantity": "active_power",
      "unit": "kW",
      "points": [
        {"timestamp_utc": "2026-10-01T00:00:00Z", "value": null}
      ]
    }
  ]
}
```

Les seuls horizons sont 7, 15 et 30 jours. Identifiant de machine, bornes UTC, unicité et appartenance des points à la fenêtre, ainsi que les unités `kW`/`kWh`, sont validés avant usage. `null` reste inconnu. Python calcule minimum, maximum et moyenne; une somme n'est produite que pour une série déjà exprimée en `kWh`. Aucun coût n'est calculé. Les dates locales sont rendues en `Europe/Berlin` avec leur décalage réel (`+01:00` ou `+02:00`).

### Sortie XGBoost transmise par la plateforme

La plateforme peut transmettre directement son résultat XGBoost dans le champ `forecast_results` de `POST /api/assistant/chat`, sans écrire le fichier dans l'image Docker :

```json
{
  "question": "Quels sont les KPI de cette prévision ?",
  "forecast_results": {
    "machine": "EPI_TotalLoad_synthetic_test",
    "value_col": "P_total",
    "frequency_minutes": 5,
    "horizon_days": 30,
    "n_points": 8640,
    "forecast": [
      {"timestamp": "2025-01-01T00:00:00", "predicted_P_total": 874.507}
    ]
  }
}
```

L'exemple est abrégé : le tableau réel doit contenir exactement `n_points` points et couvrir l'horizon à la cadence déclarée. Le nom de la valeur prédite doit être `predicted_<value_col>`. Les champs optionnels `unit`, `timezone`, `forecast_id` et `forecast_version` sont recommandés. En leur absence :

- `FORECAST_DEFAULT_UNIT=W` est appliqué et les puissances sont converties en kW ;
- `FORECAST_NAIVE_TIMEZONE=UTC` est appliqué aux timestamps sans offset ;
- un identifiant stable est dérivé du SHA-256 du contenu ;
- un avertissement signale l'absence de version XGBoost.

Le backend valide tous les points mais ne transmet pas les milliers de valeurs au LLM. Il calcule en Python les KPI et les différences entre séries. Les preuves RAG retrouvées sont ajoutées au message système sous forme de données délimitées; le message utilisateur contient uniquement la question, les KPI et les comparaisons calculées.

Le périmètre des documents et celui des prévisions sont volontairement distincts : les faits SPARK restent limités aux trois machines documentées, mais une prévision validée peut porter sur tout identifiant produit par la plateforme, par exemple `EPI_TotalLoad_synthetic_test`. Le modèle doit alors répondre avec les KPI calculés sans prétendre disposer de documentation SPARK sur cet identifiant.

## API

`POST /api/assistant/chat` exige l'en-tête `X-API-Key`, comparé à `ASSISTANT_API_KEY`. Le corps interdit les champs inconnus :

```bash
curl -X POST http://localhost:8000/api/assistant/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: replace-with-a-long-random-value" \
  -d '{"question":"Quelle alimentation est publiée pour PumpStation1 ?","machine_ids":["EPI_PumpStation1"]}'
```

Réponse :

```json
{
  "answer": "...",
  "citations": [
    {
      "chunk_id": "machines_EPI_PumpStation1__alimentation",
      "machine_id": "EPI_PumpStation1",
      "source": {"source_id": "spark_article", "title": "...", "url": "...", "archive_path": null, "locator": "..."}
    }
  ],
  "forecast_refs": [],
  "warnings": []
}
```

`machine_ids` est facultatif. Sans ce champ, les noms explicites sont détectés; sinon les trois machines sont autorisées. `horizon_days` accepte 7, 15 ou 30 et `forecast_id` sélectionne un calcul. Un fichier absent produit un avertissement et n'empêche pas le chat documentaire. Un fichier présent mais invalide est rejeté en HTTP 422.

## Vérification

```bash
pytest
```

Le test d'intégration PostgreSQL est automatiquement ignoré sans `TEST_DATABASE_URL`. Pour l'exécuter :

```bash
$env:TEST_DATABASE_URL="postgresql+psycopg://rag:change-me@localhost:5432/rag_assistant"
pytest -m integration
```

## Distribution par Docker Hub

L'image ne contient aucun secret ni `forecast_results.json`. La plateforme transmet sa sortie XGBoost dans le corps JSON de l'appel au chat. L'image contient le code, les migrations et le corpus documentaire extrait. Le modèle d'embedding est téléchargé dans le volume `rag_model_cache` lors de la première ingestion.

Construire et publier l'image :

```powershell
docker build -t DOCKERHUB_USER/epi-rag-assistant:0.1.0 .
docker login
docker push DOCKERHUB_USER/epi-rag-assistant:0.1.0
```

Sur la machine destinataire, copier `docker-compose.yml` et créer un `.env` privé :

```dotenv
ASSISTANT_IMAGE=DOCKERHUB_USER/epi-rag-assistant:0.1.0
ASSISTANT_API_KEY=<secret-de-la-plateforme>
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=qwen/qwen3.8-27b
LLM_API_KEY=<secret-du-fournisseur>
```

Puis lancer :

```powershell
docker compose pull app
docker compose up -d db
docker compose run --rm app python -m app.cli ingest
docker compose up -d app
docker compose ps
```

Le volume PostgreSQL conserve les 20 embeddings et `rag_model_cache` conserve le modèle E5. Ne jamais intégrer `.env` dans l'image ni le publier avec le projet.
