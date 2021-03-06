import asyncio

import aiohttp_jinja2
import jinja2
from aiohttp import web

from .handlers import ApiHandler, PagesHandler, WSstatsHandler, WSChatHandler


async def init_app(agent, session, consumers, logger_stats, output_formatter,
                   debug=False, response_time_limit=0):
    app = web.Application()
    handler = ApiHandler(output_formatter, response_time_limit)
    pages = PagesHandler(debug)
    stats = WSstatsHandler()
    chat = WSChatHandler(output_formatter)
    consumers = [asyncio.ensure_future(i.call_service(agent.process)) for i in consumers]

    async def on_startup(app):
        app['consumers'] = consumers
        app['agent'] = agent
        app['client_session'] = session
        app['websockets'] = []
        app['logger_stats'] = logger_stats
        asyncio.ensure_future(agent.state_manager.prepare_db())

    async def on_shutdown(app):
        for c in app['consumers']:
            c.cancel()
        if app['client_session']:
            await app['client_session'].close()
        tasks = asyncio.all_tasks()
        for task in tasks:
            task.cancel()

    app.router.add_post('', handler.handle_api_request)
    app.router.add_get('/api/dialogs/{dialog_id}', handler.dialog)
    app.router.add_get('/api/user/{user_telegram_id}', handler.dialogs_by_user)
    app.router.add_get('/ping', pages.ping)
    app.router.add_get('/debug/current_load', stats.ws_page)
    app.router.add_get('/debug/current_load/ws', stats.ws_handler)
    app.router.add_get('/chat', chat.ws_page)
    app.router.add_get('/chat/ws', chat.ws_handler)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    aiohttp_jinja2.setup(app, loader=jinja2.PackageLoader('deeppavlov_agent.http_api', 'templates'))
    return app
