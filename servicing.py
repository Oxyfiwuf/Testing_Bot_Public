# bot.py
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart
import asyncio
import logging
import sys

# Налаштування логування
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

router = Router()

MAINTENANCE_MESSAGE = "Зараз бот на техобслуговуванні, будується розділ 'Екзамен' 🙄"


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(MAINTENANCE_MESSAGE)


@router.message()
async def any_message(message: Message):
    await message.answer(MAINTENANCE_MESSAGE)


async def main():
    # ────── Запитуємо токен у консолі ──────
    print("=" * 50)
    print("Бот у режимі технічного обслуговування")
    print("=" * 50)

    while True:
        token = input("Введи токен бота (або 'exit' для виходу): ").strip()

        if token.lower() == 'exit':
            print("Виходжу...")
            return

        if token:
            break
        else:
            print("Токен не може бути порожнім! Спробуй ще раз.\n")

    print("Запускаю бота...\n")
    # ───────────────────────────────────────

    bot = Bot(token=token)
    dp = Dispatcher()
    dp.include_router(router)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, polling_timeout=20)
    except Exception as e:
        print(f"\nПомилка: {e}")
        print("Можливо, токен неправильний або немає інтернету.")
        input("\nНатисни Enter для виходу...")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nБот зупинений користувачем.")