import telebot

token = "8010104498:AAFu41LIYHrPWWl-kvT1pQ0GZrxE8AL0wZE"

bot = telebot.TeleBot(token)
HELP = '''
Список доступных команд:
* show  - напечать все задачи на заданную дату
* todo - добавить задачу
* random - добавить на сегодня случайную задачу
* help - Напечатать help
'''



@bot.message_handler(content_types=["text"])
def echo(message):
    bot.send_message(message.chat.id, message.text)


bot.polling(none_stop=True)