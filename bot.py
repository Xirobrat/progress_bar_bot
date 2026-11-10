import asyncio
import json
import os
from aiohttp import web
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

load_dotenv()

API_TOKEN = os.getenv("BOT_TOKEN")
DATA_FILE = "goals_data.json"

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# --- МИКРО ВЕБ-СЕРВЕР ДЛЯ RENDER ---
async def handle_ping(request):
    return web.Response(text="Bot is running!")


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# --- РАБОТА С ДАННЫМИ ---
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    # Структура по умолчанию
    return {
        "active_goal": "guitar",
        "goals": {
            "guitar": {
                "name": "Cort KX100 (Iron Oxide)",
                "target": 10000,
                "current": 0,
            }
        },
        "tasks": [],  # Мини-цели/заметки по заработку
    }


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def render_bar(current, target, length=10):
    percent = min(1.0, max(0.0, current / target))
    filled = int(length * percent)
    bar = "█" * filled + "░" * (length - filled)
    return f"[{bar}] {percent * 100:.1f}%\nСобрано: {current:,} / {target:,} ₴".replace(
        ",", " "
    )


# --- КОМАНДЫ ---


@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "🎸 **Бот-накопитель v2.0 (Гривны ₴)**\n\n"
        "**Основное:**\n"
        "• `/progress` — Прогресс текущей цели\n"
        "• `/add <сумма>` — Пополнить копилку (напр: `/add 500`)\n"
        "• `/sub <сумма>` — Снять из копилки (напр: `/sub 200`)\n\n"
        "**Управление целями:**\n"
        "• `/goals` — Список всех целей\n"
        "• `/set_goal <id>` — Переключить активную цель\n"
        "• `/add_goal <id> <название> <сумма>` — Создать цель\n\n"
        "**Заметки / Мини-цели по заработку:**\n"
        "• `/tasks` — Список задач по заработку\n"
        "• `/add_task <текст>` — Добавить источник заработка\n"
        "• `/done_task <номер>` — Отметить выполненной",
        parse_mode="Markdown",
    )


# --- ПОПОЛНЕНИЕ И СНЯТИЕ ---


@dp.message(Command("add"))
async def cmd_add(message: Message, command: CommandObject):
    if not command.args or not command.args.isdigit():
        await message.answer("⚠️ Пиши сумму цифрами, например: `/add 500`", parse_mode="Markdown")
        return

    val = int(command.args)
    data = load_data()
    active_id = data["active_goal"]

    if active_id not in data["goals"]:
        await message.answer("⚠️ Сначала выбери или создай цель через `/goals`")
        return

    data["goals"][active_id]["current"] += val
    save_data(data)

    goal = data["goals"][active_id]
    bar = render_bar(goal["current"], goal["target"])
    await message.answer(
        f"✅ **+ {val} ₴** в копилку «{goal['name']}»!\n\n{bar}",
        parse_mode="Markdown",
    )


@dp.message(Command("sub"))
async def cmd_sub(message: Message, command: CommandObject):
    if not command.args or not command.args.isdigit():
        await message.answer("⚠️ Пиши сумму цифрами, например: `/sub 200`", parse_mode="Markdown")
        return

    val = int(command.args)
    data = load_data()
    active_id = data["active_goal"]

    if active_id not in data["goals"]:
        await message.answer("⚠️ Нет активной цели!")
        return

    data["goals"][active_id]["current"] = max(
        0, data["goals"][active_id]["current"] - val
    )
    save_data(data)

    goal = data["goals"][active_id]
    bar = render_bar(goal["current"], goal["target"])
    await message.answer(
        f"💸 **- {val} ₴** из копилки «{goal['name']}».\n\n{bar}",
        parse_mode="Markdown",
    )


@dp.message(Command("progress"))
async def cmd_progress(message: Message):
    data = load_data()
    active_id = data["active_goal"]

    if active_id not in data["goals"]:
        await message.answer("🎯 У тебя пока нет активных целей. Добавь через `/add_goal`")
        return

    goal = data["goals"][active_id]
    bar = render_bar(goal["current"], goal["target"])
    await message.answer(
        f"🎯 **Текущая цель:** {goal['name']}\n\n{bar}", parse_mode="Markdown"
    )


# --- РАБОТА С МУЛЬТИ-ЦЕЛЯМИ ---


@dp.message(Command("goals"))
async def cmd_goals(message: Message):
    data = load_data()
    if not data["goals"]:
        await message.answer("Список целей пуст. Добавь: `/add_goal guitar Гитара 10000`")
        return

    text = "📋 **Твои цели:**\n\n"
    for gid, g in data["goals"].items():
        active_mark = "⭐ (Активна)" if gid == data["active_goal"] else ""
        text += f"• `{gid}`: **{g['name']}** — {g['current']:,} / {g['target']:,} ₴ {active_mark}\n".replace(
            ",", " "
        )

    text += "\nПереключить цель: `/set_goal <id>`"
    await message.answer(text, parse_mode="Markdown")


@dp.message(Command("add_goal"))
async def cmd_add_goal(message: Message, command: CommandObject):
    # Пример: /add_goal pedal Педаль_эффектов 3500
    if not command.args:
        await message.answer(
            "⚠️ Формат: `/add_goal <id_без_пробелов> <Название> <Сумма>`\nПример: `/add_goal bike Велик 8000`",
            parse_mode="Markdown",
        )
        return

    parts = command.args.split()
    if len(parts) < 3 or not parts[-1].isdigit():
        await message.answer("⚠️ Укажи ID, Название и Сумму цифрами.")
        return

    gid = parts[0].lower()
    target = int(parts[-1])
    name = " ".join(parts[1:-1])

    data = load_data()
    data["goals"][gid] = {"name": name, "target": target, "current": 0}
    data["active_goal"] = gid  # Сразу делаем её активной
    save_data(data)

    await message.answer(
        f"🎉 Создана новая цель **{name}** на {target:,} ₴! Она выбрана активной.".replace(
            ",", " "
        ),
        parse_mode="Markdown",
    )


@dp.message(Command("set_goal"))
async def cmd_set_goal(message: Message, command: CommandObject):
    if not command.args:
        await message.answer("⚠️ Укажи ID цели. Посмотреть ID целей: `/goals`")
        return

    gid = command.args.strip().lower()
    data = load_data()

    if gid not in data["goals"]:
        await message.answer("❌ Такой цели нет в списке.")
        return

    data["active_goal"] = gid
    save_data(data)
    goal = data["goals"][gid]
    await message.answer(
        f"🎯 Выбрана цель: **{goal['name']}**", parse_mode="Markdown"
    )


# --- ЗАМЕТКИ И МИНИ-ЦЕЛИ ПО ЗАРАБОТКУ ---


@dp.message(Command("add_task"))
async def cmd_add_task(message: Message, command: CommandObject):
    if not command.args:
        await message.answer(
            "⚠️ Напиши задачу. Пример: `/add_task Продать скейт на OLX (+1500 ₴)`",
            parse_mode="Markdown",
        )
        return

    data = load_data()
    data["tasks"].append({"text": command.args, "done": False})
    save_data(data)

    await message.answer("📌 Заметка / мини-цель добавлена в список!")


@dp.message(Command("tasks"))
async def cmd_tasks(message: Message):
    data = load_data()
    tasks = data.get("tasks", [])

    if not tasks:
        await message.answer(
            "📝 Список заметок пуст. Добавь идею по заработку: `/add_task <текст>`"
        )
        return

    text = "💡 **Идеи и мини-цели по заработку:**\n\n"
    for idx, t in enumerate(tasks, 1):
        status = "✅" if t["done"] else "📌"
        strike_start = "~~" if t["done"] else ""
        strike_end = "~~" if t["done"] else ""
        text += f"{idx}. {status} {strike_start}{t['text']}{strike_end}\n"

    text += "\nЧтобы отметить выполненным: `/done_task <номер>`"
    await message.answer(text, parse_mode="Markdown")


@dp.message(Command("done_task"))
async def cmd_done_task(message: Message, command: CommandObject):
    if not command.args or not command.args.isdigit():
        await message.answer("⚠️ Укажи номер задачи из `/tasks`, например: `/done_task 1`")
        return

    idx = int(command.args) - 1
    data = load_data()
    tasks = data.get("tasks", [])

    if idx < 0 or idx >= len(tasks):
        await message.answer("❌ Задачи с таким номером нет.")
        return

    tasks[idx]["done"] = not tasks[idx]["done"]  # Переключаем статус
    save_data(data)

    status_text = "выполнена" if tasks[idx]["done"] else "снова активна"
    await message.answer(f"👍 Задача №{idx+1} отмечена как {status_text}!")


async def main():
    await dp.start_polling(bot)


async def main():
    await start_web_server()  # Запускаем порт для Render
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
