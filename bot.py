import os
import json
import re
import time
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# ==========================================
# НАСТРОЙКИ
# ==========================================

load_dotenv()

WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
SITE_URL = "https://gta5masterlist.ru/projects/gta5rp"

UPDATE_INTERVAL = 60
MESSAGE_ID_FILE = "message_id.txt"
STATE_FILE = "previous_stats.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    )
}

if not WEBHOOK_URL:
    raise RuntimeError(
        "Не найден DISCORD_WEBHOOK_URL. "
        "Проверь файл .env"
    )


# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================

def clean_number(value):
    if not value:
        return 0

    value = value.replace("\xa0", " ")
    value = re.sub(r"[^\d]", "", value)

    return int(value) if value else 0


def format_number(number):
    return f"{number:,}".replace(",", " ")


def load_message_id():
    try:
        with open(
            MESSAGE_ID_FILE,
            "r",
            encoding="utf-8"
        ) as file:
            return file.read().strip() or None

    except FileNotFoundError:
        return None
def save_message_id(message_id):
    with open(
        MESSAGE_ID_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        file.write(str(message_id))
def load_previous_stats():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except:
        return {
            "total_online": None,
            "servers": {}
        }


def save_previous_stats(data):
    state = {
        "total_online": data["total_online"],
        "servers": {
            server["name"]: server["online"]
            for server in data["servers"]
        }
    }

    with open(STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2)

# ==========================================
# ПОЛУЧЕНИЕ ДАННЫХ С САЙТА
# ==========================================

def get_data():

    response = requests.get(
        SITE_URL,
        headers=HEADERS,
        timeout=20
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    text = soup.get_text(
        " ",
        strip=True
    )

    # --------------------------------------
    # ОБЩИЙ ОНЛАЙН
    # --------------------------------------

    total_online = 0

    patterns = [
        r"(\d[\d\s\xa0]*)\s*игроков\s*Онлайн сейчас",
        r"Онлайн сейчас\s*(\d[\d\s\xa0]*)",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:
            total_online = clean_number(
                match.group(1)
            )
            break

    # --------------------------------------
    # КОЛИЧЕСТВО СЕРВЕРОВ
    # --------------------------------------

    servers_count = 0

    match = re.search(
        r"(\d+)\s*серверов",
        text,
        re.IGNORECASE
    )

    if match:
        servers_count = int(
            match.group(1)
        )

    # --------------------------------------
    # ПИК
    # --------------------------------------

    today_peak = 0

    match = re.search(
        r"Пик сегодня\s*(\d[\d\s\xa0]*)",
        text,
        re.IGNORECASE
    )

    if match:
        today_peak = clean_number(
            match.group(1)
        )

    # --------------------------------------
    # РЕКОРД
    # --------------------------------------

    record = 0

    match = re.search(
        r"Рекорд за всё время\s*(\d[\d\s\xa0]*)",
        text,
        re.IGNORECASE
    )

    if match:
        record = clean_number(
            match.group(1)
        )

    # --------------------------------------
    # СЕРВЕРЫ
    # --------------------------------------

    servers = []

    server_links = soup.select(
        'a[href*="/servers/gta5rp/"]'
    )

    seen = set()

    for link in server_links:

        href = link.get("href", "")

        if href in seen:
            continue

        seen.add(href)

        name = link.get_text(
            " ",
            strip=True
        )

        name = re.sub(
            r"Просмотр графика онлайна.*",
            "",
            name,
            flags=re.IGNORECASE
        ).strip()

        if not name:
            continue

        link_text = link.get_text(
            " ",
            strip=True
        )

        online = None

        match = re.search(
            r"(\d[\d\s\xa0]*)\s*игрок",
            link_text,
            re.IGNORECASE
        )

        if match:
            online = clean_number(
                match.group(1)
            )

        # Если внутри ссылки числа нет,
        # смотрим родительский блок.

        if online is None:

            parent = link.parent

            if parent:

                parent_text = parent.get_text(
                    " ",
                    strip=True
                )

                match = re.search(
                    r"(\d[\d\s\xa0]*)\s*игрок",
                    parent_text,
                    re.IGNORECASE
                )

                if match:
                    online = clean_number(
                        match.group(1)
                    )

        if online is None:
            online = 0

        servers.append({
            "name": name,
            "online": online
        })

    if servers_count:
        servers = servers[:servers_count]

    return {
        "total_online": total_online,
        "servers_count": servers_count,
        "today_peak": today_peak,
        "record": record,
        "servers": servers
    }


# ==========================================
# СОЗДАНИЕ EMBED
# ==========================================

def build_embeds(data):

    embeds = []
previous = load_previous_stats()

previous_total = previous["total_online"]

if previous_total is None:
    total_change = "➖ первый запуск"
else:
    diff = data["total_online"] - previous_total

    if diff > 0:
        total_change = f"🟢 +{format_number(diff)}"
    elif diff < 0:
        total_change = f"🔴 {format_number(diff)}"
    else:
        total_change = "⚪ 0"
    # ======================================
    # EMBED №1 — СТАТИСТИКА
    # ======================================

    description = (
f"👥 **Онлайн сейчас:** `{format_number(data['total_online'])}`\n"
f"📊 **За 5 минут:** `{total_change}`\n\n"

        f"🖥️ **Серверов:** "
        f"`{data['servers_count']}`\n\n"

        f"📈 **Пик сегодня:** "
        f"`{format_number(data['today_peak'])}`\n\n"

        f"🏆 **Рекорд:** "
        f"`{format_number(data['record'])}`\n\n"

        f"🌐 [Открыть GTA5MasterList]({SITE_URL})"
    )

    embeds.append({
        "title": "🎮 GTA 5 RP — статистика",
        "description": description,
        "color": 0x5865F2,
        "url": SITE_URL,
        "footer": {
            "text": "GTA5MasterList • обновление каждые 5 минут"
        }
    })

    # ======================================
    # ДЕЛИМ СЕРВЕРЫ НА 2 EMBED
    # ======================================

    servers = data["servers"]

    middle = (len(servers) + 1) // 2

    groups = [
        servers[:middle],
        servers[middle:]
    ]

    for index, group in enumerate(
        groups,
        start=1
    ):

        if not group:
            continue

        lines = []

        for server in group:

            name = server["name"]
            online = server["online"]

            if online > 0:
                status = "🟢"
            else:
                status = "🔴"

           previous_online = previous["servers"].get(name)

if previous_online is None:
    delta = "новый"
else:
    diff = online - previous_online

    if diff > 0:
        delta = f"+{format_number(diff)}"
    elif diff < 0:
        delta = format_number(diff)
    else:
        delta = "0"

lines.append(
    f"{status} **{name}** — `{format_number(online)}` игроков ({delta})"
)

        embeds.append({
            "title": (
                f"🖥️ GTA5RP — сервера "
                f"{index}/2"
            ),
            "description": "\n".join(lines),
            "color": 0x2ECC71,
            "footer": {
                "text": (
                    f"Серверов: "
                    f"{data['servers_count']}"
                )
            }
        })

    return embeds


# ==========================================
# DISCORD
# ==========================================

def create_message(embeds):

    response = requests.post(
        WEBHOOK_URL + "?wait=true",
        json={
            "username": "GTA5RP Monitor",
            "embeds": embeds
        },
        timeout=20
    )

    response.raise_for_status()

    return response.json()["id"]


def update_message(
    message_id,
    embeds
):

    url = (
        f"{WEBHOOK_URL}"
        f"/messages/{message_id}"
    )

    response = requests.patch(
        url,
        json={
            "username": "GTA5RP Monitor",
            "embeds": embeds
        },
        timeout=20
    )

    response.raise_for_status()


# ==========================================
# ОСНОВНОЙ ЦИКЛ
# ==========================================

def main():

    message_id = load_message_id()

    print()
    print("=" * 55)
    print(" GTA5RP → DISCORD MONITOR")
    print("=" * 55)
    print()

    try:
        print("Получаю данные с сайта...")

        data = get_data()

        print(f"Общий онлайн: {format_number(data['total_online'])}")
        print(f"Серверов найдено: {len(data['servers'])}")

        for server in data["servers"]:
            print(f"  {server['name']} — {server['online']}")

        embeds = build_embeds(data)

        if message_id is None:
            print()
            print("Создаю сообщение Discord...")
            message_id = create_message(embeds)
            save_message_id(message_id)
            save_previous_stats(data)      # ← ВСТАВИТЬ СЮДА
            print("✓ Сообщение создано")
        else:
            print()
            print("Обновляю сообщение Discord...")
            try:
              update_message(message_id, embeds)
              save_previous_stats(data)      # ← ВСТАВИТЬ СЮДА
              print("✓ Сообщение обновлено")
            except requests.HTTPError as error:
                if error.response is not None and error.response.status_code == 404:
                    print("Сообщение удалено. Создаю новое...")
                    message_id = create_message(embeds)
                    save_message_id(message_id)
                    save_previous_stats(data)      # ← ВСТАВИТЬ СЮДА
                else:
                    raise

    except Exception as error:
        print()
        print("❌ ОШИБКА:")
        print(error)

if __name__ == "__main__":
    main()

