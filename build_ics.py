#!/usr/bin/env python3
"""schedule.json から購読用の kick.ics を生成する。

- 版（versions）ごとに毎週繰り返しの予定を作る。
- 次の版がある場合、前の版の予定は次の版の開始日前日で打ち切る（過去分は残る）。
- UID は「版の開始日・曜日・開始時刻・クラス名」から決まるので、再生成しても同じ予定は同じ UID になる。
使い方: python3 build_ics.py [schedule.json] [kick.ics]
"""
import datetime as dt
import hashlib
import json
import sys

DAY_INDEX = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
CAL_NAME = "キック（クロスポイント吉祥寺）"


def esc(text: str) -> str:
    return (text.replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\n", "\\n"))


def fold(line: str) -> str:
    """RFC 5545: 1行75オクテット以内に折り返す（UTF-8の文字境界を守る）。"""
    out, cur = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        limit = 75 if not out else 74
        if len(cur) + len(b) > limit:
            out.append(cur.decode("utf-8"))
            cur = b""
        cur += b
    out.append(cur.decode("utf-8"))
    return "\r\n ".join(out)


def first_on_or_after(start: dt.date, weekday: int) -> dt.date:
    return start + dt.timedelta(days=(weekday - start.weekday()) % 7)


def build(data: dict) -> str:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//kick-schedule//JA",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{esc(CAL_NAME)}",
        "X-WR-TIMEZONE:Asia/Tokyo",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
        "X-PUBLISHED-TTL:PT12H",
        "BEGIN:VTIMEZONE",
        "TZID:Asia/Tokyo",
        "BEGIN:STANDARD",
        "DTSTART:19700101T000000",
        "TZOFFSETFROM:+0900",
        "TZOFFSETTO:+0900",
        "TZNAME:JST",
        "END:STANDARD",
        "END:VTIMEZONE",
    ]
    versions = sorted(data["versions"], key=lambda v: v["valid_from"])
    for i, ver in enumerate(versions):
        v_from = dt.date.fromisoformat(ver["valid_from"])
        until = None
        if i + 1 < len(versions):
            nxt = dt.date.fromisoformat(versions[i + 1]["valid_from"])
            until = nxt - dt.timedelta(days=1)
        for c in ver["classes"]:
            day = first_on_or_after(v_from, DAY_INDEX[c["day"]])
            if until and day > until:
                continue
            sh, sm = map(int, c["start"].split(":"))
            eh, em = map(int, c["end"].split(":"))
            dtstart = dt.datetime(day.year, day.month, day.day, sh, sm)
            dtend = dt.datetime(day.year, day.month, day.day, eh, em)
            key = f'{ver["valid_from"]}|{c["day"]}|{c["start"]}|{c["name"]}|{c["floor"]}'
            uid = hashlib.sha1(key.encode()).hexdigest()[:20] + "@kick-schedule"
            rrule = f'RRULE:FREQ=WEEKLY;BYDAY={c["day"]}'
            if until:
                rrule += f';UNTIL={until.strftime("%Y%m%d")}T235959Z'
            desc = [f'場所：{c["floor"]}']
            if c.get("instructor"):
                desc.append(f'担当：{c["instructor"]}（画像からの読み取り）')
            if c.get("trial"):
                desc.append("★体験可クラス")
            if c.get("time_estimated"):
                desc.append("※時間割表に時刻の記載がないため、前後の枠から推定した時刻です")
            desc.append(f'スケジュール版：{ver["label"]}')
            desc.append(f'出典：{data["source_page"]}')
            lines += [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{stamp}",
                f'DTSTART;TZID=Asia/Tokyo:{dtstart.strftime("%Y%m%dT%H%M%S")}',
                f'DTEND;TZID=Asia/Tokyo:{dtend.strftime("%Y%m%dT%H%M%S")}',
                rrule,
                f'SUMMARY:{esc(c["name"] + "（" + c["floor"] + "）")}',
                f'LOCATION:{esc(data["location"])}',
                f'DESCRIPTION:{esc(chr(10).join(desc))}',
                "TRANSP:TRANSPARENT",
                "END:VEVENT",
            ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(fold(l) for l in lines) + "\r\n"


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "schedule.json"
    dst = sys.argv[2] if len(sys.argv) > 2 else "kick.ics"
    with open(src, encoding="utf-8") as f:
        data = json.load(f)
    with open(dst, "w", encoding="utf-8", newline="") as f:
        f.write(build(data))
    print(f"wrote {dst}")
