import json
import os
import platform
import sys
import time
from io import StringIO

import discord
import psutil
from discord.ext import commands

from bot import generate_user_error_embed, send_traceback
from cogs.model import read_json, get_model_by_alias


class Owner(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.colour = discord.Color.blurple()
        self.admins = read_json("data/admins.json")["ids"]

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author) or ctx.author.id in self.admins

    async def cog_command_error(self, ctx, error):
        error_handled = False

        if hasattr(ctx.command, "on_error"):
            return

        if isinstance(error, discord.ext.commands.errors.CheckFailure):
            message = "```NoPermissions - You don't have the correct permissions to do this```\n\n" \
                      "If you believe you should then let the bot developer know."
            await generate_user_error_embed(ctx, message)
            error_handled = True

        if not error_handled:
            await send_traceback(ctx, error)

    @commands.group()
    async def alias(self, ctx):
        if not os.path.exists("logs"):
            os.mkdir("logs")

        logs = {}

        if os.path.isfile("logs/AliasModifications.json"):
            with open("logs/AliasModifications.json", "r") as fp:
                logs = json.load(fp)

        actions = {"add": "Added", "remove": "Removed", None: None}

        with open("logs/AliasModifications.json", "w+") as fp:

            data = {
                "User ID": ctx.author.id,
                "Action": actions[ctx.invoked_subcommand.name],
                "Alias": ctx.message.content.split()[2],
                "Model": ctx.message.content.split()[-1]
            }

            logs[f"{ctx.message.created_at.date()}"] = data

            json.dump(logs, fp, indent=4)

    @alias.command()
    async def add(self, ctx, alias, model):
        model = get_model_by_alias(model)
        if not model:
            await generate_user_error_embed(ctx, "No model was found with that name or alias.\n"
                                                 "Use `*mhelp` to see all available models.")

        with open("data/aliases.json", "r") as fp:
            aliases = json.load(fp)

        if alias not in aliases[model]:
            aliases[model].append(alias)

            with open("data/aliases.json", "w+") as fp:
                json.dump(aliases, fp, sort_keys=True, indent=4)

            embed = discord.Embed(title="Alias Modification",
                                  description=f"Successfully added `{alias}` to `{model}`'s aliases.",
                                  colour=0xC63D3D)
            await ctx.send(embed=embed)
        else:
            await generate_user_error_embed(ctx, "That alias already exists.\n"
                                                 f"Use `*mhelp {model}` to see all available aliases.")

    @alias.command()
    async def remove(self, ctx, alias, model):
        model = get_model_by_alias(model)
        if not model:
            await generate_user_error_embed(ctx, "No model was found with that name or alias.\n"
                                                 "Use `*mhelp` to see all available models.")

        with open("data/aliases.json", "r") as fp:
            aliases = json.load(fp)

        if alias in aliases[model]:
            aliases[model].remove(alias)

            with open("data/aliases.json", "w+") as fp:
                json.dump(aliases, fp, sort_keys=True, indent=4)

            embed = discord.Embed(title="Alias Modification",
                                  description=f"Successfully removed `{alias}` from `{model}`'s aliases.",
                                  colour=0xC63D3D)
            await ctx.send(embed=embed)
        else:
            await generate_user_error_embed(ctx, "That alias doesn't exist.\n"
                                                 f"Use `*mhelp {model}` to see all available aliases.")


    @commands.command(aliases=["e"], hidden=True)
    async def eval(self, ctx, *, code):
        async with ctx.typing():
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
                                              "```".format(code, result_string),
                                  colour=self.colour)
        await ctx.send(embed=embed)

    @commands.command(aliases=["c", "cogs"], hidden=True)
    async def cog(self, ctx, variant, *cog_list):
        """
        :param ctx: Discord Context class
        :param variant: Type of cog modifier, can be: 'Load', 'Unload', 'Reload', 'Reloadall'
        :param cog_list: List of cogs to be modified
        """
        async with ctx.typing():
            variant = variant.title().strip()
            desc = ""
            if variant not in ["Reloadall", "Reload", "Load", "Unload"]:
                message = "```InvalidVariation - please include a valid cog variation```\n\n" \
                          "For example: `*cog reload cogs.model`\n" \
                          "Variations are: load, unload, reload and reloadall"
                await generate_user_error_embed(ctx, message)
                return

            if len(cog_list) == 0 and variant != "Reloadall":
                message = "```MissingCogs - please include a the cogs you want to modify```\n\n" \
                          "For example: `*cog reload cogs.model`\n" \
                          "All cogs names will start with `cogs.`. For example cogs.model"
                await generate_user_error_embed(ctx, message)
                return

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

    @cog.error
    async def cog_error(self, ctx, error):
        error_handled = False

        # Singular errors
        if isinstance(error, discord.ext.commands.errors.MissingRequiredArgument):
            message = "```MissingVariation - please include a cog variation```\n\n" \
                      "For example: `*cog reload cogs.model`\n" \
                      "Variations are: load, unload, reload and reloadall"
            await generate_user_error_embed(ctx, message)
            error_handled = True

        if isinstance(error, discord.ext.commands.errors.CheckFailure):
            message = "```NoPermissions - You don't have the correct permissions to do this```\n\n" \
                      "If you believe you should then let the bot developer know."
            await generate_user_error_embed(ctx, message)
            error_handled = True

        if not error_handled:
            await send_traceback(ctx, error)

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


model_aliases = read_json("data/aliases.json")
