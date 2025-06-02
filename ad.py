import asyncio
from aiogram import Bot, Dispatcher, types, F, exceptions
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.client.default import DefaultBotProperties
from aiogram.types import ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime

# Конфигурация
API_TOKEN = "8010104498:AAFu41LIYHrPWWl-kvT1pQ0GZrxE8AL0wZE"
ADMIN_USERNAME = "KitLittle"

# Инициализация
bot = Bot(
    token=API_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# База данных пользователей (временная)
users_db = {
    ADMIN_USERNAME: {"role": "admin", "name": "Главный администратор"}
}


# Состояния FSM для добавления пользователей
class AddUserStates(StatesGroup):
    WAITING_USERNAME = State()
    WAITING_ROLE = State()


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.username == ADMIN_USERNAME:
        add_user_btn = types.KeyboardButton(text="➕ Добавить пользователя")
        view_users_btn = types.KeyboardButton(text="👀 Просмотреть пользователей")
        markup = types.ReplyKeyboardMarkup(
            keyboard=[[add_user_btn], [view_users_btn]],
            resize_keyboard=True
        )
        await message.answer("✨ Добро пожаловать, администратор!", reply_markup=markup)
    else:
        # Проверка всех пользователей, даже неадминистраторов
        role = await get_user_role(message)
        if role:
            if role == "admin":
                await message.answer(f"✨ Привет, администратор! Ваша роль: {role}")
            else:
                await message.answer(f"📋 Привет! Ваша роль: {role}")
        else:
            await message.answer("📋 Привет! Вы не зарегистрированы в системе. Обратитесь к администратору.")


@dp.message(F.text == "➕ Добавить пользователя")
async def start_add_user(message: types.Message, state: FSMContext):
    """Начало процесса добавления нового пользователя"""
    if message.from_user.username != ADMIN_USERNAME:
        await message.answer("❌ Доступно только администратору")
        return

    await state.set_state(AddUserStates.WAITING_USERNAME)
    await message.answer("👤 Введите username пользователя (без '@'):")


@dp.message(AddUserStates.WAITING_USERNAME, F.text)
async def handle_username(message: types.Message, state: FSMContext):
    """Обработка введенного username"""
    if message.from_user.username != ADMIN_USERNAME:
        await message.answer("❌ Доступно только администратору", reply_markup=types.ReplyKeyboardRemove())
        await state.clear()
        return

    username = message.text.strip()
    if not username:
        await message.answer("❌ Введите username (без '@')", reply_markup=types.ReplyKeyboardRemove())
        return

    # Удаляем @ в начале, если он есть
    if username.startswith('@'):
        username = username[1:]

    # Проверяем, что username не занят
    if username in users_db and username != ADMIN_USERNAME:
        await message.answer(f"❌ Пользователь @{username} уже зарегистрирован с ролью {users_db[username]['role']}",
                             reply_markup=types.ReplyKeyboardRemove())
        await state.clear()
        return

    # Сохраняем username для дальнейшего использования
    await state.update_data(username=username)
    await state.set_state(AddUserStates.WAITING_ROLE)

    await message.answer("📋 Выберите роль для добавляемого пользователя:",
                         reply_markup=types.ReplyKeyboardMarkup(
                             keyboard=[
                                 [types.KeyboardButton(text="👨‍🎓 Student")],
                                 [types.KeyboardButton(text="👩‍🏫 Teacher")],
                                 [types.KeyboardButton(text="👑 Admin")],
                                 [types.KeyboardButton(text="🔙 Назад")]
                             ],
                             resize_keyboard=True
                         )
                         )


@dp.message(AddUserStates.WAITING_ROLE, F.text)
async def finish_add_user(message: types.Message, state: FSMContext):
    """Завершение процесса добавления пользователя"""
    if message.from_user.username != ADMIN_USERNAME:
        await message.answer("❌ Доступно только администратору", reply_markup=types.ReplyKeyboardRemove())
        await state.clear()
        return

    user_data = await state.get_data()
    username = user_data.get("username")

    role_text = message.text.strip().lower()
    if role_text == "student" or role_text == "👨‍🎓 student":
        role = "student"
    elif role_text == "teacher" or role_text == "👩‍🏫 teacher":
        role = "teacher"
    elif role_text == "admin" or role_text == "👑 admin":
        role = "admin"
    elif role_text == "🔙 назад" or role_text == "назад" or role_text == "back":
        await message.answer("❌ Отмена операции", reply_markup=types.ReplyKeyboardRemove())
        await state.clear()
        return

    if username is None or role is None:
        await message.answer("❌ Ошибка при завершении добавления", reply_markup=types.ReplyKeyboardRemove())
        await state.clear()
        return

    # Проверяем, что пользователь не пытается добавить самого себя
    if username == str(message.from_user.username) and message.from_user.username != ADMIN_USERNAME:
        await message.answer("❌ Вы не можете добавить самого себя!", reply_markup=types.ReplyKeyboardRemove())
        await state.clear()
        return

    # Создаем запись пользователя с его ролью в базе данных
    users_db[username] = {
        "role": role,
        "name": message.from_user.first_name or "Анонимный пользователь",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    }

    # Если это администратор, обновляем его данные
    if message.from_user.username == ADMIN_USERNAME:
        users_db[username] = {
            "role": "admin",
            "name": "Главный администратор",
            "created_at": users_db.get(username, {}).get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M"))
        }

    await message.answer(f"""
✅ Пользователь @{username} добавлен с ролью {role.capitalize()}

Вернуться в меню /start
""", reply_markup=types.ReplyKeyboardRemove())

    await state.clear()


async def get_user_role(message: types.Message):
    """Получить роль пользователя по его сообщению"""
    username = message.from_user.username

    if username in users_db:
        return users_db[username]["role"]

    # Если пользователь - администратор (по username)
    if username == ADMIN_USERNAME:
        return "admin"

    return None


@dp.message(F.text == "👀 Просмотреть пользователей")
async def cmd_view_users(message: types.Message):
    """Показать всех пользователей"""
    if message.from_user.username != ADMIN_USERNAME:
        await message.answer("❌ Доступно только администратору")
        return

    # Формируем список пользователей
    users_list = []
    for username, user_data in users_db.items():
        if username in (ADMIN_USERNAME, message.from_user.username):
            # Добавляем администратора и текущего пользователя отдельно
            role_text = user_data["role"].capitalize()
            if username == ADMIN_USERNAME:
                role_text = "👑 Администратор"
            if username == message.from_user.username and role_text != "👑 Администратор":
                role_text = "✨ " + role_text

            users_list.append(f"{role_text}:@{username} ({user_data['name']})")
        else:
            users_list.append(
                f"👤 Пользователь:@{username} ({user_data['name']}) - Роль: {user_data['role'].capitalize()}")

    # Добавляем информацию об администраторе отдельно
    if ADMIN_USERNAME in users_db:
        users_list.insert(0, f"👑 Администратор:@{ADMIN_USERNAME} ({users_db[ADMIN_USERNAME]['name']})")
    # И удаленный пользователь, отправивший сообщение
    current_user_role = await get_user_role(message) or "неизвестна"
    if message.from_user.username and message.from_user.username not in users_db:
        users_list.append(f"👤 Вы:@{message.from_user.username} - Роль: {current_user_role}")

    if not users_list:
        await message.answer("📋 Список пользователей пуст.")
        return

    # Отправка в несколько сообщений если нужно
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_users")
            ]
        ]
    )

    # Форматируем вывод
    content = "📋 Список пользователей системы:\n\n"
    content += "\n".join(users_list)

    await message.answer(content, reply_markup=markup, parse_mode=ParseMode.HTML)


@dp.callback_query(F.data == "refresh_users")
async def callback_refresh_users(call: types.CallbackQuery):
    """Кнопка обновления списка пользователей"""
    await call.answer()
    await cmd_view_users(await bot.send_message(call.message.chat.id, reply_markup=None))
    await call.message.delete()


# Запуск бота
async def main():
    print(f"Бот запущен. Администратор: @{ADMIN_USERNAME}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
