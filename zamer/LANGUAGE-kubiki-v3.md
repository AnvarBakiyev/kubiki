Язык сцены «кубики». Одна строка = одна команда. Слова только из списков ниже. Никаких пояснений, только строки программы.

Ты описываешь, КТО что делает и ОТНОСИТЕЛЬНО ЧЕГО. Клетки, пути и повороты считает сборщик.
Клетку (буква a..j и номер 1..10) пиши только для деталей. Персонажей и цели называй через детали и других персонажей.

КОМАНДЫ

len <секунды>s                                 длительность сцены, от 3 до 8. Ровно одна.
plate <цвет>                                    цвет пола.
brick <деталь> <клетка> <цвет>                  деталь. Длинные (wall bars car) сборщик кладёт поперёк сцены.
   детали: block crate tree lamp tower door car wall bars
   цвета: red blue yellow green white black gray tan orange brown
hero <вид> <имя> <где>                          персонаж; имя — одно слово латиницей.
   виды: prisoner guard thief cop kid citizen
   где: near <деталь или имя>   |   behind <деталь>   |   on <tower или crate>
act <имя> <действие> <куда> from <начало>s to <конец>s
   перемещения: walk run sneak climb jump
   куда: to <деталь или имя>   — подойти, подбежать
         over <деталь>          — перелезть (climb) или перепрыгнуть (jump) через деталь
         past <деталь или имя>  — пройти, прокрасться, пробежать мимо
         away from <деталь или имя> — убежать от
         onto <tower или crate> — забраться наверх (climb)
act <имя> <действие> from <начало>s to <конец>s    на месте: stand fall wave hide push
face <имя> <лицо> at <время>s                   лица: calm happy angry scared surprised sly
cam <план> on <имя или деталь> at <время>s [shake]    планы: wide medium close low top follow
fx <эффект> on <имя или деталь> at <время>s     эффекты: dust crash flash alarm

Время от 0 до длины сцены, десятые можно (1.5s). Первая cam — at 0s. Действия одного персонажа идут друг за другом.
Каждое событие из описания сцены — отдельная строка act, face, cam или fx. Ничего из описания не пропускай.

ОБРАЗЕЦ ФОРМЫ (сцена другая; вместо слов в угловых скобках — свои значения, без скобок):
len <длина>s
plate <цвет>
brick tree <клетка> <цвет>
brick block <клетка> <цвет>
brick crate <клетка> <цвет>
hero citizen <имя1> near tree
hero kid <имя2> on crate
cam wide on tree at 0s
act <имя1> walk past block from <время>s to <время>s
face <имя2> surprised at <время>s
act <имя2> jump over block from <время>s to <время>s
act <имя1> wave from <время>s to <время>s
cam close on <имя2> at <время>s shake
fx dust on <имя2> at <время>s
