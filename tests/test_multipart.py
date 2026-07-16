#!/usr/bin/env python3
"""Contract tests for SUPER-I multipart uploads without network access."""

import json
import os
import re
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import superi_app as app
import superi_web as web


class _Response:
    status = 201

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return b'{"success": true, "data": {"id": 1}}'


class MultipartContractTests(unittest.TestCase):
    def test_tegangan_uses_two_ordered_files_and_clean_json(self):
        payload = {
            "trafoId": 123,
            "periode": 2,
            "fotoHV": {"date": "2026-07-17T02:10:00.000Z"},
            "fotoMV": {"date": "2026-07-17T02:10:15.000Z"},
            "_item_name_hint": "TRAFO 1",
        }
        hv_bytes = b"\xff\xd8HV_IMAGE\xff\xd9"
        mv_bytes = b"\xff\xd8MV_IMAGE\xff\xd9"
        captured = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return _Response()

        def fake_jpeg(*_args, **kwargs):
            return hv_bytes if kwargs.get("subtype") == "HV" else mv_bytes

        with patch.object(app, "get_photo_source", return_value="manual"), \
             patch.object(app, "_verify_tegangan_photo_upload", return_value={"ok": True}), \
             patch.object(app.hu, "rand_boundary", return_value="----ContractBoundary"), \
             patch.object(app.hu, "rand_jpeg_bytes", side_effect=fake_jpeg), \
             patch.object(app.hu, "rand_filename", side_effect=lambda _ts, idx, data_type, subtype: f"foto{subtype}_{idx}.jpg"), \
             patch.object(app.hu, "rand_user_agent", return_value="okhttp/4.12.0"), \
             patch.object(app.urllib.request, "urlopen", side_effect=fake_urlopen):
            status, result = app.api_post_multipart(
                "token",
                app.ENDPOINTS["tegangan-trafo"]["input"],
                payload,
                app.DUMMY_JPEG,
                "files",
                2,
            )

        self.assertEqual(status, 201)
        self.assertTrue(result["success"])
        self.assertEqual(captured["timeout"], 60)
        self.assertIn("_item_name_hint", payload, "caller payload must not be mutated")

        request = captured["request"]
        body = request.data
        self.assertEqual(request.get_header("Content-type"), "multipart/form-data; boundary=----ContractBoundary")
        self.assertEqual(body.count(b'name="data"'), 1)
        self.assertEqual(body.count(b'name="files"'), 2)
        self.assertNotIn(b"_item_name_hint", body)
        self.assertLess(body.index(hv_bytes), body.index(mv_bytes))
        self.assertRegex(body, rb'name="files"; filename="fotoHV\.jpg"')
        self.assertRegex(body, rb'name="files"; filename="fotoMV\.jpg"')

        match = re.search(rb'name="data"\r\n\r\n(.+?)\r\n--', body, re.DOTALL)
        self.assertIsNotNone(match)
        sent_payload = json.loads(match.group(1))
        self.assertEqual(sent_payload["fotoHV"], payload["fotoHV"])
        self.assertEqual(sent_payload["fotoMV"], payload["fotoMV"])

    def test_verification_reports_missing_voltage_uris(self):
        listed = {
            "data": {
                "items": [{
                    "tegangan": [{
                        "id": 405811,
                        "fotoHV": {"date": "2026-07-17T03:00:00.000Z"},
                        "fotoMV": {"date": "2026-07-17T03:00:10.000Z"},
                    }],
                }],
            },
        }
        payload = {"tahun": 2026, "bulan": 6, "tanggal": 17}
        with patch.object(app, "api_get", return_value=listed), \
             patch.object(app, "load_config", return_value={"gi_id": "222"}):
            result = app._verify_tegangan_photo_upload(
                "token", payload, {"data": {"id": 405811}},
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "URI foto HV/MV tidak dibuat server")

    def test_verification_fetches_both_voltage_images(self):
        listed = {
            "data": {
                "items": [{
                    "tegangan": [{
                        "id": 1,
                        "fotoHV": {"uri": "/media/hv.jpg"},
                        "fotoMV": {"uri": "/media/mv.jpg"},
                    }],
                }],
            },
        }
        image = b"\xff\xd8" + (b"x" * 1200) + b"\xff\xd9"

        class ImageResponse(_Response):
            def read(self):
                return image

        payload = {"tahun": 2026, "bulan": 6, "tanggal": 17}
        with patch.object(app, "api_get", return_value=listed), \
             patch.object(app, "load_config", return_value={"gi_id": "222"}), \
             patch.object(app.urllib.request, "urlopen", return_value=ImageResponse()) as urlopen:
            result = app._verify_tegangan_photo_upload(
                "token", payload, {"data": {"id": 1}},
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["sizes"], {"HV": len(image), "MV": len(image)})
        self.assertEqual(urlopen.call_count, 2)

    def test_verification_retries_until_voltage_record_is_visible(self):
        empty = {"data": {"items": []}}
        listed = {
            "data": {
                "items": [{
                    "tegangan": [{
                        "id": 1,
                        "fotoHV": {"uri": "/media/hv.jpg"},
                        "fotoMV": {"uri": "/media/mv.jpg"},
                    }],
                }],
            },
        }
        image = b"\xff\xd8" + (b"x" * 1200) + b"\xff\xd9"

        class ImageResponse(_Response):
            def read(self):
                return image

        payload = {"tahun": 2026, "bulan": 6, "tanggal": 17}
        with patch.object(app, "api_get", side_effect=[empty, listed]) as api_get, \
             patch.object(app, "load_config", return_value={"gi_id": "222"}), \
             patch.object(app.time, "sleep") as sleep, \
             patch.object(app.urllib.request, "urlopen", return_value=ImageResponse()):
            result = app._verify_tegangan_photo_upload(
                "token", payload, {"data": {"id": 1}},
            )

        self.assertTrue(result["ok"])
        self.assertEqual(api_get.call_count, 2)
        sleep.assert_called_once()

    def test_web_voltage_upload_uses_shared_verified_uploader(self):
        payload = {
            "trafoId": 123,
            "tahun": 2026,
            "bulan": 6,
            "tanggal": 17,
            "fotoHV": {"date": "2026-07-17T02:10:00.000Z"},
            "fotoMV": {"date": "2026-07-17T02:10:15.000Z"},
        }
        expected = {
            "success": True,
            "data": {"id": 1},
            "_photo_upload": {"ok": True},
        }

        with patch.object(app, "api_post_multipart", return_value=(201, expected)) as shared:
            status, result = web.api_post_multipart(
                "token",
                app.ENDPOINTS["tegangan-trafo"]["input"],
                payload,
                app.DUMMY_JPEG,
                "files",
                2,
                item_name="TRAFO 1",
            )

        self.assertEqual((status, result), (201, expected))
        shared.assert_called_once_with(
            "token",
            app.ENDPOINTS["tegangan-trafo"]["input"],
            payload,
            app.DUMMY_JPEG,
            "files",
            2,
            item_name="TRAFO 1",
        )

    def test_server_side_voltage_filenames_remain_humanized(self):
        """Humanized names remain available for storage; transport uses APK names."""
        hv = app.hu.rand_filename(
            "2026-07-17T02:10:00.000Z", 0, "tegangan-trafo", "HV"
        )
        mv = app.hu.rand_filename(
            "2026-07-17T02:10:15.000Z", 1, "tegangan-trafo", "MV"
        )

        self.assertRegex(hv, r"^fotoHV_2026-07-17_[0-9a-f]+\.jpg$")
        self.assertRegex(mv, r"^fotoMV_2026-07-17_[0-9a-f]+\.jpg$")
        self.assertNotEqual(hv, "fotoHV.jpg")
        self.assertNotEqual(mv, "fotoMV.jpg")


if __name__ == "__main__":
    unittest.main()
