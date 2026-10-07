import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote
from datetime import datetime
from email.utils import parsedate_to_datetime, format_datetime
import hashlib


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

    except Exception:
        old_items = {}


# --------------------------------------------------
# Google News RSS取得
# --------------------------------------------------

print("取得URL:")
print(GOOGLE_NEWS_RSS)
print()

response = requests.get(
    GOOGLE_NEWS_RSS,
    headers=HEADERS,
    timeout=30
)

print("HTTP:", response.status_code)

response.raise_for_status()

root = ET.fromstring(response.content)

google_items = root.findall("./channel/item")

print(
    "Google News取得件数:",
    len(google_items),
    "件"
)

print()


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

    source_element = item.find("source")

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
# --------------------------------------------------

tree = ET.ElementTree(rss)

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