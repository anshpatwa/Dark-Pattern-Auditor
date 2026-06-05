from dpa import taxonomy


def test_every_pattern_has_a_valid_category():
    for p in taxonomy.PATTERNS:
        assert p.category in taxonomy.VALID_CATEGORIES, p.key
        assert p.default_severity in {"low", "medium", "high", "critical"}


def test_pattern_keys_are_unique():
    keys = [p.key for p in taxonomy.PATTERNS]
    assert len(keys) == len(set(keys))


def test_categories_cover_all_patterns():
    nested = sum(len(c.patterns) for c in taxonomy.categories())
    assert nested == len(taxonomy.PATTERNS)


def test_prompt_block_mentions_every_pattern():
    block = taxonomy.taxonomy_prompt_block()
    for p in taxonomy.PATTERNS:
        assert p.key in block
