import pytest

from lexicon.model import Dataset, Language, Source
from lexicon.validate import DatasetValidationError, validate_dataset


def test_dataset_validation_requires_usable_source_license_metadata() -> None:
    dataset = Dataset(
        language=Language(id="en", iso_639_1="en", name="English"),
        sources=(
            Source(
                id="seed",
                name="Seed",
                version="1",
                source_url="https://example.invalid",
                license="",
                retrieved_at="2026-07-31",
            ),
        ),
        lexemes=(),
    )
    with pytest.raises(DatasetValidationError, match="license"):
        validate_dataset(dataset)
