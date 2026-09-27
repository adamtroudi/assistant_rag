---
doc_id: spark_variables_2024_3_machines
site: EPI
year: 2024
doc_type: qualite_donnees
indexable: true
---

# Disponibilité des mesures des trois équipements en 2024

Pour les trois équipements retenus, SPARK répertorie la variable électrique P_total en W et une entrée de métadonnées pour 2024. Le ZIP fourni répertorie les métadonnées; il ne contient pas les fichiers de mesures électriques. [source: spark_metadata_machine; EPI_PumpStation1/2 et EPI_PickAndPlace, measurements / years] [source: spark_metadata_measurement; measurement=P_total; unit=W]

| Équipement | Variable | Proportion de points valides |
|---|---|---:|
| EPI_PumpStation1 | P_total | 68.3% |
| EPI_PumpStation2 | P_total | 68.3% |
| EPI_PickAndPlace | P_total | 83.0% |

Les proportions de points valides annoncées pour P_total en 2024 sont : EPI_PumpStation1 68.3%; EPI_PumpStation2 68.3%; EPI_PickAndPlace 83.0%. Il s'agit de points disponibles, et non de taux de marche ou d'une durée de cycle; les valeurs ont été arrondies à une décimale. [source: spark_metadata_availability; machine=EPI_PumpStation1; measurement=P_total; year=2024; csv_index=5438] [source: spark_metadata_availability; machine=EPI_PumpStation2; measurement=P_total; year=2024; csv_index=6852] [source: spark_metadata_availability; machine=EPI_PickAndPlace; measurement=P_total; year=2024; csv_index=4762]

Le statut et le contenu du fichier physique de mesure doivent être confirmés dans l'archive complète avant tout calcul énergétique.
