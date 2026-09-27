# Corpus RAG SPARK limité à trois équipements EPI

Périmètre strict : EPI_PumpStation1, EPI_PumpStation2, EPI_PickAndPlace. Ce paquet dérive du catalogue et des métadonnées SPARK déjà vérifiés. Il ne contient aucun résultat XGBoost ni optimisation; leurs sorties seront raccordées au backend séparément. Le site TEC, les sept autres machines EPI, EPI_PV et EPI_TotalLoad sont exclus de l'index de ce paquet.

## Contenu et utilisation

- `machines.json` : catalogue des trois équipements, avec provenance et valeurs inconnues nulles.
- `knowledge_base/machines/` : trois fiches techniques, une par équipement.
- `knowledge_base/spark/` : contexte des sites, qualité des mesures et fichiers exogènes annoncés par SPARK.
- `rag_chunks.jsonl` : 20 passages à indexer; `source_refs` contient des repères de citation.
- `sources.csv` : six références utilisées par les passages, avec URL ou chemin de métadonnées.
- `rag_config.json` et `rag_system_prompt.md` : filtres et consignes de génération.
- `missing_data.csv` et `assumptions.csv` : lacunes à lever et registre encore vide pour hypothèses synthétiques.
- `knowledge_base/scenario/README.md` : suivi non indexable des règles de production manquantes.

Indexer le champ `text` de chaque ligne `rag_chunks.jsonl` et conserver `machine_id`, `site`, `year`, `origin`, `confidence`, `source_refs` comme métadonnées. Appliquer le filtre `site=EPI` et valider `machine_id` dans `supported_machine_ids`; les passages généraux (`machine_id=null`) peuvent compléter les trois fiches. L'interface doit afficher le titre et le repère de chaque source via `sources.csv`.

Pour brancher `forecast_results.json`, définir avec l'équipe XGBoost le schéma des horizons, horodatages, unités et machines. Valider ces résultats côté Python et les fournir au LLM comme données structurées à chaque demande; ils ne font pas partie de l'index documentaire. Le ZIP utilisateur ne contient que des métadonnées : contrôler la présence des mesures brutes et des séries exogènes dans l'archive complète SPARK.
