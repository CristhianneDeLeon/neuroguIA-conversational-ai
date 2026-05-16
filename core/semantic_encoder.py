from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from core.classic_text_anchors import CATEGORY_ANCHOR_EXAMPLES, INTENT_ANCHOR_EXAMPLES

try:
    import numpy as np
except ImportError:
    np = None

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None


DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"


@dataclass(frozen=True)
class SemanticInventorySummary:
    task_name: str
    sample_count: int
    label_count: int
    source: str
    aggregation_method: str
    aggregation_top_k: int


def _flatten_anchor_examples(
    examples_by_label: Mapping[str, Sequence[str]],
) -> Tuple[List[str], List[str]]:
    texts: List[str] = []
    labels: List[str] = []

    for label, examples in examples_by_label.items():
        for text in examples:
            clean_text = str(text or "").strip()
            if not clean_text:
                continue
            texts.append(clean_text)
            labels.append(str(label))

    return texts, labels


@lru_cache(maxsize=2)
def _load_sentence_transformer(model_name: str) -> Tuple[Optional[Any], Optional[str]]:
    """
    Carga una sola vez el modelo de embeddings por proceso.

    Si la dependencia o el modelo no estan disponibles, devolvemos una
    razon de indisponibilidad en lugar de romper el flujo.
    """
    if SentenceTransformer is None:
        return None, "sentence_transformers_not_installed"

    try:
        return SentenceTransformer(model_name), None
    except Exception as exc:
        return None, f"model_load_failed:{type(exc).__name__}"


class SemanticAnchorEncoder:
    """
    Senal semantica local basada en embeddings.

    Esta capa:
    - convierte texto en vectores densos con sentence-transformers
    - compara contra anchors por categoria o intencion
    - agrega varias similitudes por etiqueta para evitar depender solo
      de un anchor aislado

    No reemplaza la logica por reglas ni la baseline clasica TF-IDF.
    Solo produce una senal complementaria interpretable para el sistema.
    """

    def __init__(
        self,
        task_name: str,
        anchor_examples: Mapping[str, Sequence[str]],
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        aggregation_top_k: int = 2,
    ) -> None:
        self.task_name = task_name
        self.anchor_examples = {label: list(examples) for label, examples in anchor_examples.items()}
        self.model_name = model_name
        self.aggregation_top_k = max(1, int(aggregation_top_k))

        self._fit_attempted = False
        self._is_ready = False
        self._unavailable_reason: Optional[str] = None
        self._model: Optional[Any] = None
        self._anchor_texts: List[str] = []
        self._anchor_labels: List[str] = []
        self._anchor_embeddings: Optional[Any] = None
        self._inventory_summary: Optional[SemanticInventorySummary] = None

    @property
    def is_ready(self) -> bool:
        return self._is_ready

    @property
    def inventory_summary(self) -> Optional[SemanticInventorySummary]:
        return self._inventory_summary

    def fit(self) -> "SemanticAnchorEncoder":
        """
        Prepara modelo y anchors solo una vez.

        El trabajo costoso ocurre al inicializar esta capa por primera vez:
        - carga del modelo
        - codificacion de anchors

        Despues, cada mensaje solo codifica el texto entrante.
        """
        if self._fit_attempted:
            return self

        self._fit_attempted = True

        if np is None:
            self._unavailable_reason = "numpy_not_installed"
            return self

        model, model_error = _load_sentence_transformer(self.model_name)
        if model is None:
            self._unavailable_reason = model_error or "embedding_model_unavailable"
            return self

        anchor_texts, anchor_labels = _flatten_anchor_examples(self.anchor_examples)
        if len(anchor_texts) < 2 or len(set(anchor_labels)) < 2:
            self._unavailable_reason = "insufficient_anchor_examples"
            return self

        try:
            anchor_embeddings = model.encode(
                anchor_texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        except Exception as exc:
            self._unavailable_reason = f"anchor_encoding_failed:{type(exc).__name__}"
            return self

        self._model = model
        self._anchor_texts = anchor_texts
        self._anchor_labels = anchor_labels
        self._anchor_embeddings = anchor_embeddings
        self._is_ready = True
        self._inventory_summary = SemanticInventorySummary(
            task_name=self.task_name,
            sample_count=len(anchor_texts),
            label_count=len(set(anchor_labels)),
            source="anchor_examples",
            aggregation_method="mean_top_k_cosine",
            aggregation_top_k=self.aggregation_top_k,
        )
        return self

    def encode(self, text: str) -> Optional[Any]:
        """
        Genera el embedding del texto de entrada.

        Se expone como metodo separado para que la capa semantica pueda
        explicarse de forma independiente en la tesis.
        """
        clean_text = str(text or "").strip()
        if not clean_text:
            return None

        if not self._fit_attempted:
            self.fit()

        if not self._is_ready or self._model is None:
            return None

        try:
            return self._model.encode(
                [clean_text],
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )[0]
        except Exception:
            return None

    def predict(self, text: str, top_k: int = 3) -> Dict[str, Any]:
        clean_text = str(text or "").strip()
        if not clean_text:
            return self._empty_prediction(reason="empty_text")

        if not self._fit_attempted:
            self.fit()

        if not self._is_ready or self._anchor_embeddings is None:
            return self._empty_prediction(reason=self._unavailable_reason or "semantic_encoder_not_ready")

        query_embedding = self.encode(clean_text)
        if query_embedding is None:
            return self._empty_prediction(reason="query_encoding_failed")

        # Como los embeddings ya estan normalizados, el producto punto
        # equivale a similitud coseno.
        similarities = np.matmul(self._anchor_embeddings, query_embedding)
        label_scores: Dict[str, List[float]] = {}
        for idx, label in enumerate(self._anchor_labels):
            label_scores.setdefault(label, []).append(float(similarities[idx]))

        aggregated_candidates: List[Dict[str, Any]] = []
        for label, scores in label_scores.items():
            sorted_scores = sorted(scores, reverse=True)
            top_scores = sorted_scores[: min(self.aggregation_top_k, len(sorted_scores))]
            aggregated_similarity = float(sum(top_scores) / len(top_scores))
            aggregated_candidates.append(
                {
                    "label": label,
                    "similarity": round(aggregated_similarity, 4),
                    "best_anchor_similarity": round(sorted_scores[0], 4),
                    "anchor_count": len(scores),
                }
            )

        aggregated_candidates.sort(key=lambda item: (-item["similarity"], -item["best_anchor_similarity"], item["label"]))
        top_candidates = aggregated_candidates[: max(1, top_k)]
        best = top_candidates[0]

        return {
            "available": True,
            "task_name": self.task_name,
            "model_type": "sentence_transformer_anchor_similarity",
            "model_name": self.model_name,
            "predicted_label": best["label"],
            "similarity": best["similarity"],
            "top_candidates": top_candidates,
            "anchor_summary": self._serialize_inventory_summary(),
        }

    def _empty_prediction(self, reason: str) -> Dict[str, Any]:
        return {
            "available": False,
            "task_name": self.task_name,
            "model_type": "sentence_transformer_anchor_similarity",
            "model_name": self.model_name,
            "predicted_label": None,
            "similarity": 0.0,
            "top_candidates": [],
            "reason": reason,
            "anchor_summary": self._serialize_inventory_summary(),
        }

    def _serialize_inventory_summary(self) -> Optional[Dict[str, Any]]:
        if not self._inventory_summary:
            return None
        return {
            "task_name": self._inventory_summary.task_name,
            "sample_count": self._inventory_summary.sample_count,
            "label_count": self._inventory_summary.label_count,
            "source": self._inventory_summary.source,
            "aggregation_method": self._inventory_summary.aggregation_method,
            "aggregation_top_k": self._inventory_summary.aggregation_top_k,
        }


@lru_cache(maxsize=1)
def get_default_category_semantic_encoder() -> SemanticAnchorEncoder:
    encoder = SemanticAnchorEncoder(
        task_name="category",
        anchor_examples=CATEGORY_ANCHOR_EXAMPLES,
        model_name=DEFAULT_EMBEDDING_MODEL,
    )
    encoder.fit()
    return encoder


@lru_cache(maxsize=1)
def get_default_intent_semantic_encoder() -> SemanticAnchorEncoder:
    encoder = SemanticAnchorEncoder(
        task_name="intent",
        anchor_examples=INTENT_ANCHOR_EXAMPLES,
        model_name=DEFAULT_EMBEDDING_MODEL,
    )
    encoder.fit()
    return encoder
