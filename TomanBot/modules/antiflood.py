import html
from typing import Optional, List

from telegram import Message, Chat, Update, Bot, User, InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, ChatPermissions

from TomanBot import TIGER_USERS, WHITELIST_USERS, dispatcher
from TomanBot.modules.helper_funcs.chat_status import (
    bot_admin, can_restrict, connection_status, is_user_admin, user_admin,
    user_admin_no_reply)
from TomanBot.modules.log_channel import loggable
from TomanBot.modules.sql import antiflood_sql as sql
from telegram.error import BadRequest
from telegram.ext import CallbackContext, CallbackQueryHandler, CommandHandler, Filters, MessageHandler, run_async
from telegram.utils.helpers import mention_html, escape_markdown
from TomanBot import dispatcher
from TomanBot.modules.helper_funcs.chat_status import is_user_admin, user_admin, can_restrict
from TomanBot.modules.helper_funcs.string_handling import extract_time
from TomanBot.modules.log_channel import loggable
from TomanBot.modules.sql import antiflood_sql as sql
from TomanBot.modules.connection import connected
from TomanBot.modules.helper_funcs.alternate import send_message
FLOOD_GROUP = 3


@run_async
@loggable
def check_flood(update, context) -> str:
    user = update.effective_user  # type: Optional[User]
    chat = update.effective_chat  # type: Optional[Chat]
    msg = update.effective_message  # type: Optional[Message]
    if not user:  # ignore channels
        return ""

    # ignore admins and whitelists
    if (is_user_admin(chat, user.id) or user.id in WHITELIST_USERS or
            user.id in TIGER_USERS):
        sql.update_flood(chat.id, None)
        return ""

    should_ban = sql.update_flood(chat.id, user.id)
    if not should_ban:
        return ""

    try:
        getmode, getvalue = sql.get_flood_setting(chat.id)
        if getmode == 1:
            chat.kick_member(user.id)
            execstrings = ("Banned")
            tag = "BANNED"
        elif getmode == 2:
            chat.kick_member(user.id)
            chat.unban_member(user.id)
            execstrings = ("Kicked")
            tag = "KICKED"
        elif getmode == 3:
            context.bot.restrict_chat_member(
                chat.id,
                user.id,
                permissions=ChatPermissions(can_send_messages=False))
            execstrings = ("Muted")
            tag = "MUTED"
        elif getmode == 4:
            bantime = extract_time(msg, getvalue)
            chat.kick_member(user.id, until_date=bantime)
            execstrings = ("Baneado por {}".format(getvalue))
            tag = "TBAN"
        elif getmode == 5:
            mutetime = extract_time(msg, getvalue)
            context.bot.restrict_chat_member(
                chat.id,
                user.id,
                until_date=mutetime,
                permissions=ChatPermissions(can_send_messages=False))
            execstrings = ("Muteado por {}".format(getvalue))
            tag = "TMUTE"
        send_message(
            update.effective_message,
            "Maravilloso, me gusta dejar hacer explosiones y dejar desastres naturales pero tu, "
            "solo fuiste una decepci??n {}!".format(execstrings))

        return "<b>{}:</b>" \
               "\n#{}" \
               "\n<b>Usuario:</b> {}" \
               "\nFloodeo en el grupo.".format(tag, html.escape(chat.title),
                                             mention_html(user.id, user.first_name))

    except BadRequest:
        msg.reply_text(
            "No puedo restringir a las personas aqu??, dame permisos primero! Hasta entonces, desactivar?? el anti-flood.."
        )
        sql.set_flood(chat.id, 0)
        return "<b>{}:</b>" \
               "\n#INFO" \
               "\nNo tengo suficiente permiso para restringir a los usuarios, por lo que la funci??n anti-flood se desactiva autom??ticamente".format(chat.title)


@run_async
@user_admin_no_reply
@bot_admin
def flood_button(update: Update, context: CallbackContext):
    bot = context.bot
    query = update.callback_query
    user = update.effective_user
    match = re.match(r"unmute_flooder\((.+?)\)", query.data)
    if match:
        user_id = match.group(1)
        chat = update.effective_chat.id
        try:
            bot.restrict_chat_member(
                chat,
                int(user_id),
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True))
            update.effective_message.edit_text(
                f"Unmuted by {mention_html(user.id, user.first_name)}.",
                parse_mode="HTML")
        except:
            pass


@run_async
@user_admin
@loggable
def set_flood(update, context) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    message = update.effective_message  # type: Optional[Message]
    args = context.args

    conn = connected(context.bot, update, chat, user.id, need_admin=True)
    if conn:
        chat_id = conn
        chat_name = dispatcher.bot.getChat(conn).title
    else:
        if update.effective_message.chat.type == "private":
            send_message(update.effective_message,
                         "Este comando est?? destinado a usarse en grupo, no en PM")
            return ""
        chat_id = update.effective_chat.id
        chat_name = update.effective_message.chat.title

    if len(args) >= 1:
        val = args[0].lower()
        if val == "off" or val == "no" or val == "0":
            sql.set_flood(chat_id, 0)
            if conn:
                text = message.reply_text(
                    "El anti-flood ha sido deshabilitado en {}.".format(chat_name))
            else:
                text = message.reply_text("El anti-flood ha sido deshabilitado.")

        elif val.isdigit():
            amount = int(val)
            if amount <= 0:
                sql.set_flood(chat_id, 0)
                if conn:
                    text = message.reply_text(
                        "El anti-flood ha sido deshabilitado en {}.".format(chat_name))
                else:
                    text = message.reply_text("El anti-flood ha sido deshabilitado.")
                return "<b>{}:</b>" \
                       "\n#SetFlood" \
                       "\n<b>Administrador:</b> {}" \
                       "\nDesactivo el anti-flood.".format(html.escape(chat_name), mention_html(user.id, user.first_name))

            elif amount < 3:
                send_message(
                    update.effective_message,
                    "El anti-flood debe ser 0 (desactivado) o un n??mero mayor que 3!"
                )
                return ""

            else:
                sql.set_flood(chat_id, amount)
                if conn:
                    text = message.reply_text(
                        " El anti-flood se ha configurado en {} en el chat: {}".format(
                            amount, chat_name))
                else:
                    text = message.reply_text(
                        "L??mite anti-flood actualizado con ??xito para {}!".format(
                            amount))
                return "<b>{}:</b>" \
                       "\n#SETFLOOD" \
                       "\n<b>Administrador:</b> {}" \
                       "\nEstablecer anti-flood en <code>{}</code>.".format(html.escape(chat_name),
                                                                    mention_html(user.id, user.first_name), amount)

        else:
            message.reply_text(
                "Argumento no v??lido, utilice un n??mero, 'off' o 'no'")
    else:
        message.reply_text((
            "Use `/setflood (numero)` para habilitar anti-flood.\nO use `/setflood off` para deshabilitar anti-flood!."
        ),
                           parse_mode="markdown")
    return ""


@run_async
def flood(update, context):
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    msg = update.effective_message

    conn = connected(context.bot, update, chat, user.id, need_admin=False)
    if conn:
        chat_id = conn
        chat_name = dispatcher.bot.getChat(conn).title
    else:
        if update.effective_message.chat.type == "private":
            send_message(update.effective_message,
                         "Este comando est?? destinado a usarse en grupo, no en PM")
            return
        chat_id = update.effective_chat.id
        chat_name = update.effective_message.chat.title

    limit = sql.get_flood_limit(chat_id)
    if limit == 0:
        if conn:
            text = msg.reply_text(
                "No estoy imponiendo ning??n control de flood en {}!".format(chat_name))
        else:
            text = msg.reply_text("No estoy imponiendo ning??n control de flood aqu??!")
    else:
        if conn:
            text = msg.reply_text(
                "Actualmente estoy restringiendo miembros despu??s de {} mensajes consecutivos en {}."
                .format(limit, chat_name))
        else:
            text = msg.reply_text(
                "Actualmente estoy restringiendo miembros despu??s de {} mensajes consecutivos."
                .format(limit))


@run_async
@user_admin
def set_flood_mode(update, context):
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    msg = update.effective_message  # type: Optional[Message]
    args = context.args

    conn = connected(context.bot, update, chat, user.id, need_admin=True)
    if conn:
        chat = dispatcher.bot.getChat(conn)
        chat_id = conn
        chat_name = dispatcher.bot.getChat(conn).title
    else:
        if update.effective_message.chat.type == "private":
            send_message(update.effective_message,
                         "Este comando est?? destinado a usarse en grupo, no en PM")
            return ""
        chat = update.effective_chat
        chat_id = update.effective_chat.id
        chat_name = update.effective_message.chat.title

    if args:
        if args[0].lower() == 'ban':
            settypeflood = ('ban')
            sql.set_flood_strength(chat_id, 1, "0")
        elif args[0].lower() == 'kick':
            settypeflood = ('kick')
            sql.set_flood_strength(chat_id, 2, "0")
        elif args[0].lower() == 'mute':
            settypeflood = ('mute')
            sql.set_flood_strength(chat_id, 3, "0")
        elif args[0].lower() == 'tban':
            if len(args) == 1:
                teks = """Parece que intent?? establecer un valor de tiempo para el antiflood pero no especific?? el tiempo; Prueba, `/setfloodmode tban <valor de tiempo>`.

Ejemplos de valor de tiempo: 4m = 4 minutos, 3h = 3 horas, 6d = 6 d??as, 5w = 5 semanas."""
                send_message(
                    update.effective_message, teks, parse_mode="markdown")
                return
            settypeflood = ("tban for {}".format(args[1]))
            sql.set_flood_strength(chat_id, 4, str(args[1]))
        elif args[0].lower() == 'tmute':
            if len(args) == 1:
                teks = update.effective_message, """Parece que intent?? establecer un valor de tiempo para el antiflood pero no especific?? el tiempo; Prueba, `/setfloodmode tmute <valor de tiempo>`.

Ejemplos de valor de tiempo: 4m = 4 minutos, 3h = 3 horas, 6d = 6 d??as, 5w = 5 semanas."""
                send_message(
                    update.effective_message, teks, parse_mode="markdown")
                return
            settypeflood = ("tmute for {}".format(args[1]))
            sql.set_flood_strength(chat_id, 5, str(args[1]))
        else:
            send_message(update.effective_message,
                         "Solo entiendo /ban /kick /mute /tban /tmute!")
            return
        if conn:
            text = msg.reply_text(
                "Exceder el l??mite de flood consecutivos resultar?? en {} en {}!"
                .format(settypeflood, chat_name))
        else:
            text = msg.reply_text(
                "Exceder el l??mite de flood consecutivo resultar?? en {}!".format(
                    settypeflood))
        return "<b>{}:</b>\n" \
                "<b>Administrador:</b> {}\n" \
                "Ha cambiado el modo anti-flood. Al usuario {}.".format(settypeflood, html.escape(chat.title),
                                                                            mention_html(user.id, user.first_name))
    else:
        getmode, getvalue = sql.get_flood_setting(chat.id)
        if getmode == 1:
            settypeflood = ('ban')
        elif getmode == 2:
            settypeflood = ('kick')
        elif getmode == 3:
            settypeflood = ('mute')
        elif getmode == 4:
            settypeflood = ('tban for {}'.format(getvalue))
        elif getmode == 5:
            settypeflood = ('tmute for {}'.format(getvalue))
        if conn:
            text = msg.reply_text(
                "Enviar m??s mensajes que el l??mite de flood resultar?? en {} en {}."
                .format(settypeflood, chat_name))
        else:
            text = msg.reply_text(
                "Enviar m??s mensajes que el l??mite de flood resultar?? en {}."
                .format(settypeflood))
    return ""


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    limit = sql.get_flood_limit(chat_id)
    if limit == 0:
        return "No hacer cumplir el control de flood."
    else:
        return "El anti-flood se ha establecido en`{}`.".format(limit)


__help__ = """
El antiflood le permite tomar medidas sobre los usuarios que env??an m??s de x mensajes seguidos. Superando la inundaci??n establecida \
resultar?? en la restricci??n de ese usuario.

 Esto silenciar?? a los usuarios si env??an m??s de 10 mensajes seguidos, los bots se ignoran.
 ??? `/flood`*:* Obtiene la configuraci??n actual de control deflood

??? *Solo administradores:*
 ??? `/setflood <int / 'no' / 'off'>`*: * Habilita o deshabilita el control de flood
 *Ejemplo:* `/ setflood 10`
 ??? `/setfloodmode <ban / kick / mute / tban / tmute> <valor>`*:* Acci??n a realizar cuando el usuario ha superado el l??mite de inundaci??n. ban / kick / mute / tmute / tban

??? *Nota:*
 ??? Se debera completar el valor para tban y tmute !!
 Puede ser:
 `5m` = 5 minutos
 `6h` = 6 horas
 `3d` = 3 d??as
 `1w` = 1 semana
 """

__mod_name__ = "Anti-Flood"

FLOOD_BAN_HANDLER = MessageHandler(
    Filters.all & ~Filters.status_update & Filters.group, check_flood)
SET_FLOOD_HANDLER = CommandHandler("setflood", set_flood, filters=Filters.group)
SET_FLOOD_MODE_HANDLER = CommandHandler(
    "setfloodmode", set_flood_mode, pass_args=True)  #, filters=Filters.group)
FLOOD_QUERY_HANDLER = CallbackQueryHandler(
    flood_button, pattern=r"unmute_flooder")
FLOOD_HANDLER = CommandHandler("flood", flood, filters=Filters.group)

dispatcher.add_handler(FLOOD_BAN_HANDLER, FLOOD_GROUP)
dispatcher.add_handler(FLOOD_QUERY_HANDLER)
dispatcher.add_handler(SET_FLOOD_HANDLER)
dispatcher.add_handler(SET_FLOOD_MODE_HANDLER)
dispatcher.add_handler(FLOOD_HANDLER)

__handlers__ = [(FLOOD_BAN_HANDLER, FLOOD_GROUP), SET_FLOOD_HANDLER,
                FLOOD_HANDLER, SET_FLOOD_MODE_HANDLER]
