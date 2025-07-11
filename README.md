# Асинхронный сумматор компенсационного фонда СРО

Этот проект представляет собой **асинхронный скрипт** для сайтов:
- [reestr.nostroy.ru](https://reestr.nostroy.ru/api/sro/list)
- [reestr.nopriz.ru](https://reestr.nopriz.ru/api/sro/list)

Скрипт суммирует взносы в компенсационный фонд (ООД) для каждой СРО, выводя готовый CSV-отчёт.

Работает **асинхронно**, поэтому обрабатывает сотни страниц параллельно.

Проверка SSL отключена (`ssl_ctx.verify_mode = ssl.CERT_NONE`), так как серверы реестров могут отдавать некорректные сертификаты.

## Установка и запуск локально

1. **Клонирование репозитория**
   ```bash
   git clone https://github.com/ai-zaytsev/sro_parsing_comfond.git
   cd sro_parsing_comfond

2. **(Опционально) виртуальное окружение**

   ```bash
   python -m venv venv
   source venv/bin/activate   # Linux/Mac
   venv\Scripts\activate      # Windows
   ```
3. **Установка зависимостей**

   ```bash
   pip install -r requirements.txt
   ```
4. **Запуск**

   ```bash
   python main.py both
   ```

   После выполнения появится `result.csv` в корне проекта.

---

## Как работает скрипт?

1. Делает **асинхронные HTTP-POST-запросы** к API НОПРИЗ/НОСТРОЙ.
2. Определяет количество страниц (`countPages`).
3. Параллельно опрашивает все страницы, вытягивая суммы взносов.
4. Записывает результаты постранично в `result.csv`.

---

## CI/CD и Docker

### Автоматическая сборка Docker-образа

* Настроен **GitHub Actions**: при каждом пуше, если изменились файлы кода, `Dockerfile` или `requirements.txt`, собирается Docker-образ и публикуется в [Docker Hub](https://hub.docker.com/r/aizaytsev/sro-parsing-comfond).
* При изменениях только `README.md` (или файлов, указанных в `paths-ignore`) Action **не** запускается, и новый образ **не** создаётся.

### Локально

```bash
# Сборка
docker build -t aizaytsev/sro-parsing-comfond:latest .

# Тестовый запуск (результат сохранится в текущую папку)
mkdir -p output
docker run --rm \
  -v $(pwd)/output:/app \
  aizaytsev/sro-parsing-comfond:latest both
```

### Обновление Docker-образа на сервере

После того как GitHub Actions соберёт новую версию образа и загрузит её в Docker Hub, **сервер не обновляется автоматически**. Чтобы вручную получить свежий код:

```bash
docker pull aizaytsev/sro-parsing-comfond:latest
docker stop sro_parser || true
docker rm sro_parser  || true

docker run --rm -d \
  --name sro_parser \
  -v /srv/sro_data:/app \
  aizaytsev/sro-parsing-comfond:latest both
```

---

## ❓ Возможные проблемы и решения

| Ошибка                                           | Решение                                                        |
| ------------------------------------------------ | -------------------------------------------------------------- |
| `ModuleNotFoundError: No module named 'aiohttp'` | Установите зависимости: `pip install -r requirements.txt`      |
| `SSL: CERTIFICATE_VERIFY_FAILED`                 | Проверка SSL уже отключена, ошибка не должна возникнуть.       |
| `PermissionError: [Errno 13]` при записи CSV     | Убедитесь, что у вас есть права на запись в монтируемую папку. |

---

## Лицензия

Проект распространяется под лицензией **MIT**.

