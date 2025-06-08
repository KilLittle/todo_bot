import asyncio
import psycopg2
from aiogram import Bot, Dispatcher, types, F, exceptions
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
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

class AssignTeacherStates(StatesGroup):
    WAITING_STUDENT_SELECTION = State()
    WAITING_TEACHER_SELECTION = State()
    CONFIRM_ASSIGNMENT = State()

class AssignmentStates(StatesGroup):
    WAITING_STUDENT_SELECTION = State()
    WAITING_TITLE = State()
    WAITING_DESCRIPTION = State()
    WAITING_DEADLINE = State()
    WAITING_FILE = State()
    CONFIRMATION = State()

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


async def add_user_to_db(username: str, role: str, full_name: str = None):
    """Добавление пользователя в БД"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (username, role, full_name) VALUES (%s, %s, %s) "
            "ON CONFLICT (username) DO UPDATE SET role = EXCLUDED.role, full_name = EXCLUDED.full_name",
            (username, role, full_name or "Не указано")  # Добавляем третий параметр
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

        cur.execute("""
            INSERT INTO users (username, role, full_name, chat_id)
            VALUES (%s, 'student', %s, %s)
            ON CONFLICT (username) 
            DO UPDATE SET 
                chat_id = EXCLUDED.chat_id,
                full_name = EXCLUDED.full_name
        """, (
            message.from_user.username,
            message.from_user.full_name or "Аноним",
            message.chat.id
        ))
        conn.commit()
    except Error as e:
        print(f"Ошибка сохранения данных: {e}")
        await message.answer("⚠️ Произошла ошибка при обновлении данных")
        return
    finally:
        if conn:
            conn.close()


    try:
        user_role = await get_user_role_by_username(message.from_user.username)
        if not user_role:
            await message.answer("❌ Ваш профиль не найден в системе")
            return
    except Exception as e:
        print(f"Ошибка получения роли: {e}")
        await message.answer("⚠️ Ошибка при проверке вашей роли")
        return

    markup = types.ReplyKeyboardMarkup(keyboard=[], resize_keyboard=True)

    if user_role == "admin":
        markup.keyboard = [
            [types.KeyboardButton(text="🔄 Старт"),
             types.KeyboardButton(text="➕ Добавить пользователя")],
            [types.KeyboardButton(text="👀 Просмотреть пользователей")]
        ]
        await message.answer("✨ Добро пожаловать, администратор!", reply_markup=markup)

    elif user_role == "methodist":
        markup.keyboard = [
            [types.KeyboardButton(text="🔄 Старт"),
             types.KeyboardButton(text="📋 Посмотреть расписание")],
            [types.KeyboardButton(text="📅 Добавить расписание"),
             types.KeyboardButton(text="📢 Рассылка студентам")],
            [types.KeyboardButton(text="👨‍🎓 Список студентов"),
             types.KeyboardButton(text="👨‍🏫 Преподаватели")]
        ]
        await message.answer("📚 Добро пожаловать, методист!", reply_markup=markup)

    elif user_role == "teacher":
        markup.keyboard = [
            [types.KeyboardButton(text="🔄 Старт"),
             types.KeyboardButton(text="📋 Посмотреть расписание")],
            [types.KeyboardButton(text="👨‍🎓 Мои студенты"),
             types.KeyboardButton(text="📝 Задания студентов")]
        ]
        await message.answer("👨‍🏫 Добро пожаловать, преподаватель!", reply_markup=markup)

    elif user_role == "student":
        markup.keyboard = [
            [types.KeyboardButton(text="🔄 Старт"),
             types.KeyboardButton(text="👨‍🏫 Мой преподаватель")],
            [types.KeyboardButton(text="📄 Подать заявление"),
             types.KeyboardButton(text="📝 Индивидуальное задание")],
            [types.KeyboardButton(text="📋 Посмотреть расписание")]
        ]
        await message.answer("🎓 Добро пожаловать, студент!", reply_markup=markup)

    else:
        await message.answer("❌ Ваша роль не распознана", reply_markup=types.ReplyKeyboardRemove())


# Обработчик кнопки "Старт" (дублирует функционал /start)
@dp.message(F.text == "🔄 Старт")
async def handle_start_button(message: types.Message):
    # Вызываем тот же обработчик, что и для команды /start
    await cmd_start(message)

async def get_assignment_info(student_username: str) -> dict:
    """Получает информацию о задании студента из БД"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT  file_name, file_content, created_by, status 
            FROM assignment_tasks 
            WHERE student_username = %s
        """, (student_username,))
        result = cur.fetchone()

        if result:
            return {
                'file_name': result[0],
                'file_content': result[1],
                'created_by': result[2],
                'status': result[3]
            }
        return None
    except Error as e:
        print(f"Ошибка получения задания: {e}")
        return None
    finally:
        if conn:
            conn.close()


async def download_assignment(assignment_id: int, chat_id: int):
    """Отправляет файл задания пользователю"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT file_content, title 
            FROM assignment_tasks 
            WHERE id = %s
        """, (assignment_id,))
        result = cur.fetchone()

        if result:
            file_content, title = result
            await bot.send_document(
                chat_id=chat_id,
                document=types.BufferedInputFile(
                    file=file_content,
                    filename=f"{title}.pdf"
                ),
                caption=f"📄 Ваше индивидуальное задание: {title}"
            )
            return True
        return False
    except Error as e:
        print(f"Ошибка скачивания задания: {e}")
        return False
    finally:
        if conn:
            conn.close()




async def get_teacher_assignments(teacher_username: str) -> list[tuple]:
    """Возвращает список заданий преподавателя"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT a.student_username, a.title, a.deadline 
            FROM assignment_tasks a
            JOIN users u ON a.student_username = u.username
            WHERE a.teacher_username = %s AND a.status = 'assigned'
            ORDER BY a.deadline
        """, (teacher_username,))
        return cur.fetchall()
    except Error as e:
        print(f"Ошибка получения заданий преподавателя: {e}")
        return []
    finally:
        if conn:
            conn.close()


@dp.callback_query(F.data == "view_assignments")
async def view_assignments(callback: types.CallbackQuery):
    """Показывает список заданий студентов по преподавателю"""
    user_role = await get_user_role_by_username(callback.from_user.username)

    if user_role != 'teacher':
        await callback.answer("❌ Доступно только преподавателям")
        return

    # Получаем список студентов текущего преподавателя
    students = await get_teacher_students(callback.from_user.username)

    if not students:
        await callback.answer("ℹ️ У вас нет студентов с заданиями")
        return

    # Группируем задания по студентам и форматируем ответ
    full_text = "📚 Задания студентов:\n\n"

    # Split students into chunks of 10 to avoid long text
    for i in range(0, len(students), 10):
        chunk = students[i:i + 10]
        for student in chunk:
            full_text += await format_assignments_per_student({
                'username': student[0],
                'full_name': student[1],
                'chat_id': student[2]
            })

        if i + 10 < len(students):  # Add separator only if there are more students
            full_text += "\n---\n"

    # Send the text to the user (limited to 4096 characters)
    if len(full_text) > 4096:
        # For very long texts, split into multiple messages
        pass  # Add splitting logic here

    await callback.message.answer(full_text)
    await callback.answer()


async def get_teacher_students(teacher_username: str) -> list[tuple]:
    """Возвращает список студентов преподавателя с информацией о их заданиях"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT s.username, s.full_name, u.chat_id
            FROM students st
            JOIN users s ON st.student_username = s.username
            WHERE st.teacher_username = %s
        """, (teacher_username,))
        return cur.fetchall()
    except Error as e:
        print(f"Ошибка получения студентов преподавателя: {e}")
        return []
    finally:
        if conn:
            conn.close()

@dp.callback_query(F.data == "check_submitted")
async def check_submitted_N(callback: types.CallbackQuery):
    """Показывает сданные задания"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT a.student_username, a.title, a.submitted_date 
            FROM assignment_tasks a
            WHERE a.teacher_username = %s AND a.status = 'submitted'
            ORDER BY a.submitted_date DESC
        """, (callback.from_user.username,))
        assignments = cur.fetchall()

        if not assignments:
            await callback.answer("ℹ️ Нет сданных заданий")
            return

        response = ["📤 Сданные задания:"]
        for idx, (student, title, submitted_date) in enumerate(assignments, 1):
            response.append(
                f"{idx}. {title}\n"
                f"   👨‍🎓 Студент: @{student}\n"
                f"   📅 Дата сдачи: {submitted_date.strftime('%d.%m.%Y')}"
            )

        await callback.message.edit_text("\n".join(response))

    except Error as e:
        await callback.message.edit_text("❌ Ошибка при получении заданий")
        print(f"Ошибка получения сданных заданий: {e}")
    finally:
        if conn:
            conn.close()
    await callback.answer()


@dp.callback_query(F.data == "tasks_statistics")
async def show_tasks_statistics(callback: types.CallbackQuery):
    """Показывает статистику по заданиям"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Получаем общую статистику
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'assigned' THEN 1 ELSE 0 END) as assigned,
                SUM(CASE WHEN status = 'submitted' THEN 1 ELSE 0 END) as submitted,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed
            FROM assignment_tasks
            WHERE teacher_username = %s
        """, (callback.from_user.username,))
        stats = cur.fetchone()

        # Получаем информацию о просроченных заданиях
        cur.execute("""
            SELECT COUNT(*) 
            FROM assignment_tasks 
            WHERE teacher_username = %s 
            AND status = 'assigned' 
            AND deadline < CURRENT_DATE
        """, (callback.from_user.username,))
        overdue = cur.fetchone()[0]

        response = (
            f"📊 Статистика по заданиям:\n\n"
            f"• Всего заданий: {stats[0]}\n"
            f"• Назначено: {stats[1]}\n"
            f"• Сдано: {stats[2]}\n"
            f"• Завершено: {stats[3]}\n"
            f"• Просрочено: {overdue}"
        )

        await callback.message.edit_text(response)

    except Error as e:
        await callback.message.edit_text("❌ Ошибка при получении статистики")
        print(f"Ошибка получения статистики: {e}")
    finally:
        if conn:
            conn.close()
    await callback.answer()


async def get_teacher_students(teacher_username: str) -> list[tuple[str, str]]:
    """
    Возвращает список студентов преподавателя в формате:
    [(username1, full_name1), (username2, full_name2), ...]

    Args:
        teacher_username: Логин преподавателя

    Returns:
        Список кортежей (username студента, полное имя)
    """
    conn = None
    try:
        conn = get_db_connection()  # Синхронное подключение (ваш текущий код использует psycopg2)
        cur = conn.cursor()

        # Запрос для получения студентов преподавателя
        cur.execute("""
            SELECT s.username, s.full_name 
            FROM student_teacher st
            JOIN users s ON st.student_username = s.username
            WHERE st.teacher_username = %s
            ORDER BY s.full_name
        """, (teacher_username,))

        return cur.fetchall()

    except Error as e:
        print(f"[Ошибка] Не удалось получить студентов преподавателя {teacher_username}: {e}")
        return []
    finally:
        if conn:
            conn.close()

# В меню преподавателя добавляем кнопку работы с заданиями
async def get_student_assignments(student_username: str) -> list[dict]:
    """Возвращает список заданий для студента"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                file_name, file_content, created_by, status
            FROM assignment_tasks a
            WHERE 
                student_username = %s AND
                status = true
        """, (student_username,))
        result = cur.fetchall()

        assignments = []
        for row in result:
            assignments.append({
                'file_name': row[0],
                'file_content': row[1],
                'status': row[2],
                'created_by': row[3],
                'status': row[4]
            })
        return assignments
    except Error as e:
        print(f"Ошибка получения заданий студента: {e}")
        return []
    finally:
        if conn:
            conn.close()

@dp.callback_query(F.data == "assign_new_task")
async def start_assignment_process(callback: types.CallbackQuery, state: FSMContext):
    print("Обработчик assign_new_task вызван")
    """Начинает процесс назначения задания"""
    teacher_username = callback.from_user.username
    students = await get_teacher_students(teacher_username)

    if not students:
        await callback.answer("❌ У вас нет студентов для назначения задания")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{full_name} (@{username})",
            callback_data=f"select_student_{username}"
        )]
        for username, full_name in students
    ])

    await callback.message.edit_text(
        "👨‍🎓 Выберите студента для назначения задания:",
        reply_markup=keyboard
    )
    await state.set_state(AssignmentStates.WAITING_STUDENT_SELECTION)
    await callback.answer()


@dp.callback_query(
    AssignmentStates.WAITING_STUDENT_SELECTION,
    F.data.startswith("select_my_student_") | F.data.startswith("select_student_")
)
async def select_student(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор студента (общий для методиста и преподавателя)"""
    # Определяем тип callback data
    if callback.data.startswith("select_my_student_"):
        student_username = callback.data.split("_")[3]  # для преподавателя
    else:
        student_username = callback.data.split("_")[2]  # для методиста

    await state.update_data(student_username=student_username)

    # Проверяем роль текущего пользователя
    user_role = await get_user_role_by_username(callback.from_user.username)

    if user_role == 'teacher':
        # Для преподавателя сразу переходим к вводу названия задания
        await callback.message.edit_text(
            f"✏️ Введите название задания для @{student_username}:",
            reply_markup=None
        )
        await state.set_state(AssignmentStates.WAITING_TITLE)
    else:
        # Для методиста продолжаем стандартный процесс
        await start_assign_teacher_process(callback.message, state)

    await callback.answer()


@dp.message(AssignmentStates.WAITING_TITLE)
async def process_title(message: types.Message, state: FSMContext):
    """Обрабатывает название задания и переходит к описанию"""



    # Получаем данные о студенте из состояния
    data = await state.get_data()
    student_username = data.get('student_username')

    await message.answer(
        f"📝 Введите описание задания для @{student_username} (можно пропустить, отправивить '-'):",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(AssignmentStates.WAITING_DESCRIPTION)


@dp.message(AssignmentStates.WAITING_DESCRIPTION)
async def process_description(message: types.Message, state: FSMContext):
    """Обрабатывает описание задания"""
    description = None if message.text == "-" else message.text
    await state.update_data(description=description)

    await message.answer("📅 Введите срок сдачи задания (в формате ДД.ММ.ГГГГ):")
    await state.set_state(AssignmentStates.WAITING_DEADLINE)


@dp.message(AssignmentStates.WAITING_DEADLINE)
async def process_deadline(message: types.Message, state: FSMContext):
    """Обрабатывает срок сдачи задания"""
    try:
        deadline = datetime.strptime(message.text, "%d.%m.%Y").date()
        if deadline < date.today():
            await message.answer("❌ Срок сдачи не может быть в прошлом. Введите снова:")
            return

        await state.update_data(deadline=deadline)
        await message.answer("📎 Прикрепите файл с заданием (PDF/DOCX) или отправьте '-' чтобы пропустить:")
        await state.set_state(AssignmentStates.WAITING_FILE)
    except ValueError:
        await message.answer("❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ. Введите снова:")






@dp.callback_query(AssignmentStates.CONFIRMATION, F.data == "confirm_assignment")
async def confirm_assignment(callback: types.CallbackQuery, state: FSMContext):
    print("Обработчик confirm_assignment вызван")
    """Подтверждает создание задания"""
    data = await state.get_data()
    print("Пытаюсь создать задание 2")
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO assignment_tasks 
            (file_name, file_content, created_by, created_by, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data['student_username'],
            callback.from_user.username,
            data['file_name'],
            data['file_content'],
            data['created_by'],
            data.get('status'),
            date.today(),
            'assigned'
        ))
        conn.commit()

        # Уведомляем студента
        student_chat_id = await get_user_chat_id(data['student_username'])
        if student_chat_id:
            try:
                await bot.send_message(
                    chat_id=student_chat_id,
                    text=f"📝 Вам назначено новое задание от преподавателя:\n\n"
                         f"📌 {data['title']}\n"
                         f"📅 Срок сдачи: {data['deadline'].strftime('%d.%m.%Y')}"
                )
            except Exception as e:
                print(f"Ошибка уведомления студента: {e}")

        await callback.message.edit_text(
            "✅ Задание успешно назначено!",
            reply_markup=None
        )

    except Error as e:
        await callback.message.edit_text(
            "❌ Ошибка при сохранении задания",
            reply_markup=None
        )
        print(f"Ошибка сохранения задания: {e}")
    finally:
        if conn:
            conn.close()
        await state.clear()
    await callback.answer()


@dp.callback_query(AssignmentStates.CONFIRMATION, F.data == "cancel_assignment")
async def cancel_assignment(callback: types.CallbackQuery, state: FSMContext):
    """Отменяет создание задания"""
    await callback.message.edit_text(
        "❌ Создание задания отменено",
        reply_markup=None
    )
    await state.clear()
    await callback.answer()
@dp.callback_query(F.data == "show_my_students")
async def show_my_students_callback(callback: types.CallbackQuery):
    """Обработчик кнопки показа студентов"""
    user_role = await get_user_role_by_username(callback.from_user.username)
    await show_my_students(callback.message)
    await callback.answer()

@dp.message(F.text == "👨‍🎓 Мои студенты")
async def show_my_students(message: types.Message):
    """Показывает список студентов преподавателя"""
    teacher_username = message.from_user.username

    # Проверяем, что пользователь действительно преподаватель
    if await get_user_role_by_username(teacher_username) != 'teacher':
        await message.answer("❌ Доступно только преподавателям")
        return

    # Получаем список студентов
    students = await get_teacher_students(teacher_username)

    if not students:
        await message.answer("ℹ️ У вас пока нет назначенных студентов")
        return

    # Формируем сообщение
    response = ["👨‍🎓 Ваши студенты:"]
    for idx, (username, full_name) in enumerate(students, 1):
        response.append(f"{idx}. {full_name} (@{username})")

    # Добавляем кнопки для управления
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📝 Назначить задание", callback_data="assign_task_to_my_student"),
            InlineKeyboardButton(text="🔄 Обновить список", callback_data="show_my_students")
        ]
    ])

    await message.answer("\n".join(response), reply_markup=keyboard)
@dp.callback_query(F.data == "assign_task_to_my_student")
async def assign_task_to_my_student(callback: types.CallbackQuery, state: FSMContext):
    """Начинает процесс назначения задания своему студенту"""
    teacher_username = callback.from_user.username
    students = await get_teacher_students(teacher_username)

    if not students:
        await callback.answer("❌ У вас нет студентов для назначения задания")
        return

    # Создаем клавиатуру с кнопками для выбора студента
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"{full_name} (@{username})",
            callback_data=f"select_my_student_{username}"
        )]
        for username, full_name in students
    ])

    await callback.message.edit_text(
        "👨‍🎓 Выберите студента для назначения задания:",
        reply_markup=keyboard
    )
    await state.set_state(AssignmentStates.WAITING_STUDENT_SELECTION)
    await callback.answer()


@dp.message(F.text == "📝 Индивидуальное задание")
async def handle_individual_task(message: types.Message):
    """Обработчик кнопки индивидуального задания для студента"""
    student_username = message.from_user.username

    # Получаем информацию о задании из базы данных
    assignment = await get_assignment_info(student_username)

    if assignment:
        # Формируем текст сообщения
        response = (
            f"📝 <b>Ваше индивидуальное задание:</b>\n\n"
            f"<b>Название:</b> {assignment['file_name']}\n"
            f"<b>Статус:</b> {assignment['file_content']}\n"
            f"<b>Дата выдачи:</b> {assignment['created_by'].strftime('%d.%m.%Y')}\n"
            f"<b>Срок сдачи:</b> {assignment['status']}"
        )

        # Создаем кнопки для скачивания и просмотра
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📥 Скачать задание",
                    callback_data=f"download_assignment_{assignment['id']}"
                )
            ]
        ])

        await message.answer(response, reply_markup=keyboard, parse_mode="HTML")
    else:
        await message.answer(
            "ℹ️ Вам еще не назначено индивидуальное задание.\n"
            "Ожидайте назначения от вашего руководителя."
        )


@dp.callback_query(F.data.startswith("download_assignment_"))
async def download_assignment_handler(callback: types.CallbackQuery):
    """Обработчик скачивания задания"""
    assignment_id = int(callback.data.split("_")[2])

    try:
        # Получаем данные о задании из базы
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT file_content, title 
            FROM assignment_tasks 
            WHERE id = %s
        """, (assignment_id,))
        result = cur.fetchone()

        if result:
            file_content, title = result
            # Отправляем файл студенту
            await callback.message.answer_document(
                document=types.BufferedInputFile(
                    file=file_content,
                    filename=f"{title}.pdf"
                ),
                caption=f"📄 Ваше индивидуальное задание: {title}"
            )
            await callback.answer("Файл отправлен")
        else:
            await callback.answer("❌ Файл задания не найден", show_alert=True)

    except Exception as e:
        print(f"Ошибка при скачивании задания: {e}")
        await callback.answer("❌ Ошибка при отправке файла", show_alert=True)
    finally:
        if conn:
            conn.close()


@dp.callback_query(F.data.startswith("edit_assignment_"))
async def edit_assignment_handler(callback: types.CallbackQuery):
    """Обработчик редактирования задания"""
    assignment_id = int(callback.data.split("_")[2])
    await callback.answer("Функция редактирования в разработке", show_alert=True)

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



@dp.message(AddUserStates.WAITING_USERNAME, F.text)
async def handle_username(message: types.Message, state: FSMContext):

    username = message.text.strip()
    if not username:
        await message.answer("❌ Введите username (без '@')", reply_markup=types.ReplyKeyboardRemove())
        return

    # Удаляем @ в начале, если он есть
    if username.startswith('@'):
        username = username[1:]

    # Проверяем, что username не занят через БД
    existing_user = await get_user_role_by_username(username)
    if existing_user:
        await message.answer(
            f"❌ Пользователь @{username} уже зарегистрирован с ролью {existing_user}\n"
            "Пожалуйста, введите другой username:",
            reply_markup=types.ReplyKeyboardRemove()
        )
        # Возвращаем в состояние ожидания username
        await state.set_state(AddUserStates.WAITING_USERNAME)
        return

    # Сохраняем username для дальнейшего использования
    await state.update_data(username=username)
    await state.set_state(AddUserStates.WAITING_ROLE)

    await message.answer("📋 Выберите роль для добавляемого пользователя:",
                         reply_markup=types.ReplyKeyboardMarkup(
                             keyboard=[
                                 [
                                    types.KeyboardButton(text="👨‍🎓 Студент"),
                                    types.KeyboardButton(text="👩‍🏫 Преподаватель")
                                 ],
                                 [types.KeyboardButton(text="📚 Методист"),
                                 types.KeyboardButton(text="👑 Администратор")
                                  ]

                             ],
                             resize_keyboard=True
                         ))


@dp.message(AddUserStates.WAITING_ROLE, F.text)
async def finish_add_user(message: types.Message, state: FSMContext):

    user_data = await state.get_data()
    username = user_data.get("username")

    # Проверяем, что пользователь не пытается добавить самого себя
    if username == str(message.from_user.username):
        await message.answer("❌ Вы не можете добавить самого себя!", reply_markup=types.ReplyKeyboardRemove())
        await state.clear()
        return
    if message.text == "👨‍🎓 Студент":
        role = "student"
    elif message.text == "👩‍🏫 Преподаватель":
        role = "teacher"
    elif message.text == "📚 Методист":
        role = "methodist"
    elif message.text == "👑 Администратор":
        role = "admin"

    success = await add_user_to_db(username, role)

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

@dp.message(F.text == "👀 Просмотреть пользователей")
async def cmd_view_users(message: types.Message):

    users = await get_all_users()
    if not users:
        await message.answer("📋 Список пользователей пуст.")
        return

    text = "📌 Список пользователей:\n\n"

    for user in users:
        username, role, name = user

        if role == "admin":
            icon = "👑"
        elif role == "teacher":
            icon = "👩‍🏫"
        elif role == "student":
            icon = "👨‍🎓"
        else:
            icon = "👤"

        text += f"{icon} @{username} - {name}\n"


    await message.answer(text)

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

@dp.callback_query(F.data == "view_schedule")
@dp.message(F.text == "📋 Посмотреть расписание")
async def cmd_view_schedule(message: types.Message):
    """Показывает список доступных расписаний"""
    schedule = await get_schedule_list()
    user_role = await get_user_role_by_username(message.from_user.username)

    if not schedule:
        await message.answer("📅 Расписаний пока нет.")
        return

    response = "📅 Расписание:\n"
    for idx, (semester, start, end, practice, teacher) in enumerate(schedule, 1):
        response += f"{idx}📌 {semester}\n"
       # response += f"   Период: {start.strftime('%d.%m.%Y')} - {end.strftime('%d.%m.%Y')}\n"
        response += f"   Практика: {practice}\n"
        response += f"   Ответственный: @{teacher}\n\n"

        # Для студентов добавляем кнопку подачи заявления
    if user_role == 'student':
        # Для студентов добавляем кнопку подачи заявления
        application_button = InlineKeyboardButton(
            text="📄 Подать заявление",
            callback_data="start_application"
        )
        markup = InlineKeyboardMarkup(inline_keyboard=[[application_button]])
        await message.answer(response, reply_markup=markup)
    else:
        await message.answer(response)


@dp.callback_query(F.data == "start_application")
async def start_application_callback(callback: types.CallbackQuery, state: FSMContext):
    message = callback.message
    await message.answer(
            "📝 Пожалуйста, прикрепите файл с заявлением (PDF, DOCX):",
            reply_markup=ReplyKeyboardRemove()
        )
    await state.set_state(ApplicationStates.WAITING_APPLICATION_FILE)
    await callback.answer()


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
async def select_student_for_teacher(callback: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор студента и переходит к выбору преподавателя"""
    try:
        # Правильно парсим callback data: assign_student_<student_username>
        student_username = callback.data.split("_")[2]

        # Сохраняем student_username в state
        await state.update_data(student_username=student_username)

        # Получаем список преподавателей
        teachers = await get_teachers_list()

        if not teachers:
            await callback.answer("❌ Нет доступных преподавателей")
            return

        # Создаем клавиатуру с преподавателями
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{full_name} (@{username})",
                callback_data=f"assign_teacher_{student_username}_{username}"
            )]
            for username, full_name in teachers
        ])

        await callback.message.edit_text(
            f"👨‍🏫 Выберите преподавателя для студента @{student_username}:",
            reply_markup=keyboard
        )
        await callback.answer()

    except Exception as e:
        print(f"Ошибка в select_student_for_teacher: {e}")
        await callback.answer("❌ Ошибка при выборе студента")


# Обработчик подтверждения назначения преподавателя
@dp.callback_query(AssignTeacherStates.CONFIRM_ASSIGNMENT, F.data == "confirm_assignment")
async def confirm_teacher_assignment(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждает назначение преподавателя студенту"""
    try:
        data = await state.get_data()
        student_username = data['student_username']
        teacher_username = data['teacher_username']

        # Обязательно проверяем наличие данных
        if not student_username or not teacher_username:
            await callback.answer("❌ Ошибка: данные неполные", show_alert=True)
            return

        conn = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()

            # Удаляем старую связь
            cur.execute("DELETE FROM student_teacher WHERE student_username = %s", (student_username,))

            # Добавляем новую связь
            cur.execute(
                "INSERT INTO student_teacher (student_username, teacher_username) VALUES (%s, %s)",
                (student_username, teacher_username)
            )
            conn.commit()

            # Уведомляем студента
            student_chat_id = await get_user_chat_id(student_username)
            if student_chat_id:
                teacher_info = await get_user_info(teacher_username)
                if teacher_info:
                    await bot.send_message(
                        chat_id=student_chat_id,
                        text=f"👨‍🏫 Вам назначен руководитель: {teacher_info['full_name']} (@{teacher_username})"
                    )

            await callback.message.edit_text(
                "✅ Преподаватель успешно назначен!",
                reply_markup=None
            )

        except Error as e:
            await callback.message.edit_text(
                "❌ Ошибка при сохранении назначения",
                reply_markup=None
            )
            print(f"Ошибка БД: {e}")
        finally:
            if conn:
                conn.close()
            await state.clear()

    except Exception as e:
        print(f"Ошибка в обработчике подтверждения: {e}")
    finally:
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

    # Уведомление преподавателюё
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
        "📝 Пожалуйста, прикрепите файл с заявлением (PDF, DOCX):",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(ApplicationStates.WAITING_APPLICATION_FILE)


@dp.message(
    AssignmentStates.WAITING_FILE,
    ApplicationStates.WAITING_APPLICATION_FILE,
    F.document | F.photo | (F.text & (F.text == "-"))
)
async def handle_uploaded_file(message: types.Message, state: FSMContext, bot: Bot):
    """Универсальный обработчик загружаемых файлов для разных контекстов"""
    try:
        current_state = await state.get_state()
        is_assignment = current_state == AssignmentStates.WAITING_FILE.state
        is_application = current_state == ApplicationStates.WAITING_APPLICATION_FILE.state

        # Получаем текущие данные из состояния
        data = await state.get_data()

        # Обработка файла/документа
        file_info = {
            'file_id': None,
            'file_name': None,
            'file_type': None,
            'file_content': None
        }

        if message.document:
            if is_assignment:
                # Проверка форматов только для заданий
                allowed_types = {
                    'application/pdf',
                    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    'application/msword'
                }

                if message.document.mime_type not in allowed_types:
                    await message.answer(
                        "❌ Поддерживаются только файлы PDF или DOC/DOCX",
                        reply_markup=types.ReplyKeyboardRemove()
                    )
                    return

                try:
                    file = await bot.get_file(message.document.file_id)
                    file_bytes = (await bot.download_file(file.file_path)).read()
                    file_info['file_content'] = file_bytes
                except Exception as e:
                    print(f"Ошибка загрузки файла задания: {e}")
                    await message.answer(
                        "❌ Не удалось загрузить файл. Попробуйте снова",
                        reply_markup=types.ReplyKeyboardRemove()
                    )
                    return

            file_info.update({
                'file_id': message.document.file_id,
                'file_name': message.document.file_name or "document",
                'file_type': 'document'
            })

        elif message.photo:
            file_info.update({
                'file_id': message.photo[-1].file_id,
                'file_name': f"photo_{message.photo[-1].file_unique_id}.jpg",
                'file_type': 'photo'
            })

        elif message.text == "-":
            file_info.update({
                'file_name': "не прикреплен",
                'file_type': 'none'
            })

        else:
            await message.answer("❌ Поддерживаются только документы или фото")
            return

        # Обновляем состояние
        await state.update_data(**file_info)

        # Формируем текст подтверждения в зависимости от контекста
        if is_assignment:
            # Проверяем обязательные поля для заданий
            required_fields = ['student_username', 'title', 'description', 'deadline']
            missing_fields = [field for field in required_fields if field not in data]

            if missing_fields:
                error_msg = "❌ Ошибка: отсутствуют данные задания:\n" + "\n".join(
                    f"• {field}" for field in missing_fields)
                await message.answer(error_msg, reply_markup=types.ReplyKeyboardRemove())
                await state.clear()
                return

            confirm_text = (
                "📋 Подтвердите данные задания:\n\n"
                f"👨‍🎓 Студент: @{data['student_username']}\n"
                f"📌 Название: {data['title']}\n"
                f"📝 Описание: {data['description'] or 'не указано'}\n"
                f"📅 Срок сдачи: {data['deadline'].strftime('%d.%m.%Y')}\n"
                f"📎 Файл: {file_info['file_name']}"
            )

            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_assignment"),
                InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_assignment")
            ]])

            next_state = AssignmentStates.CONFIRMATION

        elif is_application:
            confirm_text = (
                f"📄 Файл '{file_info['file_name']}' готов к отправке методисту.\n"
                "Подтвердите отправку:"
            )

            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✅ Подтвердить отправку", callback_data="confirm_application"),
                InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_application")
            ]])

            next_state = ApplicationStates.WAITING_APPLICATION_CONFIRM

        await message.answer(confirm_text, reply_markup=keyboard)
        await state.set_state(next_state)

    except Exception as e:
        print(f"Ошибка обработки файла: {e}")
        await message.answer(
            "❌ Произошла ошибка при обработке файла. Попробуйте еще раз",
            reply_markup=types.ReplyKeyboardRemove()
        )
        await state.clear()


@dp.callback_query(ApplicationStates.WAITING_APPLICATION_CONFIRM, F.data == "confirm_application")
async def confirm_application(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    """Обработчик подтверждения отправки заявления с возвратом в меню"""
    data = await state.get_data()
    methodists = await get_methodists_list()
    user_role = await get_user_role_by_username(callback.from_user.username)

    if not methodists:
        await callback.message.edit_text("❌ В системе нет методистов для обработки заявки")
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

    # Формируем клавиатуру в зависимости от роли пользователя
    if user_role == 'student':
        markup = ReplyKeyboardMarkup(
            keyboard=[
                         [
                             types.KeyboardButton(text="👨‍🏫 Мой преподаватель"),
                             types.KeyboardButton(text="📄 Подать заявление")
                         ],
                         [
                             types.KeyboardButton(text="📝 Индивидуальное задание")
                         ]
                     ] ,
            resize_keyboard=True
        )
    elif user_role == 'methodist':
        markup = ReplyKeyboardMarkup(
            keyboard=[
                         [
                             types.KeyboardButton(text="👨‍🏫 Мой преподаватель"),
                             types.KeyboardButton(text="📄 Подать заявление")
                         ],
                         [
                             types.KeyboardButton(text="📝 Индивидуальное задание")
                         ]
                     ] ,
            resize_keyboard=True
        )
    else:
        markup = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🔄 Старт")]
            ],
            resize_keyboard=True
        )

    if success > 0:
        await callback.message.answer(
            f"✅ Ваше заявление отправлено {success} методистам!",
            reply_markup=markup
        )
    else:
        await callback.message.answer(
            "❌ Не удалось отправить заявление ни одному методисту",
            reply_markup=markup
        )

    await state.clear()
    await callback.answer()


@dp.callback_query(ApplicationStates.WAITING_APPLICATION_CONFIRM, F.data == "cancel_application")
async def cancel_application(callback: types.CallbackQuery, state: FSMContext):
    """Обработчик отмены заявления с возвратом в меню"""
    user_role = await get_user_role_by_username(callback.from_user.username)

    # Формируем клавиатуру в зависимости от роли
    if user_role == 'student':
        markup = ReplyKeyboardMarkup(
            keyboard=[
                         [
                             types.KeyboardButton(text="👨‍🏫 Мой преподаватель"),
                             types.KeyboardButton(text="📄 Подать заявление")
                         ],
                         [
                             types.KeyboardButton(text="📝 Индивидуальное задание")
                         ]
                     ] ,
            resize_keyboard=True
        )
    else:
        markup = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🔄 Старт")]
            ],
            resize_keyboard=True
        )

    await callback.message.answer(
        "❌ Отправка заявления отменена",
        reply_markup=markup
    )
    await state.clear()
    await callback.answer()


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

async def user_exists(username: str) -> bool:
    """Проверяет существование пользователя в БД"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM users WHERE username = %s", (username,))
        return bool(cur.fetchone())
    except Error as e:
        print(f"Ошибка проверки пользователя: {e}")
        return False
    finally:
        if conn:
            conn.close()


@dp.callback_query(F.data.startswith("assign_teacher_"))
async def assign_teacher_handler(callback: types.CallbackQuery, state: FSMContext = None):
    """Унифицированный обработчик назначения преподавателя"""
    try:
        # Проверяем и парсим данные из callback
        parts = callback.data.split('_')
        if len(parts) != 4:
            await callback.answer("❌ Неверный формат данных callback", show_alert=True)
            return

        student_username = parts[2]  # Третий элемент - student
        teacher_username = parts[3]  # Четвертый элемент - teacher ДВА ДНЯ на это убила, капец

        # Проверяем существование пользователей в базе
        if not await user_exists(student_username):
            await callback.answer(f"❌ Студент @{student_username} не найден", show_alert=True)
            return

        if not await user_exists(teacher_username):
            await callback.answer(f"❌ Преподаватель @{teacher_username} не найден", show_alert=True)
            return

        # Проверяем, что teacher_username действительно преподаватель
        teacher_role = await get_user_role_by_username(teacher_username)
        if teacher_role != 'teacher':
            await callback.answer(f"❌ @{teacher_username} не является преподавателем", show_alert=True)
            return

        conn = None
        try:
            conn = get_db_connection()
            cur = conn.cursor()

            # Удаляем старую связь (если есть)
            cur.execute("""
                DELETE FROM student_teacher 
                WHERE student_username = %s
            """, (student_username,))

            # Добавляем новую связь
            cur.execute("""
                INSERT INTO student_teacher 
                (student_username, teacher_username)
                VALUES (%s, %s)
            """, (student_username, teacher_username))

            conn.commit()

            # Получаем информацию для уведомлений
            teacher_info = await get_user_info(teacher_username)
            student_info = await get_user_info(student_username)

            # Уведомляем студента
            student_chat_id = await get_user_chat_id(student_username)
            if student_chat_id and teacher_info:
                try:
                    await bot.send_message(
                        chat_id=student_chat_id,
                        text=f"👨‍🏫 Вам назначен руководитель практики: {teacher_info['full_name']} (@{teacher_username})"
                    )
                except Exception as e:
                    print(f"Ошибка уведомления студента: {e}")

            # Уведомляем преподавателя
            teacher_chat_id = await get_user_chat_id(teacher_username)
            if teacher_chat_id and student_info:
                try:
                    await bot.send_message(
                        chat_id=teacher_chat_id,
                        text=f"👨‍🎓 Вам назначен студент: {student_info['full_name']} (@{student_username})"
                    )
                except Exception as e:
                    print(f"Ошибка уведомления преподавателя: {e}")

            await callback.message.edit_text(
                f"✅ Руководитель {teacher_info['full_name']} назначен студенту @{student_username}",
                reply_markup=None
            )

        except Error as e:
            await callback.message.edit_text(
                "❌ Ошибка при назначении преподавателя",
                reply_markup=None
            )
            print(f"Ошибка БД: {e}")
        finally:
            if conn:
                conn.close()
    except Exception as e:
        print(f"Ошибка в обработчике назначения преподавателя: {e}")
    finally:
        if state:
            await state.clear()
        await callback.answer()



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
    await state.update_data(teacher_username=teacher_username, student_username=student_username)

    await callback.answer()
# Добавляем новую функцию для получения файла задания из базы
async def get_assignment_file() -> bytes:
    """Получает файл типового задания из базы данных"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT file_content FROM assignment_tasks 
            WHERE status = TRUE 
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        result = cur.fetchone()
        return result[0] if result else None
    except Error as e:
        print(f"Ошибка получения файла задания: {e}")
        return None
    finally:
        if conn:
            conn.close()

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

    print(f"Назначение преподавателя: student={student_username}, teacher={teacher_username}")


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

        # Уведомляем студента
        student_chat_id = await get_user_chat_id(student_username)
        teacher_info = await get_user_info(teacher_username)

        if student_chat_id and teacher_info:
            try:
                await bot.send_message(
                    chat_id=student_chat_id,
                    text=f"👨‍🏫 Вам назначен руководитель практики: {teacher_info['full_name']} (@{teacher_username})"
                )

                # Отправляем типовое задание
                assignment_file = await get_assignment_file()
                if assignment_file:
                    cur.execute("""
                        INSERT INTO assignments 
                        (student_username, teacher_username, title, file_content, status)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        student_username,
                        teacher_username,
                        "Типовое индивидуальное задание",
                        assignment_file,
                        'assigned'
                    ))
                    conn.commit()

                    await bot.send_document(
                        chat_id=student_chat_id,
                        document=types.BufferedInputFile(
                            file=assignment_file,
                            filename="Типовое индивидуальное задание.pdf"
                        ),
                        caption="📄 Ваше типовое индивидуальное задание"
                    )
                else:
                    await bot.send_message(
                        chat_id=student_chat_id,
                        text="ℹ️ Файл с типовым заданием временно недоступен"
                    )

            except Exception as e:
                print(f"Ошибка уведомления студента: {e}")

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


@dp.message(Command("upload_template"))
async def upload_template_command(message: types.Message):
    """Команда для загрузки файла"""
    await message.answer("📤 Отправьте файл с типовым заданием (PDF/DOCX)")



@dp.message(F.document & (F.document.mime_type == 'application/pdf') |
            (F.document.mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'))
async def handle_template_upload(message: types.Message, bot: Bot):
    """Обработчик загрузки файла в базу данных"""


    conn = None
    try:
        # Получаем информацию о файле
        file_id = message.document.file_id
        file = await bot.get_file(file_id)
        file_bytes = (await bot.download_file(file.file_path)).read()

        # Подключаемся к базе
        conn = get_db_connection()
        cur = conn.cursor()



        # 2. Сохраняем новый
        cur.execute("""
            INSERT INTO assignment_tasks 
            (file_name, file_content, created_by, status)
            VALUES (%s, %s, %s, TRUE)
        """, (
            message.document.file_name,
            file_bytes,
            message.from_user.username
        ))

        conn.commit()
        user_role = await get_user_role_by_username(message.from_user.username)
        if user_role == "teacher":
            await message.answer(
                f"""✅ Задание успешно загружено!
            Файл: {message.document.file_name}
            Размер: {len(file_bytes) / 1024:.1f} KB\n 
        Вы можете вернуться в меню /start"""
            )
        else:
            await message.answer(
                f"""✅ Заявление успешно загружено!
        Файл: {message.document.file_name}
        Размер: {len(file_bytes) / 1024:.1f} KB\n 
        Вы можете вернуться в меню /start""")

    except Exception as e:
        await message.answer(f"❌ Ошибка при загрузке задания: {str(e)}")
        print(f"Ошибка загрузки задания: {e}")

    finally:
        if conn:
            conn.close()


@dp.message(F.document)
async def handle_wrong_file_type(message: types.Message):
    """Обработчик неподдерживаемых форматов"""
    if message.document.mime_type not in [
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    ]:
        await message.answer("""
        ❌ Неподдерживаемый формат файла.
        Пожалуйста, отправьте файл в формате PDF или DOCX.
        """)



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
    print(f"Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
