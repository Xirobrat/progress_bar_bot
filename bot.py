import asyncio
import json
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("BOT_TOKEN")
DATA_FILE = "goals_data.json"

bot = Bot(token=API_TOKEN)
dp = Dispatcher()


# --- ВЕБ-СЕРВЕР ДЛЯ RENDER (чтобы не падал таймаут) ---
async def handle_ping(request):
    return web.Response(text="Bot is running 24/7!")


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
    return {
        "active_goal": "guitar",
        "goals": {
            "guitar": {
                "name": "Cort KX100 (Iron Oxide)",
                "target": 10000,
                "current": 0,
            }
        },
        "tasks": [],
    }


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def render_bar(current, target, length=10):
    percent = min(1.0, max(0.0, current / target))
    filled = int(length * percent)
    bar = "█" * filled + "░" * (length - filled)
    return f"[{bar}] {current}/{target} ₴ ({percent * 100:.1f}%)"


# --- КОМАНДЫ БОТА ---
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 Привет! Я твой бот для отслеживания финансовых целей.\n\n"
        "📌 **Доступные команды:**\n"
        "• `/progress` — Посмотреть текущий прогресс\n"
        "• `/add <сумма>` — Добавить накопления (напр. `/add 500`)\n"
        "• `/sub <сумма>` — Потратить/списать (напр. `/sub 200`)\n"
        "• `/tasks` — Посмотреть варианты/источники заработка\n"
        "• `/add_task <текст>` — Добавить идею заработка\n"
        "• `/del_task <номер>` — Удалить задачу по номеру"
    )


@dp.message(Command("progress"))
async def cmd_progress(message: Message):
    data = load_data()
    active_id = data.get("active_goal", "guitar")

    if active_id not in data["goals"]:
        await message.answer("❌ Активная цель не найдена!")
        return

    goal = data["goals"][active_id]
    bar = render_bar(goal["current"], goal["target"])
    await message.answer(f"🎯 **Цель:** {goal['name']}\n{bar}")


@dp.message(Command("add"))
async def cmd_add(message: Message, command: CommandObject):
    if not command.args or not command.args.isdigit():
        await message.answer("❌ Укажи сумму числом! Пример: `/add 500`")
        return

    amount = int(command.args)
    data = load_data()
    active_id = data.get("active_goal", "guitar")

    if active_id in data["goals"]:
        data["goals"][active_id]["current"] += amount
        save_data(data)
        goal = data["goals"][active_id]
        bar = render_bar(goal["current"], goal["target"])
        await message.answer(f"✅ Добавлено {amount} ₴!\n\n{bar}")
    else:
        await message.answer("❌ Активная цель не найдена!")


@dp.message(Command("sub"))
async def cmd_sub(message: Message, command: CommandObject):
    if not command.args or not command.args.isdigit():
        await message.answer("❌ Укажи сумму числом! Пример: `/sub 200`")
        return

    amount = int(command.args)
    data = load_data()
    active_id = data.get("active_goal", "guitar")

    if active_id in data["goals"]:
        data["goals"][active_id]["current"] = max(
            0, data["goals"][active_id]["current"] - amount
        )
        save_data(data)
        goal = data["goals"][active_id]
        bar = render_bar(goal["current"], goal["target"])
        await message.answer(f"📉 Списано {amount} ₴!\n\n{bar}")
    else:
        await message.answer("❌ Активная цель не найдена!")


@dp.message(Command("tasks"))
async def cmd_tasks(message: Message):
    data = load_data()
    tasks = data.get("tasks", [])

    if not tasks:
        await message.answer(
            "📝 Список задач пуст. Добавь через `/add_task <текст>`"
        )
        return

    text = "📋 **Источники заработка / Задачи:**\n\n"
    for idx, task in enumerate(tasks, start=1):
        text += f"{idx}. {task}\n"
    await message.answer(text)


@dp.message(Command("add_task"))
async def cmd_add_task(message: Message, command: CommandObject):
    if not command.args:
        await message.answer("❌ Напиши текст задачи! Пример: `/add_task Раздача листовок`")
        return

    data = load_data()
    data.setdefault("tasks", []).append(command.args)
    save_data(data)
    await message.answer(f"✅ Задача «{command.args}» добавлена!")


@dp.message(Command("del_task"))
async def cmd_del_task(message: Message, command: CommandObject):
    if not command.args or not command.args.isdigit():
        await message.answer("❌ Укажи номер задачи числом! Пример: `/del_task 1`")
        return

    idx = int(command.args) - 1
    data = load_data()
    tasks = data.get("tasks", [])

    if 0 <= idx < len(tasks):
        removed = tasks.pop(idx)
        save_data(data)
        await message.answer(f"🗑 Удалена задача: «{removed}»")
    else:
        await message.answer("❌ Задачи с таким номером не существует!")


# --- ГЛАВНАЯ ТОЧКА ВХОДА ---
async def main():
    await start_web_server()
    # Сбрасываем старые зависшие подключения Telegram, чтобы не было ConflictError
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
