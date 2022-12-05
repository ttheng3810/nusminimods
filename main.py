import requests
import logging
import random
from const import *
from math import ceil
from datetime import date
from telegram import Bot, Update, ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import Updater, CommandHandler, ConversationHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler

# Enable logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)


def error(update, context):
    logging.exception("An error occurred.")

logger = logging.getLogger(__name__)


# Helper functions
def get_acad_year():
    today = date.today()
    today_mth, today_yr = today.month, today.year
    if 8 <= today_mth <= 12:
        acad_year = "-".join((str(today_yr), str(today_yr + 1)))
    elif 1 <= today_mth < 8:
        acad_year = "-".join((str(today_yr - 1), str(today_yr)))
    return acad_year


# Bot messages
WELCOME_MESSAGE = ["<b>Welcome to NUSMiniMods!</b> 📕", "This Telegram bot has two main functions: it provides a list of prerequisite modules for the modules that you plan to take next semester, as well as recommends a list of modules based on the modules you have taken this semester.", "Select the <b>Input Modules</b> button to get started.", "<a href='https://github.com/ttheng3810/nusminimods'>GitHub repo link</a>"]
COLLECT_MODULES = ["Please input the modules that you have taken <b>this semester</b> (for getting <b><i>recommendations</i></b>), or you are taking <b>next semester</b> (for getting <b><i>prerequisites</i></b>).", "To add modules, please type <code>/input_mod</code> followed by the module codes, e.g. <code>/input_mod CS1010S EC1101E</code>.", "To remove modules, please type <code>/remove_mod</code> followed by the module codes, e.g. <code>/remove_mod CS1010S EC1101E</code>.", "*<i>No changes occur if a valid module one attempts to remove is not among the currently input modules.</i>", "Once you are done, you can then choose to <b>Check for Prerequisites</b> or <b>Look for Recommendations</b>."]
PREREQ_MODULES = ["Here are the prerequisite modules required for each of your input modules. 📍"]
RECOMMENDED_MODULES = ["Here are some recommended modules based on each of your input modules. 💡", "<i>Disclaimer: some of these recommended modules may require other prerequisites.</i>"]


# Callback query data
INPUT_MODULE_DATA = "inputmoddata"
PREREQ_CALLBACK_DATA = "prereqcallbackdata"
RECOMMEND_CALLBACK_DATA = "recommendcallbackdata"
RESTART_DATA = "restartagaindata"


# Data global variables
last_message = None
collect_mod_module_code = []


# Callback query handler
def callback_query_handler(update: Update, context: CallbackContext) -> None:
    # message_id = update.callback_query.message.message_id
    # update_id = update.update_id
    cqd = update.callback_query.data
    if cqd == PREREQ_CALLBACK_DATA:
        prereq_command(update, context)
    if cqd == RECOMMEND_CALLBACK_DATA:
        recommend_command(update, context)
    if cqd == INPUT_MODULE_DATA:
        input_mod_command(update, context)
    if cqd == RESTART_DATA:
        start_command(update, context)


# /start behaviour (CommandHandler)
def start_command(update: Update, context: CallbackContext) -> None:
    global last_message, collect_mod_module_code
    last_message = None
    collect_mod_module_code = []
    chat_id = update.effective_user.id
    text_lst = WELCOME_MESSAGE
    input_module_button = InlineKeyboardButton(text="Input Modules", callback_data=INPUT_MODULE_DATA)
    markup = [[input_module_button]]
    message = context.bot.send_message(chat_id=chat_id, text="\n\n".join(text_lst), reply_markup=InlineKeyboardMarkup(markup), parse_mode=ParseMode.HTML)
    last_message = message


# (Invalid) message echo behaviour (MessageHandler)
def echo(update: Update, context: CallbackContext) -> None:
    update.message.reply_text(f"I don't understand <code>{update.message.text}</code>.", parse_mode=ParseMode.HTML)


# /tetris behaviour (CommandHandler)
def tetris_command(update: Update, context: CallbackContext) -> None:
    update.message.reply_text("<a href='https://nusmods.com/tetris'>You want TETRIS? Sure.</a>", parse_mode=ParseMode.HTML)


# /input_mod behaviour (CommandHandler)
def input_mod_command(update: Update, context: CallbackContext) -> None:
    global last_message, collect_mod_module_code
    incoming_message = update
    incoming_message_phrases = list(incoming_message.message.text.split(" ")) if incoming_message.message else []
    if incoming_message_phrases:
        incoming_message_phrases = incoming_message_phrases[incoming_message_phrases.index("/input_mod")+1:]
    collect_mod_module_code.extend(incoming_message_phrases)
    mod_input = set(collect_mod_module_code)

    acad_year = get_acad_year()
    mod_list = list(map(lambda mod: mod["moduleCode"], requests.get(f"https://api.nusmods.com/v2/{acad_year}/moduleList.json").json()))
    if any(mod not in mod_list for mod in mod_input):
        invalid = " ".join(filter(lambda mod: mod not in mod_list, mod_input))
        update.message.reply_text(f"<i>Some of your input module codes are invalid!</i>\n\n<code>{invalid}</code>", parse_mode=ParseMode.HTML)
    module_code = set(filter(lambda mod: mod in mod_list, mod_input))
    collect_mod_module_code = list(module_code)

    mod_data = list(map(lambda mod: requests.get(f"https://api.nusmods.com/v2/{acad_year}/modules/{mod}.json").json(), module_code))
    total_mc = sum(map(lambda data: int(data["moduleCredit"]), mod_data))
    if total_mc < 18:
        mc_message = "<i>Seems like your module combination does not meet the minimum workload requirement...</i>"
    elif 18 <= total_mc <= 20:
        mc_message = "<i>Just nice!</i>"
    elif total_mc > 20:
        mc_message = "❗ <i><b>Overload advice</b>: consider wisely before overloading.</i>"

    prereq_button = InlineKeyboardButton(text="Check for Prerequisites", callback_data=PREREQ_CALLBACK_DATA)
    recomm_button = InlineKeyboardButton(text="Look for Recommendations", callback_data=RECOMMEND_CALLBACK_DATA)
    markup = [[prereq_button], [recomm_button]]
    text_lst = COLLECT_MODULES + ["\n".join(module_code), f"<b>Total MCs: {total_mc} MC</b>", mc_message]
    chat_id = update.effective_user.id
    message = context.bot.send_message(chat_id=chat_id, text="\n\n".join(text_lst), reply_markup=InlineKeyboardMarkup(markup), parse_mode=ParseMode.HTML)
    last_message = incoming_message.message
        

# /remove_mod behaviour (CommandHandler)
def remove_mod_command(update: Update, context: CallbackContext) -> None:
    global last_message, collect_mod_module_code
    if len(collect_mod_module_code) == 0:
        update.message.reply_text(f"<i>You have nothing to remove!</i>", parse_mode=ParseMode.HTML)
    incoming_message = update
    incoming_message_phrases = list(incoming_message.message.text.split(" ")) if incoming_message.message else []
    if incoming_message_phrases:
        incoming_message_phrases = incoming_message_phrases[incoming_message_phrases.index("/remove_mod")+1:]
    collect_mod_module_code.extend(incoming_message_phrases)
    mod_input = set(collect_mod_module_code)

    acad_year = get_acad_year()
    mod_list = list(map(lambda mod: mod["moduleCode"], requests.get(f"https://api.nusmods.com/v2/{acad_year}/moduleList.json").json()))
    if any(mod not in mod_list or mod not in collect_mod_module_code for mod in mod_input):
        invalid = " ".join(filter(lambda mod: mod not in mod_list, mod_input))
        update.message.reply_text(f"<i>Some of your input module codes are invalid!</i>\n\n<code>{invalid}</code>", parse_mode=ParseMode.HTML)
    module_code = set(filter(lambda mod: mod in mod_list, mod_input)) - set(incoming_message_phrases)
    collect_mod_module_code = list(module_code)

    mod_data = list(map(lambda mod: requests.get(f"https://api.nusmods.com/v2/{acad_year}/modules/{mod}.json").json(), module_code))
    total_mc = sum(map(lambda data: int(data["moduleCredit"]), mod_data))
    if total_mc < 18:
        mc_message = "<i>Seems like your module combination does not meet the minimum workload requirement...</i>"
    elif 18 <= total_mc <= 20:
        mc_message = "<i>Just nice!</i>"
    elif total_mc > 20:
        mc_message = "❗ <i><b>Overload advice</b>: consider wisely before overloading.</i>"

    prereq_button = InlineKeyboardButton(text="Check for Prerequisites", callback_data=PREREQ_CALLBACK_DATA)
    recomm_button = InlineKeyboardButton(text="Look for Recommendations", callback_data=RECOMMEND_CALLBACK_DATA)
    markup = [[prereq_button], [recomm_button]]
    text_lst = COLLECT_MODULES + ["\n".join(module_code), f"<b>Total MCs: {total_mc} MC</b>", mc_message]
    chat_id = update.effective_user.id
    message = context.bot.send_message(chat_id=chat_id, text="\n\n".join(text_lst), reply_markup=InlineKeyboardMarkup(markup), parse_mode=ParseMode.HTML)
    last_message = incoming_message.message
        

def prereq_command(update: Update, context: CallbackContext) -> None:
    no_prereq = "<i>No prerequisites needed!</i> 😊"
    module_code = collect_mod_module_code
    format_mod = lambda mod_code: f"<a href='https://nusmods.com/modules/{mod_code}/'>{mod_code}</a>"
    
    acad_year = get_acad_year()
    mod_list = list(map(lambda mod: mod["moduleCode"], requests.get(f"https://api.nusmods.com/v2/{acad_year}/moduleList.json").json()))
    mod_data = list(map(lambda mod: requests.get(f"https://api.nusmods.com/v2/{acad_year}/modules/{mod}.json").json(), module_code))
    def flatten_tree(tree):
        if type(tree) == str:
            return tree
        def flatten(k, v):
            return f"({f' {k} '.join(map(lambda mod: format_mod(mod) if mod in mod_list else mod, filter(lambda mod: mod in mod_list or (mod[0] == '(' and mod[-1] == ')'), v)))})"
        flattened = []
        for k, v in tree.items():
            new_v = []
            for elem in v:
                if type(elem) == dict:
                    new_v.append(flatten_tree(elem))
                else:
                    new_v.append(elem)
            flattened.append(flatten(k, new_v))
        return " ".join(flattened)
    prereq_trees = list(map(lambda data: (data["moduleCode"], data.get("prereqTree", no_prereq)), mod_data))
    prereqs = "\n".join(map(lambda pair: f"<b>{pair[0]}</b>: {flatten_tree(pair[1])}", prereq_trees))
    
    recomm_button = InlineKeyboardButton(text="Look for Recommendations", callback_data=RECOMMEND_CALLBACK_DATA)
    restart_button = InlineKeyboardButton(text="Restart Session", callback_data=RESTART_DATA)
    markup = [[recomm_button], [restart_button]]
    chat_id = update.effective_user.id
    text_lst = PREREQ_MODULES + [prereqs]
    message = context.bot.send_message(chat_id=chat_id, text="\n\n".join(text_lst), reply_markup=InlineKeyboardMarkup(markup), parse_mode=ParseMode.HTML)


def recommend_command(update: Update, context: CallbackContext) -> None:
    module_code = collect_mod_module_code
    format_mod = lambda mod_code: f"<a href='https://nusmods.com/modules/{mod_code}/'>{mod_code}</a>"

    acad_year = get_acad_year()
    mod_data = list(map(lambda mod: requests.get(f"https://api.nusmods.com/v2/{acad_year}/modules/{mod}.json").json(), module_code))
    fulfil_requirements_lst = list(map(lambda data: (data["moduleCode"], data.get("fulfillRequirements")), mod_data))
    mod_list = list(map(lambda mod: mod["moduleCode"], requests.get(f"https://api.nusmods.com/v2/{acad_year}/moduleList.json").json()))
    recommended_mods = "\n".join(map(lambda pair: f"<b>{pair[0]}</b>: {', '.join(map(lambda mod: format_mod(mod), filter(lambda mod: mod in mod_list, random.sample(pair[1], ceil(len(pair[1])/3)))))}", fulfil_requirements_lst))
    
    prereq_button = InlineKeyboardButton(text="Check for Prerequisites", callback_data=PREREQ_CALLBACK_DATA)
    restart_button = InlineKeyboardButton(text="Restart Session", callback_data=RESTART_DATA)
    markup = [[prereq_button], [restart_button]]
    chat_id = update.effective_user.id
    text_lst = RECOMMENDED_MODULES + [recommended_mods]
    message = context.bot.send_message(chat_id=chat_id, text="\n\n".join(text_lst), reply_markup=InlineKeyboardMarkup(markup), parse_mode=ParseMode.HTML)


# Main bot function
def main() -> None:
    updater = Updater(TOKEN) # initialise updater and pass it with bot token
    dp = updater.dispatcher # dispatcher for registering handlers
    dp.add_error_handler(error)
    dp.add_handler(CommandHandler("start", start_command))
    dp.add_handler(CommandHandler("input_mod", input_mod_command))
    dp.add_handler(CommandHandler("remove_mod", remove_mod_command))
    dp.add_handler(CommandHandler("prereq", prereq_command))
    dp.add_handler(CommandHandler("recomm", recommend_command))
    dp.add_handler(CommandHandler("tetris", tetris_command))
    dp.add_handler(CallbackQueryHandler(callback_query_handler))
    dp.add_handler(MessageHandler(Filters.text, echo))
    
    updater.start_polling() # start the bot
    updater.idle() # run the bot until SIGINT, SIGTERM or SIGABRT signal received


if __name__ == "__main__":
    print("Bot started...")
    main()
