import platform
import sys
import time
from io import StringIO

import discord
import psutil
from discord.ext import commands


class Owner(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.colour = discord.Color.blurple()

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)

    @commands.command(aliases=["e"], hidden=True)
    async def eval(self, ctx, *, code):
        old_stdout = sys.stdout
        result = StringIO()
        sys.stdout = result
        exec("async def __exc(self, ctx):\n    {}".format(code))
        await locals()["__exc"](self, ctx)
        sys.stdout = old_stdout
        result_string = result.getvalue()
        embed = discord.Embed(title="Evaluation",
                              description="Input:"
                                          "```python\n"
                                          "{}"
                                          "```\n\n"
                                          "Output:"
                                          "```python\n\u200b"
                                          "{}"
                                          "```".format(code,result_string),
                              colour=self.colour)
        await ctx.send(embed=embed)

    @commands.command(aliases=["c"], hidden=True)
    async def cog(self, ctx, variant, *cog_list):
        """
        :param ctx: Discord Context class
        :param variant: Type of cog modifier, can be: 'Load', 'Unload', 'Reload', 'Reloadall'
        :param cog_list: List of cogs to be modified
        """
        variant = variant.title().strip()
        desc = ""

        if len(cog_list) == 0 and variant != "Reloadall":
            await ctx.send("`ERROR: MissingRequiredArgument - missing cog arguments.`")

            return

        if variant not in ["Load", "Unload", "Reload"]:
            if variant == "Reloadall":
                cog_list = self.bot.cog_list

        for cog in cog_list:
            try:
                if variant in ["Unload", "Reload", "Reloadall"]:
                    self.bot.unload_extension(cog)
                if variant in ["Load", "Reload", "Reloadall"]:
                    self.bot.load_extension(cog)
                desc += "<:tick:671116183751360523> | {}\n".format(cog)
            except Exception as e:
                desc += "<:cross:671116183780720670> | {} ~ `{} - {}`\n".format(cog, type(e).__name__, e)

        embed = discord.Embed(title=variant, description=desc, colour=self.colour)
        await ctx.send(embed=embed)

    @commands.command(aliases=["system", "stats", "ping"])
    async def sys(self, ctx):
        t1 = time.time()
        async with ctx.typing():
            t2 = time.time()
            diff_ping = t2 - t1

            embed = discord.Embed(colour=self.colour)
            CPU = ":gear: **CPU**" \
                  "```" \
                  "{0:^18}|{1:^18}|{2:^18}\n" \
                  "{3:^18}|{4:^18}|{5:^18}\n" \
                  "```".format("Usage:", "Cores:", "Clock Speed:",
                               "{} %".format(psutil.cpu_percent()),
                               psutil.cpu_count(),
                               "{} GHz".format(psutil.cpu_freq().current / 1000)
                               )

            TOTAL = psutil.virtual_memory().total / 1024000000
            USED = psutil.virtual_memory().used / 1024000000
            PERCENT = USED * 100 / TOTAL
            AVAILABLE = TOTAL - USED

            RAM = "\n\n:bar_chart: **MEMORY**" \
                  "```" \
                  "{0:^18}|{1:^18}|{2:^18}\n" \
                  "{3:^18}|{4:^18}|{5:^18}" \
                  "```".format("Usage:", "Total:", "Available:",
                               "{}%".format(round(PERCENT, 1)),
                               "{} GB".format(round(TOTAL, 2)),
                               "{} GB".format(round(AVAILABLE, 2))
                               )

            PING = "\n\n:globe_with_meridians: **PING**" \
                   "```" \
                   "{0:^27}|{1:^27}\n" \
                   "{2:^27}|{3:^27}" \
                   "```".format("Websocket Ping:", "Heartbeat:",
                                "{} ms".format(round(diff_ping * 1000)),
                                "{} ms".format(round(self.bot.latency * 1000))
                                )

            template = CPU + RAM + PING
            embed.description = template
            embed.set_footer(text="Python {}\n"
                                  "Discord.py {}".format(platform.python_version(), discord.__version__))
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Owner(bot))
