"""QuickDrop 共享文件管理（见 docs/architecture.md）。

设计原则：用户不需要把文件复制到特定目录，运行时维护一个共享列表。
默认 use_shared_dir=false，列表由拖拽动态添加；源文件消失时 list() 自动剔除。
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets

# 进程级随机盐：让 file_id 不可从路径离线推算。
# 长度保持 8 位十六进制（对外 API 契约：下载链接形如 /api/download/<8位ID>）。
_ID_SALT = secrets.token_bytes(16)


class SharedFiles:
    def __init__(self) -> None:
        self._map: dict[str, str] = {}  # file_id -> absolute_path

    def _make_id(self, path: str) -> str:
        """带盐 HMAC-SHA256 前 8 位。相比无盐 md5(abspath) 不可预测，
        且同一路径在不同进程间不再产生固定 id。"""
        return hmac.new(
            _ID_SALT, os.path.abspath(path).encode("utf-8"), hashlib.sha256
        ).hexdigest()[:8]

    def add(self, path: str) -> str | None:
        path = os.path.abspath(path)
        if not os.path.isfile(path):
            return None
        fid = self._make_id(path)
        self._map[fid] = path
        return fid

    def remove(self, fid: str) -> None:
        self._map.pop(fid, None)

    def list(self) -> list[dict]:
        result: list[dict] = []
        for fid, path in list(self._map.items()):
            if not os.path.isfile(path):
                self._map.pop(fid, None)  # 源文件消失自动剔除
                continue
            stat = os.stat(path)
            result.append(
                {
                    "id": fid,
                    "name": os.path.basename(path),
                    "size": stat.st_size,
                    "mtime": int(stat.st_mtime),
                    "download_url": f"/api/download/{fid}",
                }
            )
        return result

    def get_path(self, fid: str) -> str | None:
        return self._map.get(fid)
