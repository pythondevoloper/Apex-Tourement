# -*- coding: utf-8 -*-
"""Apex Tournament - O'YINCHILAR ilovasi (ro'yxatdan o'tish, draft, tarkib, jadval)."""
from common import *


class PlayerApp(LeagueApp):
    ADMIN_APP = False
    APP_TITLE = "Apex Tournament"
    CACHE_NAME = "apex_cache.json"


if __name__ == "__main__":
    PlayerApp().run()
