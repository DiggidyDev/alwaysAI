import re
from subprocess import Popen, PIPE

import discord
from discord.ext import commands


class Commands(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.bot.docs = None
        self.bot.lookup = None

    async def get_docs(self):

        if not self.bot.docs:  # If the find command has already been used, then this acts as a cache, almost - it'll only need to fetch the docs once per boot/reload
            process = Popen(["python", "-m", "sphinx.ext.intersphinx", "https://alwaysai.co/docs/objects.inv"], stdout=PIPE)
            output = process.communicate()

            self.bot.docs = output  # Using a bot variable which will be used to create the lookup dict

        return self.bot.docs

    async def fetch(self, query):
        docs = await self.get_docs()

        if not self.bot.lookup:  # Create the lookup dict if it doesn't exist
            self.bot.lookup = {}
            sections = []

            for section in docs[0].decode("utf-8").split("py:")[1:]:

                sectors = section.split()  # Removing whitespace

                if sectors[0] == "module":
                    sectors = sectors[:sectors.index("std:doc")]  # Chop out extraneous data from the end
                    # TODO: ADD LABELS(?)

                sections.append(" ".join([s for s in sectors]))  # Replacing all of the whitespace with a single space

                links = [w for w in sectors if "/" in w]  # Grab each object's link
                attrs = [w for w in sectors if "/" not in w and "." in w]  # Grab each object

                # They're ordered like so with their respective links:
                #
                #    OBJECT.ATTR               #URL.EXT.FOR.OBJECT.ATTR
                #    ANOTHER.OBJECT.ATTR       #URL.EXT.FOR.ANOTHER.OBJECT.ATTR
                #
                #
                # Hence zipping it will group them correctly:
                #
                #    [("OBJECT.ATTR", "#URL.EXT.FOR.OBJECT.ATTR"), (...)]

                meta = zip(attrs, links)

                for a, l in meta:
                    self.bot.lookup[a] = f"https://alwaysai.co/docs/{l}"  # Assign the object's URL to the object

            self.bot.docs = " ".join(sections)  # Concatenating each of the sections: attribute, function, method, module, class


        pattern = re.compile(rf"\w*(\.*{query}\.*)\w*", re.IGNORECASE)
        indices = [(i.span()[0], i.span()[1]) for i in pattern.finditer(self.bot.docs)]  # Getting the indices of each search result in the sections' concatenation

        # Probably one of the more disgusting lines :/
        # Finds the entire word that was found - characters up to the previous and next space.
        # Sorts it alphabetically (and case-sensitively)
        suggestions = sorted({self.bot.docs[self.bot.docs.rfind(" ", 0, pos[0]) + 1:self.bot.docs.find(" ", pos[1])] for pos in indices
                          if "/" not in self.bot.docs[self.bot.docs.rfind(" ", 0, pos[0]) + 1:self.bot.docs.find(" ", pos[1])]})

        return suggestions

    @commands.command()
    async def help(self, ctx):
        """
        Just a help command that'll be useful some day soon.

        :param ctx:
        :return:
        """
        await ctx.send("~ W.I.P ~")

    @commands.command()
    async def find(self, ctx, *, query):
        suggestions = await self.fetch(query)  # Made asynchronous due to subprocess' Popen being a blocking call

        links = [self.bot.lookup[x] for x in suggestions]  # Get each object's link from the lookup dictionary created earlier

        # Removes the preceding edgeiq. from each object
        results = "\n".join([f"[`{r.replace('edgeiq.', '')}`]({l})" for l, r in zip(links, suggestions)])

        # General fancifying of the results
        results_count_true = len(links)
        results_short = results[:results.rfind("[", 0, 2048)] if len(results) > 2048 else results
        results_count = results_short.count("\n") + 1

        embed = discord.Embed(title=f"{results_count} Result{'s' if results_count != 1 else ''}",
                              description=results_short)

        filtered_results = results_count_true - results_count
        if filtered_results > 0:
            embed.set_footer(text=f"{filtered_results} other result{'s' if filtered_results != 1 else ''} found")

        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Commands(bot))
