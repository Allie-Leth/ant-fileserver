from datetime import datetime, timezone, timedelta
import pytest


from app.models import FirmwareMetaData


@pytest.mark.unit
def test_from_dict_parses_dates_and_defaults():
    data = {
        "project": "acme",
        "device_type": "widget",
        "version": "1.2.3",
        "checksum": "abc",
        "file_size": 123,
        "release_date": "2025-01-02T03:04:05Z",
    }
    meta = FirmwareMetaData.from_dict(data)

    assert meta.release_date == datetime(2025, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    assert meta.channel == "stable"          # default value present
    assert meta.version == "1.2.3"

@pytest.mark.unit
def test_to_dict_roundtrip():
    meta = FirmwareMetaData(
        project="acme",
        device_type="widget",
        version="2.0.0",
        checksum="x",
        file_size=1,
        release_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    d = meta.to_dict(include_url=False)
    assert d["version"] == "2.0.0"
    assert "download_url" not in d

@pytest.mark.unit
def test_metadata_version_validation():
    with pytest.raises(ValueError):
        FirmwareMetaData(
            project="acme",
            device_type="widget",
            version="0.1.0",
            checksum="x",
            file_size=1,
            release_date=datetime.now(timezone.utc),
            metadata_version=99,          # unsupported
        )

def test_from_dict_parses_offset_date():
    """
    release_date without trailing 'Z' should be parsed by the fallback
    branch (line 53).  We use an explicit UTC+02:00 offset to be sure.
    """
    data = {
        "project":      "acme",
        "device_type":  "widget",
        "version":      "3.3.3",
        "checksum":     "abc",
        "file_size":    999,
        "release_date": "2025-06-01T12:00:00+02:00",   # ← no 'Z'
    }

    meta = FirmwareMetaData.from_dict(data)

    expected_dt = datetime(2025, 6, 1, 12, 0, 0,
                           tzinfo=timezone(timedelta(hours=2)))
    assert meta.release_date == expected_dt