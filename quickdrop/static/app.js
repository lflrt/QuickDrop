/* QuickDrop 手机端逻辑 —— 原生 JS，无框架 */
(function () {
  "use strict";

  var params = new URLSearchParams(location.search);
  var token = params.get("token") || sessionStorage.getItem("qd_token") || "";
  if (params.get("token")) sessionStorage.setItem("qd_token", params.get("token"));

  function $(id) { return document.getElementById(id); }
  function setMsg(el, text, isErr) {
    if (!el) return;
    el.textContent = text;
    el.className = "msg" + (isErr ? " err" : "");
  }
  function request(path, opts) {
    opts = opts || {};
    opts.headers = Object.assign({}, opts.headers || {}, { "X-Token": token });
    return fetch(path, opts).then(function (r) {
      if (r.status === 403) throw new Error("token 无效或已过期，请重新扫码");
      if (r.status === 413) throw new Error("文件超过大小上限");
      if (!r.ok) throw new Error("请求失败（" + r.status + "）");
      return r;
    });
  }

  function checkConn() {
    fetch("/api/health")
      .then(function (r) { $("conn").textContent = r.ok ? "连接状态：已连接 ✅" : "连接状态：异常"; })
      .catch(function () { $("conn").textContent = "连接状态：已断开 ❌"; });
  }

  function refreshFiles() {
    request("/api/files")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var ul = $("fileList");
        ul.innerHTML = "";
        if (!data.files || !data.files.length) {
          ul.innerHTML = '<li class="muted">暂无共享文件</li>';
          return;
        }
        data.files.forEach(function (f) {
          var li = document.createElement("li");
          var a = document.createElement("a");
          a.className = "dl";
          a.href = f.download_url + "?token=" + encodeURIComponent(token);
          a.textContent = f.name;
          var meta = document.createElement("span");
          meta.className = "muted";
          meta.textContent = (f.size / 1024 / 1024).toFixed(2) + " MB";
          li.appendChild(a);
          li.appendChild(meta);
          ul.appendChild(li);
        });
      })
      .catch(function (e) { setMsg($("uploadMsg"), e.message, true); });
  }

  function upload() {
    var input = $("fileInput");
    if (!input.files || !input.files.length) { setMsg($("uploadMsg"), "请先选择文件", true); return; }
    var fd = new FormData();
    for (var i = 0; i < input.files.length; i++) fd.append("file", input.files[i]);
    var xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/upload");
    xhr.setRequestHeader("X-Token", token);
    var bar = $("progress");
    bar.hidden = false; bar.value = 0;
    xhr.upload.onprogress = function (e) {
      if (e.lengthComputable) bar.value = (e.loaded / e.total) * 100;
    };
    xhr.onload = function () {
      if (xhr.status === 200) {
        var res = {};
        try { res = JSON.parse(xhr.responseText); } catch (e) {}
        setMsg($("uploadMsg"), "上传成功 ✅（" + (res.count || 0) + " 个文件）", false);
        input.value = "";
        refreshFiles();
      } else if (xhr.status === 403) {
        setMsg($("uploadMsg"), "token 无效或已过期", true);
      } else if (xhr.status === 413) {
        setMsg($("uploadMsg"), "文件超过大小上限", true);
      } else {
        setMsg($("uploadMsg"), "上传失败（" + xhr.status + "）", true);
      }
      setTimeout(function () { bar.hidden = true; }, 800);
    };
    xhr.onerror = function () { setMsg($("uploadMsg"), "网络错误，请确认仍连在同一 WiFi", true); bar.hidden = true; };
    setMsg($("uploadMsg"), "上传中…", false);
    xhr.send(fd);
  }

  function sendClip() {
    request("/api/clipboard", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: $("clipText").value })
    })
      .then(function (r) { return r.json().catch(function () { return {}; }); })
      .then(function (d) {
        if (d && d.clipped === false) {
          setMsg($("clipMsg"), "已发送，但电脑剪贴板被其他程序占用；电脑窗口已显示内容，可在窗口点「复制到剪贴板」", true);
        } else {
          setMsg($("clipMsg"), "已发送到电脑 ✅ 可直接 Ctrl+V", false);
        }
      })
      .catch(function (e) { setMsg($("clipMsg"), e.message, true); });
  }

  function getClip() {
    request("/api/clipboard")
      .then(function (r) { return r.json(); })
      .then(function (d) { $("clipText").value = d.text || ""; setMsg($("clipMsg"), "已读取电脑剪贴板", false); })
      .catch(function (e) { setMsg($("clipMsg"), e.message, true); });
  }

  document.addEventListener("DOMContentLoaded", function () {
    $("uploadBtn").addEventListener("click", upload);
    $("refreshBtn").addEventListener("click", refreshFiles);
    $("clipSend").addEventListener("click", sendClip);
    $("clipGet").addEventListener("click", getClip);
    checkConn();
    refreshFiles();
  });
})();
