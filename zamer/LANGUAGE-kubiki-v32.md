Язык сцены «кубики». Одна строка = одна команда. Слова только из списков ниже. Никаких пояснений, только строки программы.

Ты описываешь, КТО что делает и ОТНОСИТЕЛЬНО ЧЕГО. Клетки, пути и повороты считает сборщик.
Клеток не нужно: детали сборщик расставит сам. Персонажа называй по его виду: guard, prisoner, cop и так далее.
Если персонажей одного вида двое, второго зови с цифрой 2: guard2.

КОМАНДЫ

len <секунды>s                                 длительность сцены, от 3 до 8. Ровно одна.
plate <цвет>                                    цвет пола.
brick <деталь> <цвет>                           одна деталь на строку, одно слово детали.
   детали: block crate tree lamp tower door car wall bars
   цвета: red blue yellow green white black gray tan orange brown
hero <вид> <где>                                персонаж. Дальше в программе его зовут его видом.
   виды: prisoner guard thief cop kid citizen
   где: near <деталь или кто>   |   behind <деталь>   |   on <tower или crate>
        west of <деталь или кто>  |  east of ...  |  north of ...  |  south of ...   — в трёх клетках с этой стороны
        (чтобы двое прибежали с разных сторон, поставь их по разные стороны: west of и east of)
act <кто> <действие> <куда> from <начало>s to <конец>s
   перемещения: walk run sneak climb jump
   куда: to <деталь или кто>   — подойти, подбежать
         over <деталь>          — перелезть (climb) или перепрыгнуть (jump) через деталь
         past <деталь или кто>  — пройти, прокрасться, пробежать мимо
         away from <деталь или кто> — убежать от
         onto <tower или crate> — забраться наверх (climb)
act <кто> <действие> from <начало>s to <конец>s    на месте: stand fall wave hide push
act <кто> trip over <деталь> from <начало>s to <конец>s       добежать до детали, споткнуться и упасть
act <кто> stop at <деталь или кто> from <начало>s to <конец>s  добежать и остановиться рядом
act <кто> hide behind <деталь> from <начало>s to <конец>s      добежать за деталь и спрятаться
face <кто> <лицо> at <время>s                   лица: calm happy angry scared surprised sly
cam <план> on <кто или деталь> at <время>s [shake]    планы: wide medium close low top follow
fx <эффект> on <кто или деталь> at <время>s     эффекты: dust crash flash alarm

Время от 0 до длины сцены, десятые можно (1.5s). Первая cam — at 0s. Действия одного персонажа идут друг за другом.
Каждое событие из описания сцены — отдельная строка act, face, cam или fx. Ничего из описания не пропускай.

ОБРАЗЕЦ ФОРМЫ (сцена другая; вместо слов в угловых скобках — свои значения, без скобок):
len <длина>s
plate <цвет>
brick tree <цвет>
brick block <цвет>
brick crate <цвет>
hero citizen near tree
hero kid on crate
cam wide on tree at 0s
act citizen walk past block from <время>s to <время>s
face kid surprised at <время>s
act kid jump over block from <время>s to <время>s
act citizen wave from <время>s to <время>s
cam close on kid at <время>s shake
fx dust on kid at <время>s
