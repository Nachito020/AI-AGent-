from dealfinder.dedupe import dedupe_listings
from dealfinder.models import VehicleListing


def test_dedupe_by_vin_keeps_richest():
    sparse = VehicleListing(make="Toyota", model="Tacoma", vin="ABC123")
    rich = VehicleListing(
        make="Toyota", model="Tacoma", vin="abc123",
        mileage=62000, asking_price=21500, url="http://x",
    )
    result = dedupe_listings([sparse, rich])
    assert len(result) == 1
    assert result[0].mileage == 62000


def test_dedupe_fuzzy_without_vin():
    a = VehicleListing(year=2018, make="Honda", model="CR-V", mileage=78000, asking_price=14800)
    b = VehicleListing(
        year=2018, make="honda", model="cr-v", mileage=78400, asking_price=14900,
        url="http://y",
    )
    result = dedupe_listings([a, b])
    assert len(result) == 1
    assert result[0].url == "http://y"


def test_different_vehicles_not_merged():
    a = VehicleListing(year=2018, make="Honda", model="CR-V", mileage=78000, asking_price=14800)
    b = VehicleListing(year=2019, make="Honda", model="CR-V", mileage=50000, asking_price=18500)
    assert len(dedupe_listings([a, b])) == 2
