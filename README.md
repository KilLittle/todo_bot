# Telegram Bot for Educational Practice Management

Бот для управления учебными практиками студентов с ролевой системой (администраторы, методисты, преподаватели, студенты).

## 📌 Основные функции

### Для администраторов:
- Управление пользователями (добавление/просмотр)
- Полный доступ ко всем функциям системы

### Для методистов:
- Управление расписанием практик
- Рассылка уведомлений студентам
- Назначение преподавателей студентам
- Просмотр списков студентов и преподавателей

### Для преподавателей:
- Просмотр назначенных студентов
- Создание и проверка заданий
- Доступ к функциям методиста (по требованию)

### Для студентов:
- Просмотр расписания практик
- Подача заявлений
- Просмотр заданий и сроков сдачи
- Связь с преподавателем

## 🛠 Технологии

- **Python 3.10+**
- **Aiogram 3.x** (асинхронный фреймворк для Telegram API)
- **PostgreSQL** (хранение данных)
- **psycopg2** (драйвер для работы с PostgreSQL)

## ⚙️ Настроить базу данных

- Создать БД в PostgreSQL
- Выполнить SQL-скрипты:



## 📄 Структура базы данных

Основные таблицы:
- `users` - информация о пользователях
- `schedule` - расписание практик
- `student_teacher` - связи студентов и преподавателей
- `assignment_tasks` - учебные задания
Создать:
-- Таблица пользователей
CREATE TABLE users (
    username VARCHAR(50) PRIMARY KEY,
    role VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'methodist', 'teacher', 'student')),
    full_name VARCHAR(100) NOT NULL,
    chat_id BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица расписания практик
CREATE TABLE schedule (
    id SERIAL PRIMARY KEY,
    semester_name VARCHAR(100) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    practice_name VARCHAR(200) NOT NULL,
    practice_description TEXT,
    responsible_teacher VARCHAR(50) REFERENCES users(username),
    created_by VARCHAR(50) REFERENCES users(username),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (end_date > start_date)
);

-- Таблица связей студент-преподаватель
CREATE TABLE student_teacher (
    student_username VARCHAR(50) REFERENCES users(username) ON DELETE CASCADE,
    teacher_username VARCHAR(50) REFERENCES users(username) ON DELETE CASCADE,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (student_username)
);

-- Таблица заданий
CREATE TABLE assignment_tasks (
    id SERIAL PRIMARY KEY,
    student_username VARCHAR(50) REFERENCES users(username) ON DELETE CASCADE,
    teacher_username VARCHAR(50) REFERENCES users(username),
    title VARCHAR(200) NOT NULL,
    description TEXT,
    deadline DATE NOT NULL,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed')),
    file_name VARCHAR(255),
    file_content BYTEA,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица заявлений студентов
CREATE TABLE student_applications (
    id SERIAL PRIMARY KEY,
    student_username VARCHAR(50) REFERENCES users(username) ON DELETE CASCADE,
    file_id VARCHAR(255) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_by VARCHAR(50) REFERENCES users(username),
    processed_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected'))
);


## 🚀 Не забудь
Настроить конфигурацию:
API_TOKEN
DB_CONFIG
