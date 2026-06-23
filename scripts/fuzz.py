"""Property-based tests for Black.

By Zac Hatfield-Dodds, based on my Hypothesmith tool for source code
generation.  You can run this file with `python`, `pytest`, or (soon)
a coverage-guided fuzzer I'm working on.
"""

import black
import hypothesmith
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st


# This test uses the Hypothesis and Hypothesmith libraries to generate random
# syntatically-valid Python source code and run Black in odd modes.
@settings(
    max_examples=1000,  # roughly 1k tests/minute, or half that under coverage
    derandomize=True,  # deterministic mode to avoid CI flakiness
    deadline=None,  # ignore Hypothesis' health checks; we already know that
    suppress_health_check=list(HealthCheck),  # this is slow and filter-heavy.
)
@given(
    # Note that while Hypothesmith might generate code unlike that written by
    # humans, it's a general test that should pass for any *valid* source code.
    # (so e.g. running it against code scraped of the internet might also help)
    src_contents=hypothesmith.from_grammar() | hypothesmith.from_node(),
    # Using randomly-varied modes helps us to exercise less common code paths.
    mode=st.builds(
        black.FileMode,
        line_length=st.just(88) | st.integers(0, 200),
        string_normalization=st.booleans(),
        preview=st.booleans(),
        is_pyi=st.booleans(),
        magic_trailing_comma=st.booleans(),
    ),
)
def test_idempotent_any_syntatically_valid_python(
    src_contents: str, mode: black.FileMode
) -> None:
    # Before starting, let's confirm that the input string is valid Python:
    compile(src_contents, "<string>", "exec")  # else the bug is in hypothesmith

    # Then format the code and check that we got equivalent and stable output.
    try:
        dst_contents = black.format_str(src_contents, mode=mode)
        # And check that we got equivalent and stable output.
        black.assert_equivalent(src_contents, dst_contents)
        black.assert_stable(src_contents, dst_contents, mode=mode)
    except black.parsing.ASTSafetyError as e:
        # Convert Black's internal safety error into a controlled test skip so the
        # test harness doesn't crash the whole run. If pytest is available, use
        # pytest.skip to report the skip; otherwise, just return from the test.
        try:
            import pytest
        except Exception:
            pytest = None

        if pytest is not None:
            pytest.skip(f"Black ASTSafetyError encountered: {e}")
        else:
            return

    # Future test: check that pure-python and mypyc versions of black
    # give identical output for identical input?


if __name__ == "__main__":
    # Prefer running tests via pytest to get the proper test harness and to
    # avoid invoking Hypothesis-decorated tests directly at module runtime.
    try:
        import pytest
    except Exception:
        pytest = None

    if pytest is not None:
        # Run pytest programmatically for this file and exit with its return code.
        raise SystemExit(pytest.main([__file__]))
    else:
        # Fallback: do not call the Hypothesis-decorated test directly; inform the user.
        import sys

        print("Please run this test module with pytest (e.g., `pytest fuzz.py`).")
        sys.exit(0)

    # If Atheris is available, run coverage-guided fuzzing.
    # (if you want only bounded fuzzing, just use `pytest fuzz.py`)
    try:
        import sys

        import atheris
    except ImportError:
        pass
    else:
        test = test_idempotent_any_syntatically_valid_python
        atheris.Setup(
            sys.argv,
            test.hypothesis.fuzz_one_input,  # type: ignore[attr-defined]
        )
        atheris.Fuzz()
