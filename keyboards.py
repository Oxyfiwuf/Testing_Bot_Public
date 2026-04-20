from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, \
    InlineKeyboardButton, CallbackQuery, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Головна клавіатура
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔄 Переглянути спроби")],
        [KeyboardButton(text="📱 Розрахувати ціну")],
        [KeyboardButton(text="📝 Обрати тест")],
        [KeyboardButton(text="🏫 Екзамен")]
    ],
    resize_keyboard=True
)

# ====================== АДМІНСЬКА КЛАВІАТУРА ======================
admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Видати спроби\n/give_attempts"),
            KeyboardButton(text="Видати ЕКЗАМЕН-спроби\n/give_exam_attempts"),
            KeyboardButton(text="Перевірити спроби\n/check_attempts")
        ],
        [
            KeyboardButton(text="Завантажити тест\n/upload_test"),
            KeyboardButton(text="Імпорт користувачів\n/import_users")
        ],
        [
            KeyboardButton(text="Розрахунок ціни\n/calculate"),
            KeyboardButton(text="Видалити тест\n/delete_test"),
            KeyboardButton(text="Адмін-режим ВИКЛ\n🕊😉")
        ]
    ],
    resize_keyboard=True
)

# Клавіатура коли адмін-режим вимкнено (показує тільки кнопку увімкнення)
main_with_admin_button = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔄 Переглянути спроби")],
        [KeyboardButton(text="📱 Розрахувати ціну")],
        [KeyboardButton(text="📝 Обрати тест")],
        [KeyboardButton(text="🏫 Екзамен")],
        [KeyboardButton(text="Адмін-режим ВКЛ")]  # ← завжди видно адмінам
    ],
    resize_keyboard=True
)

# Налаштування клавіатури вибору тестів
#test_keyboard = ReplyKeyboardMarkup(
#    keyboard=[
#                 # Тести 1.1, 1.2, ..., 8.1, 8.2
#                 [KeyboardButton(text=f"ТЕСТ {i}_{j}"), KeyboardButton(text=f"ТЕСТ {i}_{j + 1}")]
#                 for i in range(1, 9) for j in [1]
#             ] +
#             # Тести 9, 10, ..., 30
#             [
#                 [KeyboardButton(text=f"ТЕСТ {i}"), KeyboardButton(text=f"ТЕСТ {i + 1}")]
#                 for i in range(9, 30, 2)
#             ] +
#             # ТП тести 1-15
#             [
#                 [KeyboardButton(text=f"ТП {i}"), KeyboardButton(text=f"ТП {i + 1}")]
#                 for i in range(1, 15, 2)
#             ] +
#             # Останній ТП тест (15) і кнопка "Назад"
#             [
#                 [KeyboardButton(text="ТП 15")],
#                 [KeyboardButton(text="⬅ Назад")]
#             ],
#    resize_keyboard=True
#)

test_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="⬅ Назад")],
        # Тести по 3 в рядку
        [KeyboardButton(text="TDPAZ")],
        [KeyboardButton(text="AKSM")],
        [KeyboardButton(text="APKS")],
        [KeyboardButton(text="MOS")],
        [KeyboardButton(text="ТЕСТ 1_1"), KeyboardButton(text="ТЕСТ 1_2"), KeyboardButton(text="ТЕСТ 2_1")],
        [KeyboardButton(text="ТЕСТ 2_2"), KeyboardButton(text="ТЕСТ 3_1"), KeyboardButton(text="ТЕСТ 4_1")],
        [KeyboardButton(text="ТЕСТ 5_1"), KeyboardButton(text="ТЕСТ 6_1"), KeyboardButton(text="ТЕСТ 7_1")],
        [KeyboardButton(text="ТЕСТ 7_2"), KeyboardButton(text="ТЕСТ 8_1"), KeyboardButton(text="ТЕСТ 8_2")],
        [KeyboardButton(text="ТЕСТ 10"), KeyboardButton(text="ТЕСТ 11"), KeyboardButton(text="ТЕСТ 12")],
        [KeyboardButton(text="ТЕСТ 13"), KeyboardButton(text="ТЕСТ 15"), KeyboardButton(text="ТЕСТ 16")],
        [KeyboardButton(text="ТЕСТ 18"), KeyboardButton(text="ТЕСТ 19"), KeyboardButton(text="ТЕСТ 20")],
        [KeyboardButton(text="ТЕСТ 21_1"), KeyboardButton(text="ТЕСТ 21_2")],

        # ТП тести по 3 в рядку
        [KeyboardButton(text="ТП 1"), KeyboardButton(text="ТП 2"), KeyboardButton(text="ТП 3")],
        [KeyboardButton(text="ТП 4"), KeyboardButton(text="ТП 5"), KeyboardButton(text="ТП 6")],
        [KeyboardButton(text="ТП 7"), KeyboardButton(text="ТП 8"), KeyboardButton(text="ТП 9")],
        [KeyboardButton(text="ТП 10"),KeyboardButton(text="ТП 11"),KeyboardButton(text="ТП 12")],
        [KeyboardButton(text="ТП 13"),KeyboardButton(text="ТП 14"),KeyboardButton(text="ТП 15")],

        # Кнопка Назад знизу
        [KeyboardButton(text="⬅ Назад")]
    ],
    resize_keyboard=True
)

# Клавіатура для відміни
cancel_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="❌ Скасувати")]],
    resize_keyboard=True
)

# Головна клавіатура
exam_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔄 Переглянути ЕКЗАМЕН-спроби")],
        [KeyboardButton(text="🤗 Разом дешевше")],
        [KeyboardButton(text="📝 Почати Екзамен")],
        [KeyboardButton(text="⬅ Назад")]
    ],
    resize_keyboard=True
)

exam_confirmed_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Запуск тесту")],
        [KeyboardButton(text="⬅ Назад")]
    ],
    resize_keyboard=True
)

exam_finish_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Закінчити екзамен")]
    ],
    resize_keyboard=True
)

exam_finish_confirm_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Так, закінчити екзамен"),
            KeyboardButton(text="Продовжити екзамен")
        ]
    ],
    resize_keyboard=True
)

apks_selected_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Надати файли"),
            KeyboardButton(text="⬅ Назад")
        ]
    ],
    resize_keyboard=True
)


mos_selected_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Надати файли МОС"),
            KeyboardButton(text="⬅ Назад")
        ]
    ],
    resize_keyboard=True
)
