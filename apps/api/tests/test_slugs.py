from app.core.slugs import slugify


def test_slugify_game_titles() -> None:
    assert slugify("Granblue Fantasy Relink") == "granblue-fantasy-relink"
    assert slugify("Monster Hunter Wilds") == "monster-hunter-wilds"
    assert slugify("Grand Blue Dreaming") == "grand-blue-dreaming"
    assert slugify("  League of Legends  ") == "league-of-legends"
