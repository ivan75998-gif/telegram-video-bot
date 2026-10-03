```python
import asyncio
import json
import os
from urllib.parse import quote, urljoin

import aiohttp
from bs4 import BeautifulSoup

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = os.getenv("BOT_TOKEN")
SITES_FILE = "sites.json"

bot = Bot(token=TOKEN)
dp = Dispatcher()


# -----------------------------
# Работа со списком сайтов
# -----------------------------

def load_sites():
    try:
        with open(SITES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def save_sites(sites):
    with open(SITES_FILE, "w", encoding="utf-8") as f:
        json.dump(sites, f, ensure_ascii=False, indent=2)


# -----------------------------
# /start
# -----------------------------

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "🎬 <b>Video Search Bot</b>\n\n"
        "Напиши название или ключевое слово видео.\n\n"
        "Команды:\n"
        "/sites — список сайтов\n"
        "/addsite URL — добавить сайт\n"
        "/delsite URL — удалить сайт",
        parse_mode="HTML"
    )


# -----------------------------
# /sites
# -----------------------------

@dp.message(Command("sites"))
async def sites_command(message: Message):
    sites = load_sites()

    if not sites:
        await message.answer("🌐 Сайтов пока нет.")
        return

    text = "🌐 <b>Сайты для поиска:</b>\n\n"

    for site in sites:
        text += f"• {site}\n"

    await message.answer(text, parse_mode="HTML")


# -----------------------------
# /addsite
# -----------------------------

@dp.message(Command("addsite"))
async def add_site(message: Message):
    parts = message.text.split(maxsplit=1)

    if len(parts) < 2:
        await message.answer(
            "Использование:\n"
            "/addsite https://example.com"
        )
        return

    site = parts[1].strip().rstrip("/")

    if not site.startswith(("http://", "https://")):
        await message.answer(
            "❌ Укажи полный адрес сайта, например:\n"
            "/addsite https://example.com"
        )
        return

    sites = load_sites()

    if site in sites:
        await message.answer("Этот сайт уже добавлен.")
        return

    sites.append(site)
    save_sites(sites)

    await message.answer(
        f"✅ Сайт добавлен:\n{site}"
    )


# -----------------------------
# /delsite
# -----------------------------

@dp.message(Command("delsite"))
async def delete_site(message: Message):
    parts = message.text.split(maxsplit=1)

    if len(parts) < 2:
        await message.answer(
            "Использование:\n"
            "/delsite https://example.com"
        )
        return

    site = parts[1].strip().rstrip("/")

    sites = load_sites()

    if site not in sites:
        await message.answer("Такого сайта нет в списке.")
        return

    sites.remove(site)
    save_sites(sites)

    await message.answer(
        f"🗑️ Сайт удалён:\n{site}"
    )


# -----------------------------
# Поиск на одном сайте
# -----------------------------

async def search_site(session, site, query):
    """
    Универсальный пример.

    Важно:
    разные сайты используют разные URL поиска.
    Поэтому для конкретных сайтов может понадобиться
    отдельный адаптер.
    """

    search_url = site + "/search?q=" + quote(query)

    try:
        async with session.get(
            search_url,
            headers={
                "User-Agent": "Mozilla/5.0"
            },
            timeout=aiohttp.ClientTimeout(total=15)
        ) as response:

            if response.status != 200:
                return []

            html = await response.text()

        soup = BeautifulSoup(html, "html.parser")

        results = []

        for link in soup.find_all("a", href=True):

            title = link.get_text(" ", strip=True)

            if not title:
                continue

            url = urljoin(site + "/", link["href"])

            if not url.startswith(("http://", "https://")):
                continue

            image = None

            img = link.find("img")

            if img:
                image = (
                    img.get("src")
                    or img.get("data-src")
                    or img.get("data-lazy-src")
                )

                if image:
                    image = urljoin(url, image)

            results.append({
                "title": title[:200],
                "url": url,
                "image": image
            })

            if len(results) >= 10:
                break

        return results

    except Exception as e:
        print(f"Ошибка {site}: {e}")
        return []


# -----------------------------
# Поиск по всем сайтам
# -----------------------------

async def search_all(query):

    sites = load_sites()

    if not sites:
        return []

    async with aiohttp.ClientSession() as session:

        tasks = [
            search_site(session, site, query)
            for site in sites
        ]

        results = await asyncio.gather(
            *tasks,
            return_exceptions=True
        )

    all_results = []

    for result in results:
        if isinstance(result, list):
            all_results.extend(result)

    return all_results[:20]


# -----------------------------
# Получение поискового запроса
# -----------------------------

@dp.message(F.text)
async def search(message: Message):

    # Команды обрабатываются отдельно
    if message.text.startswith("/"):
        return

    query = message.text.strip()

    if not query:
        return

    await message.answer(
        f"🔎 Ищу:\n<b>{query}</b>\n\n"
        "⏳ Подожди немного...",
        parse_mode="HTML"
    )

    results = await search_all(query)

    if not results:
        await message.answer(
            "😔 Ничего не найдено.\n\n"
            "Проверь сайты командой /sites "
            "или попробуй другой запрос."
        )
        return

    for item in results:

        title = item["title"]
        url = item["url"]
        image = item["image"]

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="▶️ Смотреть",
                        url=url
                    )
                ]
            ]
        )

        text = (
            f"🎬 <b>{title}</b>\n\n"
            f"🔗 {url}"
        )

        try:

            if image:

                await message.answer_photo(
                    photo=image,
                    caption=text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )

            else:

                await message.answer(
                    text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )

        except Exception:

            await message.answer(
                text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )


# -----------------------------
# Запуск
# -----------------------------

async def main():

    if not TOKEN:
        raise RuntimeError(
            "Не задан BOT_TOKEN"
        )

    print("Бот запущен")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
```
