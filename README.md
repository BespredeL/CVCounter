## <div align="center">CVCounter</div>
Данное решение далеко от идела, даже наверно вообще кусок ..., но оно рабочее =))
Это мой первый опыт работы с Python, поэтому получилось как получилось.


**В этом решение реализовано 2 вида просмотра:**
1. **Основной вид** - страница на которой выводится значение счетчиков и видео с результатом распознавания
2. **Текстовый вид** - страница на которой выводится только значение счетчиков
3. **Текстовый вид с двумя счетчиками** - страница на которой выводится значение 2 счетчиков (например на входе и выходе)

После нескольких вариантов, принял решение реализации на Flask, т.е решение в виде мини веб-сайта,
так как такое решение позволяет избежать установки какого либо дополнительного софта на клиенты.
А так же это решение не требовательно к клиентам в плане ресурсов (за исключением основного вида с видео)

Мне удалось запустить 5 одновременных подсчетов (без вывода видео), и 4 подсчета с выводом видео.<br>

Характеристики сервера:
- AMD Ryzen 5 3600
- GeForce GTX 1050 Ti (4Гб)

Все основные настройки находятся в файле config.json (переименуйте config.json.example в config.json)

**P.S.:** 
- Друзья, если вас не затруднит, не убирайте, пожалуйста, мой копирайт внизу страницы. Это не требование, но если оставите я буду очень вам благодарен! 
- Всё это реализовано без какого либо ТЗ и вообще никто не верил в успех, поэтому пока что есть некоторая хаотичность, но постараюсь всё переделать более правильно =)
- Если вам помогло это решение, вы можете проспонсировать меня отправив слово "Спасибо". Ссылки на контакты ниже =))
- Если нужна помощь с внедрением, можем обсудить =).

## Screenshots
<img src="https://github.com/BespredeL/BespredeL/blob/c27b6d786e6569cbaa17d49eac8c7433812a1024/Desktop-2023.12.31-13.16.42.01.gif" alt="" width="360">
<img src="https://github.com/BespredeL/BespredeL/blob/c27b6d786e6569cbaa17d49eac8c7433812a1024/Main%20View.png" alt="" width="360">
<img src="https://github.com/BespredeL/BespredeL/blob/c27b6d786e6569cbaa17d49eac8c7433812a1024/Text%20View.png" alt="" width="360">

## <div align="center">Author</div>

Александр Киреев

Website: [https://bespredel.name](https://bespredel.name)<br>
E-mail: [hello@bespredel.name](mailto:hello@bespredel.name)<br>
Telegram: [https://t.me/BespredeL_name](https://t.me/BespredeL_name)

## <div align="center">References</div>
Ultralytics: [https://github.com/ultralytics](https://github.com/ultralytics)

## <div align="center">License</div>
**AGPL-3.0 License**: This [OSI-approved](https://opensource.org/licenses/) open-source license is ideal for students and enthusiasts,
  promoting open collaboration and knowledge sharing.