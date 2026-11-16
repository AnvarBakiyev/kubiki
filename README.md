# Кубики: мультфильм из текста

Немые мультфильмы про человечков из кубиков. Человек пишет сцену обычными словами, языковая модель
переводит её в короткую программу на маленьком языке сцены, а Blender рисует кадры. Человечков,
детали и город строит код, готовые модели не используются.

Пример сцены: «Вор крадётся мимо ящика и прячется за деревом. Камера средним планом на воре».
Модель пишет программу:

```
len 6s
plate tan
brick crate brown
brick tree green
hero thief near crate
act thief sneak past crate from 0s to 3s
act thief hide behind tree from 3s to 5s
face thief sly at 4s
cam medium on thief at 0s
```

Сборщик расставляет детали по клеткам, считает пути и повороты и отдаёт JSON сцены. Рендер Blender
строит площадку, город вокруг, персонажей и камеру.

## Что уже получилось

Цифры из [zamer/REPORT.md](zamer/REPORT.md). Там же видно, как каждая цифра получена.

| что | результат |
|---|---|
| Qwen 3.5 9B, первая версия языка, 10 сцен | 1 из 10 верных |
| DeepSeek-V4-Flash, язык v3.2, исправление по ошибкам сборщика, 3 попытки, отбор судьёй | 78 % сцен верны по строгой ручной проверке |
| Серия 1 «Побег», 29 сцен по 6 с | сборщик принял 29 из 29, судья 24 из 29, на глаз читается 26 из 29 |
| Серия 2 «Прятки», 29 сцен по 6 с, город вокруг площадки | сборщик принял 29 из 29, судья 19 из 29, на глаз читается 29 из 29, из них 9 слабых |
| Рендер Eevee 1080p на MacBook Pro M2 Pro | 2,3–2,8 с на кадр; серия 3 минуты за 80–90 мин, с городом около 126 мин |

Серия 1 «Побег»: лист кадров [seriya1/out/sheet.jpg](seriya1/out/sheet.jpg), ролик в релизе v0.1-seriya1.
Серия 2 «Прятки» (город вокруг площадки, волосы, герои не проходят друг сквозь друга, камера снимает
группу героев): лист кадров [seriya2/out/sheet.jpg](seriya2/out/sheet.jpg), ролик в релизе v0.2-seriya2.

## Как продолжить работу

Сначала прочитайте [HOW-WE-WORK.md](HOW-WE-WORK.md): там описан порядок работы, история
решений и открытые задачи.

## Установка

Нужны Python 3.10+, numpy, ffmpeg и Blender 4.3 (проверено на 4.3.2).

```bash
pip install numpy
export BLENDER=/path/to/blender          # на macOS по умолчанию /Applications/Blender.app/Contents/MacOS/Blender
export KUBIKI_FRAMES=~/kubiki-frames     # сюда пишутся кадры, это десятки гигабайт на серию
```

Модель можно подключить двумя способами:

- Ollama на своей машине (по умолчанию): `ollama pull qwen3.5:9b`.
- Любой сервер с OpenAI-совместимым `chat/completions` (так работала серия на DeepSeek-V4-Flash):

```bash
export KUBIKI_BACKEND=api
export KUBIKI_API_URL=https://<ваш-сервер>/openai/v1/chat/completions
export KUBIKI_API_MODEL=DeepSeek-V4-Flash
export KUBIKI_API_KEY=...                # или положите ключ в ~/.config/kubiki/api.key
```

Звук. По умолчанию эффекты синтезирует сам код (`zamer/sound_kubiki.py`). Чтобы взять эффекты из банка
[earshot](https://github.com/Leonxlnx/earshot), поставьте его в отдельное окружение и запускайте
шаг `sound` питоном из него.

## Быстрый старт

Проверить программу сборщиком. Он печатает развёрнутую программу с клетками и «ок» или список ошибок:

```bash
cd zamer
python3 kubiki_core31.py ruchnye/v32_test.kub
```

Нарисовать сцену из готового JSON (здесь кадры с 1-го по 12-й):

```bash
$BLENDER -b --factory-startup --python zamer/render_kubiki.py -- \
  --scene seriya1/out/programs/01.json --out /tmp/kubiki01 --res 960x540 --samples 16 --frames 1-12 --place street
```

Серия целиком, номер серии вторым аргументом:

```bash
cd seriya1
python3 series.py programs 2     # программы сцен моделью, судья, выбор попытки
python3 series.py render 2       # кадры
python3 series.py sound 2        # звук
python3 series.py assemble 2     # титр, склейка, звук -> seriya2/out/seriya2.mp4
python3 series.py sheet 2        # лист кадров для проверки на глаз
```

## Что где лежит

| путь | что внутри |
|---|---|
| `zamer/LANGUAGE-kubiki-v32.md` | текущий язык сцены, именно его модель получает в подсказке |
| `zamer/LANGUAGE-kubiki*.md` | прошлые версии языка: v1, v2, v3, v3.1 |
| `zamer/kubiki_core*.py` | сборщики по версиям языка. Текущий `kubiki_core31.py`, он собирает и v3.1, и v3.2 |
| `zamer/run3.py`, `repair.py` | прогон модели по десяти сценам замера и круг исправления по ошибкам сборщика |
| `zamer/CHECKS-kubiki.md`, `judge.py` | судья: модель читает описание сцены и пишет проверки, код сверяет их со сценой |
| `zamer/scenes.json`, `staging.py` | десять сцен замера и ручные условия, которыми мерили судью |
| `zamer/render_kubiki.py` | рендер Blender: детали, человечки, камера с проверкой лучом, движение |
| `zamer/city_block.py` | город вокруг площадки для мест street, park, market, prison |
| `zamer/sound_kubiki.py`, `sound_earshot.py` | звук: музыка и эффекты по событиям сцены |
| `zamer/out/` | все ответы моделей из замера с результатами проверок |
| `zamer/clip/` | короткие ролики и листы кадров по ходу замера |
| `seriya1/`, `seriya2/` | сценарии серий, программы сцен, выбор судьи |

## Лицензия

GPL-3.0-or-later, см. [LICENSE](LICENSE). Рендер работает внутри Blender, а Blender распространяется
по GPL, поэтому весь код под той же лицензией.

Проект не связан с LEGO Group. Детали и человечки построены кодом и только похожи на кубики
конструктора.

---

**English summary.** Text-to-cartoon pipeline for silent brick-figure shorts. An LLM turns a plain
scene description into a program in a tiny scene language (`zamer/LANGUAGE-kubiki-v32.md`). A Python
compiler lays the scene out, an LLM judge checks it against the description, and Blender (Eevee) renders
it with procedural bricks, figures and a city. Best result: DeepSeek-V4-Flash, 3 attempts and judge
selection give 78 % correct scenes. Episode 1: 26 of 29 scenes readable by eye. Episode 2 (city, hair,
group-aware camera): 29 of 29 readable, 9 of them weak. Docs are in Russian.
Start with `HOW-WE-WORK.md`.
