#!/usr/bin/env python3
"""R2 图片上传工具（零依赖，标准库实现 AWS SigV4 签名）。

用法：
    python3 upload-to-r2.py <图片目录或文件> [图片2 ...]

环境变量（从同目录 .env 读取）：
    R2_ACCESS_KEY_ID      32 位 S3 Access Key ID
    R2_SECRET_ACCESS_KEY  对应 Secret
    R2_ACCOUNT_ID         Cloudflare 账户 ID
    R2_BUCKET             桶名
    R2_PUBLIC_DOMAIN      绑定的自定义域名（用于打印可贴 URL）

上传成功后打印每张图的可贴 URL： https://<域名>/<文件名>
"""
import os
import sys
import hashlib
import hmac
import datetime
import urllib.request
import urllib.error

# ---------- 读取 .env（极简解析，不引入第三方库） ----------
def load_env():
    env = {}
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env

ENV = load_env()
ACCESS = ENV.get("R2_ACCESS_KEY_ID", "")
SECRET = ENV.get("R2_SECRET_ACCESS_KEY", "")
ACCT = ENV.get("R2_ACCOUNT_ID", "")
BUCKET = ENV.get("R2_BUCKET", "")
PUBLIC = ENV.get("R2_PUBLIC_DOMAIN", "")

ENDPOINT = f"{ACCT}.r2.cloudflarestorage.com"
REGION = "auto"


def _hmac(key, msg):
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _signing_key(secret, datestamp, region, service):
    k = _hmac(("AWS4" + secret).encode("utf-8"), datestamp)
    k = _hmac(k, region)
    k = _hmac(k, service)
    k = _hmac(k, "aws4_request")
    return k


def upload_file(path):
    key = os.path.basename(path)
    with open(path, "rb") as f:
        body = f.read()
    payload_hash = hashlib.sha256(body).hexdigest()
    t = datetime.datetime.utcnow()
    amz = t.strftime("%Y%m%dT%H%M%SZ")
    ds = t.strftime("%Y%m%d")

    headers = {
        "host": ENDPOINT,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz,
    }
    # 仅在文件有扩展名时推断 content-type
    ctype = "application/octet-stream"
    ext = os.path.splitext(key)[1].lower()
    ctypes = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml",
        ".avif": "image/avif", ".mp4": "video/mp4", ".pdf": "application/pdf",
    }
    if ext in ctypes:
        ctype = ctypes[ext]

    sorted_hdrs = sorted(headers.items())
    canonical_headers = "".join(f"{k}:{v}\n" for k, v in sorted_hdrs)
    signed_headers = ";".join(k for k, _ in sorted_hdrs)
    canonical_request = (
        f"PUT\n/{BUCKET}/{key}\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
    )
    scope = f"{ds}/{REGION}/s3/aws4_request"
    string_to_sign = (
        f"AWS4-HMAC-SHA256\n{amz}\n{scope}\n"
        + hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    )
    signing_key = _signing_key(SECRET, ds, REGION, "s3")
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    authorization = (
        f"AWS4-HMAC-SHA256 Credential={ACCESS}/{scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    url = f"https://{ENDPOINT}/{BUCKET}/{key}"
    req_headers = dict(headers)
    req_headers["Authorization"] = authorization
    req_headers["Content-Type"] = ctype
    req = urllib.request.Request(url, data=body, method="PUT", headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            status = resp.status
    except urllib.error.HTTPError as e:
        status = e.code
        body_err = e.read()[:300]
        print(f"  ✗ {key} 失败 (HTTP {status}): {body_err}")
        return None
    if status in (200, 2000):
        url_pub = f"https://{PUBLIC}/{key}" if PUBLIC else f"https://{ENDPOINT}/{BUCKET}/{key}"
        print(f"  ✓ {key} -> {url_pub}")
        return url_pub
    else:
        print(f"  ✗ {key} 意外状态码 {status}")
        return None


def collect(paths):
    files = []
    for p in paths:
        if os.path.isdir(p):
            for name in sorted(os.listdir(p)):
                if os.path.isfile(os.path.join(p, name)):
                    files.append(os.path.join(p, name))
        elif os.path.isfile(p):
            files.append(p)
    return files


def main():
    if not (ACCESS and SECRET and ACCT and BUCKET):
        print("缺少配置：请检查 scripts/.env 中的 R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY / R2_ACCOUNT_ID / R2_BUCKET")
        sys.exit(1)
    if len(sys.argv) < 2:
        print("用法：python3 upload-to-r2.py <图片目录或文件> [...]")
        sys.exit(1)
    files = collect(sys.argv[1:])
    if not files:
        print("没有找到可上传的文件")
        sys.exit(1)
    print(f"上传 {len(files)} 个文件到桶 {BUCKET} ...")
    ok = 0
    for fp in files:
        if upload_file(fp):
            ok += 1
    print(f"\n完成：{ok}/{len(files)} 成功")


if __name__ == "__main__":
    main()
