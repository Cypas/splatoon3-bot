from collections import defaultdict
from datetime import datetime as dt, timedelta

from nonebot import on_command, logger, require
from nonebot.adapters import Event, Bot
from nonebot.typing import T_State

from .db_sqlite import get_or_set_user, get_user
from .utils import INTERVAL, bot_send, _check_session_handler, Kook_Bot, QQ_Bot, V12_Bot
from .sp3bot import push_latest_battle
from .sp3msg import get_statics

require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler

__all__ = ['start_push', 'stop_push', 'scheduler']


@on_command("start_push", aliases={'sp', 'push', 'start'}, block=True, rule=_check_session_handler).handle()
async def start_push(bot: Bot, event: Event, state: T_State):
    if isinstance(bot, QQ_Bot):
        await bot_send(bot, event, '暂不支持')
        return
    user_id = event.get_user_id()
    user = get_user(user_id=user_id)

    cmd_lst = event.get_plaintext().strip().split(' ')

    get_image = True
    if 't' in cmd_lst or 'text' in cmd_lst:
        get_image = False

    if user and user.push or scheduler.get_job(f'{user_id}_push'):
        logger.info(f'remove job {user_id}_push')
        try:
            scheduler.remove_job(f'{user_id}_push')
        except:
            pass

    push_cnt = user.push_cnt or 0
    push_cnt += 1

    get_or_set_user(user_id=user_id, push=True, push_cnt=push_cnt)

    group_id = ''

    _event = event.dict() or {}
    if _event.get('chat', {}).get('type') == 'group':
        group_id = _event['chat']['id']
    if _event.get('group_id'):
        group_id = _event['group_id']

    job_id = f'{user_id}_push'

    logger.info(f'add job {job_id}')
    job_data = {
        'user_id': user_id,
        'get_image': get_image,
        'push_cnt': 0,
        'nickname': user.nickname,
        'group_id': group_id,
        'job_id': job_id,
        'current_statics': defaultdict(int),
    }
    state['job_data'] = job_data
    scheduler.add_job(
        push_latest_battle, 'interval', seconds=INTERVAL, next_run_time=dt.now() + timedelta(seconds=3),
        id=job_id, args=[bot, event, job_data],
        misfire_grace_time=INTERVAL - 1, coalesce=True, max_instances=1
    )
    msg = f'Start push! check new data(battle or coop) every {INTERVAL} seconds. /stop_push to stop'
    if isinstance(bot, (V12_Bot, Kook_Bot)):
        str_i = '图片' if get_image else '文字'
        msg = f'开启{str_i}推送模式，每10秒钟查询一次最新数据(对战或打工)\n/stop_push 停止推送'
    await bot_send(bot, event, msg)


@on_command("stop_push", aliases={'stop', 'st', 'stp'}, block=True, rule=_check_session_handler).handle()
async def stop_push(bot: Bot, event: Event):
    if isinstance(bot, QQ_Bot):
        await bot_send(bot, event, '暂不支持')
        return
    msg = f'Stop push!'

    logger.info(msg)
    user_id = event.get_user_id()
    get_or_set_user(user_id=user_id, push=False)

    if isinstance(bot, (V12_Bot, Kook_Bot)):
        msg = '停止推送！'
        user = get_user(user_id=user_id)
        if not user.api_key:
            msg += '''\n/set_api_key 可保存数据到 stat.ink\n(App最多可查看最近50*5场对战和50场打工)'''

    job_id = f'{user_id}_push'
    logger.info(f'remove job {job_id}')
    try:
        r = scheduler.get_job(job_id)
        job_data = r.args[-1] or {}
        scheduler.remove_job(job_id)
    except:
        job_data = {}

    if job_data and job_data.get('current_statics') and job_data['current_statics'].get('TOTAL'):
        msg += get_statics(job_data['current_statics'])

    await bot_send(bot, event, msg, parse_mode='Markdown')
