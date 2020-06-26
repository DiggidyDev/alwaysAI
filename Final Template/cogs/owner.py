from discord.ext import commands


class Owner(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="cog", aliases=["c"], hidden=True)
    @commands.is_owner()
    async def modify_cog(self, ctx, variant, *cog_list):
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

        embed = discord.Embed(title=variant, description=desc, colour=0x5288E5)
        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(Owner(bot))
