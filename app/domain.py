from typing import Final

SUPPORTED_MACHINE_IDS: Final[tuple[str, ...]] = (
    "EPI_PumpStation1",
    "EPI_PumpStation2",
    "EPI_PickAndPlace",
)
CORPUS_NAME: Final[str] = "rag_epi_3_machines"
EMBEDDING_DIMENSION: Final[int] = 384

