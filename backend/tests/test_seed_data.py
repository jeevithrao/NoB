"""Guards the demo content so a typo can't ship a broken walk."""
from app.seed_data import NEIGHBOURHOODS, TOURS

DIFFICULTIES = {"Easy", "Moderate", "Hard"}


def test_every_tour_points_at_a_real_neighbourhood_and_is_complete():
    slugs = {n["slug"] for n in NEIGHBOURHOODS}
    assert len(slugs) == len(NEIGHBOURHOODS)
    for tour in TOURS:
        assert tour["neighbourhood"] in slugs
        assert tour["difficulty"] in DIFFICULTIES
        assert tour["theme"] and tour["start_point"] and tour["includes"] and tour["languages"]
        assert tour["is_free"] == (tour["price_paise"] == 0)
        assert tour["preview_audio_filename"] and tour["preview_text"] and tour["preview_audio_title"]


def test_stops_have_teasers_coordinates_in_bangalore_and_unique_audio():
    seen = set()
    for tour in TOURS:
        assert len(tour["stops"]) >= 3
        for stop in tour["stops"]:
            assert stop["blurb"] and stop["icon"] and stop["narrative_text"]
            assert 12.7 < stop["lat"] < 13.2 and 77.3 < stop["lng"] < 77.9  # inside Bengaluru
            assert stop["audio_filename"] not in seen
            seen.add(stop["audio_filename"])


def test_passport_has_twelve_slots_and_tour_names_are_unique():
    assert len(NEIGHBOURHOODS) == 12
    names = [t["name"] for t in TOURS]
    assert len(names) == len(set(names))
