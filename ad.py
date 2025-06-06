import asyncio
import psycopg2
from aiogram import Bot, Dispatcher, types, F, exceptions
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.client.default import DefaultBotProperties
from aiogram.types import ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime, date
from psycopg2 import sql, Error
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import InlineQueryResultArticle, InputTextMessageContent
from aiogram.fsm.state import State, StatesGroup

# Конфигурация
API_TOKEN = "8010104498:AAFu41LIYHrPWWl-kvT1pQ0GZrxE8AL0wZE"
ADMIN_USERNAME = ""
DATE_FORMAT = "%d.%m.%Y"
# Настройки БД
DB_CONFIG = {
    "dbname": "postgres",
    "user": "postgres",
    "password": "admin",
    "host": "localhost",
    "port": "5433"
}
# Инициализация
bot = Bot(
    token=API_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()


# Функции для работы с БД
def get_db_connection():
    """Установка соединения с PostgreSQL"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Error as e:
        print(f"Ошибка подключения к PostgreSQL: {e}")
        return None





# Состояния FSM для добавления пользователей
class AddUserStates(StatesGroup):
    WAITING_USERNAME = State()
    WAITING_ROLE = State()

class ScheduleStates(StatesGroup):
    WAITING_SEMESTER_NAME = State()
    WAITING_START_DATE = State()
    WAITING_END_DATE = State()
    WAITING_PRACTICE_NAME = State()
    WAITING_PRACTICE_DESC = State()
    WAITING_TEACHER = State()
    CONFIRMATION = State()
class ScheduleDistribution(StatesGroup):
    select_schedule = State()
    confirm_distribution = State()
class ApplicationStates(StatesGroup):
    WAITING_APPLICATION_FILE = State()
    WAITING_APPLICATION_CONFIRM = State()

# Добавляем новое состояние для процесса назначения руководителя
class AssignTeacherStates(StatesGroup):
    WAITING_STUDENT_SELECTION = State()
    WAITING_TEACHER_SELECTION = State()
    CONFIRM_ASSIGNMENT = State()

@dp.message(F.text == "📅 Добавить расписание")
async def cmd_add_schedule(message: types.Message, state: FSMContext):
    """Иницирует процесс добавления расписания"""
    if not await get_user_role_by_username(message.from_user.username):
        await message.answer("❌ Доступно только методистам", reply_markup=types.ReplyKeyboardRemove())
        await state.clear()
        return



    await message.answer(
        "Введите название семестра (например: 'Осенний семестр 2025'):",

    )
    await state.set_state(ScheduleStates.WAITING_SEMESTER_NAME)




@dp.message(ScheduleStates.WAITING_SEMESTER_NAME)
async def process_semester_name(message: types.Message, state: FSMContext):
    """Обрабатывает название семестра"""
    if len(message.text) > 100:
        await message.answer("❌ Слишком длинное название (макс. 100 символов). Введите снова:")
        return

    await state.update_data(semester_name=message.text)
    await message.answer("Введите дату начала семестра (в формате ДД.ММ.ГГГГ):")
    await state.set_state(ScheduleStates.WAITING_START_DATE)


@dp.message(ScheduleStates.WAITING_START_DATE)
async def process_start_date(message: types.Message, state: FSMContext):
    """Обрабатывает дату начала семестра"""
    try:
        start_date = datetime.strptime(message.text, "%d.%m.%Y").date()

        await state.update_data(start_date=start_date)
        await message.answer("Введите дату окончания семестра (в формате ДД.ММ.ГГГГ):")
        await state.set_state(ScheduleStates.WAITING_END_DATE)
    except ValueError:
        await message.answer("❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ. Введите снова:")


@dp.message(ScheduleStates.WAITING_END_DATE)
async def process_end_date(message: types.Message, state: FSMContext):
    """Обрабатывает дату окончания семестра"""
    try:
        data = await state.get_data()
        start_date = data.get('start_date')
        end_date = datetime.strptime(message.text, "%d.%m.%Y").date()

        if end_date <= start_date:
            await message.answer("❌ Дата окончания должна быть позже даты начала. Введите снова:")
            return

        await state.update_data(end_date=end_date)
        await message.answer("Введите название практики (например: 'Ознакомительная практика'):")
        await state.set_state(ScheduleStates.WAITING_PRACTICE_NAME)
    except ValueError:
        await message.answer("❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ. Введите снова:")


@dp.message(ScheduleStates.WAITING_PRACTICE_NAME)
async def process_practice_name(message: types.Message, state: FSMContext):
    """Обрабатывает название практики"""
    if len(message.text) > 200:
        await message.answer("❌ Слишком длинное название (макс. 200 символов). Введите снова:")
        return

    await state.update_data(practice_name=message.text)
    await message.answer("Введите описание практики (можно пропустить, отправив '-'):")
    await state.set_state(ScheduleStates.WAITING_PRACTICE_DESC)

async def get_teachers_list() -> list[tuple]:
    """Возвращает список преподавателей из БД"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT username,full_name 
            FROM users 
            WHERE role = 'teacher' 
            ORDER BY username
        """)
        teachers = cur.fetchall()
        cur.close()
        return teachers
    except Error as e:
        print(f"Ошибка получения списка преподавателей: {e}")
        return []
    finally:
        if conn:
            conn.close()


@dp.message(ScheduleStates.WAITING_PRACTICE_DESC)
async def process_practice_desc(message: types.Message, state: FSMContext):
    """Обрабатывает описание практики и переходит к выбору преподавателя"""
    practice_desc = None if message.text == "-" else message.text
    await state.update_data(practice_description=practice_desc)

    teachers = await get_teachers_list()
    if not teachers:
        await message.answer("❌ Нет доступных преподавателей", reply_markup=types.ReplyKeyboardRemove())
        await state.clear()
        return

    # Создаем inline-клавиатуру для выбора преподавателя
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{full_name} (@{username})", callback_data=f"teacher_{username}")]
        for username, full_name in teachers
    ])

    await message.answer(
        "👨‍🏫 Выберите преподавателя:",
        reply_markup=keyboard
    )
    await state.set_state(ScheduleStates.WAITING_TEACHER)




@dp.inline_query()
async def inline_teacher_search(inline_query: types.InlineQuery):
    """Обработка inline запроса для поиска преподавателей"""
    query = inline_query.query.lower().strip()
    if not query:
        return

    teachers = await get_teachers_list()
    results = [
        InlineQueryResultArticle(
            id=username,
            title=full_name,
            input_message_content=InputTextMessageContent(
                message_text=f"Выбран преподаватель: {full_name}"
            )
        )
        for username, full_name in teachers
        if query in full_name.lower() or query in username.lower()
    ]



    await inline_query.answer(results)




# Обработчик выбора преподавателя через inline-кнопки
@dp.callback_query(ScheduleStates.WAITING_TEACHER, F.data.startswith("teacher_"))
async def process_teacher_selection(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор преподавателя из inline-клавиатуры"""
    username = callback.data.split("_")[1]
    teacher_data = next((t for t in await get_teachers_list() if t[0] == username), None)

    if not teacher_data:
        await callback.answer("❌ Преподаватель не найден")
        return

    username, full_name = teacher_data
    await state.update_data(responsible_teacher=username)

    # Формируем подтверждение с данными
    data = await state.get_data()
    confirm_text = (
        "📋 Подтвердите данные расписания:\n\n"
        f"Семестр: {data['semester_name']}\n"
        f"Дата начала: {data['start_date'].strftime('%d.%m.%Y')}\n"
        f"Дата окончания: {data['end_date'].strftime('%d.%m.%Y')}\n"
        f"Практика: {data['practice_name']}\n"
        f"Описание: {data['practice_description'] or 'не указано'}\n"
        f"Ответственный: {full_name} (@{username})\n\n"
        "Всё верно?"
    )

    # Создаем inline-клавиатуру для подтверждения
    confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_schedule"),
            InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_schedule")
        ]
    ])

    await callback.message.edit_text(confirm_text, reply_markup=confirm_keyboard)
    await state.set_state(ScheduleStates.CONFIRMATION)
    await callback.answer()


@dp.callback_query(ScheduleStates.CONFIRMATION, F.data == "confirm_schedule")
async def confirm_schedule(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает подтверждение создания расписания"""
    data = await state.get_data()

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO schedule 
            (semester_name, start_date, end_date, practice_name, practice_description, responsible_teacher, created_by) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (
                data['semester_name'],
                data['start_date'],
                data['end_date'],
                data['practice_name'],
                data['practice_description'],
                data['responsible_teacher'],
                callback.from_user.username
            )
        )
        conn.commit()

        # Удаляем клавиатуру и редактируем сообщение
        await callback.message.edit_text(
            "✅ Расписание успешно добавлено!\n\n"
            "Вы можете добавить ещё одно расписание или вернуться в меню /start",
            reply_markup=None  # Удаляем inline-клавиатуру
        )

        # Отправляем новое сообщение с удалением reply-клавиатуры
        await callback.message.answer(
            "Вы можете продолжить работу",
            reply_markup=types.ReplyKeyboardRemove()
        )
    except Error as e:
        await callback.message.edit_text(
            "❌ Ошибка при сохранении расписания",
            reply_markup=None
        )
        print(f"Ошибка сохранения расписания: {e}")
    finally:
        if conn:
            conn.close()
        await state.clear()
    await callback.answer()


@dp.message(ScheduleStates.CONFIRMATION)
async def process_confirmation(message: types.Message, state: FSMContext):
    """Обрабатывает подтверждение"""
    if message.text.lower() not in ["да", "yes", "✅ да"]:
        await message.answer("❌ Добавление отменено", reply_markup=types.ReplyKeyboardRemove())
        await state.clear()
        return

    data = await state.get_data()

    # Сохраняем в базу данных
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO schedule 
            (semester_name, start_date, end_date, practice_name, practice_description, responsible_teacher, created_by) 
            VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (
                data['semester_name'],
                data['start_date'],
                data['end_date'],
                data['practice_name'],
                data['practice_description'],
                data['responsible_teacher'],
                message.from_user.username
            )
        )
        conn.commit()

        await message.answer(
            "✅ Расписание успешно добавлено!\n\n"
            "Вы можете добавить ещё одно расписание или вернуться в меню /start",
            reply_markup=types.ReplyKeyboardRemove()
        )
    except Error as e:
        await message.answer(
            "❌ Ошибка при сохранении расписания. Попробуйте позже.",
            reply_markup=types.ReplyKeyboardRemove()
        )
        print(f"Ошибка сохранения расписания: {e}")
    finally:
        if conn:
            conn.close()
        await state.clear()


dp.callback_query(ScheduleStates.CONFIRMATION, F.data == "cancel_schedule")


async def cancel_schedule(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает отмену создания расписания"""
    await callback.message.edit_text(
        "❌ Добавление расписания отменено",
        reply_markup=None  # Удаляем inline-клавиатуру
    )

    # Отправляем новое сообщение с удалением reply-клавиатуры
    await callback.message.answer(
        "Вы можете начать заново",
        reply_markup=types.ReplyKeyboardRemove()
    )

    await state.clear()
    await callback.answer()


async def add_user_to_db(username: str, role: str, full_name: str):
    """Добавление пользователя в БД"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (username, role, full_name) VALUES (%s, %s, %s) ON CONFLICT (username) DO UPDATE SET role = EXCLUDED.role, full_name = EXCLUDED.full_name",
            (username, role, full_name)
        )
        conn.commit()
        cur.close()
        return True
    except Error as e:
        print(f"Ошибка добавления пользователя: {e}")
        return False
    finally:
        if conn is not None:
            conn.close()

async def get_all_users():
    """Получение списка всех пользователей"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT username, role, full_name FROM users ORDER BY created_at DESC")
        users = cur.fetchall()
        cur.close()
        return users
    except Error as e:
        print(f"Ошибка получения пользователей: {e}")
        return []
    finally:
        if conn is not None:
            conn.close()


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Обновляем запись пользователя с chat_id
        cur.execute("""
                INSERT INTO users (username, role, full_name, chat_id)
                VALUES (%s, 'student', %s, %s)
                ON CONFLICT (username) 
                DO UPDATE SET 
                    chat_id = EXCLUDED.chat_id,
                    full_name = COALESCE(EXCLUDED.full_name, users.full_name)
            """, (
            message.from_user.username,
            message.from_user.full_name or "Аноним",
            message.chat.id
        ))
        conn.commit()
    except Error as e:
        print(f"Ошибка сохранения chat_id: {e}")
    finally:
        if conn:
            conn.close()
    user_role = await get_user_role_by_username(message.from_user.username)

    # Общая кнопка для всех ролей
    common_buttons = [types.KeyboardButton(text="📋 Посмотреть расписание")], [KeyboardButton(text="🚀 /start")]

    # Администратор
    if message.from_user.username == ADMIN_USERNAME:
        markup = types.ReplyKeyboardMarkup(
            keyboard=[
                [
                    types.KeyboardButton(text="➕ Добавить пользователя"),
                    types.KeyboardButton(text="👀 Просмотреть пользователей")
                ],
                [
                    types.KeyboardButton(text="📅 Добавить расписание"),
                    types.KeyboardButton(text="📋 Посмотреть расписание"),
                    types.KeyboardButton(text="📢 Рассылка студентам")
                ]
            ],
            resize_keyboard=True
        )
        await message.answer("✨ Добро пожаловать, администратор!", reply_markup=markup)

    # Методист
    elif user_role == "methodist":
        markup = types.ReplyKeyboardMarkup(
            keyboard=[
                [
                    types.KeyboardButton(text="📅 Добавить расписание"),
                    types.KeyboardButton(text="📢 Рассылка студентам")
                ],
                [
                    types.KeyboardButton(text="📋 Посмотреть расписание"),
                    types.KeyboardButton(text="👨‍🏫 Преподаватели")
                ],
                [
                    types.KeyboardButton(text="👨‍🎓 Список студентов"),
                    types.KeyboardButton(text="⚙️ Настройки")
                ],
            ],
            resize_keyboard=True
        )
        await message.answer("📚 Добро пожаловать, методист!", reply_markup=markup)

    # Остальные роли
    else:
        markup = types.ReplyKeyboardMarkup(
            keyboard=[
                [
                    types.KeyboardButton(text="📋 Посмотреть расписание"),
                    types.KeyboardButton(text="👨‍🏫 Мой преподаватель")
                ],
                [types.KeyboardButton(text="📄 Подать заявление")]
            ],
            resize_keyboard=True
        )
        if user_role:
            await message.answer(f"📋 Привет! Ваша роль: {user_role}", reply_markup=markup)
        else:
            await message.answer("❌ Вы не зарегистрированы в системе", reply_markup=markup)


@dp.message(F.text == "⚙️ Настройки")
async def settings_menu(message: types.Message):
    """Меню настроек с кнопкой старт"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Профиль")],
            [KeyboardButton(text="🔔 Уведомления")],
            [KeyboardButton(text="/start")],  # Кнопка старт
            [KeyboardButton(text="🔙 Главное меню")]
        ],
        resize_keyboard=True,
        is_persistent=True
    )

    await message.answer(
        "⚙️ Настройки системы:",
        reply_markup=keyboard
    )


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

    # Проверяем, что username не занят через БД
    existing_user = await get_user_role_by_username(username)
    if existing_user and username != ADMIN_USERNAME:
        await message.answer(f"❌ Пользователь @{username} уже зарегистрирован с ролью {existing_user}",
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
                                 [types.KeyboardButton(text="📚 Methodist")],  # Новая кнопка
                                 [types.KeyboardButton(text="👑 Admin")],
                                 [types.KeyboardButton(text="🔙 Назад")]
                             ],
                             resize_keyboard=True
                         ))


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
    elif role_text == "methodist" or role_text == "📚 methodist" or role_text == "методист":
        role = "methodist"
    elif role_text == "🔙 назад" or role_text == "назад" or role_text == "back":
        await message.answer("❌ Отмена операции", reply_markup=types.ReplyKeyboardRemove())
        await state.clear()
        return
    else:
        await message.answer("❌ Неизвестная роль", reply_markup=types.ReplyKeyboardRemove())
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

    # Добавляем пользователя в БД
    full_name = message.from_user.first_name or "Анонимный пользователь"
    success = await add_user_to_db(username, role, full_name)

    if not success:
        await message.answer("❌ Ошибка при добавлении пользователя в базу данных",
                             reply_markup=types.ReplyKeyboardRemove())
        await state.clear()
        return

    await message.answer(f"""
✅ Пользователь @{username} добавлен с ролью {role.capitalize()}

Вернуться в меню /start
""", reply_markup=types.ReplyKeyboardRemove())

    await state.clear()


async def get_user_role_by_username(username: str):
    """Получить роль пользователя по username из БД"""
    if not username:
        return None
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT role FROM users WHERE username = %s", (username,))
        result = cur.fetchone()
        cur.close()
        return result[0] if result else None
    except Error as e:
        print(f"Ошибка получения роли: {e}")
        return None
    finally:
        if conn is not None:
            conn.close()



@dp.message(F.text == "👀 Просмотреть пользователей")
async def cmd_view_users(message: types.Message):
    """Показать всех пользователей без кнопки обновления"""
    if message.from_user.username != ADMIN_USERNAME:
        await message.answer("❌ Доступно только администратору")
        return

    users = await get_all_users()
    if not users:
        await message.answer("📋 Список пользователей пуст.")
        return

    # Формируем список одним блоком
    content = "📋 Список пользователей системы:\n\n" + "\n".join(
        f"👑 Администратор:@{u} ({n})" if u == ADMIN_USERNAME else
        f"✨ {r.capitalize()}:@{u} ({n})" if u == message.from_user.username else
        f"👤 Пользователь:@{u} ({n}) - Роль: {r.capitalize()}"
        for u, r, n in users
    )

    await message.answer(
        content,
        parse_mode=ParseMode.HTML
    )

async def get_schedule_list() -> list[tuple]:
    """Возвращает список расписаний из БД"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                semester_name, 
                start_date, 
                end_date, 
                practice_name,
                responsible_teacher
            FROM schedule 
            ORDER BY start_date DESC
        """)
        schedule = cur.fetchall()
        cur.close()
        return schedule
    except Error as e:
        print(f"Ошибка получения списка расписаний: {e}")
        return []
    finally:
        if conn:
            conn.close()


@dp.message(F.text == "📋 Посмотреть расписание")
async def cmd_view_schedule(message: types.Message):
    """Показывает список доступных расписаний"""
    schedule = await get_schedule_list()
    user_role = await get_user_role_by_username(message.from_user.username)

    if not schedule:
        await message.answer("📅 Расписаний пока нет.")
        return

    response = "📅 Доступные расписания:\n\n"

    for idx, (semester, start_date, end_date, practice, teacher) in enumerate(schedule, 1):
        response += (
            f"{idx}. {semester}\n"
            f"   📆 Период: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}\n"
            f"   🏫 Практика: {practice}\n"
            f"   👨‍🏫 Ответственный: @{teacher}\n\n"
        )

        # Для студентов добавляем кнопку подачи заявления
        if user_role == 'student':
            markup = types.ReplyKeyboardMarkup(
                keyboard=[
                    [types.KeyboardButton(text="📄 Подать заявление")],
                    [types.KeyboardButton(text="🔙 Назад")]
                ],
                resize_keyboard=True
            )
            await message.answer(response, reply_markup=markup)
        else:
            await message.answer(response)
async def get_students_list() -> list[str]:
    """Возвращает список username студентов"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
                SELECT username, chat_id 
                FROM users 
                WHERE role = 'student' AND chat_id IS NOT NULL
            """)
        return cur.fetchall()
    except Error as e:
        print(f"Ошибка получения списка студентов: {e}")
        return []
    finally:
        if conn:
            conn.close()


@dp.message(F.text == "📢 Рассылка студентам")
async def start_schedule_distribution(message: types.Message, state: FSMContext):
    schedules = await get_schedule_list()

    if not schedules:
        await message.answer("❌ Нет доступных расписаний для рассылки")
        return

    buttons = []
    for schedule in schedules:
        buttons.append([types.KeyboardButton(
            text=f"📅 {schedule[0]} ({schedule[1].strftime('%d.%m.%Y')}-{schedule[2].strftime('%d.%m.%Y')})"
        )])

    markup = types.ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    await message.answer("Выберите расписание для рассылки:", reply_markup=markup)
    await state.set_state(ScheduleDistribution.select_schedule)


@dp.message(ScheduleDistribution.select_schedule)
async def select_schedule_for_distribution(message: types.Message, state: FSMContext):
    schedule_text = message.text.replace("📅 ", "")
    await state.update_data(selected_schedule=schedule_text)

    markup = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="✅ Да, отправить")],
            [types.KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )
    await message.answer(
        f"Вы выбрали: {schedule_text}\n"
        "Отправить всем студентам?",
        reply_markup=markup
    )
    await state.set_state(ScheduleDistribution.confirm_distribution)


@dp.message(ScheduleDistribution.confirm_distribution, F.text == "✅ Да, отправить")
async def confirm_distribution(message: types.Message, state: FSMContext):
    data = await state.get_data()
    schedule_text = data['selected_schedule']
    students = await get_students_list()

    if not students:
        await message.answer("❌ Нет студентов для рассылки")
        await state.clear()
        return

    success = 0
    failed = []

    for username, chat_id in students:
        try:
            await message.bot.send_message(
                chat_id=chat_id,  # Используем числовой chat_id
                text=f"📢 Практики, предстоящие в этом семестре:\n\n{schedule_text}"
            )
            success += 1
        except Exception as e:
            failed.append(f"{username}: {str(e)}")
            continue

    # Отчёт администратору
    report = (
        f"📊 Результаты рассылки:\n"
        f"• Успешно: {success}\n"
        f"• Ошибки: {len(failed)}"
    )

    if failed:
        report += "\n\nОшибки:\n" + "\n".join(f"→ {f}" for f in failed[:5])  # Показываем первые 5 ошибок
        if len(failed) > 5:
            report += f"\n...и ещё {len(failed) - 5} ошибок"

    await message.answer(report, reply_markup=types.ReplyKeyboardRemove())
    await state.clear()

@dp.message(ScheduleDistribution.confirm_distribution, F.text == "❌ Отмена")
async def cancel_distribution(message: types.Message, state: FSMContext):
    await message.answer("❌ Рассылка отменена", reply_markup=types.ReplyKeyboardRemove())
    await state.clear()

@dp.callback_query(F.data == "unassign_teacher_menu")
async def unassign_teacher_menu(callback: types.CallbackQuery):
    """Меню выбора студента для снятия преподавателя (только студенты с преподавателями)"""
    students_with_teachers = await get_students_with_teachers_only()

    if not students_with_teachers:
        await callback.answer("ℹ️ Нет студентов с назначенными преподавателями")
        return

    # Формируем список с информацией о студентах и их преподавателях
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"👨‍🎓 {student_name} → 👨‍🏫 {teacher_name}",
            callback_data=f"confirm_unassign_{student_username}"
        )]
        for student_username, student_name, _, teacher_name in
        students_with_teachers
    ] + [
        [InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="teacher_management"
        )]
    ])

    await callback.message.edit_text(
        "👨‍🎓 Выберите студента для снятия преподавателя:\n"
        "(Формат: Студент → Текущий преподаватель)",
        reply_markup=keyboard
    )
    await callback.answer()

@dp.message(F.text == "👨‍🎓 Список студентов")
async def show_all_students(message: types.Message):
    """Показывает список студентов с кнопками для назначения преподавателя"""
    user_role = await get_user_role_by_username(message.from_user.username)


    students = await get_all_students_with_teachers()

    if not students:
        await message.answer("📋 Список студентов пуст.")
        return

    # Группировка по преподавателям
    grouped = {}
    for username, full_name, teacher_username, teacher_name in students:
        key = teacher_name or "❌ Без преподавателя"
        if key not in grouped:
            grouped[key] = []
        grouped[key].append((username, full_name))

    # Формируем сообщение
    response = ["📊 <b>Полный список студентов:</b>"]
    for teacher, student_list in grouped.items():
        response.append(f"\n👨‍🏫 <b>{teacher}</b>:")
        for username, full_name in student_list:
            response.append(f"• {full_name} (@{username})")

    # Добавляем кнопки действий
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔄 Назначить преподавателя",
                callback_data="assign_teacher_menu"
            ),
            InlineKeyboardButton(
                text="❌ Снять преподавателя",
                callback_data="unassign_teacher_menu"
            ),
            InlineKeyboardButton(
                text="🔄 Обновить список",
                callback_data="refresh_students"
            )
        ]
    ])

    await message.answer(
        "\n".join(response),
        parse_mode="HTML",
        reply_markup=keyboard
    )



async def get_current_teacher(student_username: str) -> dict:
    """Возвращает текущего преподавателя студента"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT u.username, u.full_name
            FROM users u
            JOIN student_teacher st ON u.username = st.teacher_username
            WHERE st.student_username = %s
        """, (student_username,))
        result = cur.fetchone()
        return {
            'username': result[0],
            'full_name': result[1]
        } if result else None
    except Error as e:
        print(f"Ошибка получения преподавателя: {e}")
        return None
    finally:
        if conn:
            conn.close()
@dp.callback_query(F.data == "teacher_management")
async def teacher_management(callback: types.CallbackQuery):
    """Возврат в меню управления преподавателями"""
    await show_all_students(callback.message)
    await callback.answer()


@dp.callback_query(F.data.startswith("confirm_unassign_"))
async def confirm_unassign(callback: types.CallbackQuery):
    """Упрощенное подтверждение снятия преподавателя"""
    try:
        student_username = callback.data.split("_")[2]
        print(f"[DEBUG] Подтверждение снятия для @{student_username}")

        # Получаем данные один раз
        student_info = await get_user_info(student_username)
        current_teacher = await get_current_teacher(student_username)

        if not student_info:
            await callback.answer("❌ Студент не найден", show_alert=True)
            return await callback.message.edit_text(
                "❌ Студент не найден",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="Назад", callback_data="teacher_management")
                ]])
            )

        if not current_teacher:
            await callback.answer("❌ Нет преподавателя", show_alert=True)
            return await callback.message.edit_text(
                f"ℹ️ У @{student_username} нет преподавателя",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="Назад", callback_data="teacher_management")
                ]])
            )

        # Формируем сообщение
        text = (
            f"⚠️ Подтвердите снятие преподавателя\n\n"
            f"Студент: @{student_username}\n"
            f"Преподаватель: {current_teacher['full_name']} (@{current_teacher['username']})"
        )

        # Простые кнопки подтверждения/отмены
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Снять",
                    callback_data=f"execute_unassign_{student_username}"
                ),
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="teacher_management"
                )
            ]
        ])

        await callback.message.edit_text(text, reply_markup=markup)
        await callback.answer()

    except Exception as e:
        print(f"[ERROR] Ошибка подтверждения: {str(e)}")
        await callback.answer("❌ Ошибка подтверждения", show_alert=True)


@dp.callback_query(F.data.startswith("execute_unassign_"))
async def execute_unassign(callback: types.CallbackQuery):
    """Фактическое снятие преподавателя"""
    try:
        student_username = callback.data.split("_")[2]

        # Проверяем существование студента
        student_info = await get_user_info(student_username)
        if not student_info:
            await callback.answer("❌ Студент не найден", show_alert=True)
            return await callback.message.edit_text(
                "❌ Студент не найден",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="Назад", callback_data="teacher_management")
                ]])
            )

        # Проверяем текущего преподавателя
        current_teacher = await get_current_teacher(student_username)
        if not current_teacher:
            await callback.answer("ℹ️ У студента нет преподавателя", show_alert=True)
            return await callback.message.edit_text(
                f"ℹ️ У @{student_username} нет преподавателя",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="Назад", callback_data="teacher_management")
                ]])
            )

        # Удаляем связь из базы данных
        conn = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                DELETE FROM student_teacher 
                WHERE student_username = %s
                RETURNING 1
            """, (student_username,))

            if not cur.fetchone():
                await callback.answer("❌ Не удалось снять преподавателя", show_alert=True)
                return

            conn.commit()

            # Уведомляем студента
            student_chat_id = await get_user_chat_id(student_username)
            if student_chat_id:
                try:
                    await bot.send_message(
                        chat_id=student_chat_id,
                        text=f"ℹ️ С вас снят руководитель практики: {current_teacher['full_name']} (@{current_teacher['username']})"
                    )
                except Exception as e:
                    print(f"Ошибка уведомления студента: {e}")

            # Обновляем сообщение
            await callback.message.edit_text(
                f"✅ Преподаватель {current_teacher['full_name']} снят со студента @{student_username}\n"
                f"Время: {datetime.now().strftime('%H:%M:%S')}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="В меню", callback_data="teacher_management")
                ]])
            )

        except Error as e:
            print(f"[DB ERROR] Ошибка снятия преподавателя: {e}")
            await callback.message.edit_text(
                "❌ Ошибка при снятии преподавателя",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="Повторить", callback_data=f"confirm_unassign_{student_username}"),
                    InlineKeyboardButton(text="Отмена", callback_data="teacher_management")
                ]])
            )
        finally:
            if conn:
                conn.close()

    except Exception as e:
        print(f"[ERROR] Ошибка снятия: {str(e)}")
        await callback.answer("❌ Ошибка", show_alert=True)


@dp.callback_query(F.data.startswith("cancel_unassign_"))
async def cancel_unassign(callback: types.CallbackQuery):
    """Отмена операции снятия преподавателя"""
    student_username = callback.data.split("_")[2]

    await callback.message.edit_text(
        f"❎ Снятие преподавателя для @{student_username} отменено",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Вернуться к управлению", callback_data="teacher_management")
        ]])
    )
    await callback.answer("Операция отменена")


@dp.callback_query(F.data.startswith("refresh_unassign_"))
async def refresh_unassign(callback: types.CallbackQuery):
    """Обновление данных перед снятием преподавателя"""
    try:
        student_username = callback.data.split("_")[2]
        print(f"[DEBUG] Обновление данных для @{student_username}")

        # Получаем актуальные данные
        student_info = await get_user_info(student_username)
        current_teacher = await get_current_teacher(student_username)

        if not student_info:
            await callback.answer("❌ Студент не найден", show_alert=True)
            return await callback.message.edit_text(
                "❌ Студент не найден",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="Назад", callback_data="unassign_teacher_menu")
                ]])
            )

        if not current_teacher:
            await callback.answer("❌ Нет преподавателя", show_alert=True)
            return await callback.message.edit_text(
                f"ℹ️ У @{student_username} нет назначенного преподавателя",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="Проверить снова", callback_data=f"refresh_unassign_{student_username}"),
                    InlineKeyboardButton(text="Назад", callback_data="unassign_teacher_menu")
                ]])
            )

        # Обновляем сообщение с актуальными данными
        await callback.message.edit_text(
            f"🔄 Данные обновлены\n\n"
            f"Студент: @{student_username}\n"
            f"Текущий преподаватель: {current_teacher['full_name']} (@{current_teacher['username']})\n\n"
            f"Подтвердите снятие преподавателя:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Да, снять", callback_data=f"execute_unassign_{student_username}"),
                    InlineKeyboardButton(text="❌ Нет", callback_data=f"cancel_unassign_{student_username}")
                ],
                [
                    InlineKeyboardButton(text="🔄 Ещё раз обновить",
                                         callback_data=f"refresh_unassign_{student_username}")
                ]
            ])
        )
        await callback.answer("Данные обновлены")

    except Exception as e:
        print(f"[ERROR] Ошибка обновления: {str(e)}")
        await callback.message.edit_text(
            "❌ Ошибка обновления данных",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="Попробовать снова", callback_data=f"refresh_unassign_{student_username}"),
                InlineKeyboardButton(text="Отмена", callback_data="unassign_teacher_menu")
            ]])
        )
        await callback.answer("❌ Ошибка обновления", show_alert=True)



async def get_all_students_with_teachers() -> list[tuple]:
    """Возвращает полный список студентов (с преподавателями и без)"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                s.username as student_username,
                s.full_name as student_name,
                t.username as teacher_username, 
                t.full_name as teacher_name
            FROM users s
            LEFT JOIN student_teacher st ON s.username = st.student_username
            LEFT JOIN users t ON st.teacher_username = t.username
            WHERE s.role = 'student'
            ORDER BY s.username
        """)
        return cur.fetchall()
    except Error as e:
        print(f"Ошибка получения списка студентов: {e}")
        return []
    finally:
        if conn:
            conn.close()

async def get_students_with_teachers_only() -> list[tuple]:
    """Возвращает только студентов с преподавателями"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                s.username as student_username,
                s.full_name as student_name,
                t.username as teacher_username, 
                t.full_name as teacher_name
            FROM users s
            JOIN student_teacher st ON s.username = st.student_username
            JOIN users t ON st.teacher_username = t.username
            WHERE s.role = 'student'
            ORDER BY s.username
        """)
        return cur.fetchall()
    except Error as e:
        print(f"Ошибка получения списка студентов с преподавателями: {e}")
        return []
    finally:
        if conn:
            conn.close()


@dp.callback_query(F.data == "assign_teacher_menu")
async def assign_teacher_menu(callback: types.CallbackQuery):
    """Меню выбора студента для назначения преподавателя"""
    students = await get_students_without_teachers()

    if not students:
        await callback.answer("✅ У всех студентов есть преподаватели")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{full_name} (@{username})",
            callback_data=f"assign_student_{username}"
        )]
        for username, full_name in students
    ])

    await callback.message.edit_text(
        "👨‍🎓 Выберите студента для назначения преподавателя:",
        reply_markup=keyboard
    )
    await callback.answer()
@dp.callback_query(F.data.startswith("assign_student_"))
async def select_student_for_teacher(callback: types.CallbackQuery):
    """Обрабатывает выбор студента"""
    student_username = callback.data.split("_")[2]
    teachers = await get_teachers_list()

    if not teachers:
        await callback.answer("❌ Нет доступных преподавателей")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{full_name} (@{username})",
            callback_data=f"confirm_assign_{student_username}_{username}"
        )]
        for username, full_name in teachers
    ])

    await callback.message.edit_text(
        f"👨‍🏫 Выберите преподавателя для студента @{student_username}:",
        reply_markup=keyboard
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("confirm_assign_"))
async def confirm_teacher_assignment(callback: types.CallbackQuery):
    """Подтверждает назначение преподавателя"""
    _, _, student_username, teacher_username = callback.data.split("_")

    # Получаем информацию о пользователях
    student_info = await get_user_info(student_username)
    teacher_info = await get_user_info(teacher_username)

    if not student_info or not teacher_info:
        await callback.answer("❌ Ошибка: пользователь не найден")
        return

    # Сохраняем в базу данных
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Удаляем предыдущее назначение (если есть)
        cur.execute("""
            DELETE FROM student_teacher 
            WHERE student_username = %s
        """, (student_username,))

        # Добавляем новое назначение
        cur.execute("""
            INSERT INTO student_teacher (student_username, teacher_username)
            VALUES (%s, %s)
        """, (student_username, teacher_username))

        conn.commit()

        # Отправляем уведомления
        await notify_assignment(student_username, teacher_username)

        await callback.message.edit_text(
            f"✅ Преподаватель @{teacher_username} назначен для студента @{student_username}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="🔙 К списку студентов",
                    callback_data="refresh_students"
                )
            ]])
        )

    except Error as e:
        await callback.message.edit_text(
            "❌ Ошибка при сохранении назначения",
            reply_markup=None
        )
        print(f"Ошибка назначения преподавателя: {e}")
    finally:
        if conn:
            conn.close()
    await callback.answer()

async def notify_assignment(student_username: str, teacher_username: str):
    """Отправляет уведомления студенту и преподавателю"""
    student_chat_id = await get_user_chat_id(student_username)
    teacher_chat_id = await get_user_chat_id(teacher_username)

    student_info = await get_user_info(student_username)
    teacher_info = await get_user_info(teacher_username)

    # Уведомление студенту
    if student_chat_id:
        try:
            await bot.send_message(
                chat_id=student_chat_id,
                text=f"👨‍🏫 Вам назначен руководитель: {teacher_info['full_name']} (@{teacher_username})"
            )
        except Exception as e:
            print(f"Ошибка уведомления студента: {e}")

    # Уведомление преподавателю
    if teacher_chat_id:
        try:
            await bot.send_message(
                chat_id=teacher_chat_id,
                text=f"👨‍🎓 Вам назначен студент: {student_info['full_name']} (@{student_username})"
            )
        except Exception as e:
            print(f"Ошибка уведомления преподавателя: {e}")

async def delete_assignment(student_username: str) -> bool:
    """Удаляет связь студент-преподаватель"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            DELETE FROM student_teacher 
            WHERE student_username = %s
            RETURNING 1
        """, (student_username,))
        conn.commit()
        return bool(cur.fetchone())
    except Error as e:
        print(f"[DB ERROR] Ошибка удаления связи: {e}")
        return False
    finally:
        if conn:
            conn.close()


@dp.callback_query(F.data.startswith("execute_unassign_"))
async def execute_unassign(callback: types.CallbackQuery):
    """Фактическое снятие преподавателя"""
    try:
        student_username = callback.data.split("_")[2]

        # Проверяем существование студента
        student_info = await get_user_info(student_username)
        if not student_info:
            await callback.answer("❌ Студент не найден", show_alert=True)
            return await callback.message.edit_text(
                "❌ Студент не найден",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="Назад", callback_data="teacher_management")
                ]])
            )

        # Проверяем текущего преподавателя
        current_teacher = await get_current_teacher(student_username)
        if not current_teacher:
            await callback.answer("ℹ️ У студента нет преподавателя", show_alert=True)
            return await callback.message.edit_text(
                f"ℹ️ У @{student_username} нет преподавателя",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="Назад", callback_data="teacher_management")
                ]])
            )

        # Удаляем связь из базы данных
        conn = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                DELETE FROM student_teacher 
                WHERE student_username = %s
                RETURNING 1
            """, (student_username,))

            if not cur.fetchone():
                await callback.answer("❌ Не удалось снять преподавателя", show_alert=True)
                return

            conn.commit()

            # Уведомляем студента
            student_chat_id = await get_user_chat_id(student_username)
            if student_chat_id:
                try:
                    await bot.send_message(
                        chat_id=student_chat_id,
                        text=f"ℹ️ С вас снят руководитель практики: {current_teacher['full_name']} (@{current_teacher['username']})"
                    )
                except Exception as e:
                    print(f"Ошибка уведомления студента: {e}")

            # Обновляем сообщение
            await callback.message.edit_text(
                f"✅ Преподаватель {current_teacher['full_name']} снят со студента @{student_username}\n"
                f"Время: {datetime.now().strftime('%H:%M:%S')}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="В меню", callback_data="teacher_management")
                ]])
            )

        except Error as e:
            print(f"[DB ERROR] Ошибка снятия преподавателя: {e}")
            await callback.message.edit_text(
                "❌ Ошибка при снятии преподавателя",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="Повторить", callback_data=f"confirm_unassign_{student_username}"),
                    InlineKeyboardButton(text="Отмена", callback_data="teacher_management")
                ]])
            )
        finally:
            if conn:
                conn.close()

    except Exception as e:
        print(f"[ERROR] Ошибка снятия: {str(e)}")
        await callback.answer("❌ Ошибка", show_alert=True)

@dp.callback_query(F.data == "refresh_students")
async def refresh_students_list(callback: types.CallbackQuery):
    """Обновляет список студентов"""
    await callback.answer("🔄 Обновление списка...")
    await show_all_students(callback.message)
# Обработчик кнопки подачи заявления
@dp.message(F.text == "📄 Подать заявление")
async def start_application(message: types.Message, state: FSMContext):
    """Начинает процесс подачи заявления"""
    await message.answer(
        "📝 Пожалуйста, прикрепите файл с заявлением (PDF, DOCX, JPG, PNG):",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(ApplicationStates.WAITING_APPLICATION_FILE)


# Обработчик прикрепленного файла
@dp.message(ApplicationStates.WAITING_APPLICATION_FILE, F.document | F.photo)
async def handle_application_file(message: types.Message, state: FSMContext, bot: Bot):
    """Обрабатывает прикрепленный файл заявления с правильным определением типа"""
    file_info = {
        'file_id': None,
        'file_name': "application",
        'file_type': None  # 'document' или 'photo'
    }

    if message.document:
        file_info.update({
            'file_id': message.document.file_id,
            'file_name': message.document.file_name or "document",
            'file_type': 'document'
        })
    elif message.photo:
        file_info.update({
            'file_id': message.photo[-1].file_id,  # Берем самое высокое качество
            'file_name': f"photo_{message.photo[-1].file_unique_id}.jpg",
            'file_type': 'photo'
        })

    if not file_info['file_id']:
        await message.answer("❌ Не удалось получить файл. Попробуйте еще раз.")
        return

    # Сохраняем информацию о файле
    await state.update_data({
        **file_info,
        'student_username': message.from_user.username,
        'student_full_name': message.from_user.full_name
    })

    # Подтверждение отправки
    markup = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="✅ Подтвердить отправку")],
            [types.KeyboardButton(text="❌ Отменить")]
        ],
        resize_keyboard=True
    )

    await message.answer(
        f"📄 Файл '{file_info['file_name']}' ({file_info['file_type']}) готов к отправке методисту.\n"
        "Подтвердите отправку:",
        reply_markup=markup
    )
    await state.set_state(ApplicationStates.WAITING_APPLICATION_CONFIRM)


# Обработчик подтверждения отправки
@dp.message(ApplicationStates.WAITING_APPLICATION_CONFIRM, F.text == "✅ Подтвердить отправку")
async def confirm_application(message: types.Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    methodists = await get_methodists_list()

    if not methodists:
        await message.answer("❌ В системе нет методистов для обработки заявки")
        await state.clear()
        return

    success = 0
    for methodist_username, methodist_chat_id in methodists:
        try:
            caption = (
                f"📨 Новое заявление от студента:\n"
                f"👤 {data['student_full_name']} (@{data['student_username']})\n"
                f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )

            if data['file_type'] == 'document':
                await bot.send_document(
                    chat_id=methodist_chat_id,
                    document=data['file_id'],
                    caption=caption
                )
            elif data['file_type'] == 'photo':
                await bot.send_photo(
                    chat_id=methodist_chat_id,
                    photo=data['file_id'],
                    caption=caption
                )
            success += 1

        except exceptions.TelegramBadRequest as e:
            print(f"Ошибка отправки методисту {methodist_username} (chat_id: {methodist_chat_id}): {e}")
            continue

    if success > 0:
        await message.answer(
            f"✅ Ваше заявление отправлено {success} методистам!",
            reply_markup=types.ReplyKeyboardRemove()
        )
    else:
        await message.answer(
            "❌ Не удалось отправить заявление ни одному методисту",
            reply_markup=types.ReplyKeyboardRemove()
        )

    await state.clear()
#тест пуш
# Новая функция для получения информации о пользователе
async def get_user_info(username: str) -> dict:
    """Возвращает информацию о пользователе из БД"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
                SELECT full_name, chat_id 
                FROM users 
                WHERE username = %s
            """, (username,))
        result = cur.fetchone()
        if result:
            return {'full_name': result[0], 'chat_id': result[1]}
        return None
    except Error as e:
        print(f"Ошибка получения данных пользователя: {e}")
        return None
    finally:
        if conn:
            conn.close()


# Обработчик отмены
@dp.message(ApplicationStates.WAITING_APPLICATION_CONFIRM, F.text == "❌ Отменить")
async def cancel_application(message: types.Message, state: FSMContext):
    """Отменяет подачу заявления"""
    await message.answer(
        "❌ Подача заявления отменена",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.clear()


# Новая функция для получения списка методистов
async def get_methodists_list() -> list[tuple]:
    """Возвращает список методистов с chat_id"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT username, chat_id 
            FROM users 
            WHERE role = 'methodist' AND chat_id IS NOT NULL
        """)
        return cur.fetchall()
    except Error as e:
        print(f"Ошибка получения списка методистов: {e}")
        return []
    finally:
        if conn:
            conn.close()


# Обработчик для методиста при получении заявления
@dp.message(F.document | F.photo)
async def handle_application_from_student(message: types.Message, state: FSMContext):
    """Обрабатывает заявление от студента для методиста"""
    user_role = await get_user_role_by_username(message.from_user.username)

    if user_role != 'methodist':
        return  # Только для методистов

    # Проверяем, есть ли подпись с username студента
    if message.caption and '@' in message.caption:
        student_username = None
        for part in message.caption.split():
            if part.startswith('@'):
                student_username = part[1:]
                break

        if student_username:
            await state.update_data(student_username=student_username)
            await start_assign_teacher_process(message, state)
            return

    # Если username не найден, предлагаем выбрать студента вручную
    await message.answer("Выберите студента для назначения руководителя:")
    await show_students_list(message, state)
    await state.set_state(AssignTeacherStates.WAITING_STUDENT_SELECTION)


async def show_students_list(message: types.Message, state: FSMContext):
    """Показывает список студентов для выбора"""
    students = await get_students_without_teachers()

    if not students:
        await message.answer("❌ Нет студентов без руководителей")
        await state.clear()
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{full_name} (@{username})", callback_data=f"assign_student_{username}")]
        for username, full_name in students
    ])

    await message.answer("👨‍🎓 Выберите студента:", reply_markup=keyboard)


async def get_students_without_teachers() -> list[tuple]:
    """Возвращает список студентов без назначенных преподавателей"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT u.username, u.full_name 
            FROM users u
            LEFT JOIN student_teacher st ON u.username = st.student_username
            WHERE u.role = 'student' AND st.teacher_username IS NULL
            ORDER BY u.username
        """)
        return cur.fetchall()
    except Error as e:
        print(f"Ошибка получения студентов без преподавателей: {e}")
        return []
    finally:
        if conn:
            conn.close()



async def start_assign_teacher_process(message: types.Message, state: FSMContext):
    """Начинает процесс назначения преподавателя"""
    teachers = await get_teachers_list()

    if not teachers:
        await message.answer("❌ Нет доступных преподавателей")
        await state.clear()
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{full_name} (@{username})", callback_data=f"assign_teacher_{username}")]
        for username, full_name in teachers
    ])

    await message.answer("👨‍🏫 Выберите преподавателя:", reply_markup=keyboard)
    await state.set_state(AssignTeacherStates.WAITING_TEACHER_SELECTION)


# Обработчик выбора студента
@dp.callback_query(AssignTeacherStates.WAITING_STUDENT_SELECTION, F.data.startswith("assign_student_"))
async def process_student_selection(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор студента"""
    student_username = callback.data.split("_")[2]
    await state.update_data(student_username=student_username)

    await callback.message.edit_text(f"Выбран студент: @{student_username}")
    await start_assign_teacher_process(callback.message, state)
    await callback.answer()


# Обработчик выбора преподавателя
@dp.callback_query(AssignTeacherStates.WAITING_TEACHER_SELECTION, F.data.startswith("assign_teacher_"))
async def process_teacher_selection(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор преподавателя"""
    teacher_username = callback.data.split("_")[2]
    data = await state.get_data()
    student_username = data.get('student_username')

    if not student_username:
        await callback.answer("❌ Ошибка: студент не выбран")
        await state.clear()
        return

    # Получаем информацию о студенте и преподавателе
    student_info = await get_user_info(student_username)
    teacher_info = await get_user_info(teacher_username)

    if not student_info or not teacher_info:
        await callback.answer("❌ Ошибка: пользователь не найден")
        await state.clear()
        return

    await state.update_data(teacher_username=teacher_username)

    # Формируем сообщение подтверждения
    confirm_text = (
        "📋 Подтвердите назначение:\n\n"
        f"👨‍🎓 Студент: {student_info['full_name']} (@{student_username})\n"
        f"👨‍🏫 Руководитель: {teacher_info['full_name']} (@{teacher_username})\n\n"
        "Назначить этого преподавателя руководителем практики для студента?"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_assignment"),
            InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_assignment")
        ]
    ])

    await callback.message.edit_text(confirm_text, reply_markup=keyboard)
    await state.set_state(AssignTeacherStates.CONFIRM_ASSIGNMENT)
    await callback.answer()


# Обработчик подтверждения назначения
@dp.callback_query(AssignTeacherStates.CONFIRM_ASSIGNMENT, F.data == "confirm_assignment")
async def confirm_assignment(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждает назначение преподавателя"""
    data = await state.get_data()
    student_username = data.get('student_username')
    teacher_username = data.get('teacher_username')

    if not student_username or not teacher_username:
        await callback.answer("❌ Ошибка: данные неполные")
        await state.clear()
        return

    # Сохраняем в базу данных
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Удаляем предыдущее назначение (если есть)
        cur.execute("""
            DELETE FROM student_teacher 
            WHERE student_username = %s
        """, (student_username,))

        # Добавляем новое назначение
        cur.execute("""
            INSERT INTO student_teacher (student_username, teacher_username)
            VALUES (%s, %s)
        """, (student_username, teacher_username))

        conn.commit()

        # Отправляем уведомление студенту
        student_chat_id = await get_user_chat_id(student_username)
        teacher_info = await get_user_info(teacher_username)

        if student_chat_id:
            try:
                await bot.send_message(
                    chat_id=student_chat_id,
                    text=f"👨‍🏫 Вам назначен руководитель практики: {teacher_info['full_name']} (@{teacher_username})"
                )
            except Exception as e:
                print(f"Ошибка отправки уведомления студенту: {e}")

        await callback.message.edit_text(
            "✅ Руководитель практики успешно назначен!",
            reply_markup=None
        )

    except Error as e:
        await callback.message.edit_text(
            "❌ Ошибка при сохранении назначения",
            reply_markup=None
        )
        print(f"Ошибка назначения руководителя: {e}")
    finally:
        if conn:
            conn.close()
        await state.clear()
    await callback.answer()


# Обработчик отмены назначения
@dp.callback_query(AssignTeacherStates.CONFIRM_ASSIGNMENT, F.data == "cancel_assignment")
async def cancel_assignment(callback: types.CallbackQuery, state: FSMContext):
    """Отменяет процесс назначения"""
    await callback.message.edit_text(
        "❌ Назначение отменено",
        reply_markup=None
    )
    await state.clear()
    await callback.answer()


async def get_user_chat_id(username: str) -> int:
    """Возвращает chat_id пользователя по username"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT chat_id FROM users WHERE username = %s
        """, (username,))
        result = cur.fetchone()
        return result[0] if result else None
    except Error as e:
        print(f"Ошибка получения chat_id: {e}")
        return None
    finally:
        if conn:
            conn.close()


# Обработчик кнопки "Мой преподаватель"
@dp.message(F.text == "👨‍🏫 Мой преподаватель")
async def show_my_teacher(message: types.Message):
    """Показывает информацию о назначенном преподавателе"""
    student_username = message.from_user.username
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT u.username, u.full_name 
            FROM student_teacher st
            JOIN users u ON st.teacher_username = u.username
            WHERE st.student_username = %s
        """, (student_username,))
        teacher = cur.fetchone()

        if teacher:
            username, full_name = teacher
            await message.answer(
                f"👨‍🏫 Ваш руководитель практики:\n"
                f"{full_name} (@{username})\n\n"
                f"Вы можете связаться с ним в любое время."
            )
        else:
            await message.answer(
                "❌ Вам еще не назначен руководитель практики.\n"
                "Подайте заявление и ожидайте назначения."
            )
    except Error as e:
        await message.answer("❌ Ошибка при получении данных")
        print(f"Ошибка получения преподавателя: {e}")
    finally:
        if conn:
            conn.close()

# Запуск бота
async def main():
    print(f"Бот запущен. Администратор: @{ADMIN_USERNAME}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())