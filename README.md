# Assistant RAG EPI

API FastAPI dédiée à l'explication documentée des données SPARK pour `EPI_PumpStation1`, `EPI_PumpStation2` et `EPI_PickAndPlace`, ainsi qu'à l'analyse de prévisions XGBoost transmises dynamiquement par la plateforme pour tout identifiant de machine.

Le corpus fourni est extrait sous `data/rag_epi_3_machines/`. Voir [le guide d'intégration](docs/rag_integration.md) pour PostgreSQL/pgvector, l'ingestion, le contrat de prévision, l'API et les tests.
