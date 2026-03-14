# Golden Test Fixtures

These JSON files capture the expected output of `build_tax_year_results()` for
the three ATO worked examples validated in test_tax_engine.py.

## Files

- ato_fixture_a_sonya.json -- ATO Example: Sonya (short-term, no CGT discount)
- ato_fixture_b_mei_ling.json -- ATO Example: Mei-Ling (long-term with prior loss)
- ato_fixture_c_fifo.json -- FIFO multi-parcel disposal across two lots

## Regeneration

If the tax engine output changes intentionally, regenerate with:

    pytest tests/test_golden.py --regen-golden

This will update the JSON files and skip the tests (they are regenerated, not run).
Review the diff before committing. Never regenerate without a code review.

## Normal Use

    pytest tests/ -k "golden"

Compares current engine output to the stored JSON. Any divergence fails the test.
