import discord

class ControlView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None) # Timeout=None is crucial so the buttons don't expire
        from .music_view import Views
        # Add buttons to the view
        self.add_item(Views.PauseResumeButton(guild_id))
        self.add_item(Views.SkipButton(guild_id))
        self.add_item(Views.StopButton(guild_id))