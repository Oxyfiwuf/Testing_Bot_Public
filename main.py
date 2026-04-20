import asyncio
from aiogram import F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
import asyncpg
from datetime import timedelta, datetime
import logging
from states import GiveAttempts, DeleteTest, CheckAttempts, UploadTest, ImportUsers, ChatMass, Exam, GiveEXAMAttempts, UploadHTML, UploadHTML_MOS
from admin_handlers import register_admin_handlers, announcement, set_price_command, set_price_exam_command, import_users_entry,give_attempts_entry,upload_test_entry,check_attempts_entry,receive_users_file,wrong_type_users,process_user_identifier,process_attempts,receive_test_file,\
wrong_type_in_upload,process_check_user,wrong_check_input, delete_test_entry, cancel_delete, confirm_delete_test, delete_test_confirmed, delete_test_cancelled, chat_entry, process_chat_users, process_chat_text, give_exam_attempts_entry, exam_process_attempts, exam_process_user_identifier, get_questions_count, backup_database
from config import load_attempts, save_attempts, ADMIN_ID, FORWARD_TO_USER_ID, DATABASE_URL, bot, dp, price_settings, router, EXAM_TIMER_DURATION
from keyboards import main_keyboard, admin_keyboard, main_with_admin_button, test_keyboard, cancel_kb, exam_keyboard, exam_confirmed_keyboard, exam_finish_keyboard, exam_finish_confirm_keyboard, mos_selected_keyboard, apks_selected_keyboard
from apks_logic import receive_html_file, start_upload_process, handle_html_document, invalid_input_in_state, cancel_upload
from mos_selected import receive_html_file_mos, start_upload_process_mos, handle_html_document_mos, invalid_input_in_state_mos, cancel_upload_mos
import math

# Крок 2: Підтвердження завершення
@dp.message(F.text == "Так, закінчити екзамен", Exam.in_exam and Exam.confirm)
async def exam_finish_confirm(message: Message, state: FSMContext):
    await message.answer("Екзамен завершено.", reply_markup=main_keyboard)
    user_id = message.from_user.id
    attempts_data = await load_attempts()
    attempts_data[user_id]["exam_attempts"] = 0
    await save_attempts(attempts_data)
    await state.clear()

@dp.message(F.text == "Продовжити екзамен", Exam.in_exam and Exam.confirm)
async def exam_finish_cancel(message: Message, state: FSMContext):
    await message.answer("Продовжуємо екзамен. Шукайте питання далі.", reply_markup=exam_finish_keyboard)
    await state.clear()
    await state.set_state(Exam.in_exam)

@dp.message(Exam.in_exam and Exam.confirm)
async def request_exam_finish(message: Message, state: FSMContext):
    await message.answer(
        "Ви впевнені, що хочете закінчити екзамен?\n"
        "Після підтвердження ви не зможете продовжувати пошук відповідей у цьому сеансі.",
        reply_markup=exam_finish_confirm_keyboard
    )
    await state.set_state(Exam.confirm)

# Пошук питань під час екзамену (в стані Exam.in_exam)
@dp.message(Exam.in_exam)
async def receive_questions_exam(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if message.text == "Закінчити екзамен":
        await request_exam_finish(message, state)
        return
    # Тут логіка як вище, але з екзаменаційними спробами
    if user_id not in user_selected_test:
        await message.answer("Будь ласка, спершу виберіть тест.")
        await forward_to_admin(message, f"{user_ident(message)} \nБудь ласка, спершу виберіть тест.")
        return

    attempts_data = await load_attempts()

    if user_id not in attempts_data or attempts_data[user_id]['exam_attempts'] <= 0:
        await message.answer("У вас немає екзаменаційних спроб. Якщо ви ще не завершили екзамен, зверніться до @one234five")
        await message.answer("Якщо ви хочете завершити екзамен натисніть кнопку\n<code>Закінчити екзамен</code>",
                             parse_mode="HTML")

        await forward_to_admin(message, f" У {user_ident(message)} закінчилися екзаменаційні спроби")
        return

    sheet_title = "exam"
    qa_dict = await load_questions_and_answers(sheet_title)

    if not qa_dict:
        await message.answer("Виникла помилка. Зверніться до адміністратора @one234five")
        await forward_to_admin(message, "Не вдалося завантажити запитання з файлу.")
        await state.clear()
        return

    user_question = message.text.strip()
    words = user_question.split()
    min_length = max(1, len(words) * 3 // 4)

    while len(words) >= min_length:
        shortened_question = " ".join(words)

        if shortened_question in qa_dict:
            await message.answer(f"Відповідь: {qa_dict[shortened_question]["answer"]}")
            await forward_to_admin(message, f"Відповідь: {qa_dict[shortened_question]["answer"]}")

            attempts_data[user_id]["exam_attempts"] -= 1
            await save_attempts(attempts_data)
            return

        words.pop()

    await message.answer("Це запитання не знайдено у тесті.")
    await forward_to_admin(message, "Це запитання не знайдено у тесті")
    await message.answer("Якщо ви хочете завершити екзамен натисніть кнопку\n<code>Закінчити екзамен</code>", parse_mode="HTML")
user_desired_attempts = {}  # {user_id: "waiting_for_number"}

@dp.message(lambda m: m.text == "⬅ Назад")
async def go_back(message: Message, state: FSMContext):
    if message.from_user.id != FORWARD_TO_USER_ID:
        await addUser(message)
        await delete_selected_test(message)
        await message.answer("""Ви повернулись в меню. 
Тут ви можете переглянути спроби або вибрати тест. 
Нагадую: 
- Питання вказуйте повністю
- Слідкуйте щобнезагубились пробіли при копіюванні.
- Для поповнення спроб напишіть @one234five. Порахувати ціну - /calculate
Оберіть дію:""", reply_markup=main_keyboard)
        await forward_to_admin(message, f"{user_ident(message)} повернувся до головного меню")
        await state.clear()


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
dp.message.register(give_exam_attempts_entry, F.text == "Видати ЕКЗАМЕН-спроби\n/give_exam_attempts")

# Перевірка інформації про користувача
dp.message.register(check_attempts_entry, Command("check_attempts"))
dp.message.register(check_attempts_entry, F.text == "Перевірити спроби\n/check_attempts")

# Видалити тест
dp.message.register(delete_test_entry, Command("delete_test"))
dp.message.register(delete_test_entry, F.text == "Видалити тест\n/delete_test")

# Чат з користувачами
dp.message.register(chat_entry, Command("chat"))
dp.message.register(chat_entry, F.text.lower() == "чат")

# Бекап бази даних
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

# АПКС ТЕСТ

# 1. Кнопка або текст "Надати файли" — починаємо процес
dp.message.register(start_upload_process, F.text =="Надати файли")

# 2. У стані очікування — приймаємо ТІЛЬКИ HTML-документ
dp.message.register(
    handle_html_document,
    UploadHTML.html_required,                                 # стан
    lambda m: m.document and m.document.file_name.lower().endswith('.html')  # фільтр на .html
)
# 4. Скасування — працює в будь-який час, але особливо в стані
dp.message.register(cancel_upload, UploadHTML.html_required, F.text == "⬅ Назад")  # або F.text == "⬅ Назад"

# 3. У стані очікування — якщо надіслано щось інше (текст, фото тощо)
dp.message.register(invalid_input_in_state, UploadHTML.html_required)

# МОС ТЕСТ

# 1. Кнопка або текст "Надати файли" — починаємо процес
dp.message.register(start_upload_process_mos, F.text =="Надати файли МОС")

# 2. У стані очікування — приймаємо ТІЛЬКИ HTML-документ
dp.message.register(
    handle_html_document_mos,
    UploadHTML_MOS.html_required,                                 # стан
    lambda m: m.document and m.document.file_name.lower().endswith('.html')  # фільтр на .html
)
# 4. Скасування — працює в будь-який час, але особливо в стані
dp.message.register(cancel_upload_mos, UploadHTML_MOS.html_required, F.text == "⬅ Назад")  # або F.text == "⬅ Назад"

# 3. У стані очікування — якщо надіслано щось інше (текст, фото тощо)
dp.message.register(invalid_input_in_state_mos, UploadHTML_MOS.html_required)



dp.message.register(get_questions_count, Command("check_test"))

working_phrases = """Вітаю друзі, тут можна пройти екзамен з КЛ (КІ-2).

Принцип роботи такий:
Видаю спроби, проходите, після чого оплачуєте! Все просто.
Вартість 200 гривень, якщо беруть декілька чоловік то буде пристойна знижка (Розрахунок ціни в "Разом дешевше")
Проходження таке ж як і у звичайних тестів, скидуєте питання, слідкуйте щоб питання було повним - питання, де пропущений знак питання в кінці речення чи який-небудь відсутній пробіл не оброблюється алгоритом.
На проходження екзамену вам буде виділений час (зараз це 60 хв), після чого екзамен завершиться і спроби, які ви не використали, будуть анульовані.
Безкоштовна можливість отримати спроби ще раз, тільки якщо ви:
1. Не встигнули пройти екзамен, як він закінчився (кількість спроб визначається кількістю питань, що залишилися), 
2. Не використали ні однієї спроби (Помилково відкрили екзамен, абощо). В випадку помилкового відкриття раджу негайно його закрити і звернутись до адміністратора,
3. Проблеми з ВНС (кількість спроб визначається, взалежності від того, що скаже Валерій Сергійович),
4. Та інші непередбачувані ситуації, на розсуд адміністратора.
"""
# Налаштування логування
logging.basicConfig(level=logging.INFO)


async def init_db():
    conn = await asyncpg.connect(DATABASE_URL)
    try:

        # Створення таблиці для спроб користувачів
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS attempts (
                user_id BIGINT PRIMARY KEY,
                attempts INTEGER DEFAULT 0,
                first_name VARCHAR(255),
                username VARCHAR(255)
            );
        """)

        # Додаємо exam_attempts
        await conn.execute("""
                ALTER TABLE attempts 
                ADD COLUMN IF NOT EXISTS exam_attempts INTEGER DEFAULT 0;
            """)

        # Додаємо used_attempts
        await conn.execute("""
                ALTER TABLE attempts 
                ADD COLUMN IF NOT EXISTS used_attempts INTEGER DEFAULT 0;
            """)


        # Створення таблиці для налаштувань цін (один рядок)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS price_settings (
                id SERIAL PRIMARY KEY,
                base_price NUMERIC,
                alpha NUMERIC,
                min_price NUMERIC,
                base_price_exam NUMERIC,
                alpha_exam NUMERIC,
                min_price_exam NUMERIC
            );
        """)

        # Якщо таблиця порожня, вставляємо дефолтні значення
        row = await conn.fetchrow("SELECT * FROM price_settings LIMIT 1;")
        if not row:
            await conn.execute("""
                INSERT INTO price_settings (base_price, alpha, min_price, base_price_exam, alpha_exam, min_price_exam)
                VALUES ($1, $2, $3, $4, $5, $6);
            """, price_settings["base_price"], price_settings["alpha"], price_settings["min_price"],
                 price_settings["base_price_exam"], price_settings["alpha_exam"], price_settings["min_price_exam"])
    finally:
        await conn.close()


async def load_questions_and_answers(table_name: str) -> dict:
    """
    Завантажує питання та відповіді з таблиці.
    Повертає словник: {question: {"answer": str, "added_by": str | None}}
    """
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        # Перевіряємо існування таблиці
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM pg_tables 
                WHERE schemaname = 'public' 
                AND tablename = $1
            )
        """, table_name)

        if not exists:
            logging.warning(f"Таблиці {table_name} не існує")
            return {}

        # Перевіряємо, чи є стовпець added_by
        has_added_by = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = $1 AND column_name = 'added_by'
            )
        """, table_name)

        if has_added_by:
            # Якщо є стовпець — завантажуємо з added_by
            rows = await conn.fetch(f'''
                SELECT question, answer, added_by FROM "{table_name}"
            ''')
            qa_dict = {
                row["question"].strip(): {
                    "answer": row["answer"].strip(),
                    "added_by": row["added_by"].strip() if row["added_by"] else None
                }
                for row in rows
            }
        else:
            # Якщо немає — тільки питання і відповідь
            rows = await conn.fetch(f'''
                SELECT question, answer FROM "{table_name}"
            ''')
            qa_dict = {
                row["question"].strip(): {
                    "answer": row["answer"].strip(),
                    "added_by": None
                }
                for row in rows
            }

        logging.info(f"Завантажено {len(qa_dict)} питань з таблиці {table_name} "
                     f"(з added_by: {has_added_by})")
        return qa_dict

    except Exception as e:
        logging.error(f"Помилка при завантаженні з таблиці {table_name}: {e}")
        return {}
    finally:
        await conn.close()


async def load_price_settings():
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        row = await conn.fetchrow("SELECT base_price, alpha, min_price, base_price_exam, alpha_exam, min_price_exam FROM price_settings LIMIT 1;")
        if row:
            price_settings["base_price"] = float(row['base_price'])
            price_settings["alpha"] = float(row['alpha'])
            price_settings["min_price"] = float(row['min_price'])
            price_settings["base_price_exam"] = float(row['base_price_exam'])
            price_settings["alpha_exam"] = float(row['alpha_exam'])
            price_settings["min_price_exam"] = float(row['min_price_exam'])
            logging.info(f"Ціни завантажено: {price_settings}")
    except Exception as e:
        logging.warning(f"Не вдалося завантажити ціни: {e}")
    finally:
        await conn.close()


# Глобальні змінні для зберігання стану
user_attempts = {}  # Тепер завантажуємо асинхронно
user_selected_test = {}
# Словник стану адмін-режиму (щоб не спамити клавіатурою всім)
admin_mode = {}  # {user_id: True/False}




@dp.message(F.text == "Розрахунок ціни\n/calculate")
async def admin_calculate(message: Message):
    if message.from_user.id not in ADMIN_ID:
        return
    await calculate_command(message)

async def forward_to_admin(message: Message, text):
    # Перевіряємо, щоб повідомлення не надсилалось самому собі
    if message.from_user.id != FORWARD_TO_USER_ID:
        try:
            await bot.forward_message(chat_id=FORWARD_TO_USER_ID, from_chat_id=message.chat.id,
                                  message_id=message.message_id)
            await bot.send_message(chat_id=FORWARD_TO_USER_ID, text=text)
        except Exception as e:
            logging.error(f"Не вдалося надіслати адміну: {e}")




async def addUser(message: Message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "Без імені"
    username = message.from_user.username or ""

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        # Перевіряємо існування користувача
        exists = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM attempts WHERE user_id = $1)", user_id)

        if exists:
            # Оновлюємо тільки змінні дані (first_name, username), решта лишається недоторканою
            await conn.execute("""
                UPDATE attempts
                SET first_name = $1, username = $2
                WHERE user_id = $3
            """, first_name, username, user_id)
        else:
            # Додаємо нового користувача з дефолтними значеннями
            await conn.execute("""
                INSERT INTO attempts (user_id, attempts, exam_attempts, used_attempts, first_name, username)
                VALUES ($1, 10, 0, 0, $2, $3)
            """, user_id, first_name, username)

            # Повідомляємо адміну про нового користувача
            await forward_to_admin(
                message,
                f"В бота зайшов користувач:\n"
                f"id - {user_id}\n"
                f"username - {username or str(user_id)}\n"
                f"name - {first_name}"
            )
    except Exception as e:
        logging.error(f"Помилка при додаванні/оновленні користувача {user_id}: {e}")
    finally:
        await conn.close()


@dp.message(F.text.in_(["Адмін-режим ВКЛ", "Адмін-режим ВИКЛ\n🕊😉"]))
async def toggle_admin_mode(message: Message):
    if message.from_user.id not in ADMIN_ID:
        return

    if message.text == "Адмін-режим ВКЛ":
        await message.answer("Адмін-режим увімкнено!", reply_markup=admin_keyboard)
    else:
        await message.answer(
            "Адмін-режим вимкнено.\n"
            "Ви повернулись до звичайного меню.",
            reply_markup=main_with_admin_button  # ← саме ця клавіатура!
        )


@dp.message(Command("start"))
async def start(message: Message):
    if message.from_user.id != FORWARD_TO_USER_ID:
        await addUser(message)
        await delete_selected_test(message)
        # Якщо це адмін — пропонуємо увімкнути адмін-режим
        if message.from_user.id in ADMIN_ID:
            await message.answer(
                "Вітаю, адмін!\n"
                "Увімкніть адмін-панель кнопкою нижче:",
                reply_markup=main_with_admin_button
            )
        else:
            await message.answer("""Вітаємо любі друзі - це тести Глухова (КЛ)👋
📌 Наші правила:
- Питання завжди вказуйте повністю 
- Деякі форматовані питання в ВНС з'їдають пробіли. Слідкуйте, щобнічого не загубилось при копіюванні)
- Для поповнення спроб пишіть @one234five.
- Розрахувати ціну можна на будь-яку кількість спроб /calculate
При вході в бота перші 10 тестів безкоштовно
""", reply_markup=main_keyboard)
            await forward_to_admin(message, f"{user_ident(message)} ввів команду /start і зараз він в головному меню")



@dp.message(Command("calculate"))
async def calculate_command(message: Message):
    user_desired_attempts[message.from_user.id] = "waiting_for_number"
    await message.answer("Введіть бажану кількість спроб для розрахунку ціни:")


@dp.message(lambda m: m.text == "📱 Розрахувати ціну")
async def calculate_button(message: Message):
    user_id = message.from_user.id
    user_desired_attempts[user_id] = "waiting_for_number"
    await message.answer("Введіть бажану кількість спроб для розрахунку ціни:")
    await forward_to_admin(message, f"{user_ident(message)} Розраховує ціну")


@dp.message(lambda m: user_desired_attempts.get(m.from_user.id) == "waiting_for_number")
async def handle_attempt_number(message: Message):
    user_id = message.from_user.id
    try:
        Q = int(message.text.strip())
        if Q <= 0:
            raise ValueError
        price_per_unit, total_price, discount_percent = calculate_price(Q)
        total_price = math.ceil(total_price)
        await message.answer(
            f"Для {Q} спроб:\n"
            f"- Ціна за одну спробу: {price_per_unit:.2f} грн\n"
            f"- Загальна ціна: {total_price:.2f} грн\n"
            f"- Знижка: {discount_percent:.1f}%"
        )

        await forward_to_admin(message, f"{user_ident(message)} шукає такі дані\n"
                                        f"Для {Q} спроб:\n"
                                        f"- Ціна за одну спробу: {price_per_unit:.2f} грн\n"
                                        f"- Загальна ціна: {total_price:.2f} грн\n"
                                        f"- Знижка: {discount_percent:.1f}%"
                               )
    except ValueError:
        await message.answer("Будь ласка, введіть коректне число більше 0.")
        await forward_to_admin(message, f"{user_ident(message)} ввів некоректне число")
    finally:
        user_desired_attempts.pop(user_id, None)


def calculate_price(Q):
    P0 = price_settings["base_price"]
    alpha = price_settings["alpha"]
    P_min = price_settings["min_price"]
    price_per_unit = max(P0 * Q ** -alpha, P_min)
    total_price = price_per_unit * Q
    discount_percent = 100 * (1 - price_per_unit / P0)
    return price_per_unit, total_price, discount_percent

async def delete_selected_test(message: Message):
    user_id = message.from_user.id
    if user_id in user_selected_test:
        del user_selected_test[user_id]


@dp.message(lambda m: m.text == "🔄 Переглянути спроби")
async def check_attempts(message: Message):
    if message.from_user.id != FORWARD_TO_USER_ID:

        await addUser(message)
        attempts = await load_attempts()
        user_attempts = attempts.get(message.from_user.id, {}).get('attempts', 0)
        await message.answer(
            f"Ваші спроби: {user_attempts}. Напишіть @one234five для поповнення або /calculate для розрахунку")
        await forward_to_admin(message,
                               f"Користувач {user_ident(message)} переглянув спроби. У нього - {user_attempts}")
        # Видаляємо вибір тесту, якщо він був
        await delete_selected_test(message)

@dp.message(lambda m: m.text == "🔄 Переглянути ЕКЗАМЕН-спроби")
async def check_exam_attempts(message: Message):
    if message.from_user.id != FORWARD_TO_USER_ID:

        await addUser(message)
        attempts = await load_attempts()
        user_attempts = attempts.get(message.from_user.id, {}).get('exam_attempts', 0)
        await message.answer(
            f"Ваші ЕКЗАМЕН-спроби: {user_attempts}. Напишіть @one234five, якщо хочете пройти екзамен")
        await forward_to_admin(message,
                               f"Користувач {user_ident(message)} переглянув ЕКЗАМЕН-спроби. У нього - {user_attempts}")
        # Видаляємо вибір тесту, якщо він був
        await delete_selected_test(message)

@dp.message(lambda m: m.text == "📝 Обрати тест")
async def select_test(message: Message):
    if message.from_user.id != FORWARD_TO_USER_ID:
        await addUser(message)
        await message.answer("Оберіть тест:", reply_markup=test_keyboard)
        await forward_to_admin(message, f"{user_ident(message)} обирає тест")
        await delete_selected_test(message)


@dp.message(lambda m: m.text == "🏫 Екзамен")
async def select_test(message: Message):
    if message.from_user.id != FORWARD_TO_USER_ID:
        await addUser(message)
        await message.answer(working_phrases, reply_markup=exam_keyboard)
        await forward_to_admin(message, f"{user_ident(message)} відвідав вкладку Екзамен")

@dp.message(lambda m: m.text == "🤗 Разом дешевше")
async def calculate_exam_button(message: Message):
    user_id = message.from_user.id
    user_desired_attempts[user_id] = "waiting_for_number_exam"
    await message.answer("Введіть кількість осіб, для отримання знижки:")
    await forward_to_admin(message, f"{user_ident(message)} Розраховує ціну для екзаменом")


@dp.message(lambda m: user_desired_attempts.get(m.from_user.id) == "waiting_for_number_exam")
async def handle_attempt_exam_number(message: Message):
    user_id = message.from_user.id
    try:
        Q = int(message.text.strip())
        if Q <= 0:
            raise ValueError
        price_per_unit, total_price, discount_percent = calculate_price_exam(Q)
        total_price = math.ceil(total_price)
        await message.answer(
            f"Для {Q} осіб:\n"
            f"- Ціна на одну особу: {price_per_unit:.2f} грн\n"
            f"- Загальна ціна: {total_price:.2f} грн\n"
            f"- Знижка: {discount_percent:.1f}%"
        )

        await forward_to_admin(message, f"{user_ident(message)} шукає такі дані\n"
                                        f"Для {Q} осіб:\n"
                                        f"- Ціна на одну особу: {price_per_unit:.2f} грн\n"
                                        f"- Загальна ціна: {total_price:.2f} грн\n"
                                        f"- Знижка: {discount_percent:.1f}%"
                               )
    except ValueError:
        await message.answer("Будь ласка, введіть коректне число більше 0.")
        await forward_to_admin(message, f"{user_ident(message)} ввів некоректне число")
    finally:
        user_desired_attempts.pop(user_id, None)


def calculate_price_exam(Q):
    P0 = price_settings["base_price_exam"]
    alpha = price_settings["alpha_exam"]
    P_min = price_settings["min_price_exam"]
    price_per_unit = max(P0 * Q ** -alpha, P_min)
    total_price = price_per_unit * Q
    discount_percent = 100 * (1 - price_per_unit / P0)
    return price_per_unit, total_price, discount_percent


@dp.message(F.text.startswith("ТЕСТ "))
async def test_selected(message: Message):
    if message.from_user.id != FORWARD_TO_USER_ID:
        await addUser(message)
        test_name = message.text.split(" ")[1]  # Отримуємо номер тесту (наприклад, "1.1" або "9")
        sheet_title = f"Test{test_name}"  # Формуємо назву тесту (Test1.1, Test9 тощо)
        user_selected_test[message.from_user.id] = sheet_title
        qa_dict = await load_questions_and_answers(sheet_title)
        if qa_dict:
            await message.answer(f"Ви вибрали ТЕСТ {test_name}. Будь ласка, впишіть свої запитання:",
                                 reply_markup=main_keyboard)
        else:
            await message.answer("Нажаль такого тесту ще не існує.", reply_markup=main_keyboard)
        await forward_to_admin(message, f"{'@' + message.from_user.username or 'N/A'} вибрав тест {test_name}")


@dp.message(F.text.startswith("ТП "))
async def tp_selected(message: Message):
    if message.from_user.id != FORWARD_TO_USER_ID:
        await addUser(message)
        number = message.text.split(" ")[1]  # Отримуємо номер ТП тесту (1, 2, ..., 15)
        sheet_title = f"TP{number}"  # Формуємо назву тесту (TP1, TP2 тощо)
        user_selected_test[message.from_user.id] = sheet_title
        qa_dict = await load_questions_and_answers(sheet_title)
        if qa_dict:
            await message.answer(f"Ви вибрали ТП {number}. Будь ласка, впишіть свої запитання:",
                                 reply_markup=main_keyboard)
        else:
            await message.answer("Нажаль такого тесту ще не існує.", reply_markup=main_keyboard)
        await forward_to_admin(message, f"{'@' + message.from_user.username or 'N/A'} вибрав ТП {number}")

@dp.message(F.text == "AKSM")
async def aksm_selected(message: Message):
    if message.from_user.id != FORWARD_TO_USER_ID:
        await addUser(message)
        sheet_title = "AKSM"  # Формуємо назву тесту (TP1, TP2 тощо)
        user_selected_test[message.from_user.id] = sheet_title
        qa_dict = await load_questions_and_answers(sheet_title)
        if qa_dict:
            await message.answer(f"Ви вибрали тест AKSM. Будь ласка, впишіть свої запитання:",
                                 reply_markup=main_keyboard)
        else:
            await message.answer("Нажаль такого тесту ще не існує.", reply_markup=main_keyboard)
        await forward_to_admin(message, f"{'@' + message.from_user.username or 'N/A'} вибрав AKSM")


@dp.message(F.text == "APKS")
async def APKS_selected(message: Message):
    if message.from_user.id != FORWARD_TO_USER_ID:
        await addUser(message)
        sheet_title = "APKS"  # Формуємо назву тесту (TP1, TP2 тощо)
        user_selected_test[message.from_user.id] = sheet_title
        qa_dict = await load_questions_and_answers(sheet_title)
        if qa_dict:
            await message.answer(f"Ви вибрали тест APKS (Шпіцер). Будь ласка, впишіть свої запитання:",
                                 reply_markup=apks_selected_keyboard)
        else:
            await message.answer("Нажаль такого тесту ще не існує.", reply_markup=apks_selected_keyboard)
        await forward_to_admin(message, f"{'@' + message.from_user.username or 'N/A'} вибрав APKS (Шпіцер)")

@dp.message(F.text == "MOS")
async def MOS_selected(message: Message):
    if message.from_user.id != FORWARD_TO_USER_ID:
        await addUser(message)
        sheet_title = "MOS"  # Формуємо назву тесту (TP1, TP2 тощо)
        user_selected_test[message.from_user.id] = sheet_title
        qa_dict = await load_questions_and_answers(sheet_title)
        if qa_dict:
            await message.answer(f"Ви вибрали тест MOS (Бочкарьов). Будь ласка, впишіть свої запитання:",
                                 reply_markup=mos_selected_keyboard)
        else:
            await message.answer("Нажаль такого тесту ще не існує.", reply_markup=mos_selected_keyboard)
        await forward_to_admin(message, f"{'@' + message.from_user.username or 'N/A'} вибрав MOS (Бочкарьов)")


@dp.message(F.text == "TDPAZ")
async def TDPAZ_selected(message: Message):
    if message.from_user.id != FORWARD_TO_USER_ID:
        await addUser(message)
        sheet_title = "alltdpaz"  # Формуємо назву тесту (TP1, TP2 тощо)
        user_selected_test[message.from_user.id] = sheet_title
        qa_dict = await load_questions_and_answers(sheet_title)
        if qa_dict:
            await message.answer(f"Ви вибрали тест TDPAZ. Будь ласка, впишіть свої запитання:",
                                 reply_markup=main_keyboard)
        else:
            await message.answer("Нажаль такого тесту ще не існує.", reply_markup=main_keyboard)
        await forward_to_admin(message, f"{'@' + message.from_user.username or 'N/A'} вибрав TDPAZ")


@dp.message(Command("test"))
async def test_selected_command(message: Message):
    if message.from_user.id == FORWARD_TO_USER_ID:
        return  # адмін не повинен випадково вибирати тести

    await addUser(message)

    try:
        # Отримуємо все після /test
        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            raise ValueError("Не вказано назву тесту")

        raw_input = args[1].strip()

        sheet_title = None
        selected_text = None

        # Варіант 1: класичний — "ТЕСТ 1.1" або "ТП 5"
        if raw_input.startswith("ТЕСТ ") or raw_input.startswith("ТП "):
            parts = raw_input.split(" ", 2)
            if len(parts) < 2:
                raise ValueError("Неправильний формат для ТЕСТ/ТП")

            prefix, number = parts[0], parts[1]
            if prefix == "ТЕСТ":
                sheet_title = f"Test{number}"
                selected_text = f"ТЕСТ {number}"
            elif prefix == "ТП":
                sheet_title = f"TP{number}"
                selected_text = f"ТП {number}"

        # Варіант 2: пряма назва таблиці — просто "exam", "zno2024", "final" тощо
        else:
            # Дозволяємо назви з цифр, букв, підкреслень і дефісів
            if not raw_input.replace("_", "").replace("-", "").isalnum():
                raise ValueError("Назва тесту містить недопустимі символи")
            sheet_title = raw_input
            selected_text = raw_input  # відображаємо як ввів користувач

        # Перевіряємо, чи існує така таблиця в базі
        qa_dict = await load_questions_and_answers(sheet_title)

        if not qa_dict:
            await message.answer(
                f"Тесту з назвою <b>{sheet_title}</b> не знайдено.\n",
                reply_markup=main_keyboard,
                parse_mode="HTML"
            )
            return

        # Успішно — зберігаємо вибір
        user_selected_test[message.from_user.id] = sheet_title

        await message.answer(
            f"Ви вибрали тест: <b>{selected_text}</b>\n"
            f"Тепер можете надсилати питання з цього тесту!",
            reply_markup=main_keyboard,
            parse_mode="HTML"
        )

        await forward_to_admin(
            message,
            f"{user_ident(message)} вибрав тест <code>{sheet_title}</code> через команду /test"
        )

    except ValueError as e:
        if "Не вказано" in str(e) or "Неправильний" in str(e):
            error_msg = str(e)
        else:
            error_msg = "Неправильний формат команди"
        await message.answer(
            f"{error_msg}\n\n"
            f"Приклади правильного використання:\n"
            f"• <code>/test ТЕСТ 1.1</code>\n"
            f"• <code>/test ТП 5</code>\n",
            parse_mode="HTML"
        )

@dp.message(F.text == "📝 Почати Екзамен")
async def exam_confirmed(message: Message):
    await message.answer("Чи готові ви проходити Екзамен? \n<b>Якщо ви зайдете в Екзамен, то у вас буде година на те щоб пройти тест, після чого ваші екзаменаційні спроби зникнуть</b>", parse_mode="HTML", reply_markup=exam_confirmed_keyboard)

@dp.message(F.text == "Запуск тесту")
async def exam_selected(message: Message, state: FSMContext):
    user_id = message.from_user.id
    sheet_title = 'exam'
    # Перевіряємо, чи існує така таблиця в базі
    qa_dict = await load_questions_and_answers(sheet_title)

    if not qa_dict:
        await message.answer(
            f"Тесту з назвою <b>{sheet_title}</b> не знайдено.\n",
            reply_markup=main_keyboard,
            parse_mode="HTML"
        )
        return

    # Успішно — зберігаємо вибір
    user_selected_test[message.from_user.id] = sheet_title

    await message.answer(
        f"Ви проходите <b>ЕКЗАМЕН</b>\n"
        f"Надсилайте питання! Коли завершите тест натисніть кнопку <i>\"Завершити Екзамен\"</i>",
        reply_markup=exam_finish_keyboard,
        parse_mode="HTML"
    )

    await forward_to_admin(
        message,
        f"{user_ident(message)} вибрав ЕКЗАМЕН"
    )
    await state.set_state(Exam.in_exam)
    # Запускаємо таймер на 1 годину (3600 секунд)
    asyncio.create_task(exam_timer(user_id, state))

@dp.message()
async def receive_questions(message: Message):
    if message.from_user.id != FORWARD_TO_USER_ID:
        await addUser(message)
        user_id = message.from_user.id

        # Перевірка вибору тесту
        if user_id not in user_selected_test:
            await message.answer("Будь ласка, спершу виберіть тест: /test")
            await forward_to_admin(message,
                                   f"{user_ident(message)} не вибрав тест")
            return

        # Перевірка спроб
        attempts_data = await load_attempts()
        if user_id not in attempts_data or attempts_data[user_id]['attempts'] <= 0:
            await message.answer("У вас закінчилися спроби. Зверніться до адміністратора: @one234five")
            await forward_to_admin(message, f"У {user_ident(message)} закінчилися спроби")
            return

        sheet_title = user_selected_test[user_id]
        qa_dict = await load_questions_and_answers(sheet_title)

        if not qa_dict:
            await message.answer("Виникла помилка при завантаженні тесту. Зверніться до @one234five")
            await forward_to_admin(message, f"Не вдалося завантажити таблицю {sheet_title}")
            return

        user_question = message.text.strip()
        words = user_question.split()
        min_length = max(1, len(words) * 3 // 4)

        found = False
        while len(words) >= min_length:
            shortened_question = " ".join(words)

            if shortened_question in qa_dict:
                answer = qa_dict[shortened_question]["answer"]
                added_by = qa_dict[shortened_question]["added_by"]

                text = f"Відповідь: {answer}"

                # Показуємо автора ТІЛЬКИ якщо він є і це тест APKS
                if sheet_title == "APKS" or sheet_title == "MOS" and added_by :
                    text += f"\n\nПитання надано: {added_by}"

                await message.answer(text)
                await forward_to_admin(message, f"Відповідь надіслано:\n{answer}")

                # Зменшуємо спроби тільки для AKSM
                if sheet_title != "AKSM" and sheet_title != "APKS" and sheet_title != "MOS":
                    attempts_data[user_id]["attempts"] -= 1
                    attempts_data[user_id]["used_attempts"] += 1
                    await save_attempts(attempts_data)

                found = True
                break

            words.pop()

        if not found:
            await message.answer("Це запитання не знайдено у тесті.")
            await forward_to_admin(message, "Запитання не знайдено")

# Функція таймера
async def exam_timer(user_id: int, state: FSMContext):
    duration = EXAM_TIMER_DURATION
    end_time = datetime.now() + timedelta(seconds=duration)

    # Надсилаємо повідомлення з таймером
    timer_msg = await bot.send_message(
        user_id,
        "⏳ Таймер екзамену: ヽ(*・ω・)ﾉ♪\n\n"
    )

    # Прикріплюємо (pin) повідомлення
    #try:
    #    pin_message = await bot.pin_chat_message(chat_id=user_id, message_id=timer_msg.message_id)
    #except Exception as e:
    #    logging.warning(f"Не вдалося прикріпити таймер для {user_id}: {e}")
    helper_msg = await bot.send_message(user_id, "Для зручності можете прикріпити таймер", reply_markup=exam_finish_keyboard)
    # Оновлюємо кожні 5 секунд
    while True:
        await asyncio.sleep(1)
        # Перевіряємо, чи користувач ще в екзамені
        current_state = await state.get_state()
        if current_state != Exam.in_exam.state and current_state != Exam.confirm.state:
            # Користувач вийшов раніше — видаляємо таймер
            try:
                await timer_msg.delete()
                await helper_msg.delete()
            except:
                pass
            return

        remaining = (end_time - datetime.now()).total_seconds()
        if remaining <= 0:
            # Час вийшов
            await timer_msg.edit_text(
                "⏰ Час екзамену вичерпано!\n\n"
                "Екзамен завершено автоматично.\n"
                "Залишені спроби анульовано."
            )
            try:
                await bot.delete_message(chat_id=user_id, message_id=timer_msg.message_id)
                await bot.delete_message(chat_id=user_id, message_id=helper_msg.message_id)
            except Exception as e:
                logging.warning(f"Не вдалося відкріпити таймер для {user_id}: {e}")
            await bot.send_message(user_id,"⏰ Час екзамену вичерпано!\n\n"
                "Екзамен завершено автоматично.\n"
                "Залишені спроби анульовано.", reply_markup=main_keyboard)
            await state.clear()
            attempts_data = await load_attempts()
            attempts_data[user_id]["exam_attempts"] = 0
            await save_attempts(attempts_data)
            return

        # Оновлюємо текст
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        seconds = int(remaining % 60)
        new_text = f"⏳ Таймер екзамену: {hours:02d}:{minutes:02d}:{seconds:02d}"

        try:
            await timer_msg.edit_text(new_text)
        except Exception:
            # Якщо повідомлення видалене або заблоковане — виходимо
            return


def user_ident(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    user_ident = "@" + username if username else str(user_id)
    return user_ident


async def main():
    await init_db()
    await load_price_settings()
    await dp.start_polling(bot)


if __name__ == "__main__":

    asyncio.run(main())
