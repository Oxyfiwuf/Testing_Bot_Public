import asyncpg
import logging
from aiogram import Bot, Dispatcher, F, Router
from dotenv import load_dotenv
import os

# ====================== НАЛАШТУВАННЯ — ОБОВ'ЯЗКОВО через .env на сервері ======================

load_dotenv()  # Завантажуємо змінні з .env файлу

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("Помилка: не знайдено TOKEN в .env файлі!")

ADMIN_ID = list(map(int, os.getenv("ADMIN_ID", "").split(",")))  # наприклад: 123456789,987654321
if not ADMIN_ID:
    raise ValueError("Помилка: не вказано ADMIN_ID в .env")

FORWARD_TO_USER_ID = int(os.getenv("FORWARD_TO_USER_ID"))  # ID адміна, куди форвардити

EXAM_TIMER_DURATION = int(os.getenv("EXAM_TIMER_DURATION"))  # Час на проходження екзамену

# Підключення до PostgreSQL — ОБОВ'ЯЗКОВО через .env на продакшні!
DATABASE_URL = os.getenv("DATABASE_URL")  # Наприклад: postgresql://user:pass@host:5432/dbname
if not DATABASE_URL:
    raise ValueError("Помилка: не знайдено DATABASE_URL в .env файлі!")



logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
bot = Bot(token=TOKEN)
dp = Dispatcher()

price_settings = {
    "base_price": 2,
    "alpha": 0.07,
    "min_price": 0.9,
    "base_price_exam": 200,
    "alpha_exam": 0.1,
    "min_price_exam": 150
}
router = Router()


async def load_attempts() -> dict:
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        rows = await conn.fetch("SELECT * FROM attempts;")

        attempts_data = {}
        for row in rows:
            user_id = row['user_id']
            attempts_data[user_id] = {
                "attempts": row['attempts'] or 0,
                "exam_attempts": row['exam_attempts'] or 0,  # нове
                "used_attempts": row['used_attempts'] or 0,  # нове
                "first_name": row['first_name'] or "Без імені",
                "username": row['username'] or "",
            }
        return attempts_data

    except Exception as e:
        logging.error(f"Помилка при завантаженні спроб: {e}")
        return {}

    finally:
        await conn.close()

async def save_attempts(data: dict):
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        async with conn.transaction():
            for user_id, info in data.items():
                await conn.execute("""
                    INSERT INTO attempts (
                        user_id, attempts, exam_attempts, used_attempts,
                        first_name, username
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (user_id) DO UPDATE SET
                        attempts = EXCLUDED.attempts,
                        exam_attempts = EXCLUDED.exam_attempts,
                        used_attempts = EXCLUDED.used_attempts,
                        first_name = EXCLUDED.first_name,
                        username = EXCLUDED.username
                """,
                user_id,
                info.get("attempts", 0),
                info.get("exam_attempts", 0),
                info.get("used_attempts", 0),
                info.get("first_name", ""),
                info.get("username", "")
                )
        return True
    except Exception as e:
        logging.error(f"Помилка при збереженні спроб: {e}")
        return False
    finally:
        await conn.close()
