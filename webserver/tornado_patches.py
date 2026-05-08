"""Tornado 兼容性补丁。

集中管理对 tornado 行为的修补，以便在生产、测试、脚本等所有入口
都能一致地应用——也方便单独测试，无需引入 webserver 其他模块（避免
calibre 等重型依赖）。
"""

from __future__ import annotations

import inspect
import logging


# multipart/form-data 子部分只会出现以下两类头部，仅对它们放宽校验，
# 其他 HTTP header 仍走 Tornado 原始的严格 ABNF 验证。
_LENIENT_MULTIPART_HEADERS = ("content-disposition", "content-type")


def patch_tornado_header_validation() -> bool:
    """在 Tornado < 6.5.1 上放宽 multipart 子头部校验，支持 UTF-8 文件名。

    Tornado 6.5.0 在 ``parse_multipart_form_data`` 中将 part 头部
    ``decode("utf-8")`` 成功后，仍用 ``_ABNF.field_value``（仅允许 latin-1
    范围）校验 header value，导致中文 filename 被拒绝。Tornado 6.5.1+ 已通过
    ``_chars_are_bytes=False`` 修复，这里仅作为防御性兜底。

    Returns:
        True 表示已应用 patch；False 表示 Tornado 已含官方修复，跳过。
    """
    from tornado import httputil

    sig = inspect.signature(httputil.HTTPHeaders.add)
    if "_chars_are_bytes" in sig.parameters:
        # Tornado 6.5.1+：官方已修复，避免覆盖正确实现
        return False

    original_add = httputil.HTTPHeaders.add

    def patched_add(self, name, value):
        if name.lower() in _LENIENT_MULTIPART_HEADERS:
            norm_name = httputil._normalize_header(name)
            self._last_key = norm_name
            if norm_name in self:
                self._dict[norm_name] = (
                    httputil.native_str(self[norm_name]) + "," + httputil.native_str(value)
                )
                self._as_list[norm_name].append(value)
            else:
                self[norm_name] = value
            return None
        return original_add(self, name, value)

    httputil.HTTPHeaders.add = patched_add
    logging.info(
        "Patched Tornado HTTPHeaders.add to accept UTF-8 in multipart sub-headers"
    )
    return True


# 导入即生效，确保任何使用本模块的入口（main、测试、脚本）都受保护
patch_tornado_header_validation()
