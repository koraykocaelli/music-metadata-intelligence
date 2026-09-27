import json
from pathlib import Path

from app.services.matching import (
    calculate_similarity,
    calculate_similarity_components,
    is_metadata_match,
)

from app.services.normalization import (
    normalize_text,
    normalize_track_title,
)


DATASET_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "evaluation_pairs.json"
)


def load_evaluation_pairs() -> list[dict]:
    with DATASET_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def predict_match(pair: dict) -> tuple[bool, float]:
    artist_a = normalize_text(pair["artist_a"])
    artist_b = normalize_text(pair["artist_b"])

    title_a = normalize_track_title(pair["title_a"])
    title_b = normalize_track_title(pair["title_b"])

    score = calculate_similarity(
        artist_a,
        title_a,
        artist_b,
        title_b,
    )

    predicted = is_metadata_match(
        artist_a,
        title_a,
        artist_b,
        title_b,
        raw_title_a=pair["title_a"],
        raw_title_b=pair["title_b"],
    )

    return predicted, score


def evaluate() -> None:
    pairs = load_evaluation_pairs()

    true_positive = 0
    false_positive = 0
    true_negative = 0
    false_negative = 0

    false_positive_cases = []
    false_negative_cases = []

    for pair in pairs:
        expected = pair["expected_match"]
        predicted, score = predict_match(pair)

        if expected and predicted:
            true_positive += 1

        elif not expected and predicted:
            false_positive += 1

            artist_a = normalize_text(pair["artist_a"])
            artist_b = normalize_text(pair["artist_b"])

            title_a = normalize_track_title(pair["title_a"])
            title_b = normalize_track_title(pair["title_b"])

            artist_score, title_score = calculate_similarity_components(
                artist_a,
                title_a,
                artist_b,
                title_b,
            )

            false_positive_cases.append(
                {
                    "pair": pair,
                    "artist_score": artist_score,
                    "title_score": title_score,
                    "final_score": score,
                }
            )

        elif not expected and not predicted:
            true_negative += 1

        else:
            false_negative += 1
            false_negative_cases.append((pair, score))

    total = len(pairs)
    correct = true_positive + true_negative

    accuracy = correct / total if total else 0.0

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

    print(f"Total pairs: {total}")
    print(f"Correct predictions: {correct}")
    print(f"Accuracy: {accuracy:.2%}")
    print(f"Precision: {precision:.2%}")
    print(f"Recall: {recall:.2%}")
    print(f"F1 score: {f1_score:.2%}")

    print()
    print(f"True positives: {true_positive}")
    print(f"False positives: {false_positive}")
    print(f"True negatives: {true_negative}")
    print(f"False negatives: {false_negative}")

    if false_positive_cases:
        print()
        print("False positive analysis:")

        for case in false_positive_cases:
            pair = case["pair"]

            print(
                f'- "{pair["artist_a"]} - {pair["title_a"]}" '
                f'vs "{pair["artist_b"]} - {pair["title_b"]}"'
            )

            print(
                f'  artist={case["artist_score"]:.2f}, '
                f'title={case["title_score"]:.2f}, '
                f'final={case["final_score"]:.2f}'
            )

    if false_negative_cases:
        print()
        print("False negative cases:")

        for pair, score in false_negative_cases:
            print(
                f'- "{pair["artist_a"]} - {pair["title_a"]}" '
                f'vs "{pair["artist_b"]} - {pair["title_b"]}" '
                f"(score: {score:.2f})"
            )


if __name__ == "__main__":
    evaluate()