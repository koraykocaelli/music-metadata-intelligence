import json
from pathlib import Path

from app.services.matching import calculate_similarity_components
from app.services.normalization import (
    detect_track_versions,
    normalize_text,
    normalize_track_title,
)


DATASET_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "evaluation_pairs.json"
)


ARTIST_THRESHOLDS = [60.0, 70.0, 80.0, 90.0]
TITLE_THRESHOLDS = [
    70.0,
    80.0,
    85.0,
    90.0,
    92.5,
    95.0,
]
FINAL_THRESHOLDS = [80.0, 85.0, 90.0, 95.0]


def load_evaluation_pairs() -> list[dict]:
    with DATASET_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def calculate_final_score(
    artist_score: float,
    title_score: float,
) -> float:
    return round(
        (artist_score * 0.4) + (title_score * 0.6),
        2,
    )


def predict_match(
    pair: dict,
    artist_threshold: float,
    title_threshold: float,
    final_threshold: float,
) -> bool:
    artist_a = normalize_text(pair["artist_a"])
    artist_b = normalize_text(pair["artist_b"])

    title_a = normalize_track_title(pair["title_a"])
    title_b = normalize_track_title(pair["title_b"])

    versions_a = detect_track_versions(pair["title_a"])
    versions_b = detect_track_versions(pair["title_b"])

    artist_score, title_score = calculate_similarity_components(
        artist_a,
        title_a,
        artist_b,
        title_b,
    )

    final_score = calculate_final_score(
        artist_score,
        title_score,
    )

    if versions_a != versions_b:
        return False

    if artist_score < artist_threshold:
        return False

    if title_score < title_threshold:
        return False

    return final_score >= final_threshold


def evaluate_thresholds(
    pairs: list[dict],
    artist_threshold: float,
    title_threshold: float,
    final_threshold: float,
) -> dict:
    true_positive = 0
    false_positive = 0
    true_negative = 0
    false_negative = 0

    for pair in pairs:
        expected = pair["expected_match"]

        predicted = predict_match(
            pair,
            artist_threshold,
            title_threshold,
            final_threshold,
        )

        if expected and predicted:
            true_positive += 1
        elif not expected and predicted:
            false_positive += 1
        elif not expected and not predicted:
            true_negative += 1
        else:
            false_negative += 1

    precision_denominator = true_positive + false_positive
    precision = (
        true_positive / precision_denominator
        if precision_denominator
        else 0.0
    )

    recall_denominator = true_positive + false_negative
    recall = (
        true_positive / recall_denominator
        if recall_denominator
        else 0.0
    )

    f1_denominator = precision + recall
    f1_score = (
        2 * precision * recall / f1_denominator
        if f1_denominator
        else 0.0
    )

    return {
        "artist_threshold": artist_threshold,
        "title_threshold": title_threshold,
        "final_threshold": final_threshold,
        "precision": precision,
        "recall": recall,
        "f1": f1_score,
        "false_positive": false_positive,
        "false_negative": false_negative,
    }


def main() -> None:
    pairs = load_evaluation_pairs()

    results = []

    for artist_threshold in ARTIST_THRESHOLDS:
        for title_threshold in TITLE_THRESHOLDS:
            for final_threshold in FINAL_THRESHOLDS:
                result = evaluate_thresholds(
                    pairs,
                    artist_threshold,
                    title_threshold,
                    final_threshold,
                )

                results.append(result)

    results.sort(
        key=lambda result: (
            result["f1"],
            result["precision"],
            -result["false_positive"],
        ),
        reverse=True,
    )

    print(f"Dataset size: {len(pairs)}")
    print(f"Configurations tested: {len(results)}")
    print()
    print("Top threshold configurations:")

    for result in results[:10]:
        print(
            f'artist >= {result["artist_threshold"]:.0f}, '
            f'title >= {result["title_threshold"]:.0f}, '
            f'final >= {result["final_threshold"]:.0f} | '
            f'precision={result["precision"]:.2%}, '
            f'recall={result["recall"]:.2%}, '
            f'F1={result["f1"]:.2%}, '
            f'FP={result["false_positive"]}, '
            f'FN={result["false_negative"]}'
        )


if __name__ == "__main__":
    main()