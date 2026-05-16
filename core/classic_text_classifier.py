from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from core.classic_text_anchors import CATEGORY_ANCHOR_EXAMPLES, INTENT_ANCHOR_EXAMPLES

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
except ImportError:
    TfidfVectorizer = None
    LogisticRegression = None
    Pipeline = None


@dataclass(frozen=True)
class TrainingSummary:
    task_name: str
    sample_count: int
    label_count: int
    source: str


def _flatten_examples(examples_by_label: Mapping[str, Sequence[str]]) -> Tuple[List[str], List[str]]:
    texts: List[str] = []
    labels: List[str] = []

    for label, examples in examples_by_label.items():
        for text in examples:
            clean_text = str(text or "").strip()
            if not clean_text:
                continue
            texts.append(clean_text)
            labels.append(label)

    return texts, labels


class ClassicTextClassifier:
    """
    Linea base clasica y explicable para texto corto.

    Se basa en:
    - TF-IDF para convertir texto en rasgos lexicales
    - Logistic Regression para obtener una prediccion probabilistica

    Esta clase no reemplaza al router actual. Solo genera una senal
    auxiliar interpretable que puede convivir con reglas, embeddings
    y LLMs.
    """

    def __init__(
        self,
        task_name: str,
        anchor_examples: Mapping[str, Sequence[str]],
        random_state: int = 42,
    ) -> None:
        self.task_name = task_name
        self.anchor_examples = {label: list(examples) for label, examples in anchor_examples.items()}
        self.random_state = random_state
        self._pipeline: Optional[Pipeline] = None
        self._is_trained = False
        self._training_summary: Optional[TrainingSummary] = None
        self._unavailable_reason: Optional[str] = None

    @property
    def is_trained(self) -> bool:
        return self._is_trained

    @property
    def training_summary(self) -> Optional[TrainingSummary]:
        return self._training_summary

    def fit(
        self,
        examples_by_label: Optional[Mapping[str, Sequence[str]]] = None,
        additional_examples: Optional[Iterable[Tuple[str, str]]] = None,
    ) -> "ClassicTextClassifier":
        """
        Entrena el pipeline una sola vez y lo deja listo para reuse.

        - examples_by_label permite sustituir el dataset base.
        - additional_examples agrega pares (label, text) al dataset.
        """
        if self._is_trained:
            return self

        if Pipeline is None or TfidfVectorizer is None or LogisticRegression is None:
            self._unavailable_reason = "scikit_learn_not_installed"
            return self

        training_examples = dict(examples_by_label or self.anchor_examples)
        texts, labels = _flatten_examples(training_examples)

        for label, text in additional_examples or []:
            clean_text = str(text or "").strip()
            if not label or not clean_text:
                continue
            texts.append(clean_text)
            labels.append(str(label))

        if len(texts) < 2 or len(set(labels)) < 2:
            self._unavailable_reason = "insufficient_training_examples"
            return self

        self._pipeline = Pipeline(
            steps=[
                (
                    "tfidf",
                    TfidfVectorizer(
                        lowercase=True,
                        strip_accents="unicode",
                        ngram_range=(1, 2),
                        min_df=1,
                        sublinear_tf=True,
                    ),
                ),
                (
                    "classifier",
                    LogisticRegression(
                        max_iter=1000,
                        class_weight="balanced",
                        random_state=self.random_state,
                    ),
                ),
            ]
        )
        self._pipeline.fit(texts, labels)
        self._is_trained = True
        self._training_summary = TrainingSummary(
            task_name=self.task_name,
            sample_count=len(texts),
            label_count=len(set(labels)),
            source="anchor_examples",
        )
        return self

    def predict(self, text: str, top_k: int = 3) -> Dict[str, Any]:
        """
        Devuelve prediccion, score y top candidatos.

        Si la dependencia no existe o el clasificador no esta disponible,
        responde de forma segura sin romper el flujo del sistema.
        """
        clean_text = str(text or "").strip()
        if not clean_text:
            return self._empty_prediction(reason="empty_text")

        if not self._is_trained:
            self.fit()

        if not self._pipeline or not self._is_trained:
            return self._empty_prediction(reason=self._unavailable_reason or "classifier_not_ready")

        probabilities = self._pipeline.predict_proba([clean_text])[0]
        classes = [str(label) for label in self._pipeline.named_steps["classifier"].classes_]
        ranked_indexes = sorted(range(len(classes)), key=lambda idx: probabilities[idx], reverse=True)
        top_candidates = [
            {
                "label": classes[idx],
                "score": round(float(probabilities[idx]), 4),
            }
            for idx in ranked_indexes[: max(1, top_k)]
        ]
        best = top_candidates[0]

        return {
            "available": True,
            "task_name": self.task_name,
            "model_type": "tfidf_logistic_regression",
            "predicted_label": best["label"],
            "confidence": best["score"],
            "top_candidates": top_candidates,
            "training_summary": self._serialize_training_summary(),
        }

    def _empty_prediction(self, reason: str) -> Dict[str, Any]:
        return {
            "available": False,
            "task_name": self.task_name,
            "model_type": "tfidf_logistic_regression",
            "predicted_label": None,
            "confidence": 0.0,
            "top_candidates": [],
            "reason": reason,
            "training_summary": self._serialize_training_summary(),
        }

    def _serialize_training_summary(self) -> Optional[Dict[str, Any]]:
        if not self._training_summary:
            return None
        return {
            "task_name": self._training_summary.task_name,
            "sample_count": self._training_summary.sample_count,
            "label_count": self._training_summary.label_count,
            "source": self._training_summary.source,
        }


@lru_cache(maxsize=1)
def get_default_category_classifier() -> ClassicTextClassifier:
    """
    Clasificador cacheado para no reentrenar en cada mensaje.

    La primera llamada lo entrena; las siguientes reutilizan la misma
    instancia ya ajustada dentro del proceso actual.
    """
    classifier = ClassicTextClassifier(
        task_name="category",
        anchor_examples=CATEGORY_ANCHOR_EXAMPLES,
    )
    classifier.fit()
    return classifier


@lru_cache(maxsize=1)
def get_default_intent_classifier() -> ClassicTextClassifier:
    classifier = ClassicTextClassifier(
        task_name="intent",
        anchor_examples=INTENT_ANCHOR_EXAMPLES,
    )
    classifier.fit()
    return classifier
