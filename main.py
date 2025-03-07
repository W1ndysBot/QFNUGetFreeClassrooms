# script/QFNUGetFreeClassrooms/main.py

import logging
import os
import sys
import re
import json
from bs4 import BeautifulSoup

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


# 解析HTML内容，获取教室课程安排信息
def parse_classroom_schedule(html_content, day_of_week=None, time_slot=None):
    """
    解析HTML内容，获取教室课程安排信息
    
    参数:
        html_content: 教务系统返回的HTML内容
        day_of_week: 星期几 (1-7，1代表星期一，如果为None则返回所有天的数据)
        time_slot: 时间段 (可选值: "0102", "0304", "0506", "0708", "091011", "1213"，如果为None则返回所有时间段)
    
    返回:
        dict: 按天和时间段组织的教室课程安排字典，格式为 {day: {time_slot: {classroom: course_info}}}
    """
    # 解析HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 获取所有教室行
    classroom_rows = soup.select('#kbtable tr')
    
    # 跳过表头行
    classroom_rows = classroom_rows[2:]  # 跳过前两行表头
    
    # 初始化结果字典
    classroom_schedule = {}
    for d in range(1, 8):  # 1-7表示周一到周日
        classroom_schedule[d] = {}
        for t in ["0102", "0304", "0506", "0708", "091011", "1213"]:
            classroom_schedule[d][t] = {}
    
    # 遍历每个教室行
    for row in classroom_rows:
        cells = row.find_all('td')
        if len(cells) < 43:  # 确保行有足够的单元格
            continue
        
        # 获取教室名称
        classroom_name = cells[0].get_text().strip()
        
        # 遍历每天的每个时间段
        for day in range(1, 8):  # 1-7表示周一到周日
            for time_idx, time_period in enumerate(["0102", "0304", "0506", "0708", "091011", "1213"]):
                # 计算单元格索引
                cell_idx = (day - 1) * 6 + time_idx + 1
                
                # 获取单元格内容
                cell_content = cells[cell_idx].get_text().strip()
                if cell_content and cell_content != "&nbsp;" and cell_content != " ":
                    # 有课程安排
                    classroom_schedule[day][time_period][classroom_name] = cell_content
    
    # 如果指定了特定的天和时间段，只返回那些数据
    if day_of_week is not None and time_slot is not None:
        return {day_of_week: {time_slot: classroom_schedule[day_of_week][time_slot]}}
    elif day_of_week is not None:
        return {day_of_week: classroom_schedule[day_of_week]}
    elif time_slot is not None:
        result = {}
        for day in range(1, 8):
            if day not in result:
                result[day] = {}
            result[day][time_slot] = classroom_schedule[day][time_slot]
        return result
    
    return classroom_schedule

# 获取空闲教室信息
def get_free_classrooms(classroom_schedule, all_classrooms, day_of_week=None, time_slot=None):
    """
    根据课程安排获取空闲教室信息
    
    参数:
        classroom_schedule: parse_classroom_schedule函数返回的字典
        all_classrooms: 所有教室的列表
        day_of_week: 星期几 (1-7，1代表星期一，如果为None则返回所有天的数据)
        time_slot: 时间段 (可选值: "0102", "0304", "0506", "0708", "091011", "1213"，如果为None则返回所有时间段)
    
    返回:
        dict: 按天和时间段组织的空闲教室字典
    """
    free_classrooms = {}
    
    days_to_process = [day_of_week] if day_of_week is not None else range(1, 8)
    
    for day in days_to_process:
        if isinstance(day, int):  # 确保day是整数
            if day not in free_classrooms:
                free_classrooms[day] = {}
            
            time_slots_to_process = [time_slot] if time_slot is not None else ["0102", "0304", "0506", "0708", "091011", "1213"]
            
            for slot in time_slots_to_process:
                # 获取该时间段有课的教室
                occupied_classrooms = set(classroom_schedule.get(day, {}).get(slot, {}).keys())
                
                # 计算空闲教室
                free_classrooms[day][slot] = [room for room in all_classrooms if room not in occupied_classrooms]
    
    return free_classrooms

# 格式化输出空闲教室信息
def format_free_classrooms(free_classrooms):
    """
    将空闲教室信息格式化为易读的文本
    
    参数:
        free_classrooms: get_free_classrooms函数返回的字典
    
    返回:
        str: 格式化后的文本
    """
    weekday_names = {
        1: "星期一",
        2: "星期二",
        3: "星期三",
        4: "星期四",
        5: "星期五",
        6: "星期六",
        7: "星期日"
    }
    
    time_slot_names = {
        "0102": "第1-2节",
        "0304": "第3-4节",
        "0506": "第5-6节",
        "0708": "第7-8节",
        "091011": "第9-11节",
        "1213": "第12-13节"
    }
    
    result = []
    
    for day, time_slots in sorted(free_classrooms.items()):
        result.append(f"【{weekday_names[day]}】")
        
        for time_slot, classrooms in sorted(time_slots.items()):
            if classrooms:  # 如果有空闲教室
                result.append(f"  {time_slot_names[time_slot]}: {', '.join(classrooms)}")
            else:
                result.append(f"  {time_slot_names[time_slot]}: 无空闲教室")
        
        result.append("")  # 添加空行分隔不同天
    
    return "\n".join(result)

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
