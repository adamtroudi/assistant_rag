---
doc_id: spark_exogenes
site: EPI
year: 2024
doc_type: donnees_exogenes
indexable: true
---

# Fichiers exogènes déclarés dans SPARK

- SPARK référence electricity_emissions_15min_transnetbw_2018_2024.csv : fréquence 15min, horodatage UTC, colonnes notamment utc_datetime (sans unité), nuclear (MW), hydro (MW), wind_onshore (MW), solar_pv (MW), emission_intensity_g_per_kwh (g/kWh). Le ZIP de métadonnées reçu ne contient pas ce fichier de données. [source: spark_metadata_exogenous; datasets.file=electricity_emissions_15min_transnetbw_2018_2024.csv]
- SPARK référence electricity_prices_15min_de_2018_2024.csv : fréquence 15min, horodatage UTC, colonnes notamment utc_datetime (sans unité), price_eur_per_mwh (EUR/MWh). Le ZIP de métadonnées reçu ne contient pas ce fichier de données. [source: spark_metadata_exogenous; datasets.file=electricity_prices_15min_de_2018_2024.csv]
- SPARK référence holidays_kalsruhe_bw_2018_2024.csv : fréquence daily, horodatage local, colonnes notamment date (sans unité), weekday (sans unité), is_holiday (sans unité), holiday_name (sans unité). Le ZIP de métadonnées reçu ne contient pas ce fichier de données. [source: spark_metadata_exogenous; datasets.file=holidays_kalsruhe_bw_2018_2024.csv]
- SPARK référence weather_data_karlsruhe_hourly_2018_2024.csv : fréquence hourly, horodatage UTC, colonnes notamment utc_datetime (sans unité), temperature_air_mean_2m_°C (°C), temperature_dew_point_mean_2m_°C (°C), humidity_% (%), wind_speed_m/s (m/s), radiation_global_J/cm²_per_hour (J/cm² per hour). Le ZIP de métadonnées reçu ne contient pas ce fichier de données. [source: spark_metadata_exogenous; datasets.file=weather_data_karlsruhe_hourly_2018_2024.csv]
- SPARK référence weather_data_stations_used.csv : fréquence static_table, horodatage non précisé, colonnes notamment parameter (sans unité), station_id (sans unité), name (sans unité), state (sans unité), distance (km). Le ZIP de métadonnées reçu ne contient pas ce fichier de données. [source: spark_metadata_exogenous; datasets.file=weather_data_stations_used.csv]

Les séries exogènes horodatées de SPARK utilisent des instants UTC tandis que le calendrier de jours fériés décrit des dates locales. Convertir les instants UTC en Europe/Berlin pour l’affichage et les créneaux de production; au passage à l’heure d’hiver, distinguer les deux occurrences de 02:00 par leur décalage UTC. [source: spark_metadata_exogenous; datasets[*].timezone / time_column]

Le fichier SPARK des cours allemands est présenté sur une grille de 15 minutes. Selon la Bundesnetzagentur, le marché day-ahead allemand a commencé à négocier des prix de 15 minutes le 1er octobre 2025. Pour 2024, ne pas prendre quatre lignes à la même heure pour quatre prix day-ahead indépendants; vérifier les valeurs et leur traitement dans l’archive complète. [source: spark_metadata_exogenous; datasets.file=electricity_prices_15min_de_2018_2024.csv] [source: smard_market_resolution; section 'Since 1 October 2025']

Le prix `price_eur_per_mwh` correspond à un cours de gros déclaré par le jeu, pas à la facture ni au contrat du site EPI. Les émissions régionales `emission_intensity_g_per_kwh` ne prouvent pas un facteur contractuel d’achat d’électricité. Ne créer aucun tarif ou facteur numérique à partir des seules métadonnées.
