import discord


class ControlView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        from .music_view import Views

        self.add_item(Views.PauseResumeButton(guild_id))
        self.add_item(Views.SkipButton(guild_id))
        self.add_item(Views.StopButton(guild_id))
