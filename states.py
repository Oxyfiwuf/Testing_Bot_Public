from aiogram.fsm.state import State, StatesGroup

# Оголошення станів
class GiveAttempts(StatesGroup):
    waiting_for_user = State()
    waiting_for_attempts = State()
# ───── Команда для видалення тесту (таблиці) ─────
class DeleteTest(StatesGroup):
    waiting_for_name = State()

# ───── Новий стан для перевірки спроб ─────
class CheckAttempts(StatesGroup):
    waiting_for_user = State()
# Додаємо стан для очікування файлу
class UploadTest(StatesGroup):
    waiting_for_file = State()

# Стани для імпорту користувачів
class ImportUsers(StatesGroup):
    waiting_for_file = State()

class ChatMass(StatesGroup):
    send_waiting_for_users = State()
    send_waiting_for_text = State()

class GiveEXAMAttempts(StatesGroup):
    waiting_for_user = State()
    waiting_for_attempts = State()

# Стани для екзамену
class Exam(StatesGroup):
    in_exam = State()
    confirm = State()

# Визначення станів FSM
class UploadHTML(StatesGroup):
    html_required = State()

class UploadHTML_MOS(StatesGroup):
    html_required = State()
