#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""multipart/form-data 解析回归测试。

直接调用 tornado.httputil.parse_multipart_form_data，不依赖 calibre/handler，
确保 UTF-8（中文）filename 在任何 Tornado 版本下都能被正确解析。

复现的是线上 issue：
    [W ...] 400 POST /api/book/upload ... :
    Invalid body: Invalid multipart/form-data:
    Invalid header value 'form-data; name="ebook"; filename="《纳瓦尔宝典》.pdf"'
"""

import unittest

# 确保兼容性补丁在解析前生效（Tornado < 6.5.1 时通过 monkey patch 修复，
# 6.5.1+ 时为 no-op）
from webserver import tornado_patches  # noqa: F401


class TestMultipartUtf8FilenameParsing(unittest.TestCase):
    def _build_body(self, filename: str, payload: bytes, boundary: bytes) -> bytes:
        disposition = f'Content-Disposition: form-data; name="ebook"; filename="{filename}"\r\n'
        return (
            b"--" + boundary + b"\r\n"
            + disposition.encode("utf-8")
            + b"Content-Type: application/pdf\r\n\r\n"
            + payload + b"\r\n"
            + b"--" + boundary + b"--\r\n"
        )

    def _parse(self, filename: str, payload: bytes = b"%PDF-1.4 fake"):
        from tornado import httputil

        boundary = b"WebKitFormBoundaryX"
        args, files = {}, {}
        httputil.parse_multipart_form_data(
            boundary, self._build_body(filename, payload, boundary), args, files
        )
        return args, files

    def test_chinese_filename_with_brackets(self):
        """精确复现 issue 的文件名：《纳瓦尔宝典》.pdf"""
        _, files = self._parse("《纳瓦尔宝典》.pdf")
        self.assertIn("ebook", files)
        self.assertEqual(files["ebook"][0]["filename"], "《纳瓦尔宝典》.pdf")
        self.assertEqual(files["ebook"][0]["content_type"], "application/pdf")

    def test_chinese_filename_plain(self):
        _, files = self._parse("索恩·德国史.epub")
        self.assertEqual(files["ebook"][0]["filename"], "索恩·德国史.epub")

    def test_ascii_filename_still_works(self):
        _, files = self._parse("book.epub")
        self.assertEqual(files["ebook"][0]["filename"], "book.epub")

    def test_payload_intact(self):
        payload = b"%PDF-1.4\n%binary\xff\xd8\x00 content"
        _, files = self._parse("中文.pdf", payload=payload)
        self.assertEqual(files["ebook"][0]["body"], payload)


class TestPatchVersionAware(unittest.TestCase):
    """补丁应能识别 Tornado 版本并避免覆盖官方修复。"""

    def test_no_op_on_fixed_tornado(self):
        import inspect

        from tornado import httputil

        from webserver.tornado_patches import patch_tornado_header_validation

        sig = inspect.signature(httputil.HTTPHeaders.add)
        if "_chars_are_bytes" in sig.parameters:
            # 6.5.1+：再次调用 patch 应返回 False（无操作）
            self.assertFalse(patch_tornado_header_validation())
        else:
            # 6.5.0：再次调用补丁返回 True；并且 multipart 解析必须能工作
            self.assertTrue(patch_tornado_header_validation())


if __name__ == "__main__":
    unittest.main()
