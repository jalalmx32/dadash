import base64, json, os
from datetime import datetime, date
from urllib.parse import quote
from flask import Flask, Response, abort, request, render_template
import segno

app = Flask(__name__)
TOKEN = os.environ.get("SUB_TOKEN", "change-me")
GB = 1024 ** 3
FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
ZERO = "00000000-0000-0000-0000-000000000000"


def fa(v):
    return str(v).translate(FA)


def load():
    with open(os.path.join(os.path.dirname(__file__), "data.json"), encoding="utf-8") as f:
        return json.load(f)


def wants_html():
    ua = request.headers.get("User-Agent", "")
    return "text/html" in request.headers.get("Accept", "") and "Mozilla" in ua


UNL = {"", "0", "unlimited", "نامحدود", "none", "null", "inf"}


def is_unl(v):
    return v is None or str(v).strip().lower() in UNL


def info_configs(used, total, pct, days, expire):
    """کانفیگ‌های نمایشی که مصرف و اعتبار را داخل خود کلاینت نشان می‌دهند"""
    t1 = f"📊 مصرف: {used:g} گیگ (نامحدود)" if total is None else f"📊 مصرف: {used:g} از {total:g} گیگ ({pct}%)"
    t2 = "⏳ اعتبار: نامحدود" if days is None else f"⏳ اعتبار: {fa(days)} روز مانده (تا {expire})"
    mk = lambda i, t: {
        "title": t,
        "url": f"vless://{ZERO}@0.0.0.0:{i}?encryption=none&security=none&type=tcp#{quote(t)}",
    }
    return [mk(1, t1), mk(2, t2)]


@app.route("/")
def home():
    return "ok"


@app.route("/sub/<token>")
def sub(token):
    if token != TOKEN:
        abort(404)
    d = load()
    unl_exp, unl_vol = is_unl(d.get("expire")), is_unl(d.get("total_gb"))
    exp = None if unl_exp else datetime.strptime(d["expire"], "%Y-%m-%d").date()
    days = None if unl_exp else max((exp - date.today()).days, 0)
    expired = (not unl_exp) and exp < date.today()
    used = round(float(d.get("used_gb", 0)), 2)
    total = None if unl_vol else float(d["total_gb"])
    pct = 0 if unl_vol else min(100, round(used / total * 100))
    infos = info_configs(used, total, pct, days, d["expire"])
    all_links = "\n".join([c["url"] for c in infos] + [c["url"] for c in d["configs"]])

    if not wants_html():
        r = Response(base64.b64encode(all_links.encode()).decode(), mimetype="text/plain")
        ui = f"upload=0; download={int(used*GB)}"
        if total is not None:
            ui += f"; total={int(total*GB)}"
        if exp is not None:
            ui += f"; expire={int(datetime.combine(exp, datetime.min.time()).timestamp())}"
        r.headers["Subscription-Userinfo"] = ui
        r.headers["Profile-Title"] = d["name"]
        r.headers["Profile-Update-Interval"] = "12"
        return r

    host = request.headers.get("X-Forwarded-Host", request.host)
    link = f"https://{host}/sub/{token}"
    if expired:
        status, cls = "منقضی شده", "danger"
    elif days is not None and days <= 3:
        status, cls = "نزدیک انقضا", "warn"
    else:
        status, cls = "فعال", ""
    return render_template(
        "page.html", d=d, link=link, host=host, qr=segno.make(link).svg_data_uri(scale=8, border=1),
        pct=pct, status=status, cls=cls, unl_exp=unl_exp,
        used_s=f"{used:.2f}",
        total_label="نامحدود" if unl_vol else f"{total:g} GB",
        usage_note="حجم نامحدود" if unl_vol else f"{fa(pct)}٪ مصرف شده — {fa(f'{max(total-used,0):.2f}')} گیگابایت باقی‌مانده",
        days_main="∞" if unl_exp else fa(days),
        days_caption="بدون تاریخ انقضا" if unl_exp else "روز تا انقضای دوره",
        exp_label="UNLIMITED" if unl_exp else d["expire"],
        info_configs=infos, all_links=all_links,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
