from aiohttp import web
from botbuilder.schemas import Activity, ActivityTypes


class CandidateSearchBot:
    def __init__(self):
        pass

    async def on_message_activity(self):

        pass

    async def process_and_reply(self):
        pass


Bot = CandidateSearchBot()


async def messages(req: web.Request) -> web.Response:
    """incoming requests from teams"""
    if "application/json" in req.headers["Content-Type"]:
        body = await req.json()
    else:
        return web.Response(status=415, text="Unsupported Media Type")

    activity = Activity().deserialize(body)
    auth_header = req.headers.get("Authorization", "")

    async def aux_func(turn_context):
        if activity.type == ActivityTypes.message:
            await Bot.on_message_activity(turn_context)
        else:
            await turn_context.send_activity("Unsupported activity type.")

    try:
        # add the adapter

        return web.Response(status=200, text="Message processed successfully")
    except Exception as e:
        print(f"Error processing message: {e}")
        return web.Response(status=500, text="Internal Server Error")
