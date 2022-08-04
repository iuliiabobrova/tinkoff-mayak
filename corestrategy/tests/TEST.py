from datetime import datetime, timedelta, time, date
from os.path import getmtime
from pandas import to_datetime, read_csv, errors
import pandas
from threading import Event

from queue import Queue
import time, datetime, threading


def printer():
    while True:
        print('thr1 is ok')
        Event().wait(timeout=1)


def student(q):
    while True:
        # Получаем задание из очереди
        check = q.get()
        # Выводим время начала проверки
        print(check[1], 'сдал работу в', datetime.datetime.now()
              .strftime('%H:%M:%S'))
        # Время затраченное на проверку, которое зависит от рейтинга
        Event().wait(timeout=((100 - check[0]) / 5))
        # Время окончания проверки
        print(check[1], 'забрал работу в', datetime.datetime.now()
              .strftime('%H:%M:%S'))
        # Даём сигнал о том, что задание очереди выполнено
        q.task_done()


def run_delivery_boy(lst_of_sgnls):
    # Загружаем в очередь студентов
    for signal in lst_of_sgnls:
        q.put(signal)
    # создаём и запускаем потоки
    thread2 = threading.Thread(target=student, args=(q,), daemon=True)
    thread2.start()
    # Блокируем дальнейшее выполнение до завершения всех заданий
    q.join()
    print("Этот текст напечатается после окончания блокировки")


if __name__ == "__main__":

    q = Queue()

    thr_1 = threading.Thread(target=printer)
    thr_1.start()

    list_of_signals = [(99, "Андрей"),
                       (76, "Александр"),
                       (75, "Никита"),
                       (72, "Евгений"),
                       (66, "Алексей"),
                       (62, "Сергей"),
                       (50, "Михаил")]

    for x in range(4):
        run_delivery_boy(lst_of_sgnls=list_of_signals)
        list_of_signals = [(99, 'XXX')]


