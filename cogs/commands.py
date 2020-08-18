import random
import re
from subprocess import Popen, PIPE

import discord
from discord.ext import commands

from bot import generate_user_error_embed, send_traceback
from cogs.model import get_model_info, get_model_aliases, get_model_by_alias, read_json


class Commands(commands.Cog):
    # TODO Install more models

    def __init__(self, bot):
        self.bot = bot
        self.bot.docs = None
        self.bot.lookup = None

    def get_docs(self):

        if not self.bot.docs:  # If the find command has already been used, then this acts as a cache, almost - it'll
            # only need to fetch the docs once per boot/reload
            process = Popen(["python", "-m", "sphinx.ext.intersphinx", "https://alwaysai.co/docs/objects.inv"],
                            stdout=PIPE, stderr=PIPE)
            output = process.communicate()

            self.bot.docs = output  # Using a bot variable which will be used to create the lookup dict

        return self.bot.docs

    async def fetch(self, query):
        docs = self.get_docs()

        if not self.bot.lookup:  # Create the lookup dict if it doesn't exist
            self.bot.lookup = {}
            sections = []

            # Doesn't like UTF-8 codec, hence cp1252.
            # Also force ignore errors. Only temporary though!
            for section in docs[0].decode("cp1252", "ignore").split("py:")[1:]:

                sectors = section.split()  # Removing whitespace

                if sectors[0] == "module":
                    sectors = sectors[:sectors.index("std:doc")]  # Chop out extraneous data from the end
                    # TODO: ADD LABELS(?)

                # Replacing all of the whitespace with a single space
                sections.append(" ".join([s for s in sectors[1:]]))

                links = [i for i in sectors if "/" in i]  # Grab each object's link
                objects = [i for i in sectors if "/" not in i and "." in i]  # Grab each object

                # They're ordered like so with their respective links:
                #
                #    OBJECT.ATTR               #URL.EXT.FOR.OBJECT.ATTR
                #    ANOTHER.OBJECT.ATTR       #URL.EXT.FOR.ANOTHER.OBJECT.ATTR
                #
                #
                # Hence zipping it will group them correctly:
                #
                #    [("OBJECT.ATTR", "#URL.EXT.FOR.OBJECT.ATTR"), (...)]
                meta = zip(objects, links)

                for o, l in meta:
                    self.bot.lookup[o] = "https://alwaysai.co/docs/{}".format(
                        l)  # Assign the object's URL to the object

            self.bot.docs = " ".join(
                sections)  # Concatenating each of the sections: attribute, function, method, module, class

        pattern = re.compile(r"\w*(\.*{}\.*)\w*".format(query), re.IGNORECASE)
        indices = [(i.span()[0], i.span()[1]) for i in pattern.finditer(
            self.bot.docs)]  # Getting the indices of each search result in the sections' concatenation

        # Probably one of the more disgusting lines :/ (I agree, my brain can't process the chaos)
        # Finds the entire word that was found - characters up to the previous and next space.
        # Sorts it alphabetically (and case-sensitively)
        suggestions = sorted(
            {self.bot.docs[self.bot.docs.rfind(" ", 0, pos[0]) + 1:self.bot.docs.find(" ", pos[1])] for pos in indices
             if "/" not in self.bot.docs[self.bot.docs.rfind(" ", 0, pos[0]) + 1:self.bot.docs.find(" ", pos[1])]})

        return suggestions

    @staticmethod
    async def model_help_react(message):
        await message.add_reaction("\U000023ea")  # Left fast
        await message.add_reaction("\U00002b05")  # Left
        await message.add_reaction("\U000027a1")  # Right
        await message.add_reaction("\U000023e9")  # Right fast
        await message.add_reaction("<:cross:671116183780720670>")  # Cross

    @staticmethod
    def limit(text, limit_int):
        text = str(text)
        if len(text) > limit_int:
            return text[:limit_int - 3] + "..."
        return text

    @commands.command(aliases=["h"])
    async def help(self, ctx, command=None):
        async with ctx.typing():
            help_data = read_json("data/help.json")

            title = help_data["default"]["title"]
            colour = 0xB91C36
            thumbnail = discord.File("data/HelpThumbnail.png", filename="thumbnail.png")

            # Retrieves command - useful if user wants to use a commands alias
            command = self.bot.get_command(str(command))

            if command is not None and command.name in help_data.keys():  # Command exists
                # Grabbing title, footer, description and notes (if that exists)
                title += help_data[command.name]["title"]
                description = "\n".join(help_data[command.name]["description"])
                footer = "" if len(command.aliases) == 0 else "Aliases: {}".format(", ".join(command.aliases))

                # Basically just a special formatted description addition
                if "formatted" in help_data[command.name].keys():
                    description += "{}\n\u200b".format("\n> ".join(help_data[command.name]["formatted"]))

                # Different colour for owner commands to help distinguish easier
                if command.cog.qualified_name == "Owner":
                    colour = 0xB32DBF
                    thumbnail = discord.File("data/AdminHelpThumbnail.png", filename="thumbnail.png")

            else:  # If no command exists it uses the default description
                description = "\n".join(help_data["default"]["description"])
                footer = ""

            embed = discord.Embed(title="{}**".format(title), description=description, colour=colour)
            embed.set_footer(text=footer)

            embed.set_thumbnail(url="attachment://thumbnail.png")
        await ctx.send(embed=embed, file=thumbnail)

    @commands.command(aliases=["i"])
    async def info(self, ctx):
        async with ctx.typing():  # Diggy#0649  TestedBubble#0745
            devs = ["Diggy#0649", "TestedBubble#0745"]
            random.shuffle(devs)
            description = "This bot was made by:\n" \
                          "`{}` and `{}`\n\n" \
                          "For help on using the bot, try using `*help` and `*help <command>`".format(devs[0], devs[1])
            embed = discord.Embed(title="**Info**", description=description, colour=0x4CD4E0)
        await ctx.send(embed=embed)

    @commands.command(aliases=["f", "search"])
    async def find(self, ctx, *queries):
        for query in queries:
            async with ctx.typing():
                # Made asynchronous due to subprocess' Popen being a blocking call
                suggestions = await self.fetch(query)

                # Get each object's link from the lookup dictionary created earlier
                links = [self.bot.lookup[s] for s in suggestions if s not in ["attribute", "function",
                                                                              "method", "module", "class"]]

                # Removes the preceding edgeiq. from each object
                results = "\n".join(["[`{}`]({})".format(r.replace("edgeiq.", ""), l) for l, r in zip(links,
                                                                                                      suggestions)])

                # General fancifying of the results
                results_count_true = len(links)
                results_short = results[:results.rfind("[", 0, 2048)] if len(results) > 2048 else results
                results_count = results_short.count("\n") + 1 if len(
                    results) <= 2048 and results_count_true != 0 else results_short.count("\n")

                embed = discord.Embed(title="{} Result{}".format(results_count, "s" if results_count != 1 else ""),
                                      description=results_short,
                                      colour=0x8b0048)

                filtered_results = results_count_true - results_count
                if filtered_results > 0:
                    embed.set_footer(
                        text="{} other result{} found".format(filtered_results, "s" if filtered_results != 1 else ""))

            await ctx.send(embed=embed)

    @find.error
    async def find_error(self, ctx, error):
        error_handled = False

        if isinstance(error, discord.ext.commands.errors.MissingRequiredArgument):
            message = "```MissingQuery - please include a query```\n\n" \
                      "For example: `*find Detection`\n" \
                      "This try to find anything in the docs with `Detection` in it's name."
            await generate_user_error_embed(ctx, message)
            error_handled = True

        if not error_handled:
            await send_traceback(ctx, error)

    @commands.command(aliases=["modelhelp", "mhelp", "mh"])
    async def model_help(self, ctx, model_name=None):
        model_name = get_model_by_alias(model_name)

        if model_name is None:  # No specified model so show list of models
            decoded_data = read_json("alwaysai.app.json")

            # Formatting all models into a 2D list - each inner list is an unformatted page
            models_per_page = 10
            model_list = list(decoded_data["models"].keys())
            models_split = [model_list[x:x + models_per_page] for x in range(0, len(model_list), models_per_page)]

            # Splitting the page lists into page strings and formatting them to make em look good
            pages = ["`{}`\n\u200b".format("`\n`".join(inner_list)) for inner_list in models_split]
            current_page_num = 0

            if len(pages) == 0:
                message = "```MissingModels - no models have been installed for this bot.```\n\n" \
                          "Unless you own the bot there's not much you can do.\n" \
                          "Try to contact the owner of the bot if you ever see this bug."
                await generate_user_error_embed(ctx, message)
                return

            title = "**Model List**"
            colour = 0x8b0048

            embed = discord.Embed(title=title, description=pages[current_page_num], colour=colour)
            embed.set_footer(text="Page: {}/{}".format(current_page_num + 1, len(pages)))

            embed_message = await ctx.send(embed=embed)
            await self.model_help_react(embed_message)

            # Logic behind whether a user reaction is accepted or not
            def check(reaction, user):
                valid_emoji_list = ["⏪", "⬅", "➡", "⏩", "<:cross:671116183780720670>"]
                return str(reaction) in valid_emoji_list and str(reaction.message) == str(embed_message) and \
                       user == ctx.author

            # Wait for a users reaction
            while True:
                reaction, user = await self.bot.wait_for("reaction_add", check=check)
                await embed_message.remove_reaction(str(reaction.emoji), user)

                emoji = str(reaction)

                page_changed = True

                if emoji == "<:cross:671116183780720670>":  # Close model_help embed
                    await embed_message.delete()
                    return

                elif emoji == "⏪" and current_page_num != 0:  # Go to first page
                    current_page_num = 0
                elif emoji == "⬅" and current_page_num != 0:  # Go back a page
                    current_page_num -= 1
                elif emoji == "➡" and current_page_num != len(pages) - 1:  # Go forward a page
                    current_page_num += 1
                elif emoji == "⏩" and current_page_num != len(pages) - 1:  # Go to last page
                    current_page_num = len(pages) - 1
                else:
                    page_changed = False

                if page_changed:  # Only need to edit the message if the page needs to be changed
                    embed = discord.Embed(title=title, description=pages[current_page_num], colour=colour)
                    embed.set_footer(text="Page: {}/{}".format(current_page_num + 1, len(pages)))

                    await embed_message.edit(embed=embed)

        else:
            async with ctx.typing():
                data = get_model_info(model_name)
                aliases = get_model_aliases(model_name)

                # Adding spaces between words
                # SemanticSegmentation -> Semantic Segmentation
                category_split = re.findall("[A-Z][^A-Z]*", data["model_parameters_purpose"])
                category = " ".join(category_split)

                embed_description = self.limit(data["description"], 1000)
                embed_license = self.limit(data["license"], 50)
                embed_inf_time = self.limit(data["inference_time"], 20)
                embed_framework = self.limit(data["model_parameters_framework_type"], 50)
                embed_dataset = self.limit(data["dataset"], 50)
                embed_version = self.limit(data["version"], 10)

                if aliases is None:
                    embed_aliases = None
                else:
                    embed_aliases = ", ".join(aliases[:-1])

                description = "**Description:** {}\n" \
                              "**Category:** {}\n" \
                              "**License:** {}\n\n" \
                              "**Inference Time:** {}\n" \
                              "**Framework:** {}\n" \
                              "**Dataset:** {}\n" \
                              "**Version:** {}\n\n" \
                              "**Aliases:** {}".format(embed_description,
                                                       category,
                                                       embed_license,
                                                       embed_inf_time,
                                                       embed_framework,
                                                       embed_dataset,
                                                       embed_version,
                                                       embed_aliases)

                embed = discord.Embed(title=data["id"],
                                      description=description,
                                      colour=0x8b0048)

                thumbnail = discord.File("data/{}.png".format(data["model_parameters_purpose"]),
                                         filename="thumbnail.png")
                embed.set_thumbnail(url="attachment://thumbnail.png")

                regex = re.compile(
                    r"^(?:http|ftp)s?://"  # http:// or https://
                    r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"  # domain...
                    r"localhost|"  # localhost...
                    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
                    r"(?::\d+)?"  # optional port
                    r"(?:/?|[/?]\S+)$", re.IGNORECASE)

                if re.match(regex, data["website_url"]) is not None:
                    embed.url = data["website_url"]
                    
                await ctx.send(embed=embed, file=thumbnail)

    @model_help.error
    async def model_help_error(self, ctx, error):
        error_handled = False

        # Wrapped errors e.g: discord.ext.commands.errors.CommandInvokeError: ... FileNotFoundError: ...
        error = getattr(error, "original", error)

        if isinstance(error, FileNotFoundError):
            message = "```InvalidModelName - please specify a valid model name```\n\n" \
                      "For example: `*mhelp alwaysai/enet`\n" \
                      "You can find all available models by running `*mhelp`"
            await generate_user_error_embed(ctx, message)
            error_handled = True

        if not error_handled:
            await send_traceback(ctx, error)


def setup(bot):
    bot.add_cog(Commands(bot))
