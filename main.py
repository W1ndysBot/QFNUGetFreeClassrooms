# script/QFNUGetFreeClassrooms/main.py

import logging
import os
import sys
import re
import json
import datetime
import time
import base64
from bs4 import BeautifulSoup
import colorlog
from io import BytesIO
from PIL import Image
import asyncio

# 添加项目根目录到sys.path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from app.config import *
from app.api import *
from app.switch import load_switch, save_switch
from app.scripts.QFNUGetFreeClassrooms.src.utils.session_manager import (
    get_session,
    reset_session,
)
from app.scripts.QFNUGetFreeClassrooms.src.utils.captcha_ocr import get_ocr_res
from app.scripts.QFNUGetFreeClassrooms.src.core.get_room_classtable import (
    get_room_classtable,
)
from app.api import send_group_msg, send_private_msg, delete_msg


# 数据存储路径，实际开发时，请将QFNUGetFreeClassrooms替换为具体的数据存放路径
DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "QFNUGetFreeClassrooms",
)


# 开学日期配置
SEMESTER_START_DATES = {
    "2023-2024-1": "2023-09-04",  # 2023-2024学年第一学期开学日期
    "2023-2024-2": "2024-02-26",  # 2023-2024学年第二学期开学日期
    "2024-2025-1": "2024-09-02",  # 2024-2025学年第一学期开学日期
    "2024-2025-2": "2025-02-17",  # 2024-2025学年第二学期开学日期
}


# 添加全局变量存储消息ID
QUERY_MESSAGE_IDS = []


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
    soup = BeautifulSoup(html_content, "html.parser")

    # 获取所有教室行
    classroom_rows = soup.select("#kbtable tr")

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
        cells = row.find_all("td")
        if len(cells) < 43:  # 确保行有足够的单元格
            continue

        # 获取教室名称
        classroom_name = cells[0].get_text().strip()

        # 遍历每天的每个时间段
        for day in range(1, 8):  # 1-7表示周一到周日
            for time_idx, time_period in enumerate(
                ["0102", "0304", "0506", "0708", "091011", "1213"]
            ):
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
def get_free_classrooms(
    classroom_schedule, all_classrooms, day_of_week=None, time_slot=None
):
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

            time_slots_to_process = (
                [time_slot]
                if time_slot is not None
                else ["0102", "0304", "0506", "0708", "091011", "1213"]
            )

            for slot in time_slots_to_process:
                # 获取该时间段有课的教室
                occupied_classrooms = set(
                    classroom_schedule.get(day, {}).get(slot, {}).keys()
                )

                # 计算空闲教室
                free_classrooms[day][slot] = [
                    room for room in all_classrooms if room not in occupied_classrooms
                ]

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
        7: "星期日",
    }

    time_slot_names = {
        "0102": "第1-2节",
        "0304": "第3-4节",
        "0506": "第5-6节",
        "0708": "第7-8节",
        "091011": "第9-11节",
        "1213": "第12-13节",
    }

    result = []

    for day, time_slots in sorted(free_classrooms.items()):
        result.append(f"【{weekday_names[day]}】")

        for time_slot, classrooms in sorted(time_slots.items()):
            if classrooms:  # 如果有空闲教室
                result.append(
                    f"  {time_slot_names[time_slot]}: {', '.join(classrooms)}"
                )
            else:
                result.append(f"  {time_slot_names[time_slot]}: 无空闲教室")

        result.append("")  # 添加空行分隔不同天

    return "\n".join(result)


# 处理验证码
async def handle_captcha():
    """获取并识别验证码"""
    session = get_session()
    rand_code_url = "http://zhjw.qfnu.edu.cn/jsxsd/verifycode.servlet"
    response = session.get(rand_code_url)

    if response.status_code != 200:
        logging.error(f"请求验证码失败，状态码: {response.status_code}")
        return None

    try:
        image = Image.open(BytesIO(response.content))
        return get_ocr_res(image)
    except Exception as e:
        logging.error(f"无法识别验证码: {e}")
        return None


# 生成登录所需的encoded字符串
def generate_encoded_string(user_account, user_password):
    """生成登录所需的encoded字符串"""
    # 对账号和密码分别进行base64编码
    account_b64 = base64.b64encode(user_account.encode()).decode()
    password_b64 = base64.b64encode(user_password.encode()).decode()

    # 拼接编码后的字符串
    encoded = f"{account_b64}%%%{password_b64}"

    return encoded


# 执行登录操作
async def login(random_code, encoded):
    """执行登录操作"""
    # 登录请求URL
    login_url = "http://zhjw.qfnu.edu.cn/jsxsd/xk/LoginToXkLdap"
    session = get_session()
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36",
        "Origin": "http://zhjw.qfnu.edu.cn",
        "Referer": "http://zhjw.qfnu.edu.cn/",
    }

    data = {
        "userAccount": "",
        "userPassword": "",
        "RANDOMCODE": random_code,
        "encoded": encoded,
    }

    return session.post(login_url, headers=headers, data=data, timeout=10)


# 模拟登录过程
async def simulate_login(user_account, user_password):
    """模拟登录过程"""
    session = get_session()
    # 访问教务系统首页，获取必要的cookie
    response = session.get("http://zhjw.qfnu.edu.cn/jsxsd/")
    if response.status_code != 200:
        logging.error("无法访问教务系统首页，请检查网络连接或教务系统的可用性。")
        return False

    for attempt in range(3):
        random_code = await handle_captcha()
        logging.info(f"验证码: {random_code}")
        encoded = generate_encoded_string(user_account, user_password)
        response = await login(random_code, encoded)
        logging.info(f"登录响应: {response.status_code}")

        if response.status_code == 200:
            if "验证码错误" in response.text:
                logging.warning(f"验证码识别错误，重试第 {attempt + 1} 次")
                continue
            if "密码错误" in response.text or "账号或密码错误" in response.text:
                logging.error("用户名或密码错误")
                return False

            # 检查是否成功登录
            main_page = session.get(
                "http://zhjw.qfnu.edu.cn/jsxsd/framework/xsMain.jsp"
            )
            if main_page.status_code != 200 or "登录" in main_page.text:
                logging.error("登录失败，无法访问主页")
                return False

            logging.info("登录成功!")
            return True
        else:
            logging.error("登录失败")
            return False

    logging.error("验证码识别错误，请重试")
    return False


# 检查会话是否有效
async def check_session_valid():
    """检查当前会话是否有效"""
    session = get_session()
    try:
        response = session.get(
            "http://zhjw.qfnu.edu.cn/jsxsd/framework/xsMain.jsp", timeout=5
        )
        return response.status_code == 200 and "登录" not in response.text
    except Exception as e:
        logging.error(f"检查会话状态时出错: {str(e)}")
        return False


# 保存会话到文件
def save_session_to_file():
    """将当前会话保存到文件"""
    session = get_session()
    session_file = os.path.join(DATA_DIR, "session.json")

    try:
        # 提取cookies
        cookies_dict = {name: value for name, value in session.cookies.items()}

        # 保存cookies到文件
        with open(session_file, "w") as f:
            json.dump(cookies_dict, f)

        logging.info("会话已保存到文件")
        return True
    except Exception as e:
        logging.error(f"保存会话失败: {str(e)}")
        return False


# 从文件加载会话
async def load_session_from_file():
    """从文件加载会话"""
    session_file = os.path.join(DATA_DIR, "session.json")

    if not os.path.exists(session_file):
        logging.info("会话文件不存在，需要重新登录")
        return False

    try:
        # 读取cookies
        with open(session_file, "r") as f:
            cookies_dict = json.load(f)

        # 将cookies加载到会话
        session = get_session()
        for name, value in cookies_dict.items():
            session.cookies.set(name, value)

        # 验证会话是否有效
        if await check_session_valid():
            logging.info("成功从文件加载有效会话")
            return True
        else:
            logging.info("从文件加载的会话已过期，需要重新登录")
            return False
    except Exception as e:
        logging.error(f"加载会话失败: {str(e)}")
        return False


# 确保登录状态
async def ensure_login():
    """确保已登录状态，如果会话无效则重新登录"""
    # 尝试从文件加载会话
    if await load_session_from_file() and await check_session_valid():
        return True

    # 如果加载失败或会话无效，重置会话并重新登录
    reset_session()

    try:
        # 加载账号密码
        credentials = load_account_and_password()
        user_account = credentials["account"]
        user_password = credentials["password"]

        # 尝试登录
        if await simulate_login(user_account, user_password):
            # 登录成功，保存会话
            save_session_to_file()
            return True
        else:
            logging.error("登录失败，请检查账号密码")
            return False
    except Exception as e:
        logging.error(f"登录过程中出错: {str(e)}")
        return False


# 获取当前学期
def get_current_term():
    """获取当前学期"""
    try:
        now = datetime.now()
        year = now.year
        month = now.month

        if month >= 9:
            start_year = year
            end_year = year + 1
            term = 1
        elif month <= 1:
            start_year = year - 1
            end_year = year
            term = 1
        else:
            start_year = year - 1
            end_year = year
            term = 2

        current_term = f"{start_year}-{end_year}-{term}"
        return current_term
    except Exception as e:
        logging.error(f"获取当前学期出错: {str(e)}")
        return "2024-2025-2"  # 默认返回当前学期


# 获取当前周次和星期
def get_current_week_and_day():
    """获取当前周次和星期"""
    try:
        term = get_current_term()

        # 获取学期开始日期
        start_date = SEMESTER_START_DATES.get(term)
        if not start_date:
            logging.warning(f"未找到学期 {term} 的开始日期，使用默认值")
            return 1, datetime.now().weekday() + 1

        # 计算当前是第几周和星期几
        today = datetime.now().date()
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()

        # 计算相差的天数
        days_diff = (today - start_date_obj).days

        # 如果是未来学期，并且当前日期早于开学日期，则模拟为第1周
        if days_diff < 0:
            current_week = 1
            # 使用当前星期几
            current_day = today.weekday() + 1  # weekday()返回0-6，对应周一到周日
        else:
            # 计算当前是第几周（从1开始）
            current_week = days_diff // 7 + 1

            # 如果超过20周，则限制为20周
            if current_week > 20:
                current_week = 20
            elif current_week < 1:
                current_week = 1

            # 计算当前是星期几（1-7，对应周一到周日）
            current_day = today.weekday() + 1  # weekday()返回0-6，对应周一到周日

        return current_week, current_day
    except Exception as e:
        logging.error(f"获取当前周次和星期出错: {str(e)}")
        # 默认返回第1周，当前星期
        return 1, datetime.now().weekday() + 1


# 获取所有教室列表
def get_all_classrooms(building_prefix=None):
    """获取所有教室列表，如果指定了建筑前缀，则只返回该建筑的教室"""
    # 尝试从配置文件加载教室列表
    classrooms_file = os.path.join(DATA_DIR, "classrooms.json")

    if os.path.exists(classrooms_file):
        try:
            with open(classrooms_file, "r", encoding="utf-8") as f:
                classrooms_data = json.load(f)
                all_rooms = classrooms_data.get("classrooms", [])
        except Exception as e:
            logging.error(f"读取教室配置文件出错: {str(e)}")
            # 使用默认教室列表
            all_rooms = get_default_classrooms()
    else:
        # 使用默认教室列表
        all_rooms = get_default_classrooms()

    if building_prefix:
        return [room for room in all_rooms if room.startswith(building_prefix)]
    return all_rooms


# 默认教室列表
def get_default_classrooms():
    """返回默认的教室列表"""
    return [
        "格物楼B201",
        "格物楼B202",
        "格物楼B203",
        "格物楼B204",
        "格物楼B205",
        "格物楼B206",
        "格物楼B207",
        "格物楼B208",
        "格物楼A101",
        "格物楼A102",
        "格物楼A103",
        "格物楼A104",
        "致知楼101",
        "致知楼102",
        "致知楼103",
        "致知楼104",
    ]


# 提取所有被占用的教室
def extract_occupied_rooms(result):
    """从查询结果中提取所有被占用的教室"""
    occupied_rooms = set()

    if "data" in result and result["data"]:
        for room_data in result["data"]:
            room_name = room_data.get("name", "")
            if room_name:
                occupied_rooms.add(room_name)

    return occupied_rooms


# 获取空闲教室
async def get_free_rooms(
    websocket, group_id, message_id, building_prefix=None, specific_day=None
):
    """获取空闲教室并发送到群"""

    if not await ensure_login():
        await send_group_msg(
            websocket,
            group_id,
            f"[CQ:reply,id={message_id}]❌❌❌登录教务系统失败，请联系管理员更新cookies",
        )
        await send_private_msg(
            websocket,
            owner_id[0],
            f"[CQ:reply,id={message_id}]❌❌❌空闲教室查询失败，请及时检查cookies，发送【存储教务账号密码+账号+密码】更新cookies",
        )
        return

    # 获取当前学期
    xnxqh = get_current_term()

    # 获取当前周次和星期
    current_week, current_day = get_current_week_and_day()

    # 如果指定了特定日期，则使用指定的日期
    if specific_day is not None:
        query_day = specific_day
    else:
        query_day = current_day

    # 如果指定了建筑前缀，则只查询该建筑
    room_name = building_prefix if building_prefix else ""

    try:
        # 查询空闲教室
        result = get_room_classtable(xnxqh, room_name, current_week, query_day)

        # 处理结果
        if "error" in result:
            await send_group_msg(
                websocket,
                group_id,
                f"[CQ:reply,id={message_id}]❌❌❌获取空闲教室失败: {result.get('error')}",
            )
            return

        # 解析结果，找出空闲教室
        all_rooms = get_all_classrooms(room_name)
        occupied_rooms = extract_occupied_rooms(result)
        free_rooms = [room for room in all_rooms if room not in occupied_rooms]

        # 格式化消息
        weekday_names = {
            1: "星期一",
            2: "星期二",
            3: "星期三",
            4: "星期四",
            5: "星期五",
            6: "星期六",
            7: "星期日",
        }

        message = f"【空闲教室查询结果】\n\n"
        message += f"学期: {xnxqh}\n"
        message += f"第{current_week}周 {weekday_names[query_day]}\n\n"

        if free_rooms:
            # 按教学楼分组
            buildings = {}
            for room in free_rooms:
                # 提取教学楼名称
                building = re.match(r"(.*?)[A-Z]?\d+", room)
                if building:
                    building_name = building.group(1)
                    if building_name not in buildings:
                        buildings[building_name] = []
                    buildings[building_name].append(room)

            # 格式化输出
            for building, rooms in buildings.items():
                message += f"{building}:\n"
                message += ", ".join(rooms) + "\n\n"
        else:
            message += "无空闲教室"

        # 发送消息
        await send_group_msg(
            websocket,
            group_id,
            f"[CQ:reply,id={message_id}]{message}",
        )

        # 延迟0.5秒后撤回"正在查询"的消息
        await asyncio.sleep(0.5)
        if QUERY_MESSAGE_IDS:

            for message_id in QUERY_MESSAGE_IDS:
                await delete_msg(websocket, message_id)
            QUERY_MESSAGE_IDS.clear()

    except Exception as e:
        logging.error(f"查询空闲教室出错: {str(e)}")
        await send_group_msg(
            websocket,
            group_id,
            f"[CQ:reply,id={message_id}]❌❌❌查询空闲教室出错: {str(e)}",
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
            # 处理查询空闲教室命令
            if raw_message.startswith("查空教室"):
                # 提取可能的建筑前缀
                building_prefix = None
                specific_day = None

                # 解析命令参数
                params = raw_message[4:].strip().split()

                # 如果没有参数，显示使用说明
                if not params:
                    usage_message = (
                        "【查空教室使用说明】\n\n"
                        "基本格式：查空教室 [教学楼] [日期]\n\n"
                        "示例：\n"
                        "- 查空教室 格物楼 （查询当天格物楼空闲教室）\n"
                        "- 查空教室 致知楼 今天 （查询今天致知楼空闲教室）\n"
                        "- 查空教室 格物楼 明天 （查询明天格物楼空闲教室）\n"
                        "- 查空教室 格物楼 后天 （查询后天格物楼空闲教室）\n\n"
                        "可用建筑：格物楼、致知楼等\n"
                        "可用日期：今天、明天、后天\n"
                        "默认只查全天无课的教室，后期自定义时间段待更新\n"
                        "支持节次的在线查询：https://freeclassrooms.w1ndys.top\n"
                    )
                    await send_group_msg(
                        websocket,
                        group_id,
                        f"[CQ:reply,id={message_id}]{usage_message}",
                    )
                    return

                if params:
                    building_prefix = params[0]

                    # 检查是否指定了日期
                    if len(params) > 1:
                        day_map = {"今天": None, "明天": 1, "后天": 2}
                        day_param = params[1]

                        if day_param in day_map:
                            if day_map[day_param] is not None:
                                current_day = datetime.now().weekday() + 1
                                specific_day = (current_day + day_map[day_param]) % 7
                                if specific_day == 0:
                                    specific_day = 7

                await send_group_msg(
                    websocket,
                    group_id,
                    f"[CQ:reply,id={message_id}]正在查询空闲教室，请稍候...",
                )
                await get_free_rooms(
                    websocket, group_id, message_id, building_prefix, specific_day
                )
                return
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
        message_id = str(msg.get("message_id"))
        authorized = user_id in owner_id
        # 私聊消息处理逻辑
        await save_account_and_password(
            websocket, user_id, message_id, raw_message, authorized
        )
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
        echo = msg.get("echo", "")
        if echo and echo.startswith("send_group_msg_") and "正在查询空闲教室" in echo:
            # 存储消息ID用于后续撤回
            message_id = msg.get("data", {}).get("message_id")
            if message_id:
                QUERY_MESSAGE_IDS.append(message_id)
                logging.info(f"查询空闲教室消息ID: {message_id}")

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
