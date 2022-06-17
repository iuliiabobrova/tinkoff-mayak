import pandas as pd

df_texts = pd.read_csv('csv/static_texts.csv', sep=',')

ask_feedback = df_texts.feedback[0]
feedback_text = df_texts.feedback[1]
positive_answer = df_texts.feedback[2]
negative_answer = df_texts.feedback[3]
thanks_for_feedback = "Спасибо за ваш отзыв! Мы успешно получили ваше сообщение: '{message}'"
feedback_cancelled = "Команда отменена"

positive_answer_button_text = "👍"
negative_answer_button_text = "👎"
ask_for_detailed_feedback_button_text = "Оставить развёрнутый отзыв"
