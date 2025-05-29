import asyncio
from datetime import date
from typing import Dict, Optional
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Конфигурация (ВАШ ТОКЕН УЖЕ ВСТАВЛЕН)
API_TOKEN = "8010104498:AAFu41LIYHrPWWl-kvT1pQ0GZrxE8AL0wZE"
ADMIN_ID = 123456789  # Замените на ваш ID

# Инициализация
bot = Bot(token=API_TOKEN, parse_mode=ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Хранение данных
users_roles: Dict[int, str] = {}
user_dates: Dict[int, date] = {}

# Доступные роли
ROLES = {
    "admin": "Администратор",
    "editor": "Редактор",
    "user": "Пользователь"
}


# Состояния FSM
class Form(StatesGroup):
    waiting_for_role = State()
    waiting_for_date = State()


# ================== КЛАВИАТУРЫ ================== #
def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎭 Моя роль", callback_data="my_role"),
        InlineKeyboardButton(text="📅 Установить дату", callback_data="set_date")
    )
    if has_role(user_id=ADMIN_ID, required_role="admin"):
        builder.row(
            InlineKeyboardButton(text="🛠 Назначить роль", callback_data="set_role"),
            InlineKeyboardButton(text="📋 Список ролей", callback_data="list_roles")
        )
    return builder.as_markup()


def roles_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for role, name in ROLES.items():
        builder.add(InlineKeyboardButton(text=name, callback_data=f"role_{role}"))
    builder.adjust(2)
    return builder.as_markup()


def generate_calendar(year: int, month: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    # Заголовок (месяц и год)
    builder.row(InlineKeyboardButton(
        text=date(year, month, 1).strftime("%B %Y"),
        callback_data="ignore"
    ))

    # Дни недели
    week_days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    for day in week_days:
        builder.add(InlineKeyboardButton(text=day, callback_data="ignore"))

    # Дни месяца
    first_day = date(year, month, 1)
    last_day = date(year, month + 1, 1) if month < 12 else date(year + 1, 1, 1)

    # Пустые кнопки для дней предыдущего месяца
    for _ in range((first_day.weekday() + 1) % 7):
        builder.add(InlineKeyboardButton(text=" ", callback_data="ignore"))

    # Кнопки с датами
    current_day = first_day
    while current_day < last_day:
        builder.add(InlineKeyboardButton(
            text=str(current_day.day),
            callback_data=f"date_{current_day}"
        ))
        current_day = current_day.replace(day=current_day.day + 1)

    # Навигация
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1

    builder.row(
        InlineKeyboardButton(
            text="⬅️",
            callback_data=f"nav_{prev_year}_{prev_month}"
        ),
        InlineKeyboardButton(
            text="➡️",
            callback_data=f"nav_{next_year}_{next_month}"
        )
    )

    builder.adjust(7)
    return builder.as_markup()


# ================== ОСНОВНЫЕ ФУНКЦИИ ================== #
def has_role(user_id: int, required_role: str) -> bool:
    current_role = users_roles.get(user_id, "user")
    role_priority = {"user": 0, "editor": 1, "admin": 2}
    return role_priority[current_role] >= role_priority[required_role]


# ================== ОБРАБОТЧИКИ КОМАНД ================== #
@dp.message(F.text == "/start")
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Добро пожаловать! Используйте кнопки ниже:",
        reply_markup=main_menu_kb()
    )


# Обработка inline-кнопок
@dp.callback_query(F.data == "my_role")
async def cb_my_role(callback: types.CallbackQuery):
    role = users_roles.get(callback.from_user.id, "user")
    await callback.message.edit_text(
        f"Ваша роль: <b>{ROLES[role]}</b>",
        reply_markup=main_menu_kb()
    )
    await callback.answer()


@dp.callback_query(F.data == "set_role")
async def cb_set_role(callback: types.CallbackQuery):
    if not has_role(callback.from_user.id, "admin"):
        await callback.answer("🚫 Недостаточно прав!", show_alert=True)
        return

    await callback.message.edit_text(
        "Выберите роль для назначения:",
        reply_markup=roles_kb()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("role_"))
async def cb_role_selected(callback: types.CallbackQuery, state: FSMContext):
    role = callback.data.split("_")[1]
    await state.update_data(selected_role=role)
    await callback.message.edit_text(
        "Введите ID пользователя:",
        reply_markup=None
    )
    await state.set_state(Form.waiting_for_role)
    await callback.answer()


@dp.message(Form.waiting_for_role)
async def process_user_id(message: types.Message, state: FSMContext):
    try:
        user_id = int(message.text)
        data = await state.get_data()
        role = data["selected_role"]
        users_roles[user_id] = role

        await message.answer(
            f"✅ Пользователю {user_id} назначена роль: <b>{ROLES[role]}</b>",
            reply_markup=main_menu_kb()
        )
        await state.clear()
    except ValueError:
        await message.answer("❌ Ошибка: ID должен быть числом")


@dp.callback_query(F.data == "set_date")
async def cb_set_date(callback: types.CallbackQuery):
    today = date.today()
    await callback.message.edit_text(
        "Выберите дату:",
        reply_markup=generate_calendar(today.year, today.month)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("date_"))
async def cb_date_selected(callback: types.CallbackQuery):
    selected_date = date.fromisoformat(callback.data[5:])
    user_dates[callback.from_user.id] = selected_date

    await callback.message.edit_text(
        f"📅 Выбрана дата: <b>{selected_date.strftime('%d.%m.%Y')}</b>",
        reply_markup=main_menu_kb()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("nav_"))
async def cb_navigate_calendar(callback: types.CallbackQuery):
    _, year, month = callback.data.split("_")
    await callback.message.edit_reply_markup(
        reply_markup=generate_calendar(int(year), int(month))
    )
    await callback.answer()


@dp.callback_query(F.data == "list_roles")
async def cb_list_roles(callback: types.CallbackQuery):
    if not has_role(callback.from_user.id, "editor"):
        await callback.answer("🚫 Недостаточно прав!", show_alert=True)
        return

    if not users_roles:
        text = "📭 Список ролей пуст"
    else:
        roles_list = "\n".join(
            f"• {uid}: {ROLES[r]}"
            for uid, r in users_roles.items()
        )
        text = f"📋 Список ролей:\n\n{roles_list}"

    await callback.message.edit_text(
        text,
        reply_markup=main_menu_kb()
    )
    await callback.answer()


# ================== ЗАПУСК БОТА ================== #
async def main():
    print("Бот запущен! Для остановки нажмите Ctrl+C")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())