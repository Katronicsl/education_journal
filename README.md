# Education Journal

**Курсовой проект по дисциплине ТРПО**  
Второй курс | 2026

---

## 📋 Описание проекта

**Education Journal** — это веб-приложение для управления электронным журналом успеваемости и посещаемости студентов. Система позволяет преподавателям вести учет оценок и посещений, администраторам управлять группами и преподавателями, а студентам отслеживать свою успеваемость.

### Основной функционал

- **Управление студентами и группами** — создание групп, добавление студентов
- **Система оценивания** — гибкие системы оценок (точки, кастомные шкалы)
- **Учет посещаемости** — отслеживание присутствия студентов на занятиях
- **Рейтинги** — рейтинг студентов по предметам и общий рейтинг
- **Управление дисциплинами** — назначение дисциплин преподавателям
- **Профили пользователей** — разные уровни доступа (администратор, преподаватель, студент)
- **Экспорт данных** — возможность загрузки данных в Excel

---

## 🛠️ Технологический стек

| Компонент | Технология | Версия |
|-----------|-----------|--------|
| **Backend** | Python | 3.8+ |
| **Фреймворк** | Flask | 3.1.2 |
| **База данных** | PostgreSQL | 12+ |
| **ORM** | SQLAlchemy | 3.1.1 |
| **Аутентификация** | JWT (Flask-JWT-Extended) | 4.7.1 |
| **Хеширование** | Bcrypt (Flask-Bcrypt) | 1.0.1 |
| **Работа с Excel** | openpyxl, pandas | 3.1.5, 3.0.0 |
| **Фронтенд** | HTML5, CSS3, JavaScript (ES6+) | — |
| **Драйвер БД** | psycopg2 | 2.9.6 |

---

## 📁 Структура проекта

```
education_journal/
├── app/
│   ├── __init__.py                    # Инициализация приложения Flask
│   ├── controllers/                   # Маршруты и обработчики запросов
│   │   ├── auth.py                   # Аутентификация и авторизация
│   │   ├── main.py                   # Главные страницы
│   │   ├── student.py                # API и обработчики для студентов
│   │   ├── teacher.py                # API и обработчики для преподавателей
│   │   └── admin.py                  # API и обработчики для администраторов
│   ├── models/                        # Модели данных
│   │   ├── __init__.py               # Инициализация БД (SQLAlchemy)
│   │   ├── user.py                   # Модель пользователя
│   │   ├── course.py                 # Модели дисциплин, групп, университетов
│   │   ├── grade.py                  # Модели оценок и системы оценивания
│   │   └── attendance.py             # Модель посещаемости
│   ├── templates/                     # HTML шаблоны (Jinja2)
│   │   ├── login.html                # Страница входа
│   │   ├── index.html                # Главная страница
│   │   ├── profile.html              # Профиль пользователя
│   │   ├── admin_*.html              # Страницы администратора
│   │   ├── teacher_*.html            # Страницы преподавателя
│   │   ├── student_*.html            # Страницы студента
│   │   └── grading_system.html       # Управление системой оценивания
│   ├── static/                        # Статические файлы
│   │   ├── css/
│   │   │   └── style.css             # Основные стили
│   │   ├── avatars/                  # Аватары пользователей
│   │   └── *.png, *.jpg              # Логотипы и изображения дисциплин
│   └── utils/                         # Утилиты и вспомогательные функции
│       ├── helpers.py                # Функции-помощники
│       └── validators.py             # Валидация данных
├── config.py                          # Конфигурация приложения
├── run.py                             # Точка входа приложения
├── requirements.txt                   # Зависимости проекта
├── documents/                         # Документация проекта
└── README.md                          # Этот файл
```

---

## 🚀 Установка и запуск

### Требования

- Python 3.8 или выше
- PostgreSQL 12 или выше
- pip (менеджер пакетов Python)

### Пошаговая инструкция

#### 1. Клонирование репозитория

```bash
git clone https://github.com/Katronicsl/education_journal.git
cd education_journal
```

#### 2. Создание виртуального окружения

```bash
# Linux/macOS
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

#### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

#### 4. Настройка базы данных PostgreSQL

```bash
# Создание базы данных
createdb postgres

# Или через psql
psql -U postgres
CREATE DATABASE postgres;
```

#### 5. Конфигурация приложения

Отредактируйте файл `config.py`:

```python
# Для разработки (уже настроено)
SQLALCHEMY_DATABASE_URI = "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres"

# Для продакшена установите переменную окружения
export DATABASE_URL="postgresql+psycopg2://user:password@host:port/dbname"
```

#### 6. Запуск приложения

```bash
python run.py
```

Приложение будет доступно по адресу: **http://localhost:5001**

---

## 👤 Учетные данные по умолчанию

После первого запуска приложение автоматически создает администратора:

| Поле | Значение |
|------|----------|
| **Email** | admin@example.com |
| **Пароль** | admin123 |
| **Роль** | Администратор |

⚠️ **Рекомендуется сменить пароль администратора в продакшене!**

---

## 🔐 Безопасность

- **Аутентификация:** JWT токены, сохраняются в cookies
- **Хеширование паролей:** Bcrypt с солью
- **CSRF защита:** Отключена для API (убедитесь в своей защите на уровне фреймворка)
- **Переменные окружения:** Используйте переменные окружения для секретных ключей

### Обязательные переменные окружения

```bash
export SECRET_KEY="ваш-очень-длинный-секретный-ключ-здесь"
export JWT_SECRET_KEY="ваш-jwt-секретный-ключ-здесь"
export FLASK_ENV="production"  # или "development"
export DATABASE_URL="postgresql+psycopg2://user:password@host:port/dbname"
```

---

## 📊 Основные компоненты системы

### Модели данных

#### User (Пользователь)
- id, фамилия, имя, отчество
- email, пароль (хеш)
- роль (администратор, преподаватель, студент)
- создано, обновлено

#### Group (Группа)
- id, название группы, год обучения
- связь с университетом
- студенты в группе

#### Course (Дисциплина)
- id, название, описание, часы, кредиты
- преподаватель
- связь с группами

#### Assignment (Назначение)
- группа + дисциплина + преподаватель
- система оценивания для данного назначения
- вес в рейтинге

#### Grade (Оценка)
- студент, назначение, дата
- значение оценки, дисплей-значение
- важность (для фильтрации)

#### Attendance (Посещаемость)
- студент, назначение, дата занятия
- статус (присутствует, отсутствует, отсутствует по уважительной причине)

### Система оценивания

Система поддерживает несколько типов оценок:

1. **Points (Баллы):** 0-100, 50 — проходной балл
2. **5-point scale (5-балльная система):** 2-5, 3 — проходной балл
3. **Custom (Кастомная система):** произвольные значения

**Методы расчета:**
- **Average:** средняя арифметическая всех оценок
- **Sum:** сумма всех оценок

---

## 🎯 Функциональность по ролям

### 🔑 Администратор

- ✅ Управление преподавателями (одобрение, удаление)
- ✅ Управление группами (создание, редактирование)
- ✅ Назначение дисциплин группам
- ✅ Управление системой оценивания
- ✅ Просмотр рейтингов студентов
- ✅ Управление дисциплинами и университетами

### 👨‍🏫 Преподаватель

- ✅ Просмотр своих групп и дисциплин
- ✅ Ввод оценок студентов (таблица в стиле Excel)
- ✅ Учет посещаемости
- ✅ Просмотр рейтинга студентов
- ✅ Отслеживание успеваемости
- ✅ Экспорт данных в Excel

### 👨‍🎓 Студент

- ✅ Просмотр своего профиля
- ✅ Просмотр оценок по дисциплинам
- ✅ Просмотр посещаемости
- ✅ Просмотр рейтинга в группе
- ✅ Отслеживание своей успеваемости

---

## 🧮 Примеры расчета средней оценки

### Пример 1: Система баллов (Points) с методом Average
```
Оценки: 80, 90, 75
Средняя: (80 + 90 + 75) / 3 = 81.67
Проходной балл: 60
Статус: ЗЕЛЕНЫЙ (81.67 >= 60)
```

### Пример 2: 5-балльная система с методом Sum
```
Оценки: 5, 4, 3
Сумма: 5 + 4 + 3 = 12
Проходной балл: макс (15) / 2 = 7.5
Статус: ЗЕЛЕНЫЙ (12 >= 7.5)
```

---

## 🔄 API Endpoints

### Аутентификация
- `POST /auth/login` — вход в систему
- `POST /auth/register` — регистрация преподавателя
- `POST /auth/logout` — выход из системы

### Студент
- `GET /student/grades` — оценки студента
- `GET /student/attendance` — посещаемость
- `GET /student/rating` — рейтинг

### Преподаватель
- `GET /teacher/groups` — мои группы
- `GET /teacher/api/get_group_students` — студенты группы
- `POST /teacher/api/update_grades` — обновление оценок
- `POST /teacher/api/update_attendance` — обновление посещаемости

### Администратор
- `GET /admin/groups` — все группы
- `GET /admin/api/get_grading_system` — система оценивания
- `POST /admin/api/set_grading_system` — установка системы оценивания
- `GET /admin/api/get_all_grades` — все оценки
- `GET /admin/api/get_attendance_data` — все данные о посещаемости

---

## 🗄️ База данных (PostgreSQL)

### Подключение к БД

```bash
# Подключение к локальной БД
psql -U postgres -d postgres

# Выполнение запросов для проверки таблиц
\dt  # список таблиц
\d users  # описание таблицы
```

### Структура основных таблиц

```sql
-- Пользователи
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    last_name VARCHAR(100) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    middle_name VARCHAR(100),
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Группы
CREATE TABLE groups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    year INT,
    university_id INT REFERENCES universities(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Дисциплины
CREATE TABLE courses (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    hours INT,
    credits INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Оценки
CREATE TABLE grades (
    id SERIAL PRIMARY KEY,
    student_id INT REFERENCES users(id),
    assignment_id INT REFERENCES assignments(id),
    lesson_column_id INT,
    value FLOAT,
    display_value VARCHAR(50),
    is_important BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Посещаемость
CREATE TABLE attendance (
    id SERIAL PRIMARY KEY,
    student_id INT REFERENCES users(id),
    assignment_id INT REFERENCES assignments(id),
    lesson_column_id INT,
    status VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 📝 Разработка и тестирование

### Режим разработки

Приложение запускается в режиме разработки по умолчанию:

```bash
python run.py
```

**Особенности:**
- Hot reload при изменении файлов
- Отладочная информация в консоль
- Отключена оптимизация производительности

### Режим продакшена

```bash
export FLASK_ENV=production
python run.py
```

---

## 🐛 Решение проблем

### Ошибка подключения к БД

```
Error: could not connect to server: Connection refused
```

**Решение:**
- Проверьте, что PostgreSQL запущен: `pg_isready`
- Проверьте учетные данные в `config.py`
- Убедитесь, что база данных создана

### Ошибка при импорте модулей

```
ModuleNotFoundError: No module named 'flask'
```

**Решение:**
```bash
pip install -r requirements.txt
```

### Ошибка CSRF/JWT токена

**Решение:**
- Проверьте, что SECRET_KEY и JWT_SECRET_KEY установлены
- Очистите cookies браузера
- Перезагрузитесь и войдите заново

---

## 📚 Зависимости проекта

```
Flask==3.1.2              # Веб-фреймворк
Flask_Bcrypt==1.0.1       # Хеширование паролей
Flask_JWT_Extended==4.7.1 # JWT аутентификация
flask_sqlalchemy==3.1.1   # ORM для работы с БД
openpyxl==3.1.5           # Работа с Excel файлами
pandas==3.0.0             # Обработка данных
psycopg2==2.9.6           # Драйвер PostgreSQL
```

Для установки всех зависимостей используйте:
```bash
pip install -r requirements.txt
```

---

## 📄 Лицензия

Этот проект является учебной работой и создан в образовательных целях.

---

## 👨‍💻 Автор

**Katronicsl**  
Студент 2 курса  
Дисциплина: ТРПО  
Дата создания: 2026

---

## 📞 Контакты и поддержка

Для вопросов и предложений по проекту обратитесь к автору или создайте Issue в репозитории.

**GitHub:** https://github.com/Katronicsl/education_journal
