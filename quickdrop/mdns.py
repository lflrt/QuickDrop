"""mDNS 发布/注销 `quickdrop.local`（见 docs/architecture.md）。

作用：解决电脑 IP 变化导致手机书签失效的问题 —— 手机可用
`http://quickdrop.local:{port}/?token=xxx` 固定访问。

- publish(hostname, port, ip) -> (Zeroconf, ServiceInfo) 句柄
- unpublish(handle) 幂等注销并关闭

⚠️ 需要局域网支持组播（multicast）；部分路由器/网络会屏蔽 mDNS，此时失败由调用方降级为 IP 访问。
"""

from __future__ import annotations

import socket


def publish(hostname: str, port: int, ip: str):
    """发布 A 记录（hostname→ip）与 `_http._tcp` 服务。失败会抛异常，由调用方处理。"""
    from zeroconf import ServiceInfo, Zeroconf

    zc = Zeroconf()
    info = ServiceInfo(
        "_http._tcp.local.",
        "QuickDrop._http._tcp.local.",
        addresses=[socket.inet_aton(ip)],
        port=port,
        properties={"path": "/"},
        server=f"{hostname}.",  # 使 hostname（如 quickdrop.local）可解析
    )
    zc.register_service(info)
    return zc, info


def unpublish(handle) -> None:
    """注销 mDNS 服务并关闭；幂等、吞异常（用于关窗/退出）。"""
    if not handle:
        return
    zc, info = handle
    try:
        if info is not None:
            zc.unregister_service(info)
    except Exception:
        pass
    try:
        zc.close()
    except Exception:
        pass
