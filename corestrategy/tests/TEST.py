import asyncio

# def printer():
#     while True:
#         print('thr1 is ok')
#         Event().wait(timeout=1)
#
#
# def student(q):
#     while True:
#         # Получаем задание из очереди
#         check = q.get()
#         # Выводим время начала проверки
#         print(check[1], 'сдал работу в', datetime.datetime.now()
#               .strftime('%H:%M:%S'))
#         # Время затраченное на проверку, которое зависит от рейтинга
#         Event().wait(timeout=((100 - check[0]) / 5))
#         # Время окончания проверки
#         print(check[1], 'забрал работу в', datetime.datetime.now()
#               .strftime('%H:%M:%S'))
#         # Даём сигнал о том, что задание очереди выполнено
#         q.task_done()
#
#
# def run_delivery_boy(lst_of_sgnls):
#     # Загружаем в очередь студентов
#     for signal in lst_of_sgnls:
#         q.put(signal)
#     # создаём и запускаем потоки
#     thread2 = threading.Thread(target=student, args=(q,), daemon=True)
#     thread2.start()
#     # Блокируем дальнейшее выполнение до завершения всех заданий
#     q.join()
#     print("Этот текст напечатается после окончания блокировки")


# if __name__ == "__main__":
#
#     q = Queue()
#
#     thr_1 = threading.Thread(target=printer)
#     thr_1.start()
#
#     list_of_signals = [(99, "Андрей"),
#                        (76, "Александр"),
#                        (75, "Никита"),
#                        (72, "Евгений"),
#                        (66, "Алексей"),
#                        (62, "Сергей"),
#                        (50, "Михаил")]
#
#     for x in range(4):
#         run_delivery_boy(lst_of_sgnls=list_of_signals)
#         list_of_signals = [(99, 'XXX')]

# def get_attributes_list(cls):
#     """"""
#
#     for i in inspect.getmembers(cls):
#         if not i[0].startswith('_'):
#             if not inspect.ismethod(i[1]) and i[0] != 'DoesNotExist' 'MultipleObjectsReturned':
#                 print(i[0])


# print(Share.__doc__[6:-1].split(sep=', '))
from corestrategy.utils import timer


@timer
async def main():

    figi_list = list(range(1000))

    async def apply_filter(ticker) -> bool:
        await asyncio.sleep(1)
        print(ticker)
        return True

    async def async_filter(async_func, ticker):
        should_yield = await async_func(ticker)
        if should_yield:
            return ticker

    filtered_tickers = await asyncio.gather(*[async_filter(apply_filter, ticker) for ticker in figi_list])
    return filtered_tickers

a = asyncio.run(main())
print(a)
