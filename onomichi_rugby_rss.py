import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote
from datetime import datetime
from email.utils import parsedate_to_datetime
import hashlib
import time


# --------------------------------------------------
# 設定
# --------------------------------------------------

QUERY = "尾道 ラグビー"

GOOGLE_NEWS_RSS = (
    "https://news.google.com/rss/search"
    f"?q={quote(QUERY)}"
    "&hl=ja"
    "&gl=JP"
    "&ceid=JP:ja"
)

OUTPUT = Path(__file__).parent / "onomichi_rugby.xml"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/154.0.0.0 Safari/537.36"
    )
}


# --------------------------------------------------
# 既存RSSを読み込む
# --------------------------------------------------

old_items = {}

if OUTPUT.exists():
    try:
        old_tree = ET.parse(OUTPUT)

        for item in old_tree.getroot().findall("./channel/item"):

            guid = item.findtext("guid", "")

            if guid:
                old_items[guid] = {
                    "title": item.findtext("title", ""),
                    "link": item.findtext("link", ""),
                    "description": item.findtext(
                        "description",
                        ""
                    ),
                    "pubDate": item.findtext(
                        "pubDate",
                        ""
                    ),
                    "guid": guid,
                }

    except Exception as e:
        print("既存RSS読み込みエラー:", e)
        print("安全のため今回は更新しません。")
        raise SystemExit(0)


print("既存RSS件数:", len(old_items))


# --------------------------------------------------
# Google News RSS取得
#
# 503・タイムアウト等の場合は少し待って再試行。
# それでも取得できなければ既存RSSを維持して正常終了。
# --------------------------------------------------

print("取得URL:")
print(GOOGLE_NEWS_RSS)
print()

response = None

MAX_RETRIES = 3

for attempt in range(1, MAX_RETRIES + 1):

    try:
        print(
            f"Google News取得 "
            f"{attempt}/{MAX_RETRIES}"
        )

        response = requests.get(
            GOOGLE_NEWS_RSS,
            headers=HEADERS,
            timeout=30
        )

        print(
            "HTTP:",
            response.status_code
        )

        response.raise_for_status()

        # 正常取得できたので再試行終了
        break

    except requests.RequestException as e:

        print(
            "取得失敗:",
            e
        )

        response = None

        if attempt < MAX_RETRIES:
            print(
                "10秒待って再試行します。"
            )
            time.sleep(10)


# --------------------------------------------------
# 3回とも失敗した場合
# --------------------------------------------------

if response is None:

    print()
    print(
        "Google Newsを取得できませんでした。"
    )
    print(
        "今回はRSSを更新しません。"
    )
    print(
        "既存の onomichi_rugby.xml を"
        "そのまま維持します。"
    )
    print(
        "次回の定期実行で再度確認します。"
    )

    # exit code 0 で正常終了
    raise SystemExit(0)


# --------------------------------------------------
# Google News XML解析
# --------------------------------------------------

try:
    root = ET.fromstring(
        response.content
    )

except ET.ParseError as e:

    print()
    print(
        "Google NewsのXML解析に失敗しました:",
        e
    )
    print(
        "今回はRSSを更新しません。"
    )
    print(
        "既存の onomichi_rugby.xml を"
        "そのまま維持します。"
    )

    raise SystemExit(0)


google_items = root.findall(
    "./channel/item"
)

print(
    "Google News取得件数:",
    len(google_items),
    "件"
)

print()


# --------------------------------------------------
# 0件だった場合
#
# Google News側の一時的な異常や
# 仕様変更の可能性があるため、
# 空RSSで既存XMLを上書きしない
# --------------------------------------------------

if len(google_items) == 0:

    print(
        "Google Newsの記事が0件でした。"
    )
    print(
        "異常取得の可能性があるため、"
        "今回はRSSを更新しません。"
    )
    print(
        "既存の onomichi_rugby.xml を"
        "そのまま維持します。"
    )

    raise SystemExit(0)


# --------------------------------------------------
# 記事を自前RSS用に変換
# --------------------------------------------------

current_items = []
seen = set()


for item in google_items:

    title = item.findtext(
        "title",
        ""
    ).strip()

    link = item.findtext(
        "link",
        ""
    ).strip()

    pub_date = item.findtext(
        "pubDate",
        ""
    ).strip()

    source_element = item.find(
        "source"
    )

    if source_element is not None:
        source = (
            source_element.text or ""
        ).strip()
    else:
        source = ""


    if not title or not link:
        continue


    # --------------------------------------------------
    # 重複防止
    # --------------------------------------------------

    guid = hashlib.sha256(
        link.encode("utf-8")
    ).hexdigest()

    if guid in seen:
        continue

    seen.add(guid)


    # --------------------------------------------------
    # 説明
    # --------------------------------------------------

    if source:
        description = (
            f"配信元: {source}"
        )
    else:
        description = (
            'Google News「尾道 ラグビー」検索結果'
        )


    current_items.append(
        {
            "title": title,
            "link": link,
            "description": description,
            "pubDate": pub_date,
            "guid": guid,
        }
    )


# --------------------------------------------------
# 有効記事が0件なら更新しない
# --------------------------------------------------

if len(current_items) == 0:

    print(
        "有効な記事を1件も取得できませんでした。"
    )
    print(
        "今回はRSSを更新しません。"
    )
    print(
        "既存の onomichi_rugby.xml を"
        "そのまま維持します。"
    )

    raise SystemExit(0)


# --------------------------------------------------
# 既存RSSと統合
# --------------------------------------------------

all_items = []
seen_guids = set()


for item in current_items:

    if item["guid"] not in seen_guids:
        all_items.append(item)
        seen_guids.add(item["guid"])


for guid, item in old_items.items():

    if guid not in seen_guids:
        all_items.append(item)
        seen_guids.add(guid)


# --------------------------------------------------
# 新しい順に並べる
# --------------------------------------------------

def get_date(item):

    try:
        return parsedate_to_datetime(
            item["pubDate"]
        )

    except Exception:
        return datetime.min.astimezone()


all_items.sort(
    key=get_date,
    reverse=True
)

all_items = all_items[:300]


# --------------------------------------------------
# RSS作成
# --------------------------------------------------

rss = ET.Element(
    "rss",
    version="2.0"
)

channel = ET.SubElement(
    rss,
    "channel"
)

ET.SubElement(
    channel,
    "title"
).text = 'Google News「尾道 ラグビー」'

ET.SubElement(
    channel,
    "link"
).text = GOOGLE_NEWS_RSS

ET.SubElement(
    channel,
    "description"
).text = (
    'Google Newsで「尾道 ラグビー」と'
    "検索した記事を保存するRSS"
)

ET.SubElement(
    channel,
    "language"
).text = "ja"


# --------------------------------------------------
# RSS記事
# --------------------------------------------------

for item in all_items:

    element = ET.SubElement(
        channel,
        "item"
    )

    ET.SubElement(
        element,
        "title"
    ).text = item["title"]

    ET.SubElement(
        element,
        "link"
    ).text = item["link"]

    ET.SubElement(
        element,
        "description"
    ).text = item["description"]

    ET.SubElement(
        element,
        "pubDate"
    ).text = item["pubDate"]

    guid_element = ET.SubElement(
        element,
        "guid"
    )

    guid_element.set(
        "isPermaLink",
        "false"
    )

    guid_element.text = item["guid"]


# --------------------------------------------------
# XML保存
#
# ここまで正常に処理できた場合だけ上書きする
# --------------------------------------------------

tree = ET.ElementTree(
    rss
)

ET.indent(
    tree,
    space="  "
)

tree.write(
    OUTPUT,
    encoding="utf-8",
    xml_declaration=True
)


# --------------------------------------------------
# 結果表示
# --------------------------------------------------

print("RSS作成成功")

print(
    "今回取得:",
    len(current_items),
    "件"
)

print(
    "RSS保存件数:",
    len(all_items),
    "件"
)

print(
    "保存先:",
    OUTPUT
)

print()
print("取得記事:")


for i, item in enumerate(
    current_items,
    start=1
):

    print()
    print(
        f"[{i}] {item['title']}"
    )

    print(
        "    ",
        item["pubDate"]
    )

    print(
        "    ",
        item["description"]
    )

    print(
        "    ",
        item["link"]
    )
