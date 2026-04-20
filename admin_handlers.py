# handlers/admin_handlers.py

from aiogram import F
from aiogram.types import Message, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
import logging
import asyncpg
from aiogram.fsm.context import FSMContext
import pandas as pd
import io
from datetime import timedelta, datetime
from aiogram.types import BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import load_attempts, save_attempts, ADMIN_ID, FORWARD_TO_USER_ID, DATABASE_URL, bot, price_settings, router
from states import GiveAttempts, DeleteTest, CheckAttempts, UploadTest, ImportUsers, ChatMass, GiveEXAMAttempts
from keyboards import main_keyboard, admin_keyboard, main_with_admin_button, test_keyboard, cancel_kb, exam_keyboard



async def announcement(message: Message):
    if message.from_user.id not in ADMIN_ID:
        await message.answer("У вас немає прав для цієї команди.")
        return

    announcement_text = message.text.strip().removeprefix("/ancm").strip()
    if not announcement_text:
        await message.answer("Будь ласка, надайте текст оголошення.")
        return

    try:
        attempts_data = await load_attempts()
        user_ids = list(attempts_data.keys())

        if not user_ids:
            await message.answer("Немає користувачів для надсилання оголошення.")
            return

        sent = 0
        for user_id in user_ids:
            try:
                await bot.send_message(user_id, announcement_text)
                sent += 1
            except Exception as e:
                logging.warning(f"Не вдалося надіслати користувачу {user_id}: {e}")

        await message.answer(f"Оголошення надіслано {sent} користувачам.")
    except Exception as e:
        await message.answer(f"Помилка при надсиланні оголошення: {e}")

async def set_price_command(message: Message):
    if message.from_user.id not in ADMIN_ID:
        await message.answer("У вас немає прав для цієї команди.")
        return
    try:
        parts = message.text.split()
        if len(parts) != 2:
            raise ValueError
        values = [float(x) for x in parts[1].split(',')]
        if len(values) != 3:
            raise ValueError
        price_settings["base_price"], price_settings["alpha"], price_settings["min_price"] = values
        await save_price_settings()
        await message.answer(
            f"Ціни успішно оновлено:\n"
            f"- Базова ціна: {price_settings['base_price']}\n"
            f"- Коефіцієнт знижки: {price_settings['alpha']}\n"
            f"- Мінімальна ціна: {price_settings['min_price']}"
        )
    except ValueError:
        await message.answer(
            "Неправильний формат. Використовуйте:\n"
            "/set_price базова_ціна,альфа,мінімальна_ціна\n"
            "Наприклад: <code>/set_price 2,0.07,0.9</code>",
            parse_mode="HTML"
        )

async def save_price_settings():
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute("""
            UPDATE price_settings SET
                base_price = $1,
                alpha = $2,
                min_price = $3
            WHERE id = (SELECT id FROM price_settings LIMIT 1);
        """, price_settings["base_price"], price_settings["alpha"], price_settings["min_price"])
        logging.info(f"Ціни збережено: {price_settings}")
    except Exception as e:
        logging.error(f"Не вдалося зберегти ціни: {e}")
    finally:
        await conn.close()

async def set_price_exam_command(message: Message):
    if message.from_user.id not in ADMIN_ID:
        await message.answer("У вас немає прав для цієї команди.")
        return
    try:
        parts = message.text.split()
        if len(parts) != 2:
            raise ValueError
        values = [float(x) for x in parts[1].split(',')]
        if len(values) != 3:
            raise ValueError
        price_settings["base_price_exam"], price_settings["alpha_exam"], price_settings["min_price_exam"] = values
        await save_price_exam_settings()
        await message.answer(
            f"Ціни успішно оновлено:\n"
            f"- Базова ціна: {price_settings['base_price_exam']}\n"
            f"- Коефіцієнт знижки: {price_settings['alpha_exam']}\n"
            f"- Мінімальна ціна: {price_settings['min_price_exam']}"
        )
    except ValueError:
        await message.answer(
            "Неправильний формат. Використовуйте:\n"
            "/set_price_exam базова_ціна,альфа,мінімальна_ціна\n"
            "Наприклад: <code>/set_price_exam 200,0.1,150</code>",
            parse_mode="HTML"
        )

async def save_price_exam_settings():
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute("""
            UPDATE price_settings SET
                base_price_exam = $1,
                alpha_exam = $2,
                min_price_exam = $3
            WHERE id = (SELECT id FROM price_settings LIMIT 1);
        """, price_settings["base_price_exam"], price_settings["alpha_exam"], price_settings["min_price_exam"])
        logging.info(f"Ціни збережено: {price_settings}")
    except Exception as e:
        logging.error(f"Не вдалося зберегти ціни: {e}")
    finally:
        await conn.close()

async def import_users_entry(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_ID:
        await message.answer("У вас немає прав для цієї команди.")
        return

    await message.answer(
        "Надішліть файл .xlsx з користувачами.\n"
        "Формат стовпців:\n"
        "• user_id (можна у форматі 6,63E+08)\n"
        "• attempts\n"
        "• first_name (може бути кілька слів)\n"
        "• username\n\n"
        "Після надсилання — я оновлю таблицю attempts."
    )
    await state.set_state(ImportUsers.waiting_for_file)


async def receive_users_file(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_ID:
        return

    doc = message.document
    if not doc.file_name.lower().endswith(('.xlsx', '.xls')):
        return await message.answer("Надішліть файл у форматі .xlsx")

    status = await message.answer(f"Завантажую {doc.file_name}...")

    file_io = io.BytesIO()
    await bot.download(doc, file_io)
    file_io.seek(0)

    try:
        df = pd.read_excel(file_io, dtype=str)
    except Exception as e:
        await status.edit_text(f"Помилка читання Excel: {e}")
        await state.clear()
        return

    required = ["user_id", "attempts", "first_name", "username"]
    if not all(col in df.columns for col in required):
        await status.edit_text(f"Не знайдено колонки: {required}\nЗнайдено: {list(df.columns)}")
        await state.clear()
        return

    users = []
    skipped = 0

    for _, row in df.iterrows():
        try:
            uid = str(row["user_id"]).strip().replace(",", ".")
            user_id = int(float(uid))

            attempts = int(float(str(row["attempts"]).replace(",", ".")))
            first_name = str(row["first_name"]).strip()
            username = str(row["username"]).strip() if pd.notna(row["username"]) else ""

            users.append((user_id, attempts, first_name, username))
        except:
            skipped += 1
            continue

    if not users:
        await status.edit_text("Не вдалося прочитати жодного користувача. Перевірте формат.")
        await state.clear()
        return

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.executemany("""
            INSERT INTO attempts (user_id, attempts, first_name, username)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id) DO UPDATE SET
                attempts = EXCLUDED.attempts,
                first_name = EXCLUDED.first_name,
                username = EXCLUDED.username
        """, users)

        total_in_db = await conn.fetchval("SELECT COUNT(*) FROM attempts")

        await status.edit_text(
            f"Успішно імпортовано!\n\n"
            f"• Користувачів оброблено: <b>{len(users)}</b>\n"
            f"• Пропущено рядків: <b>{skipped}</b>\n"
            f"• Всього в базі зараз: <b>{total_in_db}</b>\n\n"
            f"Таблиця attempts оновлена!",
            parse_mode="HTML"
        )
    except Exception as e:
        await status.edit_text(f"Помилка бази даних:\n{e}")
    finally:
        await conn.close()
        await state.clear()


async def wrong_type_users(message: Message):
    await message.answer("Будь ласка, надішліть файл .xlsx")

# Єдиний вхідний хендлер для команди та кнопки
async def give_attempts_entry(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_ID:
        await message.answer("У вас немає прав для цієї команди.")
        return

    await message.answer("Вкажіть ID або @username користувача:", reply_markup=cancel_kb)
    await state.set_state(GiveAttempts.waiting_for_user)


async def process_user_identifier(message: Message, state: FSMContext):
    if message.text == "❌ Скасувати":
        await message.answer("Операцію скасовано.", reply_markup=main_with_admin_button)
        await state.clear()
        return

    await state.update_data(user_identifier=message.text)
    await message.answer("Добре. Скільки спроб видати?", reply_markup=cancel_kb)
    await state.set_state(GiveAttempts.waiting_for_attempts)


async def process_attempts(message: Message, state: FSMContext):
    if message.text == "❌ Скасувати":
        await message.answer("Операцію скасовано.", reply_markup=main_with_admin_button)
        await state.clear()
        return

    try:
        attempts = int(message.text)
        if attempts <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Кількість спроб повинна бути позитивним цілим числом.")
        return

    data = await state.get_data()
    user_identifier = data["user_identifier"]

    attempts_data = await load_attempts()

    target_user = None
    for user_id, info in attempts_data.items():
        if str(user_id) == user_identifier.lstrip('@') or ("@" + info.get("username", "")) == user_identifier:
            target_user = int(user_id)
            break

    if not target_user:
        await message.answer(f"Користувача {user_identifier} не знайдено в базі.", reply_markup=main_with_admin_button)
        await state.clear()
        return

    attempts_data[target_user]["attempts"] += attempts
    if await save_attempts(attempts_data):
        await message.answer(
            f"Користувачу {target_user} додано {attempts} спроб(и).\n"
            f"Загальна кількість: {attempts_data[target_user]['attempts']}",
            reply_markup=main_with_admin_button
        )
        try:
            await bot.send_message(
                target_user,
                f"Вам додано {attempts} спроб(и).\n"
                f"Загальна кількість спроб: {attempts_data[target_user]['attempts']}"
            )
        except Exception:
            await message.answer(f"Не вдалося надіслати повідомлення користувачу {target_user}.")
    else:
        await message.answer("Помилка при збереженні спроб. Спробуйте ще раз.")

    await state.clear()


# Єдиний вхідний хендлер для команди та кнопки
async def give_exam_attempts_entry(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_ID:
        await message.answer("У вас немає прав для цієї команди.")
        return

    await message.answer("Вкажіть ID або @username користувача:", reply_markup=cancel_kb)
    await state.set_state(GiveEXAMAttempts.waiting_for_user)


async def exam_process_user_identifier(message: Message, state: FSMContext):
    if message.text == "❌ Скасувати":
        await message.answer("Операцію скасовано.", reply_markup=main_with_admin_button)
        await state.clear()
        return

    await state.update_data(user_identifier=message.text)
    await message.answer("Добре. Скільки спроб видати?", reply_markup=cancel_kb)
    await state.set_state(GiveEXAMAttempts.waiting_for_attempts)


async def exam_process_attempts(message: Message, state: FSMContext):
    if message.text == "❌ Скасувати":
        await message.answer("Операцію скасовано.", reply_markup=main_with_admin_button)
        await state.clear()
        return

    try:
        attempts = int(message.text)
        if attempts <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Кількість спроб повинна бути позитивним цілим числом.")
        return

    data = await state.get_data()
    user_identifier = data["user_identifier"]

    attempts_data = await load_attempts()

    target_user = None
    for user_id, info in attempts_data.items():
        if str(user_id) == user_identifier.lstrip('@') or ("@" + info.get("username", "")) == user_identifier:
            target_user = int(user_id)
            break

    if not target_user:
        await message.answer(f"Користувача {user_identifier} не знайдено в базі.", reply_markup=main_with_admin_button)
        await state.clear()
        return

    attempts_data[target_user]["exam_attempts"] += attempts
    if await save_attempts(attempts_data):
        await message.answer(
            f"Користувачу {target_user} додано {attempts} ЕКЗАМЕН-спроб(и).\n"
            f"Загальна кількість: {attempts_data[target_user]['exam_attempts']}",
            reply_markup=main_with_admin_button
        )
        try:
            await bot.send_message(
                target_user,
                f"Вам додано {attempts} ЕКЗАМЕН-спроб(и).\n"
                f"Загальна кількість спроб: {attempts_data[target_user]['exam_attempts']}"
            )
        except Exception:
            await message.answer(f"Не вдалося надіслати повідомлення користувачу {target_user}.")
    else:
        await message.answer("Помилка при збереженні спроб. Спробуйте ще раз.")

    await state.clear()




# Єдиний вхідний хендлер для команди та кнопки
async def upload_test_entry(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_ID:
        await message.answer("У вас немає прав для цієї команди.")
        return

    await message.answer(
        "Надішліть .xlsx файл з тестом (2 стовпці: Питання | Відповідь)\n"
        "Після надсилання файлу — я автоматично його імпортую."
    )
    await state.set_state(UploadTest.waiting_for_file)


async def receive_test_file(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_ID:
        return

    document = message.document
    if not document.file_name.lower().endswith(('.xlsx', '.xls')):
        return await message.answer("Надішліть, будь ласка, файл у форматі .xlsx")

    status_msg = await message.answer(f"Завантажую {document.file_name}...")

    file_io = io.BytesIO()
    await bot.download(document, file_io)
    file_io.seek(0)

    try:
        df = pd.read_excel(file_io, header=None, usecols=[0, 1])
    except Exception as e:
        await status_msg.edit_text(f"Помилка читання файлу: {e}")
        await state.clear()
        return

    if df.empty or df.shape[1] < 2:
        await status_msg.edit_text("Файл порожній або неправильний формат (потрібно 2 стовпці)")
        await state.clear()
        return

    table_name = document.file_name.split('.')[0].replace('.', '_').replace('-', '_')
    if not table_name.replace('_', '').isalnum():
        await status_msg.edit_text("Неправильна назва файлу. Використовуйте: Test1.1.xlsx, TP5.xlsx тощо")
        await state.clear()
        return

    records = []
    for _, row in df.iterrows():
        q = str(row[0]).strip() if not pd.isna(row[0]) else ""
        a = str(row[1]).strip() if not pd.isna(row[1]) else ""
        if q and a and q != "nan" and a != "nan":
            records.append((q, a))

    if not records:
        await status_msg.edit_text("У файлі немає валідних пар питання-відповідь")
        await state.clear()
        return

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute(f'''
            CREATE TABLE IF NOT EXISTS "{table_name}" (
                id SERIAL PRIMARY KEY,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                UNIQUE(question)
            );
        ''')

        await conn.execute(f'''TRUNCATE TABLE "{table_name}" RESTART IDENTITY;''')

        await conn.executemany(f'''
            INSERT INTO "{table_name}" (question, answer)
            VALUES ($1, $2)
            ON CONFLICT (question) DO UPDATE SET answer = EXCLUDED.answer;
        ''', records)

        await status_msg.edit_text(
            f"Успішно імпортовано!\n"
            f"Тест: <b>{document.file_name}</b>\n"
            f"Таблиця: <code>{table_name}</code>\n"
            f"Питань додано: <b>{len(records)}</b>\n\n"
            f"Тепер користувачі можуть вибрати цей тест у меню!",
            parse_mode="HTML"
        )
    except Exception as e:
        await status_msg.edit_text(f"Помилка бази даних: {e}")
    finally:
        await conn.close()
        await state.clear()


async def wrong_type_in_upload(message: Message):
    await message.answer("Будь ласка, надішліть файл .xlsx")

# Єдиний вхідний хендлер для команди та кнопки
async def check_attempts_entry(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_ID:
        await message.answer("У вас немає прав для цієї команди.")
        return

    await message.answer(
        "Вкажіть ID або @username користувача, щоб дізнатись кількість його спроб:",
        reply_markup=cancel_kb
    )
    await state.set_state(CheckAttempts.waiting_for_user)


async def process_check_user(message: Message, state: FSMContext):
    if message.text.strip() == "❌ Скасувати":
        await message.answer("Операцію скасовано.", reply_markup=main_with_admin_button)
        await state.clear()
        return

    user_identifier = message.text.strip()

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        row = await conn.fetchrow("""
            SELECT user_id, attempts, first_name, username 
            FROM attempts 
            WHERE user_id::text = $1 
               OR username = $2 
               OR '@' || username = $1
        """, user_identifier, user_identifier.lstrip('@'))

        if not row:
            await message.answer(
                f"Користувача <code>{user_identifier}</code> не знайдено в базі.",
                parse_mode="HTML",
                reply_markup=main_with_admin_button
            )
            await state.clear()
            return

        user_id = row['user_id']
        attempts = row['attempts']
        name = row['first_name'] or "Без імені"
        username = row['username']
        username_display = f"@{username}" if username else "(без username)"

        await message.answer(
            f"<b>Інформація про користувача:</b>\n\n"
            f"• Ім'я: <b>{name}</b>\n"
            f"• Username: {username_display}\n"
            f"• ID: <code>{user_id}</code>\n"
            f"• Спроб: <b>{attempts}</b>\n",
            parse_mode="HTML",
            reply_markup=main_with_admin_button
        )

    except Exception as e:
        logging.error(f"Помилка в process_check_user: {e}")
        await message.answer(f"Сталася помилка: {e}")

    finally:
        await conn.close()
        await state.clear()


async def wrong_check_input(message: Message):
    await message.answer("Будь ласка, надішліть ID або @username текстом.")


async def delete_test_entry(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_ID:
        await message.answer("У вас немає прав для цієї команди.")
        return

    await message.answer(
        "Надішліть назву таблиці, яку хочете видалити.\n\n"
        "Наприклад:\n"
        "<code>Test8.2</code>\n"
        "<code>TP15</code>\n"
        "<code>exam</code>\n"
        "<code>zno_2025</code>\n\n"
        "Увага! Видалення незворотне!",
        parse_mode="HTML",
        reply_markup=cancel_kb
    )
    await state.set_state(DeleteTest.waiting_for_name)


async def cancel_delete(message: Message, state: FSMContext):
    await message.answer("Видалення скасовано.", reply_markup=None)
    await state.clear()


async def confirm_delete_test(message: Message, state: FSMContext):
    table_name = message.text.strip()

    if table_name.lower() in {"attempts"}:
        await message.answer("Цю таблицю видаляти заборонено!", reply_markup=None)
        await state.clear()
        return

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM pg_tables 
                WHERE schemaname = 'public' 
                  AND tablename = $1
            )
        """, table_name)

        if not exists:
            await message.answer(
                f"Таблиці <code>{table_name}</code> не існує.",
                parse_mode="HTML",
                reply_markup=None
            )
            await state.clear()
            return

        builder = InlineKeyboardBuilder()
        builder.button(text="Видалити назавжди", callback_data=f"delete_test_confirm:{table_name}")
        builder.button(text="Скасувати", callback_data="delete_test_cancel")
        builder.adjust(1)

        await message.answer(
            f"Ви впевнені, що хочете <b>видалити тест</b>:\n"
            f"<code>{table_name}</code>\n\n"
            f"Всі питання з цього тесту будуть втрачені назавжди!",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )

    except Exception as e:
        await message.answer(f"Помилка: {e}")
    finally:
        await conn.close()
        await state.clear()


async def delete_test_confirmed(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_ID:
        await callback.answer("Недостатньо прав", show_alert=True)
        return

    table_name = callback.data.split(":", 1)[1]

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute(f'DROP TABLE IF EXISTS "{table_name}" CASCADE')

        await callback.message.edit_text(
            f"Тест <code>{table_name}</code> успішно видалено!\n"
            f"Таблиця та всі дані знищені.",
            parse_mode="HTML"
        )

        await bot.send_message(
            FORWARD_TO_USER_ID,
            f"Адмін {callback.from_user.full_name} (@{callback.from_user.username or 'без username'}) "
            f"видалив тест: <code>{table_name}</code>",
            parse_mode="HTML"
        )

    except Exception as e:
        await callback.message.edit_text(f"Помилка при видаленні: {e}")
    finally:
        await conn.close()
        await callback.answer()


async def delete_test_cancelled(callback: CallbackQuery):
    await callback.message.edit_text("Видалення скасовано.")
    await callback.answer()

# Вхідна команда /chat
async def chat_entry(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_ID:
        await message.answer("У вас немає прав для цієї команди.")
        return

    await message.answer(
        "Надішліть список користувачів (по одному на рядок або через кому/крапку з комою).\n\n"
        "Підтримуються:\n"
        "• user_id (наприклад: 123456789)\n"
        "• @username (наприклад: @durov)\n\n"
        "Після цього я попрошу текст повідомлення.\n\n"
        "<i>Щоб скасувати — надішліть «Скасувати»</i>",
        parse_mode="HTML",
        reply_markup=cancel_kb
    )
    await state.set_state(ChatMass.send_waiting_for_users)


# Крок 1: отримуємо список користувачів
async def process_chat_users(message: Message, state: FSMContext):
    if message.text.strip().lower() == "скасувати":
        await message.answer("Розсилку скасовано.", reply_markup=main_with_admin_button)
        await state.clear()
        return

    raw_users = message.text.strip()

    # Розбиваємо по комі, крапці з комою або новому рядку
    users = [u.strip() for u in raw_users.replace('\n', ',').split(',')]
    users = [u for u in users if u]  # видаляємо порожні

    if not users:
        await message.answer("Список користувачів порожній. Надішліть ще раз або «Скасувати».", reply_markup=cancel_kb)
        return

    await state.update_data(users_list=users)

    await message.answer(
        f"Отримано {len(users)} отримувачів.\n\n"
        "Тепер надішліть текст повідомлення, яке потрібно надіслати.\n\n"
        "<i>Щоб скасувати — надішліть «Скасувати»</i>",
        parse_mode="HTML",
        reply_markup=cancel_kb
    )
    await state.set_state(ChatMass.send_waiting_for_text)


# Крок 2: отримуємо текст і надсилаємо
async def process_chat_text(message: Message, state: FSMContext):
    if message.text.strip().lower() == "скасувати":
        await message.answer("Розсилку скасовано.", reply_markup=main_with_admin_button)
        await state.clear()
        return

    text = message.text

    data = await state.get_data()
    users = data.get("users_list", [])

    attempts_data = await load_attempts()

    sent = 0
    failed = 0

    status_msg = await message.answer(f"Надсилаю повідомлення {len(users)} користувачам... 0/{len(users)}")

    for idx, user in enumerate(users, 1):
        target_user = None
        for user_id, info in attempts_data.items():
            if str(user_id) == user.lstrip('@') or ("@" + info.get("username", "")) == user:
                target_user = int(user_id)
                break

        if not target_user:
            logging.warning(f"Користувача {user} не знайдено в базі.")
            failed += 1
            continue

        try:
            await bot.send_message(target_user, text)
            sent += 1
        except Exception as e:
            logging.warning(f"Не вдалося надіслати користувачу {target_user}: {e}")
            failed += 1

        # Оновлюємо статус кожні 5 користувачів (щоб не спамити)
        if idx % 5 == 0 or idx == len(users):
            await status_msg.edit_text(f"Надсилаю... {idx}/{len(users)} (надіслано: {sent})")

    await status_msg.edit_text(
        f"Розсилку завершено!\n\n"
        f"• Надіслано: <b>{sent}</b>\n"
        f"• Не знайдено / помилка: <b>{failed}</b>\n"
        f"• Всього в списку: <b>{len(users)}</b>",
        parse_mode="HTML",

    )
    await message.answer("VICTORY!!!!", reply_markup=main_with_admin_button)
    await state.clear()

async def get_questions_count(message: Message):
    """
    Повертає кількість питань (рядків) у таблиці.
    Якщо таблиця не існує або сталася помилка — повертає 0.
    """
    if message.from_user.id not in ADMIN_ID:
        await message.answer("У вас немає прав для цієї команди.")
    else:
        test_name = message.text.strip().removeprefix("/check_test").strip()
        if test_name == "":
            await message.answer(f"<b>Введіть назву таблиці</b>\nПравильне застосування команди: <code>/check_test APKS</code>", parse_mode="HTML")
            return
        conn = await asyncpg.connect(DATABASE_URL)
        try:
            # Перевіряємо, чи існує таблиця
            exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT FROM pg_tables 
                    WHERE schemaname = 'public' 
                    AND tablename = $1
                )
            """, test_name)

            if not exists:
                await message.answer(f"<b>Таблиці '{test_name}' не існує</b>\nПравильне застосування команди: <code>/check_test APKS</code>", parse_mode="HTML")
                return

            # Рахуємо кількість рядків
            count = await conn.fetchval(f'''
                SELECT COUNT(*) FROM "{test_name}"
            ''')

            await message.answer(f"У таблиці <b>{test_name}</b> знайдено {count} питань", parse_mode= "HTML")
            return int(count)

        except Exception as e:
            await message.answer(f"Помилка при підрахунку питань у таблиці '{test_name}': {e}")
            return 0
        finally:
            await conn.close()

async def backup_database(message: Message):
    """Команда /backup — створює повний бекап бази даних у форматі .xlsx"""
    if message.from_user.id not in ADMIN_ID:
        await message.answer("У вас немає прав для цієї команди.")
        return

    status = await message.answer("🔄 Починаю створення бекапу бази даних... Це може зайняти трохи часу.")

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        # Отримуємо всі таблиці в схемі public
        tables = await conn.fetch("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename
        """)

        if not tables:
            await status.edit_text("⚠️ Не знайдено жодної таблиці в базі даних.")
            return

        await status.edit_text(f"📊 Знайдено {len(tables)} таблиць. Формую Excel-файл...")

        # Створюємо файл у пам'яті
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for table in tables:
                table_name = table['tablename']
                try:
                    # Завантажуємо дані
                    rows = await conn.fetch(f'SELECT * FROM "{table_name}"')
                    if rows:
                        df = pd.DataFrame(rows, columns=rows[0].keys())
                    else:
                        # Порожня таблиця — створюємо з колонками
                        cols = await conn.fetch(f"""
                            SELECT column_name 
                            FROM information_schema.columns 
                            WHERE table_name = $1
                            ORDER BY ordinal_position
                        """, table_name)
                        df = pd.DataFrame(columns=[c['column_name'] for c in cols])

                    # Обрізаємо назву аркуша до 31 символу (ліміт Excel)
                    sheet_name = table_name[:31]
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                except Exception as e:
                    logging.error(f"Помилка при обробці таблиці {table_name}: {e}")
                    # Додаємо аркуш з помилкою
                    error_df = pd.DataFrame({"Помилка": [f"Не вдалося завантажити дані: {str(e)}"]})
                    error_df.to_excel(writer, sheet_name=table_name[:27] + "_err", index=False)

        output.seek(0)

        # Назва файлу з датою та часом
        filename = f"backup_bot_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.xlsx"

        # Створюємо BufferedInputFile
        input_file = BufferedInputFile(
            file=output.read(),
            filename=filename
        )

        await status.delete()  # якщо є повідомлення про статус

        await message.answer_document(
            document=input_file,
            caption=(
                f"📦 <b>Бекап бази даних створено!</b>\n\n"
                f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                f"📋 Таблиць у файлі: <b>{len(tables)}</b>\n"
                f"💾 Включено: attempts, price_settings та всі тести"
            ),
            parse_mode="HTML"
        )

    except Exception as e:
        logging.error(f"Критична помилка при створенні бекапу: {e}")
        await status.edit_text(f"❌ Помилка при створенні бекапу:\n<code>{str(e)}</code>", parse_mode="HTML")
    finally:
        await conn.close()


def register_admin_handlers(dp):
    # Встановлення ціни
    dp.message.register(set_price_command, Command("set_price"))

    # Встановлення ціни на екзамен
    dp.message.register(set_price_exam_command, Command("set_price_exam"))

    # Оголошення всім користувачам
    dp.message.register(announcement, Command("ancm"))

    # Імпорт в DataBase з Excel
    dp.message.register(import_users_entry, Command("import_users"))
    dp.message.register(import_users_entry, F.text == "Імпорт користувачів\n/import_users")

    # Завантаження тестів
    dp.message.register(upload_test_entry, Command("upload_test"))
    dp.message.register(upload_test_entry, F.text == "Завантажити тест\n/upload_test")

    # Видача спроб користувачу
    dp.message.register(give_attempts_entry, Command("give_attempts"))
    dp.message.register(give_attempts_entry, F.text == "Видати спроби\n/give_attempts")

    # Видача ЕКЗАМЕН-спроб користувачу
    dp.message.register(give_exam_attempts_entry, Command("give_exam_attempts"))
    dp.message.register(give_exam_attempts_entry, F.text == "Видати спроби\n/give_exam_attempts")

    # Перевірка інформації про користувача
    dp.message.register(check_attempts_entry, Command("check_attempts"))
    dp.message.register(check_attempts_entry, F.text == "Перевірити спроби\n/check_attempts")

    # Видалити тест
    dp.message.register(delete_test_entry, Command("delete_test"))
    dp.message.register(delete_test_entry, F.text == "Видалити тест\n/delete_test")

    # Чат з користувачами
    dp.message.register(chat_entry, Command("chat"))
    dp.message.register(chat_entry, F.text.lower() == "чат")

    # Бекап Бази даних
    dp.message.register(backup_database, Command("backup"))

    # ---------------------------КРОКИ СТАНУ--------------------------------#
    # Імпорт в DataBase з Excel
    dp.message.register(receive_users_file, ImportUsers.waiting_for_file, F.document)
    dp.message.register(wrong_type_users, ImportUsers.waiting_for_file)

    # Видача спроб користувачу
    dp.message.register(process_user_identifier, GiveAttempts.waiting_for_user, F.text)
    dp.message.register(process_attempts, GiveAttempts.waiting_for_attempts, F.text)

    # Видача ЕКЗАМЕН-спроб користувачу
    dp.message.register(exam_process_user_identifier, GiveEXAMAttempts.waiting_for_user, F.text)
    dp.message.register(exam_process_attempts, GiveEXAMAttempts.waiting_for_attempts, F.text)

    # Завантаження тестів
    dp.message.register(receive_test_file, UploadTest.waiting_for_file, F.document)
    dp.message.register(wrong_type_in_upload, UploadTest.waiting_for_file)

    # Перевірка інформації про користувача
    dp.message.register(process_check_user, CheckAttempts.waiting_for_user, F.text)
    dp.message.register(wrong_check_input, CheckAttempts.waiting_for_user)

    # Видалити тест
    dp.message.register(cancel_delete, DeleteTest.waiting_for_name, F.text == "Скасувати")
    dp.message.register(confirm_delete_test, DeleteTest.waiting_for_name, F.text)
    dp.callback_query.register(delete_test_confirmed, F.data.startswith("delete_test_confirm:"))
    dp.callback_query.register(delete_test_cancelled, F.data == "delete_test_cancel")

    # Чат з користувачами
    dp.message.register(process_chat_users, ChatMass.send_waiting_for_users, F.text)
    dp.message.register(process_chat_text, ChatMass.send_waiting_for_text, F.text)
    

