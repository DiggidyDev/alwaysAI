import re
from subprocess import Popen, PIPE
import discord
from discord.ext import commands

from cogs.model import get_model_info


class Commands(commands.Cog):
    # TODO Add in model list command
    # TODO Install more models
    # TODO Model install command - owner only

    def __init__(self, bot):
        self.bot = bot
        self.bot.docs = None
        self.bot.lookup = None

    def get_docs(self):

        if not self.bot.docs:  # If the find command has already been used, then this acts as a cache, almost - it'll
            # only need to fetch the docs once per boot/reload
            process = Popen(["python", "-m", "sphinx.ext.intersphinx", "https://alwaysai.co/docs/objects.inv"],
                            stdout=PIPE)
            output = process.communicate()

            self.bot.docs = output  # Using a bot variable which will be used to create the lookup dict

        return self.bot.docs

    async def fetch(self, query):
        docs = self.get_docs()

        if not self.bot.lookup:  # Create the lookup dict if it doesn't exist
            self.bot.lookup = {}
            sections = []

            # Doesn't like UTF-8 codec, hence \/
            for section in docs[0].decode("cp1252").split("py:")[1:]:

                sectors = section.split()  # Removing whitespace

                if sectors[0] == "module":
                    sectors = sectors[:sectors.index("std:doc")]  # Chop out extraneous data from the end
                    # TODO: ADD LABELS(?)

                sections.append(" ".join([s for s in sectors]))  # Replacing all of the whitespace with a single space

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

    @commands.command()
    async def help(self, ctx):
        """
        Just a help command that'll be useful some day soon.
        We should soooo do like *help <cmd> and then show what args each command takes
        It'd look funky - like how Dpys docs are really nice
        Sorry I just reaaaally like the docs
        """
        await ctx.send("~ W.I.P ~")

    @commands.command(aliases=["search"])
    async def find(self, ctx, *, query):
        suggestions = await self.fetch(query)  # Made asynchronous due to subprocess' Popen being a blocking call

        links = [self.bot.lookup[s] for s in suggestions]  # Get each object's link from the lookup dictionary
        # created earlier

        # Removes the preceding edgeiq. from each object
        results = "\n".join(["[`{}`]({})".format(r.replace("edgeiq.", ""), l) for l, r in zip(links, suggestions)])

        # General fancifying of the results
        results_count_true = len(links)
        results_short = results[:results.rfind("[", 0, 2048)] if len(results) > 2048 else results
        results_count = results_short.count("\n") + 1 if len(
            results) <= 2048 and results_count_true != 0 else results_short.count("\n")

        embed = discord.Embed(title="{} Result{}".format(results_count, "s" if results_count != 1 else ""),
                              description=results_short)

        filtered_results = results_count_true - results_count
        if filtered_results > 0:
            embed.set_footer(
                text="{} other result{} found".format(filtered_results, "s" if filtered_results != 1 else ""))

        await ctx.send(embed=embed)

    # TODO Error for no model name
    # TODO Error for invalid model name
    # TODO Potential char limiter needed for long descriptions due to embed char limitations
    @commands.command(aliases=["modelhelp", "mhelp", "mh"])
    async def model_help(self, ctx, model_name=None):
        if model_name is None:  # No specified model so show list of models
            # TODO Actually list the models with links and a functioning interactive reaction menu
            embed = discord.Embed(title="Test", description="LIST OF MODELS")
            print(get_model_info("alwaysai/enet"))
        else:
            data = get_model_info(model_name)
            description = "**Description:** {}\n" \
                          "**Category:** {}\n" \
                          "**License:** {}\n\n" \
                          "**Inference Time:** {}\n" \
                          "**Framework:** {}\n" \
                          "**Dataset:** {}\n" \
                          "**Version:** {}".format(data["description"],
                                                   data["model_parameters_purpose"],
                                                   data["license"],
                                                   data["inference_time"],
                                                   data["model_parameters_framework_type"],
                                                   data["dataset"],
                                                   data["version"])

            embed = discord.Embed(title=data["id"], url=data["website_url"], description=description, colour=0x8b0048)

        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Commands(bot))
