# script/QFNUGetFreeClassrooms/main.py

import logging
import os
import sys
import re
import json

# 添加项目根目录到sys.path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app.config import *
from app.api import *
from app.switch import load_switch, save_switch


# 数据存储路径，实际开发时，请将QFNUGetFreeClassrooms替换为具体的数据存放路径
DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "QFNUGetFreeClassrooms",
)


# 查看功能开关状态
def load_function_status(group_id):
    return load_switch(group_id, "QFNUGetFreeClassrooms")


# 保存功能开关状态
def save_function_status(group_id, status):
    save_switch(group_id, "QFNUGetFreeClassrooms", status)


async def save_account_and_password(
    websocket, user_id, message_id, raw_message, authorized
):
    """保存账号和密码"""
    if not authorized:
        await send_private_msg(
            websocket,
            user_id,
            f"[CQ:reply,id={message_id}]❌❌❌你没有权限对QFNUGetFreeClassrooms功能进行操作,请联系管理员。",
        )
        return
    if raw_message.startswith("存储教务账号密码"):
        account, password = raw_message.replace("存储教务账号密码", "").split(" ")
        # 确保数据目录存在
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(os.path.join(DATA_DIR, "account.json"), "w") as f:
            json.dump({"account": account, "password": password}, f)
        await send_private_msg(
            websocket,
            user_id,
            f"[CQ:reply,id={message_id}]✅✅✅账号和密码已保存",
        )


def load_account_and_password():
    """加载账号和密码"""
    with open(os.path.join(DATA_DIR, "account.json"), "r") as f:
        return json.load(f)


# 处理开关状态
async def toggle_function_status(websocket, group_id, message_id, authorized):
    if not authorized:
        await send_group_msg(
            websocket,
            group_id,
            f"[CQ:reply,id={message_id}]❌❌❌你没有权限对QFNUGetFreeClassrooms功能进行操作,请联系管理员。",
        )
        return

    if load_function_status(group_id):
        save_function_status(group_id, False)
        await send_group_msg(
            websocket,
            group_id,
            f"[CQ:reply,id={message_id}]🚫🚫🚫QFNUGetFreeClassrooms功能已关闭",
        )
    else:
        save_function_status(group_id, True)
        await send_group_msg(
            websocket,
            group_id,
            f"[CQ:reply,id={message_id}]✅✅✅QFNUGetFreeClassrooms功能已开启",
        )


# 群消息处理函数
async def handle_group_message(websocket, msg):
    """处理群消息"""
    # 确保数据目录存在
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        user_id = str(msg.get("user_id"))
        group_id = str(msg.get("group_id"))
        raw_message = str(msg.get("raw_message"))
        message_id = str(msg.get("message_id"))
        authorized = user_id in owner_id

        # 处理开关命令
        if raw_message.lower() == "qgfc":
            await toggle_function_status(websocket, group_id, message_id, authorized)
            return
        # 检查功能是否开启
        if load_function_status(group_id):
            # 其他群消息处理逻辑
            pass
    except Exception as e:
        logging.error(f"处理QFNUGetFreeClassrooms群消息失败: {e}")
        await send_group_msg(
            websocket,
            group_id,
            "处理QFNUGetFreeClassrooms群消息失败，错误信息：" + str(e),
        )
        return


# 私聊消息处理函数
async def handle_private_message(websocket, msg):
    """处理私聊消息"""
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        user_id = str(msg.get("user_id"))
        raw_message = str(msg.get("raw_message"))
        authorized = user_id in owner_id
        # 私聊消息处理逻辑
        await save_account_and_password(websocket, user_id, raw_message, authorized)
    except Exception as e:
        logging.error(f"处理QFNUGetFreeClassrooms私聊消息失败: {e}")
        await send_private_msg(
            websocket,
            msg.get("user_id"),
            "处理QFNUGetFreeClassrooms私聊消息失败，错误信息：" + str(e),
        )
        return


# 群通知处理函数
async def handle_group_notice(websocket, msg):
    """处理群通知"""
    # 确保数据目录存在
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        user_id = str(msg.get("user_id"))
        group_id = str(msg.get("group_id"))
        notice_type = str(msg.get("notice_type"))
        operator_id = str(msg.get("operator_id", ""))

    except Exception as e:
        logging.error(f"处理QFNUGetFreeClassrooms群通知失败: {e}")
        await send_group_msg(
            websocket,
            group_id,
            "处理QFNUGetFreeClassrooms群通知失败，错误信息：" + str(e),
        )
        return


# 回应事件处理函数
async def handle_response(websocket, msg):
    """处理回调事件"""
    try:
        echo = msg.get("echo")
        if echo and echo.startswith("xxx"):
            # 回调处理逻辑
            pass
    except Exception as e:
        logging.error(f"处理QFNUGetFreeClassrooms回调事件失败: {e}")
        await send_group_msg(
            websocket,
            msg.get("group_id"),
            f"处理QFNUGetFreeClassrooms回调事件失败，错误信息：{str(e)}",
        )
        return


# 统一事件处理入口
async def handle_events(websocket, msg):
    """统一事件处理入口"""
    post_type = msg.get("post_type", "response")  # 添加默认值
    try:
        # 处理回调事件
        if msg.get("status") == "ok":
            await handle_response(websocket, msg)
            return

        post_type = msg.get("post_type")

        # 处理元事件
        if post_type == "meta_event":
            ...

        # 处理消息事件
        elif post_type == "message":
            message_type = msg.get("message_type")
            if message_type == "group":
                await handle_group_message(websocket, msg)
            elif message_type == "private":
                await handle_private_message(websocket, msg)

        # 处理通知事件
        elif post_type == "notice":
            await handle_group_notice(websocket, msg)

    except Exception as e:
        error_type = {
            "message": "消息",
            "notice": "通知",
            "request": "请求",
            "meta_event": "元事件",
        }.get(post_type, "未知")

        logging.error(f"处理QFNUGetFreeClassrooms{error_type}事件失败: {e}")

        # 发送错误提示
        if post_type == "message":
            message_type = msg.get("message_type")
            if message_type == "group":
                await send_group_msg(
                    websocket,
                    msg.get("group_id"),
                    f"处理QFNUGetFreeClassrooms{error_type}事件失败，错误信息：{str(e)}",
                )
            elif message_type == "private":
                await send_private_msg(
                    websocket,
                    msg.get("user_id"),
                    f"处理QFNUGetFreeClassrooms{error_type}事件失败，错误信息：{str(e)}",
                )
