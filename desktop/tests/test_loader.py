import json

import pytest

from pipeline.word3 import load, Word3Error, extract_frames


def test_load_manifest(word3_file):
    scene = load(word3_file)
    assert scene.manifest.format == "3word"
    assert scene.manifest.frame_count == 3
    assert scene.manifest.device_model == "TestPhone"
    assert scene.manifest.gps_reference.lat == 31.23


def test_load_calibration(word3_file):
    scene = load(word3_file)
    assert scene.calibration is not None
    assert scene.calibration.fx == 500.0
    assert scene.calibration.has_intrinsics


def test_load_frames(word3_file):
    scene = load(word3_file)
    assert [n for n, _ in scene.frame_files] == ["000000.jpg", "000001.jpg", "000002.jpg"]
    data = scene.frame("000001.jpg")
    assert data[:2] == b"\xff\xd8"  # JPEG magic


def test_load_metadata(word3_file):
    scene = load(word3_file)
    assert len(scene.metadata) == 3
    assert scene.metadata[1].capture_utc_ms == 1755684000900


def test_load_sensors(word3_file):
    scene = load(word3_file)
    assert "gyro" in scene.sensor_csvs
    utc, values = scene.sensor_csvs["gyro"][0]
    assert utc == 1755684000000
    assert values == [0.1, 0.2, 0.3]


def test_load_missing_manifest(tmp_path):
    bad = tmp_path / "bad.3word"
    import zipfile
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("frames/000000.jpg", b"\xff\xd8")
    with pytest.raises(Word3Error, match="manifest"):
        load(bad)


def test_load_no_frames(tmp_path):
    bad = tmp_path / "noframes.3word"
    import zipfile
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("manifest.json", json.dumps({"frame_count": 0}))
    with pytest.raises(Word3Error, match="帧"):
        load(bad)


def test_load_sensorless(tmp_path):
    from tests.conftest import make_word3
    path = make_word3(tmp_path, sensors=False)
    scene = load(path)
    assert scene.sensor_csvs == {}


def test_extract_frames(word3_file, tmp_path):
    out = tmp_path / "out"
    files = extract_frames(word3_file, out)
    assert len(files) == 3
    assert (out / "000000.jpg").is_file()