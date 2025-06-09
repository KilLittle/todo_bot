# Telegram Bot for Educational Practice Management

Бот для управления учебными практиками студентов с ролевой системой (администраторы, методисты, преподаватели, студенты).
---
## ⚙️ Процесс
Диаграммы: 
- [IDEF0](https://drive.google.com/file/d/1mdOV-tPyFfxxlt1a6NRojqtBLCncWilJ/view)
- [BPMN](https://drive.google.com/file/d/1VvfkCW-AGezMCRecZoc_Tdq6jnWoD_Tk/view)

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
---

## 🛠 Технологии

- **Python 3.10+**
- **Aiogram 3.x** (асинхронный фреймворк для Telegram API)
- **PostgreSQL** (хранение данных)
- **psycopg2** (драйвер для работы с PostgreSQL)

## 🗃 **Структура базы данных**

### 📌 **1. Таблица `users` (Пользователи)**
```sql
CREATE TABLE users (
  username VARCHAR(50) PRIMARY KEY,
  role VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'methodist', 'teacher', 'student')),
  full_name VARCHAR(100) NOT NULL,
  chat_id BIGINT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```
**Описание полей**:  
- `username` – Логин ТГ  
- `role` – Роль   
- `full_name` – Полное имя, подставляется из ТГ  
- `chat_id` – Идентификатор Telegram (для рассылки)  

---

### 📅 **2. Таблица `schedule` (Расписание практик)**
```sql
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
```
**Ключевые особенности**:  
- Автоматическая проверка корректности дат (`end_date > start_date`)  
- Ссылки на таблицу пользователей через `REFERENCES`  

---

### 👥 **3. Таблица `student_teacher` (Связи студентов и преподавателей)**
```sql
CREATE TABLE student_teacher (
  student_username VARCHAR(50) REFERENCES users(username) ON DELETE CASCADE,
  teacher_username VARCHAR(50) REFERENCES users(username) ON DELETE CASCADE,
  assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (student_username)
);
```
**Важно**:  
- Каскадное удаление при удалении пользователя (`ON DELETE CASCADE`)  
- Один студент → один преподаватель (PRIMARY KEY на `student_username`)  

---

### 📝 **4. Таблица `assignment_tasks` (Учебные задания)**
```sql
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
```
*Статусы заданий*:  не реализовано
- `pending` – Ожидает выполнения  
- `in_progress` – В работе  
- `completed` – Завершено  

---

### 📄 **5. Таблица `student_applications` (Заявления студентов)**
```sql
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
```
*Статусы заявлений*:  не реализовано

---

## 🚀 Не забудь
Настроить конфигурацию:
API_TOKEN
DB_CONFIG
