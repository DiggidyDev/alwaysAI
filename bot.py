import traceback

import discord
from discord.ext import commands


class Bot(commands.Bot):
    def __init__(self):
        prefix = "*"
        super().__init__(command_prefix=prefix, description="Computer Vision is amazing",
                         activity=discord.Activity(type=discord.ActivityType.listening, name=prefix + "help"))
        self.cog_list = []

    async def on_ready(self):
        print("Name:\t{0}\nID:\t{1}".format(super().user.name, super().user.id))

    # TODO Make this log errors with the command + args used
    async def on_command_error(self, ctx, exception):
        if isinstance(exception, commands.errors.CommandNotFound):
            return
        else:
            tb_lines = traceback.format_exception(type(exception), exception, exception.__traceback__, 4)
            await ctx.send("An unexpected error occurred ~\n```Python\n{}```".format(''.join(tb_lines)))

    def run(self):
        super().run(open("token.secret", "r").read())

    def load_cog(self, cog):
        super().load_extension(cog)
        self.cog_list.append(cog)


if __name__ == "__main__":
    bot = Bot()
    bot.remove_command("help")
    bot.load_cog("cogs.owner")
    bot.load_cog("cogs.commands")
    bot.load_cog("cogs.model")
    bot.run()